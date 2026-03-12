"""
Photobooth Explainer Video v2
Continuous reel — each keyframe is shared between adjacent clips.
8 keyframes → 7 morph clips → stitched with text overlays → seamless loop.

Venue: neon-lit art gallery opening night. Consistent character & style.
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

# ── Consistent style suffix for ALL image prompts ────────────────────────
STYLE = (
    "Studio Ghibli style, 2D anime digital painting, soft warm lighting, "
    "rich purple and cyan neon accents, golden highlights, "
    "cinematic composition, highly detailed, consistent art style"
)

VENUE = (
    "inside a glamorous neon-lit art gallery opening night, "
    "purple and cyan neon strip lights on dark walls, warm golden spotlights, "
    "204.ai logo glowing in neon purple on the wall, polished dark floor reflections, "
    "other small animal guests visible in background"
)

CHAR = (
    "a cute adorable round fluffy golden-brown hamster character with big sparkly eyes "
    "and rosy cheeks, wearing a tiny purple bowtie and a small glowing sci-fi headset"
)

# ── 8 keyframe descriptions (consecutive frames shared between clips) ────
# Frame N end = Frame N+1 start → continuous reel
KEYFRAMES = [
    # KF1: Ari arrives at the gallery entrance
    f"{CHAR} standing outside a grand art gallery entrance at night, looking up in wonder at "
    f"a glowing neon sign reading 204.ai PHOTOBOOTH above ornate doors, warm light spilling "
    f"out from inside, a small crowd of animal guests entering, {STYLE}",

    # KF2: Ari approaches the photobooth kiosk inside
    f"{CHAR} standing inside the gallery {VENUE}, facing a sleek modern photobooth kiosk "
    f"with a large screen displaying STEP UP and a camera mounted on top, paws reaching "
    f"toward the kiosk excitedly, {STYLE}",

    # KF3: Camera captures — flash moment
    f"{CHAR} posing in front of the photobooth camera with a big confident smile, "
    f"a bright camera flash illuminating the scene with golden light rays and sparkles, "
    f"{VENUE}, {STYLE}",

    # KF4: AI transformation on screen
    f"A large glowing display screen showing {CHAR} being magically transformed, "
    f"half the face is normal and half is a golden royal knight with a crown, "
    f"swirling neural network patterns and sparkles around the screen, {VENUE}, {STYLE}",

    # KF5: Portrait revealed — crowd amazed
    f"A large display screen showing the completed magnificent portrait of {CHAR} as a golden "
    f"royal knight with a crown, two hamster guests below looking up in awe with mouths open, "
    f"golden sparkles falling like confetti, {VENUE}, {STYLE}",

    # KF6: Printer producing the print
    f"{CHAR} eagerly grabbing a freshly printed photo portrait from a sleek printer, "
    f"the print shows the knight portrait with a 204.ai watermark, a green status light "
    f"glowing on the printer, {VENUE}, {STYLE}",

    # KF7: Scanning QR → gallery on phone
    f"{CHAR} holding up a tiny phone showing a beautiful grid gallery of AI portraits, "
    f"a QR code visible on the kiosk screen behind, the phone screen shows gallery.204.ai "
    f"with rows of transformed portraits, {VENUE}, {STYLE}",

    # KF8: Watching morph video — loops back to entrance vibe
    f"{CHAR} standing in the gallery watching a magical morphing video on a floating screen, "
    f"film strip frames and sparkles floating in the air, other guests gathered around "
    f"mesmerized, the neon 204.ai sign glowing in background, {VENUE}, {STYLE}",
]

# ── 7 morph transition prompts (clip N morphs KF[N] → KF[N+1]) ──────────
MORPH_PROMPTS = [
    # Clip 1: Entrance → Approach kiosk
    "A cute hamster walks through grand doors into a neon-lit art gallery and approaches "
    "a glowing photobooth kiosk. The camera follows smoothly. Purple and cyan neon lights, "
    "warm golden spotlights. Smooth cinematic dolly movement, consistent lighting.",

    # Clip 2: At kiosk → Flash capture
    "A cute hamster poses in front of a photobooth camera. A bright flash goes off with "
    "golden light rays and sparkles filling the frame. The hamster's expression shifts from "
    "posing to delighted surprise. Steady camera, smooth lighting transition.",

    # Clip 3: Flash → AI transformation
    "The camera pulls back to reveal a large screen where the hamster's photo is being "
    "magically transformed by AI. Neural network patterns and sparkles swirl as the plain "
    "portrait morphs into a golden knight. Smooth magical transformation, steady camera.",

    # Clip 4: Transformation → Portrait reveal
    "The AI transformation completes on screen — the full golden knight portrait is revealed. "
    "Golden sparkles fall like confetti. Hamster guests below look up in amazement, mouths open. "
    "Celebratory atmosphere, steady camera, warm golden lighting.",

    # Clip 5: Portrait → Print
    "A printer next to the screen whirs to life and produces a beautiful printed portrait. "
    "The hamster eagerly reaches for the print as it emerges. The printer's green light glows. "
    "Smooth animation, steady camera, warm lighting.",

    # Clip 6: Print → Phone gallery
    "The hamster puts down the print and pulls out a tiny phone, scanning a QR code on the "
    "kiosk screen. The phone loads a beautiful gallery page showing rows of AI portraits. "
    "Smooth transition, steady camera, consistent neon lighting.",

    # Clip 7: Gallery → Morph video (loops to entrance)
    "The hamster looks up from the phone at a floating screen playing a magical morphing video. "
    "Film strip frames and sparkles float through the air. Other animal guests gather to watch, "
    "mesmerized. Smooth cinematic motion, steady camera, neon gallery atmosphere.",
]

# ── Narration text overlays per clip ─────────────────────────────────────
CAPTIONS = [
    "Step right up!",
    "Strike a pose!",
    "AI magic...",
    "Behold!",
    "Take it home!",
    "Share it!",
    "Watch the magic!",
]


# ── Image & morph generation helpers (reused from v1) ────────────────────

from PIL import Image, ImageDraw, ImageFont

HAMSTER_ASCII = r"""
   (\(\ /)/)
    ( ^.^ )
  * ( " ^ " ) *
     ( w )
      (   )
