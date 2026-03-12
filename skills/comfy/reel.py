"""
Reel Generator — Unified 4-phase ad/reel pipeline.

Takes a JSON config describing scenes, generates keyframe images via ComfyUI
Qwen image-edit, morphs between them via LTX Video 2.3, adds text overlays
and branding, then stitches into a final video.

Usage:
  python reel.py config.json
  python reel.py config.json --resume 3    # resume from clip 3
  python reel.py config.json --skip-keyframes  # skip phase 1

Config JSON format:
{
  "name": "my_ad",
  "brand": "204.ai",
  "secondary_brand": "RnA Studio",   // optional
  "audio_mode": "none",              // "none" | "tts" | "native"
  "width": 720, "height": 1280,
  "fps": 24, "frames_per_clip": 121,
  "keyframes": ["prompt1", "prompt2", ...],
  "morph_prompts": ["transition1", ...],
  "captions": ["subtitle1", ...],
  "narration": ["tts text1", ...]     // required if audio_mode == "tts"
}
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
GENERATED = ROOT / "generated"
GENERATED.mkdir(exist_ok=True)

# Load .env.local if COMFYUI_URL not already set
_env_file = ROOT / ".env.local"
if _env_file.exists() and "COMFYUI_URL" not in os.environ:
    for _line in _env_file.read_text().splitlines():
        if _line.startswith("COMFYUI_URL="):
            os.environ["COMFYUI_URL"] = _line.split("=", 1)[1].strip()

COMFYUI = os.environ.get("COMFYUI_URL", "http://localhost:8189")

# ── Defaults ─────────────────────────────────────────────────────────

DEFAULT_NEGATIVE = (
    "snowing, jump cut, shiny, realism, realistic, photographic, 3d rendered, "
    "3d, blurry, low quality, still frame, frames, watermark, overlay, titles, "
    "has blurbox, has subtitles, unrealistic, out-of-focus, low-detail, "
    "3-arms, extra legs, walking backwards, defying physics."
)
SPEECH_NEGATIVE = (
    "snowing, jump cut, shiny, realism, realistic, photographic, 3d rendered, "
    "3d, blurry, low quality, still frame, frames, watermark, overlay, titles, "
    "has blurbox, has subtitles, unrealistic, out-of-focus, low-detail, "
    "3-arms, extra legs, walking backwards, defying physics."
)
AUDIO_NEGATIVE = "echo, distortion, static, harsh noise."

HAMSTER_ASCII = r"""
   (\(\ /)/)
    ( ^.^ )
  * ( " ^ " ) *
     ( w )
      (   )
