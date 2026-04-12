"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useStatus } from "@/lib/StatusContext";
import { useFileList } from "@/lib/hooks";
import type { FileMeta } from "@/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Category = "raw" | "wiki" | "outputs";

const CATEGORIES: Category[] = ["wiki", "raw", "outputs"];

const PREVIEWABLE = new Set([
  ".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".csv", ".html",
  ".py", ".js", ".ts", ".sql", ".log", ".toml", ".ini", ".cfg", ".sh", ".bat",
]);

function isPreviewable(name: string): boolean {
  const ext = name.lastIndexOf(".") >= 0 ? name.slice(name.lastIndexOf(".")).toLowerCase() : "";
  return PREVIEWABLE.has(ext);
}

const EMPTY_MESSAGES: Record<Category, { heading: string; hint: string }> = {
  raw: {
    heading: "No source files yet",
    hint: "Head to the Ingest tab to add files, URLs, or PDFs.",
  },
  wiki: {
    heading: "No wiki pages yet",
    hint: "Compile your raw sources to generate wiki pages.",
  },
  outputs: {
    heading: "No outputs yet",
    hint: "Ask a question or run a health check to generate output.",
  },
};

export function ExplorerTab() {
  const { refresh: refreshStatus } = useStatus();
  const [activeTab, setActiveTab] = useState<Category>("wiki");
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState("newest");
  const [selected, setSelected] = useState<FileMeta | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [contentLoading, setContentLoading] = useState(false);

  // Per-category file lists
  const wiki = useFileList("wiki");
  const raw = useFileList("raw");
  const outputs = useFileList("outputs");
  const lists: Record<Category, ReturnType<typeof useFileList>> = { wiki, raw, outputs };
  const active = lists[activeTab];

  // Fetch counts for inactive tabs once on mount
  useEffect(() => {
    CATEGORIES.forEach((cat) => lists[cat].refresh());
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const filteredFiles = active.files
    .filter((f) => {
      if (!filter) return true;
      const q = filter.toLowerCase();
      return (
        f.name.toLowerCase().includes(q) ||
        (f.title?.toLowerCase().includes(q) ?? false)
      );
    })
    .sort((a, b) => {
      const aLabel = a.title || a.name;
      const bLabel = b.title || b.name;
      if (sort === "newest") return b.modified - a.modified;
      if (sort === "oldest") return a.modified - b.modified;
      if (sort === "name_asc") return aLabel.localeCompare(bLabel);
      if (sort === "name_desc") return bLabel.localeCompare(aLabel);
      if (sort === "largest") return b.size - a.size;
      return 0;
    });

  const handleSelect = async (file: FileMeta) => {
    setSelected(file);
    setContent(null);
    if (!isPreviewable(file.name)) return;
    setContentLoading(true);
    try {
      const res = await api.getFile(activeTab, file.rel);
      if (res.previewable) setContent(res.content);
    } catch (e) {
      console.error(e);
    } finally {
      setContentLoading(false);
    }
  };

  const handleDelete = async (file: FileMeta) => {
    if (!confirm(`Delete ${file.name}?`)) return;
    try {
      await api.deleteFile(activeTab, file.rel);
      active.removeLocal(file.rel);
      if (selected?.rel === file.rel) {
        setSelected(null);
        setContent(null);
      }
      refreshStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const handleRefresh = () => {
    active.refresh();
    refreshStatus();
  };

  const switchTab = (tab: Category) => {
    setActiveTab(tab);
    setSelected(null);
    setContent(null);
    lists[tab].refresh();
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="flex border-b border-slate-200">
          {CATEGORIES.map((tab) => (
            <button
              key={tab}
              onClick={() => switchTab(tab)}
              className={`px-4 py-3 text-sm font-medium capitalize transition-colors ${
                activeTab === tab ? "text-blue-600 border-b-2 border-blue-600 bg-blue-50" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {tab} ({lists[tab].count})
            </button>
          ))}
        </div>

        <div className="p-4 border-b border-slate-200 flex gap-4">
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by name..."
            className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
          />
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white"
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="name_asc">Name A-Z</option>
            <option value="name_desc">Name Z-A</option>
            <option value="largest">Largest first</option>
          </select>
          <button
            onClick={handleRefresh}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm hover:bg-slate-50 transition-colors"
          >
            Refresh
          </button>
        </div>

        <div className="max-h-48 overflow-y-auto">
          {filteredFiles.length === 0 ? (
            <div className="p-8 text-center">
              <div className="text-slate-500 font-medium mb-1">
                {filter ? "No matching files" : EMPTY_MESSAGES[activeTab].heading}
              </div>
              {!filter && (
                <div className="text-sm text-slate-400">
                  {EMPTY_MESSAGES[activeTab].hint}
                </div>
              )}
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs sticky top-0">
                <tr>
                  <th className="text-left px-4 py-2">File</th>
                  <th className="text-right px-4 py-2">Size</th>
                  <th className="text-right px-4 py-2">Modified</th>
                  <th className="w-20"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredFiles.map((file) => (
                  <tr
                    key={file.rel}
                    onClick={() => handleSelect(file)}
                    className={`cursor-pointer hover:bg-blue-50 ${selected?.rel === file.rel ? "bg-blue-100" : ""}`}
                  >
                    <td className="px-4 py-2.5 font-medium text-slate-700 truncate max-w-xs">
                      {file.title ? (
                        <>
                          <div className="truncate">{file.title}</div>
                          <div className="text-xs text-slate-400 font-normal truncate">{file.name}</div>
                        </>
                      ) : (
                        file.name
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right text-slate-500">{file.size_h}</td>
                    <td className="px-4 py-2.5 text-right text-slate-500">{file.modified_h}</td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(file); }}
                        className="text-red-500 hover:text-red-700 text-xs px-2 py-1 rounded hover:bg-red-50"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {selected && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="min-w-0">
              <h3 className="font-semibold text-slate-900 truncate">{selected.title || selected.name}</h3>
              {selected.title && (
                <div className="text-xs text-slate-400 truncate">{selected.name}</div>
              )}
            </div>
            <span className="text-xs text-slate-400 whitespace-nowrap ml-3">{selected.size_h} | {selected.modified_h}</span>
          </div>
          {contentLoading ? (
            <div className="text-sm text-slate-400 bg-slate-50 rounded-lg p-4">
              Loading preview...
            </div>
          ) : content ? (
            activeTab === "wiki" || selected.name.endsWith(".md") ? (
              <div className="prose prose-slate prose-sm max-w-none bg-slate-50 rounded-lg p-4 max-h-[60vh] overflow-auto">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {content.length > 15000 ? content.slice(0, 15000) + "\n\n...(truncated)" : content}
                </ReactMarkdown>
              </div>
            ) : (
              <pre className="text-xs text-slate-600 bg-slate-50 rounded-lg p-4 max-h-[60vh] overflow-auto whitespace-pre-wrap">
                {content.length > 15000 ? content.slice(0, 15000) + "\n\n...(truncated)" : content}
              </pre>
            )
          ) : (
            <div className="text-sm text-slate-400 bg-slate-50 rounded-lg p-4">
              {isPreviewable(selected.name)
                ? "Could not load preview"
                : "Binary file — preview not available"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
