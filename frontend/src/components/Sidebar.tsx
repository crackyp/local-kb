"use client";

import { useState, useEffect } from "react";
import type { View } from "@/types";
import { useStatus } from "@/lib/StatusContext";
import { useCompile } from "@/lib/CompileContext";
import { StatusBadge, ModelSelect } from "@/components/shared";
import { api } from "@/lib/api";

const NAV_ITEMS: { id: View; label: string }[] = [
  { id: "explorer", label: "Explorer" },
  { id: "chat", label: "Chat" },
  { id: "ingest", label: "Ingest" },
  { id: "compile", label: "Compile" },
  { id: "quality", label: "Quality" },
];

const VIEW_ICONS: Record<View, string> = {
  explorer: "📂",
  chat: "💬",
  ingest: "⬆️",
  compile: "⚙️",
  quality: "✅",
};

interface SidebarProps {
  activeView: View;
  onNavigate: (view: View) => void;
}

export function Sidebar({ activeView, onNavigate }: SidebarProps) {
  const { status, refresh, model } = useStatus();
  const { compiling, stopCompile } = useCompile();
  const [loadingModel, setLoadingModel] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<boolean>(false);
  // Load saved collapsed state after mount to avoid hydration mismatch
  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("sidebar-collapsed") === "true";
      setCollapsed(saved);
    }
  }, []);
  useEffect(() => {
    if (typeof window !== "undefined")
      localStorage.setItem("sidebar-collapsed", String(collapsed));
  }, [collapsed]);

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
    <aside className={`flex flex-col bg-slate-900 text-slate-100 transition-all duration-200 ${collapsed ? "w-14" : "w-56"} min-h-screen`}>
      <div className={`flex items-center border-b border-slate-700 ${collapsed ? "p-2 justify-center" : "p-4"}`}>
        {!collapsed && (
          <div className="flex-1">
            <h1 className="text-lg font-bold text-white">Knowledge Based</h1>
            <p className="text-xs text-slate-400 mt-0.5">The Knowledge Mutilator</p>
          </div>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className={`text-slate-400 hover:text-slate-200 transition-colors ${collapsed ? "p-1" : "ml-auto p-1"}`}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? "»" : "«"}
        </button>
      </div>

      <nav className={`border-b border-slate-700 ${collapsed ? "p-1" : "p-2"}`}>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`flex items-center gap-2 w-full rounded-lg text-sm font-medium transition-colors mb-0.5 ${
              activeView === item.id
                ? "bg-blue-600 text-white"
                : "text-slate-300 hover:bg-slate-800 hover:text-white"
            } ${collapsed ? "justify-center py-3" : "px-3 py-2"}`}
            title={item.label}
          >
            <span className="text-base" aria-hidden="true">{VIEW_ICONS[item.id]}</span>
            {!collapsed && <span>{item.label}</span>}
          </button>
        ))}
      </nav>

      {!collapsed && (
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
      )}

      <div className="p-3 border-t border-slate-700">
        <button
          onClick={refresh}
          className={`w-full px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm transition-colors ${collapsed ? "py-3" : ""}`}
        >
          {collapsed ? "⟳" : "Refresh"}
        </button>
      </div>
    </aside>
  );
}
