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
  const abortRef = useRef<AbortController | null>(null);
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

  // ── Send message ──────────────────────────────────────────────────

  const sendMessage = async () => {
    const text = input.trim();
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
      <div className="px-4 py-3 border-b border-zinc-800">
        <h2 className="text-sm font-semibold text-zinc-400">Chat with Ari</h2>
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
