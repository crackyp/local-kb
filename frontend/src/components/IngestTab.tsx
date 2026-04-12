"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useStatus } from "@/lib/StatusContext";
import { CommandResultPanel, ActionButton } from "@/components/shared";

type IngestMode = "files" | "url" | "pdf";

const SUB_TABS: { id: IngestMode; label: string }[] = [
  { id: "files", label: "Files" },
  { id: "url", label: "URL" },
  { id: "pdf", label: "PDF" },
];

export function IngestTab() {
  const { refresh: refreshStatus } = useStatus();
  const [mode, setMode] = useState<IngestMode>("files");

  // Files state
  const [paths, setPaths] = useState("");
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);

  // URL state
  const [urls, setUrls] = useState("");
  const [downloadImages, setDownloadImages] = useState(false);
  const [maxImages, setMaxImages] = useState(20);
  const [urlTimeout, setUrlTimeout] = useState(30);

  // PDF state
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);
  const [maxPages, setMaxPages] = useState(0);
  const [copyOriginal, setCopyOriginal] = useState(false);

  const [result, setResult] = useState<{ returncode: number; output: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const addFiles = (files: File[]) => {
    setUploadFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name + f.size));
      const unique = files.filter((f) => !existing.has(f.name + f.size));
      return [...prev, ...unique];
    });
  };

  const removeFile = (index: number) => {
    setUploadFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const withRefresh = async (fn: () => Promise<void>) => {
    setLoading(true);
    setResult(null);
    try {
      await fn();
      refreshStatus();
    } finally {
      setLoading(false);
    }
  };

  const handleUploadFiles = () =>
    withRefresh(async () => {
      if (!uploadFiles.length) return;
      const res = await api.ingestUpload(uploadFiles);
      setResult({ returncode: 0, output: `Uploaded ${res.count} file(s):\n${res.saved.map((s) => `  ${s.name} (${(s.size / 1024).toFixed(1)} KB)`).join("\n")}` });
      setUploadFiles([]);
    });

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length) {
      addFiles(files);
    } else {
      const text = e.dataTransfer.getData("text/plain") || e.dataTransfer.getData("text");
      if (text?.trim()) {
        setPaths((prev) => (prev ? prev + "\n" + text.trim() : text.trim()));
      }
    }
  };

  const handleIngestPath = () =>
    withRefresh(async () => {
      const lines = paths.split("\n").map((l) => l.trim()).filter(Boolean);
      if (!lines.length) return;
      setResult(await api.ingestPath(lines));
    });

  const handleIngestUrl = () =>
    withRefresh(async () => {
      const lines = urls.split("\n").map((l) => l.trim()).filter(Boolean);
      if (!lines.length) return;
      setResult(await api.ingestUrl({ urls: lines, download_images: downloadImages, max_images: maxImages, timeout: urlTimeout }));
    });

  const handleIngestPdf = () =>
    withRefresh(async () => {
      if (!pdfFiles.length) return;
      setResult(await api.ingestPdf(pdfFiles, maxPages, copyOriginal));
      setPdfFiles([]);
    });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Ingest</h1>
        <p className="text-sm text-slate-500 mt-1">Add source material to your knowledge base</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="flex border-b border-slate-200">
          {SUB_TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => { setMode(tab.id); setResult(null); }}
              className={`px-5 py-3 text-sm font-medium transition-colors ${
                mode === tab.id
                  ? "text-blue-600 border-b-2 border-blue-600 bg-blue-50"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="p-6">
          {mode === "files" && (
            <div className="space-y-5">
              <div
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
                  dragging ? "border-blue-500 bg-blue-50" : "border-slate-300 hover:border-blue-400"
                }`}
              >
                <div className="text-base font-medium text-slate-700 mb-1">Drop files here or click to upload</div>
                <div className="text-sm text-slate-500">Supports any file type</div>
                <input
                  type="file"
                  multiple
                  className="hidden"
                  id="file-upload"
                  onChange={(e) => {
                    addFiles(Array.from(e.target.files || []));
                    e.target.value = "";
                  }}
                />
                <label htmlFor="file-upload" className="mt-4 inline-block px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 cursor-pointer">
                  Choose Files
                </label>
              </div>
              {uploadFiles.length > 0 && (
                <div className="space-y-2">
                  <div className="text-sm font-medium text-slate-700">Selected ({uploadFiles.length})</div>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {uploadFiles.map((f, i) => (
                      <div key={f.name + i} className="flex items-center justify-between text-xs text-slate-600 bg-slate-50 px-2 py-1.5 rounded">
                        <span>{f.name} ({(f.size / 1024).toFixed(1)} KB)</span>
                        <button
                          onClick={() => removeFile(i)}
                          className="text-red-500 hover:text-red-700 px-1.5 py-0.5 rounded hover:bg-red-50"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                  <ActionButton onClick={handleUploadFiles} loading={loading} loadingText="Uploading...">
                    Upload {uploadFiles.length} file(s)
                  </ActionButton>
                </div>
              )}
              <div>
                <label className="text-sm font-medium text-slate-700">Or ingest by path / glob</label>
                <textarea
                  value={paths}
                  onChange={(e) => setPaths(e.target.value)}
                  onDrop={(e) => {
                    e.preventDefault();
                    const text = e.dataTransfer.getData("text/plain") || e.dataTransfer.getData("text");
                    if (text?.trim()) {
                      setPaths((prev) => (prev ? prev + "\n" + text.trim() : text.trim()));
                    }
                  }}
                  placeholder="/Users/you/Research/*.md&#10;/Users/you/Research/*.txt"
                  className="mt-2 w-full h-28 px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <div className="mt-2">
                  <ActionButton onClick={handleIngestPath} loading={loading} disabled={!paths.trim()} loadingText="Ingesting...">
                    Ingest by Path
                  </ActionButton>
                </div>
              </div>
            </div>
          )}

          {mode === "url" && (
            <div className="space-y-4">
              <textarea
                value={urls}
                onChange={(e) => setUrls(e.target.value)}
                placeholder="https://example.com&#10;https://arxiv.org/abs/..."
                className="w-full h-28 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <div className="grid grid-cols-3 gap-4">
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={downloadImages} onChange={(e) => setDownloadImages(e.target.checked)} className="rounded" />
                  <span className="text-sm">Download images</span>
                </label>
                <div>
                  <label className="text-xs text-slate-500">Max images</label>
                  <input type="number" min={1} max={200} value={maxImages} onChange={(e) => setMaxImages(Number(e.target.value))} className="w-full mt-1 px-2 py-1 border rounded text-sm" />
                </div>
                <div>
                  <label className="text-xs text-slate-500">Timeout (sec)</label>
                  <input type="number" min={5} max={300} value={urlTimeout} onChange={(e) => setUrlTimeout(Number(e.target.value))} className="w-full mt-1 px-2 py-1 border rounded text-sm" />
                </div>
              </div>
              <ActionButton onClick={handleIngestUrl} loading={loading} disabled={!urls.trim()} loadingText="Fetching...">
                Ingest URL(s)
              </ActionButton>
            </div>
          )}

          {mode === "pdf" && (
            <div className="space-y-4">
              <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-blue-400 transition-colors">
                <div className="text-base font-medium text-slate-700 mb-1">Drop PDF files here</div>
                <div className="text-sm text-slate-500">Extracts text into markdown files</div>
                <input type="file" accept=".pdf" multiple onChange={(e) => setPdfFiles(Array.from(e.target.files || []))} className="hidden" id="pdf-upload" />
                <label htmlFor="pdf-upload" className="mt-4 inline-block px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 cursor-pointer">
                  Choose PDFs
                </label>
              </div>
              {pdfFiles.length > 0 && (
                <div>
                  <div className="text-sm font-medium text-slate-700 mb-2">Selected ({pdfFiles.length})</div>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {pdfFiles.map((f) => (
                      <div key={f.name} className="text-xs text-slate-600 bg-slate-50 px-2 py-1 rounded">
                        {f.name} ({(f.size / 1024).toFixed(1)} KB)
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-slate-500">Max pages (0 = all)</label>
                  <input type="number" min={0} max={5000} value={maxPages} onChange={(e) => setMaxPages(Number(e.target.value))} className="w-full mt-1 px-2 py-1 border rounded text-sm" />
                </div>
                <label className="flex items-center gap-2 pt-5">
                  <input type="checkbox" checked={copyOriginal} onChange={(e) => setCopyOriginal(e.target.checked)} className="rounded" />
                  <span className="text-sm">Copy original PDF</span>
                </label>
              </div>
              <ActionButton onClick={handleIngestPdf} loading={loading} disabled={!pdfFiles.length} loadingText="Extracting...">
                Extract PDF Text
              </ActionButton>
            </div>
          )}
        </div>
      </div>

      <CommandResultPanel result={result} />
    </div>
  );
}
