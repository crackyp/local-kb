"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export function LintTab() {
  const [result, setResult] = useState<{ returncode: number; output: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const handleLint = async () => {
    setLoading(true);
    try {
      const res = await api.lint();
      setResult(res);
    } catch (e) {
      setResult({ returncode: 1, output: String(e) });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-2">Lint Wiki</h2>
        <p className="text-sm text-slate-500 mb-4">Checks broken markdown links and orphan pages.</p>
        <button
          onClick={handleLint}
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Linting..." : "Run Lint"}
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
          <pre className="text-xs text-slate-300 overflow-auto max-h-96">{result.output}</pre>
        </div>
      )}
    </div>
  );
}
