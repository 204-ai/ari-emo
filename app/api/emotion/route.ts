import { NextResponse } from "next/server";

const VALID_EMOTIONS = [
  "happy",
  "sad",
  "angry",
  "surprised",
  "sleepy",
  "love",
  "excited",
  "neutral",
  "confused",
  "hungry",
  "mischievous",
] as const;

type Emotion = (typeof VALID_EMOTIONS)[number];

let currentEmotion: Emotion = "neutral";

export async function GET() {
  return NextResponse.json({ emotion: currentEmotion });
}

export async function POST(request: Request) {
  const body = await request.json();
  const emotion = body.emotion;

  if (!VALID_EMOTIONS.includes(emotion)) {
    return NextResponse.json(
      { error: `Invalid emotion. Must be one of: ${VALID_EMOTIONS.join(", ")}` },
      { status: 400 }
    );
  }

  currentEmotion = emotion;
  return NextResponse.json({ emotion: currentEmotion });
}
