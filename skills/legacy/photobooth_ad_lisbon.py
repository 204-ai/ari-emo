"""
204.ai Photobooth Advertisement — "A Night in Lisbon"
30 seconds, 6 scenes x 5s (121 frames each), continuous reel.
TTS voice narration + subtitles + ambient audio from LTX.

Concept: Ari the hamster arrives at a magical rooftop party in Lisbon
overlooking the Tagus river. Discovers the 204.ai photobooth.
Gets transformed into a Portuguese explorer. Becomes the star of the night.
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
KOKORO_MODEL = ROOT / "models" / "kokoro-v1.0.int8.onnx"
KOKORO_VOICES = ROOT / "models" / "voices-v1.0.bin"

# ── Consistent style tokens ─────────────────────────────────────────────
CHAR = (
    "a cute adorable round fluffy golden-brown hamster character with big sparkly eyes "
    "and rosy cheeks, wearing a tiny purple bowtie and a small glowing purple headset"
)

STYLE = (
    "Studio Ghibli anime style, 2D digital painting, soft warm Mediterranean lighting, "
    "rich purple and warm golden accents, twinkling string lights, "
    "cinematic composition, highly detailed, cohesive warm color palette"
)

VENUE = (
    "a beautiful rooftop terrace party in Lisbon at night, overlooking the Tagus river "
    "and the glowing city skyline, traditional Portuguese azulejo tile walls, "
    "warm string lights draped overhead, potted plants and lanterns, "
    "other stylish animal guests mingling"
)

# ── 7 keyframes (shared boundaries for 6 continuous clips) ──────────────
KEYFRAMES = [
    # KF1: Arriving at the rooftop
    f"{CHAR} climbing the last steps of a narrow Lisbon stairway to a rooftop terrace, "
    f"looking up in wonder at the view, the glowing city and Tagus river visible beyond, "
    f"warm string lights twinkling above, Portuguese azulejo tiles on the walls, "
    f"the sound of music and laughter from the party above, {STYLE}",

    # KF2: Discovering the photobooth
    f"{CHAR} standing on the rooftop terrace party, eyes wide with excitement, spotting "
    f"a glowing 204.ai photobooth kiosk set up between potted orange trees, "
    f"the kiosk radiates purple and golden light, {VENUE}, {STYLE}",

    # KF3: Posing — "say queijo!"
    f"{CHAR} standing in front of the photobooth camera making a funny face with tongue out "
    f"and tiny paws up, a Portuguese tile mosaic backdrop behind, "
    f"the crowd of animal friends laughing and watching, warm golden lighting, "
    f"{VENUE}, {STYLE}",

    # KF4: Camera flash
    f"{CHAR} caught in a brilliant golden camera flash, sparkles and light rays bursting "
    f"from the photobooth, the Lisbon skyline twinkling in the background, "
    f"other party guests shielding their eyes from the bright flash, "
    f"{VENUE}, {STYLE}",

    # KF5: AI transformation — Portuguese explorer
    f"A large glowing screen at the party showing {CHAR} being magnificently transformed "
    f"by AI into a Portuguese explorer hamster, wearing a grand velvet cape, "
    f"a golden compass, and a feathered captain hat, ocean maps and stars swirling "
    f"around the portrait, the crowd gasping in amazement, {VENUE}, {STYLE}",

    # KF6: Holding the print — star of the party
    f"{CHAR} proudly holding up a beautiful printed portrait of the explorer version, "
    f"friends gathered around taking photos, someone handing Ari a tiny pastel de nata, "
    f"the Lisbon skyline glowing warmly behind, confetti and sparkles in the air, "
    f"the 204.ai neon logo on the kiosk glowing purple, {VENUE}, {STYLE}",

    # KF7: Wide shot — the party from above (loops back)
    f"Wide aerial view of the beautiful Lisbon rooftop party at night, "
    f"the glowing 204.ai photobooth visible in the center with a happy queue of animals, "
    f"the Tagus river and 25 de Abril bridge lit up in the distance, "
    f"warm string lights creating a magical atmosphere, {STYLE}",
]

# ── 6 morph prompts ─────────────────────────────────────────────────────
MORPH_PROMPTS = [
    # Clip 1: Arrive -> Discover booth
    "A cute hamster reaches the top of stairs and walks onto a magical Lisbon rooftop "
    "terrace party. String lights twinkle, music plays. The hamster spots a glowing "
    "photobooth kiosk between orange trees. Eyes go wide. Smooth camera push forward, "
    "warm golden lighting, gentle ambient music.",

    # Clip 2: Discover -> Pose
    "The cute hamster approaches the glowing photobooth kiosk and steps in front of the "
    "camera. Makes a funny face with tongue out and paws up. Friends laugh. "
    "Portuguese tile backdrop behind. Smooth animation, warm party atmosphere, "
    "gentle ambient music and laughter.",

    # Clip 3: Pose -> Flash
    "A bright golden camera flash fires from the photobooth, illuminating the cute hamster "
    "and the entire rooftop. Sparkles and light rays burst outward. The Lisbon skyline "
    "twinkles in the background. Party guests shield their eyes. "
    "Smooth flash effect, warm golden burst, ambient party sounds.",

    # Clip 4: Flash -> Transformation
    "After the flash, a large screen lights up showing the hamster being transformed by AI. "
    "The portrait morphs into a magnificent Portuguese explorer with a velvet cape, "
    "golden compass, and feathered hat. Ocean maps and stars swirl. The crowd gasps. "
    "Smooth magical transformation, warm golden and purple lighting, ambient music.",

    # Clip 5: Transformation -> Print hero moment
    "The explorer portrait is complete. A printer produces a beautiful print. The hamster "
    "grabs it proudly, holding it high. Friends gather around, someone offers a tiny "
    "pastel de nata. Confetti falls. The Lisbon skyline glows behind. "
    "Celebratory energy, smooth animation, warm party music.",

    # Clip 6: Hero moment -> Wide aerial
    "The camera slowly pulls back and rises above the rooftop, revealing the full party "
    "scene from above. The glowing photobooth is visible with a queue of happy animals. "
    "The Tagus river and 25 de Abril bridge glow in the distance. String lights twinkle. "
    "Smooth cinematic aerial pullback, warm ambient music fading.",
]

# ── Narration lines (TTS) + subtitle text ────────────────────────────────
NARRATION = [
    ("Lisbon nights hit different.", "Lisbon nights\nhit different."),
    ("Wait... is that a photobooth?", "Wait...\nis that a photobooth?"),
    ("Say cheese! Or should I say... queijo!", "Say queijo!"),
    ("Three, two, one... flash!", "Three, two, one...\nflash!"),
    ("The AI turned me into a Portuguese explorer! Vasco da Hamster!", "Vasco da Hamster!"),
    ("Two oh four dot ai. Making every party unforgettable.", "204.ai\nEvery party. Unforgettable."),
]


# ── TTS generation ──────────────────────────────────────────────────────

def generate_tts(text: str, output_path: Path, voice: str = "af_heart", speed: float = 1.1) -> Path:
    """Generate TTS audio using Kokoro ONNX."""
    if output_path.exists():
        print(f"  [SKIP TTS] {output_path.name}", flush=True)
        return output_path

    from kokoro_onnx import Kokoro
    import soundfile as sf

    kokoro = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    samples, sr = kokoro.create(text, voice=voice, speed=speed)
    sf.write(str(output_path), samples, sr)
    dur = len(samples) / sr
    print(f"  TTS: \"{text[:40]}...\" -> {dur:.1f}s", flush=True)
    return output_path


# ── Image & morph helpers ────────────────────────────────────────────────

from PIL import Image, ImageDraw, ImageFont

HAMSTER_ASCII = r"""
   (\(\ /)/)
    ( ^.^ )
  * ( " ^ " ) *
     ( w )
      (   )
