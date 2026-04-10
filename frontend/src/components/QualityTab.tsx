"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "@/lib/api";
import type { StatusResponse, CommandResponse, HealthCheckResponse } from "@/types";

export function QualityTab() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [model, setModel] = useState("");

  // Lint state
  const [lintResult, setLintResult] = useState<CommandResponse | null>(null);
  const [linting, setLinting] = useState(false);

  // Health check state
  const [healthResult, setHealthResult] = useState<HealthCheckResponse | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    api.getStatus().then((s) => {
      setStatus(s);
      if (s?.ollama.models?.length && !model) {
        setModel(s.ollama.models[0]);
      }
    }).catch(console.error);
  }, []);

  const handleLint = async () => {
    setLinting(true);
    setLintResult(null);
    try {
      const res = await api.lint();
      setLintResult(res);
    } catch (e) {
      setLintResult({ returncode: 1, output: String(e), command: "" });
    } finally {
      setLinting(false);
    }
  };

  const handleHealthCheck = async () => {
    if (!model) return;
    setChecking(true);
    setHealthResult(null);
    try {
      const res = await api.healthCheck({ model });
      setHealthResult(res);
    } catch (e) {
      setHealthResult({ returncode: 1, output: String(e), command: "", report: "" });
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Lint Section */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-2">Lint Wiki</h2>
        <p className="text-sm text-slate-500 mb-4">Check broken markdown links and orphan pages.</p>
        <button
          onClick={handleLint}
          disabled={linting}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {linting ? "Linting..." : "Run Lint"}
        </button>
      </div>

      {lintResult && (
        <>
          <div className="bg-slate-800 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              {lintResult.returncode === 0 ? (
                <span className="text-green-400 text-sm">Done</span>
              ) : (
                <span className="text-red-400 text-sm">Failed (exit {lintResult.returncode})</span>
              )}
            </div>
            <pre className="text-xs text-slate-300 overflow-auto max-h-64">{lintResult.output}</pre>
          </div>
          {lintResult.recommendations && lintResult.recommendations.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {lintResult.recommendations.map((rec, i) => (
                <div key={i} className="px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
                  {rec.message}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Health Check Section */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-2">Health Check</h2>
        <p className="text-sm text-slate-500 mb-4">
          LLM-powered review: find contradictions, unexplained topics, unsourced claims, and knowledge gaps.
        </p>
        <div className="flex items-center gap-4">
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
          <button
            onClick={handleHealthCheck}
            disabled={checking || !model}
            className="mt-5 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {checking ? "Reviewing..." : "Run Health Check"}
          </button>
        </div>
      </div>

      {healthResult && healthResult.report && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="font-semibold text-slate-900 mb-3">Health Check Report</h3>
          <div className="prose prose-slate prose-sm max-w-none bg-slate-50 rounded-lg p-4">
            <ReactMarkdown>{healthResult.report}</ReactMarkdown>
          </div>
        </div>
      )}

      {healthResult && (
        <div className="bg-slate-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            {healthResult.returncode === 0 ? (
              <span className="text-green-400 text-sm">Done</span>
            ) : (
              <span className="text-red-400 text-sm">Failed (exit {healthResult.returncode})</span>
            )}
          </div>
          <pre className="text-xs text-slate-300 overflow-auto max-h-64">{healthResult.output}</pre>
        </div>
      )}
    </div>
  );
}
