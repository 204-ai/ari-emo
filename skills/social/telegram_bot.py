"""
Ari Telegram Bot — Bridges Telegram messages to the Ari chat backend.

Supports group chats and DMs. Responds when mentioned by name or replied to.
Forwards messages to the Next.js /api/chat endpoint and streams responses back.

Usage:
  python telegram_bot.py

Requires:
  - TELEGRAM_BOT_TOKEN in .env.local or environment
  - Next.js app running at http://localhost:3000
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path

import httpx
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode, ChatAction

# ── Config ──────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent
logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("ari-telegram")

# Load token from .env.local
def load_env():
    env_file = ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

load_env()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_API = os.environ.get("ARI_CHAT_API", "http://localhost:3000/api/chat")
TELEGRAM_FEED_API = os.environ.get("ARI_TELEGRAM_FEED", "http://localhost:3000/api/telegram")
BOT_NAME = "ari"

# Track session IDs per chat
sessions: dict[int, str] = {}


# ── Helpers ─────────────────────────────────────────────────────────

def should_respond(update: Update) -> bool:
    """Decide if the bot should respond to this message."""
    msg = update.message
    if not msg or not msg.text:
        return False

    # Always respond in private/DM
    if msg.chat.type == "private":
        return True

    # In groups: respond if mentioned by name, replied to, or @username
    text_lower = msg.text.lower()

    # Check @mention
    if msg.entities:
        for entity in msg.entities:
            if entity.type == "mention":
                mention = msg.text[entity.offset:entity.offset + entity.length].lower()
                if BOT_NAME in mention:
                    return True

    # Check name mention in text
    if BOT_NAME in text_lower:
        return True

    # Check if replying to the bot
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.is_bot:
            return True

    return False


def clean_message(text: str, bot_username: str | None) -> str:
    """Strip bot mentions from the message text."""
    if bot_username:
        text = text.replace(f"@{bot_username}", "").strip()
    # Remove casual "ari" prefix/mention
    text = re.sub(r"(?i)^ari[,:]?\s*", "", text).strip()
    return text or text


async def stream_chat_response(message: str, chat_id: int) -> str:
    """Send message to Ari's chat API and collect the full response."""
    session_id = sessions.get(chat_id)

    payload: dict = {"message": message}
    if session_id:
        payload["sessionId"] = session_id

    full_text = ""

    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream("POST", CHAT_API, json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                log.error("Chat API error %d: %s", resp.status_code, body.decode())
                return "Squeak! Something went wrong with my brain... try again?"

            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                lines = buffer.split("\n")
                buffer = lines.pop()

                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Extract session ID
                    if event.get("type") == "result" and event.get("session_id"):
                        sessions[chat_id] = event["session_id"]

                    # Extract assistant text
                    if event.get("type") == "assistant" and event.get("message"):
                        text_blocks = [
                            b["text"]
                            for b in event["message"].get("content", [])
                            if b.get("type") == "text"
                        ]
                        if text_blocks:
                            full_text = "".join(text_blocks)

                    # Final result text
                    if event.get("type") == "result" and event.get("result"):
                        result_text = str(event["result"])
                        if result_text:
                            full_text = result_text

    return full_text or "..."


def extract_media(text: str) -> tuple[str, list[Path]]:
    """Extract media file references from response text and return cleaned text + file paths."""
    media_files = []

    # Match markdown images: ![alt](/api/image?file=filename.png)
    for match in re.finditer(r"!\[([^\]]*)\]\(/api/image\?file=([^)]+)\)", text):
        alt_text, filename = match.group(1), match.group(2)
        file_path = ROOT / "generated" / filename
        if file_path.exists():
            media_files.append(file_path)

    # Match direct file paths in text: generated/something.png or generated/something.mp4
    for match in re.finditer(r"(?:generated/|C:\\[^\s]+\\generated\\)([\w\-]+\.(?:png|jpg|jpeg|gif|mp4|webm|mov))", text):
        filename = match.group(1)
        file_path = ROOT / "generated" / filename
        if file_path.exists() and file_path not in media_files:
            media_files.append(file_path)

    # Remove image markdown from text (we'll send them as actual files)
    cleaned = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", "", text)
    # Clean up any leftover blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    return cleaned, media_files


def format_for_telegram(text: str) -> str:
    """Clean up markdown for Telegram (basic formatting)."""
    # Convert image markdown to text (Telegram can't render these)
    text = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"[\1]", text)
    return text.strip()


async def push_to_feed(chat_id: int, chat_title: str, user_name: str,
                       user_message: str, ari_response: str, has_media: bool = False):
    """Push a message exchange to the web UI feed."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(TELEGRAM_FEED_API, json={
                "chatId": chat_id,
                "chatTitle": chat_title,
                "userName": user_name,
                "userMessage": user_message,
                "ariResponse": ari_response,
                "hasMedia": has_media,
            })
    except Exception as e:
        log.debug("Failed to push to feed: %s", e)


VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
ANIMATION_EXTENSIONS = {".gif"}


async def send_media_files(msg, media_files: list[Path]):
    """Send media files to the Telegram chat."""
    for file_path in media_files:
        ext = file_path.suffix.lower()
        try:
            if ext in VIDEO_EXTENSIONS:
                log.info("Sending video: %s", file_path.name)
                await msg.reply_video(
                    video=open(file_path, "rb"),
                    caption=file_path.stem.replace("_", " "),
                    read_timeout=120,
                    write_timeout=120,
                )
            elif ext in ANIMATION_EXTENSIONS:
                log.info("Sending animation: %s", file_path.name)
                await msg.reply_animation(
                    animation=open(file_path, "rb"),
                    caption=file_path.stem.replace("_", " "),
                )
            elif ext in IMAGE_EXTENSIONS:
                log.info("Sending photo: %s", file_path.name)
                await msg.reply_photo(
                    photo=open(file_path, "rb"),
                    caption=file_path.stem.replace("_", " "),
                )
            else:
                log.info("Sending document: %s", file_path.name)
                await msg.reply_document(
                    document=open(file_path, "rb"),
                    caption=file_path.stem.replace("_", " "),
                )
        except Exception as e:
            log.error("Failed to send media %s: %s", file_path.name, e)
            # Try as document fallback
            try:
                await msg.reply_document(
                    document=open(file_path, "rb"),
                    caption=file_path.stem.replace("_", " "),
                )
            except Exception as e2:
                log.error("Document fallback also failed: %s", e2)


# ── Handlers ────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "Hey there! I'm Ari, a cute little hamster living in a terminal. "
        "Talk to me in this chat or mention my name in a group!\n\n"
        "Commands:\n"
        "/start — Say hello\n"
        "/reset — Start a fresh conversation\n"
        "/emotion — Check my current mood"
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset the conversation session."""
    chat_id = update.effective_chat.id
    if chat_id in sessions:
        del sessions[chat_id]
    await update.message.reply_text("Fresh start! My memory of our chat is reset.")


