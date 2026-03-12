"""
204.ai Photobooth Advertisement — "Ari Gets Into Berghain"
30 seconds, 6 scenes x 5s (121 frames each), continuous reel.

Concept: Ari the hamster tries to get into a Berghain-style club.
The 204.ai photobooth inside makes everyone a star.
Consistent character, venue, style. Narration overlays. Loopable.
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
    "rich purple and cyan neon accents, golden highlights, cinematic composition, "
    "highly detailed, cohesive color palette, dark moody atmosphere with warm accents"
)

VENUE = (
    "a massive brutalist concrete nightclub inspired by Berghain Berlin, "
    "industrial concrete walls, dramatic purple and cyan neon strip lighting, "
    "dark smoky atmosphere, golden spotlights cutting through haze"
)

# ── 7 keyframes (shared boundaries for 6 continuous clips) ──────────────
KEYFRAMES = [
    # KF1: The queue outside
    f"{CHAR} standing at the back of a long queue of stylish animal characters outside "
    f"{VENUE}, a massive concrete facade with a single steel door and a neon purple "
    f"204.ai sign above it, nighttime, Ari looking tiny and nervous but determined, {STYLE}",

    # KF2: Face to face with the bouncer
    f"{CHAR} at the front of the queue, looking up with big pleading sparkly eyes at a "
    f"massive intimidating bear bouncer wearing all black and sunglasses, the steel door "
    f"of the club behind them, other animals watching nervously, {VENUE}, {STYLE}",

    # KF3: Inside — discovering the photobooth
    f"{CHAR} walking into the dark club interior, eyes wide with wonder, discovering a "
    f"magnificent glowing 204.ai photobooth kiosk in the center, the kiosk radiates purple "
    f"and golden light, other animal guests dancing nearby, {VENUE}, {STYLE}",

    # KF4: The flash — posing at the booth
    f"{CHAR} striking a confident pose in front of the photobooth camera, a brilliant golden "
    f"camera flash illuminating the scene with sparkles and light rays, the crowd behind "
    f"watching and cheering, the 204.ai logo on the kiosk glowing bright, {VENUE}, {STYLE}",

    # KF5: AI transformation on the big screen
    f"A large glowing screen showing {CHAR} being magnificently transformed by AI, "
    f"the portrait morphing into a golden royal knight hamster with a jeweled crown and "
    f"shining armor, swirling neural network sparkles and golden particles, the crowd "
    f"gasping in amazement below the screen, {VENUE}, {STYLE}",

    # KF6: Holding the print — hero moment
    f"{CHAR} proudly holding up a beautiful printed portrait showing the golden knight "
    f"version, beaming with pure joy, the big bear bouncer in the background giving a "
    f"thumbs up and smiling, other animals taking photos, confetti and sparkles falling, "
    f"the 204.ai neon sign glowing behind, {VENUE}, {STYLE}",

    # KF7: Outside again — Ari is now on the poster (loops to KF1)
    f"Wide shot of the club exterior at night, {CHAR} featured on a large glowing poster "
    f"above the entrance reading TONIGHT'S STAR, the queue of animals below looking up "
    f"in awe, the neon 204.ai sign bright above, same brutalist concrete facade, "
    f"a sense of magic and wonder, {STYLE}",
]

# ── 6 morph prompts (transition descriptions) ───────────────────────────
MORPH_PROMPTS = [
    # Clip 1: Queue -> Bouncer (KF1 -> KF2)
    "A tiny cute hamster nervously shuffles forward through a long queue of stylish animals "
    "outside a massive concrete nightclub. The camera slowly pushes forward. The hamster "
    "reaches the front and looks up at a massive bear bouncer. Dark moody neon lighting, "
    "steady smooth camera, cinematic motion.",

    # Clip 2: Bouncer -> Inside (KF2 -> KF3)
    "The massive bear bouncer steps aside and the tiny hamster walks through the steel door "
    "into the dark club interior. Inside, dramatic purple spotlights reveal a glowing "
    "photobooth kiosk. The hamster's eyes go wide with wonder. Steady camera push forward, "
    "smooth lighting transition from dark exterior to neon interior.",

    # Clip 3: Inside -> Flash (KF3 -> KF4)
    "The cute hamster approaches the glowing photobooth and strikes a confident pose. "
    "A bright golden camera flash fires, filling the frame with sparkles and light rays. "
    "The crowd behind cheers. Steady camera, smooth flash transition, warm golden burst.",

    # Clip 4: Flash -> Transformation (KF4 -> KF5)
    "After the flash, a large screen lights up showing the hamster's portrait being magically "
    "transformed by AI. Neural network patterns and golden sparkles swirl as the hamster "
    "morphs into a magnificent golden knight with a jeweled crown. The crowd gasps. "
    "Smooth magical transformation, steady camera, purple and gold lighting.",

    # Clip 5: Transformation -> Print (KF5 -> KF6)
    "The transformed knight portrait is complete on screen. A printer produces a beautiful "
    "print and the hamster grabs it proudly, holding it up high. The bear bouncer appears "
    "behind giving a thumbs up. Confetti and sparkles fall. Celebratory energy, steady camera.",

    # Clip 6: Print -> Poster outside (KF6 -> KF7)
    "The scene pulls back and transitions outside the club. The hamster's portrait now appears "
    "on a large glowing poster above the entrance. The queue below looks up in awe at the "
    "poster. The neon 204.ai sign glows bright. Smooth cinematic pullback, dark moody lighting.",
]

# ── Narration captions per clip ──────────────────────────────────────────
CAPTIONS = [
    "The line is long.\nThe bouncer is mean.",
    "One look at these eyes?\nEven Berghain says yes.",
    "Inside... something\nmagical waits.",
    "Three. Two. One.\nGorgeous!",
    "AI magic.\nYou're a masterpiece.",
    "204.ai\nYour night. Unforgettable.",
]


# ── Helpers (image gen + morph gen) ──────────────────────────────────────

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
    boundary = "----AdUploadBoundary"
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
    return json.loads(resp.read())["name"]


def build_selfie_workflow(prompt, image_name, seed):
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
        "37": {"inputs": {"unet_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors", "weight_dtype": "default"}, "class_type": "UNETLoader"},
        "38": {"inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"}, "class_type": "CLIPLoader"},
        "39": {"inputs": {"vae_name": "qwen_image_vae.safetensors"}, "class_type": "VAELoader"},
        "60": {"inputs": {"filename_prefix": "ari_ad/img", "images": ["8", 0]}, "class_type": "SaveImage"},
        "66": {"inputs": {"shift": 3, "model": ["89", 0]}, "class_type": "ModelSamplingAuraFlow"},
        "75": {"inputs": {"strength": 1, "model": ["66", 0]}, "class_type": "CFGNorm"},
        "78": {"inputs": {"image": image_name}, "class_type": "LoadImage"},
        "88": {"inputs": {"pixels": ["93", 0], "vae": ["39", 0]}, "class_type": "VAEEncode"},
        "89": {"inputs": {"lora_name": "Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors", "strength_model": 1, "model": ["37", 0]}, "class_type": "LoraLoaderModelOnly"},
        "93": {"inputs": {"upscale_method": "lanczos", "megapixels": 1, "resolution_steps": 1, "image": ["78", 0]}, "class_type": "ImageScaleToTotalPixels"},
        "110": {"inputs": {"prompt": "", "clip": ["38", 0], "vae": ["39", 0], "image1": ["93", 0]}, "class_type": "TextEncodeQwenImageEditPlus"},
        "111": {"inputs": {"prompt": prompt, "clip": ["38", 0], "vae": ["39", 0], "image1": ["93", 0]}, "class_type": "TextEncodeQwenImageEditPlus"},
    }


def queue_and_wait_selfie(workflow, timeout=240):
    payload = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(f"{COMFYUI}/prompt", data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req)
    pid = json.loads(resp.read())["prompt_id"]
    print(f"  Queued selfie {pid}", flush=True)
    for _ in range(timeout // 2):
        time.sleep(2)
        try:
            h = urllib.request.urlopen(f"{COMFYUI}/history/{pid}")
            hist = json.loads(h.read())
            if pid in hist:
                entry = hist[pid]
                st = entry.get("status", {})
                if st.get("status_str") == "error":
                    raise RuntimeError(f"Failed: {json.dumps(st)}")
                if st.get("completed"):
                    for out in entry.get("outputs", {}).values():
                        if "images" in out:
                            img = out["images"][0]
                            return img["filename"], img.get("subfolder", ""), img.get("type", "output")
                    raise RuntimeError("No image output")
        except urllib.error.URLError:
            pass
        print(".", end="", flush=True)
    raise TimeoutError("Selfie timed out")


def download(filename, subfolder, ftype, dest):
    urllib.request.urlretrieve(f"{COMFYUI}/view?filename={filename}&subfolder={subfolder}&type={ftype}", str(dest))


def gen_selfie(prompt, name, face_name):
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


def build_morph_workflow(prompt, start_img, end_img, seed, frames=121, w=720, h=1280, fps=24.0):
    sys.path.insert(0, str(ROOT / "skills" / "comfy"))
    import morph
    return morph.build_workflow(prompt, start_img, end_img, seed, frames, w, h, fps)


def queue_and_wait_morph(workflow, timeout=600):
    payload = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(f"{COMFYUI}/prompt", data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req)
    pid = json.loads(resp.read())["prompt_id"]
    print(f"  Queued morph {pid}", flush=True)
    for _ in range(timeout // 3):
        time.sleep(3)
        try:
            h = urllib.request.urlopen(f"{COMFYUI}/history/{pid}")
            hist = json.loads(h.read())
            if pid in hist:
                entry = hist[pid]
                st = entry.get("status", {})
                if st.get("status_str") == "error":
                    raise RuntimeError(f"Failed: {json.dumps(st.get('messages', []))}")
                if st.get("completed"):
                    for out in entry.get("outputs", {}).values():
                        if "gifs" in out:
                            v = out["gifs"][0]
                            return v["filename"], v.get("subfolder", ""), v.get("type", "output")
                    for out in entry.get("outputs", {}).values():
                        if "images" in out:
                            v = out["images"][0]
                            return v["filename"], v.get("subfolder", ""), v.get("type", "output")
                    raise RuntimeError("No morph output")
        except urllib.error.URLError:
            pass
        print(".", end="", flush=True)
    raise TimeoutError("Morph timed out")


def gen_morph(start_path, end_path, prompt, name):
    dest = GENERATED / name
    if dest.exists():
        print(f"  [SKIP] {name}", flush=True)
        return dest
    s_name = upload_image(start_path)
    e_name = upload_image(end_path)
    seed = int(time.time() * 1000) % (2**53)
    wf = build_morph_workflow(prompt, s_name, e_name, seed)
    fn, sf, ft = queue_and_wait_morph(wf)
    print(flush=True)
    download(fn, sf, ft, dest)
    print(f"  Saved: {name}", flush=True)
    return dest


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    TARGET_W, TARGET_H = 720, 1280

    # 1. Face input
    face_path = GENERATED / "_ad_face.png"
    print("=== Rendering ASCII face ===", flush=True)
    render_ascii_to_png(face_path)
    face_name = upload_image(face_path)

    # 2. Generate 7 keyframes
    print("\n=== PHASE 1: 7 keyframe images ===\n", flush=True)
    kf_imgs = []
    for i, kf_prompt in enumerate(KEYFRAMES, 1):
        print(f"--- KF {i}/7 ---", flush=True)
        img = gen_selfie(kf_prompt, f"ad_kf{i}.png", face_name)
        kf_imgs.append(img)
        print(f"    ({time.time()-t0:.0f}s)\n", flush=True)

    # 3. Generate 6 morph clips
    print("=== PHASE 2: 6 morph clips (121 frames each) ===\n", flush=True)
    raw_clips = []
    for i in range(6):
        print(f"--- Clip {i+1}/6: KF{i+1} -> KF{i+2} ---", flush=True)
        clip = gen_morph(kf_imgs[i], kf_imgs[i+1], MORPH_PROMPTS[i], f"ad_clip_{i+1}.mp4")
        raw_clips.append(clip)
        print(f"    ({time.time()-t0:.0f}s)\n", flush=True)

    # 4. Add text overlays + force exact resolution + 204.ai watermark
    print("=== PHASE 3: Text overlays + branding ===\n", flush=True)
    overlay_clips = []

    for i, (clip, caption) in enumerate(zip(raw_clips, CAPTIONS)):
        out = GENERATED / f"ad_final_{i+1}.mp4"
        if out.exists():
            print(f"  [SKIP] {out.name}", flush=True)
            overlay_clips.append(out)
            continue

        # Escape for ffmpeg drawtext
        safe = caption.replace("'", "'\\''").replace(":", "\\:")
        # Two-line caption: split on \n
        lines = caption.split("\n")
        line1 = lines[0].replace("'", "'\\''").replace(":", "\\:")
        line2 = lines[1].replace("'", "'\\''").replace(":", "\\:") if len(lines) > 1 else ""

        # Build filter: scale + pad + caption text + 204.ai watermark
        vf_parts = [
            f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease",
            f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=black",
        ]

        # Main caption line 1 (centered, lower third)
        vf_parts.append(
            f"drawtext=text='{line1}':"
            f"fontsize=48:fontcolor=white:borderw=3:bordercolor=black@0.8:"
            f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
            f"x=(w-text_w)/2:y=h*3/4-40:"
            f"enable='between(t\\,0.3\\,4.5)':"
            f"alpha='if(lt(t\\,0.8)\\,(t-0.3)*2\\,if(gt(t\\,4)\\,(4.5-t)*2\\,1))'"
        )

        # Caption line 2 if present
        if line2:
            vf_parts.append(
                f"drawtext=text='{line2}':"
                f"fontsize=48:fontcolor=white:borderw=3:bordercolor=black@0.8:"
                f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
                f"x=(w-text_w)/2:y=h*3/4+20:"
                f"enable='between(t\\,0.5\\,4.5)':"
                f"alpha='if(lt(t\\,1)\\,(t-0.5)*2\\,if(gt(t\\,4)\\,(4.5-t)*2\\,1))'"
            )

        # 204.ai watermark (always visible, top right)
        vf_parts.append(
            f"drawtext=text='204.ai':"
            f"fontsize=28:fontcolor=white@0.6:borderw=2:bordercolor=black@0.3:"
            f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
            f"x=w-text_w-20:y=25"
        )

        vf = ",".join(vf_parts)
        cmd = [
            "ffmpeg", "-y", "-i", str(clip),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
            "-an",
            str(out)
        ]
        print(f"  Overlay {i+1}: \"{caption.replace(chr(10), ' | ')}\"", flush=True)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  FFMPEG ERROR: {r.stderr[-500:]}", flush=True)
            # Fallback: simpler filter without fancy alpha
            cmd_simple = [
                "ffmpeg", "-y", "-i", str(clip),
                "-vf", (
                    f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
                    f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=black,"
                    f"drawtext=text='{line1}':"
                    f"fontsize=48:fontcolor=white:borderw=3:bordercolor=black:"
                    f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
                    f"x=(w-text_w)/2:y=h*3/4-40,"
                    f"drawtext=text='204.ai':"
                    f"fontsize=28:fontcolor=white@0.6:"
                    f"fontfile=C\\\\:/Windows/Fonts/arialbd.ttf:"
                    f"x=w-text_w-20:y=25"
                ),
                "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p", "-an",
                str(out)
            ]
            subprocess.run(cmd_simple, check=True, capture_output=True)
        overlay_clips.append(out)

    # 5. Stitch into final 30s video
    print("\n=== PHASE 4: Stitching final 30s ad ===\n", flush=True)
    concat_file = GENERATED / "_ad_concat.txt"
    with open(concat_file, "w") as f:
        for clip in overlay_clips:
            f.write(f"file '{clip.name}'\n")

    final = GENERATED / "204ai_berghain_ad.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(final)
    ]
    subprocess.run(cmd, check=True)

    elapsed = time.time() - t0
    print(f"\n=== DONE! ===", flush=True)
    print(f"Final: {final} ({final.stat().st_size/1024/1024:.1f} MB)", flush=True)
    print(f"Time: {elapsed/60:.1f} minutes", flush=True)


if __name__ == "__main__":
    main()
