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
  "solshine",
  "natsukashii",
] as const;

type Emotion = (typeof VALID_EMOTIONS)[number];

type HamsterState = "idle" | "thinking" | "talking";

let currentEmotion: Emotion = "neutral";
let currentState: HamsterState = "idle";

export async function GET() {
  return NextResponse.json({ emotion: currentEmotion, state: currentState });
}

export async function POST(request: Request) {
  const body = await request.json();

  // Allow setting state independently
  if (body.state) {
    const validStates: HamsterState[] = ["idle", "thinking", "talking"];
    if (validStates.includes(body.state)) {
      currentState = body.state;
    }
  }

  // Allow setting emotion independently
  if (body.emotion) {
    if (!VALID_EMOTIONS.includes(body.emotion)) {
      return NextResponse.json(
        { error: `Invalid emotion. Must be one of: ${VALID_EMOTIONS.join(", ")}` },
        { status: 400 }
      );
    }
    currentEmotion = body.emotion;
  }

  return NextResponse.json({ emotion: currentEmotion, state: currentState });
}