async def cmd_emotion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current emotion."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("http://localhost:3000/api/emotion")
            data = resp.json()
            await update.message.reply_text(f"I'm feeling: {data.get('emotion', 'neutral')}")
    except Exception:
        await update.message.reply_text("Can't check my mood right now!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    if not should_respond(update):
        return

    msg = update.message
    chat_id = msg.chat.id
    bot_username = context.bot.username
    user_text = clean_message(msg.text, bot_username)

    if not user_text:
        return

    user_name = msg.from_user.first_name if msg.from_user else "someone"
    log.info("Message from %s (chat %d): %s", user_name, chat_id, user_text[:100])

    # Show typing indicator
    await msg.chat.send_action(ChatAction.TYPING)

    # Prefix with user name for context in groups
    prompt = user_text
    if msg.chat.type != "private":
        prompt = f"[{user_name} says]: {user_text}"

    # Get response from Ari
    response_text = await stream_chat_response(prompt, chat_id)

    # Extract media files before formatting
    cleaned_text, media_files = extract_media(response_text)
    formatted = format_for_telegram(cleaned_text)

    # Send text response
    if formatted:
        for i in range(0, len(formatted), 4096):
            chunk = formatted[i:i + 4096]
            try:
                await msg.reply_text(chunk)
            except Exception as e:
                log.error("Failed to send message: %s", e)

    # Send media files
    await send_media_files(msg, media_files)

    # Push to web UI feed
    chat_title = msg.chat.title or ("DM" if msg.chat.type == "private" else "Group")
    await push_to_feed(chat_id, chat_title, user_name, user_text, formatted, bool(media_files))


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages — download and forward to chat API."""
    msg = update.message
    if not msg or not msg.photo:
        return

    # Only respond if we should (DM or mentioned)
    if msg.chat.type != "private" and not (msg.caption and BOT_NAME in msg.caption.lower()):
        return

    chat_id = msg.chat.id
    await msg.chat.send_action(ChatAction.TYPING)

    # Download the largest photo
    photo = msg.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    # Save to uploads dir
    uploads_dir = ROOT / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    local_path = uploads_dir / f"tg_{photo.file_unique_id}.jpg"
    await file.download_to_drive(str(local_path))

    caption = msg.caption or "What do you see in this image?"
    caption = clean_message(caption, context.bot.username)

    user_name = msg.from_user.first_name if msg.from_user else "someone"
    prompt = f"[{user_name} sent a photo]: {caption}"

    # Send with image path
    session_id = sessions.get(chat_id)
    payload: dict = {
        "message": prompt,
        "imagePaths": [str(local_path.resolve())],
    }
    if session_id:
        payload["sessionId"] = session_id

    full_text = ""
    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream("POST", CHAT_API, json=payload) as resp:
            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                lines = buffer.split("\n")
                buffer = lines.pop()
                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "result" and event.get("session_id"):
                        sessions[chat_id] = event["session_id"]
                    if event.get("type") == "assistant" and event.get("message"):
                        texts = [b["text"] for b in event["message"].get("content", []) if b.get("type") == "text"]
                        if texts:
                            full_text = "".join(texts)
                    if event.get("type") == "result" and event.get("result"):
                        full_text = str(event["result"])

    response = full_text or "I see a photo but I'm having trouble thinking right now!"
    cleaned_text, media_files = extract_media(response)
    formatted = format_for_telegram(cleaned_text)

    if formatted:
        for i in range(0, len(formatted), 4096):
            await msg.reply_text(formatted[i:i + 4096])

    await send_media_files(msg, media_files)

    # Push to web UI feed
    user_name = msg.from_user.first_name if msg.from_user else "someone"
    chat_title = msg.chat.title or ("DM" if msg.chat.type == "private" else "Group")
    await push_to_feed(chat_id, chat_title, user_name, f"[photo] {caption}", formatted, bool(media_files))


# ── Main ────────────────────────────────────────────────────────────

async def post_init(app: Application):
    """Set bot commands after startup."""
    await app.bot.set_my_commands([
        BotCommand("start", "Say hello to Ari"),
        BotCommand("reset", "Start a fresh conversation"),
        BotCommand("emotion", "Check Ari's current mood"),
    ])
    me = await app.bot.get_me()
    log.info("Bot started: @%s (id: %d)", me.username, me.id)


def main():
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set. Add it to .env.local")
        return 1

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("emotion", cmd_emotion))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Starting Ari Telegram bot (polling mode)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
