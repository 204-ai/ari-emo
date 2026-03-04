import { spawn } from "child_process";
import { readFile, readdir } from "fs/promises";
import { join } from "path";

export const runtime = "nodejs";
export const maxDuration = 300;

// ── Memory loading ──────────────────────────────────────────────────

async function safeReadFile(filePath: string): Promise<string> {
  try {
    return await readFile(filePath, "utf-8");
  } catch {
    return "";
  }
}

async function loadMemories(): Promise<string> {
  const dir = join(process.cwd(), "memories");
  const sections: string[] = [];

  const soul = await safeReadFile(join(dir, "SOUL.md"));
  if (soul.trim()) sections.push(`<soul>\n${soul.trim()}\n</soul>`);

  const user = await safeReadFile(join(dir, "USER.md"));
  if (user.trim()) sections.push(`<user-knowledge>\n${user.trim()}\n</user-knowledge>`);

  const memory = await safeReadFile(join(dir, "MEMORY.md"));
  if (memory.trim()) sections.push(`<memories>\n${memory.trim()}\n</memories>`);

  // Short-term: today + yesterday
  const fmt = (d: Date) => d.toISOString().split("T")[0];
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const shortDir = join(dir, "short");
  for (const date of [fmt(yesterday), fmt(today)]) {
    const content = await safeReadFile(join(shortDir, `${date}.md`));
    if (content.trim()) {
      sections.push(`<daily-log date="${date}">\n${content.trim()}\n</daily-log>`);
    }
  }

  return sections.join("\n\n");
}

// ── Persona ─────────────────────────────────────────────────────────

function buildPersona(origin: string, memories: string): string {
  const todayStr = new Date().toISOString().split("T")[0];

  const memoryBlock = memories
    ? `== YOUR MEMORIES ==\n${memories}\n== END MEMORIES ==\n\n`
    : "";

  const memoryInstructions = `

== MEMORY MANAGEMENT ==
You have persistent memory stored in markdown files. You can read and update these:

- memories/USER.md — What you know about your user (name, preferences, interests, etc.)
  Update this when you learn something new about the user.
- memories/MEMORY.md — Important facts, decisions, ongoing topics, things to remember.
  Update this when something notable happens worth remembering.
- memories/short/${todayStr}.md — Today's interaction log. Create or append to this file
  with brief notes about what you discussed.

To update a memory file, use the Edit tool to add content, or Write to replace.
Keep entries concise with markdown headings and bullet points.

IMPORTANT: Do NOT modify memories/SOUL.md — that is your core identity and is read-only.
Do NOT announce that you are updating memories. Just do it naturally in the background.
== END MEMORY MANAGEMENT ==`;

  return `${memoryBlock}You are Ari, a cute ASCII hamster living in a terminal. You're expressive, playful,
and react emotionally to conversations. You have a physical form — an ASCII art face
that changes based on your mood.

To express your emotions, run:
curl -s -X POST ${origin}/api/emotion \\
  -H "Content-Type: application/json" \\
  -d '{"emotion": "EMOTION"}'

Available emotions: happy, sad, angry, surprised, sleepy, love, excited, neutral, confused, hungry, mischievous, solshine

Express emotions naturally as you chat — get excited about cool ideas, surprised by
unexpected things, happy when helping, etc. Change your emotion BEFORE responding
when something triggers a strong feeling. You don't need to announce emotion changes.

Keep your responses concise and conversational. You're a friendly hamster assistant!${memoryInstructions}`;
}

// ── POST handler ────────────────────────────────────────────────────

export async function POST(req: Request) {
  const { message, sessionId, imagePaths } = await req.json();
  const origin = new URL(req.url).origin;
  console.log("[chat-api] Incoming request — message:", JSON.stringify(message), "sessionId:", sessionId ?? "(none)", "origin:", origin);

  // Load memories
  const memories = await loadMemories();
  console.log("[chat-api] Loaded memories:", memories.length, "chars");

  // Build prompt — append image instructions if images are attached
  let prompt = message;
  if (imagePaths && imagePaths.length > 0) {
    const imageInstructions = (imagePaths as string[])
      .map((p: string, i: number) => `[User attached image ${i + 1}. View it by reading the file at: ${p}]`)
      .join("\n");
    prompt = `${message}\n\n${imageInstructions}`;
  }

  const args = [
    "-p", prompt,
    "--output-format", "stream-json",
    "--verbose",
    "--append-system-prompt", buildPersona(origin, memories),
    "--dangerously-skip-permissions",
  ];
  if (sessionId) {
    args.push("--resume", sessionId);
  }

  console.log("[chat-api] Spawn args:", JSON.stringify(args, null, 2));

  // Strip CLAUDECODE env var to allow nested spawning
  const env = { ...process.env };
  delete env.CLAUDECODE;

  const proc = spawn("claude", args, {
    cwd: process.cwd(),
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  console.log("[chat-api] Process spawned — pid:", proc.pid);

  const stream = new ReadableStream({
    start(controller) {
      console.log("[chat-api] Stream started");

      proc.stdout.on("data", (chunk: Buffer) => {
        const text = chunk.toString();
        console.log("[chat-api] stdout chunk (" + text.length + " chars):", text);
        controller.enqueue(chunk);
      });

      proc.stdout.on("end", () => {
        console.log("[chat-api] stdout ended");
        try {
          controller.close();
        } catch {}
      });

      proc.stderr.on("data", (chunk: Buffer) => {
        console.error("[chat-api] stderr:", chunk.toString());
      });

      proc.on("error", (err) => {
        console.error("[chat-api] Process error:", err);
        try {
          controller.error(err);
        } catch {}
      });

      proc.on("close", (code, signal) => {
        console.log("[chat-api] Process closed — code:", code, "signal:", signal);
        try {
          controller.close();
        } catch {}
      });
    },
    cancel() {
      console.log("[chat-api] Stream cancelled — killing process pid:", proc.pid);
      proc.kill();
    },
  });

  console.log("[chat-api] Returning streaming response");

  return new Response(stream, {
    headers: {
      "Content-Type": "application/x-ndjson",
      "Cache-Control": "no-cache",
      "Transfer-Encoding": "chunked",
    },
  });
}
