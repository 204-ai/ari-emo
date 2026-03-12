"""
Ari 3D Model Generator
Takes an image and generates a 3D GLB model via ComfyUI + Hunyuan 3D v2.1.

Usage:
  python threedee.py image.png                    # generate 3D model from image
  python threedee.py image.png --seed 12345       # reproducible generation
  python threedee.py image.png -o my_model.glb    # custom output filename
"""

import json
import os
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


def upload_image(file_path: Path) -> str:
    """Upload an image to ComfyUI, return the server-side filename."""
    import mimetypes

    boundary = "----Ari3DUploadBoundary"
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


def build_workflow(image_name: str, seed: int) -> dict:
    """Build the ComfyUI Hunyuan 3D v2.1 workflow (API format)."""
    return {
        "1": {
            "inputs": {
                "ckpt_name": "hunyuan_3d_v2.1.safetensors",
            },
            "class_type": "ImageOnlyCheckpointLoader",
        },
        "2": {
            "inputs": {
                "image": image_name,
            },
            "class_type": "LoadImage",
        },
        "3": {
            "inputs": {
                "shift": 1,
                "model": ["1", 0],
            },
            "class_type": "ModelSamplingAuraFlow",
        },
        "4": {
            "inputs": {
                "resolution": 4096,
                "batch_size": 1,
            },
            "class_type": "EmptyLatentHunyuan3Dv2",
        },
        "13": {
            "inputs": {
                "crop": "center",
                "clip_vision": ["1", 1],
                "image": ["2", 0],
            },
            "class_type": "CLIPVisionEncode",
        },
        "6": {
            "inputs": {
                "clip_vision_output": ["13", 0],
            },
            "class_type": "Hunyuan3Dv2Conditioning",
        },
        "7": {
            "inputs": {
                "seed": seed,
                "steps": 30,
                "cfg": 5,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1,
                "model": ["3", 0],
                "positive": ["6", 0],
                "negative": ["6", 1],
                "latent_image": ["4", 0],
            },
            "class_type": "KSampler",
        },
        "8": {
            "inputs": {
                "num_chunks": 8000,
                "octree_resolution": 256,
                "samples": ["7", 0],
                "vae": ["1", 2],
            },
            "class_type": "VAEDecodeHunyuan3D",
        },
        "9": {
            "inputs": {
                "algorithm": "surface net",
                "threshold": 0.6,
                "voxel": ["8", 0],
            },
            "class_type": "VoxelToMesh",
        },
        "10": {
            "inputs": {
                "filename_prefix": "mesh/ari_3d",
                "mesh": ["9", 0],
            },
            "class_type": "SaveGLB",
        },
    }


def queue_and_wait(workflow: dict, timeout: int = 600) -> str:
    """Queue the workflow and wait for the output GLB filename."""
    payload = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        f"{COMFYUI}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read())
    prompt_id = result["prompt_id"]
    print(f"Queued prompt_id={prompt_id}", flush=True)

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
                    raise RuntimeError(f"Generation failed: {json.dumps(msgs, indent=2)}")
                if status.get("completed"):
                    for node_id, node_out in entry.get("outputs", {}).items():
                        for key in ["3d", "gltf", "glb", "files", "meshes"]:
                            if key in node_out and node_out[key]:
                                f = node_out[key][0]
                                return f["filename"], f.get("subfolder", ""), f.get("type", "output")
                    print(f"\nOutputs: {json.dumps(entry.get('outputs', {}), indent=2)}", flush=True)
                    raise RuntimeError("No GLB output found in history")
        except urllib.error.URLError:
            pass
        print(".", end="", flush=True)

    raise TimeoutError("Timed out waiting for 3D generation")


def download_file(filename: str, subfolder: str, file_type: str, dest: Path) -> None:
    """Download a generated file from ComfyUI."""
    url = f"{COMFYUI}/view?filename={filename}&subfolder={subfolder}&type={file_type}"
    urllib.request.urlretrieve(url, str(dest))


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate a 3D GLB model from an image via Hunyuan 3D v2.1")
    parser.add_argument("image", help="Input image path")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed")
    parser.add_argument("--output", "-o", default="ari_3d.glb", help="Output filename in generated/")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: {image_path} not found")
        sys.exit(1)

    seed = args.seed or int(time.time() * 1000) % (2**32)
    out_name = args.output

    # 1. Upload image to ComfyUI
    print(f"Uploading {image_path} to ComfyUI...", flush=True)
    server_name = upload_image(image_path)
    print(f"  -> {server_name}", flush=True)

    # 2. Build & queue workflow
    print(f"Generating 3D model (seed={seed}, 30 steps)...", flush=True)
    print("  This may take a few minutes...", flush=True)
    workflow = build_workflow(server_name, seed)
    filename, subfolder, file_type = queue_and_wait(workflow)

    # 3. Download result
    dest = GENERATED / out_name
    print(f"\nDownloading to {dest}...", flush=True)
    download_file(filename, subfolder, file_type, dest)
    print(f"Saved: {dest}")
    print(f"  File size: {dest.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
