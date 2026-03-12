"use client";

import { useState, useEffect } from "react";
import type { HamsterState } from "../page";

const EMOTIONS = [
  "happy", "sad", "angry", "surprised", "sleepy", "love",
  "excited", "neutral", "confused", "hungry", "mischievous",
  "solshine", "natsukashii",
] as const;

type Emotion = (typeof EMOTIONS)[number];

const EMOTION_COLORS: Record<Emotion, string> = {
  happy: "#facc15",
  sad: "#60a5fa",
  angry: "#ef4444",
  surprised: "#c084fc",
  sleepy: "#94a3b8",
  love: "#fb7185",
  excited: "#fb923c",
  neutral: "#d4d4d8",
  confused: "#a78bfa",
  hungry: "#4ade80",
  mischievous: "#fbbf24",
  solshine: "#f0a050",
  natsukashii: "#c4a0e8",
};

interface EmotionPaneProps {
  expanded: boolean;
  onToggle: () => void;
  hamsterState: HamsterState;
  setHamsterState: (state: HamsterState) => void;
}

export default function EmotionPane({
  expanded,
  onToggle,
  hamsterState,
  setHamsterState,
}: EmotionPaneProps) {
  const [emotion, setEmotion] = useState<Emotion>("neutral");

  // Poll current emotion
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch("/api/emotion");
        const data = await res.json();
        if (EMOTIONS.includes(data.emotion)) setEmotion(data.emotion);
      } catch {}
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleClick = async (e: Emotion) => {
    await fetch("/api/emotion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ emotion: e }),
    });
    setEmotion(e);
  };

  const setStateAPI = (state: HamsterState) => {
    setHamsterState(state);
    fetch("/api/emotion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state }),
    }).catch(() => {});
  };

  return (
    <div className="w-full px-4">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-3 py-2 rounded-lg
                   bg-zinc-800/50 hover:bg-zinc-800 transition-colors text-sm"
      >
        <span className="text-zinc-400 font-medium flex items-center gap-2">
          Emotions
          <span
            className="text-[10px] px-1.5 py-0.5 rounded-full"
            style={{
              backgroundColor: EMOTION_COLORS[emotion] + "30",
              color: EMOTION_COLORS[emotion],
            }}
          >
            {emotion}
          </span>
          {hamsterState !== "idle" && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-zinc-700 text-zinc-400">
              {hamsterState}
            </span>
          )}
        </span>
        <span
          className="text-zinc-500 transition-transform duration-200"
          style={{ transform: expanded ? "rotate(180deg)" : "rotate(0deg)" }}
        >
          {"\u25B4"}
        </span>
      </button>

      {expanded && (
        <div className="mt-2 space-y-3 px-1">
          {/* Emotion grid */}
          <div className="flex flex-wrap gap-1.5">
            {EMOTIONS.map((e) => (
              <button
                key={e}
                onClick={() => handleClick(e)}
                className={`px-2 py-1 rounded text-[11px] transition-colors ${
                  emotion === e
                    ? "text-zinc-900 font-semibold"
                    : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                }`}
                style={
                  emotion === e
                    ? { backgroundColor: EMOTION_COLORS[e] }
                    : undefined
                }
              >
                {e}
              </button>
            ))}
          </div>

          {/* State buttons */}
          <div className="flex gap-1.5">
            {(["idle", "thinking", "talking"] as HamsterState[]).map((s) => (
              <button
                key={s}
                onClick={() => setStateAPI(s)}
                className={`px-2 py-1 rounded text-[10px] font-mono transition-colors ${
                  hamsterState === s
                    ? "bg-zinc-600 text-zinc-100"
                    : "bg-zinc-800/50 text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
