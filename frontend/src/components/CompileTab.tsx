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
  const { model, refresh: refreshStatus, invalidate } = useStatus();
  const { compiling, liveLines, result, startCompile, stopCompile } = useCompile();
  const [force, setForce] = useState(false);
  const [maxChars, setMaxChars] = useState(524288);
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
    await startCompile({ model, force, max_source_chars: maxChars });
  };

  const handleBuildIndex = async () => {
    setIndexing(true);
    setIndexResult(null);
    try {
      const res = await api.buildIndex({ force: idxForce });
      setIndexResult(res);
      refreshStatus();
      // Fresh embeddings mean fresh similarity edges.
      invalidate();
    } catch (e) {
      setIndexResult({ returncode: 1, output: String(e), command: "" });
    } finally {
      setIndexing(false);
    }
  };

  const displayResult = indexResult ?? result;

  return (
    <div className="space-y-6">
      <SectionCard title="Compile Wiki" description="Generate wiki pages from raw sources using the LLM.">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <ModelSelect value={model} />
          <div>
            <label className="text-xs text-zinc-500">Max source chars</label>
            <select value={maxChars} onChange={(e) => setMaxChars(Number(e.target.value))} className="w-full mt-1 px-2 py-1.5 border border-zinc-300 rounded text-sm bg-white focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition-colors duration-150 ease-out">
              <option value={32000}>32K</option>
              <option value={55000}>55K</option>
              <option value={100000}>100K</option>
              <option value={192000}>192K (default)</option>
              <option value={250000}>250K (large context)</option>
              <option value={524288}>512K (max context)</option>
            </select>
          </div>
          <div className="flex flex-col gap-2 pt-5 sm:pt-0">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} className="rounded" />
              <span className="text-sm">Force recompile all docs</span>
            </label>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ActionButton onClick={handleCompile} loading={compiling} loadingText="Compiling...">
            Run Compile
          </ActionButton>
          {compiling && (
            <button
              onClick={stopCompile}
              className="ml-3 px-4 py-2 rounded text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors duration-150 ease-out"
            >
              Stop Compile
            </button>
          )}
        </div>
      </SectionCard>

      <SectionCard title="FAISS Index" description="Build or rebuild the vector search index.">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-4">
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
        <div className="bg-zinc-800 rounded p-4 transition-colors duration-150 ease-out">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-violet-400 text-sm animate-pulse">Compiling...</span>
          </div>
          <pre ref={liveRef} className="text-xs text-zinc-300 overflow-auto max-h-64">{liveLines.join("\n")}</pre>
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
