"use client";

import { useState, useEffect, useCallback, useRef } from "react";
// expanded state is now controlled by parent (accordion)

interface TelegramMessage {
  id: number;
  timestamp: string;
  chatId: number;
  chatTitle: string;
  userName: string;
  userMessage: string;
  ariResponse: string;
  hasMedia: boolean;
}

interface TelegramPaneProps {
  expanded: boolean;
  onToggle: () => void;
}

export default function TelegramPane({ expanded, onToggle }: TelegramPaneProps) {
  const [messages, setMessages] = useState<TelegramMessage[]>([]);
  const [lastId, setLastId] = useState(0);
  const [unread, setUnread] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  const fetchMessages = useCallback(() => {
    const url = lastId > 0
      ? `/api/telegram?since=${lastId}`
      : "/api/telegram?limit=20";

    fetch(url)
      .then((r) => r.json())
      .then((data) => {
        if (data.messages && data.messages.length > 0) {
          setMessages((prev) => {
            const combined = [...prev, ...data.messages];
            // Keep last 100
            return combined.slice(-100);
          });
          setLastId(data.lastId);
          if (!expanded) {
            setUnread((prev) => prev + data.messages.length);
          }
        }
      })
      .catch(() => {});
  }, [lastId, expanded]);

  useEffect(() => {
    fetchMessages();
    const interval = setInterval(fetchMessages, 3000);
    return () => clearInterval(interval);
  }, [fetchMessages]);

  useEffect(() => {
    if (expanded) {
      setUnread(0);
      // Auto-scroll to bottom
      setTimeout(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
      }, 50);
    }
  }, [expanded, messages.length]);

  const formatTime = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  const truncate = (text: string, max: number) =>
    text.length > max ? text.slice(0, max) + "..." : text;

  return (
    <div className="w-full px-4">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-3 py-2 rounded-lg
                   bg-zinc-800/50 hover:bg-zinc-800 transition-colors text-sm"
      >
        <span className="text-zinc-400 font-medium flex items-center gap-2">
          <span className="text-base">💬</span>
          Telegram
          {messages.length > 0 && (
            <span className="text-zinc-600">({messages.length})</span>
          )}
          {unread > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-900/40 text-blue-400 animate-pulse">
              {unread} new
            </span>
          )}
        </span>
        <span
          className="text-zinc-500 transition-transform duration-200"
          style={{ transform: expanded ? "rotate(180deg)" : "rotate(0deg)" }}
        >
          {"\u25B4"}
        </span>
      </button>

      {expanded && (
        <div
          ref={scrollRef}
          className="mt-2 max-h-64 overflow-y-auto space-y-2 scrollbar-thin scrollbar-thumb-zinc-700"
        >
          {messages.length === 0 ? (
            <div className="text-center text-zinc-600 text-xs py-4">
              No messages yet. Talk to @ari_rna_bot on Telegram!
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className="px-3 py-2 rounded-lg bg-zinc-800/30 hover:bg-zinc-800/60 transition-colors"
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-blue-400 font-medium">
                      {msg.userName}
                    </span>
                    {msg.chatTitle !== "DM" && (
                      <span className="text-[10px] text-zinc-600">
                        in {msg.chatTitle}
                      </span>
                    )}
                    {msg.hasMedia && (
                      <span className="text-[10px]" title="Has media">
                        📎
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-zinc-600">
                    {formatTime(msg.timestamp)}
                  </span>
                </div>

                {/* User message */}
                <p className="text-[11px] text-zinc-400 leading-tight">
                  {truncate(msg.userMessage, 120)}
                </p>

                {/* Ari response */}
                {msg.ariResponse && (
                  <p className="text-[11px] text-zinc-300 leading-tight mt-1 pl-2 border-l border-zinc-700">
                    {truncate(msg.ariResponse, 200)}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
