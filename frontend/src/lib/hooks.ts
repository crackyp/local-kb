"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { FileMeta } from "@/types";

/**
 * Generic hook for API actions that follow the loading → result → done pattern.
 * Returns `[execute, result, loading, clear]`.
 */
export function useCommandAction<TResult, TArgs extends unknown[] = []>(
  action: (...args: TArgs) => Promise<TResult>,
) {
  const [result, setResult] = useState<TResult | null>(null);
  const [loading, setLoading] = useState(false);

  const execute = useCallback(
    async (...args: TArgs) => {
      setLoading(true);
      setResult(null);
      try {
        const res = await action(...args);
        setResult(res);
        return res;
      } catch (e) {
        throw e;
      } finally {
        setLoading(false);
      }
    },
    [action],
  );

  const clear = useCallback(() => setResult(null), []);

  return [execute, result, loading, clear] as const;
}

/**
 * Hook to fetch a file listing for a given category, with refresh support.
 */
export function useFileList(category: "raw" | "wiki" | "outputs") {
  const [files, setFiles] = useState<FileMeta[]>([]);
  const [count, setCount] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const res = await api.listFiles(category);
      setFiles(res.files);
      setCount(res.count);
    } catch (e) {
      console.error(`Failed to list ${category}:`, e);
    }
  }, [category]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const removeLocal = useCallback((rel: string) => {
    setFiles((prev) => prev.filter((f) => f.rel !== rel));
    setCount((c) => Math.max(0, c - 1));
  }, []);

  return { files, count, refresh, removeLocal };
}
