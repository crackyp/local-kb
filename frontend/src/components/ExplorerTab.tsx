"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { api } from "@/lib/api";
import { useStatus } from "@/lib/StatusContext";
import { useFileList } from "@/lib/hooks";
import type { FileMeta, TrashItem, View } from "@/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { downloadWikiHtml } from "@/lib/exportHtml";

type Category = "raw" | "wiki" | "outputs";
const CATEGORIES: Category[] = ["wiki", "raw", "outputs"];
const CATEGORY_LABELS: Record<Category, string> = { wiki: "Wiki", raw: "Raw", outputs: "Outputs" };
const CATEGORY_EMPTY_ACTIONS: Record<Category, { action: View; label: string }> = {
  raw: { action: "ingest", label: "Open Ingest" },
  wiki: { action: "compile", label: "Open Compile" },
  outputs: { action: "chat", label: "Open Chat" },
};
const PREVIEWABLE = new Set([
  ".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".csv", ".html",
  ".py", ".js", ".ts", ".sql", ".log", ".toml", ".ini", ".cfg", ".sh", ".bat",
]);
const TRUNCATION_LIMIT = 100_000;
const EXT_EMOJI: Record<string, string> = {
  md: "📄", txt: "📄", pdf: "📕", json: "📋", yaml: "⚙️", yml: "⚙️",
  xml: "📋", csv: "📊", html: "🌐", py: "🐍", js: "🟨", ts: "🔷",
  sql: "🗄️", log: "📝", toml: "⚙️", ini: "⚙️", cfg: "⚙️",
  sh: "💻", bat: "💻", docx: "📘", pptx: "📙", png: "🖼️",
  jpg: "🖼️", jpeg: "🖼️", gif: "🖼️", webp: "🖼️",
};

function isPreviewable(name: string): boolean {
  const ext = name.lastIndexOf(".") >= 0 ? name.slice(name.lastIndexOf(".")).toLowerCase() : "";
  return PREVIEWABLE.has(ext);
}
function getExt(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i + 1).toLowerCase() : "";
}
function getEmoji(name: string): string {
  return EXT_EMOJI[getExt(name)] || "📄";
}
function formatCount(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "k";
  return String(n);
}
function getTopFolder(rel: string): string | null {
  // Handle both / and \ path separators (Windows uses \)
  const normalized = rel.replace(/\\/g, "/");
  const i = normalized.indexOf("/");
  return i >= 0 ? normalized.slice(0, i) : null;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

interface Toast { id: number; message: string; type: "info" | "success" | "error" | "undo"; undoAction?: () => void; undoLabel?: string; }
let toastIdCounter = 0;

function InlineConfirm({ message, confirmLabel, confirmVariant, onConfirm, onCancel }: {
  message: string; confirmLabel: string; confirmVariant?: "danger" | "primary";
  onConfirm: () => void; onCancel: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel(); };
    window.addEventListener("keydown", handler);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", handler);
  }, [onCancel]);
  return (
    <div ref={ref} role="dialog" aria-modal="true" tabIndex={-1}
      className="absolute right-0 top-full mt-1 z-50 bg-white border border-slate-200 rounded-lg shadow-lg p-3 min-w-[220px]">
      <div className="text-sm text-slate-700 mb-3">{message}</div>
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel}
          className="px-3 py-1.5 text-xs font-medium rounded border border-slate-300 text-slate-600 hover:bg-slate-50">Cancel</button>
        <button onClick={onConfirm}
          className={`px-3 py-1.5 text-xs font-medium rounded text-white ${confirmVariant === "danger" ? "bg-red-600 hover:bg-red-700" : "bg-blue-600 hover:bg-blue-700"}`}>
          {confirmLabel}
        </button>
      </div>
    </div>
  );
}

