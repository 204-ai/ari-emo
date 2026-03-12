"""Faster Whisper transcription server for Ari voice input."""

import io
import uvicorn
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

print("Loading faster-whisper large-v3 model...")
model = WhisperModel("large-v3", device="cuda", compute_type="float16")
print("Model loaded!")


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = file.filename or "audio.webm"

    segments, info = model.transcribe(audio_file, beam_size=5)
    text = " ".join(segment.text.strip() for segment in segments)

    return {"text": text, "language": info.language}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8190)
