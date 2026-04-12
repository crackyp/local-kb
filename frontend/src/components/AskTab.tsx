"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";
import { useStatus } from "@/lib/StatusContext";
import type { QaHistoryEntry, AskResponse } from "@/types";
import {
  SectionCard,
  ModelSelect,
  CommandResultPanel,
  ActionButton,
} from "@/components/shared";

export function AskTab() {
  const { model, refresh: refreshStatus } = useStatus();
  const [question, setQuestion] = useState("");
  const [limit, setLimit] = useState(6);
  const [useFaiss, setUseFaiss] = useState(true);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [history, setHistory] = useState<QaHistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [promoted, setPromoted] = useState<string | null>(null);
  const [showCorrection, setShowCorrection] = useState(false);
  const [correction, setCorrection] = useState("");
  const [correctionSaved, setCorrectionSaved] = useState(false);

  const handlePromote = async (filename: string) => {
    try {
      const res = await api.promote(filename);
      if (res.returncode === 0) {
        setPromoted(filename);
        refreshStatus();
      }
    } catch (e) {
      console.error("Promote failed:", e);
    }
  };

  const handleCorrect = async () => {
    if (!correction.trim() || !question.trim()) return;
    try {
      const res = await api.correct(question.trim(), correction.trim());
      if (res.returncode === 0) {
        setCorrectionSaved(true);
      }
    } catch (e) {
      console.error("Correction failed:", e);
    }
  };

  const handleAsk = async () => {
    if (!question.trim() || !model) return;
    setLoading(true);
    setResult(null);
    setPromoted(null);
    setShowCorrection(false);
    setCorrection("");
    setCorrectionSaved(false);
    try {
      const res = await api.ask({ question: question.trim(), model, limit, use_faiss: useFaiss });
      setResult(res);
      setHistory((prev) => [
        { question: question.trim(), file: res.written_file || "unknown", time: new Date().toLocaleString() },
        ...prev.slice(0, 9),
      ]);
      refreshStatus();
    } catch (e) {
      setResult({ returncode: 1, output: String(e), command: "", answer: "", written_file: null });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard title="Ask the Wiki">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="What are the recurring claims about retrieval quality?"
          className="w-full h-32 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />

        <div className="grid grid-cols-3 gap-4 mt-4">
          <ModelSelect value={model} />
          <div>
            <label className="text-xs text-slate-500">Page limit (TF-IDF)</label>
            <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="w-full mt-1 px-2 py-1.5 border rounded-lg text-sm bg-white">
              {[3, 6, 10, 15, 25].map((n) => (
                <option key={n} value={n}>{n} pages</option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 pt-5">
            <input type="checkbox" checked={useFaiss} onChange={(e) => setUseFaiss(e.target.checked)} className="rounded" />
            <span className="text-sm">Use semantic search (FAISS)</span>
          </label>
        </div>

        <div className="mt-4">
          <ActionButton onClick={handleAsk} loading={loading} disabled={!question.trim()} loadingText="Thinking...">
            Run Q&A
          </ActionButton>
        </div>
      </SectionCard>

      {result && result.answer && (
        <SectionCard title="Answer">
          <div className="prose prose-slate prose-sm max-w-none bg-slate-50 rounded-lg p-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.answer}</ReactMarkdown>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
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
                className="px-3 py-1.5 bg-slate-100 text-slate-700 rounded text-xs font-medium hover:bg-slate-200"
              >
                Download {result.written_file}
              </button>
            )}
            {result.recommendations?.map((rec, i) =>
              rec.action === "promote" && rec.payload?.filename ? (
                promoted === rec.payload.filename ? (
                  <span key={i} className="px-3 py-1.5 bg-green-50 text-green-700 rounded text-xs font-medium">
                    Saved to KB
                  </span>
                ) : (
                  <button
                    key={i}
                    onClick={() => handlePromote(rec.payload!.filename)}
                    className="px-3 py-1.5 bg-amber-50 text-amber-800 border border-amber-200 rounded text-xs font-medium hover:bg-amber-100"
                  >
                    {rec.message}
                  </button>
                )
              ) : null
            )}
            {correctionSaved ? (
              <span className="px-3 py-1.5 bg-green-50 text-green-700 rounded text-xs font-medium">
                Correction saved — recompile to apply
              </span>
            ) : (
              <button
                onClick={() => setShowCorrection(!showCorrection)}
                className="px-3 py-1.5 bg-red-50 text-red-700 border border-red-200 rounded text-xs font-medium hover:bg-red-100"
              >
                {showCorrection ? "Cancel" : "Flag & Correct"}
              </button>
            )}
          </div>
          {showCorrection && !correctionSaved && (
            <div className="mt-4 space-y-2">
              <label className="text-xs text-slate-500">What is the correct information?</label>
              <textarea
                value={correction}
                onChange={(e) => setCorrection(e.target.value)}
                placeholder="Explain what the correct answer should be, with as much detail as you can provide..."
                className="w-full h-32 px-3 py-2 border border-red-200 rounded-lg text-sm focus:ring-2 focus:ring-red-400 focus:border-red-400"
              />
              <button
                onClick={handleCorrect}
                disabled={!correction.trim()}
                className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              >
                Save Correction to KB
              </button>
            </div>
          )}
        </SectionCard>
      )}

      <CommandResultPanel result={result} />

      {history.length > 0 && (
        <SectionCard title="Recent Q&A History">
          <div className="space-y-2">
            {history.map((entry, i) => (
              <div key={i} className="text-xs text-slate-600 bg-slate-50 px-3 py-2 rounded">
                <span className="font-medium">{entry.time}</span> — {entry.question.slice(0, 80)}
                {entry.question.length > 80 ? "..." : ""}
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  );
}
