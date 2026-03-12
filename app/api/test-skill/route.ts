import { NextResponse } from "next/server";
import { spawn } from "child_process";
import { writeFile, readdir, stat } from "fs/promises";
import { join } from "path";

// ComfyUI workflows can take 30-120s — extend route timeout
export const maxDuration = 180;

const PROJECT_ROOT = process.cwd();
const GENERATED_DIR = join(PROJECT_ROOT, "generated");

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
      const output = stderr || stdout;
      const tests: { name: string; passed: boolean; detail?: string }[] = [];

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
        const descMatch = line.match(/^(\w.*?)\s+\.\.\.\s+(ok|FAIL|ERROR)/i);
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
        output: output.trim().slice(-500),
        tests,
      });
    });

    proc.on("error", () => {
      resolve({ passed: false, output: "Failed to spawn test process", tests: [] });
    });
  });
}

/** Run a Python script and return stdout/stderr + exit code. */
function runScript(
  args: string[],
  env?: Record<string, string>,
  timeout = 20000
): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const proc = spawn("python", args, {
      cwd: PROJECT_ROOT,
      timeout,
      env: { ...process.env, ...env },
    });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d: Buffer) => (stdout += d.toString()));
    proc.stderr.on("data", (d: Buffer) => (stderr += d.toString()));
    proc.on("close", (code) => resolve({ code: code ?? 1, stdout: stdout.trim(), stderr: stderr.trim() }));
    proc.on("error", (e) => resolve({ code: 1, stdout: "", stderr: e.message }));
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

type SampleType = "image" | "video" | "audio" | "model" | "text";
interface Sample {
  type: SampleType;
  url?: string;
  content?: string;
  file?: string;
}

/** Find the most recent file matching a prefix in generated/. */
async function findRecentFile(prefix: string, extensions: string[]): Promise<string | null> {
  try {
    const files = await readdir(GENERATED_DIR);
    const matching = files.filter((f) => {
      const lower = f.toLowerCase();
      return lower.startsWith(prefix.toLowerCase()) &&
        extensions.some((ext) => lower.endsWith(ext));
    });
    if (matching.length === 0) return null;
    const withStats = await Promise.all(
      matching.map(async (f) => ({
        name: f,
        mtime: (await stat(join(GENERATED_DIR, f))).mtimeMs,
      }))
    );
    withStats.sort((a, b) => b.mtime - a.mtime);
    return withStats[0].name;
  } catch {
    return null;
  }
}

/** Cache-bust helper — append &t=<now> so browsers don't serve stale images. */
function sampleUrl(file: string): string {
  return `/api/image?file=${file}&t=${Date.now()}`;
}

/** Find existing sample output for skills too slow to generate live. */
async function findExistingSample(
  prefix: string,
  type: SampleType,
  extensions: string[]
): Promise<Sample | null> {
  const file = await findRecentFile(prefix, extensions);
  if (!file) return null;
  return { type, url: sampleUrl(file), file };
}

// ── Skill runners ──────────────────────────────────────────────

/** Run cam.py to take a live snapshot. */
async function runCameraSnap(camType: string): Promise<{
  ok: boolean; sample: Sample | null; detail: string;
}> {
  const filename = `cam_snap_${camType}.png`;
  const args = ["skills/camera/cam.py", "--cam", camType, "--output", filename];
  if (camType === "ndi") {
    args.push("--ndi-ip", process.env.NDI_IP || "192.168.1.188");
  }
  const { code, stdout, stderr } = await runScript(args, undefined, 15000);
  const output = (stdout + "\n" + stderr).trim();
  if (code === 0) {
    return {
      ok: true,
      sample: { type: "image", url: sampleUrl(filename), file: filename },
      detail: output.match(/(\d+x\d+)/)?.[1] || "captured",
    };
  }
  return { ok: false, sample: null, detail: output.slice(-120) };
}

/** Run frame.py status + screenshot. */
async function runFrameStatus(): Promise<{
  ok: boolean; sample: Sample | null; detail: string;
}> {
  const env = { MSYS_NO_PATHCONV: "1" };
  const { stdout, stderr } = await runScript(
    ["skills/camera/frame.py", "status"], env, 10000
  );
  const statusOutput = (stdout + "\n" + stderr).trim();
  const hasDevice = statusOutput.includes("device product:") || statusOutput.includes("Model:");

  if (hasDevice) {
    const ssFile = "frame_screenshot_test.png";
    const ss = await runScript(
      ["skills/camera/frame.py", "screenshot", join(GENERATED_DIR, ssFile)], env, 10000
    );
    if (ss.code === 0) {
      return {
        ok: true,
        sample: { type: "image", url: sampleUrl(ssFile), file: ssFile },
        detail: "screenshot taken",
      };
    }
    return { ok: true, sample: { type: "text", content: statusOutput }, detail: "connected (screenshot failed)" };
  }
  return { ok: false, sample: { type: "text", content: statusOutput }, detail: "no device" };
}

