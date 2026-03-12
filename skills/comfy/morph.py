"""
Morph Video Generator
Takes two images (start + end frame) and a prompt, generates a morphing video
via ComfyUI's LTX Video 2.3 pipeline.

Usage:
  python morph.py --start img1.png --end img2.png "A smooth transformation..."
  python morph.py --start img1.png --end img2.png --frames 121 --seed 42 "prompt"
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

DEFAULT_PROMPT = (
    "A smooth cinematic transformation between the two frames. "
    "The camera remains steady. Soft lighting, high detail, natural motion."
)


def upload_image(file_path: Path) -> str:
    """Upload an image to ComfyUI, return the server-side filename."""
    import mimetypes

    boundary = "----MorphUploadBoundary"
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


def build_workflow(prompt: str, start_image: str, end_image: str,
                   seed: int, frames: int = 121, width: int = 720,
                   height: int = 1280, fps: float = 24.0) -> dict:
    """Build the LTX Video 2.3 start-to-end frame workflow."""
    return {
        "101": {
            "inputs": {
                "positive": ["106", 0],
                "negative": ["106", 1],
                "latent": ["114", 0]
            },
            "class_type": "LTXVCropGuides",
        },
        "102": {
            "inputs": {
                "cfg": 1,
                "model": ["459", 0],
                "positive": ["101", 0],
                "negative": ["101", 1]
            },
            "class_type": "CFGGuider",
        },
        "103": {
            "inputs": {
                "upscale_method": "lanczos",
                "scale_by": ["335", 0],
                "image": ["110", 0]
            },
            "class_type": "ImageScaleBy",
        },
        "104": {
            "inputs": {"image": ["103", 0]},
            "class_type": "GetImageSize",
        },
        "105": {
            "inputs": {
                "frames_number": ["111", 0],
                "frame_rate": ["163", 0],
                "batch_size": 1,
                "audio_vae": ["121", 0]
            },
            "class_type": "LTXVEmptyLatentAudio",
        },
        "106": {
            "inputs": {
                "frame_rate": ["126", 0],
                "positive": ["119", 0],
                "negative": ["109", 0]
            },
            "class_type": "LTXVConditioning",
        },
        "107": {
            "inputs": {
                "width": ["104", 0],
                "height": ["104", 1],
                "length": ["111", 0],
                "batch_size": 1
            },
            "class_type": "EmptyLTXVLatentVideo",
        },
        "108": {
            "inputs": {
                "video_latent": ["107", 0],
                "audio_latent": ["344", 0]
            },
            "class_type": "LTXVConcatAVLatent",
        },
        "109": {
            "inputs": {
                "text": "snowing, jump cut, talking, lips moving, mouth movement, dialogue, shiny, realism, realistic, photographic, 3d rendered, 3d, blurry, low quality, still frame, frames, watermark, overlay, titles, has blurbox, has subtitles, has Americanisms, unrealistic, out-of-focus, low-detail, 3-arms, extra legs, walking backwards, defying physics.",
                "clip": ["136", 0]
            },
            "class_type": "CLIPTextEncode",
        },
        "110": {
            "inputs": {
                "width": ["199", 0],
                "height": ["200", 0],
                "batch_size": 1,
                "color": 0
            },
            "class_type": "EmptyImage",
        },
        "111": {
            "inputs": {"value": frames},
            "class_type": "PrimitiveInt",
        },
        "112": {
            "inputs": {
                "noise": ["113", 0],
                "guider": ["138", 0],
                "sampler": ["131", 0],
                "sigmas": ["244", 0],
                "latent_image": ["257", 0]
            },
            "class_type": "SamplerCustomAdvanced",
        },
        "113": {
            "inputs": {"noise_seed": ["479", 3]},
            "class_type": "RandomNoise",
        },
        "114": {
            "inputs": {"av_latent": ["112", 0]},
            "class_type": "LTXVSeparateAVLatent",
        },
        "115": {
            "inputs": {
                "video_latent": ["272", 0],
                "audio_latent": ["114", 1]
            },
            "class_type": "LTXVConcatAVLatent",
        },
        "116": {
            "inputs": {
                "samples": ["101", 2],
                "upscale_model": ["328", 0],
                "vae": ["134", 2]
            },
            "class_type": "LTXVLatentUpsampler",
        },
        "117": {
            "inputs": {
                "noise": ["135", 0],
                "guider": ["102", 0],
                "sampler": ["132", 0],
                "sigmas": ["139", 0],
                "latent_image": ["115", 0]
            },
            "class_type": "SamplerCustomAdvanced",
        },
        "119": {
            "inputs": {
                "text": prompt,
                "clip": ["136", 0]
            },
            "class_type": "CLIPTextEncode",
        },
        "121": {
            "inputs": {"ckpt_name": "ltx-2.3-22b-distilled.safetensors"},
            "class_type": "LTXVAudioVAELoader",
        },
        "122": {
            "inputs": {"av_latent": ["117", 1]},
            "class_type": "LTXVSeparateAVLatent",
        },
        "124": {
            "inputs": {
                "tile_size": 512,
                "overlap": 64,
                "temporal_size": 4096,
                "temporal_overlap": 8,
                "samples": ["320", 0],
                "vae": ["134", 2]
            },
            "class_type": "VAEDecodeTiled",
        },
        "125": {
            "inputs": {
                "samples": ["326", 0],
                "audio_vae": ["121", 0]
            },
            "class_type": "LTXVAudioVAEDecode",
        },
        "126": {
            "inputs": {"value": fps},
            "class_type": "PrimitiveFloat",
        },
        "131": {
            "inputs": {"sampler_name": "euler_ancestral"},
            "class_type": "KSamplerSelect",
        },
        "132": {
            "inputs": {"sampler_name": "euler_ancestral"},
            "class_type": "KSamplerSelect",
        },
        "134": {
            "inputs": {"ckpt_name": "ltx-2.3-22b-distilled.safetensors"},
            "class_type": "CheckpointLoaderSimple",
        },
        "135": {
            "inputs": {"noise_seed": ["366", 0]},
            "class_type": "RandomNoise",
        },
        "136": {
            "inputs": {
                "text_encoder": "gemma_3_12B_it_fp4_mixed.safetensors",
                "ckpt_name": "ltx-2.3-22b-distilled.safetensors",
                "device": "default"
            },
            "class_type": "LTXAVTextEncoderLoader",
        },
        "138": {
            "inputs": {
                "cfg": ["224", 0],
                "model": ["468", 0],
                "positive": ["106", 0],
                "negative": ["106", 1]
            },
            "class_type": "CFGGuider",
        },
        "139": {
            "inputs": {"sigmas": "0.909375, 0.725, 0.421875, 0.0"},
            "class_type": "ManualSigmas",
        },
        "163": {
            "inputs": {"a": ["126", 0]},
            "class_type": "CM_FloatToInt",
        },
        "180": {
            "inputs": {
                "frame_rate": ["300", 0],
                "loop_count": 0,
                "filename_prefix": "ari_morph/video",
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 19,
                "save_metadata": True,
                "trim_to_audio": False,
                "pingpong": False,
                "save_output": True,
                "images": ["124", 0],
                "audio": ["125", 0]
            },
            "class_type": "VHS_VideoCombine",
        },
        "187": {
            "inputs": {"image": start_image},
            "class_type": "LoadImage",
        },
        "191": {
            "inputs": {
                "width": ["199", 0],
                "height": ["200", 0],
                "upscale_method": "lanczos",
                "keep_proportion": "resize",
                "pad_color": "32,32,32",
                "crop_position": "center",
                "divisible_by": 2,
                "device": "cpu",
                "image": ["187", 0]
            },
            "class_type": "ImageResizeKJv2",
        },
        "199": {
            "inputs": {"value": width},
            "class_type": "INTConstant",
        },
        "200": {
            "inputs": {"value": height},
            "class_type": "INTConstant",
        },
        "209": {
            "inputs": {
                "longer_edge": 1536,
                "images": ["191", 0]
            },
            "class_type": "ResizeImagesByLongerEdge",
        },
        "210": {
            "inputs": {
                "img_compression": 33,
                "image": ["209", 0]
            },
            "class_type": "LTXVPreprocess",
        },
        "211": {
            "inputs": {
                "strength": 1,
                "bypass": False,
                "vae": ["134", 2],
                "image": ["210", 0],
                "latent": ["107", 0]
            },
            "class_type": "LTXVImgToVideoInplace",
        },
        "212": {
            "inputs": {
                "video_latent": ["211", 0],
                "audio_latent": ["344", 0]
            },
            "class_type": "LTXVConcatAVLatent",
        },
        "218": {
            "inputs": {"value": 8},
            "class_type": "INTConstant",
        },
        "224": {
            "inputs": {"value": 1.0},
            "class_type": "FloatConstant",
        },
        "243": {
            "inputs": {
                "steps": ["218", 0],
                "max_shift": 2.05,
                "base_shift": 0.95,
                "stretch": True,
                "terminal": 0.1,
                "latent": ["257", 0]
            },
            "class_type": "LTXVScheduler",
        },
        "244": {
            "inputs": {"any_02": ["243", 0]},
            "class_type": "Any Switch (rgthree)",
        },
        "257": {
            "inputs": {
                "any_01": ["427", 0],
                "any_02": ["212", 0],
                "any_03": ["108", 0]
            },
            "class_type": "Any Switch (rgthree)",
        },
        "265": {
            "inputs": {
                "strength": 1,
                "bypass": False,
                "vae": ["134", 2],
                "image": ["210", 0],
                "latent": ["116", 0]
            },
            "class_type": "LTXVImgToVideoInplace",
        },
        "272": {
            "inputs": {
                "any_01": ["433", 0],
                "any_02": ["265", 0],
                "any_03": ["116", 0]
            },
            "class_type": "Any Switch (rgthree)",
        },
        "287": {
            "inputs": {
                "PowerLoraLoaderHeaderWidget": {"type": "PowerLoraLoaderHeaderWidget"},
                "lora_1": {
                    "on": False,
                    "lora": "ltx-2-19b-lora-camera-control-dolly-left.safetensors",
                    "strength": 1
                },
                "lora_2": {
                    "on": False,
                    "lora": "LTX/ltx-2-19b-ic-lora-detailer.safetensors",
                    "strength": 1
                },
                "\u27a5 Add Lora": "",
                "model": ["134", 0]
            },
            "class_type": "Power Lora Loader (rgthree)",
        },
        "300": {
            "inputs": {
                "op": "Mul",
                "a": ["126", 0],
                "b": ["304", 0]
            },
            "class_type": "CM_FloatBinaryOperation",
        },
        "301": {
            "inputs": {"value": 1.0},
            "class_type": "FloatConstant",
        },
        "304": {
            "inputs": {"any_02": ["301", 0]},
            "class_type": "Any Switch (rgthree)",
        },
        "320": {
            "inputs": {
                "any_02": ["122", 0],
                "any_03": ["101", 2]
            },
            "class_type": "Any Switch (rgthree)",
        },
        "326": {
            "inputs": {
                "any_01": ["122", 1],
                "any_02": ["114", 1]
            },
            "class_type": "Any Switch (rgthree)",
        },
        "328": {
            "inputs": {"model_name": "ltx-2.3-spatial-upscaler-x2-1.0.safetensors"},
            "class_type": "LatentUpscaleModelLoader",
        },
        "335": {
            "inputs": {"value": 0.5},
            "class_type": "FloatConstant",
        },
        "344": {
            "inputs": {"any_02": ["105", 0]},
            "class_type": "Any Switch (rgthree)",
        },
        "352": {
            "inputs": {
                "text": "American accent, background music, echo, distortion.",
                "clip": ["136", 0]
            },
            "class_type": "CLIPTextEncode",
        },
        "358": {
            "inputs": {"any_02": ["287", 0]},
            "class_type": "Any Switch (rgthree)",
        },
        "366": {
            "inputs": {"seed": seed},
            "class_type": "Seed (rgthree)",
        },
        "406": {
            "inputs": {
                "first_strength": 1,
                "last_strength": 1,
                "vae": ["134", 2],
                "latent": ["107", 0],
                "first_image": ["421", 0],
                "last_image": ["436", 0]
            },
            "class_type": "LTXVFirstLastFrameControl_TTP",
        },
        "411": {
            "inputs": {"image": end_image},
            "class_type": "LoadImage",
        },
        "417": {
            "inputs": {
                "width": ["199", 0],
                "height": ["200", 0],
                "upscale_method": "lanczos",
                "keep_proportion": "resize",
                "pad_color": "32,32,32",
                "crop_position": "center",
                "divisible_by": 2,
                "device": "cpu",
                "image": ["411", 0]
            },
            "class_type": "ImageResizeKJv2",
        },
        "421": {
            "inputs": {
                "img_compression": 33,
                "image": ["424", 0]
            },
            "class_type": "LTXVPreprocess",
        },
        "424": {
            "inputs": {
                "longer_edge": 1536,
                "images": ["191", 0]
            },
            "class_type": "ResizeImagesByLongerEdge",
        },
        "427": {
            "inputs": {
                "video_latent": ["406", 0],
                "audio_latent": ["344", 0]
            },
            "class_type": "LTXVConcatAVLatent",
        },
        "433": {
            "inputs": {
                "first_strength": 1,
                "last_strength": 1,
                "vae": ["134", 2],
                "latent": ["116", 0],
                "first_image": ["421", 0],
                "last_image": ["436", 0]
            },
            "class_type": "LTXVFirstLastFrameControl_TTP",
        },
        "435": {
            "inputs": {
                "longer_edge": 1536,
                "images": ["417", 0]
            },
            "class_type": "ResizeImagesByLongerEdge",
        },
        "436": {
            "inputs": {
                "img_compression": 33,
                "image": ["435", 0]
            },
            "class_type": "LTXVPreprocess",
        },
        "453": {
            "inputs": {
                "lora_name": "ltx-2.3-22b-distilled-lora-384.safetensors",
                "strength_model": 0.4,
                "model": ["358", 0]
            },
            "class_type": "LoraLoaderModelOnly",
        },
        "459": {
            "inputs": {
                "switch": ["461", 0],
                "on_false": ["358", 0],
                "on_true": ["453", 0]
            },
            "class_type": "ComfySwitchNode",
        },
        "461": {
            "inputs": {"value": False},
            "class_type": "PrimitiveBoolean",
        },
        "466": {
            "inputs": {"value": False},
            "class_type": "PrimitiveBoolean",
        },
        "468": {
            "inputs": {
                "switch": ["466", 0],
                "on_false": ["358", 0],
                "on_true": ["453", 0]
            },
            "class_type": "ComfySwitchNode",
        },
        "473": {
            "inputs": {
                "any_01": ["122", 0],
                "any_02": ["101", 2]
            },
            "class_type": "Any Switch (rgthree)",
        },
        "479": {
            "inputs": {"seed": seed},
            "class_type": "Seed",
        },
    }


def queue_and_wait(workflow: dict, timeout: int = 600) -> tuple:
    """Queue the workflow and wait for the output video."""
    payload = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        f"{COMFYUI}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    prompt_id = json.loads(resp.read())["prompt_id"]
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
                    raise RuntimeError(f"Generation failed: {json.dumps(msgs)}")
                if status.get("completed"):
                    outputs = entry.get("outputs", {})
                    # Look for video output (VHS_VideoCombine uses 'gifs' key)
                    for node_id, node_out in outputs.items():
                        if "gifs" in node_out:
                            vid = node_out["gifs"][0]
                            return (
                                vid["filename"],
                                vid.get("subfolder", ""),
                                vid.get("type", "output"),
                                "video"
                            )
                        if "images" in node_out:
                            img = node_out["images"][0]
                            return (
                                img["filename"],
                                img.get("subfolder", ""),
                                img.get("type", "output"),
                                "image"
                            )
                    raise RuntimeError("No output found in history")
        except urllib.error.URLError:
            pass
        print(".", end="", flush=True)

    raise TimeoutError("Timed out waiting for video generation")


def download_output(filename: str, subfolder: str, out_type: str, dest: Path) -> None:
    """Download a generated file from ComfyUI."""
    url = f"{COMFYUI}/view?filename={filename}&subfolder={subfolder}&type={out_type}"
    urllib.request.urlretrieve(url, str(dest))


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate a morph video via ComfyUI LTX Video 2.3")
    parser.add_argument("prompt", nargs="?", default=None, help="Text prompt describing the transformation")
    parser.add_argument("--start", "-s", required=True, help="Start frame image path")
    parser.add_argument("--end", "-e", required=True, help="End frame image path")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed")
    parser.add_argument("--frames", type=int, default=121, help="Number of frames (default: 121)")
    parser.add_argument("--width", type=int, default=720, help="Video width (default: 720)")
    parser.add_argument("--height", type=int, default=1280, help="Video height (default: 1280)")
    parser.add_argument("--fps", type=float, default=24.0, help="Frame rate (default: 24)")
    parser.add_argument("--output", "-o", default=None, help="Output filename in generated/")
    args = parser.parse_args()

    prompt = args.prompt or DEFAULT_PROMPT
    seed = args.seed if args.seed is not None else int(time.time() * 1000) % (2**53)
    out_name = args.output or f"morph_{int(time.time())}.mp4"

    start_path = Path(args.start)
    end_path = Path(args.end)

    if not start_path.exists():
        print(f"Error: Start image not found: {start_path}")
        return 1
    if not end_path.exists():
        print(f"Error: End image not found: {end_path}")
        return 1

    # 1. Upload both images
    print(f"Uploading start frame: {start_path.name}...", flush=True)
    start_name = upload_image(start_path)

    print(f"Uploading end frame: {end_path.name}...", flush=True)
    end_name = upload_image(end_path)

    # 2. Build & queue workflow
    print(f"Generating video (seed={seed}, {args.frames} frames, {args.fps}fps)...", flush=True)
    workflow = build_workflow(
        prompt=prompt,
        start_image=start_name,
        end_image=end_name,
        seed=seed,
        frames=args.frames,
        width=args.width,
        height=args.height,
        fps=args.fps,
    )
    filename, subfolder, out_type, media_type = queue_and_wait(workflow)

    # 3. Download result
    dest = GENERATED / out_name
    print(f"\nDownloading to {dest}...", flush=True)
    download_output(filename, subfolder, out_type, dest)
    print(f"Saved: {dest}")
    print(f"Type: {media_type}")

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
