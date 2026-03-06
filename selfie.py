"""
Ari Selfie Generator
Renders Ari's ASCII face, sends it to ComfyUI, and saves the portrait.

Usage:
  python selfie.py                          # default hamster portrait
  python selfie.py "a pirate hamster"       # custom prompt
  python selfie.py --seed 12345             # reproducible generation
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
GENERATED = ROOT / "generated"
GENERATED.mkdir(exist_ok=True)

COMFYUI = os.environ.get("COMFYUI_URL", "http://localhost:8189")

HAMSTER_ASCII = r"""
   (\(\ /)/)
    ( ^.^ )
  * ( " ^ " ) *
     ( w )
      (   )
"""

DEFAULT_PROMPT = (
    "A cute adorable hamster character portrait, studio Ghibli style. "
    "Round fluffy golden-brown hamster with big sparkly eyes and rosy cheeks, "
    "tiny paws held up near its face. Wearing a tiny glowing sci-fi headset. "
    "Soft warm lighting, dark cozy background with faint glowing terminal text. "
    "The hamster looks happy and friendly. Ultra detailed, cinematic, "
    "digital painting, warm color palette, soft bokeh background."
)


def render_ascii_to_png(out_path: Path) -> None:
    """Render Ari's ASCII face to a 1024x1024 PNG."""
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
    """Upload an image to ComfyUI, return the server-side filename."""
    import mimetypes

    boundary = "----AriUploadBoundary"
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


def build_workflow(prompt: str, image_name: str, seed: int) -> dict:
    """Build the ComfyUI Qwen image-edit workflow."""
    return {
        "3": {
            "inputs": {
                "seed": seed,
                "steps": 4, "cfg": 1,
                "sampler_name": "euler", "scheduler": "simple",
                "denoise": 1,
                "model": ["75", 0],
                "positive": ["111", 0], "negative": ["110", 0],
                "latent_image": ["88", 0],
            },
            "class_type": "KSampler",
        },
        "8": {
            "inputs": {"samples": ["3", 0], "vae": ["39", 0]},
            "class_type": "VAEDecode",
        },
        "37": {
            "inputs": {
                "unet_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
                "weight_dtype": "default",
            },
            "class_type": "UNETLoader",
        },
        "38": {
            "inputs": {
                "clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                "type": "qwen_image", "device": "default",
            },
            "class_type": "CLIPLoader",
        },
        "39": {
            "inputs": {"vae_name": "qwen_image_vae.safetensors"},
            "class_type": "VAELoader",
        },
        "60": {
            "inputs": {
                "filename_prefix": "ari_selfie/img",
                "images": ["8", 0],
            },
            "class_type": "SaveImage",
        },
        "66": {
            "inputs": {"shift": 3, "model": ["89", 0]},
            "class_type": "ModelSamplingAuraFlow",
        },
        "75": {
            "inputs": {"strength": 1, "model": ["66", 0]},
            "class_type": "CFGNorm",
        },
        "78": {
            "inputs": {"image": image_name},
            "class_type": "LoadImage",
        },
        "88": {
            "inputs": {"pixels": ["93", 0], "vae": ["39", 0]},
            "class_type": "VAEEncode",
        },
        "89": {
            "inputs": {
                "lora_name": "Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors",
                "strength_model": 1, "model": ["37", 0],
            },
            "class_type": "LoraLoaderModelOnly",
        },
        "93": {
            "inputs": {
                "upscale_method": "lanczos", "megapixels": 1,
                "resolution_steps": 1, "image": ["78", 0],
            },
            "class_type": "ImageScaleToTotalPixels",
        },
        "110": {
            "inputs": {
                "prompt": "",
                "clip": ["38", 0], "vae": ["39", 0], "image1": ["93", 0],
            },
            "class_type": "TextEncodeQwenImageEditPlus",
        },
        "111": {
            "inputs": {
                "prompt": prompt,
                "clip": ["38", 0], "vae": ["39", 0], "image1": ["93", 0],
            },
            "class_type": "TextEncodeQwenImageEditPlus",
        },
    }


def queue_and_wait(workflow: dict, timeout: int = 240) -> str:
    """Queue the workflow and wait for the output image filename."""
    payload = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        f"{COMFYUI}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    prompt_id = json.loads(resp.read())["prompt_id"]
    print(f"Queued prompt_id={prompt_id}", flush=True)

    for _ in range(timeout // 2):
        time.sleep(2)
        try:
            h = urllib.request.urlopen(f"{COMFYUI}/history/{prompt_id}")
            history = json.loads(h.read())
            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(f"Generation failed: {json.dumps(status)}")
                if status.get("completed"):
                    for node_out in entry.get("outputs", {}).values():
                        if "images" in node_out:
                            img = node_out["images"][0]
                            return img["filename"], img.get("subfolder", ""), img.get("type", "output")
                    raise RuntimeError("No image output found")
        except urllib.error.URLError:
            pass
        print(".", end="", flush=True)

    raise TimeoutError("Timed out waiting for generation")


def download_image(filename: str, subfolder: str, img_type: str, dest: Path) -> None:
    """Download a generated image from ComfyUI."""
    url = f"{COMFYUI}/view?filename={filename}&subfolder={subfolder}&type={img_type}"
    urllib.request.urlretrieve(url, str(dest))


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate an Ari selfie via ComfyUI")
    parser.add_argument("prompt", nargs="?", default=None, help="Custom prompt")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed")
    parser.add_argument("--output", "-o", default="ari_selfie.png", help="Output filename in generated/")
    args = parser.parse_args()

    prompt = args.prompt or DEFAULT_PROMPT
    seed = args.seed or int(time.time() * 1000) % (2**32)
    out_name = args.output

    # 1. Render ASCII face
    face_path = GENERATED / "_ari_face_input.png"
    print("Rendering ASCII face...", flush=True)
    render_ascii_to_png(face_path)

    # 2. Upload to ComfyUI
    print("Uploading to ComfyUI...", flush=True)
    server_name = upload_image(face_path)

    # 3. Build & queue workflow
    print(f"Generating (seed={seed})...", flush=True)
    workflow = build_workflow(prompt, server_name, seed)
    filename, subfolder, img_type = queue_and_wait(workflow)

    # 4. Download result
    dest = GENERATED / out_name
    print(f"\nDownloading to {dest}...", flush=True)
    download_image(filename, subfolder, img_type, dest)
    print(f"Saved: {dest}")

    # Output the markdown for the chat UI
    print(f"\n![Ari selfie](/api/image?file={out_name})")


if __name__ == "__main__":
    main()
