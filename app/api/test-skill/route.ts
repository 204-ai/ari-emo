import { NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";

const PROJECT_ROOT = process.cwd();

/** Run a Python unittest class and return structured results. */
function runPythonTest(testClass: string): Promise<{
  passed: boolean;
  output: string;
  tests: { name: string; passed: boolean; detail?: string }[];
}> {
  return new Promise((resolve) => {
    const proc = spawn(
      "python",
      ["skills/test_skills.py", testClass],
      { cwd: PROJECT_ROOT, timeout: 15000 }
    );

    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d: Buffer) => (stdout += d.toString()));
    proc.stderr.on("data", (d: Buffer) => (stderr += d.toString()));

    proc.on("close", (code) => {
      const output = stderr || stdout; // unittest writes to stderr
      const tests: { name: string; passed: boolean; detail?: string }[] = [];

      // Parse unittest verbose output: "test_name (module.Class) ... ok"
      for (const line of output.split("\n")) {
        const match = line.match(/^(test_\w+)\s+\(.*?\)\s*(?:\.\.\.|-)\s*(.*)/);
        if (match) {
          const [, name, result] = match;
          const ok = result.trim().toLowerCase() === "ok";
          tests.push({
            name: name.replace(/^test_/, ""),
            passed: ok,
            detail: ok ? undefined : result.trim(),
          });
          continue;
        }
        // Also handle: "test_name (module.Class)\ndescription ... ok"
        const descMatch = line.match(
          /^(\w.*?)\s+\.\.\.\s+(ok|FAIL|ERROR)/i
        );
        if (descMatch) {
          const [, desc, result] = descMatch;
          tests.push({
            name: desc.trim(),
            passed: result.toLowerCase() === "ok",
            detail: result.toLowerCase() !== "ok" ? result : undefined,
          });
        }
      }

      resolve({
        passed: code === 0,
        output: output.trim().slice(-500), // last 500 chars
        tests,
      });
    });

    proc.on("error", () => {
      resolve({ passed: false, output: "Failed to spawn test process", tests: [] });
    });
  });
}

/** Ping a service URL and return latency. */
async function pingService(
  url: string,
  timeout = 3000
): Promise<{ reachable: boolean; latencyMs: number }> {
  const start = Date.now();
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);
    return { reachable: res.ok || res.status < 500, latencyMs: Date.now() - start };
  } catch {
    return { reachable: false, latencyMs: Date.now() - start };
  }
}

const TTS_SERVER = "http://127.0.0.1:8191";
const WHISPER_URL = process.env.WHISPER_URL || "http://127.0.0.1:8190";
const MEMORY_URL = process.env.MEMORY_SERVER_URL || "http://127.0.0.1:8192";
const COMFYUI_URL = process.env.COMFYUI_URL || "http://localhost:8189";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const skill = searchParams.get("skill");

  if (!skill) {
    return NextResponse.json({ error: "Missing ?skill= param" }, { status: 400 });
  }

  // Map skill names to test classes and/or service pings
  const testMap: Record<string, { testClass?: string; ping?: { name: string; url: string } }> = {
    Selfie:       { testClass: "TestSelfie", ping: { name: "ComfyUI", url: `${COMFYUI_URL}/system_stats` } },
    Morph:        { testClass: "TestMorph", ping: { name: "ComfyUI", url: `${COMFYUI_URL}/system_stats` } },
    "3D Model":   { testClass: "TestThreedee", ping: { name: "ComfyUI", url: `${COMFYUI_URL}/system_stats` } },
    Reel:         { testClass: "TestReel", ping: { name: "ComfyUI", url: `${COMFYUI_URL}/system_stats` } },
    Camera:       { testClass: "TestCam" },
    Frames:       { testClass: "TestFrame" },
    "Voice Input": { ping: { name: "Whisper", url: `${WHISPER_URL}/` } },
    "TTS Voice":  { ping: { name: "TTS", url: `${TTS_SERVER}/tts` } },
    Memory:       { ping: { name: "Memory", url: `${MEMORY_URL}/stats` } },
    Emotions:     { testClass: "TestAPIRoutes" },
  };

  const config = testMap[skill];
  if (!config) {
    return NextResponse.json({
      passed: true,
      tests: [{ name: "availability", passed: true, detail: "No automated test" }],
      output: "No test configured for this skill",
    });
  }

  const results: { name: string; passed: boolean; detail?: string }[] = [];
  let allPassed = true;
  let output = "";

  // Run service ping if configured
  if (config.ping) {
    const { reachable, latencyMs } = await pingService(config.ping.url);
    results.push({
      name: `${config.ping.name} reachable`,
      passed: reachable,
      detail: reachable ? `${latencyMs}ms` : "unreachable",
    });
    if (!reachable) allPassed = false;
  }

  // Run Python unit tests if configured
  if (config.testClass) {
    const testResult = await runPythonTest(config.testClass);
    results.push(...testResult.tests);
    if (!testResult.passed) allPassed = false;
    output = testResult.output;
  }

  return NextResponse.json({ passed: allPassed, tests: results, output });
}
