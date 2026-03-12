"use client";

import { useEffect, useState, useRef } from "react";
import type { HamsterState } from "../page";

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
  "natsukashii",
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
  natsukashii: {
    color: "#c4a0e8",
    speed: 1200,
    frames: [
      { eyes: "◕･◕", mouth: "ω", cheeks: ["ﾟ ", " ﾟ"] },
      { eyes: "ｰ･ｰ", mouth: "ω", cheeks: ["  ", "  "] },
      { eyes: "◕･◕", mouth: "ω", cheeks: [" ﾟ", "ﾟ "] },
    ],
  },
};

// Thought bubble content per emotion
const THOUGHT_CONTENT: Record<Emotion, [string, string]> = {
  happy: ["~*~", "*~*"],
  sad: ["...", "~~~"],
  angry: ["#!@", "!!!"],
  surprised: ["?!?", "!!!"],
  sleepy: ["zzz", "ZzZ"],
  love: ["<3~", "~<3"],
  excited: ["!!!", "***"],
  neutral: ["...", "~~~"],
  confused: ["???", "?~?"],
  hungry: ["nom", "~Q~"],
  mischievous: ["heh", ">:)"],
  solshine: ["~~~", "..."],
  natsukashii: ["ﾎｯ", "~ω~"],
};

// Thinking cloud ASCII art — 4 frames with floating sparkles
function buildThinkingArt(content: [string, string]): string[][] {
  return [
    [
      `      .  ·  .`,
      `    (  ${content[0]}  )`,
      `      '───'`,
      `        °`,
      `       ○`,
    ],
    [
      `      ·  .  ·`,
      `    (  ${content[1]}  )`,
      `      '───'`,
      `       ○`,
      `        °`,
    ],
    [
      `      .  *  .`,
      `    (  ${content[0]}  )`,
      `      '───'`,
      `        °`,
      `         ○`,
    ],
    [
      `      *  .  *`,
      `    (  ${content[1]}  )`,
      `      '───'`,
      `         ○`,
      `       °`,
    ],
  ];
}

// Talking sound waves — 4 frames pulsing outward
const TALKING_ART: string[][] = [
  [
    `    ♪          ♫`,
    `       ·)  )·`,
    `        ·))·`,
    `         ·)·`,
  ],
  [
    `    ♫          ♪`,
    `     ·))    ))·`,
    `      ·))  ))·`,
    `        ·))·`,
  ],
  [
    `    ♪    ♫    ♪`,
    `    ·)))  )))·`,
    `     ·))  ))·`,
    `       ·))·`,
  ],
  [
    `    ♫    ♪    ♫`,
    `   ·)))    )))·`,
    `    ·)))  )))·`,
    `      ·))  ))·`,
  ],
];

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

interface HamsterPaneProps {
  hamsterState: HamsterState;
}

export default function HamsterPane({ hamsterState }: HamsterPaneProps) {
  const [emotion, setEmotion] = useState<Emotion>("neutral");
  const [visible, setVisible] = useState(true);
  const [frame, setFrame] = useState(0);
  const [thoughtFrame, setThoughtFrame] = useState(0);
  const [talkingFrame, setTalkingFrame] = useState(0);
  const frameRef = useRef(0);

  // Poll for emotion changes only (state is now passed via props)
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

  // Animate frames (faster when talking)
  useEffect(() => {
    const config = EMOTION_MAP[emotion];
    const numFrames = config.frames.length;
    if (numFrames <= 1) return;

    const speed = hamsterState === "talking" ? config.speed / 2 : config.speed;
    const timer = setInterval(() => {
      frameRef.current = (frameRef.current + 1) % numFrames;
      setFrame(frameRef.current);
    }, speed);

    return () => clearInterval(timer);
  }, [emotion, hamsterState]);

  // Thought bubble animation (4 frames)
  useEffect(() => {
    if (hamsterState !== "thinking") return;
    setThoughtFrame(0);
    const timer = setInterval(() => {
      setThoughtFrame((f) => (f + 1) % 4);
    }, 800);
    return () => clearInterval(timer);
  }, [hamsterState]);

  // Talking sound wave animation (4 frames, faster)
  useEffect(() => {
    if (hamsterState !== "talking") return;
    setTalkingFrame(0);
    const timer = setInterval(() => {
      setTalkingFrame((f) => (f + 1) % 4);
    }, 350);
    return () => clearInterval(timer);
  }, [hamsterState]);

  const config = EMOTION_MAP[emotion];
  const currentFrame = config.frames[frame % config.frames.length];
  const thoughtContent = THOUGHT_CONTENT[emotion];

  return (
    <div className="flex flex-col items-center gap-4 p-4">
      <h1 className="text-2xl font-bold text-zinc-300">Ari Emo</h1>

      {/* Animated state indicator */}
      <div className="h-28 flex items-end justify-center">
        {hamsterState === "thinking" && (
          <pre
            className="text-base leading-snug text-center select-none"
            style={{
              color: config.color,
              fontFamily: "monospace",
              textShadow: `0 0 8px ${config.color}30, 0 0 16px ${config.color}15`,
              animation: "thinking-float 3s ease-in-out infinite",
            }}
          >
            {buildThinkingArt(thoughtContent)[thoughtFrame].join("\n")}
          </pre>
        )}

        {hamsterState === "talking" && (
          <pre
            className="text-base leading-snug text-center select-none"
            style={{
              color: config.color,
              fontFamily: "monospace",
              textShadow: `0 0 10px ${config.color}40, 0 0 20px ${config.color}20`,
              animation: "talking-pulse 0.6s ease-in-out infinite",
            }}
          >
            {TALKING_ART[talkingFrame].join("\n")}
          </pre>
        )}
      </div>

      <pre
        className="text-3xl leading-relaxed transition-all duration-200 select-none"
        style={{
          opacity: visible ? 1 : 0,
          color: config.color,
          fontFamily: "monospace",
          textShadow: `0 0 10px ${config.color}40, 0 0 20px ${config.color}20`,
          filter: visible ? "none" : "blur(4px)",
          animation: hamsterState === "talking" ? "hamster-bob 0.6s ease-in-out infinite" : "none",
        }}
      >
        {buildHamster(currentFrame)}
      </pre>

      <p className="text-lg text-zinc-400">
        feeling{" "}
        <span className="font-semibold" style={{ color: config.color }}>
          {emotion}
        </span>
        {hamsterState !== "idle" && (
          <span className="text-zinc-500 text-sm ml-2">
            ({hamsterState === "thinking" ? "thinking..." : "talking..."})
          </span>
        )}
      </p>

      {/* CSS for animations */}
      <style jsx>{`
        @keyframes hamster-bob {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-3px); }
        }
        @keyframes thinking-float {
          0%, 100% { transform: translateY(0); opacity: 0.9; }
          50% { transform: translateY(-6px); opacity: 1; }
        }
        @keyframes talking-pulse {
          0%, 100% { transform: scale(1); opacity: 0.85; }
          50% { transform: scale(1.05); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
