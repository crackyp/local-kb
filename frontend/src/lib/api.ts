const API_BASE = "http://127.0.0.1:8000";

import type {
  StatusResponse,
  CommandResponse,
  AskResponse,
  HealthCheckResponse,
  FilesResponse,
  FileContentResponse,
  IngestUrlRequest,
  CompileRequest,
  AskRequest,
  IndexRequest,
  HealthCheckRequest,
} from "@/types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

export const api = {
  getStatus: () => request<StatusResponse>("/api/status"),

  ingestUpload: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request<{ saved: { name: string; size: number }[]; count: number }>(
      "/api/ingest/upload",
      { method: "POST", body: form }
    );
  },

  ingestPath: (paths: string[]) =>
    request<CommandResponse>("/api/ingest/path", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paths }),
    }),

  ingestUrl: (data: IngestUrlRequest) =>
    request<CommandResponse>("/api/ingest/url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  ingestPdf: (files: File[], maxPages: number, copyOriginal: boolean) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    form.append("max_pages", String(maxPages));
    form.append("copy_original", String(copyOriginal));
    return request<CommandResponse>("/api/ingest/pdf", {
      method: "POST",
      body: form,
    });
  },

  compile: (data: CompileRequest) =>
    request<CommandResponse>("/api/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  buildIndex: (data: IndexRequest) =>
    request<CommandResponse>("/api/index", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  ask: (data: AskRequest) =>
    request<AskResponse>("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  lint: () => request<CommandResponse>("/api/lint", { method: "POST" }),

  promote: (filename: string) =>
    request<CommandResponse>("/api/promote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    }),

  healthCheck: (data: HealthCheckRequest) =>
    request<HealthCheckResponse>("/api/health-check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  listFiles: (category: "raw" | "wiki" | "outputs") =>
    request<FilesResponse>(`/api/files/${category}`),

  getFile: (category: "raw" | "wiki" | "outputs", path: string) =>
    request<FileContentResponse>(`/api/file/${category}/${encodeURIComponent(path)}`),

  deleteFile: (category: "raw" | "wiki" | "outputs", path: string) =>
    request<{ success: boolean; deleted: string }>(
      `/api/file/${category}/${encodeURIComponent(path)}`,
      { method: "DELETE" }
    ),
};
