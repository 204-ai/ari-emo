"use client";

import { useEffect, useRef, useState } from "react";
import type { HamsterState } from "../page";
import WebcamCapture from "./WebcamCapture";

interface Message {
  role: "user" | "assistant";
  content: string;
  toolUse?: string;
}

interface HistorySession {
  filename: string;
  date: string;
  summary: string;
  messages: { role: "user" | "assistant"; content: string; time?: string }[];
}

/** Check if a URL points to a video file. */
function isVideoUrl(url: string) {
  return /\.(mp4|webm|mov)(\?|$)/i.test(url);
}

/** Check if a URL points to a 3D model file. */
function isModelUrl(url: string) {
  return /\.(glb|gltf)(\?|$)/i.test(url);
}

/** Ensure Google model-viewer script is loaded (shared guard with SkillsPane). */
function ensureModelViewer() {
  if (typeof window === "undefined") return;
  if (document.querySelector('script[src*="model-viewer"]')) return;
  const script = document.createElement("script");
  script.type = "module";
  script.src =
    "https://ajax.googleapis.com/ajax/libs/model-viewer/4.0.0/model-viewer.min.js";
  document.head.appendChild(script);
}

/** 3D model viewer component using Google model-viewer. */
function ModelViewer({ src, alt }: { src: string; alt: string }) {
  useEffect(() => {
    ensureModelViewer();
  }, []);

  return (
    <div className="rounded-lg my-2 overflow-hidden" style={{ maxWidth: 480 }}>
      {/* @ts-expect-error model-viewer is a web component */}
      <model-viewer
        src={src}
        alt={alt || "3D model"}
        auto-rotate
        camera-controls
        camera-target="auto auto auto"
        touch-action="pan-y"
        shadow-intensity="1"
        environment-image="neutral"
        style={{
          width: "100%",
          height: "360px",
          backgroundColor: "#1a1a2e",
          borderRadius: "8px",
        }}
      >
        <div
          slot="progress-bar"
          style={{
            position: "absolute",
            bottom: 8,
            left: 8,
            color: "#aaa",
            fontSize: "12px",
          }}
        >
          Loading 3D model...
        </div>
      {/* @ts-expect-error model-viewer is a web component */}
      </model-viewer>
      <div
        style={{
          padding: "6px 10px",
          fontSize: "11px",
          color: "#888",
          background: "#111",
        }}
      >
        Drag to rotate / Scroll to zoom / Shift+drag to pan
      </div>
    </div>
  );
}

/** Parse message content, rendering ![alt](url) as images, videos, or 3D models. */
function renderContent(content: string) {
  const parts = content.split(/(!\[[^\]]*\]\([^)]+\))/g);
  if (parts.length === 1) return content;

  return parts.map((part, i) => {
    const match = part.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
    if (match) {
      const [, alt, src] = match;
      if (isModelUrl(src)) {
        return <ModelViewer key={i} src={src} alt={alt} />;
      }
      if (isVideoUrl(src)) {
        return (
          <video
            key={i}
            src={src}
            controls
            loop
            muted
            autoPlay
            playsInline
            className="rounded-lg my-2 max-w-full"
            style={{ maxHeight: 400 }}
          />
        );
      }
      return (
        <img
          key={i}
          src={src}
          alt={alt}
          className="rounded-lg my-2 max-w-full"
          style={{ maxHeight: 320 }}
        />
      );
    }
    return part ? <span key={i}>{part}</span> : null;
  });
}

/** Upload files to the server, return upload results. */
async function uploadFiles(
  files: File[]
): Promise<{ filename: string; absolutePath: string }[]> {
  const results = [];
  for (const file of files) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    results.push(await res.json());
  }
  return results;
}

interface ChatPaneProps {
  setHamsterState: (state: HamsterState) => void;
}

