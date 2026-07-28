"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useStatus } from "@/lib/StatusContext";
import { useChat } from "@/lib/ChatContext";
import type { Conversation, ChatToolEvent, ChatUiMessage } from "@/types";
import { SectionCard, ModelSelect } from "@/components/shared";
import {
  MessageSquare,
  Plus,
  Send,
  Square,
  Sparkles,
  Trash2,
} from "lucide-react";

const SUGGESTED_PROMPTS = [
  "What do you know about this project?",
  "Summarize the wiki",
  "Search for specific files",
  "Explain the codebase",
];

export function ChatTab() {
  const { model } = useStatus();
  const {
    conversations,
    activeId,
    active,
    loading,
    streamingId,
    pendingTools,
    error,
    send,
    stop,
    newChat,
    selectChat,
    deleteChat,
  } = useChat();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const messages = active?.messages ?? [];
  const streamingHere = streamingId !== null && streamingId === activeId;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    // Depend on `active?.messages`, not the `?? []` fallback above: that literal
    // is a new array every render and would re-run this on each one.
  }, [active?.messages, pendingTools, streamingHere, activeId]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || !model || loading) return;
    setInput("");
    void send(trimmed, model);
  };

  return (
    <div className="space-y-4">
      <SectionCard title="Chat">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <ModelSelect value={model} />
          <div className="flex items-end justify-end">
            <button
              onClick={newChat}
              disabled={activeId === null}
              className="px-3 py-2 bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded-lg text-sm font-medium disabled:opacity-50 transition-colors duration-150 ease-out flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              New chat
            </button>
          </div>
        </div>

        <div className="flex gap-3 h-[28rem]">
          <HistoryRail
            conversations={conversations}
            activeId={activeId}
            streamingId={streamingId}
            onSelect={selectChat}
            onDelete={deleteChat}
          />

          <div
            ref={scrollRef}
            className="flex-1 min-w-0 overflow-y-auto bg-zinc-50 rounded-lg p-3 space-y-3 border border-zinc-200"
          >
            {messages.length === 0 && !streamingHere && (
              <div className="flex flex-col items-center justify-center h-full text-center py-8">
                <MessageSquare className="w-10 h-10 text-zinc-300 mb-3" />
                <p className="text-sm text-zinc-500 mb-4">Ask about anything in this project — files, code, the wiki, or the raw sources.</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
                  {SUGGESTED_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => setInput(prompt)}
                      disabled={loading || !model}
                      className="text-left px-3 py-2 bg-white border border-zinc-200 rounded-lg text-xs text-zinc-600 hover:border-violet-300 hover:text-violet-700 hover:bg-violet-50 disabled:opacity-50 transition-colors duration-150 ease-out"
                    >
                      <Sparkles className="w-3 h-3 inline mr-1 text-zinc-400" />
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <MessageBubble key={i} msg={m} />
            ))}

            {streamingHere && (
              <div className="space-y-2">
                {pendingTools.map((t, i) => (
                  <ToolBlock key={i} tool={t} />
                ))}
                {/* Skeleton loading placeholder */}
                <div className="space-y-2 animate-pulse">
                  <div className="h-3 bg-zinc-200 rounded w-3/4" />
                  <div className="h-3 bg-zinc-200 rounded w-1/2" />
                  <div className="h-3 bg-zinc-200 rounded w-5/6" />
                </div>
              </div>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
            {error}
          </div>
        )}

        {loading && !streamingHere && (
          <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
            A reply is still coming in on another conversation.
          </div>
        )}

        <div className="mt-3 flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask the agent anything about this project…"
            rows={2}
            className="flex-1 px-3 py-2 border border-zinc-300 rounded-lg text-sm focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition-colors duration-150 ease-out"
          />
          {loading ? (
            <button
              onClick={stop}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors duration-150 ease-out flex items-center gap-1.5"
            >
              <Square className="w-3.5 h-3.5" />
              Stop
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim() || !model}
              className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors duration-150 ease-out flex items-center gap-1.5"
            >
              <Send className="w-3.5 h-3.5" />
              Send
            </button>
          )}
        </div>
      </SectionCard>
    </div>
  );
}

/* ── History rail ───────────────────────────────────────────── */

