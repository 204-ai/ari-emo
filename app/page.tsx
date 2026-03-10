"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import ChatPane from "./components/ChatPane";
import HamsterPane from "./components/HamsterPane";
import SkillsPane from "./components/SkillsPane";

export type HamsterState = "idle" | "thinking" | "talking";

export default function Home() {
  const [splitPercent, setSplitPercent] = useState(50);
  const [hamsterState, setHamsterState] = useState<HamsterState>("idle");
  const dragging = useRef(false);

  const onMouseDown = useCallback(() => {
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  const onMouseMove = useCallback((e: MouseEvent) => {
    if (!dragging.current) return;
    const pct = (e.clientX / window.innerWidth) * 100;
    setSplitPercent(Math.min(80, Math.max(20, pct)));
  }, []);

  const onMouseUp = useCallback(() => {
    dragging.current = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  }, []);

  useEffect(() => {
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [onMouseMove, onMouseUp]);

  return (
    <main className="flex h-screen">
      <div style={{ width: `${splitPercent}%` }} className="border-r border-zinc-800">
        <ChatPane setHamsterState={setHamsterState} />
      </div>
      <div
        onMouseDown={onMouseDown}
        className="w-1.5 bg-zinc-800 hover:bg-zinc-600 cursor-col-resize transition-colors flex-shrink-0"
      />
      <div style={{ width: `${100 - splitPercent}%` }} className="flex flex-col items-center h-full">
        <div className="flex-1 flex items-center justify-center">
          <HamsterPane hamsterState={hamsterState} setHamsterState={setHamsterState} />
        </div>
        <div className="w-full pb-4">
          <SkillsPane />
        </div>
      </div>
    </main>
  );
}
