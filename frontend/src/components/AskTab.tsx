"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { StatusResponse, QaHistoryEntry, AskResponse } from "@/types";

export function AskTab() {
  const [question, setQuestion] = useState("");
  const [model, setModel] = useState("");
  const [limit, setLimit] = useState(6);
  const [useFaiss, setUseFaiss] = useState(true);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [history, setHistory] = useState<QaHistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getStatus().then(setStatus).catch(console.error);
  }, []);

  useEffect(() => {
    if (!model && status?.ollama.models && status.ollama.models.length > 0) {
      setModel(status.ollama.models[0]);
    }
  }, [status, model]);

  const handleAsk = async () => {
    if (!question.trim()) return;
    if (!model) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await api.ask({ question: question.trim(), model, limit, use_faiss: useFaiss });
      setResult(res);
      setHistory((prev) => [
        { question: question.trim(), file: res.written_file || "unknown", time: new Date().toLocaleString() },
        ...prev.slice(0, 9),
      ]);
    } catch (e) {
      setResult({ returncode: 1, output: String(e), command: "", answer: "", written_file: null });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Ask the Wiki</h2>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="What are the recurring claims about retrieval quality?"
          className="w-full h-32 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />

        <div className="grid grid-cols-3 gap-4 mt-4">
          <div>
            <label className="text-xs text-slate-500">Model</label>
            {status?.ollama.models && status.ollama.models.length > 0 ? (
              <select value={model} onChange={(e) => setModel(e.target.value)} className="w-full mt-1 px-2 py-1.5 border rounded-lg text-sm bg-white">
                {status.ollama.models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            ) : (
              <input type="text" value={model} onChange={(e) => setModel(e.target.value)} className="w-full mt-1 px-2 py-1.5 border rounded-lg text-sm" />
            )}
          </div>
          <div>
            <label className="text-xs text-slate-500">Page limit (TF-IDF)</label>
            <input type="number" min={1} max={30} value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="w-full mt-1 px-2 py-1.5 border rounded-lg text-sm" />
          </div>
          <label className="flex items-center gap-2 pt-5">
            <input type="checkbox" checked={useFaiss} onChange={(e) => setUseFaiss(e.target.checked)} className="rounded" />
            <span className="text-sm">Use semantic search (FAISS)</span>
          </label>
        </div>

        <button
          onClick={handleAsk}
          disabled={loading || !question.trim()}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Thinking..." : "Run Q&A"}
        </button>
      </div>

      {result && result.answer && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="font-semibold text-slate-900 mb-3">Answer</h3>
          <div className="prose prose-sm max-w-none">
            <pre className="whitespace-pre-wrap text-sm text-slate-700">{result.answer}</pre>
          </div>
          {result.written_file && (
            <button
              onClick={() => {
                const blob = new Blob([result.answer], { type: "text/markdown" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = result.written_file!;
                a.click();
              }}
              className="mt-4 px-3 py-1.5 bg-slate-100 text-slate-700 rounded text-xs font-medium hover:bg-slate-200"
            >
              Download {result.written_file}
            </button>
          )}
        </div>
      )}

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

      {history.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="font-semibold text-slate-900 mb-3">Recent Q&A History</h3>
          <div className="space-y-2">
            {history.map((entry, i) => (
              <div key={i} className="text-xs text-slate-600 bg-slate-50 px-3 py-2 rounded">
                <span className="font-medium">{entry.time}</span> — {entry.question.slice(0, 80)}
                {entry.question.length > 80 ? "..." : ""}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
