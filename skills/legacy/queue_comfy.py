"""Queue a ComfyUI workflow to generate Ari's portrait."""

import json
import time
import urllib.request
import urllib.error

SERVER = "http://localhost:8189"

PROMPT = (
    "A cute adorable hamster character portrait, studio Ghibli style. "
    "Round fluffy golden-brown hamster with big sparkly eyes and rosy cheeks, "
    "tiny paws held up near its face. Wearing a tiny glowing sci-fi headset. "
    "Soft warm lighting, dark cozy background with faint glowing terminal text. "
    "The hamster looks happy and friendly. Ultra detailed, cinematic, "
    "digital painting, warm color palette, soft bokeh background."
)

# Build the workflow from the user's template, swapping the image + prompt
workflow = {
    "3": {
        "inputs": {
            "seed": 428571337,
            "steps": 4,
            "cfg": 1,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1,
            "model": ["75", 0],
            "positive": ["111", 0],
            "negative": ["110", 0],
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
            "type": "qwen_image",
            "device": "default",
        },
        "class_type": "CLIPLoader",
    },
    "39": {
        "inputs": {"vae_name": "qwen_image_vae.safetensors"},
        "class_type": "VAELoader",
    },
    "60": {
        "inputs": {
            "filename_prefix": "ari_portrait/img",
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
        "inputs": {"image": "ari_face.png"},
        "class_type": "LoadImage",
    },
    "88": {
        "inputs": {"pixels": ["93", 0], "vae": ["39", 0]},
        "class_type": "VAEEncode",
    },
    "89": {
        "inputs": {
            "lora_name": "Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors",
            "strength_model": 1,
            "model": ["37", 0],
        },
        "class_type": "LoraLoaderModelOnly",
    },
    "93": {
        "inputs": {
            "upscale_method": "lanczos",
            "megapixels": 1,
            "resolution_steps": 1,
            "image": ["78", 0],
        },
        "class_type": "ImageScaleToTotalPixels",
    },
    "110": {
        "inputs": {
            "prompt": "",
            "clip": ["38", 0],
            "vae": ["39", 0],
            "image1": ["93", 0],
        },
        "class_type": "TextEncodeQwenImageEditPlus",
    },
    "111": {
        "inputs": {
            "prompt": PROMPT,
            "clip": ["38", 0],
            "vae": ["39", 0],
            "image1": ["93", 0],
        },
        "class_type": "TextEncodeQwenImageEditPlus",
    },
}

payload = json.dumps({"prompt": workflow}).encode("utf-8")

# Queue the prompt
req = urllib.request.Request(
    f"{SERVER}/prompt",
    data=payload,
    headers={"Content-Type": "application/json"},
)
resp = urllib.request.urlopen(req)
result = json.loads(resp.read())
prompt_id = result["prompt_id"]
print(f"Queued! prompt_id = {prompt_id}")

# Poll for completion
print("Waiting for generation...", end="", flush=True)
for _ in range(120):
    time.sleep(2)
    try:
        hist_resp = urllib.request.urlopen(f"{SERVER}/history/{prompt_id}")
        history = json.loads(hist_resp.read())
        if prompt_id in history:
            entry = history[prompt_id]
            if entry.get("status", {}).get("completed", False):
                outputs = entry.get("outputs", {})
                # Find the SaveImage node output
                for node_id, node_out in outputs.items():
                    if "images" in node_out:
                        for img_info in node_out["images"]:
                            fname = img_info["filename"]
                            subfolder = img_info.get("subfolder", "")
                            img_type = img_info.get("type", "output")
                            url = f"{SERVER}/view?filename={fname}&subfolder={subfolder}&type={img_type}"
                            print(f"\nDone! Downloading {fname}...")
                            urllib.request.urlretrieve(url, "ari_portrait.png")
                            print("Saved ari_portrait.png")
                            raise SystemExit(0)
                print("\nCompleted but no image output found.")
                print(json.dumps(outputs, indent=2))
                raise SystemExit(1)
            elif entry.get("status", {}).get("status_str") == "error":
                print("\nGeneration failed!")
                print(json.dumps(entry.get("status", {}), indent=2))
                raise SystemExit(1)
    except urllib.error.URLError:
        pass
    print(".", end="", flush=True)

print("\nTimed out waiting for result.")
raise SystemExit(1)
