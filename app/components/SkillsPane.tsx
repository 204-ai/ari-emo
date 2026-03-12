"use client";

import { useState, useEffect, useCallback } from "react";

interface Skill {
  name: string;
  command: string;
  description: string;
  icon: string;
  /** Key in the health response, if this skill depends on a backend service */
  healthKey?: string;
}

interface HealthStatus {
  tts: boolean;
  whisper: boolean;
  memory: boolean;
  comfyui: boolean;
}

interface TestResult {
  passed: boolean;
  tests: { name: string; passed: boolean; detail?: string }[];
  output: string;
}

const SKILLS: Skill[] = [
  {
    name: "Selfie",
    command: "/selfie",
    description: "Generate an AI portrait of Ari via ComfyUI Qwen image-edit",
    icon: "\ud83d\udcf8",
    healthKey: "comfyui",
  },
  {
    name: "Morph",
    command: "/morph",
    description: "Morphing video between two images via LTX Video 2.3",
    icon: "\ud83c\udfac",
    healthKey: "comfyui",
  },
  {
    name: "3D Model",
    command: "/3d",
    description: "Image to 3D GLB model via Hunyuan 3D v2.1",
    icon: "\ud83e\uddca",
    healthKey: "comfyui",
  },
  {
    name: "Reel",
    command: "/reel",
    description: "Branded video: keyframes, morph, overlays, stitch",
    icon: "\ud83c\udf9e\ufe0f",
    healthKey: "comfyui",
  },
  {
    name: "Camera",
    command: "/cam",
    description: "Capture from Orbecc, C920, or NDI network source",
    icon: "\ud83d\udcf7",
  },
  {
    name: "Frames",
    command: "/frame",
    description: "Push images/video to Muse Frames via ADB wireless",
    icon: "\ud83d\udd76\ufe0f",
  },
  {
    name: "Voice Input",
    command: "mic button",
    description: "Speech-to-text with live transcription preview",
    icon: "\ud83c\udfa4",
    healthKey: "whisper",
  },
  {
    name: "TTS Voice",
    command: "auto",
    description: "Text-to-speech with sentence-chunked playback",
    icon: "\ud83d\udd0a",
    healthKey: "tts",
  },
  {
    name: "Memory",
    command: "auto",
    description: "Persistent memory across sessions",
    icon: "\ud83e\udde0",
    healthKey: "memory",
  },
  {
    name: "Telegram",
    command: "auto",
    description: "Chat with Ari via @ari_rna_bot",
    icon: "\u2708\ufe0f",
  },
  {
    name: "Emotions",
    command: "curl /api/emotion",
    description: "13 expressive moods with animated ASCII art",
    icon: "\ud83d\ude0a",
  },
  {
    name: "History",
    command: "scroll up",
    description: "Infinite scroll through past chat sessions",
    icon: "\ud83d\udcdc",
  },
];

function StatusDot({ status }: { status: boolean | null }) {
  if (status === null) {
    return (
      <span
        className="inline-block w-1.5 h-1.5 rounded-full bg-zinc-600"
        title="Checking..."
      />
    );
  }
  return (
    <span
      className={`inline-block w-1.5 h-1.5 rounded-full ${
        status ? "bg-emerald-400" : "bg-red-400"
      }`}
      title={status ? "Online" : "Offline"}
    />
  );
}

