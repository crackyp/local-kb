"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";
import { useStatus } from "@/lib/StatusContext";
import type { CommandResponse, CompileRequest } from "@/types";

interface CompileContextValue {
  compiling: boolean;
  liveLines: string[];
  result: CommandResponse | null;
  startCompile: (data: CompileRequest) => Promise<void>;
  stopCompile: () => void;
}

const CompileContext = createContext<CompileContextValue | null>(null);

function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException) {
    return error.name === "AbortError";
  }
  return error instanceof Error && error.name === "AbortError";
}

export function CompileProvider({ children }: { children: ReactNode }) {
  const { refresh: refreshStatus } = useStatus();
  const [compiling, setCompiling] = useState(false);
  const [liveLines, setLiveLines] = useState<string[]>([]);
  const [result, setResult] = useState<CommandResponse | null>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const liveLinesRef = useRef<string[]>([]);

  const pushLine = useCallback((line: string) => {
    setLiveLines((prev) => {
      const next = [...prev, line];
      liveLinesRef.current = next;
      return next;
    });
  }, []);

  const startCompile = useCallback(
    async (data: CompileRequest) => {
      if (abortRef.current) return;

      setCompiling(true);
      setResult(null);
      setLiveLines([]);
      liveLinesRef.current = [];

      try {
        const { promise, abort } = api.compileStream(data, pushLine);
        abortRef.current = abort;
        const res = await promise;
        abortRef.current = null;
        setResult(res);
        setLiveLines([]);
        liveLinesRef.current = [];
        if (res.returncode === 0) {
          refreshStatus();
        }
      } catch (error) {
        abortRef.current = null;
        if (isAbortError(error)) {
          const output = liveLinesRef.current.length
            ? `${liveLinesRef.current.join("\n")}\nCompile stopped by user.`
            : "Compile stopped by user.";
          setResult({ returncode: 130, output, command: "" });
        } else {
          setResult({ returncode: 1, output: String(error), command: "" });
        }
        setLiveLines([]);
        liveLinesRef.current = [];
      } finally {
        setCompiling(false);
      }
    },
    [pushLine, refreshStatus],
  );

  const stopCompile = useCallback(() => {
    abortRef.current?.();
  }, []);

  const value = useMemo(
    () => ({ compiling, liveLines, result, startCompile, stopCompile }),
    [compiling, liveLines, result, startCompile, stopCompile],
  );

  return <CompileContext.Provider value={value}>{children}</CompileContext.Provider>;
}

export function useCompile() {
  const ctx = useContext(CompileContext);
  if (!ctx) throw new Error("useCompile must be used within CompileProvider");
  return ctx;
}