"""


# ── Image helpers ────────────────────────────────────────────────────

from PIL import Image, ImageDraw, ImageFont


def render_ascii_to_png(out_path: Path) -> None:
    """Render Ari's ASCII face to a 1024x1024 PNG."""
    w, h = 1024, 1024
    img = Image.new("RGB", (w, h), (30, 30, 35))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("consola.ttf", 64)
    except OSError:
        try:
            font = ImageFont.truetype("cour.ttf", 64)
        except OSError:
            font = ImageFont.load_default()
    lines = HAMSTER_ASCII.strip().split("\n")
    lh = 72
    th = len(lines) * lh
    ys = (h - th) // 2
    for i, line in enumerate(lines):
        bb = draw.textbbox((0, 0), line, font=font)
        tw = bb[2] - bb[0]
        draw.text(((w - tw) // 2, ys + i * lh), line, fill=(255, 200, 100), font=font)
    img.save(str(out_path))


def upload_image(file_path: Path) -> str:
    """Upload an image to ComfyUI, return server-side filename."""
    import mimetypes
    boundary = "----ReelUploadBoundary"
    fn = file_path.name
    mime = mimetypes.guess_type(fn)[0] or "image/png"
    data = file_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{fn}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}\r\n".encode() + (
        f'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
        f"--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(
        f"{COMFYUI}/upload/image", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    return json.loads(urllib.request.urlopen(req).read())["name"]


# ── Selfie (keyframe) generation ─────────────────────────────────────

def build_selfie_workflow(prompt: str, image_name: str, seed: int) -> dict:
    return {
        "3": {"inputs": {"seed": seed, "steps": 4, "cfg": 1, "sampler_name": "euler", "scheduler": "simple", "denoise": 1, "model": ["75", 0], "positive": ["111", 0], "negative": ["110", 0], "latent_image": ["88", 0]}, "class_type": "KSampler"},
        "8": {"inputs": {"samples": ["3", 0], "vae": ["39", 0]}, "class_type": "VAEDecode"},
        "37": {"inputs": {"unet_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors", "weight_dtype": "default"}, "class_type": "UNETLoader"},
        "38": {"inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"}, "class_type": "CLIPLoader"},
        "39": {"inputs": {"vae_name": "qwen_image_vae.safetensors"}, "class_type": "VAELoader"},
        "60": {"inputs": {"filename_prefix": "ari_reel/img", "images": ["8", 0]}, "class_type": "SaveImage"},
        "66": {"inputs": {"shift": 3, "model": ["89", 0]}, "class_type": "ModelSamplingAuraFlow"},
        "75": {"inputs": {"strength": 1, "model": ["66", 0]}, "class_type": "CFGNorm"},
        "78": {"inputs": {"image": image_name}, "class_type": "LoadImage"},
        "88": {"inputs": {"pixels": ["93", 0], "vae": ["39", 0]}, "class_type": "VAEEncode"},
        "89": {"inputs": {"lora_name": "Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors", "strength_model": 1, "model": ["37", 0]}, "class_type": "LoraLoaderModelOnly"},
        "93": {"inputs": {"upscale_method": "lanczos", "megapixels": 1, "resolution_steps": 1, "image": ["78", 0]}, "class_type": "ImageScaleToTotalPixels"},
        "110": {"inputs": {"prompt": "", "clip": ["38", 0], "vae": ["39", 0], "image1": ["93", 0]}, "class_type": "TextEncodeQwenImageEditPlus"},
        "111": {"inputs": {"prompt": prompt, "clip": ["38", 0], "vae": ["39", 0], "image1": ["93", 0]}, "class_type": "TextEncodeQwenImageEditPlus"},
    }


