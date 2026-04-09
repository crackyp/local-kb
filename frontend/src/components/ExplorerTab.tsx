"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { FileMeta } from "@/types";
import ReactMarkdown from "react-markdown";

type Category = "raw" | "wiki" | "outputs";

const PREVIEWABLE = new Set([".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".csv", ".html", ".py", ".js", ".ts", ".sql", ".log", ".toml", ".ini", ".cfg", ".sh", ".bat"]);

export function ExplorerTab() {
  const [activeTab, setActiveTab] = useState<Category>("wiki");
  const [files, setFiles] = useState<FileMeta[]>([]);
  const [counts, setCounts] = useState<Record<Category, number>>({ raw: 0, wiki: 0, outputs: 0 });
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState("newest");
  const [selected, setSelected] = useState<FileMeta | null>(null);
  const [content, setContent] = useState<string | null>(null);

  // Fetch counts for all categories once on mount
  useEffect(() => {
    (["raw", "wiki", "outputs"] as Category[]).forEach((cat) => {
      api.listFiles(cat).then((res) => {
        setCounts((prev) => ({ ...prev, [cat]: res.count }));
      }).catch(console.error);
    });
  }, []);

  useEffect(() => {
    let ignore = false;
    async function fetchFiles() {
      const res = await api.listFiles(activeTab);
      if (!ignore) {
        setFiles(res.files);
        setCounts((prev) => ({ ...prev, [activeTab]: res.count }));
      }
    }
    fetchFiles().catch(console.error);
    return () => { ignore = true; };
  }, [activeTab]);

  const filteredFiles = files
    .filter((f) => filter === "" || f.name.toLowerCase().includes(filter.toLowerCase()))
    .sort((a, b) => {
      if (sort === "newest") return b.modified - a.modified;
      if (sort === "oldest") return a.modified - b.modified;
      if (sort === "name_asc") return a.name.localeCompare(b.name);
      if (sort === "name_desc") return b.name.localeCompare(a.name);
      if (sort === "largest") return b.size - a.size;
      return 0;
    });

  const handleSelect = async (file: FileMeta) => {
    setSelected(file);
    setContent(null);
    if (file.name.split(".").pop() && PREVIEWABLE.has("." + file.name.split(".").pop()!.toLowerCase())) {
      try {
        const res = await api.getFile(activeTab, file.rel);
        if (res.previewable) setContent(res.content);
      } catch (e) {
        console.error(e);
      }
    }
  };

  const handleDelete = async (file: FileMeta) => {
    if (!confirm(`Delete ${file.name}?`)) return;
    try {
      await api.deleteFile(activeTab, file.rel);
      setFiles((prev) => prev.filter((f) => f.rel !== file.rel));
      if (selected?.rel === file.rel) setSelected(null);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="flex border-b border-slate-200">
          {(["wiki", "raw", "outputs"] as Category[]).map((tab) => (
            <button
              key={tab}
              onClick={() => { setActiveTab(tab); setSelected(null); }}
              className={`px-4 py-3 text-sm font-medium capitalize transition-colors ${
                activeTab === tab ? "text-blue-600 border-b-2 border-blue-600 bg-blue-50" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {tab} ({counts[tab]})
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
        </div>

        <div className="max-h-48 overflow-y-auto">
          {filteredFiles.length === 0 ? (
            <div className="p-8 text-center text-slate-400">No files</div>
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
                    <td className="px-4 py-2.5 font-medium text-slate-700 truncate max-w-xs">{file.name}</td>
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
            <h3 className="font-semibold text-slate-900">{selected.name}</h3>
            <span className="text-xs text-slate-400">{selected.size_h} | {selected.modified_h}</span>
          </div>
          {content ? (
            activeTab === "wiki" || selected.name.endsWith(".md") ? (
              <div className="prose prose-slate prose-sm max-w-none bg-slate-50 rounded-lg p-4 max-h-[60vh] overflow-auto">
                <ReactMarkdown>
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
              Binary file — preview not available
            </div>
          )}
        </div>
      )}
    </div>
  );
}
