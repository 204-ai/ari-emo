Generate a branded video reel/advertisement using the 4-phase pipeline.

## How it works

The `/reel` skill automates the full ad generation pipeline:
1. **Keyframes** — Generate N+1 keyframe images via Qwen image-edit (ComfyUI)
2. **Morph clips** — Generate N morph videos between consecutive keyframes via LTX Video 2.3
3. **Overlays** — Add subtitle captions, brand watermark, and optional secondary credit via ffmpeg
4. **Stitch** — Concatenate all clips into the final video

## Your task

Based on the user's concept description: $ARGUMENTS

1. **Design the reel** — Create a compelling narrative arc with 6 scenes (7 keyframes). Include:
   - A consistent character description (CHAR)
   - A consistent visual style (STYLE)
   - A consistent venue/setting (VENUE)
   - 7 keyframe prompts that tell a story (each should include CHAR + STYLE tokens)
   - 6 morph prompts describing the transitions
   - 6 subtitle captions (short, punchy — max 2 lines each)
   - Optionally: 6 narration lines if using TTS or native audio

2. **Write the config JSON** — Save to `generated/{name}_config.json`:
```json
{
  "name": "slug_name",
  "brand": "204.ai",
  "secondary_brand": null,
  "audio_mode": "none",
  "width": 720,
  "height": 1280,
  "fps": 24,
  "frames_per_clip": 121,
  "output": "slug_name_reel.mp4",
  "keyframes": ["7 keyframe prompts..."],
  "morph_prompts": ["6 morph prompts..."],
  "captions": ["6 subtitle lines..."],
  "narration": ["6 TTS lines (if audio_mode=tts)"]
}
```

3. **Run the pipeline**:
```bash
python skills/comfy/reel.py generated/{name}_config.json
```

4. If generation fails mid-way (e.g. VRAM OOM), resume with:
```bash
python skills/comfy/reel.py generated/{name}_config.json --resume N
```

5. If keyframes are already generated and you only need to redo morphs:
```bash
python skills/comfy/reel.py generated/{name}_config.json --skip-keyframes
```

## Audio modes
- `none` — Silent video with subtitle overlays only
- `tts` — Kokoro TTS narration (requires `narration` field in config)
- `native` — LTX 2.3 native audio generation (embed speech descriptions in morph prompts)

## Tips for good results
- Keep keyframe prompts consistent: always include the same character, style, and venue tokens
- Morph prompts should describe smooth transitions, avoid jump cuts
- For speech (native mode), embed quoted dialogue in morph prompts: `A cute voice says: "Hello world!"`
- Captions should be short and punchy — they fade in/out over 5 seconds per clip
- The final video will be ~N*5 seconds (N clips x 121 frames @ 24fps)

## Parameters
- **brand**: Primary watermark text (top right), default "204.ai"
- **secondary_brand**: Optional secondary credit (bottom left)
- **audio_mode**: "none" (default), "tts", or "native"
- **scenes**: Number of morph clips (default 6, meaning 7 keyframes)
