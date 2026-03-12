"""
204.ai Photobooth Advertisement — "Ari in Residence" at RnA Studio, Lisbon
30 seconds, 6 scenes x 5s (121 frames each), continuous reel.
Uses LTX 2.3 native audio generation (no separate TTS).

Concept: Ari the hamster is an art+tech resident at RnA Studio, a creative
collective in Lisbon. The 204.ai photobooth is Ari's latest art installation.
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

# ── Consistent style tokens ─────────────────────────────────────────────
CHAR = (
    "a cute adorable round fluffy golden-brown hamster character with big sparkly eyes "
    "and rosy cheeks, wearing a tiny purple bowtie and a small glowing purple headset"
)

STYLE = (
    "Studio Ghibli anime style, 2D digital painting, soft warm lighting, "
    "rich purple and warm golden accents, contemporary art gallery aesthetic, "
    "cinematic composition, highly detailed, cohesive warm color palette"
)

VENUE = (
    "inside RnA Studio, a contemporary minimalist art and technology collective space "
    "in Lisbon, clean white walls with exposed concrete details, warm spotlights, "
    "creative installations and screens on the walls, plants and modern furniture, "
    "other creative animal characters collaborating"
)

# ── 7 keyframes ─────────────────────────────────────────────────────────
KEYFRAMES = [
    # KF1: Arriving at the studio
    f"{CHAR} standing at the entrance of RnA Studio in Lisbon, a contemporary creative "
    f"space with a minimalist facade, a subtle neon RnA sign by the door, carrying a tiny "
    f"toolbox and laptop, looking excited and determined, warm afternoon Lisbon light, {STYLE}",

    # KF2: Working on the installation
    f"{CHAR} inside a bright contemporary studio workspace, surrounded by wires, screens, "
    f"and tools, building a sleek photobooth kiosk with a glowing 204.ai logo, wearing tiny "
    f"safety goggles pushed up on forehead, soldering iron in paw, other creative animals "
    f"peeking curiously, {VENUE}, {STYLE}",

    # KF3: Opening night — guests arriving
    f"RnA Studio transformed for an exhibition opening night, warm golden lighting, "
    f"wine glasses and candles on tables, {CHAR} standing proudly next to the completed "
    f"glowing 204.ai photobooth installation, stylish animal guests arriving through "
    f"the door, the kiosk radiating purple and golden light, {VENUE}, {STYLE}",

    # KF4: Someone steps into the booth — the flash
    f"A tall elegant fox character posing in front of the 204.ai photobooth camera, "
    f"{CHAR} watching excitedly from beside the kiosk, a brilliant golden camera flash "
    f"illuminating the entire studio with sparkles and warm light rays, other guests "
    f"watching with anticipation, {VENUE}, {STYLE}",

    # KF5: AI transformation on screen — crowd gasps
    f"A large screen on the studio wall showing the fox character being magnificently "
    f"transformed by AI into a Renaissance painting subject with golden frame and rich "
    f"colors, {CHAR} pointing at the screen proudly, the crowd of animal guests gasping "
    f"with mouths open, golden sparkles floating in the air, {VENUE}, {STYLE}",

    # KF6: Celebration — prints and joy
    f"The studio full of happy animal guests holding printed AI portraits of themselves, "
    f"each transformed into a different art style, {CHAR} in the center being lifted up "
    f"by friends in celebration, confetti and sparkles everywhere, the 204.ai kiosk "
    f"glowing proudly in the background, a banner reading ART + AI, {VENUE}, {STYLE}",

    # KF7: The studio from outside at night — glowing with life (loops back)
    f"Wide shot of RnA Studio in Lisbon from outside at night, warm golden light spilling "
    f"through the windows, silhouettes of happy guests visible inside, the 204.ai photobooth "
    f"glow visible through the glass, a small poster by the door showing {CHAR} as artist "
    f"in residence, cobblestone Lisbon street, warm atmospheric lighting, {STYLE}",
]

# ── 6 morph prompts WITH speech/narration descriptions for LTX audio ────
# LTX 2.3 generates audio natively — speech prompts guide what it generates
MORPH_PROMPTS = [
    # Clip 1: Arrive -> Build
    "A cute hamster walks into a bright contemporary art studio carrying tools. "
    "The hamster looks around in wonder, then sets down the toolbox and starts working "
    "on building a glowing machine. A cute high-pitched voice narrates: "
    "'Art plus tech equals magic.' "
    "Gentle ambient electronic music plays softly. Tools clicking and whirring sounds. "
    "Warm golden lighting, smooth steady camera.",

    # Clip 2: Build -> Opening night
    "The studio transforms from a workshop into a beautiful exhibition space. "
    "Lights dim to warm golden, candles appear, guests start arriving. "
    "The photobooth kiosk glows to life. A cute voice says: "
    "'Opening night at RnA Studio!' "
    "Excited chatter and gentle ambient music. Smooth transition, steady camera.",

    # Clip 3: Opening -> Flash
    "A tall elegant fox character steps up to the photobooth and poses confidently. "
    "The cute hamster watches excitedly. A bright golden camera flash fires, "
    "illuminating the entire studio with sparkles. A cute voice says: "
    "'Say queijo!' "
    "Camera shutter click, crowd gasps, ambient party sounds. Steady camera.",

    # Clip 4: Flash -> Transformation
    "A large screen on the wall lights up showing the fox being transformed by AI. "
    "The portrait morphs into a magnificent Renaissance painting. Golden sparkles swirl. "
    "The hamster points at the screen proudly. A cute voice says: "
    "'Now that is art.' "
    "Magical transformation sounds, crowd oohs and aahs. Steady camera, warm lighting.",

    # Clip 5: Transformation -> Celebration
    "The crowd erupts in celebration. Guests hold up their own AI portrait prints. "
    "The hamster is lifted up by friends, confetti falls. A cute voice says: "
    "'This is what happens when art meets AI!' "
    "Applause, cheering, uplifting music. Celebratory energy, steady camera.",

    # Clip 6: Celebration -> Outside
    "The camera slowly pulls back through the studio window to the outside. "
    "The warm glow of the party is visible through the glass. The Lisbon street is quiet "
    "and beautiful. A cute voice says: "
    "'RnA Studio and 204.ai. Where creativity comes alive.' "
    "Gentle ambient music fading, night sounds of Lisbon. Smooth cinematic pullback.",
]

# ── Modified negative prompt — allow speech/narration ────────────────────
NEGATIVE_PROMPT = (
    "snowing, jump cut, shiny, realism, realistic, photographic, 3d rendered, 3d, "
    "blurry, low quality, still frame, frames, watermark, overlay, titles, "
    "has blurbox, has subtitles, unrealistic, out-of-focus, low-detail, "
    "3-arms, extra legs, walking backwards, defying physics."
)

AUDIO_NEGATIVE = "echo, distortion, static, harsh noise."

# ── Subtitle overlays (visible text on screen) ──────────────────────────
CAPTIONS = [
    "Art + tech = magic.",
    "Opening night\nat RnA Studio.",
    "Say queijo!",
    "Now THAT is art.",
    "Art meets AI!",
    "RnA Studio x 204.ai\nCreativity comes alive.",
]


# ── Helpers ──────────────────────────────────────────────────────────────

from PIL import Image, ImageDraw, ImageFont

HAMSTER_ASCII = r"""
   (\(\ /)/)
    ( ^.^ )
  * ( " ^ " ) *
     ( w )
      (   )
