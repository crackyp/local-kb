"use client";

import { useState } from "react";
import type { View } from "@/types";
import { useStatus } from "@/lib/StatusContext";
import { useCompile } from "@/lib/CompileContext";
import { StatusBadge, ModelSelect } from "@/components/shared";
import { api } from "@/lib/api";

const NAV_ITEMS: { id: View; label: string }[] = [
  { id: "explorer", label: "Explorer" },
  { id: "ask", label: "Ask" },
  { id: "chat", label: "Chat" },
  { id: "ingest", label: "Ingest" },
  { id: "compile", label: "Compile" },
  { id: "quality", label: "Quality" },
];

interface SidebarProps {
  activeView: View;
  onNavigate: (view: View) => void;
}

export function Sidebar({ activeView, onNavigate }: SidebarProps) {
  const { status, refresh, model } = useStatus();
  const { compiling, stopCompile } = useCompile();
  const [loadingModel, setLoadingModel] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadedModel = status?.llamacpp.loaded;
  const selectedMatchesLoaded = !!loadedModel && model === loadedModel;

  const handleLoad = async () => {
    if (!model || loadingModel) return;
    setLoadingModel(true);
    setLoadError(null);
    try {
      await api.loadModel(model);
      await refresh();
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingModel(false);
    }
  };

  return (
    <aside className="w-56 min-h-screen bg-slate-900 text-slate-100 flex flex-col">
      <div className="p-4 border-b border-slate-700">
        <h1 className="text-lg font-bold text-white">Knowledge Based</h1>
        <p className="text-xs text-slate-400 mt-0.5">The Knowledge Mutilator</p>
      </div>

      <nav className="p-2 border-b border-slate-700">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors mb-0.5 ${
              activeView === item.id
                ? "bg-blue-600 text-white"
                : "text-slate-300 hover:bg-slate-800 hover:text-white"
            }`}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className="p-4 flex-1 overflow-y-auto space-y-3">
        <div className="p-3 rounded-lg bg-slate-800/50">
          <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">llama.cpp</div>
          <StatusBadge value={status?.llamacpp.running ? "running" : "not_running"} />
          {status?.llamacpp.running && loadedModel && (
            <div className="mt-2 text-xs text-slate-300 break-all">
              <span className="text-slate-500">loaded:</span> {loadedModel}
            </div>
          )}
          <div className="mt-3">
            <ModelSelect label="Selected model" />
          </div>
          {status?.llamacpp.running && (
            <button
              onClick={handleLoad}
              disabled={!model || loadingModel || selectedMatchesLoaded}
              className="mt-2 w-full px-2 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-400 disabled:cursor-not-allowed rounded text-xs font-medium text-white transition-colors"
              title={
                selectedMatchesLoaded
                  ? "Selected model is already loaded"
                  : "Force llama-swap to load the selected model now"
              }
            >
              {loadingModel
                ? "Loading…"
                : selectedMatchesLoaded
                ? "Already loaded"
                : "Load now"}
            </button>
          )}
          {loadError && (
            <div className="mt-2 text-xs text-red-400 break-words">{loadError}</div>
          )}
        </div>

        <div className="p-3 rounded-lg bg-slate-800/50">
          <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">FAISS Index</div>
          <StatusBadge value={status?.faiss ?? "unknown"} />
        </div>

        {compiling && (
          <div className="p-3 rounded-lg bg-blue-950/60 border border-blue-800">
            <div className="text-xs text-blue-300 uppercase tracking-wide mb-1">Compile Job</div>
            <div className="text-sm text-blue-100 mb-3">Running in background while you browse.</div>
            <div className="flex gap-2">
              <button
                onClick={() => onNavigate("compile")}
                className="flex-1 px-3 py-2 bg-blue-700 hover:bg-blue-600 rounded-lg text-sm transition-colors"
              >
                Open
              </button>
              <button
                onClick={stopCompile}
                className="px-3 py-2 bg-red-700 hover:bg-red-600 rounded-lg text-sm transition-colors"
              >
                Stop
              </button>
            </div>
          </div>
        )}

        <div className="border-t border-slate-700 pt-3 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-slate-400">Raw files</span>
            <span className="font-medium">{status?.files.raw ?? "—"}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-400">Wiki pages</span>
            <span className="font-medium">{status?.files.wiki ?? "—"}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-400">Outputs</span>
            <span className="font-medium">{status?.files.outputs ?? "—"}</span>
          </div>
        </div>
      </div>

      <div className="p-3 border-t border-slate-700">
        <button
          onClick={refresh}
          className="w-full px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm transition-colors"
        >
          Refresh
        </button>
      </div>
    </aside>
  );
}