/** Generate a TTS sample via Kokoro server. */
async function runTTS(): Promise<{ ok: boolean; sample: Sample | null; detail: string }> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    const res = await fetch("http://127.0.0.1:8191/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: "Hello! I am Ari, your friendly hamster assistant!", voice: "af_heart" }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) return { ok: false, sample: null, detail: `HTTP ${res.status}` };
    const buf = Buffer.from(await res.arrayBuffer());
    const filename = "tts_test_sample.wav";
    await writeFile(join(GENERATED_DIR, filename), buf);
    const sizeKB = Math.round(buf.length / 1024);
    return {
      ok: true,
      sample: { type: "audio", url: sampleUrl(filename), file: filename },
      detail: `${sizeKB}KB wav`,
    };
  } catch {
    return { ok: false, sample: null, detail: "TTS unreachable" };
  }
}

/** Test emotion API round-trip (set then read then restore). */
async function runEmotionTest(): Promise<{ ok: boolean; sample: Sample | null; detail: string }> {
  try {
    const before = await (await fetch("http://localhost:3000/api/emotion")).json();
    await fetch("http://localhost:3000/api/emotion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ emotion: "mischievous" }),
    });
    const after = await (await fetch("http://localhost:3000/api/emotion")).json();
    // Restore original
    await fetch("http://localhost:3000/api/emotion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ emotion: before.emotion }),
    });
    const ok = after.emotion === "mischievous";
    return {
      ok,
      sample: { type: "text", content: `Set: mischievous | Read: ${after.emotion} | Restored: ${before.emotion}` },
      detail: ok ? "round-trip ok" : `expected mischievous, got ${after.emotion}`,
    };
  } catch {
    return { ok: false, sample: null, detail: "API unreachable" };
  }
}

/** Test memory server stats. */
async function runMemoryTest(): Promise<{ ok: boolean; sample: Sample | null; detail: string }> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    const res = await fetch("http://127.0.0.1:8192/stats", { signal: controller.signal });
    clearTimeout(timer);
    if (!res.ok) return { ok: false, sample: null, detail: `HTTP ${res.status}` };
    const data = await res.json();
    return {
      ok: true,
      sample: { type: "text", content: JSON.stringify(data, null, 2).slice(0, 300) },
      detail: `${data.total_memories ?? "?"} memories`,
    };
  } catch {
    return { ok: false, sample: null, detail: "unreachable" };
  }
}

/** Run selfie.py to generate a test portrait. */
async function runSelfie(): Promise<{ ok: boolean; sample: Sample | null; detail: string }> {
  const filename = "test_selfie.png";
  const start = Date.now();
  const { code, stdout, stderr } = await runScript(
    ["skills/comfy/selfie.py", "A cute hamster test portrait, round fluffy golden-brown hamster with sparkly eyes, Ghibli style", "-o", filename],
    undefined, 120000 // 2 min timeout
  );
  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  const output = (stdout + "\n" + stderr).trim();
  if (code === 0 && output.includes("Saved")) {
    return {
      ok: true,
      sample: { type: "image", url: sampleUrl(filename), file: filename },
      detail: `${elapsed}s`,
    };
  }
  return { ok: false, sample: null, detail: output.slice(-150) };
}

/** Run threedee.py on an existing image to generate a test GLB. */
async function runThreedee(): Promise<{ ok: boolean; sample: Sample | null; detail: string }> {
  // Find an input image to use
  const inputFile = await findRecentFile("ari_selfie", [".png", ".jpg"])
    || await findRecentFile("ari_", [".png", ".jpg"])
    || await findRecentFile("test_selfie", [".png"]);
  if (!inputFile) return { ok: false, sample: null, detail: "no input image found" };

  const inputPath = join(GENERATED_DIR, inputFile);
  const outputFile = "test_3d.glb";
  const start = Date.now();
  const { code, stdout, stderr } = await runScript(
    ["skills/comfy/threedee.py", inputPath, "-o", outputFile],
    undefined, 120000
  );
  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  const output = (stdout + "\n" + stderr).trim();
  if (code === 0 && output.includes("Saved")) {
    return {
      ok: true,
      sample: { type: "model", url: sampleUrl(outputFile), file: outputFile },
      detail: `${elapsed}s from ${inputFile}`,
    };
  }
  return { ok: false, sample: null, detail: output.slice(-150) };
}

