/**
 * /api/telegram — Telegram message feed
 *
 * GET  → returns latest messages (up to ?limit=50)
 * POST → push a new message from the bot
 */

export const runtime = "nodejs";

interface TelegramMessage {
  id: number;
  timestamp: string;
  chatId: number;
  chatTitle: string;
  userName: string;
  userMessage: string;
  ariResponse: string;
  hasMedia: boolean;
}

// In-memory ring buffer (latest 200 messages)
const MAX_MESSAGES = 200;
const messages: TelegramMessage[] = [];
let nextId = 1;

export async function GET(req: Request) {
  const url = new URL(req.url);
  const limit = Math.min(parseInt(url.searchParams.get("limit") || "50"), MAX_MESSAGES);
  const since = parseInt(url.searchParams.get("since") || "0");

  const filtered = since > 0
    ? messages.filter((m) => m.id > since)
    : messages.slice(-limit);

  return Response.json({
    messages: filtered,
    lastId: messages.length > 0 ? messages[messages.length - 1].id : 0,
  });
}

export async function POST(req: Request) {
  const body = await req.json();

  const msg: TelegramMessage = {
    id: nextId++,
    timestamp: body.timestamp || new Date().toISOString(),
    chatId: body.chatId || 0,
    chatTitle: body.chatTitle || "DM",
    userName: body.userName || "Unknown",
    userMessage: body.userMessage || "",
    ariResponse: body.ariResponse || "",
    hasMedia: body.hasMedia || false,
  };

  messages.push(msg);
  if (messages.length > MAX_MESSAGES) {
    messages.splice(0, messages.length - MAX_MESSAGES);
  }

  return Response.json({ ok: true, id: msg.id });
}
