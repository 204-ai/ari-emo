"use client";

import { useState, useEffect, useCallback } from "react";

interface Skill {
  name: string;
  command: string;
  description: string;
  icon: string;
  healthKey?: string;
  /** Options for this skill (e.g. camera types, frame devices) */
  options?: { id: string; name: string }[];
  /** Whether this skill supports push-to-frame on sample output */
  pushable?: boolean;
}

interface HealthStatus {
  tts: boolean;
  whisper: boolean;
  memory: boolean;
  comfyui: boolean;
}

interface Sample {
  type: "image" | "video" | "audio" | "model" | "text";
  url?: string;
  content?: string;
  /** Filename in generated/ for push-to-frame */
  file?: string;
}

interface TestResult {
  passed: boolean;
  tests: { name: string; passed: boolean; detail?: string }[];
  output: string;
  sample?: Sample | null;
}

const SKILLS: Skill[] = [
  {
    name: "Selfie",
    command: "/selfie",
    description: "Generate an AI portrait of Ari via ComfyUI Qwen image-edit",
    icon: "\ud83d\udcf8",
    healthKey: "comfyui",
    pushable: true,
  },
  {
    name: "Morph",
    command: "/morph",
    description: "Morphing video between two images via LTX Video 2.3",
    icon: "\ud83c\udfac",
    healthKey: "comfyui",
    pushable: true,
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
    pushable: true,
  },
  {
    name: "Camera",
    command: "/cam",
    description: "Capture from Orbecc, C920, or NDI network source",
    icon: "\ud83d\udcf7",
    options: [
      { id: "orbecc", name: "Orbecc" },
      { id: "c920", name: "C920" },
      { id: "ndi", name: "NDI" },
    ],
    pushable: true,
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

// Map healthKey to service key for restart
const RESTARTABLE_SERVICES: Record<string, string> = {
  tts: "tts",
  whisper: "whisper",
  memory: "memory",
};

function StatusDot({ status }: { status: boolean | null }) {
  if (status === null) {
    return (
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-zinc-600" title="Checking..." />
    );
  }
  return (
    <span
      className={`inline-block w-1.5 h-1.5 rounded-full ${status ? "bg-emerald-400" : "bg-red-400"}`}
      title={status ? "Online" : "Offline"}
    />
  );
}

function ensureModelViewer() {
  if (typeof window === "undefined") return;
  if (document.querySelector('script[src*="model-viewer"]')) return;
  const s = document.createElement("script");
  s.type = "module";
  s.src = "https://ajax.googleapis.com/ajax/libs/model-viewer/4.0.0/model-viewer.min.js";
  document.head.appendChild(s);
}

function ModelPreview({ url }: { url: string }) {
  useEffect(() => { ensureModelViewer(); }, []);
  return (
    <div className="mt-1.5 rounded overflow-hidden" style={{ height: 120 }}>
      {/* @ts-expect-error model-viewer web component */}
      <model-viewer
        src={url}
        alt="3D sample"
        auto-rotate
        camera-controls
        camera-target="auto auto auto"
        touch-action="pan-y"
        shadow-intensity="1"
        environment-image="neutral"
        style={{ width: "100%", height: "100%", backgroundColor: "#1a1a2e", borderRadius: "6px" }}
      />
    </div>
  );
}

function SamplePreview({ sample }: { sample: Sample }) {
  if (sample.type === "image" && sample.url) {
    return (
      <img
        src={sample.url}
        alt="Sample output"
        className="mt-1.5 rounded max-h-32 w-auto object-contain"
        style={{ maxWidth: "100%" }}
      />
    );
  }
  if (sample.type === "video" && sample.url) {
    return (
      <video
        src={sample.url}
        controls
        autoPlay
        loop
        muted
        playsInline
        className="mt-1.5 rounded max-h-32 w-auto"
        style={{ maxWidth: "100%" }}
      />
    );
  }
  if (sample.type === "audio" && sample.url) {
    return (
      <audio src={sample.url} controls className="mt-1.5 w-full" style={{ height: 28 }} />
    );
  }
  if (sample.type === "model" && sample.url) {
    return <ModelPreview url={sample.url} />;
  }
  if (sample.type === "text" && sample.content) {
    return (
      <pre className="mt-1.5 text-[9px] font-mono text-zinc-400 bg-zinc-900/60 rounded p-1.5 overflow-x-auto max-h-20 whitespace-pre-wrap">
        {sample.content}
      </pre>
    );
  }
  return null;
}

/** Push-to-frame button with device picker. */
function PushToFrameButton({ file }: { file: string }) {
  const [devices, setDevices] = useState<{ serial: string; model: string }[] | null>(null);
  const [pushing, setPushing] = useState(false);
  const [pushResult, setPushResult] = useState<string | null>(null);

  const loadDevices = async () => {
    if (devices !== null) return; // already loaded
    try {
      const r = await fetch("/api/skill-action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "list-frames" }),
      });
      const data = await r.json();
      setDevices(data.devices || []);
    } catch {
      setDevices([]);
    }
  };

  const push = async (serial: string) => {
    setPushing(true);
    setPushResult(null);
    try {
      const r = await fetch("/api/skill-action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "push-to-frame", file, serial }),
      });
      const data = await r.json();
      setPushResult(data.ok ? "sent" : "failed");
    } catch {
      setPushResult("failed");
    } finally {
      setPushing(false);
    }
  };

  return (
    <div className="mt-1 flex items-center gap-1 flex-wrap">
      <button
        onClick={loadDevices}
        className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-zinc-700/60 text-zinc-400 hover:bg-zinc-600 hover:text-zinc-200 transition-colors"
        title="Push to Muse Frames"
      >
        {pushing ? "..." : pushResult || "\ud83d\udd76 push"}
      </button>
      {devices && devices.length > 0 && !pushResult && (
        devices.map((d) => (
          <button
            key={d.serial}
            onClick={() => push(d.serial)}
            disabled={pushing}
            className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-indigo-900/40 text-indigo-300 hover:bg-indigo-900/60 transition-colors"
          >
            {d.model}
          </button>
        ))
      )}
      {devices && devices.length === 0 && (
        <span className="text-[9px] text-zinc-600">no frames connected</span>
      )}
    </div>
  );
}

