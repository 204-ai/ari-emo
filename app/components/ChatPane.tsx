"use client";

import { useEffect, useRef, useState } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
  toolUse?: string;
  images?: string[];
}

/** Parse message content, rendering ![alt](url) as actual images. */
function renderContent(content: string) {
  const parts = content.split(/(!\[[^\]]*\]\([^)]+\))/g);
  if (parts.length === 1) return content;

  return parts.map((part, i) => {
    const match = part.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
    if (match) {
      return (
        <img
          key={i}
          src={match[2]}
          alt={match[1]}
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

export default function ChatPane() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
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
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const ttsEnabledRef = useRef(true);
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);
  const ttsQueueRef = useRef<{ url: string; audio: HTMLAudioElement }[]>([]);
  const ttsPlayingRef = useRef(false);
  const ttsSentIndexRef = useRef(0);
  const ttsChainRef = useRef<Promise<void>>(Promise.resolve());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Cleanup preview URLs on unmount
  useEffect(() => {
    return () => {
      previewUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

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

        const transcript = liveTranscriptRef.current.trim();

        // If Web Speech API gave us text, auto-send it directly
        if (hasSpeechAPIRef.current && transcript) {
          updateLiveTranscript("");
          sendMessage(transcript);
          return;
        }

        // Fallback: transcribe via Whisper server, then auto-send
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
            sendMessage(data.text);
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
        (window as unknown as { SpeechRecognition?: typeof SpeechRecognition }).SpeechRecognition ||
        (window as unknown as { webkitSpeechRecognition?: typeof SpeechRecognition }).webkitSpeechRecognition;

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

  const toggleRecording = () => {
    if (isRecording) stopRecording();
    else startRecording();
  };

  // ── TTS playback (sentence-chunked queue) ────────────────────────

  // Keep ref in sync with state so async callbacks see current value
  useEffect(() => { ttsEnabledRef.current = ttsEnabled; }, [ttsEnabled]);

  /** Play the next queued audio clip. Calls itself on `ended`. */
  const playNextTTS = () => {
    if (!ttsEnabledRef.current) {
      // TTS was disabled — drain queue
      for (const item of ttsQueueRef.current) URL.revokeObjectURL(item.url);
      ttsQueueRef.current = [];
      ttsPlayingRef.current = false;
      return;
    }

    const next = ttsQueueRef.current.shift();
    if (!next) {
      ttsPlayingRef.current = false;
      ttsAudioRef.current = null;
      return;
    }

    ttsPlayingRef.current = true;
    ttsAudioRef.current = next.audio;
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
    ttsChainRef.current = ttsChainRef.current.then(async () => {
      const result = await audioPromise;
      if (!result || !ttsEnabledRef.current) return;

      ttsQueueRef.current.push(result);
      if (!ttsPlayingRef.current) playNextTTS();
    });
  };

  /** Extract completed sentences from new text beyond sentIndex. */
  const extractSentences = (fullText: string, sentIndex: number): { sentences: string[]; newIndex: number } => {
    const newText = fullText.slice(sentIndex);
    const sentences: string[] = [];
    // Match sentences ending with . ! ? followed by space/newline, or end of a line
    const re = /[^.!?\n]*[.!?](?=\s|$)|[^\n]+\n/g;
    let match: RegExpExecArray | null;
    let lastEnd = 0;

    while ((match = re.exec(newText)) !== null) {
      const sentence = match[0].trim();
      if (sentence) sentences.push(sentence);
      lastEnd = match.index + match[0].length;
    }

    return { sentences, newIndex: sentIndex + lastEnd };
  };

  /** Stop all TTS playback and clear the queue. */
  const flushTTS = () => {
    if (ttsAudioRef.current) {
      ttsAudioRef.current.onended = null;
      ttsAudioRef.current.onerror = null;
      ttsAudioRef.current.pause();
      ttsAudioRef.current = null;
    }
    for (const item of ttsQueueRef.current) URL.revokeObjectURL(item.url);
    ttsQueueRef.current = [];
    ttsPlayingRef.current = false;
    ttsSentIndexRef.current = 0;
    ttsChainRef.current = Promise.resolve();
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

    const messageText = text || "(shared an image)";

    // Add user message with image previews
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: messageText,
        images: previewsToSend.length > 0 ? previewsToSend : undefined,
      },
    ]);

    // Add empty assistant message to stream into
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    // Reset TTS sentence tracking for new response
    flushTTS();

    try {
      // Upload files first
      let imagePaths: string[] | undefined;
      if (filesToSend.length > 0) {
        const uploadResults = await uploadFiles(filesToSend);
        imagePaths = uploadResults.map((r) => r.absolutePath);
      }

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
                // Enqueue any remaining text that wasn't a complete sentence
                const remaining = resultText.slice(ttsSentIndexRef.current).trim();
                if (remaining) enqueueTTS(remaining);
              }
            }
          } catch (parseErr) {
            console.warn("[chat-ui] Failed to parse NDJSON line:", line, "error:", parseErr);
          }
        }
      }

      console.log("[chat-ui] Stream processing complete");
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
    }
  };

  const stopStreaming = () => {
    console.log("[chat-ui] User interrupted streaming");
    abortRef.current?.abort();
    flushTTS();
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
            setTtsEnabled((v) => !v);
            flushTTS();
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
      <div className="flex-1 overflow-y-auto p-4 space-y-4 chat-scroll">
        {messages.length === 0 && (
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
              {/* User-attached images */}
              {msg.images && msg.images.length > 0 && (
                <div className="flex gap-2 flex-wrap mb-2">
                  {msg.images.map((url, j) => (
                    <img
                      key={j}
                      src={url}
                      alt={`Attached ${j + 1}`}
                      className="rounded-lg max-w-full"
                      style={{ maxHeight: 200 }}
                    />
                  ))}
                </div>
              )}
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
        <div ref={messagesEndRef} />
      </div>

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
            title={isRecording ? "Stop recording" : isTranscribing ? "Transcribing..." : "Voice input"}
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
              onClick={sendMessage}
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
