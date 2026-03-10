import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export const runtime = "nodejs";

const SESSIONS_DIR = path.join(process.cwd(), "memories", "sessions");

function getTimestamp(): string {
  return new Date().toLocaleTimeString("en-US", { hour12: false });
}

function generateSessionFilename(): string {
  const now = new Date();
  const date = now.toISOString().slice(0, 10); // YYYY-MM-DD
  const time = now.toTimeString().slice(0, 5).replace(":", ""); // HHMM
  return `${date}_${time}.md`;
}

export async function POST(request: Request) {
  try {
    const { role, content, sessionFile } = await request.json();

    if (!role || !content) {
      return NextResponse.json({ error: "Missing role or content" }, { status: 400 });
    }

    // Ensure sessions directory exists
    fs.mkdirSync(SESSIONS_DIR, { recursive: true });

    // Use existing session file or create new one
    let filename = sessionFile;
    if (!filename) {
      filename = generateSessionFilename();
      const filepath = path.join(SESSIONS_DIR, filename);
      const header = `# Session ${new Date().toISOString().slice(0, 10)} ${new Date().toTimeString().slice(0, 5)}\n\n`;
      fs.writeFileSync(filepath, header);
    }

    const filepath = path.join(SESSIONS_DIR, filename);
    const timestamp = getTimestamp();
    const prefix = role === "user" ? "**User**" : "**Ari**";
    const entry = `\n[${timestamp}] ${prefix}: ${content}\n`;

    fs.appendFileSync(filepath, entry);

    return NextResponse.json({ sessionFile: filename });
  } catch (err) {
    console.error("[session-log] Error:", err);
    return NextResponse.json({ error: "Failed to log session" }, { status: 500 });
  }
}
