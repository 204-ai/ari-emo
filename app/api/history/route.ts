import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export const runtime = "nodejs";

const SESSIONS_DIR = path.join(process.cwd(), "memories", "sessions");

interface ParsedMessage {
  role: "user" | "assistant";
  content: string;
  time?: string;
}

function parseSessionFile(content: string): { summary: string; messages: ParsedMessage[] } {
  const lines = content.split("\n");
  const messages: ParsedMessage[] = [];
  let summary = "";
  let current: ParsedMessage | null = null;
  let contentLines: string[] = [];

  const flushCurrent = () => {
    if (current) {
      current.content = contentLines.join("\n").trim();
      if (current.content) messages.push(current);
    }
    current = null;
    contentLines = [];
  };

  for (const line of lines) {
    // Session header (# Session ...)
    if (line.startsWith("# ") && !summary) {
      summary = line.replace(/^#\s*/, "");
      continue;
    }

    // Skip sub-headers like ## Summary, ## Transcript
    if (/^#{2,}\s+(Summary|Transcript|Files)/.test(line)) continue;
    if (line.trim() === "(ongoing)") continue;

    // New format: [HH:MM:SS] **User**: ... or [HH:MM:SS] **Ari**: ...
    const newFmt = line.match(/^\[(\d{2}:\d{2}:\d{2})\]\s+\*\*(User|Ari)\*\*:\s*(.*)$/);
    if (newFmt) {
      flushCurrent();
      const [, time, speaker, text] = newFmt;
      current = { role: speaker === "User" ? "user" : "assistant", content: "", time };
      if (text.trim()) contentLines.push(text.trim());
      continue;
    }

    // Old format: ### HH:MM — User (Dimitri) or ### HH:MM — Ari
    const oldFmt = line.match(/^###\s+(\d{2}:\d{2})\s+[—–-]\s+(User|Ari)/);
    if (oldFmt) {
      flushCurrent();
      const [, time, speaker] = oldFmt;
      current = { role: speaker === "User" ? "user" : "assistant", content: "", time: time + ":00" };
      continue;
    }

    // Collect content lines for current message
    if (current) {
      // Strip blockquote markers for old-format user messages
      const stripped = line.replace(/^>\s?/, "");
      contentLines.push(stripped);
    }
  }

  flushCurrent();
  return { summary, messages };
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const before = searchParams.get("before"); // filename to load before

    // Ensure directory exists
    if (!fs.existsSync(SESSIONS_DIR)) {
      return NextResponse.json({ session: null, hasMore: false });
    }

    // Get all session files sorted by name (newest last)
    const files = fs.readdirSync(SESSIONS_DIR)
      .filter((f) => f.endsWith(".md"))
      .sort();

    if (files.length === 0) {
      return NextResponse.json({ session: null, hasMore: false });
    }

    let targetIndex: number;
    if (before) {
      // Find the file before the given one
      const idx = files.indexOf(before);
      if (idx <= 0) {
        return NextResponse.json({ session: null, hasMore: false });
      }
      targetIndex = idx - 1;
    } else {
      // Load the most recent session
      targetIndex = files.length - 1;
    }

    const filename = files[targetIndex];
    const filepath = path.join(SESSIONS_DIR, filename);
    const content = fs.readFileSync(filepath, "utf-8");
    const { summary, messages } = parseSessionFile(content);

    // Extract date from filename (YYYY-MM-DD_HHMM.md)
    const dateMatch = filename.match(/^(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})/);
    const date = dateMatch
      ? `${dateMatch[1]} ${dateMatch[2]}:${dateMatch[3]}`
      : filename;

    return NextResponse.json({
      session: { filename, date, summary, messages },
      hasMore: targetIndex > 0,
    });
  } catch (err) {
    console.error("[history] Error:", err);
    return NextResponse.json({ error: "Failed to load history" }, { status: 500 });
  }
}
