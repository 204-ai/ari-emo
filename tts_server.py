"""Kokoro TTS server for Ari voice output."""

import io
import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Loading Kokoro TTS model...")
from kokoro_onnx import Kokoro

kokoro = Kokoro("models/kokoro-v1.0.int8.onnx", "models/voices-v1.0.bin")
print("Kokoro TTS ready!")


class TTSRequest(BaseModel):
    text: str
    voice: str = "af_heart"
    speed: float = 1.0


@app.post("/tts")
async def text_to_speech(req: TTSRequest):
    samples, sample_rate = kokoro.create(
        req.text, voice=req.voice, speed=req.speed, lang="en-us"
    )

    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="WAV")
    buf.seek(0)

    return StreamingResponse(buf, media_type="audio/wav")


@app.get("/voices")
async def list_voices():
    voices = np.load("models/voices-v1.0.bin", allow_pickle=True)
    return {"voices": voices.files}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8191)
