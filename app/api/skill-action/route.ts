import { NextResponse } from "next/server";
import { spawn } from "child_process";
import { join } from "path";

const PROJECT_ROOT = process.cwd();

/** Run a command and return stdout/stderr. */
function runCommand(
  cmd: string,
  args: string[],
  timeout = 15000
): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const proc = spawn(cmd, args, { cwd: PROJECT_ROOT, timeout });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d: Buffer) => (stdout += d.toString()));
    proc.stderr.on("data", (d: Buffer) => (stderr += d.toString()));
    proc.on("close", (code) => resolve({ code: code ?? 1, stdout: stdout.trim(), stderr: stderr.trim() }));
    proc.on("error", (e) => resolve({ code: 1, stdout: "", stderr: e.message }));
  });
}

/** List connected ADB devices, deduplicating mDNS entries. */
async function listFrameDevices(): Promise<{ serial: string; model: string }[]> {
  const adb = process.env.ADB_PATH || "C:\\Users\\User\\tools\\platform-tools\\adb.exe";
  const { stdout } = await runCommand(adb, ["devices", "-l"]);
  const devices: { serial: string; model: string }[] = [];
  const seenModels = new Set<string>();
  for (const line of stdout.split("\n").slice(1)) {
    const parts = line.trim().split(/\s+/);
    if (parts.length >= 2 && parts[1] === "device") {
      const serial = parts[0];
      const modelMatch = line.match(/model:(\S+)/);
      const model = modelMatch?.[1] || serial;
      // Prefer IP:port entries over mDNS names; skip mDNS duplicates
      if (serial.includes("._tcp") || serial.includes("._adb")) {
        if (seenModels.has(model)) continue; // already have IP entry
      }
      if (seenModels.has(model)) continue;
      seenModels.add(model);
      // Label: use IP if available, otherwise shorten mDNS name
      const label = serial.match(/^\d+\.\d+\.\d+\.\d+/)
        ? `${model} (${serial.split(":")[0]})`
        : model;
      devices.push({ serial, model: label });
    }
  }
  return devices;
}

/** Push a file to a specific ADB device. */
async function pushToFrame(
  file: string,
  serial: string,
  mediaType: "image" | "video"
): Promise<{ ok: boolean; output: string }> {
  const filePath = join(PROJECT_ROOT, "generated", file);
  const cmd = mediaType === "video" ? "stream" : "screen";
  const proc = spawn(
    "python",
    ["skills/camera/frame.py", cmd, filePath],
    {
      cwd: PROJECT_ROOT,
      timeout: 20000,
      env: { ...process.env, FRAME_DEVICE: serial, MSYS_NO_PATHCONV: "1" },
    }
  );
  let out = "";
  let err = "";
  await new Promise<void>((resolve) => {
    proc.stdout.on("data", (d: Buffer) => (out += d.toString()));
    proc.stderr.on("data", (d: Buffer) => (err += d.toString()));
    proc.on("close", () => resolve());
    proc.on("error", () => resolve());
  });
  return { ok: out.includes("Pushed") || out.includes("Starting"), output: (out + "\n" + err).trim() };
}

/** Camera snap with specific camera type. */
async function cameraSnap(cam: string): Promise<{ ok: boolean; file?: string; output: string }> {
  const filename = `cam_snap_${cam}.png`;
  const args = ["skills/camera/cam.py", "--cam", cam, "--output", filename];
  if (cam === "ndi") {
    args.push("--ndi-ip", process.env.NDI_IP || "192.168.1.188");
  }
  const { code, stdout, stderr } = await runCommand("python", args, 15000);
  const output = (stdout + "\n" + stderr).trim();
  return {
    ok: code === 0,
    file: code === 0 ? filename : undefined,
    output,
  };
}

// Service restart commands (Python scripts)
const SERVICE_RESTART: Record<string, { cmd: string; args: string[]; name: string }> = {
  tts: {
    cmd: "python",
    args: ["skills/servers/tts_server.py"],
    name: "TTS (Kokoro)",
  },
  whisper: {
    cmd: "python",
    args: ["skills/servers/whisper_server.py"],
    name: "Whisper STT",
  },
  memory: {
    cmd: "python",
    args: ["skills/servers/memory_server.py"],
    name: "Memory Server",
  },
};

export async function POST(request: Request) {
  const body = await request.json();
  const { action, skill, option, file, serial } = body as {
    action: string;
    skill?: string;
    option?: string;
    file?: string;
    serial?: string;
  };

  switch (action) {
    case "list-frames": {
      const devices = await listFrameDevices();
      return NextResponse.json({ devices });
    }

    case "push-to-frame": {
      if (!file || !serial) {
        return NextResponse.json({ error: "Missing file or serial" }, { status: 400 });
      }
      const ext = file.split(".").pop()?.toLowerCase();
      const mediaType = ["mp4", "webm", "mov"].includes(ext || "") ? "video" as const : "image" as const;
      const result = await pushToFrame(file, serial, mediaType);
      return NextResponse.json(result);
    }

    case "camera-snap": {
      const cam = option || "orbecc";
      const result = await cameraSnap(cam);
      return NextResponse.json(result);
    }

    case "restart-service": {
      const svc = skill?.toLowerCase();
      if (!svc || !SERVICE_RESTART[svc]) {
        return NextResponse.json({ error: "Unknown service" }, { status: 400 });
      }
      const cfg = SERVICE_RESTART[svc];
      // Spawn detached so it outlives this request
      const proc = spawn(cfg.cmd, cfg.args, {
        cwd: PROJECT_ROOT,
        detached: true,
        stdio: "ignore",
      });
      proc.unref();
      return NextResponse.json({ ok: true, message: `Starting ${cfg.name} (PID ${proc.pid})` });
    }

    case "list-cameras": {
      // Return available camera presets
      const cameras = [
        { id: "orbecc", name: "Orbecc Femto Bolt" },
        { id: "c920", name: "Logitech C920" },
        { id: "ndi", name: "NDI Network" },
      ];
      return NextResponse.json({ cameras });
    }

    default:
      return NextResponse.json({ error: "Unknown action" }, { status: 400 });
  }
}