def queue_and_wait_selfie(workflow: dict, timeout: int = 240) -> tuple:
    payload = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        f"{COMFYUI}/prompt", data=payload,
        headers={"Content-Type": "application/json"},
    )
    pid = json.loads(urllib.request.urlopen(req).read())["prompt_id"]
    print(f"  Queued selfie {pid[:12]}...", flush=True)
    for _ in range(timeout // 2):
        time.sleep(2)
        try:
            h = json.loads(urllib.request.urlopen(f"{COMFYUI}/history/{pid}").read())
            if pid in h:
                e = h[pid]
                if e.get("status", {}).get("status_str") == "error":
                    raise RuntimeError(f"Selfie failed: {json.dumps(e['status'])}")
                if e.get("status", {}).get("completed"):
                    for o in e.get("outputs", {}).values():
                        if "images" in o:
                            img = o["images"][0]
                            return img["filename"], img.get("subfolder", ""), img.get("type", "output")
                    raise RuntimeError("No image output")
        except urllib.error.URLError:
            pass
        print(".", end="", flush=True)
    raise TimeoutError("Selfie generation timed out")


def download(filename: str, subfolder: str, ftype: str, dest: Path) -> None:
    urllib.request.urlretrieve(
        f"{COMFYUI}/view?filename={filename}&subfolder={subfolder}&type={ftype}",
        str(dest),
    )


def gen_keyframe(prompt: str, name: str, face_name: str) -> Path:
    """Generate a single keyframe image."""
    dest = GENERATED / name
    if dest.exists():
        print(f"  [SKIP] {name}", flush=True)
        return dest
    seed = int(time.time() * 1000) % (2**32)
    wf = build_selfie_workflow(prompt, face_name, seed)
    fn, sf, ft = queue_and_wait_selfie(wf)
    print(flush=True)
    download(fn, sf, ft, dest)
    print(f"  Saved: {name}", flush=True)
    return dest


# ── Morph clip generation ────────────────────────────────────────────

def build_morph_workflow(prompt, start_img, end_img, seed,
                         frames=121, w=720, h=1280, fps=24.0,
                         audio_mode="none"):
    """Build LTX 2.3 morph workflow. Delegates to morph.py's build_workflow."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import morph
    wf = morph.build_workflow(prompt, start_img, end_img, seed, frames, w, h, fps)

    # For native audio mode, use speech-friendly negative prompts
    if audio_mode == "native":
        wf["109"]["inputs"]["text"] = SPEECH_NEGATIVE
        wf["352"]["inputs"]["text"] = AUDIO_NEGATIVE

    return wf


def queue_and_wait_morph(workflow: dict, timeout: int = 600) -> tuple:
    payload = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        f"{COMFYUI}/prompt", data=payload,
        headers={"Content-Type": "application/json"},
    )
    pid = json.loads(urllib.request.urlopen(req).read())["prompt_id"]
    print(f"  Queued morph {pid[:12]}...", flush=True)
    for _ in range(timeout // 3):
        time.sleep(3)
        try:
            h = json.loads(urllib.request.urlopen(f"{COMFYUI}/history/{pid}").read())
            if pid in h:
                e = h[pid]
                if e.get("status", {}).get("status_str") == "error":
                    msgs = e.get("status", {}).get("messages", [])
                    raise RuntimeError(f"Morph failed: {json.dumps(msgs)}")
                if e.get("status", {}).get("completed"):
                    for o in e.get("outputs", {}).values():
                        if "gifs" in o:
                            v = o["gifs"][0]
                            return v["filename"], v.get("subfolder", ""), v.get("type", "output")
                    for o in e.get("outputs", {}).values():
                        if "images" in o:
                            v = o["images"][0]
                            return v["filename"], v.get("subfolder", ""), v.get("type", "output")
                    raise RuntimeError("No morph output")
        except urllib.error.URLError:
            pass
        print(".", end="", flush=True)
    raise TimeoutError("Morph generation timed out")


def gen_morph_clip(start_path: Path, end_path: Path, prompt: str, name: str,
                   frames: int = 121, w: int = 720, h: int = 1280,
                   fps: float = 24.0, audio_mode: str = "none") -> Path:
    """Generate a single morph clip."""
    dest = GENERATED / name
    if dest.exists():
        print(f"  [SKIP] {name}", flush=True)
        return dest
    s_name = upload_image(start_path)
    e_name = upload_image(end_path)
    seed = int(time.time() * 1000) % (2**53)
    wf = build_morph_workflow(prompt, s_name, e_name, seed, frames, w, h, fps, audio_mode)
    fn, sf, ft = queue_and_wait_morph(wf)
    print(flush=True)
    download(fn, sf, ft, dest)
    print(f"  Saved: {name}", flush=True)
    return dest


# ── TTS generation ───────────────────────────────────────────────────

def generate_tts(text: str, output_path: Path, voice: str = "af_heart",
                 speed: float = 1.1) -> Path:
    """Generate TTS audio using Kokoro ONNX."""
    if output_path.exists():
        print(f"  [SKIP TTS] {output_path.name}", flush=True)
        return output_path

    from kokoro_onnx import Kokoro
    import soundfile as sf

    model_path = ROOT / "models" / "kokoro-v1.0.int8.onnx"
    voices_path = ROOT / "models" / "voices-v1.0.bin"
    kokoro = Kokoro(str(model_path), str(voices_path))
    samples, sr = kokoro.create(text, voice=voice, speed=speed)
    sf.write(str(output_path), samples, sr)
    dur = len(samples) / sr
    print(f"  TTS: \"{text[:50]}...\" -> {dur:.1f}s", flush=True)
    return output_path


# ── FFmpeg overlay + stitch ──────────────────────────────────────────

def escape_drawtext(text: str) -> str:
    """Escape text for ffmpeg drawtext filter."""
    return text.replace("'", "'\\''").replace(":", "\\:").replace(",", "\\,")


def build_overlay_filter(caption: str, brand: str, secondary_brand: str | None,
                         w: int, h: int) -> str:
    """Build ffmpeg video filter string for overlays."""
    lines = caption.split("\n")
    line1 = escape_drawtext(lines[0])
    line2 = escape_drawtext(lines[1]) if len(lines) > 1 else ""

    vf_parts = [
        f"scale={w}:{h}:force_original_aspect_ratio=decrease",
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black",
    ]

    # Subtitle line 1
    vf_parts.append(
        f"drawtext=text='{line1}':"
        f"fontsize=50:fontcolor=white:borderw=4:bordercolor=black@0.9:"
        f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
        f"x=(w-text_w)/2:y=h*3/4-40:"
        f"enable='between(t\\,0.3\\,4.5)':"
        f"alpha='if(lt(t\\,0.8)\\,(t-0.3)*2\\,if(gt(t\\,4)\\,(4.5-t)*2\\,1))'"
    )

    # Subtitle line 2
    if line2:
        vf_parts.append(
            f"drawtext=text='{line2}':"
            f"fontsize=50:fontcolor=white:borderw=4:bordercolor=black@0.9:"
            f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
            f"x=(w-text_w)/2:y=h*3/4+25:"
            f"enable='between(t\\,0.5\\,4.5)':"
            f"alpha='if(lt(t\\,1)\\,(t-0.5)*2\\,if(gt(t\\,4)\\,(4.5-t)*2\\,1))'"
        )

    # Brand watermark (top right)
    if brand:
        vf_parts.append(
            f"drawtext=text='{escape_drawtext(brand)}':"
            f"fontsize=28:fontcolor=white@0.5:borderw=2:bordercolor=black@0.3:"
            f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
            f"x=w-text_w-20:y=25"
        )

    # Secondary brand (bottom left)
    if secondary_brand:
        vf_parts.append(
            f"drawtext=text='{escape_drawtext(secondary_brand)}':"
            f"fontsize=22:fontcolor=white@0.4:borderw=1:bordercolor=black@0.2:"
            f"fontfile=C\\\\:/Windows/Fonts/arial.ttf:"
            f"x=20:y=h-50"
        )

    return ",".join(vf_parts)


def compose_clip_no_audio(clip: Path, caption: str, brand: str,
                          secondary_brand: str | None, w: int, h: int,
                          out: Path) -> Path:
    """Add overlays to a clip, no audio."""
    vf = build_overlay_filter(caption, brand, secondary_brand, w, h)
    cmd = [
        "ffmpeg", "-y", "-i", str(clip),
        "-vf", vf,
        "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
        "-an",
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  WARN: overlay failed, trying simpler filter...", flush=True)
        lines = caption.split("\n")
        line1 = escape_drawtext(lines[0])
        cmd2 = [
            "ffmpeg", "-y", "-i", str(clip),
            "-vf", (
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"drawtext=text='{line1}':"
                f"fontsize=50:fontcolor=white:borderw=4:bordercolor=black:"
                f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
                f"x=(w-text_w)/2:y=h*3/4,"
                f"drawtext=text='{escape_drawtext(brand)}':"
                f"fontsize=28:fontcolor=white@0.5:"
                f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
                f"x=w-text_w-20:y=25"
            ),
            "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p", "-an",
            str(out),
        ]
        subprocess.run(cmd2, check=True, capture_output=True)
    return out


def compose_clip_with_tts(clip: Path, tts_wav: Path, caption: str, brand: str,
                          secondary_brand: str | None, w: int, h: int,
                          out: Path) -> Path:
    """Add overlays + TTS audio to a clip."""
    vf = build_overlay_filter(caption, brand, secondary_brand, w, h)

    # Get video duration
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(clip)],
        capture_output=True, text=True,
    )
    vid_dur = float(json.loads(probe.stdout)["format"]["duration"])

    cmd = [
        "ffmpeg", "-y",
        "-i", str(clip),
        "-i", str(tts_wav),
        "-filter_complex", (
            f"[0:v]{vf}[v];"
            f"[1:a]adelay=300|300,apad=whole_dur={vid_dur}[tts];"
            f"[tts]volume=1.0[a]"
        ),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-shortest",
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  WARN: TTS compose failed, trying simpler...", flush=True)
        lines = caption.split("\n")
        line1 = escape_drawtext(lines[0])
        cmd2 = [
            "ffmpeg", "-y",
            "-i", str(clip),
            "-i", str(tts_wav),
            "-filter_complex", (
                f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"drawtext=text='{line1}':"
                f"fontsize=50:fontcolor=white:borderw=4:bordercolor=black:"
                f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
                f"x=(w-text_w)/2:y=h*3/4,"
                f"drawtext=text='{escape_drawtext(brand)}':"
                f"fontsize=28:fontcolor=white@0.5:"
                f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
                f"x=w-text_w-20:y=25[v];"
                f"[1:a]adelay=300|300,apad=whole_dur={vid_dur}[a]"
            ),
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-shortest",
            str(out),
        ]
        subprocess.run(cmd2, check=True, capture_output=True)
    return out


def compose_clip_keep_audio(clip: Path, caption: str, brand: str,
                            secondary_brand: str | None, w: int, h: int,
                            out: Path) -> Path:
    """Add overlays, keep existing audio (LTX native)."""
    vf = build_overlay_filter(caption, brand, secondary_brand, w, h)
    cmd = [
        "ffmpeg", "-y", "-i", str(clip),
        "-vf", vf,
        "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  WARN: overlay+audio failed, trying simpler...", flush=True)
        lines = caption.split("\n")
        line1 = escape_drawtext(lines[0])
        cmd2 = [
            "ffmpeg", "-y", "-i", str(clip),
            "-vf", (
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"drawtext=text='{line1}':"
                f"fontsize=50:fontcolor=white:borderw=4:bordercolor=black:"
                f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
                f"x=(w-text_w)/2:y=h*3/4,"
                f"drawtext=text='{escape_drawtext(brand)}':"
                f"fontsize=28:fontcolor=white@0.5:"
                f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
                f"x=w-text_w-20:y=25"
            ),
            "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            str(out),
        ]
        subprocess.run(cmd2, check=True, capture_output=True)
    return out


def stitch_clips(clips: list[Path], output: Path, has_audio: bool = False) -> Path:
    """Stitch clips together using ffmpeg concat demuxer."""
    concat_file = GENERATED / "_reel_concat.txt"
    with open(concat_file, "w") as f:
        for clip in clips:
            f.write(f"file '{clip.name}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
    ]
    if has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "128k"])
    else:
        cmd.append("-an")
    cmd.append(str(output))
    subprocess.run(cmd, check=True)
    return output


# ── Main pipeline ────────────────────────────────────────────────────

def run_pipeline(config: dict, resume_from: int = 0,
                 skip_keyframes: bool = False) -> Path:
    """Run the full 4-phase reel pipeline."""
    t0 = time.time()

    name = config["name"]
    brand = config.get("brand", "204.ai")
    secondary_brand = config.get("secondary_brand")
    audio_mode = config.get("audio_mode", "none")
    w = config.get("width", 720)
    h = config.get("height", 1280)
    fps = config.get("fps", 24.0)
    frames = config.get("frames_per_clip", 121)
    output_name = config.get("output", f"{name}_reel.mp4")

    keyframe_prompts = config["keyframes"]
    morph_prompts = config["morph_prompts"]
    captions = config["captions"]
    narration = config.get("narration", [])

    n_clips = len(morph_prompts)
    assert len(keyframe_prompts) == n_clips + 1, \
        f"Need {n_clips + 1} keyframes for {n_clips} clips, got {len(keyframe_prompts)}"
    assert len(captions) == n_clips, \
        f"Need {n_clips} captions for {n_clips} clips, got {len(captions)}"
    if audio_mode == "tts":
        assert len(narration) == n_clips, \
            f"Need {n_clips} narration lines for TTS mode, got {len(narration)}"

    # ── Phase 1: Generate keyframe images ────────────────────────────
    face_path = GENERATED / f"_{name}_face.png"
    if not face_path.exists() or not skip_keyframes:
        print("=== Rendering ASCII face ===", flush=True)
        render_ascii_to_png(face_path)
    face_name = upload_image(face_path)

    n_kf = len(keyframe_prompts)
    kf_imgs = []

    if skip_keyframes:
        print(f"\n=== PHASE 1: Loading {n_kf} existing keyframes ===\n", flush=True)
        for i in range(n_kf):
            kf_path = GENERATED / f"{name}_kf{i+1}.png"
            if not kf_path.exists():
                raise FileNotFoundError(
                    f"Keyframe {kf_path} not found. Cannot --skip-keyframes."
                )
            kf_imgs.append(kf_path)
            print(f"  Loaded: {kf_path.name}", flush=True)
    else:
        print(f"\n=== PHASE 1: {n_kf} keyframe images ===\n", flush=True)
        for i, kf_prompt in enumerate(keyframe_prompts, 1):
            print(f"--- KF {i}/{n_kf} ---", flush=True)
            img = gen_keyframe(kf_prompt, f"{name}_kf{i}.png", face_name)
            kf_imgs.append(img)
            print(f"    ({time.time()-t0:.0f}s)\n", flush=True)

    # ── Phase 2: Generate morph clips ────────────────────────────────
    print(f"=== PHASE 2: {n_clips} morph clips ===\n", flush=True)
    raw_clips = []
    for i in range(n_clips):
        clip_num = i + 1
        if clip_num < resume_from:
            clip_path = GENERATED / f"{name}_clip_{clip_num}.mp4"
            if clip_path.exists():
                print(f"  [RESUME SKIP] clip {clip_num}", flush=True)
                raw_clips.append(clip_path)
                continue
        print(f"--- Clip {clip_num}/{n_clips}: KF{clip_num} -> KF{clip_num+1} ---", flush=True)
        clip = gen_morph_clip(
            kf_imgs[i], kf_imgs[i+1], morph_prompts[i],
            f"{name}_clip_{clip_num}.mp4",
            frames=frames, w=w, h=h, fps=fps, audio_mode=audio_mode,
        )
        raw_clips.append(clip)
        print(f"    ({time.time()-t0:.0f}s)\n", flush=True)

    # ── Phase 2.5 (optional): Generate TTS audio ────────────────────
    tts_files = []
    if audio_mode == "tts":
        print("=== PHASE 2.5: TTS narration ===\n", flush=True)
        for i, speech in enumerate(narration, 1):
            wav = GENERATED / f"{name}_tts_{i}.wav"
            generate_tts(speech, wav)
            tts_files.append(wav)
        print(f"    TTS done ({time.time()-t0:.0f}s)\n", flush=True)

    # ── Phase 3: Overlays + branding ─────────────────────────────────
    print(f"=== PHASE 3: Overlays + branding ===\n", flush=True)
    composed_clips = []

    for i in range(n_clips):
        out = GENERATED / f"{name}_composed_{i+1}.mp4"
        if out.exists():
            print(f"  [SKIP] {out.name}", flush=True)
            composed_clips.append(out)
            continue

        caption = captions[i]
        clip = raw_clips[i]
        print(f"  Composing {i+1}: \"{caption.split(chr(10))[0]}\"", flush=True)

        if audio_mode == "none":
            compose_clip_no_audio(clip, caption, brand, secondary_brand, w, h, out)
        elif audio_mode == "tts":
            compose_clip_with_tts(clip, tts_files[i], caption, brand, secondary_brand, w, h, out)
        elif audio_mode == "native":
            compose_clip_keep_audio(clip, caption, brand, secondary_brand, w, h, out)

        composed_clips.append(out)

    # ── Phase 4: Stitch final video ──────────────────────────────────
    print(f"\n=== PHASE 4: Stitching final {n_clips * 5}s video ===\n", flush=True)
    final = GENERATED / output_name
    has_audio = audio_mode in ("tts", "native")
    stitch_clips(composed_clips, final, has_audio=has_audio)

    elapsed = time.time() - t0
    sz = final.stat().st_size / 1024 / 1024
    print(f"\n=== DONE! ===", flush=True)
    print(f"Final: {final} ({sz:.1f} MB)", flush=True)
    print(f"Time: {elapsed/60:.1f} minutes", flush=True)
    return final


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a branded reel/ad video from a JSON config"
    )
    parser.add_argument("config", help="Path to JSON config file")
    parser.add_argument("--resume", type=int, default=0,
                        help="Resume morph generation from clip N")
    parser.add_argument("--skip-keyframes", action="store_true",
                        help="Skip keyframe generation (use existing)")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        return 1

    with open(config_path) as f:
        config = json.load(f)

    final = run_pipeline(config, resume_from=args.resume,
                         skip_keyframes=args.skip_keyframes)
    print(f"\nOutput: {final}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