function SkillCard({
  skill,
  serviceStatus,
}: {
  skill: Skill;
  serviceStatus: boolean | null;
}) {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);
  const [showOutput, setShowOutput] = useState(false);

  const runTest = async () => {
    setTesting(true);
    setResult(null);
    setShowOutput(false);
    try {
      const r = await fetch(
        `/api/test-skill?skill=${encodeURIComponent(skill.name)}`
      );
      const data = await r.json();
      setResult(data);
      setShowOutput(true);
    } catch {
      setResult({
        passed: false,
        tests: [{ name: "request", passed: false, detail: "Failed to reach test API" }],
        output: "",
      });
      setShowOutput(true);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div
      className="group px-3 py-2 rounded-lg bg-zinc-800/30 hover:bg-zinc-800/60
                 transition-colors cursor-default"
    >
      <div className="flex items-center gap-2">
        <span className="text-base">{skill.icon}</span>
        <span className="text-xs font-medium text-zinc-300 flex-1">
          {skill.name}
        </span>
        {skill.healthKey && <StatusDot status={serviceStatus} />}
        <button
          onClick={runTest}
          disabled={testing}
          className={`px-1.5 py-0.5 rounded text-[9px] font-mono transition-colors ${
            testing
              ? "bg-zinc-700 text-zinc-500 cursor-wait"
              : result === null
                ? "bg-zinc-700/60 text-zinc-400 hover:bg-zinc-600 hover:text-zinc-200"
                : result.passed
                  ? "bg-emerald-900/40 text-emerald-400 hover:bg-emerald-900/60"
                  : "bg-red-900/40 text-red-400 hover:bg-red-900/60"
          }`}
          title="Run unit tests for this skill"
        >
          {testing ? "..." : result === null ? "test" : result.passed ? "pass" : "fail"}
        </button>
      </div>
      <p className="text-[10px] text-zinc-500 mt-1 leading-tight">
        {skill.description}
      </p>
      {skill.command.startsWith("/") && (
        <code className="text-[10px] text-zinc-600 mt-1 block font-mono">
          {skill.command}
        </code>
      )}

      {/* Collapsible test results */}
      {result && (
        <div className="mt-1.5">
          <button
            onClick={() => setShowOutput(!showOutput)}
            className="text-[9px] text-zinc-500 hover:text-zinc-300 font-mono flex items-center gap-1"
          >
            <span
              className="transition-transform duration-150 inline-block"
              style={{ transform: showOutput ? "rotate(90deg)" : "rotate(0deg)" }}
            >
              {"\u25B6"}
            </span>
            {result.tests.length} check{result.tests.length !== 1 ? "s" : ""}
            {" \u2014 "}
            {result.tests.filter((t) => t.passed).length} passed
            {result.tests.some((t) => !t.passed) && (
              <span className="text-red-400 ml-1">
                {result.tests.filter((t) => !t.passed).length} failed
              </span>
            )}
          </button>

          {showOutput && (
            <div className="mt-1 space-y-0.5">
              {result.tests.map((t, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[9px] font-mono">
                  <span className={t.passed ? "text-emerald-400" : "text-red-400"}>
                    {t.passed ? "\u2713" : "\u2717"}
                  </span>
                  <span className="text-zinc-400">{t.name}</span>
                  {t.detail && (
                    <span className="text-zinc-600 ml-auto truncate max-w-[120px]" title={t.detail}>
                      {t.detail}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SkillsPane() {
  const [expanded, setExpanded] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [testingAll, setTestingAll] = useState(false);
  const [allResults, setAllResults] = useState<Record<string, TestResult>>({});

  const fetchHealth = useCallback(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((data) => setHealth(data))
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const runAllTests = async () => {
    setTestingAll(true);
    setAllResults({});
    const results: Record<string, TestResult> = {};
    for (const skill of SKILLS) {
      try {
        const r = await fetch(
          `/api/test-skill?skill=${encodeURIComponent(skill.name)}`
        );
        results[skill.name] = await r.json();
      } catch {
        results[skill.name] = {
          passed: false,
          tests: [{ name: "request", passed: false, detail: "Failed" }],
          output: "",
        };
      }
    }
    setAllResults(results);
    setTestingAll(false);
  };

  const onlineCount = health
    ? Object.values(health).filter(Boolean).length
    : null;
  const totalServices = 4;

  const allTotal = Object.keys(allResults).length;
  const allPassCount = Object.values(allResults).filter((r) => r.passed).length;

  return (
    <div className="w-full px-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 rounded-lg
                   bg-zinc-800/50 hover:bg-zinc-800 transition-colors text-sm"
      >
        <span className="text-zinc-400 font-medium flex items-center gap-2">
          Skills <span className="text-zinc-600">({SKILLS.length})</span>
          {health && (
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                onlineCount === totalServices
                  ? "bg-emerald-900/40 text-emerald-400"
                  : onlineCount === 0
                    ? "bg-red-900/40 text-red-400"
                    : "bg-yellow-900/40 text-yellow-400"
              }`}
            >
              {onlineCount}/{totalServices} services
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
        <>
          <div className="mt-2 flex items-center justify-end px-1">
            <button
              onClick={runAllTests}
              disabled={testingAll}
              className={`px-2 py-1 rounded text-[10px] font-mono transition-colors ${
                testingAll
                  ? "bg-zinc-700 text-zinc-500 cursor-wait"
                  : "bg-zinc-700/60 text-zinc-400 hover:bg-zinc-600 hover:text-zinc-200"
              }`}
            >
              {testingAll
                ? "testing..."
                : allTotal > 0
                  ? `${allPassCount}/${allTotal} passed \u2014 retest all`
                  : "test all"}
            </button>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {SKILLS.map((skill) => {
              const serviceStatus =
                skill.healthKey && health
                  ? health[skill.healthKey as keyof HealthStatus]
                  : null;

              return (
                <SkillCard
                  key={skill.name}
                  skill={skill}
                  serviceStatus={serviceStatus}
                />
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