"""


def render_ascii_to_png(out_path):
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
    lh = 72
    th = len(lines) * lh
    ys = (height - th) // 2
    for i, line in enumerate(lines):
        bb = draw.textbbox((0, 0), line, font=font)
        tw = bb[2] - bb[0]
        draw.text(((width - tw) // 2, ys + i * lh), line, fill=(255, 200, 100), font=font)
    img.save(str(out_path))


def upload_image(fp):
    import mimetypes
    boundary = "----LisbonAdUpload"
    fn = fp.name
    mime = mimetypes.guess_type(fn)[0] or "image/png"
    data = fp.read_bytes()
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


def build_selfie_wf(prompt, img_name, seed):
    return {
        "3": {"inputs": {"seed": seed, "steps": 4, "cfg": 1, "sampler_name": "euler", "scheduler": "simple", "denoise": 1, "model": ["75", 0], "positive": ["111", 0], "negative": ["110", 0], "latent_image": ["88", 0]}, "class_type": "KSampler"},
        "8": {"inputs": {"samples": ["3", 0], "vae": ["39", 0]}, "class_type": "VAEDecode"},
        "37": {"inputs": {"unet_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors", "weight_dtype": "default"}, "class_type": "UNETLoader"},
        "38": {"inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"}, "class_type": "CLIPLoader"},
        "39": {"inputs": {"vae_name": "qwen_image_vae.safetensors"}, "class_type": "VAELoader"},
        "60": {"inputs": {"filename_prefix": "ari_lisbon/img", "images": ["8", 0]}, "class_type": "SaveImage"},
        "66": {"inputs": {"shift": 3, "model": ["89", 0]}, "class_type": "ModelSamplingAuraFlow"},
        "75": {"inputs": {"strength": 1, "model": ["66", 0]}, "class_type": "CFGNorm"},
        "78": {"inputs": {"image": img_name}, "class_type": "LoadImage"},
        "88": {"inputs": {"pixels": ["93", 0], "vae": ["39", 0]}, "class_type": "VAEEncode"},
        "89": {"inputs": {"lora_name": "Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors", "strength_model": 1, "model": ["37", 0]}, "class_type": "LoraLoaderModelOnly"},
        "93": {"inputs": {"upscale_method": "lanczos", "megapixels": 1, "resolution_steps": 1, "image": ["78", 0]}, "class_type": "ImageScaleToTotalPixels"},
        "110": {"inputs": {"prompt": "", "clip": ["38", 0], "vae": ["39", 0], "image1": ["93", 0]}, "class_type": "TextEncodeQwenImageEditPlus"},
        "111": {"inputs": {"prompt": prompt, "clip": ["38", 0], "vae": ["39", 0], "image1": ["93", 0]}, "class_type": "TextEncodeQwenImageEditPlus"},
    }


def queue_wait_selfie(wf, timeout=240):
    payload = json.dumps({"prompt": wf}).encode()
    req = urllib.request.Request(f"{COMFYUI}/prompt", data=payload, headers={"Content-Type": "application/json"})
    pid = json.loads(urllib.request.urlopen(req).read())["prompt_id"]
    print(f"  Queued selfie {pid[:12]}...", flush=True)
    for _ in range(timeout // 2):
        time.sleep(2)
        try:
            h = json.loads(urllib.request.urlopen(f"{COMFYUI}/history/{pid}").read())
            if pid in h:
                e = h[pid]
                if e.get("status", {}).get("status_str") == "error":
                    raise RuntimeError(f"Failed: {json.dumps(e['status'])}")
                if e.get("status", {}).get("completed"):
                    for o in e.get("outputs", {}).values():
                        if "images" in o:
                            img = o["images"][0]
                            return img["filename"], img.get("subfolder", ""), img.get("type", "output")
                    raise RuntimeError("No output")
        except urllib.error.URLError:
            pass
        print(".", end="", flush=True)
    raise TimeoutError("Timeout")


def dl(fn, sf, ft, dest):
    urllib.request.urlretrieve(f"{COMFYUI}/view?filename={fn}&subfolder={sf}&type={ft}", str(dest))


def gen_selfie(prompt, name, face):
    dest = GENERATED / name
    if dest.exists():
        print(f"  [SKIP] {name}", flush=True)
        return dest
    seed = int(time.time() * 1000) % (2**32)
    fn, sf, ft = queue_wait_selfie(build_selfie_wf(prompt, face, seed))
    print(flush=True)
    dl(fn, sf, ft, dest)
    print(f"  Saved: {name}", flush=True)
    return dest


def build_morph_wf(prompt, s_img, e_img, seed, frames=121, w=720, h=1280, fps=24.0):
    sys.path.insert(0, str(ROOT / "skills" / "comfy"))
    import morph
    return morph.build_workflow(prompt, s_img, e_img, seed, frames, w, h, fps)


def queue_wait_morph(wf, timeout=600):
    payload = json.dumps({"prompt": wf}).encode()
    req = urllib.request.Request(f"{COMFYUI}/prompt", data=payload, headers={"Content-Type": "application/json"})
    pid = json.loads(urllib.request.urlopen(req).read())["prompt_id"]
    print(f"  Queued morph {pid[:12]}...", flush=True)
    for _ in range(timeout // 3):
        time.sleep(3)
        try:
            h = json.loads(urllib.request.urlopen(f"{COMFYUI}/history/{pid}").read())
            if pid in h:
                e = h[pid]
                if e.get("status", {}).get("status_str") == "error":
                    raise RuntimeError(f"Failed: {json.dumps(e.get('status',{}).get('messages',[]))}")
                if e.get("status", {}).get("completed"):
                    for o in e.get("outputs", {}).values():
                        if "gifs" in o:
                            v = o["gifs"][0]
                            return v["filename"], v.get("subfolder", ""), v.get("type", "output")
                    for o in e.get("outputs", {}).values():
                        if "images" in o:
                            v = o["images"][0]
                            return v["filename"], v.get("subfolder", ""), v.get("type", "output")
                    raise RuntimeError("No output")
        except urllib.error.URLError:
            pass
        print(".", end="", flush=True)
    raise TimeoutError("Timeout")


def gen_morph(s_path, e_path, prompt, name):
    dest = GENERATED / name
    if dest.exists():
        print(f"  [SKIP] {name}", flush=True)
        return dest
    s_n = upload_image(s_path)
    e_n = upload_image(e_path)
    seed = int(time.time() * 1000) % (2**53)
    fn, sf, ft = queue_wait_morph(build_morph_wf(prompt, s_n, e_n, seed))
    print(flush=True)
    dl(fn, sf, ft, dest)
    print(f"  Saved: {name}", flush=True)
    return dest


# ── Main pipeline ────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    W, H = 720, 1280

    # 1. Face
    face_path = GENERATED / "_lisbon_face.png"
    print("=== Rendering face ===", flush=True)
    render_ascii_to_png(face_path)
    face = upload_image(face_path)

    # 2. Keyframes
    print("\n=== PHASE 1: 7 keyframe images ===\n", flush=True)
    kfs = []
    for i, p in enumerate(KEYFRAMES, 1):
        print(f"--- KF {i}/7 ---", flush=True)
        kfs.append(gen_selfie(p, f"lisbon_kf{i}.png", face))
        print(f"    ({time.time()-t0:.0f}s)\n", flush=True)

    # 3. Morph clips
    print("=== PHASE 2: 6 morph clips ===\n", flush=True)
    clips = []
    for i in range(6):
        print(f"--- Clip {i+1}/6: KF{i+1} -> KF{i+2} ---", flush=True)
        clips.append(gen_morph(kfs[i], kfs[i+1], MORPH_PROMPTS[i], f"lisbon_clip_{i+1}.mp4"))
        print(f"    ({time.time()-t0:.0f}s)\n", flush=True)

    # 4. TTS narration for each scene
    print("=== PHASE 3: TTS narration ===\n", flush=True)
    tts_files = []
    for i, (speech, _) in enumerate(NARRATION, 1):
        wav = GENERATED / f"lisbon_tts_{i}.wav"
        generate_tts(speech, wav, voice="af_heart", speed=1.1)
        tts_files.append(wav)
    print(f"    TTS done ({time.time()-t0:.0f}s)\n", flush=True)

    # 5. Compose each clip: scale + subtitles + TTS audio + 204.ai watermark
    print("=== PHASE 4: Composing clips with audio + subtitles ===\n", flush=True)
    composed = []

    for i, (clip, tts, (_, subtitle)) in enumerate(zip(clips, tts_files, NARRATION)):
        out = GENERATED / f"lisbon_composed_{i+1}.mp4"
        if out.exists():
            print(f"  [SKIP] {out.name}", flush=True)
            composed.append(out)
            continue

        lines = subtitle.split("\n")
        line1 = lines[0].replace("'", "'\\''").replace(":", "\\:").replace(",", "\\,")
        line2 = lines[1].replace("'", "'\\''").replace(":", "\\:").replace(",", "\\,") if len(lines) > 1 else ""

        # Build ffmpeg filter
        vf_parts = [
            f"scale={W}:{H}:force_original_aspect_ratio=decrease",
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black",
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

        # 204.ai watermark
        vf_parts.append(
            f"drawtext=text='204.ai':"
            f"fontsize=28:fontcolor=white@0.5:borderw=2:bordercolor=black@0.3:"
            f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
            f"x=w-text_w-20:y=25"
        )

        vf = ",".join(vf_parts)

        # Get video duration for audio padding
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(clip)],
            capture_output=True, text=True
        )
        vid_dur = float(json.loads(probe.stdout)["format"]["duration"])

        # Pad TTS audio to match video duration, with 0.3s delay at start
        # Mix: TTS narration as main audio track
        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip),
            "-i", str(tts),
            "-filter_complex", (
                f"[0:v]{vf}[v];"
                f"[1:a]adelay=300|300,apad=whole_dur={vid_dur}[tts];"
                f"[tts]volume=1.0[a]"
            ),
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-shortest",
            str(out)
        ]

        print(f"  Composing {i+1}: \"{lines[0]}\"", flush=True)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  WARN: complex filter failed, trying simpler...", flush=True)
            # Simpler fallback: just scale + text + audio
            cmd2 = [
                "ffmpeg", "-y",
                "-i", str(clip),
                "-i", str(tts),
                "-filter_complex", (
                    f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
                    f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,"
                    f"drawtext=text='{line1}':"
                    f"fontsize=50:fontcolor=white:borderw=4:bordercolor=black:"
                    f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
                    f"x=(w-text_w)/2:y=h*3/4,"
                    f"drawtext=text='204.ai':"
                    f"fontsize=28:fontcolor=white@0.5:"
                    f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
                    f"x=w-text_w-20:y=25[v];"
                    f"[1:a]adelay=300|300,apad=whole_dur={vid_dur}[a]"
                ),
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                "-shortest",
                str(out)
            ]
            subprocess.run(cmd2, check=True, capture_output=True)
        composed.append(out)

    # 6. Stitch all composed clips
    print("\n=== PHASE 5: Stitching final 30s video ===\n", flush=True)
    concat_file = GENERATED / "_lisbon_concat.txt"
    with open(concat_file, "w") as f:
        for c in composed:
            f.write(f"file '{c.name}'\n")

    final = GENERATED / "204ai_lisbon_party.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(final)
    ]
    subprocess.run(cmd, check=True)

    elapsed = time.time() - t0
    sz = final.stat().st_size / 1024 / 1024
    print(f"\n=== DONE! ===", flush=True)
    print(f"Final: {final} ({sz:.1f} MB)", flush=True)
    print(f"Time: {elapsed/60:.1f} minutes", flush=True)


if __name__ == "__main__":
    main()