function dayGroup(ts: number): string {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const dayStart = start.getTime();
  if (ts >= dayStart) return "Today";
  if (ts >= dayStart - 86_400_000) return "Yesterday";
  return "Earlier";
}

function HistoryRail({
  conversations,
  activeId,
  streamingId,
  onSelect,
  onDelete,
}: {
  conversations: Conversation[];
  activeId: string | null;
  streamingId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [confirmId, setConfirmId] = useState<string | null>(null);

  // `conversations` arrives newest-first, so groups come out in order too.
  const groups: Array<[string, Conversation[]]> = [];
  for (const c of conversations) {
    const label = dayGroup(c.updatedAt);
    const last = groups[groups.length - 1];
    if (last && last[0] === label) last[1].push(c);
    else groups.push([label, [c]]);
  }

  return (
    <div className="w-52 shrink-0 overflow-y-auto bg-zinc-50 rounded-lg border border-zinc-200 p-2 space-y-3">
      {conversations.length === 0 && (
        <p className="text-xs text-zinc-400 text-center py-4">No saved chats yet</p>
      )}

      {groups.map(([label, items]) => (
        <div key={label}>
          <div className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
            {label}
          </div>
          <div className="space-y-0.5">
            {items.map((c) => {
              const isActive = c.id === activeId;
              const isConfirming = c.id === confirmId;
              return (
                <div
                  key={c.id}
                  className={`group flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs transition-colors duration-150 ease-out ${
                    isActive
                      ? "bg-violet-100 text-violet-900"
                      : "text-zinc-600 hover:bg-zinc-200/70"
                  }`}
                >
                  {isConfirming ? (
                    <>
                      <span className="flex-1 truncate text-red-700">Delete?</span>
                      <button
                        onClick={() => {
                          onDelete(c.id);
                          setConfirmId(null);
                        }}
                        className="px-1.5 py-0.5 rounded bg-red-600 text-white text-[10px] font-medium hover:bg-red-700 transition-colors duration-150 ease-out"
                      >
                        Yes
                      </button>
                      <button
                        onClick={() => setConfirmId(null)}
                        className="px-1.5 py-0.5 rounded bg-zinc-200 text-zinc-700 text-[10px] font-medium hover:bg-zinc-300 transition-colors duration-150 ease-out"
                      >
                        No
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => onSelect(c.id)}
                        title={c.title}
                        className="flex-1 min-w-0 truncate text-left"
                      >
                        {c.title}
                      </button>
                      {c.id === streamingId && (
                        <span className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse shrink-0" />
                      )}
                      <button
                        onClick={() => setConfirmId(c.id)}
                        aria-label={`Delete chat "${c.title}"`}
                        className="opacity-0 group-hover:opacity-100 focus:opacity-100 text-zinc-400 hover:text-red-600 transition-colors duration-150 ease-out"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function MessageBubble({ msg }: { msg: ChatUiMessage }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-violet-600 text-white px-3 py-2 rounded-lg text-sm whitespace-pre-wrap transition-colors duration-150 ease-out">
          {msg.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      {msg.tools?.map((t, i) => (
        <ToolBlock key={i} tool={t} />
      ))}
      <div className="max-w-[90%] bg-white border border-zinc-200 px-3 py-2 rounded-lg text-sm prose prose-zinc prose-sm max-w-none transition-colors duration-150 ease-out">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
      </div>
    </div>
  );
}

function ToolBlock({ tool }: { tool: ChatToolEvent }) {
  const argsStr = tool.args ? JSON.stringify(tool.args) : "";
  return (
    <details className="bg-amber-50 border border-amber-200 rounded-lg text-xs transition-colors duration-150 ease-out">
      <summary className="px-3 py-1.5 cursor-pointer font-mono text-amber-900">
        {tool.name}
        {argsStr && <span className="text-amber-700">({argsStr.slice(0, 120)}{argsStr.length > 120 ? "…" : ""})</span>}
      </summary>
      {tool.result !== undefined && (
        <pre className="px-3 pb-2 pt-1 whitespace-pre-wrap text-amber-900/80 max-h-64 overflow-auto">
          {tool.result}
        </pre>
      )}
    </details>
  );
}
