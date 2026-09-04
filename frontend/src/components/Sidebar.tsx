"use client";

import { useState, useEffect } from "react";
import type { View } from "@/types";
import { useStatus } from "@/lib/StatusContext";
import { useCompile } from "@/lib/CompileContext";
import { StatusBadge, ModelSelect } from "@/components/shared";
import { api } from "@/lib/api";
import {
  FolderOpen,
  MessageSquare,
  Upload,
  CheckCircle,
  ChevronsLeft,
  ChevronsRight,
  RotateCcw,
} from "lucide-react";

const NAV_ITEMS: { id: View; label: string; icon: string }[] = [
  { id: "explorer", label: "Explorer", icon: "FolderOpen" },
  { id: "chat", label: "Chat", icon: "MessageSquare" },
  { id: "upload", label: "Upload", icon: "Upload" },
  { id: "quality", label: "Quality", icon: "CheckCircle" },
];

function NavIcon({ name }: { name: string }) {
  switch (name) {
    case "FolderOpen": return <FolderOpen className="w-4 h-4" />;
    case "MessageSquare": return <MessageSquare className="w-4 h-4" />;
    case "Upload": return <Upload className="w-4 h-4" />;
    case "CheckCircle": return <CheckCircle className="w-4 h-4" />;
    default: return <FolderOpen className="w-4 h-4" />;
  }
}

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
    <aside className={`flex flex-col bg-zinc-900 text-zinc-100 transition-all duration-200 ${collapsed ? "w-14" : "w-56"} min-h-screen`}>
      <div className={`flex items-center border-b border-zinc-700 ${collapsed ? "p-2 justify-center" : "p-4"}`}>
        {!collapsed && (
          <div className="flex-1">
            <h1 className="text-lg font-bold text-white tracking-tight">Knowledge Base</h1>
            <p className="text-xs text-zinc-400 mt-0.5">Personal Knowledge Base</p>
          </div>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className={`text-zinc-400 hover:text-zinc-200 transition-colors duration-150 ease-out ${collapsed ? "p-1" : "ml-auto p-1"}`}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronsRight className="w-4 h-4" /> : <ChevronsLeft className="w-4 h-4" />}
        </button>
      </div>

      <nav className={`border-b border-zinc-700 ${collapsed ? "p-1" : "p-2"}`}>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`flex items-center gap-2 w-full rounded text-sm font-medium transition-colors duration-150 ease-out mb-0.5 ${
              activeView === item.id
                ? "bg-violet-600 text-white"
                : "text-zinc-300 hover:bg-zinc-800 hover:text-white"
            } ${collapsed ? "justify-center py-3" : "px-3 py-2"}`}
            title={item.label}
          >
            <NavIcon name={item.icon} />
            {!collapsed && <span>{item.label}</span>}
          </button>
        ))}
      </nav>

      {!collapsed && (
        <div className="p-4 flex-1 overflow-y-auto space-y-3">
          {/* Compact status pills */}
          <div className="p-3 rounded bg-zinc-800/50 border border-zinc-700/50">
            <div className="flex items-center gap-2 text-xs mb-2">
              <StatusBadge value={status?.llamacpp.running ? "running" : "not_running"} />
              {status?.llamacpp.running && loadedModel && (
                <span className="text-zinc-400 truncate" title={loadedModel}>
                  · {loadedModel}
                </span>
              )}
            </div>
            <ModelSelect label="Model" tone="dark" />
            {status?.llamacpp.running && (
              <button
                onClick={handleLoad}
                disabled={!model || loadingModel || selectedMatchesLoaded}
                className="mt-2 w-full px-2 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-700 disabled:text-zinc-400 disabled:cursor-not-allowed rounded text-xs font-medium text-white transition-colors duration-150 ease-out"
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

          <div className="p-3 rounded bg-zinc-800/50 border border-zinc-700/50">
            <div className="flex items-center gap-2 text-xs">
              <StatusBadge value={status?.faiss ?? "unknown"} />
            </div>
          </div>

          {compiling && (
            <div className="p-3 rounded bg-violet-950/60 border border-violet-800">
              <div className="text-xs text-violet-300 uppercase tracking-wide mb-1">Compile Job</div>
              <div className="text-sm text-violet-100 mb-3">Running in background while you browse.</div>
              <div className="flex gap-2">
                <button
                  onClick={() => onNavigate("upload")}
                  className="flex-1 px-3 py-2 bg-violet-700 hover:bg-violet-600 rounded text-sm transition-colors duration-150 ease-out"
                >
                  Open
                </button>
                <button
                  onClick={stopCompile}
                  className="px-3 py-2 bg-red-700 hover:bg-red-600 rounded text-sm transition-colors duration-150 ease-out"
                >
                  Stop
                </button>
              </div>
            </div>
          )}

          <div className="border-t border-zinc-700 pt-3 space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-zinc-400">Raw files</span>
              <span className="font-medium text-zinc-200">{status?.files.raw ?? "—"}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-zinc-400">Wiki pages</span>
              <span className="font-medium text-zinc-200">{status?.files.wiki ?? "—"}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-zinc-400">Outputs</span>
              <span className="font-medium text-zinc-200">{status?.files.outputs ?? "—"}</span>
            </div>
          </div>
        </div>
      )}

      <div className="p-3 border-t border-zinc-700">
        <button
          onClick={refresh}
          className={`w-full px-3 py-2 bg-zinc-800 hover:bg-zinc-700 rounded text-sm transition-colors duration-150 ease-out ${collapsed ? "py-3" : ""}`}
          title="Refresh status"
        >
          {collapsed ? <RotateCcw className="w-4 h-4 mx-auto" /> : "Refresh"}
        </button>
      </div>
    </aside>
  );
}