export default function ChatPane({ setHamsterState: setHamsterStateProp }: ChatPaneProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("ari-session-id");
    }
    return null;
  });
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const liveTranscriptRef = useRef("");
  const speechRecRef = useRef<SpeechRecognition | null>(null);
  const hasSpeechAPIRef = useRef(false);
  const cancelRecordingRef = useRef(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const ttsEnabledRef = useRef(true);
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);
  const ttsAudioUrlRef = useRef<string | null>(null);
  const ttsQueueRef = useRef<{ url: string; audio: HTMLAudioElement }[]>([]);
  const ttsPlayingRef = useRef(false);
  const ttsSentIndexRef = useRef(0);
  const ttsChainRef = useRef<Promise<void>>(Promise.resolve());
  const ttsGenRef = useRef(0); // generation counter to discard stale TTS callbacks
  const ttsPendingRef = useRef(0); // count of in-flight TTS fetches
  const isStreamingRef = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Token counter state
  const [estimatedTokens, setEstimatedTokens] = useState(0);
  const [sessionTokens, setSessionTokens] = useState(0);

  // Webcam state
  const [showWebcam, setShowWebcam] = useState(false);

  // History state
  const [historySessions, setHistorySessions] = useState<HistorySession[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [hasMoreHistory, setHasMoreHistory] = useState(true);
  const oldestLoadedRef = useRef<string | null>(null);
  const initialHistoryLoaded = useRef(false);

  // Session log tracking
  const sessionFileRef = useRef<string | null>(null);

  // Hamster state helper — updates React state (instant) + API (for persistence)
  const setHamsterState = (state: HamsterState) => {
    setHamsterStateProp(state); // instant React update — HamsterPane sees it immediately
    fetch("/api/emotion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state }),
    }).catch(() => {});
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Persist sessionId to localStorage
  useEffect(() => {
    if (sessionId) {
      localStorage.setItem("ari-session-id", sessionId);
    }
  }, [sessionId]);

  // Cleanup TTS and preview URLs on unmount
  useEffect(() => {
    return () => {
      flushTTS(true);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── History loading ────────────────────────────────────────────────

  const loadMoreHistory = async () => {
    if (loadingHistory || !hasMoreHistory) return;
    setLoadingHistory(true);

    const container = scrollContainerRef.current;
    const prevScrollHeight = container?.scrollHeight ?? 0;

    try {
      const params = oldestLoadedRef.current
        ? `?before=${oldestLoadedRef.current}`
        : "";
      const res = await fetch(`/api/history${params}`);
      const data = await res.json();

      if (data.session) {
        setHistorySessions((prev) => [data.session, ...prev]);
        oldestLoadedRef.current = data.session.filename;
        setHasMoreHistory(data.hasMore);

        // Preserve scroll position after prepending
        requestAnimationFrame(() => {
          if (container) {
            const newScrollHeight = container.scrollHeight;
            container.scrollTop = newScrollHeight - prevScrollHeight;
          }
        });
      } else {
        setHasMoreHistory(false);
      }
    } catch (err) {
      console.error("[history] Failed to load:", err);
    } finally {
      setLoadingHistory(false);
    }
  };

  // Load the most recent history session on mount
  useEffect(() => {
    if (!initialHistoryLoaded.current) {
      initialHistoryLoaded.current = true;
      loadMoreHistory();
    }
  }, []);

  // Scroll-to-top detection
  const handleScroll = () => {
    const container = scrollContainerRef.current;
    if (!container) return;
    if (container.scrollTop < 80 && !loadingHistory && hasMoreHistory) {
      loadMoreHistory();
    }
  };

  // ── File attachment helpers ───────────────────────────────────────

  const addFiles = (files: FileList | File[]) => {
    const imageFiles = Array.from(files).filter((f) =>
      f.type.startsWith("image/")
    );
    if (imageFiles.length === 0) return;

    setAttachedFiles((prev) => [...prev, ...imageFiles]);
    const urls = imageFiles.map((f) => URL.createObjectURL(f));
    setPreviewUrls((prev) => [...prev, ...urls]);
  };

  const removeFile = (index: number) => {
    URL.revokeObjectURL(previewUrls[index]);
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
    setPreviewUrls((prev) => prev.filter((_, i) => i !== index));
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const imageFiles: File[] = [];
    for (const item of Array.from(items)) {
      if (item.type.startsWith("image/")) {
        const file = item.getAsFile();
        if (file) imageFiles.push(file);
      }
    }
    if (imageFiles.length > 0) {
      e.preventDefault();
      addFiles(imageFiles);
    }
  };

  // ── Voice recording with real-time transcription ─────────────────

  const updateLiveTranscript = (text: string) => {
    liveTranscriptRef.current = text;
    setLiveTranscript(text);
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];
      updateLiveTranscript("");
      hasSpeechAPIRef.current = false;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());

        // Stop speech recognition if running
        if (speechRecRef.current) {
          speechRecRef.current.stop();
          speechRecRef.current = null;
        }

        // If cancelled, discard everything
        if (cancelRecordingRef.current) {
          cancelRecordingRef.current = false;
          updateLiveTranscript("");
          chunksRef.current = [];
          return;
        }

        const transcript = liveTranscriptRef.current.trim();

        // If Web Speech API gave us text, put it in the input box for editing
        if (hasSpeechAPIRef.current && transcript) {
          updateLiveTranscript("");
          setInput((prev) => (prev ? prev + " " + transcript : transcript));
          setTimeout(() => inputRef.current?.focus(), 50);
          return;
        }

        // Fallback: transcribe via Whisper server, then put in input box
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        if (blob.size === 0) {
          updateLiveTranscript("");
          return;
        }

        setIsTranscribing(true);
        try {
          const formData = new FormData();
          formData.append("file", blob, "recording.webm");
          const res = await fetch("/api/transcribe", { method: "POST", body: formData });
          if (!res.ok) throw new Error(`Transcription failed: ${res.status}`);
          const data = await res.json();
          if (data.text) {
            setInput((prev) => (prev ? prev + " " + data.text : data.text));
            setTimeout(() => inputRef.current?.focus(), 50);
          }
        } catch (err) {
          console.error("[voice] Transcription error:", err);
        } finally {
          setIsTranscribing(false);
          updateLiveTranscript("");
        }
      };

      mediaRecorder.start();
      setIsRecording(true);

      // Try Web Speech API for real-time preview
      const SpeechRecognitionAPI =
        window.SpeechRecognition || window.webkitSpeechRecognition;

      if (SpeechRecognitionAPI) {
        const recognition = new SpeechRecognitionAPI();
        recognition.continuous = true;
        recognition.interimResults = true;

        recognition.onresult = (event: SpeechRecognitionEvent) => {
          hasSpeechAPIRef.current = true;
          let finalText = "";
          let interimText = "";
          for (let i = 0; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
              finalText += event.results[i][0].transcript;
            } else {
              interimText += event.results[i][0].transcript;
            }
          }
          updateLiveTranscript(finalText + interimText);
        };

        recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
          console.log("[voice] Speech recognition error:", event.error);
        };

        recognition.start();
        speechRecRef.current = recognition;
      }
    } catch (err) {
      console.error("[voice] Mic access error:", err);
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    setIsRecording(false);
  };

  const cancelRecording = () => {
    cancelRecordingRef.current = true;
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    setIsRecording(false);
  };

  const toggleRecording = () => {
    if (isRecording) stopRecording();
    else startRecording();
  };

  // ── TTS playback (sentence-chunked queue) ────────────────────────

  // Keep refs in sync with state so async callbacks see current value
  useEffect(() => { ttsEnabledRef.current = ttsEnabled; }, [ttsEnabled]);
  // isStreamingRef is synced manually in sendMessage start/finally for immediate visibility

  /** Preload the next audio clip so it starts instantly when needed. */
  const preloadNext = () => {
    const peek = ttsQueueRef.current[0];
    if (peek) peek.audio.load();
  };

  /** Play the next queued audio clip. Calls itself on `ended`. */
  const playNextTTS = () => {
    if (!ttsEnabledRef.current) {
      // TTS was disabled — drain queue
      for (const item of ttsQueueRef.current) URL.revokeObjectURL(item.url);
      ttsQueueRef.current = [];
      ttsPlayingRef.current = false;
      setHamsterState("idle");
      return;
    }

    const next = ttsQueueRef.current.shift();
    if (!next) {
      ttsPlayingRef.current = false;
      ttsAudioRef.current = null;
      // Only go idle if stream is done AND no TTS fetches are still in-flight
      if (!isStreamingRef.current && ttsPendingRef.current === 0) {
        setHamsterState("idle");
      }
      return;
    }

    ttsPlayingRef.current = true;
    ttsAudioRef.current = next.audio;
    ttsAudioUrlRef.current = next.url;
    // Ensure hamster shows talking while audio plays
    setHamsterState("talking");
    // Preload the upcoming clip so there's no gap
    preloadNext();
    next.audio.onended = () => {
      URL.revokeObjectURL(next.url);
      playNextTTS();
    };
    next.audio.onerror = () => {
      URL.revokeObjectURL(next.url);
      playNextTTS();
    };
    next.audio.play().catch(() => playNextTTS());
  };

  /** Clean markdown/written-text artifacts so TTS sounds natural. */
  const sanitizeForSpeech = (text: string): string => {
    let s = text;
    // Remove code blocks entirely (``` ... ```)
    s = s.replace(/```[\s\S]*?```/g, " code block ");
    // Remove inline code backticks, keep the words
    s = s.replace(/`([^`]*)`/g, "$1");
    // Remove image markdown
    s = s.replace(/!\[[^\]]*\]\([^)]+\)/g, "");
    // Convert links to just the link text
    s = s.replace(/\[([^\]]*)\]\([^)]+\)/g, "$1");
    // Remove bold/italic markers
    s = s.replace(/\*{1,3}([^*]+)\*{1,3}/g, "$1");
    s = s.replace(/_{1,3}([^_]+)_{1,3}/g, "$1");
    // Remove strikethrough
    s = s.replace(/~~([^~]+)~~/g, "$1");
    // Remove markdown headers (# ## ### etc.)
    s = s.replace(/^#{1,6}\s+/gm, "");
    // Remove bullet points and list markers
    s = s.replace(/^[\s]*[-*+]\s+/gm, "");
    s = s.replace(/^[\s]*\d+\.\s+/gm, "");
    // Remove standalone URLs
    s = s.replace(/https?:\/\/[^\s)]+/g, "");
    // Remove horizontal rules
    s = s.replace(/^[-*_]{3,}\s*$/gm, "");
    // Remove blockquote markers
    s = s.replace(/^>\s+/gm, "");
    // Collapse multiple spaces/newlines
    s = s.replace(/\s+/g, " ");
    return s.trim();
  };

  /** Send a sentence to TTS and enqueue the resulting audio.
   *  Fetches fire immediately (parallel) but the chain ensures
   *  results are added to the playback queue in the correct order.
   */
  const enqueueTTS = (sentence: string) => {
    if (!ttsEnabledRef.current || !sentence.trim()) return;

    const cleaned = sanitizeForSpeech(sentence);
    if (!cleaned) return;

    // Track in-flight request so finally block knows TTS work is pending
    ttsPendingRef.current++;

    // Fire the fetch immediately — don't wait for previous sentences
    const audioPromise = fetch("/api/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: cleaned, voice: "af_heart", speed: 1.0 }),
    })
      .then((res) => (res.ok ? res.blob() : null))
      .then((blob) => {
        if (!blob) return null;
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        return { url, audio };
      })
      .catch((err) => {
        console.error("[tts] Fetch error:", err);
        return null;
      });

    // Chain ensures enqueue order matches sentence order
    const gen = ttsGenRef.current; // capture current generation
    ttsChainRef.current = ttsChainRef.current.then(async () => {
      ttsPendingRef.current = Math.max(0, ttsPendingRef.current - 1);
      // Discard if a new response has started (flushTTS bumped the generation)
      if (gen !== ttsGenRef.current) return;
      const result = await audioPromise;
      if (!result || !ttsEnabledRef.current || gen !== ttsGenRef.current) return;

      ttsQueueRef.current.push(result);
      if (!ttsPlayingRef.current) playNextTTS();
    });
  };

  /** Extract TTS-ready chunks from new text beyond sentIndex.
   *  First sentence sends immediately (fast start), then batches ~150+ chars. */
  const TTS_BATCH_CHUNK = 150;
  const ttsBufferRef = useRef("");
  const ttsFirstSentRef = useRef(true); // true until first chunk is emitted

  const extractSentences = (fullText: string, sentIndex: number): { sentences: string[]; newIndex: number } => {
    const newText = fullText.slice(sentIndex);
    const rawSentences: { text: string; end: number }[] = [];
    const re = /[^.!?\n]*[.!?](?=\s|$)|[^\n]+\n/g;
    let match: RegExpExecArray | null;

    while ((match = re.exec(newText)) !== null) {
      const sentence = match[0].trim();
      if (sentence) rawSentences.push({ text: sentence, end: match.index + match[0].length });
    }

    const chunks: string[] = [];
    let lastEnd = 0;

    for (const s of rawSentences) {
      ttsBufferRef.current += (ttsBufferRef.current ? " " : "") + s.text;
      lastEnd = s.end;

      // First sentence: emit immediately for fast start
      // After that: batch until we have enough text for smooth playback
      if (ttsFirstSentRef.current || ttsBufferRef.current.length >= TTS_BATCH_CHUNK) {
        chunks.push(ttsBufferRef.current);
        ttsBufferRef.current = "";
        ttsFirstSentRef.current = false;
      }
    }

    return { sentences: chunks, newIndex: sentIndex + lastEnd };
  };

  /** Stop all TTS playback and clear the queue. */
  const flushTTS = (goIdle = false) => {
    if (ttsAudioRef.current) {
      ttsAudioRef.current.onended = null;
      ttsAudioRef.current.onerror = null;
      ttsAudioRef.current.pause();
      if (ttsAudioUrlRef.current) URL.revokeObjectURL(ttsAudioUrlRef.current);
      ttsAudioRef.current = null;
      ttsAudioUrlRef.current = null;
    }
    for (const item of ttsQueueRef.current) URL.revokeObjectURL(item.url);
    ttsQueueRef.current = [];
    ttsPlayingRef.current = false;
    ttsSentIndexRef.current = 0;
    ttsBufferRef.current = "";
    ttsFirstSentRef.current = true; // next response starts fresh — first sentence immediate
    ttsPendingRef.current = 0;
    ttsGenRef.current++; // invalidate pending TTS fetches from previous response
    ttsChainRef.current = Promise.resolve();
    if (goIdle) setHamsterState("idle");
  };

  // ── Session logging ─────────────────────────────────────────────

  const logToSession = async (role: "user" | "assistant", content: string) => {
    // Log to markdown session file
    try {
      const res = await fetch("/api/session-log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role, content, sessionFile: sessionFileRef.current }),
      });
      if (res.ok) {
        const data = await res.json();
        sessionFileRef.current = data.sessionFile;
      }
    } catch (err) {
      console.error("[session-log] Failed to log:", err);
    }
    // Log to SQLite memory server (fire-and-forget)
    if (sessionId) {
      fetch("/api/memory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "message",
          session_id: sessionId,
          role,
          content,
          token_estimate: Math.ceil(content.length / 4),
        }),
      }).catch(() => {});
    }
  };

  // ── Send message ──────────────────────────────────────────────────

  const sendMessage = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
    if ((!text && attachedFiles.length === 0) || isStreaming) return;

    const filesToSend = [...attachedFiles];
    const previewsToSend = [...previewUrls];

    setInput("");
    setAttachedFiles([]);
    setPreviewUrls([]);
    setIsStreaming(true);
    // Sync ref immediately so playNextTTS (from previous response) sees the correct value
    isStreamingRef.current = true;

    const messageText = text || "(shared an image)";

    // Set hamster to thinking
    setHamsterState("thinking");
    setEstimatedTokens(0);

    // Reset TTS sentence tracking for new response
    flushTTS();

    try {
      // Upload files first
      let imagePaths: string[] | undefined;
      let imageUrls: string[] = [];
      if (filesToSend.length > 0) {
        const uploadResults = await uploadFiles(filesToSend);
        imagePaths = uploadResults.map((r) => r.absolutePath);
        imageUrls = uploadResults.map(
          (r) => `/api/image?file=${encodeURIComponent(r.filename)}&source=uploads`
        );
      }

      // Build content with image markdown so images persist in history
      let fullContent = messageText;
      if (imageUrls.length > 0) {
        const imageMd = imageUrls
          .map((url, i) => `![Attached ${i + 1}](${url})`)
          .join("\n");
        fullContent = messageText + "\n\n" + imageMd;
      }

      // Add user message with persistent image URLs
      setMessages((prev) => [
        ...prev,
        { role: "user", content: fullContent },
      ]);

      // Revoke blob preview URLs (no longer needed)
      previewsToSend.forEach((url) => URL.revokeObjectURL(url));

      // Log user message (with image markdown) to session file
      logToSession("user", fullContent);

      // Add empty assistant message to stream into
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

      const payload = { message: messageText, sessionId, imagePaths };
      console.log("[chat-ui] Sending message:", JSON.stringify(payload));

      const controller = new AbortController();
      abortRef.current = controller;

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      console.log("[chat-ui] Fetch response — status:", res.status, "ok:", res.ok, "body present:", !!res.body);

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentToolName = "";
      let chunkIndex = 0;
      let finalAssistantText = "";
      let firstTextReceived = false;
      let gotResult = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.log("[chat-ui] Stream reader done");
          break;
        }

        const decoded = decoder.decode(value, { stream: true });
        console.log("[chat-ui] Raw chunk #" + chunkIndex + " (" + decoded.length + " chars):", decoded);
        chunkIndex++;

        buffer += decoded;
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;

          console.log("[chat-ui] NDJSON line:", line);

          try {
            const event = JSON.parse(line);
            console.log("[chat-ui] Parsed event — type:", event.type, "subtype:", event.subtype ?? "(none)", "session_id:", event.session_id ?? "(none)");

            // Extract session_id from initial result message
            if (event.type === "result" && event.session_id) {
              console.log("[chat-ui] Captured session_id:", event.session_id);
              setSessionId(event.session_id);
            }

            // Handle stream events
            if (event.type === "assistant" && event.message) {
              const textBlocks = (event.message.content || [])
                .filter((b: { type: string }) => b.type === "text")
                .map((b: { text: string }) => b.text)
                .join("");
              if (textBlocks) {
                if (!firstTextReceived) {
                  firstTextReceived = true;
                  setHamsterState("talking");
                }
                // Estimate tokens (~4 chars per token)
                setEstimatedTokens(Math.ceil(textBlocks.length / 4));
                finalAssistantText = textBlocks;
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last?.role === "assistant") {
                    updated[updated.length - 1] = { ...last, content: textBlocks };
                  }
                  return updated;
                });

                // Detect completed sentences and enqueue TTS
                const { sentences, newIndex } = extractSentences(textBlocks, ttsSentIndexRef.current);
                ttsSentIndexRef.current = newIndex;
                for (const sentence of sentences) {
                  enqueueTTS(sentence);
                }
              }

              const toolBlocks = (event.message.content || [])
                .filter((b: { type: string }) => b.type === "tool_use");
              if (toolBlocks.length > 0) {
                const lastTool = toolBlocks[toolBlocks.length - 1];
                currentToolName = lastTool.name || "tool";
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last?.role === "assistant") {
                    updated[updated.length - 1] = {
                      ...last,
                      toolUse: `Using ${currentToolName}...`,
                    };
                  }
                  return updated;
                });
              }
            }

            // Result event
            if (event.type === "result") {
              if (event.session_id) {
                setSessionId(event.session_id);
              }
              const resultText = (event.result || "").toString();
              if (resultText) {
                if (!firstTextReceived) {
                  firstTextReceived = true;
                  setHamsterState("talking");
                }
                finalAssistantText = resultText;
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last?.role === "assistant") {
                    updated[updated.length - 1] = {
                      ...last,
                      content: resultText,
                      toolUse: undefined,
                    };
                  }
                  return updated;
                });
                // Flush TTS buffer + any remaining text that wasn't a complete sentence
                const remaining = resultText.slice(ttsSentIndexRef.current).trim();
                const finalChunk = (ttsBufferRef.current + (remaining ? " " + remaining : "")).trim();
                ttsBufferRef.current = "";
                if (finalChunk) enqueueTTS(finalChunk);
              }
              gotResult = true;
            }
          } catch (parseErr) {
            console.warn("[chat-ui] Failed to parse NDJSON line:", line, "error:", parseErr);
          }
        }

        // Once we have the result, stop waiting for the stream to close
        if (gotResult) {
          console.log("[chat-ui] Got result event — closing reader");
          reader.cancel();
          break;
        }
      }

      // Flush any remaining content in the buffer (last line without trailing newline)
      if (buffer.trim()) {
        console.log("[chat-ui] Flushing remaining buffer:", buffer);
        try {
          const event = JSON.parse(buffer);
          console.log("[chat-ui] Flushed event — type:", event.type);

          if (event.type === "result") {
            if (event.session_id) {
              console.log("[chat-ui] Captured session_id from buffer flush:", event.session_id);
              setSessionId(event.session_id);
            }
            const resultText = (event.result || "").toString();
            if (resultText) {
              if (!firstTextReceived) {
                firstTextReceived = true;
                setHamsterState("talking");
              }
              finalAssistantText = resultText;
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last?.role === "assistant") {
                  updated[updated.length - 1] = {
                    ...last,
                    content: resultText,
                    toolUse: undefined,
                  };
                }
                return updated;
              });
              const remaining = resultText.slice(ttsSentIndexRef.current).trim();
              const finalChunk = (ttsBufferRef.current + (remaining ? " " + remaining : "")).trim();
              ttsBufferRef.current = "";
              if (finalChunk) enqueueTTS(finalChunk);
            }
          }
        } catch (parseErr) {
          console.warn("[chat-ui] Failed to parse remaining buffer:", buffer, "error:", parseErr);
        }
      }

      console.log("[chat-ui] Stream processing complete");

      // Update token count with final text
      if (finalAssistantText) {
        const responseTokens = Math.ceil(finalAssistantText.length / 4);
        setEstimatedTokens(responseTokens);
        setSessionTokens((prev) => prev + responseTokens);
      }

      // Log assistant response to session file
      if (finalAssistantText) {
        logToSession("assistant", finalAssistantText);
      }
    } catch (err) {
      console.error("[chat-ui] Chat error:", err);
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last?.role === "assistant" && !last.content) {
          updated[updated.length - 1] = {
            ...last,
            content: "Sorry, something went wrong. Make sure Claude CLI is installed and available.",
          };
        }
        return updated;
      });
    } finally {
      abortRef.current = null;
      setIsStreaming(false);
      // Sync ref immediately so playNextTTS sees the correct value (useEffect is async)
      isStreamingRef.current = false;
      // Only go idle if TTS isn't active or pending — otherwise playNextTTS handles it
      if (!ttsEnabledRef.current || (!ttsPlayingRef.current && ttsQueueRef.current.length === 0 && ttsPendingRef.current === 0)) {
        setHamsterState("idle");
      }
    }
  };

  const stopStreaming = () => {
    console.log("[chat-ui] User interrupted streaming");
    abortRef.current?.abort();
    flushTTS(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-400">Chat with Ari</h2>
        <button
          onClick={() => {
            const newVal = !ttsEnabledRef.current;
            ttsEnabledRef.current = newVal; // Update ref immediately
            setTtsEnabled(newVal);
            if (!newVal) flushTTS(true);
          }}
          className={`px-2 py-1 rounded text-xs transition-colors ${
            ttsEnabled
              ? "bg-zinc-700 text-zinc-200"
              : "bg-zinc-800 text-zinc-500"
          }`}
          title={ttsEnabled ? "Mute Ari's voice" : "Unmute Ari's voice"}
        >
          {ttsEnabled ? "🔊" : "🔇"}
        </button>
      </div>

      {/* Messages */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-4 chat-scroll"
      >
        {/* Loading indicator at top */}
        {loadingHistory && (
          <div className="flex justify-center py-2">
            <span className="text-xs text-zinc-500 animate-pulse">Loading history...</span>
          </div>
        )}

        {/* Past sessions */}
        {historySessions.map((session) => (
          <div key={session.filename}>
            {/* Session divider */}
            <div className="flex items-center gap-3 my-4">
              <div className="flex-1 border-t border-zinc-700" />
              <span className="text-xs text-zinc-500 whitespace-nowrap">
                {session.date}
              </span>
              <div className="flex-1 border-t border-zinc-700" />
            </div>
            {/* Session messages */}
            {session.messages.map((msg, j) => (
              <div
                key={`${session.filename}-${j}`}
                className={`flex mb-4 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                    msg.role === "user"
                      ? "bg-zinc-700 text-zinc-100"
                      : "bg-zinc-800/50 text-zinc-200"
                  }`}
                >
                  {renderContent(msg.content)}
                </div>
              </div>
            ))}
          </div>
        ))}

        {/* Current session divider (only show if we have history loaded) */}
        {historySessions.length > 0 && messages.length > 0 && (
          <div className="flex items-center gap-3 my-4">
            <div className="flex-1 border-t border-zinc-700" />
            <span className="text-xs text-zinc-500 whitespace-nowrap">Now</span>
            <div className="flex-1 border-t border-zinc-700" />
          </div>
        )}

        {/* Current messages */}
        {messages.length === 0 && historySessions.length === 0 && (
          <div className="flex items-center justify-center h-full text-zinc-600 text-sm">
            Say hi to Ari!
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-zinc-700 text-zinc-100"
                  : "bg-zinc-800/50 text-zinc-200"
              }`}
            >
              {renderContent(msg.content)}
              {msg.toolUse && (
                <div className="mt-1 text-xs text-zinc-500 italic">{msg.toolUse}</div>
              )}
              {msg.role === "assistant" && !msg.content && isStreaming && (
                <span className="text-zinc-500 animate-pulse">...</span>
              )}
            </div>
          </div>
        ))}
        {/* Live voice transcription bubble */}
        {(isRecording || isTranscribing) && (
          <div className="flex justify-end">
            <div className="max-w-[85%] rounded-lg px-3 py-2 text-sm bg-zinc-700 text-zinc-100">
              {isRecording && (
                <span className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse flex-shrink-0" />
                  <span>{liveTranscript || "Listening..."}</span>
                </span>
              )}
              {isTranscribing && !isRecording && (
                <span className="text-amber-400 animate-pulse">Transcribing...</span>
              )}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} className="h-12 shrink-0" />
      </div>

      {/* Token counter */}
      {(isStreaming || estimatedTokens > 0) && (
        <div className="px-3 py-1 border-t border-zinc-800/50 flex justify-between"
             style={{ fontFamily: "monospace", fontVariantNumeric: "tabular-nums" }}>
          <span className="text-[10px] text-zinc-600">
            {isStreaming ? "~" : ""}{estimatedTokens.toLocaleString()} tokens
          </span>
          {sessionTokens > 0 && (
            <span className="text-[10px] text-zinc-600">
              session: {sessionTokens.toLocaleString()}
            </span>
          )}
        </div>
      )}

      {/* Webcam modal */}
      {showWebcam && (
        <WebcamCapture
          onCapture={(file) => {
            addFiles([file]);
            setShowWebcam(false);
          }}
          onClose={() => setShowWebcam(false)}
        />
      )}

      {/* Input area */}
      <div className="p-3 border-t border-zinc-800">
        {/* Thumbnail previews */}
        {previewUrls.length > 0 && (
          <div className="flex gap-2 mb-2 flex-wrap">
            {previewUrls.map((url, i) => (
              <div key={i} className="relative group">
                <img
                  src={url}
                  alt={`Attachment ${i + 1}`}
                  className="h-16 w-16 object-cover rounded-lg border border-zinc-700"
                />
                <button
                  onClick={() => removeFile(i)}
                  className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-zinc-600 text-zinc-200
                             rounded-full text-xs flex items-center justify-center
                             opacity-0 group-hover:opacity-100 transition-opacity
                             hover:bg-red-500"
                >
                  x
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files) addFiles(e.target.files);
            e.target.value = "";
          }}
        />

        {/* Input row with drag-and-drop */}
        <div
          className="flex gap-2"
          onDragOver={(e) => {
            e.preventDefault();
            e.stopPropagation();
          }}
          onDrop={(e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.dataTransfer.files) addFiles(e.dataTransfer.files);
          }}
        >
          {/* Attach button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-2 py-2 bg-zinc-800 text-zinc-400 rounded-lg text-sm
                       hover:bg-zinc-700 hover:text-zinc-200 transition-colors"
            title="Attach image"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
            </svg>
          </button>

          {/* Camera button */}
          <button
            onClick={() => setShowWebcam(true)}
            className="px-2 py-2 bg-zinc-800 text-zinc-400 rounded-lg text-sm
                       hover:bg-zinc-700 hover:text-zinc-200 transition-colors"
            title="Take photo"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
              <circle cx="12" cy="13" r="4" />
            </svg>
          </button>

          {/* Mic button */}
          <button
            onClick={toggleRecording}
            disabled={isTranscribing}
            className={`px-2 py-2 rounded-lg text-sm transition-colors ${
              isRecording
                ? "bg-red-600 text-white animate-pulse"
                : isTranscribing
                ? "bg-zinc-800 text-amber-400"
                : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
            }`}
            title={isRecording ? "Stop & send" : isTranscribing ? "Transcribing..." : "Voice input"}
          >
            {isTranscribing ? (
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill={isRecording ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            )}
          </button>

          {/* Cancel recording button — only visible while recording */}
          {isRecording && (
            <button
              onClick={cancelRecording}
              className="px-2 py-2 rounded-lg text-sm bg-zinc-800 text-zinc-400
                         hover:bg-zinc-700 hover:text-red-400 transition-colors"
              title="Cancel recording"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          )}

          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder="Message Ari..."
            rows={1}
            className="flex-1 bg-zinc-800 text-zinc-100 rounded-lg px-3 py-2 text-sm
                       resize-none placeholder-zinc-500 chat-input
                       focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />

          {isStreaming ? (
            <button
              onClick={stopStreaming}
              className="px-4 py-2 bg-red-700 text-zinc-200 rounded-lg text-sm
                         hover:bg-red-600 transition-colors"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() && attachedFiles.length === 0}
              className="px-4 py-2 bg-zinc-700 text-zinc-200 rounded-lg text-sm
                         hover:bg-zinc-600 disabled:opacity-40 disabled:cursor-not-allowed
                         transition-colors"
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
