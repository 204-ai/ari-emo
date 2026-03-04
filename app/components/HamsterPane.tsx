"use client";

import { useEffect, useState, useRef } from "react";

const EMOTIONS = [
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
] as const;

type Emotion = (typeof EMOTIONS)[number];

interface EmotionFrame {
  eyes: string;
  mouth: string;
  cheeks: [string, string];
}

interface EmotionConfig {
  frames: EmotionFrame[];
  color: string;
  speed: number; // ms between frames
}

const EMOTION_MAP: Record<Emotion, EmotionConfig> = {
  happy: {
    color: "#facc15",
    speed: 600,
    frames: [
      { eyes: "^.^", mouth: "w", cheeks: ["* ", " *"] },
      { eyes: "^.^", mouth: "u", cheeks: [" *", "* "] },
    ],
  },
  sad: {
    color: "#60a5fa",
    speed: 1000,
    frames: [
      { eyes: "T.T", mouth: "~", cheeks: ["  ", "  "] },
      { eyes: "T~T", mouth: "n", cheeks: ["  ", "  "] },
    ],
  },
  angry: {
    color: "#ef4444",
    speed: 300,
    frames: [
      { eyes: ">.<", mouth: "^", cheeks: ["  ", "  "] },
      { eyes: ">.<", mouth: "A", cheeks: ["##", "##"] },
      { eyes: ">o<", mouth: "^", cheeks: ["  ", "  "] },
    ],
  },
  surprised: {
    color: "#c084fc",
    speed: 500,
    frames: [
      { eyes: "O.O", mouth: "o", cheeks: ["  ", "  "] },
      { eyes: "o.o", mouth: "O", cheeks: ["  ", "  "] },
      { eyes: "O.O", mouth: "0", cheeks: ["! ", " !"] },
    ],
  },
  sleepy: {
    color: "#94a3b8",
    speed: 1200,
    frames: [
      { eyes: "-.-", mouth: "z", cheeks: ["  ", "  "] },
      { eyes: "-.-", mouth: " ", cheeks: ["  ", "  "] },
      { eyes: "~.~", mouth: "Z", cheeks: ["  ", "  "] },
    ],
  },
  love: {
    color: "#fb7185",
    speed: 500,
    frames: [
      { eyes: "♥.♥", mouth: "3", cheeks: ["  ", "  "] },
      { eyes: "♥.♥", mouth: "u", cheeks: ["~ ", " ~"] },
    ],
  },
  excited: {
    color: "#fb923c",
    speed: 250,
    frames: [
      { eyes: "*.*", mouth: "D", cheeks: ["! ", " !"] },
      { eyes: "+.+", mouth: "D", cheeks: [" !", "! "] },
      { eyes: "*.*", mouth: "V", cheeks: ["! ", " !"] },
    ],
  },
  neutral: {
    color: "#d4d4d8",
    speed: 2000,
    frames: [
      { eyes: "o.o", mouth: "-", cheeks: ["  ", "  "] },
      { eyes: "o.o", mouth: "_", cheeks: ["  ", "  "] },
    ],
  },
  confused: {
    color: "#a78bfa",
    speed: 700,
    frames: [
      { eyes: "?.?", mouth: "S", cheeks: ["  ", "  "] },
      { eyes: "o.?", mouth: "s", cheeks: ["  ", "  "] },
      { eyes: "?.o", mouth: "S", cheeks: ["  ", "  "] },
    ],
  },
  hungry: {
    color: "#4ade80",
    speed: 500,
    frames: [
      { eyes: "9.9", mouth: "Q", cheeks: ["~ ", " ~"] },
      { eyes: "9.9", mouth: "P", cheeks: [" ~", "~ "] },
      { eyes: "9.9", mouth: "b", cheeks: ["~ ", " ~"] },
    ],
  },
  mischievous: {
    color: "#fbbf24",
    speed: 800,
    frames: [
      { eyes: "¬.¬", mouth: ">", cheeks: ["  ", "  "] },
      { eyes: "¬.¬", mouth: ")", cheeks: ["  ", "  "] },
    ],
  },
  solshine: {
    color: "#f0a050",
    speed: 1400,
    frames: [
      { eyes: "~.~", mouth: "u", cheeks: ["* ", " *"] },
      { eyes: "~.~", mouth: "~", cheeks: [". ", " ."] },
      { eyes: "-.-", mouth: "u", cheeks: ["  ", "  "] },
    ],
  },
};

function buildHamster(frame: EmotionFrame): string {
  const { eyes, mouth, cheeks } = frame;
  return [
    `   (\\(\\ /)/)`,
    `    ( ${eyes} )`,
    `  ${cheeks[0]}( " ^ " )${cheeks[1]}`,
    `     ( ${mouth} )`,
    `      (   )`,
  ].join("\n");
}

export default function HamsterPane() {
  const [emotion, setEmotion] = useState<Emotion>("neutral");
  const [visible, setVisible] = useState(true);
  const [frame, setFrame] = useState(0);
  const frameRef = useRef(0);

  // Poll for emotion changes
  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        const res = await fetch("/api/emotion");
        const data = await res.json();
        if (EMOTIONS.includes(data.emotion) && data.emotion !== emotion) {
          setVisible(false);
          setTimeout(() => {
            setEmotion(data.emotion);
            setFrame(0);
            frameRef.current = 0;
            setVisible(true);
          }, 200);
        }
      } catch {}
    }, 1000);
    return () => clearInterval(poll);
  }, [emotion]);

  // Animate frames
  useEffect(() => {
    const config = EMOTION_MAP[emotion];
    const numFrames = config.frames.length;
    if (numFrames <= 1) return;

    const timer = setInterval(() => {
      frameRef.current = (frameRef.current + 1) % numFrames;
      setFrame(frameRef.current);
    }, config.speed);

    return () => clearInterval(timer);
  }, [emotion]);

  const handleClick = async (e: Emotion) => {
    await fetch("/api/emotion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ emotion: e }),
    });
    setVisible(false);
    setTimeout(() => {
      setEmotion(e);
      setFrame(0);
      frameRef.current = 0;
      setVisible(true);
    }, 200);
  };

  const config = EMOTION_MAP[emotion];
  const currentFrame = config.frames[frame % config.frames.length];

  return (
    <div className="flex flex-col items-center gap-8 p-8">
      <h1 className="text-2xl font-bold text-zinc-300">Ari Emo</h1>

      <pre
        className="text-3xl leading-relaxed transition-all duration-200 select-none"
        style={{
          opacity: visible ? 1 : 0,
          color: config.color,
          fontFamily: "monospace",
          textShadow: `0 0 10px ${config.color}40, 0 0 20px ${config.color}20`,
          filter: visible ? "none" : "blur(4px)",
        }}
      >
        {buildHamster(currentFrame)}
      </pre>

      <p className="text-lg text-zinc-400">
        feeling{" "}
        <span className="font-semibold" style={{ color: config.color }}>
          {emotion}
        </span>
      </p>

      <div className="flex flex-wrap justify-center gap-2 max-w-md">
        {EMOTIONS.map((e) => (
          <button
            key={e}
            onClick={() => handleClick(e)}
            className={`px-3 py-1.5 rounded text-sm transition-colors ${
              emotion === e
                ? "text-zinc-900 font-semibold"
                : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
            }`}
            style={
              emotion === e
                ? { backgroundColor: EMOTION_MAP[e].color }
                : undefined
            }
          >
            {e}
          </button>
        ))}
      </div>
    </div>
  );
}
