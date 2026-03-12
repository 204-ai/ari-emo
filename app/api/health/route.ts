import { NextResponse } from "next/server";

const TTS_SERVER = "http://127.0.0.1:8191";
const WHISPER_URL = process.env.WHISPER_URL || "http://127.0.0.1:8190";
const MEMORY_SERVER_URL =
  process.env.MEMORY_SERVER_URL || "http://127.0.0.1:8192";
const COMFYUI_URL = process.env.COMFYUI_URL || "http://localhost:8189";

async function checkService(url: string, timeout = 3000): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);
    return res.ok || res.status < 500;
  } catch {
    return false;
  }
}

export async function GET() {
  const [tts, whisper, memory, comfyui] = await Promise.all([
    checkService(`${TTS_SERVER}/tts`, 2000).catch(() => false),
    checkService(`${WHISPER_URL}/`, 2000).catch(() => false),
    checkService(`${MEMORY_SERVER_URL}/stats`, 2000).catch(() => false),
    checkService(`${COMFYUI_URL}/system_stats`, 3000).catch(() => false),
  ]);

  return NextResponse.json({ tts, whisper, memory, comfyui });
}
