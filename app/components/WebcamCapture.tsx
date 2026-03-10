"use client";

import { useRef, useState, useEffect } from "react";

interface WebcamCaptureProps {
  onCapture: (file: File) => void;
  onClose: () => void;
}

export default function WebcamCapture({ onCapture, onClose }: WebcamCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "user" } })
      .then((s) => {
        if (!active) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }
        setStream(s);
        if (videoRef.current) {
          videoRef.current.srcObject = s;
        }
      })
      .catch(() => setError("Could not access camera"));

    return () => {
      active = false;
    };
  }, []);

  // Cleanup stream on unmount
  useEffect(() => {
    return () => {
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [stream]);

  const capture = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Mirror the capture to match the preview
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0);

    canvas.toBlob((blob) => {
      if (blob) {
        const file = new File([blob], `webcam-${Date.now()}.png`, { type: "image/png" });
        onCapture(file);
      }
    }, "image/png");

    // Stop camera
    stream?.getTracks().forEach((t) => t.stop());
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          stream?.getTracks().forEach((t) => t.stop());
          onClose();
        }
      }}
    >
      <div className="bg-zinc-900 rounded-xl p-4 flex flex-col items-center gap-3 max-w-lg w-full mx-4">
        <h3 className="text-sm font-semibold text-zinc-300">Camera</h3>

        {error ? (
          <p className="text-red-400 text-sm py-8">{error}</p>
        ) : (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="rounded-lg w-full"
            style={{ transform: "scaleX(-1)" }}
          />
        )}

        <canvas ref={canvasRef} className="hidden" />

        <div className="flex gap-3">
          <button
            onClick={() => {
              stream?.getTracks().forEach((t) => t.stop());
              onClose();
            }}
            className="px-4 py-2 bg-zinc-700 text-zinc-300 rounded-lg text-sm hover:bg-zinc-600 transition-colors"
          >
            Cancel
          </button>
          {!error && (
            <button
              onClick={capture}
              className="px-4 py-2 bg-zinc-200 text-zinc-900 rounded-lg text-sm font-semibold hover:bg-white transition-colors"
            >
              Capture
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
