import { NextResponse } from "next/server";

const WHISPER_URL = process.env.WHISPER_URL || "http://127.0.0.1:8190";

export async function POST(request: Request) {
  const formData = await request.formData();
  const file = formData.get("file");

  if (!file || !(file instanceof Blob)) {
    return NextResponse.json({ error: "No audio file provided" }, { status: 400 });
  }

  const whisperForm = new FormData();
  whisperForm.append("file", file, "audio.webm");

  const res = await fetch(`${WHISPER_URL}/transcribe`, {
    method: "POST",
    body: whisperForm,
  });

  if (!res.ok) {
    const err = await res.text();
    return NextResponse.json({ error: `Transcription failed: ${err}` }, { status: 500 });
  }

  const data = await res.json();
  return NextResponse.json(data);
}
