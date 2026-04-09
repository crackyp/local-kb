"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { StatusResponse } from "@/types";

export function CompileTab() {
  const [model, setModel] = useState("");
  const [force, setForce] = useState(false);
  const [idxForce, setIdxForce] = useState(false);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [result, setResult] = useState<{ returncode: number; output: string } | null>(null);
  const [compiling, setCompiling] = useState(false);
  const [indexing, setIndexing] = useState(false);

  useEffect(() => {
    api.getStatus().then((s) => {
      setStatus(s);
      if (s?.ollama.models?.length && !model) {
        setModel(s.ollama.models[0]);
      }
    }).catch(console.error);
  }, []);

  const handleCompile = async () => {
    setCompiling(true);
    setResult(null);
    try {
      const res = await api.compile({ model, force });
      setResult(res);
    } catch (e) {
      setResult({ returncode: 1, output: String(e) });
    } finally {
      setCompiling(false);
    }
  };

  const handleBuildIndex = async () => {
    setIndexing(true);
    setResult(null);
    try {
      const res = await api.buildIndex({ force: idxForce });
      setResult(res);
    } catch (e) {
      setResult({ returncode: 1, output: String(e) });
    } finally {
      setIndexing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Compile Wiki</h2>
        <div className="grid grid-cols-2 gap-4 mb-4">
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
          <label className="flex items-center gap-2 pt-5">
            <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} className="rounded" />
            <span className="text-sm">Force recompile all docs</span>
          </label>
        </div>
        <button
          onClick={handleCompile}
          disabled={compiling}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {compiling ? "Compiling..." : "Run Compile"}
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">FAISS Index</h2>
        <div className="flex items-center gap-4 mb-4">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={idxForce} onChange={(e) => setIdxForce(e.target.checked)} className="rounded" />
            <span className="text-sm">Force rebuild index</span>
          </label>
        </div>
        <button
          onClick={handleBuildIndex}
          disabled={indexing}
          className="px-4 py-2 bg-slate-700 text-white rounded-lg text-sm font-medium hover:bg-slate-600 disabled:opacity-50"
        >
          {indexing ? "Building..." : "Build FAISS Index"}
        </button>
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