"""


def render_ascii_to_png(out_path):
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


def upload_image(fp):
    import mimetypes
    boundary = "----RnAAdUpload"
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
        "60": {"inputs": {"filename_prefix": "ari_rna/img", "images": ["8", 0]}, "class_type": "SaveImage"},
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


def build_morph_wf_with_speech(prompt, s_img, e_img, seed,
                                negative=NEGATIVE_PROMPT,
                                audio_neg=AUDIO_NEGATIVE,
                                frames=121, w=720, h=1280, fps=24.0):
    """Modified LTX 2.3 workflow with speech-friendly negative prompts."""
    # Import the base workflow builder
    sys.path.insert(0, str(ROOT / "skills" / "comfy"))
    import morph
    wf = morph.build_workflow(prompt, s_img, e_img, seed, frames, w, h, fps)

    # Override the negative prompt to ALLOW speech/narration
    wf["109"]["inputs"]["text"] = negative

    # Override audio negative to be less restrictive
    wf["352"]["inputs"]["text"] = audio_neg

    return wf


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
    wf = build_morph_wf_with_speech(prompt, s_n, e_n, seed)
    fn, sf, ft = queue_wait_morph(wf)
    print(flush=True)
    dl(fn, sf, ft, dest)
    print(f"  Saved: {name}", flush=True)
    return dest


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    W, H = 720, 1280

    # 1. Face
    face_path = GENERATED / "_rna_face.png"
    print("=== Rendering face ===", flush=True)
    render_ascii_to_png(face_path)
    face = upload_image(face_path)

    # 2. Keyframes
    print("\n=== PHASE 1: 7 keyframe images ===\n", flush=True)
    kfs = []
    for i, p in enumerate(KEYFRAMES, 1):
        print(f"--- KF {i}/7 ---", flush=True)
        kfs.append(gen_selfie(p, f"rna_kf{i}.png", face))
        print(f"    ({time.time()-t0:.0f}s)\n", flush=True)

    # 3. Morph clips (with LTX native audio — speech-friendly prompts)
    print("=== PHASE 2: 6 morph clips (LTX native audio) ===\n", flush=True)
    clips = []
    for i in range(6):
        print(f"--- Clip {i+1}/6: KF{i+1} -> KF{i+2} ---", flush=True)
        clips.append(gen_morph(kfs[i], kfs[i+1], MORPH_PROMPTS[i], f"rna_clip_{i+1}.mp4"))
        print(f"    ({time.time()-t0:.0f}s)\n", flush=True)

    # 4. Add subtitle overlays + 204.ai watermark, KEEP LTX audio
    print("=== PHASE 3: Subtitle overlays + branding (keeping LTX audio) ===\n", flush=True)
    overlay_clips = []

    for i, (clip, caption) in enumerate(zip(clips, CAPTIONS)):
        out = GENERATED / f"rna_overlay_{i+1}.mp4"
        if out.exists():
            print(f"  [SKIP] {out.name}", flush=True)
            overlay_clips.append(out)
            continue

        lines = caption.split("\n")
        line1 = lines[0].replace("'", "'\\''").replace(":", "\\:").replace(",", "\\,")
        line2 = lines[1].replace("'", "'\\''").replace(":", "\\:").replace(",", "\\,") if len(lines) > 1 else ""

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

        # RnA Studio credit (bottom left)
        vf_parts.append(
            f"drawtext=text='RnA Studio':"
            f"fontsize=22:fontcolor=white@0.4:borderw=1:bordercolor=black@0.2:"
            f"fontfile=C\\\\:/Windows/Fonts/arial.ttf:"
            f"x=20:y=h-50"
        )

        vf = ",".join(vf_parts)

        # KEEP LTX audio (-c:a copy or re-encode)
        cmd = [
            "ffmpeg", "-y", "-i", str(clip),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            str(out)
        ]
        print(f"  Overlay {i+1}: \"{lines[0]}\"", flush=True)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  WARN: overlay failed, trying simpler...", flush=True)
            cmd2 = [
                "ffmpeg", "-y", "-i", str(clip),
                "-vf", (
                    f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                    f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,"
                    f"drawtext=text='{line1}':"
                    f"fontsize=50:fontcolor=white:borderw=4:bordercolor=black:"
                    f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
                    f"x=(w-text_w)/2:y=h*3/4,"
                    f"drawtext=text='204.ai':"
                    f"fontsize=28:fontcolor=white@0.5:"
                    f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
                    f"x=w-text_w-20:y=25"
                ),
                "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                str(out)
            ]
            subprocess.run(cmd2, check=True, capture_output=True)
        overlay_clips.append(out)

    # 5. Stitch final video
    print("\n=== PHASE 4: Stitching final 30s ad ===\n", flush=True)
    concat_file = GENERATED / "_rna_concat.txt"
    with open(concat_file, "w") as f:
        for c in overlay_clips:
            f.write(f"file '{c.name}'\n")

    final = GENERATED / "204ai_rna_studio.mp4"
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