function SkillCard({
  skill,
  serviceStatus,
  onRestart,
}: {
  skill: Skill;
  serviceStatus: boolean | null;
  onRestart?: (healthKey: string) => void;
}) {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);
  const [showOutput, setShowOutput] = useState(false);
  const [selectedOption, setSelectedOption] = useState(skill.options?.[0]?.id || "");

  const runTest = async () => {
    setTesting(true);
    // Keep previous result visible during rerun (don't clear)
    try {
      const url = `/api/test-skill?skill=${encodeURIComponent(skill.name)}` +
        (selectedOption ? `&option=${encodeURIComponent(selectedOption)}` : "");
      const r = await fetch(url);
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

  // Extract filename from sample URL for push-to-frame
  const sampleFile = result?.sample?.url
    ? new URLSearchParams(result.sample.url.split("?")[1] || "").get("file")
    : null;

  const isOffline = skill.healthKey && serviceStatus === false;
  const canRestart = isOffline && RESTARTABLE_SERVICES[skill.healthKey!];

  return (
    <div className="group px-3 py-2 rounded-lg bg-zinc-800/30 hover:bg-zinc-800/60 transition-colors cursor-default">
      {/* Header row: label toggles card, status badge + refresh are separate */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setShowOutput(!showOutput)}
          className="flex items-center gap-2 flex-1 min-w-0 text-left"
          title={showOutput ? "Collapse" : "Expand"}
        >
          <span className="text-base">{skill.icon}</span>
          <span className="text-xs font-medium text-zinc-300 truncate">{skill.name}</span>
        </button>

        {skill.healthKey && <StatusDot status={serviceStatus} />}

        {/* Restart button when offline */}
        {canRestart && (
          <button
            onClick={() => onRestart?.(skill.healthKey!)}
            className="px-1 py-0.5 rounded text-[9px] font-mono bg-amber-900/40 text-amber-400 hover:bg-amber-900/60 transition-colors"
            title="Restart service"
          >
            restart
          </button>
        )}

        {/* Status badge (not clickable) */}
        {result && (
          <span
            className={`px-1.5 py-0.5 rounded text-[9px] font-mono ${
              result.passed
                ? "bg-emerald-900/40 text-emerald-400"
                : "bg-red-900/40 text-red-400"
            }`}
          >
            {result.passed ? "\u2713 pass" : "\u2717 fail"}
          </span>
        )}

        {/* Run / rerun button */}
        <button
          onClick={runTest}
          disabled={testing}
          className={`px-1.5 py-0.5 rounded text-[9px] font-mono transition-colors ${
            testing
              ? "bg-zinc-700 text-zinc-500 cursor-wait"
              : "bg-zinc-700/60 text-zinc-400 hover:bg-zinc-600 hover:text-zinc-200"
          }`}
          title={result ? "Re-run test" : "Run test"}
        >
          {testing ? "..." : result ? "\u21BB" : "test"}
        </button>
      </div>

      {/* Expandable content */}
      {showOutput && (
        <div className="mt-1.5">
          <p className="text-[10px] text-zinc-500 leading-tight">{skill.description}</p>

          {/* Option selector (cameras, etc.) */}
          {skill.options && skill.options.length > 0 && (
            <div className="mt-1 flex items-center gap-1">
              {skill.options.map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setSelectedOption(opt.id)}
                  className={`px-1.5 py-0.5 rounded text-[9px] font-mono transition-colors ${
                    selectedOption === opt.id
                      ? "bg-blue-900/50 text-blue-300"
                      : "bg-zinc-700/40 text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  {opt.name}
                </button>
              ))}
            </div>
          )}

          {skill.command.startsWith("/") && (
            <code className="text-[10px] text-zinc-600 mt-1 block font-mono">{skill.command}</code>
          )}

          {/* Test results */}
          {result && (
            <div className="mt-1.5 space-y-0.5">
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
              {result.sample && <SamplePreview sample={result.sample} />}
              {/* Push to frame button */}
              {skill.pushable && sampleFile && (
                <PushToFrameButton file={sampleFile} />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface SkillsPaneProps {
  expanded: boolean;
  onToggle: () => void;
}

export default function SkillsPane({ expanded, onToggle }: SkillsPaneProps) {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [testingAll, setTestingAll] = useState(false);
  const [allResults, setAllResults] = useState<Record<string, TestResult>>({});
  const [restarting, setRestarting] = useState<string | null>(null);

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

  const restartService = async (healthKey: string) => {
    setRestarting(healthKey);
    try {
      await fetch("/api/skill-action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "restart-service", skill: healthKey }),
      });
      // Wait a moment then re-check health
      setTimeout(fetchHealth, 3000);
    } catch {
      // ignore
    } finally {
      setTimeout(() => setRestarting(null), 3000);
    }
  };

  const runAllTests = async () => {
    setTestingAll(true);
    setAllResults({});
    const results: Record<string, TestResult> = {};
    for (const skill of SKILLS) {
      try {
        const r = await fetch(`/api/test-skill?skill=${encodeURIComponent(skill.name)}`);
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

  const onlineCount = health ? Object.values(health).filter(Boolean).length : null;
  const totalServices = 4;
  const allTotal = Object.keys(allResults).length;
  const allPassCount = Object.values(allResults).filter((r) => r.passed).length;

  return (
    <div className="w-full px-4">
      <button
        onClick={onToggle}
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
                  onRestart={restartService}
                />
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
