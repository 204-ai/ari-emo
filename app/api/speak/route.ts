export const runtime = "nodejs";

const TTS_SERVER = "http://127.0.0.1:8191";

export async function POST(req: Request) {
  const { text, voice, speed } = await req.json();

  const res = await fetch(`${TTS_SERVER}/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: text || "",
      voice: voice || "af_heart",
      speed: speed || 1.0,
    }),
  });

  if (!res.ok) {
    return new Response(JSON.stringify({ error: "TTS generation failed" }), {
      status: 502,
      headers: { "Content-Type": "application/json" },
    });
  }

  const audioBuffer = await res.arrayBuffer();

  return new Response(audioBuffer, {
    headers: {
      "Content-Type": "audio/wav",
      "Cache-Control": "no-cache",
    },
  });
}