/** Run morph.py between two existing images. */
async function runMorph(): Promise<{ ok: boolean; sample: Sample | null; detail: string }> {
  // Find two different images to morph between
  const files = await readdir(GENERATED_DIR);
  const images = files
    .filter((f) => /^ari_.*\.png$/i.test(f))
    .sort()
    .reverse();
  if (images.length < 2) return { ok: false, sample: null, detail: "need 2+ ari images" };

  const startImg = join(GENERATED_DIR, images[0]);
  const endImg = join(GENERATED_DIR, images[1]);
  const outputFile = "test_morph.mp4";
  const start = Date.now();
  const { code, stdout, stderr } = await runScript(
    [
      "skills/comfy/morph.py",
      "--start", startImg,
      "--end", endImg,
      "--frames", "49",      // shorter test: 49 frames (~2s video)
      "--width", "512",      // smaller for speed
      "--height", "768",
      "-o", outputFile,
      "A smooth transformation between two hamster portraits",
    ],
    undefined, 180000 // 3 min timeout
  );
  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  const output = (stdout + "\n" + stderr).trim();
  if (code === 0 && (output.includes("Saved") || output.includes("Done"))) {
    return {
      ok: true,
      sample: { type: "video", url: sampleUrl(outputFile), file: outputFile },
      detail: `${elapsed}s (49f 512x768)`,
    };
  }
  return { ok: false, sample: null, detail: output.slice(-150) };
}

// ── Config ─────────────────────────────────────────────────────

const TTS_SERVER = "http://127.0.0.1:8191";
const WHISPER_URL = process.env.WHISPER_URL || "http://127.0.0.1:8190";
const MEMORY_URL = process.env.MEMORY_SERVER_URL || "http://127.0.0.1:8192";
const COMFYUI_URL = process.env.COMFYUI_URL || "http://localhost:8189";


export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const skill = searchParams.get("skill");
  const option = searchParams.get("option");

  if (!skill) {
    return NextResponse.json({ error: "Missing ?skill= param" }, { status: 400 });
  }

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
  let sample: Sample | null = null;

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

  // ── Run actual skills ──
  try {
    switch (skill) {
      case "Camera": {
        const camType = option || "c920";
        const snap = await runCameraSnap(camType);
        results.push({ name: `${camType} snap`, passed: snap.ok, detail: snap.detail });
        if (!snap.ok) allPassed = false;
        sample = snap.sample;
        break;
      }

      case "Frames": {
        const frame = await runFrameStatus();
        results.push({ name: "device status", passed: frame.ok, detail: frame.detail });
        if (!frame.ok) allPassed = false;
        sample = frame.sample;
        break;
      }

      case "TTS Voice": {
        const tts = await runTTS();
        results.push({ name: "generate sample", passed: tts.ok, detail: tts.detail });
        if (!tts.ok) allPassed = false;
        sample = tts.sample;
        break;
      }

      case "Voice Input":
        break;

      case "Emotions": {
        const emo = await runEmotionTest();
        results.push({ name: "round-trip", passed: emo.ok, detail: emo.detail });
        if (!emo.ok) allPassed = false;
        sample = emo.sample;
        break;
      }

      case "Memory": {
        const mem = await runMemoryTest();
        results.push({ name: "stats", passed: mem.ok, detail: mem.detail });
        if (!mem.ok) allPassed = false;
        sample = mem.sample;
        break;
      }

      case "Selfie": {
        const selfie = await runSelfie();
        results.push({ name: "generate selfie", passed: selfie.ok, detail: selfie.detail });
        if (!selfie.ok) allPassed = false;
        sample = selfie.sample;
        break;
      }
      case "Morph": {
        const morph = await runMorph();
        results.push({ name: "generate morph", passed: morph.ok, detail: morph.detail });
        if (!morph.ok) allPassed = false;
        sample = morph.sample;
        break;
      }
      case "3D Model": {
        const threedee = await runThreedee();
        results.push({ name: "generate GLB", passed: threedee.ok, detail: threedee.detail });
        if (!threedee.ok) allPassed = false;
        sample = threedee.sample;
        break;
      }
      case "Reel": {
        // Reel is multi-step (keyframes + morphs + stitch), too heavy for a test button.
        // Run a selfie as a sanity check that ComfyUI pipeline works.
        const reelCheck = await runSelfie();
        results.push({ name: "ComfyUI pipeline", passed: reelCheck.ok, detail: reelCheck.ok ? "selfie generated" : reelCheck.detail });
        if (!reelCheck.ok) allPassed = false;
        // Show most recent reel output
        sample = await findExistingSample("reel_", "video", [".mp4"]);
        if (!sample) sample = await findExistingSample("204ai_", "video", [".mp4"]);
        if (!sample && reelCheck.sample) sample = reelCheck.sample;
        if (sample) results.push({ name: "recent output", passed: true, detail: sample.file });
        break;
      }
    }
  } catch {
    // Skill run is best-effort
  }

  return NextResponse.json({ passed: allPassed, tests: results, output, sample });
}