function TrashDrawer({ open, onClose, onRestore, onEmptyTrash }: {
  open: boolean; onClose: () => void; onRestore: () => void; onEmptyTrash: () => void;
}) {
  const [trashItems, setTrashItems] = useState<TrashItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [confirmEmpty, setConfirmEmpty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fetchTrash = useCallback(async () => {
    setLoading(true); setError(null);
    try { const res = await api.listTrash(); setTrashItems(res.files); }
    catch (e) { setError(String(e)); } finally { setLoading(false); }
  }, []);
  useEffect(() => { if (open) fetchTrash(); }, [open, fetchTrash]);

  const handleRestore = async (item: TrashItem) => {
    try {
      await api.restoreTrash(item.name, item.category);
      setTrashItems(p => p.filter(t => !(t.original_name === item.original_name && t.category === item.category)));
      onRestore();
    } catch (e: unknown) {
      const message = errorMessage(e);
      if (message.includes("ALREADY_EXISTS") || message.includes("409")) {
        setError(`"${item.original_name}" already exists in ${item.category}/ — rename or delete the current one first.`);
      } else { setError(message); }
    }
  };
  const handleEmpty = async () => {
    try { await api.emptyTrash(); setTrashItems([]); setConfirmEmpty(false); onEmptyTrash(); }
    catch (e) { setError(String(e)); }
  };
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-black/20" onClick={onClose} aria-hidden="true" />
      <div role="dialog" aria-label="Trash" className="ml-auto w-full max-w-md bg-white border-l border-slate-200 shadow-xl h-full flex flex-col z-10">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <h2 className="font-semibold text-slate-900">Trash</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-lg leading-none" aria-label="Close trash">✕</button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {loading && <div className="text-sm text-slate-400 text-center py-8">Loading…</div>}
          {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>}
          {!loading && trashItems.length === 0 && <div className="text-sm text-slate-400 text-center py-8">Trash is empty</div>}
          {trashItems.map((item, idx) => (
            <div key={`${item.category}-${item.original_name}-${idx}`}
              className="flex items-center justify-between p-3 rounded-lg border border-slate-100 hover:bg-slate-50">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-slate-800 truncate">{item.original_name}</div>
                <div className="text-xs text-slate-400 flex gap-2 mt-0.5">
                  <span className="bg-slate-100 px-1.5 py-0.5 rounded text-[10px] uppercase">{item.category}</span>
                  <span>{item.trashed_at}</span>
                </div>
              </div>
              <button onClick={() => handleRestore(item)}
                className="ml-3 px-3 py-1.5 text-xs font-medium rounded bg-blue-600 text-white hover:bg-blue-700 whitespace-nowrap">Restore</button>
            </div>
          ))}
        </div>
        {trashItems.length > 0 && (
          <div className="p-4 border-t border-slate-200">
            {confirmEmpty ? (
              <div className="flex gap-2 items-center">
                <span className="text-sm text-slate-600 flex-1">Empty all trash?</span>
                <button onClick={() => setConfirmEmpty(false)}
                  className="px-3 py-1.5 text-xs rounded border border-slate-300 text-slate-600 hover:bg-slate-50">Cancel</button>
                <button onClick={handleEmpty}
                  className="px-3 py-1.5 text-xs rounded bg-red-600 text-white hover:bg-red-700">Empty all</button>
              </div>
            ) : (
              <button onClick={() => setConfirmEmpty(true)}
                className="w-full px-3 py-2 text-xs font-medium rounded border border-red-300 text-red-600 hover:bg-red-50">
                Empty trash ({trashItems.length} items)
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function OutboundLinks({ linksTo, wikiFiles, onNavigateTo, onClose }: {
  linksTo: string[]; wikiFiles: FileMeta[]; onNavigateTo: (file: FileMeta) => void; onClose: () => void;
}) {
  return (
    <div className="w-56 border-l border-slate-200 bg-slate-50 flex flex-col flex-shrink-0">
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-200">
        <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Links</span>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xs" aria-label="Close links sidebar">✕</button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {linksTo.map((target) => {
          const targetName = target.split("/").pop() || target;
          const found = wikiFiles.find((f) => f.name === targetName);
          return (
            <button key={target} onClick={() => found && onNavigateTo(found)} disabled={!found}
              className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${
                found ? "text-blue-600 hover:bg-blue-50 cursor-pointer" : "text-slate-400 cursor-default"
              }`}
              title={found ? `Open "${found.title || found.name}"` : "Page not found in wiki"}>
              <span className={found ? "" : "opacity-60"}>{target}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

interface ExplorerTabProps { onNavigate?: (view: View) => void; }

export function ExplorerTab({ onNavigate }: ExplorerTabProps) {
  const { refresh: refreshStatus } = useStatus();

  // ── Phase 3: URL state ────────────────────────────────────
  const getUrlParams = () => {
    if (typeof window === "undefined") return { tab: null, file: null };
    const p = new URLSearchParams(window.location.search);
    return { tab: p.get("tab"), file: p.get("file") };
  };
  const initialUrlParams = getUrlParams();

  const [activeTab, setActiveTab] = useState<Category>(() => {
    if (initialUrlParams.tab && CATEGORIES.includes(initialUrlParams.tab as Category))
      return initialUrlParams.tab as Category;
    if (typeof window !== "undefined") {
      try {
        const v = localStorage.getItem("explorer-tab");
        if (v && CATEGORIES.includes(v as Category)) return v as Category;
      } catch {}
    }
    return "wiki";
  });
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState<string>("");

  // Load sort from localStorage on mount
  const sortLoaded = useRef(false);
  useEffect(() => {
    if (sortLoaded.current) return;
    sortLoaded.current = true;
    try {
      const v = localStorage.getItem("explorer-sort-" + activeTab);
      if (v) setSort(v);
    } catch {}
  }, [activeTab]);
  const [selected, setSelected] = useState<FileMeta | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [contentLoading, setContentLoading] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<FileMeta | null>(null);
  const [trashOpen, setTrashOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [wikiFiles, setWikiFiles] = useState<FileMeta[]>([]);
  const [outboundOpen, setOutboundOpen] = useState(false);
  const [folderCollapsed, setFolderCollapsed] = useState<Record<string, boolean>>({});
  const filterRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [focusIndex, setFocusIndex] = useState<number>(-1);

  // ── Phase 3: Line-wrap toggle (localStorage) ────────────
  const [wrapCode, setWrapCode] = useState<boolean>(true);
  // Load saved wrap preference after mount to avoid hydration mismatch
  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("explorer-wrapCode");
      if (saved !== null) setWrapCode(saved !== "false");
    }
  }, []);
  useEffect(() => { localStorage.setItem("explorer-wrapCode", String(wrapCode)); }, [wrapCode]);

  // ── Phase 3: Filter chips ────────────────────────────────
  const [filterChip, setFilterChip] = useState<string>("");

  // ── Resizable split pane ──────────────────────────────────
  const SPLIT_MIN = 240;
  const SPLIT_MAX = 600;
  const SPLIT_DEFAULT = 340;
  const [masterWidth, setMasterWidth] = useState<number>(SPLIT_DEFAULT);
  // Load saved width after mount to avoid hydration mismatch
  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("explorer-masterWidth");
      if (saved) {
        const n = parseInt(saved, 10);
        if (!isNaN(n)) setMasterWidth(Math.max(SPLIT_MIN, Math.min(SPLIT_MAX, n)));
      }
    }
  }, []);
  const dragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      let w = e.clientX - rect.left;
      w = Math.max(SPLIT_MIN, Math.min(SPLIT_MAX, w));
      setMasterWidth(w);
    };
    const onMouseUp = () => {
      if (dragging.current) {
        dragging.current = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  const wiki = useFileList("wiki");
  const raw = useFileList("raw");
  const outputs = useFileList("outputs");
  const lists = useMemo<Record<Category, ReturnType<typeof useFileList>>>(
    () => ({ wiki, raw, outputs }),
    [wiki, raw, outputs],
  );
  const active = lists[activeTab];

  // ── Phase 3: Filter chips (needs `active`) ────────────────
  const extensionCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const f of active.files) {
      const ext = getExt(f.name);
      if (ext) counts[ext] = (counts[ext] || 0) + 1;
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [active.files]);

  useEffect(() => { CATEGORIES.forEach((cat) => lists[cat].refresh()); }, [lists]);
  useEffect(() => { if (wiki.files.length > 0) setWikiFiles(wiki.files); }, [wiki.files]);

  // ── Phase 3: URL sync ─────────────────────────────────────
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const changed: string[] = [];
    if (params.get("tab") !== activeTab) { params.set("tab", activeTab); changed.push("tab"); }
    if (selected && params.get("file") !== selected.rel) { params.set("file", selected.rel); changed.push("file"); }
    else if (!selected && params.has("file")) { params.delete("file"); changed.push("file"); }
    if (changed.length > 0) {
      const qs = params.toString();
      const url = qs ? window.location.pathname + "?" + qs : window.location.pathname;
      history.replaceState(null, "", url);
    }
  }, [activeTab, selected]);

  // ── Phase 3: Save preferences ─────────────────────────────
  useEffect(() => {
    if (typeof window !== "undefined")
      localStorage.setItem("explorer-tab", activeTab);
  }, [activeTab]);
  useEffect(() => {
    if (typeof window !== "undefined")
      localStorage.setItem("explorer-sort-" + activeTab, sort);
  }, [sort, activeTab]);
  useEffect(() => {
    if (typeof window !== "undefined")
      localStorage.setItem("explorer-masterWidth", String(masterWidth));
  }, [masterWidth]);

  const effectiveSort = sort || (activeTab === "wiki" ? "name_asc" : "newest");

  const filteredFiles = useMemo(() => {
    return active.files
      .filter((f) => {
        if (!filter) return true;
        const q = filter.toLowerCase();
        return f.name.toLowerCase().includes(q) || (f.title?.toLowerCase().includes(q) ?? false) || f.rel.toLowerCase().includes(q);
      })
      .filter((f) => {
        if (!filterChip) return true;
        return getExt(f.name) === filterChip;
      })
      .sort((a, b) => {
        // Phase 3: Pin INDEX.md to the top in wiki view
        if (activeTab === "wiki") {
          if (a.name === "INDEX.md") return -1;
          if (b.name === "INDEX.md") return 1;
        }
        const aLabel = a.title || a.name;
        const bLabel = b.title || b.name;
        if (effectiveSort === "newest") return b.modified - a.modified;
        if (effectiveSort === "oldest") return a.modified - b.modified;
        if (effectiveSort === "name_asc") return aLabel.localeCompare(bLabel);
        if (effectiveSort === "name_desc") return bLabel.localeCompare(aLabel);
        if (effectiveSort === "largest") return b.size - a.size;
        return 0;
      });
  }, [active.files, filter, filterChip, effectiveSort, activeTab]);

  const groupedFiles = useMemo(() => {
    if (activeTab !== "raw") return null;
    const groups: Record<string, FileMeta[]> = {};
    const ungrouped: FileMeta[] = [];
    for (const f of filteredFiles) {
      const folder = getTopFolder(f.rel);
      if (folder) { if (!groups[folder]) groups[folder] = []; groups[folder].push(f); }
      else { ungrouped.push(f); }
    }
    return { groups, ungrouped };
  }, [filteredFiles, activeTab]);

  const flatList = useMemo(() => {
    if (!groupedFiles) return filteredFiles;
    const result: FileMeta[] = [];
    const addFiles = (files: FileMeta[]) => result.push(...files);
    for (const [name, files] of Object.entries(groupedFiles.groups)) {
      if (!folderCollapsed[name]) addFiles(files);
    }
    if (!folderCollapsed["__ungrouped__"]) addFiles(groupedFiles.ungrouped);
    return result;
  }, [groupedFiles, filteredFiles, folderCollapsed]);

  const addToast = useCallback((message: string, type: Toast["type"] = "info", undoAction?: () => void, undoLabel?: string) => {
    const id = ++toastIdCounter;
    setToasts((prev) => [...prev, { id, message, type, undoAction, undoLabel }]);
    if (type !== "undo") setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  }, []);
  const dismissToast = useCallback((id: number) => setToasts((prev) => prev.filter((t) => t.id !== id)), []);

  const handleSelect = useCallback(async (file: FileMeta) => {
    setSelected(file); setContent(null); setOutboundOpen(false);
    if (!isPreviewable(file.name)) return;
    setContentLoading(true);
    try { const res = await api.getFile(activeTab, file.rel); if (res.previewable) setContent(res.content); }
    catch (e) { console.error(e); } finally { setContentLoading(false); }
  }, [activeTab]);

  const handleDelete = useCallback(async (file: FileMeta) => {
    setDeleteConfirm(null);
    try {
      const deleted = await api.deleteFile(activeTab, file.rel);
      active.removeLocal(file.rel);
      if (selected?.rel === file.rel) { setSelected(null); setContent(null); }
      refreshStatus();
      const undoAction = async () => {
        try {
          await api.restoreTrash(deleted.trash_name || file.name, activeTab);
          active.refresh();
          addToast(`"${file.title || file.name}" restored`, "success");
        } catch (e: unknown) {
          const message = errorMessage(e);
          if (message.includes("ALREADY_EXISTS") || message.includes("409")) {
            addToast(`"${file.name}" already exists — rename or delete the current one first`, "error");
          } else { addToast(`Failed to restore: ${message}`, "error"); }
        }
      };
      addToast(`"${file.title || file.name}" moved to trash`, "undo", undoAction, "Undo");
    } catch (e) { console.error(e); addToast(`Failed to delete: ${e}`, "error"); }
  }, [activeTab, selected, active, refreshStatus, addToast]);

  const handleRefresh = useCallback(() => { active.refresh(); refreshStatus(); }, [active, refreshStatus]);
  const switchTab = useCallback((tab: Category) => {
    setActiveTab(tab); setSelected(null); setContent(null); setDeleteConfirm(null);
    setFocusIndex(-1); setSort(""); lists[tab].refresh();
  }, [lists]);

  const handleDownload = useCallback(() => {
    if (!selected || !content) return;
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = selected.name;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  }, [selected, content]);

  const handleCopyContent = useCallback(() => {
    if (!content) return;
    navigator.clipboard.writeText(content).then(() => addToast("Content copied", "success"), () => addToast("Failed to copy", "error"));
  }, [content, addToast]);

  const handleCopyPath = useCallback(() => {
    if (!selected) return;
    navigator.clipboard.writeText(`${activeTab}/${selected.rel}`).then(
      () => addToast("Path copied", "success"), () => addToast("Failed to copy", "error"));
  }, [selected, activeTab, addToast]);

  const handlePromote = useCallback(async () => {
    if (!selected) return;
    try { await api.promote(selected.name); addToast("Saved to raw/", "success"); }
    catch (e) { addToast(`Failed to promote: ${e}`, "error"); }
  }, [selected, addToast]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
        if (e.key !== "Escape" && e.key !== "/") return;
      }
      if (e.key === "/" && tag !== "INPUT") { e.preventDefault(); filterRef.current?.focus(); return; }
      if (e.key === "Escape") {
        if (deleteConfirm) { setDeleteConfirm(null); return; }
        if (trashOpen) { setTrashOpen(false); return; }
        if (filter) { setFilter(""); filterRef.current?.focus(); return; }
        return;
      }
      if (e.key === "1") { switchTab("wiki"); return; }
      if (e.key === "2") { switchTab("raw"); return; }
      if (e.key === "3") { switchTab("outputs"); return; }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (flatList.length === 0) return;
        let next = focusIndex;
        if (e.key === "ArrowDown") next = Math.min(focusIndex + 1, flatList.length - 1);
        else next = Math.max(focusIndex - 1, 0);
        setFocusIndex(next);
        const el = listRef.current?.querySelector(`[data-index="${next}"]`) as HTMLElement | null;
        el?.scrollIntoView({ block: "nearest" });
        return;
      }
      if (e.key === "Enter" && focusIndex >= 0 && focusIndex < flatList.length) {
        e.preventDefault(); handleSelect(flatList[focusIndex]); return;
      }
      if ((e.key === "Delete" || e.key === "Backspace") && focusIndex >= 0 && focusIndex < flatList.length && tag !== "INPUT") {
        e.preventDefault(); setDeleteConfirm(flatList[focusIndex]); return;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [filter, deleteConfirm, trashOpen, focusIndex, flatList, switchTab, handleSelect]);

  useEffect(() => {
    if (focusIndex >= flatList.length) setFocusIndex(flatList.length > 0 ? 0 : -1);
  }, [flatList.length, focusIndex]);

  // ── Phase 3: Restore selected file from URL on mount ──────
  const initialFileHandled = useRef(false);
  useEffect(() => {
    if (initialFileHandled.current) return;
    const fp = getUrlParams().file;
    if (fp && active.files.length > 0) {
      const match = active.files.find((f) => f.rel === fp);
      if (match) {
        initialFileHandled.current = true;
        handleSelect(match);
      }
    }
  }, [active.files, handleSelect]);

  const renderRow = (file: FileMeta, index: number) => {
    const isSelected = selected?.rel === file.rel;
    const isFocused = focusIndex === index;
    const label = file.title || file.name;
    const emoji = getEmoji(file.name);
    return (
      <div key={file.rel} data-index={index} role="option" aria-selected={isSelected} tabIndex={-1}
        onClick={() => { handleSelect(file); setFocusIndex(index); }}
        onMouseEnter={() => setFocusIndex(index)}
        className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-colors ${isSelected ? "bg-blue-50" : "hover:bg-slate-50"} ${isFocused && !isSelected ? "bg-slate-50" : ""}`}
        style={{ borderLeft: isSelected ? "3px solid #3b82f6" : "3px solid transparent" }}>
        <span className="text-base flex-shrink-0">{emoji}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-800 truncate">{label}</span>
            {file.name === "INDEX.md" && <span className="text-[10px] font-semibold uppercase px-1 py-0.5 rounded bg-amber-100 text-amber-700 flex-shrink-0">index</span>}
            {file.words && <span className="text-[10px] text-slate-400 flex-shrink-0">{formatCount(file.words)}w</span>}
          </div>
          <div className="text-xs text-slate-400 truncate">{file.rel} · {file.size_h} · {file.modified_h}</div>
        </div>
        <button onClick={(e) => { e.stopPropagation(); setDeleteConfirm(file); }}
          className={`text-red-400 hover:text-red-600 text-xs px-1.5 py-1 rounded hover:bg-red-50 flex-shrink-0 transition-opacity ${
            isFocused || isSelected ? "opacity-100" : "opacity-0 group-hover:opacity-100 focus:opacity-100"
          }`}
          aria-label={`Delete ${file.name}`} tabIndex={-1}>✕</button>
      </div>
    );
  };

  const renderFolderGroup = (folderName: string, files: FileMeta[], startIndex: number) => {
    const collapsed = folderCollapsed[folderName] ?? false;
    return (
      <div key={`folder-${folderName}`}>
        <button onClick={() => setFolderCollapsed((prev) => ({ ...prev, [folderName]: !collapsed }))}
          className="w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-500 hover:bg-slate-50">
          <span className="text-xs">{collapsed ? "▸" : "▾"}</span>
          <span>📁 {folderName}</span>
          <span className="text-slate-400 font-normal normal-case">({files.length})</span>
        </button>
        {!collapsed && files.map((f, i) => renderRow(f, startIndex + i))}
      </div>
    );
  };

  const truncationBanner = content && content.length > TRUNCATION_LIMIT
    ? `Showing first ${formatCount(TRUNCATION_LIMIT)} of ${formatCount(content.length)} characters — Download to view in full.`
    : null;
  const displayContent = content && content.length > TRUNCATION_LIMIT ? content.slice(0, TRUNCATION_LIMIT) : content;

  const resolveLink = useCallback((href: string): FileMeta | null => {
    const targetName = href.split("#")[0].split("/").pop()!;
    return wikiFiles.find((f) => f.name === targetName) || null;
  }, [wikiFiles]);

  return (
    <>
      <div className="flex flex-col h-[calc(100vh-8rem)] bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        {/* Command bar */}
        <div className="flex items-center gap-3 px-4 py-2.5 border-b border-slate-200 bg-white flex-shrink-0">
          <div className="flex bg-slate-100 rounded-lg p-0.5">
            {CATEGORIES.map((tab) => (
              <button key={tab} onClick={() => switchTab(tab)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors capitalize ${
                  activeTab === tab ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
                }`}>
                {CATEGORY_LABELS[tab]} ({lists[tab].count})
              </button>
            ))}
          </div>
          <div className="relative flex-1 max-w-xs">
            <input ref={filterRef} type="text" value={filter}
              onChange={(e) => { setFilter(e.target.value); setFocusIndex(-1); }}
              placeholder="Filter…  (/)"
              className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white" />
            {filter && <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-slate-400">{filteredFiles.length} of {active.files.length}</span>}
          </div>
          {/* Phase 3: Filter chips */}
          {extensionCounts.length > 0 && !filter && (
            <div className="flex gap-1 overflow-x-auto flex-shrink-0 max-w-[180px]">
              {filterChip && (
                <button onClick={() => setFilterChip("")}
                  className="px-1.5 py-1 text-[10px] font-medium rounded bg-slate-200 text-slate-600 hover:bg-slate-300 whitespace-nowrap">
                  ✕ clear
                </button>
              )}
              {extensionCounts.slice(0, 6).map(([ext, count]) => (
                <button key={ext} onClick={() => setFilterChip(filterChip === ext ? "" : ext)}
                  className={`px-1.5 py-1 text-[10px] font-medium rounded whitespace-nowrap transition-colors ${
                    filterChip === ext
                      ? "bg-blue-600 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}>
                  .{ext} {count}
                </button>
              ))}
            </div>
          )}
          <select value={effectiveSort} onChange={(e) => setSort(e.target.value)}
            className="px-2 py-1.5 text-xs border border-slate-300 rounded-lg bg-white text-slate-700">
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
            <option value="name_asc">A→Z</option>
            <option value="name_desc">Z→A</option>
            <option value="largest">Largest</option>
          </select>
          <button onClick={() => { setTrashOpen(true); setDeleteConfirm(null); }}
            className="px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors">🗑️ Trash</button>
          <button onClick={handleRefresh}
            className="px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors" title="Refresh">⟳</button>
        </div>

        {/* Master-detail columns */}
        <div ref={containerRef} className="flex flex-1 min-h-0">
          {/* Master column */}
          <div style={{ width: masterWidth, minWidth: SPLIT_MIN, maxWidth: SPLIT_MAX }} className="border-r border-slate-200 flex flex-col flex-shrink-0">
            <div className="px-3 py-2 text-[10px] uppercase tracking-wider text-slate-400 border-b border-slate-100 flex-shrink-0">
              {filteredFiles.length === active.files.length
                ? `${active.files.length} file${active.files.length !== 1 ? "s" : ""}`
                : `${filteredFiles.length} of ${active.files.length} match`}
              <span className="ml-2 text-slate-300">· sorted {effectiveSort === "name_asc" ? "A→Z" : effectiveSort === "name_desc" ? "Z→A" : effectiveSort === "newest" ? "newest" : effectiveSort === "oldest" ? "oldest" : "largest"}</span>
            </div>
            <div ref={listRef} role="listbox" aria-label="File list" className="flex-1 overflow-y-auto divide-y divide-slate-50 group">
              {filteredFiles.length === 0 ? (
                <div className="p-6 text-center">
                  <div className="text-slate-500 font-medium mb-1">{filter ? "No matching files" : `No ${activeTab} files yet`}</div>
                  {!filter && <div className="text-xs text-slate-400 mb-3">
                    {activeTab === "raw" && "Head to the Ingest tab to add files, URLs, or PDFs."}
                    {activeTab === "wiki" && "Compile your raw sources to generate wiki pages."}
                    {activeTab === "outputs" && "Ask a question or run a health check to generate output."}                    
                  </div>}
                  {!filter && onNavigate && (
                    <button onClick={() => onNavigate(CATEGORY_EMPTY_ACTIONS[activeTab].action)}
                      className="px-4 py-2 text-xs font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors">
                      {CATEGORY_EMPTY_ACTIONS[activeTab].label}
                    </button>
                  )}
                </div>
              ) : activeTab === "raw" && groupedFiles ? (
                <>
                  {Object.entries(groupedFiles.groups).map(([name, files], gi) => {
                    const startIndex = Object.entries(groupedFiles.groups).slice(0, gi).reduce((sum, [, fs]) => sum + (folderCollapsed[name] ? 0 : fs.length), 0);
                    return renderFolderGroup(name, files, startIndex);
                  })}
                  {groupedFiles.ungrouped.length > 0 && renderFolderGroup("Ungrouped", groupedFiles.ungrouped,
                    Object.entries(groupedFiles.groups).reduce((sum, [, fs]) => sum + (folderCollapsed["__ungrouped__"] ? 0 : fs.length), 0))}
                </>
              ) : (
                filteredFiles.map((f, i) => renderRow(f, i))
              )}
            </div>
          </div>

          {/* Draggable divider */}
          <div
            onMouseDown={onDragStart}
            className="w-1.5 cursor-col-resize bg-transparent hover:bg-blue-400 active:bg-blue-500 flex-shrink-0 transition-colors relative"
            style={{ marginLeft: "-1px" }}
            title="Drag to resize"
          />

          {/* Detail column */}
          <div className="flex-1 flex flex-col min-w-0">
            {selected ? (
              <>
                <div className="px-5 py-3 border-b border-slate-200 flex-shrink-0">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold text-slate-900 truncate text-base">{selected.title || selected.name}</h3>
                      <div className="text-xs text-slate-400 mt-0.5 flex gap-3 flex-wrap">
                        <span>{selected.rel}</span>
                        <span>{selected.size_h}</span>
                        <span>{selected.modified_h}</span>
                        {selected.words && <span>{formatCount(selected.words)} words</span>}
                        {selected.links_to && selected.links_to.length > 0 && (
                          <span>{selected.links_to.length} link{selected.links_to.length !== 1 ? "s" : ""}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0 flex-wrap">
                      {content && (activeTab === "wiki" || selected.name.endsWith(".md")) && (
                        <button onClick={() => downloadWikiHtml(selected.title || selected.name, selected.name, content)}
                          className="text-xs px-2.5 py-1 rounded border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors">HTML</button>
                      )}
                      <button onClick={handleDownload}
                        className="text-xs px-2.5 py-1 rounded border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors">Download</button>
                      {content && <button onClick={handleCopyContent}
                        className="text-xs px-2.5 py-1 rounded border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors">Copy</button>}
                      <button onClick={handleCopyPath}
                        className="text-xs px-2.5 py-1 rounded border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors">Path</button>
                      {content && !(activeTab === "wiki" || selected.name.endsWith(".md")) && (
                        <button onClick={() => setWrapCode((w) => !w)}
                          className={`text-xs px-2.5 py-1 rounded border transition-colors ${
                            wrapCode
                              ? "bg-blue-50 border-blue-300 text-blue-700"
                              : "border-slate-300 text-slate-600 hover:bg-slate-50"
                          }`}>
                          {wrapCode ? "Wrap" : "No wrap"}
                        </button>
                      )}
                      {activeTab === "outputs" && (
                        <button onClick={handlePromote}
                          className="text-xs px-2.5 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors">Promote</button>
                      )}
                      {selected.links_to && selected.links_to.length > 0 && (
                        <button onClick={() => setOutboundOpen((o) => !o)}
                          className="text-xs px-2.5 py-1 rounded border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors">Links ({selected.links_to.length})</button>
                      )}
                      <div className="relative">
                        <button onClick={() => setDeleteConfirm(selected)}
                          className="text-xs px-2.5 py-1 rounded bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 transition-colors">Delete</button>
                        {deleteConfirm?.rel === selected.rel && (
                          <InlineConfirm
                            message={`Move "${selected.title || selected.name}" to trash?`}
                            confirmLabel="Delete" confirmVariant="danger"
                            onConfirm={() => handleDelete(selected)}
                            onCancel={() => setDeleteConfirm(null)} />
                        )}
                      </div>
                    </div>
                  </div>
                </div>
                <div className="flex flex-1 min-h-0">
                  <div className="flex-1 overflow-y-auto">
                    {contentLoading ? (
                      <div className="p-4 text-sm text-slate-400">Loading preview…</div>
                    ) : displayContent ? (
                      <>
                        {truncationBanner && (
                          <div className="mx-4 mt-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                            {truncationBanner}
                          </div>
                        )}
                        {activeTab === "wiki" || selected.name.endsWith(".md") ? (
                          <div className="prose prose-slate prose-sm max-w-none p-4 max-h-full overflow-visible">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                a: ({ href, children, ...props }) => {
                                  const isInternalMd =
                                    !!href &&
                                    !/^[a-z]+:\/\//i.test(href) &&
                                    !href.startsWith("/") &&
                                    !href.startsWith("#") &&
                                    href.split("#")[0].toLowerCase().endsWith(".md");
                                  if (isInternalMd) {
                                    const target = resolveLink(href!);
                                    return (
                                      <a
                                        href={href}
                                        onClick={(e) => {
                                          e.preventDefault();
                                          if (target) {
                                            handleSelect(target);
                                          }
                                        }}
                                        className={target ? "" : "text-slate-400 cursor-default"}
                                        title={target ? "" : "No matching page in wiki"}
                                      >
                                        {children}
                                      </a>
                                    );
                                  }
                                  return (
                                    <a href={href} target="_blank" rel="noreferrer" {...props}>
                                      {children}
                                    </a>
                                  );
                                },
                              }}
                            >
                              {displayContent}
                            </ReactMarkdown>
                          </div>
                        ) : (
                          <pre className={`text-xs text-slate-600 p-4 ${wrapCode ? "whitespace-pre-wrap" : "whitespace-pre overflow-x-auto"}`}>
                            {displayContent}
                          </pre>
                        )}
                      </>
                    ) : selected && isPreviewable(selected.name) ? (
                      <div className="p-4 text-sm text-slate-400">Could not load preview</div>
                    ) : selected ? (
                      <div className="p-4 text-sm text-slate-400 flex items-center gap-3">
                        <span className="text-2xl">{getEmoji(selected.name)}</span>
                        <div>
                          <div className="font-medium text-slate-600">Binary file — preview not available</div>
                          <div className="text-xs text-slate-400 mt-1">{selected.size_h} · {selected.name}</div>
                          <button onClick={handleDownload}
                            className="mt-2 px-3 py-1.5 text-xs font-medium rounded bg-blue-600 text-white hover:bg-blue-700">
                            Download
                          </button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                  {activeTab === "wiki" && outboundOpen && selected?.links_to && selected.links_to.length > 0 && (
                    <OutboundLinks
                      linksTo={selected.links_to}
                      wikiFiles={wikiFiles}
                      onNavigateTo={(file) => {
                        if (activeTab !== "wiki") switchTab("wiki");
                        handleSelect(file);
                      }}
                      onClose={() => setOutboundOpen(false)}
                    />
                  )}
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <div className="text-4xl mb-2">📂</div>
                  <div className="text-sm text-slate-400">Select a file to preview</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Toast container */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`px-4 py-3 rounded-lg shadow-lg text-sm flex items-center gap-3 min-w-[280px] max-w-md transition-all ${
              toast.type === "error"
                ? "bg-red-600 text-white"
                : toast.type === "success"
                ? "bg-green-600 text-white"
                : toast.type === "undo"
                ? "bg-slate-800 text-white"
                : "bg-slate-800 text-white"
            }`}
            role={toast.type === "undo" ? "alert" : "status"}
            aria-live={toast.type === "undo" ? "assertive" : "polite"}
          >
            <span className="flex-1">{toast.message}</span>
            {toast.type === "undo" && toast.undoAction && (
              <button
                onClick={() => {
                  toast.undoAction!();
                  dismissToast(toast.id);
                }}
                className="text-xs font-semibold uppercase tracking-wide text-blue-300 hover:text-blue-200 whitespace-nowrap"
              >
                {toast.undoLabel || "Undo"}
              </button>
            )}
            <button
              onClick={() => dismissToast(toast.id)}
              className="text-white/60 hover:text-white text-xs"
              aria-label="Dismiss"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      {/* Trash drawer */}
      <TrashDrawer
        open={trashOpen}
        onClose={() => { setTrashOpen(false); }}
        onRestore={() => { active.refresh(); refreshStatus(); }}
        onEmptyTrash={() => { active.refresh(); refreshStatus(); }}
      />
    </>
  );
}
