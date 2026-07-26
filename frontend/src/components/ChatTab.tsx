"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, type ChatEvent } from "@/lib/api";
import { useStatus } from "@/lib/StatusContext";
import { SectionCard, ModelSelect } from "@/components/shared";
import {
  MessageSquare,
  Send,
  Square,
  Sparkles,
} from "lucide-react";

type Role = "user" | "assistant" | "tool";

interface ToolEvent {
  name: string;
  args?: Record<string, unknown>;
  result?: string;
}

interface UiMessage {
  role: Role;
  content: string;
  tools?: ToolEvent[];
}

interface WireMessage {
  role: string;
  content?: string | null;
  tool_call_id?: string;
  name?: string;
  tool_calls?: unknown;
}

const SUGGESTED_PROMPTS = [
  "What do you know about this project?",
  "Summarize the wiki",
  "Search for specific files",
  "Explain the codebase",
];

export function ChatTab() {
  const { model } = useStatus();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [wire, setWire] = useState<WireMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [pendingTools, setPendingTools] = useState<ToolEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, pendingTools, loading]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || !model || loading) return;

    setError(null);
    setInput("");

    const newUserUi: UiMessage = { role: "user", content: trimmed };
    const newUserWire: WireMessage = { role: "user", content: trimmed };
    const nextUi = [...messages, newUserUi];
    const nextWire = [...wire, newUserWire];
    setMessages(nextUi);
    setWire(nextWire);
    setLoading(true);
    setPendingTools([]);

    const collectedTools: ToolEvent[] = [];
    let assistantText = "";

    const { promise, abort } = api.chatStream(
      { messages: nextWire, model, temperature: 0.3, max_iters: 1000 },
      (ev: ChatEvent) => {
        if (ev.type === "tool_call") {
          collectedTools.push({ name: ev.name, args: ev.args });
          setPendingTools([...collectedTools]);
        } else if (ev.type === "tool_result") {
          const last = collectedTools[collectedTools.length - 1];
          if (last && last.name === ev.name && last.result === undefined) {
            last.result = ev.result;
          } else {
            collectedTools.push({ name: ev.name, result: ev.result });
          }
          setPendingTools([...collectedTools]);
        } else if (ev.type === "content") {
          assistantText = ev.text;
        } else if (ev.type === "error") {
          setError(ev.message);
        }
      },
    );
    abortRef.current = abort;

    try {
      await promise;
    } catch (e) {
      setError(String(e));
    } finally {
      const assistantUi: UiMessage = {
        role: "assistant",
        content: assistantText || "(no response)",
        tools: collectedTools.length ? collectedTools : undefined,
      };
      const assistantWire: WireMessage = { role: "assistant", content: assistantText };

      setMessages([...nextUi, assistantUi]);
      setWire([...nextWire, assistantWire]);
      setPendingTools([]);
      setLoading(false);
      abortRef.current = null;
    }
  };

  const handleStop = () => {
    abortRef.current?.();
    abortRef.current = null;
    setLoading(false);
  };

  const handleClear = () => {
    if (loading) return;
    setMessages([]);
    setWire([]);
    setError(null);
  };

  const handlePromptClick = (prompt: string) => {
    setInput(prompt);
  };

  return (
    <div className="space-y-4">
      <SectionCard title="Chat">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <ModelSelect value={model} />
          <div className="flex items-end justify-end">
            <button
              onClick={handleClear}
              disabled={loading || messages.length === 0}
              className="px-3 py-2 bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded-lg text-sm font-medium disabled:opacity-50 transition-colors duration-150 ease-out"
            >
              Clear conversation
            </button>
          </div>
        </div>

        <div
          ref={scrollRef}
          className="h-[28rem] overflow-y-auto bg-zinc-50 rounded-lg p-3 space-y-3 border border-zinc-200"
        >
          {messages.length === 0 && !loading && (
            <div className="flex flex-col items-center justify-center h-full text-center py-8">
              <MessageSquare className="w-10 h-10 text-zinc-300 mb-3" />
              <p className="text-sm text-zinc-500 mb-4">Ask about anything in this project — files, code, the wiki, or the raw sources.</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => handlePromptClick(prompt)}
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

          {loading && (
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

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
            {error}
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
              onClick={handleStop}
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

function MessageBubble({ msg }: { msg: UiMessage }) {
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

function ToolBlock({ tool }: { tool: ToolEvent }) {
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