"""


def render_ascii_to_png(out_path: Path) -> None:
    width, height = 1024, 1024
    img = Image.new("RGB", (width, height), (30, 30, 35))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("consola.ttf", 64)
    except OSError:
        try:
            font = ImageFont.truetype("cour.ttf", 64)
        except OSError:
            font = ImageFont.load_default()
    lines = HAMSTER_ASCII.strip().split("\n")
    line_height = 72
    total_height = len(lines) * line_height
    y_start = (height - total_height) // 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        y = y_start + i * line_height
        draw.text((x, y), line, fill=(255, 200, 100), font=font)
    img.save(str(out_path))


def upload_image(file_path: Path) -> str:
    import mimetypes
    boundary = "----PBv2UploadBoundary"
    filename = file_path.name
    mime = mimetypes.guess_type(filename)[0] or "image/png"
    data = file_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}\r\n".encode() + (
        f'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
        f"--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(
        f"{COMFYUI}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read())
    return result["name"]


def build_selfie_workflow(prompt: str, image_name: str, seed: int) -> dict:
    return {
        "3": {
            "inputs": {
                "seed": seed, "steps": 4, "cfg": 1,
                "sampler_name": "euler", "scheduler": "simple", "denoise": 1,
                "model": ["75", 0], "positive": ["111", 0],
                "negative": ["110", 0], "latent_image": ["88", 0],
            },
            "class_type": "KSampler",
        },
        "8": {"inputs": {"samples": ["3", 0], "vae": ["39", 0]}, "class_type": "VAEDecode"},
        "37": {
            "inputs": {"unet_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors", "weight_dtype": "default"},
            "class_type": "UNETLoader",
        },
        "38": {
            "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"},
            "class_type": "CLIPLoader",
        },
        "39": {"inputs": {"vae_name": "qwen_image_vae.safetensors"}, "class_type": "VAELoader"},
        "60": {"inputs": {"filename_prefix": "ari_pb2/img", "images": ["8", 0]}, "class_type": "SaveImage"},
        "66": {"inputs": {"shift": 3, "model": ["89", 0]}, "class_type": "ModelSamplingAuraFlow"},
        "75": {"inputs": {"strength": 1, "model": ["66", 0]}, "class_type": "CFGNorm"},
        "78": {"inputs": {"image": image_name}, "class_type": "LoadImage"},
        "88": {"inputs": {"pixels": ["93", 0], "vae": ["39", 0]}, "class_type": "VAEEncode"},
        "89": {
            "inputs": {
                "lora_name": "Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors",
                "strength_model": 1, "model": ["37", 0],
            },
            "class_type": "LoraLoaderModelOnly",
        },
        "93": {
            "inputs": {"upscale_method": "lanczos", "megapixels": 1, "resolution_steps": 1, "image": ["78", 0]},
            "class_type": "ImageScaleToTotalPixels",
        },
        "110": {
            "inputs": {"prompt": "", "clip": ["38", 0], "vae": ["39", 0], "image1": ["93", 0]},
            "class_type": "TextEncodeQwenImageEditPlus",
        },
        "111": {
            "inputs": {"prompt": prompt, "clip": ["38", 0], "vae": ["39", 0], "image1": ["93", 0]},
            "class_type": "TextEncodeQwenImageEditPlus",
        },
    }


def queue_selfie(workflow: dict, timeout: int = 240) -> tuple:
    payload = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        f"{COMFYUI}/prompt", data=payload,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    prompt_id = json.loads(resp.read())["prompt_id"]
    print(f"  Queued selfie prompt_id={prompt_id}", flush=True)
    for _ in range(timeout // 2):
        time.sleep(2)
        try:
            h = urllib.request.urlopen(f"{COMFYUI}/history/{prompt_id}")
            history = json.loads(h.read())
            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(f"Selfie generation failed: {json.dumps(status)}")
                if status.get("completed"):
                    for node_out in entry.get("outputs", {}).values():
                        if "images" in node_out:
                            img = node_out["images"][0]
                            return img["filename"], img.get("subfolder", ""), img.get("type", "output")
                    raise RuntimeError("No image output found")
        except urllib.error.URLError:
            pass
        print(".", end="", flush=True)
    raise TimeoutError("Selfie timed out")


def download_file(filename: str, subfolder: str, file_type: str, dest: Path) -> None:
    url = f"{COMFYUI}/view?filename={filename}&subfolder={subfolder}&type={file_type}"
    urllib.request.urlretrieve(url, str(dest))


def generate_selfie(prompt: str, output_name: str, face_server_name: str) -> Path:
    dest = GENERATED / output_name
    if dest.exists():
        print(f"  [SKIP] {output_name} already exists", flush=True)
        return dest
    seed = int(time.time() * 1000) % (2**32)
    workflow = build_selfie_workflow(prompt, face_server_name, seed)
    filename, subfolder, img_type = queue_selfie(workflow)
    print(flush=True)
    download_file(filename, subfolder, img_type, dest)
    print(f"  Saved: {dest.name}", flush=True)
    return dest


def build_morph_workflow(prompt, start_image, end_image, seed, frames=121,
                         width=720, height=1280, fps=24.0):
    sys.path.insert(0, str(ROOT / "skills" / "comfy"))
    import morph as morph_mod
    return morph_mod.build_workflow(prompt, start_image, end_image, seed, frames, width, height, fps)


def queue_morph(workflow: dict, timeout: int = 600) -> tuple:
    payload = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        f"{COMFYUI}/prompt", data=payload,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    prompt_id = json.loads(resp.read())["prompt_id"]
    print(f"  Queued morph prompt_id={prompt_id}", flush=True)
    for _ in range(timeout // 3):
        time.sleep(3)
        try:
            h = urllib.request.urlopen(f"{COMFYUI}/history/{prompt_id}")
            history = json.loads(h.read())
            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    msgs = entry.get("status", {}).get("messages", [])
                    raise RuntimeError(f"Morph failed: {json.dumps(msgs)}")
                if status.get("completed"):
                    outputs = entry.get("outputs", {})
                    for node_out in outputs.values():
                        if "gifs" in node_out:
                            vid = node_out["gifs"][0]
                            return vid["filename"], vid.get("subfolder", ""), vid.get("type", "output")
                    for node_out in outputs.values():
                        if "images" in node_out:
                            img = node_out["images"][0]
                            return img["filename"], img.get("subfolder", ""), img.get("type", "output")
                    raise RuntimeError("No morph output found")
        except urllib.error.URLError:
            pass
        print(".", end="", flush=True)
    raise TimeoutError("Morph timed out")


def generate_morph(start_path: Path, end_path: Path, prompt: str, output_name: str) -> Path:
    dest = GENERATED / output_name
    if dest.exists():
        print(f"  [SKIP] {output_name} already exists", flush=True)
        return dest
    start_name = upload_image(start_path)
    end_name = upload_image(end_path)
    seed = int(time.time() * 1000) % (2**53)
    workflow = build_morph_workflow(prompt, start_name, end_name, seed)
    filename, subfolder, out_type = queue_morph(workflow)
    print(flush=True)
    download_file(filename, subfolder, out_type, dest)
    print(f"  Saved: {dest.name}", flush=True)
    return dest


# ── Main pipeline ────────────────────────────────────────────────────────

def main():
    total_start = time.time()

    # 1. Render and upload ASCII face
    face_path = GENERATED / "_pb2_face_input.png"
    print("=== Rendering ASCII face ===", flush=True)
    render_ascii_to_png(face_path)
    face_server_name = upload_image(face_path)
    print(f"Uploaded face: {face_server_name}\n", flush=True)

    # 2. Generate 8 keyframe images (consecutive pairs shared)
    print("=== PHASE 1: Generating 8 keyframe images ===\n", flush=True)
    kf_images = []
    for i, kf_prompt in enumerate(KEYFRAMES, 1):
        print(f"--- Keyframe {i}/8 ---", flush=True)
        img = generate_selfie(kf_prompt, f"pb2_kf{i}.png", face_server_name)
        kf_images.append(img)
        elapsed = time.time() - total_start
        print(f"    KF{i} done ({elapsed:.0f}s elapsed)\n", flush=True)

    # 3. Generate 7 morph clips (KF[i] → KF[i+1])
    print("=== PHASE 2: Generating 7 morph clips (121 frames each) ===\n", flush=True)
    raw_clips = []
    for i in range(7):
        start_img = kf_images[i]
        end_img = kf_images[i + 1]
        prompt = MORPH_PROMPTS[i]
        clip_name = f"pb2_clip_{i+1}.mp4"
        print(f"--- Clip {i+1}/7: KF{i+1} -> KF{i+2} ---", flush=True)
        clip = generate_morph(start_img, end_img, prompt, clip_name)
        raw_clips.append(clip)
        elapsed = time.time() - total_start
        print(f"    Clip {i+1} done ({elapsed:.0f}s elapsed)\n", flush=True)

    # 4. Add text overlays to each clip and force consistent resolution
    print("=== PHASE 3: Adding text overlays ===\n", flush=True)
    TARGET_W, TARGET_H = 720, 1280
    overlay_clips = []

    for i, (clip, caption) in enumerate(zip(raw_clips, CAPTIONS)):
        out = GENERATED / f"pb2_overlay_{i+1}.mp4"
        if out.exists():
            print(f"  [SKIP] {out.name} already exists", flush=True)
            overlay_clips.append(out)
            continue

        # Escape single quotes for ffmpeg drawtext
        safe_caption = caption.replace("'", "'\\''")

        # Force exact resolution + add centered bottom text with fade in/out
        cmd = [
            "ffmpeg", "-y", "-i", str(clip),
            "-vf", (
                f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
                f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"drawtext=text='{safe_caption}':"
                f"fontsize=52:fontcolor=white:borderw=3:bordercolor=black:"
                f"fontfile=C\\\\:/Windows/Fonts/arial.ttf:"
                f"x=(w-text_w)/2:y=h-h/6:"
                f"enable='between(t,0.5,4.5)':"
                f"alpha='if(lt(t,1),t-0.5,if(gt(t,4),4.5-t,1))'"
            ),
            "-c:v", "libx264", "-crf", "19",
            "-pix_fmt", "yuv420p",
            "-an",  # strip audio for clean concat
            str(out)
        ]
        print(f"  Overlay clip {i+1}: \"{caption}\"", flush=True)
        subprocess.run(cmd, check=True, capture_output=True)
        overlay_clips.append(out)

    # 5. Stitch all overlay clips into final seamless video
    print("\n=== PHASE 4: Stitching final video ===\n", flush=True)
    concat_file = GENERATED / "_pb2_concat.txt"
    with open(concat_file, "w") as f:
        for clip in overlay_clips:
            f.write(f"file '{clip.name}'\n")

    final_output = GENERATED / "photobooth_explainer_v2.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(final_output)
    ]
    print(f"Running: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True)

    elapsed = time.time() - total_start
    print(f"\n=== DONE! ===", flush=True)
    print(f"Final video: {final_output}", flush=True)
    print(f"Total time: {elapsed/60:.1f} minutes", flush=True)


if __name__ == "__main__":
    main()
