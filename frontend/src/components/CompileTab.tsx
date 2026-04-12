"use client";

import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { useStatus } from "@/lib/StatusContext";
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
  const [force, setForce] = useState(false);
  const [maxChars, setMaxChars] = useState(55000);
  const [chunking, setChunking] = useState(false);
  const [idxForce, setIdxForce] = useState(false);
  const [result, setResult] = useState<CommandResponse | null>(null);
  const [liveLines, setLiveLines] = useState<string[]>([]);
  const [compiling, setCompiling] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const liveRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (liveRef.current) {
      liveRef.current.scrollTop = liveRef.current.scrollHeight;
    }
  }, [liveLines]);

  const handleCompile = async () => {
    setCompiling(true);
    setResult(null);
    setLiveLines([]);
    try {
      const { promise } = api.compileStream(
        { model, force, max_source_chars: maxChars, chunking },
        (line) => setLiveLines((prev) => [...prev, line]),
      );
      const res = await promise;
      setResult(res);
      setLiveLines([]);
      refreshStatus();
    } catch (e) {
      setResult({ returncode: 1, output: String(e), command: "" });
      setLiveLines([]);
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
      refreshStatus();
    } catch (e) {
      setResult({ returncode: 1, output: String(e), command: "" });
    } finally {
      setIndexing(false);
    }
  };

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

      <CommandResultPanel result={result} />

      {result?.recommendations && (
        <RecommendationBar
          recommendations={result.recommendations}
          onAction={(rec) => {
            if (rec.action === "rebuild_index") handleBuildIndex();
          }}
          loading={indexing}
        />
      )}
    </div>
  );
}
