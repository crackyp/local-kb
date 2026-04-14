"use client";

import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { useStatus } from "@/lib/StatusContext";
import { useCompile } from "@/lib/CompileContext";
import type { CommandResponse } from "@/types";
import {
  SectionCard,
  ModelSelect,
  CommandResultPanel,
  RecommendationBar,
  ActionButton,
} from "@/components/shared";

export function CompileTab() {
  const { model, refresh: refreshStatus } = useStatus();
  const { compiling, liveLines, result, startCompile, stopCompile } = useCompile();
  const [force, setForce] = useState(false);
  const [maxChars, setMaxChars] = useState(55000);
  const [chunking, setChunking] = useState(false);
  const [idxForce, setIdxForce] = useState(false);
  const [indexResult, setIndexResult] = useState<CommandResponse | null>(null);
  const [indexing, setIndexing] = useState(false);
  const liveRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (liveRef.current) {
      liveRef.current.scrollTop = liveRef.current.scrollHeight;
    }
  }, [liveLines]);

  const handleCompile = async () => {
    setIndexResult(null);
    await startCompile({ model, force, max_source_chars: maxChars, chunking });
  };

  const handleBuildIndex = async () => {
    setIndexing(true);
    setIndexResult(null);
    try {
      const res = await api.buildIndex({ force: idxForce });
      setIndexResult(res);
      refreshStatus();
    } catch (e) {
      setIndexResult({ returncode: 1, output: String(e), command: "" });
    } finally {
      setIndexing(false);
    }
  };

  const displayResult = indexResult ?? result;

  return (
    <div className="space-y-6">
      <SectionCard title="Compile Wiki">
        <div className="grid grid-cols-3 gap-4 mb-4">
          <ModelSelect value={model} />
          <div>
            <label className="text-xs text-slate-500">Max source chars</label>
            <select value={maxChars} onChange={(e) => setMaxChars(Number(e.target.value))} className="w-full mt-1 px-2 py-1.5 border rounded-lg text-sm bg-white">
              <option value={16000}>16K (small context)</option>
              <option value={32000}>32K</option>
              <option value={55000}>55K (default)</option>
              <option value={100000}>100K</option>
              <option value={200000}>200K (large context)</option>
            </select>
          </div>
          <div className="flex flex-col gap-2 pt-5">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} className="rounded" />
              <span className="text-sm">Force recompile all docs</span>
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={chunking} onChange={(e) => setChunking(e.target.checked)} className="rounded" />
              <span className="text-sm">Chunk long documents (slower, more complete)</span>
            </label>
          </div>
        </div>
        <ActionButton onClick={handleCompile} loading={compiling} loadingText="Compiling...">
          Run Compile
        </ActionButton>
        {compiling && (
          <button
            onClick={stopCompile}
            className="ml-3 px-4 py-2 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700"
          >
            Stop Compile
          </button>
        )}
      </SectionCard>

      <SectionCard title="FAISS Index">
        <div className="flex items-center gap-4 mb-4">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={idxForce} onChange={(e) => setIdxForce(e.target.checked)} className="rounded" />
            <span className="text-sm">Force rebuild index</span>
          </label>
        </div>
        <ActionButton onClick={handleBuildIndex} loading={indexing} loadingText="Building..." variant="secondary">
          Build FAISS Index
        </ActionButton>
      </SectionCard>

      {compiling && liveLines.length > 0 && (
        <div className="bg-slate-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-blue-400 text-sm animate-pulse">Compiling...</span>
          </div>
          <pre ref={liveRef} className="text-xs text-slate-300 overflow-auto max-h-64">{liveLines.join("\n")}</pre>
        </div>
      )}

      <CommandResultPanel result={displayResult} />

      {displayResult?.recommendations && (
        <RecommendationBar
          recommendations={displayResult.recommendations}
          onAction={(rec) => {
            if (rec.action === "rebuild_index") handleBuildIndex();
          }}
          loading={indexing}
        />
      )}
    </div>
  );
}
