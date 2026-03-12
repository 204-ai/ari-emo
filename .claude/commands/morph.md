---
name: morph
description: Generate a morph video between two images using LTX Video 2.3
user_invocable: true
arguments:
  - name: prompt
    description: "Description of the transformation/motion between start and end frames. If omitted, uses a default smooth transformation prompt."
    required: false
---

# Morph Skill — LTX Video 2.3 Start-to-End Frame Video Generation

Generate a smooth morphing video between two reference images using ComfyUI's LTX Video 2.3 pipeline.

## Requirements
- ComfyUI running with LTX Video 2.3 models loaded:
  - `ltx-2.3-22b-distilled.safetensors` (checkpoint)
  - `gemma_3_12B_it_fp4_mixed.safetensors` (text encoder)
  - `ltx-2.3-spatial-upscaler-x2-1.0.safetensors` (upscaler)

## How It Works
The pipeline takes a **start frame** and an **end frame**, plus a text prompt describing the desired transformation. It uses `LTXVFirstLastFrameControl_TTP` to generate a video that smoothly morphs between the two images. Two-pass sampling with spatial upscaling produces high quality output.

## Instructions

1. Ask the user for two images:
   - **Start frame**: The first image (beginning of the video)
   - **End frame**: The second image (end of the video)

   These can be:
   - Uploaded images from the user
   - Previously generated images in `generated/`
   - Any image file path

2. Set emotion to `excited`:
```bash
curl -s -X POST http://localhost:3000/api/emotion \
  -H "Content-Type: application/json" \
  -d '{"emotion": "excited"}'
```

3. Generate a unique output filename using timestamp. Run the morph script:

Without custom prompt:
```bash
python skills/comfy/morph.py --start "path/to/start.png" --end "path/to/end.png" -o "morph_TIMESTAMP.mp4"
```

With custom prompt (use $ARGUMENTS_PROMPT or craft one based on the images):
```bash
python skills/comfy/morph.py --start "path/to/start.png" --end "path/to/end.png" -o "morph_TIMESTAMP.mp4" "PROMPT_TEXT"
```

Optional flags:
- `--frames 121` — number of frames (default 121 = ~5 seconds at 24fps)
- `--width 720 --height 1280` — resolution (default portrait 720x1280)
- `--fps 24` — frame rate
- `--seed 12345` — reproducible generation

4. This is a video generation task and will take significantly longer than image generation (several minutes). Warn the user it may take a while.

5. Once complete, report the output path and set emotion to `love`.

## Tips for Good Prompts
- Describe the **motion and transformation**, not just the static scene
- Mention camera behavior (e.g., "camera remains steady", "slow dolly in")
- Describe what changes between start and end (e.g., "the flower blooms", "day turns to night")
- Keep it cinematic: mention lighting, atmosphere, mood
- The negative prompt is built-in (no jump cuts, no talking, no watermarks, etc.)
