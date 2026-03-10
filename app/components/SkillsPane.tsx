"use client";

import { useState } from "react";

interface Skill {
  name: string;
  command: string;
  description: string;
  icon: string;
}

const SKILLS: Skill[] = [
  {
    name: "Selfie",
    command: "/selfie",
    description: "Generate an AI portrait of Ari via ComfyUI image editing",
    icon: "\ud83d\udcf8",
  },
  {
    name: "Voice Input",
    command: "mic button",
    description: "Speech-to-text with live transcription preview",
    icon: "\ud83c\udfa4",
  },
  {
    name: "Webcam",
    command: "camera button",
    description: "Capture photos to share in chat",
    icon: "\ud83d\udcf7",
  },
  {
    name: "Emotions",
    command: "curl /api/emotion",
    description: "13 expressive moods with animated ASCII art",
    icon: "\ud83d\ude0a",
  },
  {
    name: "TTS Voice",
    command: "auto",
    description: "Text-to-speech responses with sentence-chunked playback",
    icon: "\ud83d\udd0a",
  },
  {
    name: "Memory",
    command: "auto",
    description: "Persistent memory across sessions — knows who you are",
    icon: "\ud83e\udde0",
  },
  {
    name: "Image Gen",
    command: "attach photo + prompt",
    description: "Edit images with Qwen via ComfyUI pipeline",
    icon: "\ud83c\udfa8",
  },
  {
    name: "History",
    command: "scroll up",
    description: "Infinite scroll through past chat sessions",
    icon: "\ud83d\udcdc",
  },
];

export default function SkillsPane() {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="w-full px-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 rounded-lg
                   bg-zinc-800/50 hover:bg-zinc-800 transition-colors text-sm"
      >
        <span className="text-zinc-400 font-medium">
          Skills <span className="text-zinc-600">({SKILLS.length})</span>
        </span>
        <span
          className="text-zinc-500 transition-transform duration-200"
          style={{ transform: expanded ? "rotate(180deg)" : "rotate(0deg)" }}
        >
          \u25B4
        </span>
      </button>

      {expanded && (
        <div className="mt-2 grid grid-cols-2 gap-2">
          {SKILLS.map((skill) => (
            <div
              key={skill.name}
              className="group px-3 py-2 rounded-lg bg-zinc-800/30 hover:bg-zinc-800/60
                         transition-colors cursor-default"
            >
              <div className="flex items-center gap-2">
                <span className="text-base">{skill.icon}</span>
                <span className="text-xs font-medium text-zinc-300">
                  {skill.name}
                </span>
              </div>
              <p className="text-[10px] text-zinc-500 mt-1 leading-tight">
                {skill.description}
              </p>
              {skill.command.startsWith("/") && (
                <code className="text-[10px] text-zinc-600 mt-1 block font-mono">
                  {skill.command}
                </code>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
