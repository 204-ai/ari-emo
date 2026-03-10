# Important Memories

## Project
- Next.js app with split-pane layout: ChatPane (left) + HamsterPane (right)
- Skills panel added below hamster pane (collapsible)
- ComfyUI at external IP (set via COMFYUI_URL in .env.local, NOT hardcoded)
- TTS server at 127.0.0.1:8191 (Kokoro)
- selfie.py generates AI portraits via Qwen image-edit pipeline

## Architecture Decisions
- Hamster state (idle/thinking/talking) lifted to parent page.tsx as shared React state
- Both ChatPane and HamsterPane receive it as props — no API polling for state
- Emotion still polled via /api/emotion (1s interval) — only for emotion, not state
- TTS uses generation counter to prevent stale callbacks from previous responses
- TTS batching: first sentence immediate, then ~150 char chunks for smooth playback
- In-flight TTS tracking (ttsPendingRef) prevents premature idle

## Session History
- 2026-03-10: Fixed TTS state management, hamster state races, memory leaks
- 2026-03-10: Added SkillsPane component
- Generated selfies: Ari solo, Ari + Brian, Ari + Dimitri, Dimitri on beach with baby seals
