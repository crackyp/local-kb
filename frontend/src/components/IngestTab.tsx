"use client";

import { useState } from "react";
import { api } from "@/lib/api";

type IngestMode = "files" | "url" | "pdf";

const SUB_TABS: { id: IngestMode; label: string }[] = [
  { id: "files", label: "Files" },
  { id: "url", label: "URL" },
  { id: "pdf", label: "PDF" },
];

export function IngestTab() {
  const [mode, setMode] = useState<IngestMode>("files");

  // Files state
  const [paths, setPaths] = useState("");

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

  const handleIngestPath = async () => {
    const lines = paths.split("\n").map((l) => l.trim()).filter(Boolean);
    if (!lines.length) return;
    setLoading(true);
    setResult(null);
    try {
      setResult(await api.ingestPath(lines));
    } catch (e) {
      setResult({ returncode: 1, output: String(e) });
    } finally {
      setLoading(false);
    }
  };

  const handleIngestUrl = async () => {
    const lines = urls.split("\n").map((l) => l.trim()).filter(Boolean);
    if (!lines.length) return;
    setLoading(true);
    setResult(null);
    try {
      setResult(await api.ingestUrl({ urls: lines, download_images: downloadImages, max_images: maxImages, timeout: urlTimeout }));
    } catch (e) {
      setResult({ returncode: 1, output: String(e) });
    } finally {
      setLoading(false);
    }
  };

  const handleIngestPdf = async () => {
    if (!pdfFiles.length) return;
    setLoading(true);
    setResult(null);
    try {
      setResult(await api.ingestPdf(pdfFiles, maxPages, copyOriginal));
      setPdfFiles([]);
    } catch (e) {
      setResult({ returncode: 1, output: String(e) });
    } finally {
      setLoading(false);
    }
  };

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
              <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-blue-400 transition-colors">
                <div className="text-4xl mb-3">📁</div>
                <div className="text-base font-medium text-slate-700 mb-1">Drop files here or click to upload</div>
                <div className="text-sm text-slate-500">Supports any file type</div>
                <input type="file" multiple className="hidden" id="file-upload" />
                <label htmlFor="file-upload" className="mt-4 inline-block px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 cursor-pointer">
                  Choose Files
                </label>
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">Or ingest by path / glob</label>
                <textarea
                  value={paths}
                  onChange={(e) => setPaths(e.target.value)}
                  placeholder="/Users/you/Research/*.md&#10;/Users/you/Research/*.txt"
                  className="mt-2 w-full h-28 px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <button
                  onClick={handleIngestPath}
                  disabled={loading || !paths.trim()}
                  className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? "Ingesting..." : "Ingest by Path"}
                </button>
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
              <button
                onClick={handleIngestUrl}
                disabled={loading || !urls.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Fetching..." : "Ingest URL(s)"}
              </button>
            </div>
          )}

          {mode === "pdf" && (
            <div className="space-y-4">
              <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-blue-400 transition-colors">
                <div className="text-4xl mb-3">📄</div>
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
              <button
                onClick={handleIngestPdf}
                disabled={loading || !pdfFiles.length}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Extracting..." : "Extract PDF Text"}
              </button>
            </div>
          )}
        </div>
      </div>

      {result && (
        <div className="bg-slate-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            {result.returncode === 0 ? (
              <span className="text-green-400 text-sm">✓ Done</span>
            ) : (
              <span className="text-red-400 text-sm">✗ Failed (exit {result.returncode})</span>
            )}
          </div>
          <pre className="text-xs text-slate-300 overflow-auto max-h-64">{result.output}</pre>
        </div>
      )}
    </div>
  );
}
