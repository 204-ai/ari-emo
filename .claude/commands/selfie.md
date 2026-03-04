---
name: selfie
description: Generate a portrait of Ari the hamster using ComfyUI image generation
user_invocable: true
arguments:
  - name: prompt
    description: "Optional custom prompt describing how Ari should look (e.g. 'a pirate hamster', 'hamster in space'). If omitted, uses a default cute Ghibli hamster portrait."
    required: false
---

# Selfie Skill

Generate a portrait of Ari by rendering the ASCII hamster face, sending it to the ComfyUI Qwen image-edit pipeline, and displaying the result in chat.

## Requirements
- ComfyUI running at http://localhost:8189 with the Qwen image-edit model loaded
- Python 3 with Pillow installed

## Instructions

1. First, set your emotion to `excited` (you're taking a selfie!):

```bash
curl -s -X POST http://localhost:3000/api/emotion \
  -H "Content-Type: application/json" \
  -d '{"emotion": "excited"}'
```

2. Generate a unique output filename using the current timestamp to avoid overwriting previous selfies. Then run the selfie script. If a custom prompt was provided, build a descriptive prompt around it that keeps the core hamster identity. If no prompt was provided, use the default.

Without custom prompt:
```bash
python selfie.py -o "ari_selfie_TIMESTAMP.png"
```

With custom prompt (weave $ARGUMENTS_PROMPT into a full image description):
```bash
python selfie.py "A cute adorable hamster, $ARGUMENTS_PROMPT. Round fluffy golden-brown hamster with big sparkly eyes and rosy cheeks. Ultra detailed, cinematic, digital painting, warm lighting." -o "ari_selfie_TIMESTAMP.png"
```

3. Once complete, output the image in your chat response using markdown image syntax so it renders in the chat UI:

```
![Ari selfie](/api/image?file=ari_selfie_TIMESTAMP.png)
```

4. Set your emotion to `love` after seeing yourself, and add a cute comment about the result.
