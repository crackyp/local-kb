"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { StatusResponse } from "@/types";
import { api } from "@/lib/api";

interface StatusContextValue {
  status: StatusResponse | null;
  refresh: () => Promise<void>;
  /** Selected model shared across all tabs */
  model: string;
  setModel: (m: string) => void;
}

const StatusContext = createContext<StatusContextValue | null>(null);

const POLL_MS = 10_000;

export function StatusProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [model, setModel] = useState("");

  const refresh = useCallback(async () => {
    try {
      const s = await api.getStatus();
      setStatus(s);
    } catch (e) {
      console.error("Status fetch failed:", e);
    }
  }, []);

  // Initial fetch + polling
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  // Auto-select first model when models arrive and none chosen yet
  useEffect(() => {
    if (!model && status?.ollama.models?.length) {
      setModel(status.ollama.models[0]);
    }
  }, [status, model]);

  return (
    <StatusContext.Provider value={{ status, refresh, model, setModel }}>
      {children}
    </StatusContext.Provider>
  );
}

export function useStatus() {
  const ctx = useContext(StatusContext);
  if (!ctx) throw new Error("useStatus must be used within StatusProvider");
  return ctx;
}
