export type View = "ingest" | "compile" | "ask" | "explorer" | "lint";

export interface FileMeta {
  name: string;
  size: number;
  size_h: string;
  modified: number;
  modified_h: string;
  rel: string;
}

export interface OllamaStatus {
  running: boolean;
  models: string[];
}

export interface StatusResponse {
  ollama: OllamaStatus;
  files: {
    raw: number;
    wiki: number;
    outputs: number;
  };
  faiss: "ready" | "stale" | "not_built" | "not_installed" | "unavailable" | "unknown";
}

export interface IngestUrlRequest {
  urls: string[];
  download_images: boolean;
  max_images: number;
  timeout: number;
}

export interface CompileRequest {
  model: string;
  force: boolean;
}

export interface AskRequest {
  question: string;
  model: string;
  limit: number;
  use_faiss: boolean;
}

export interface IndexRequest {
  force: boolean;
  model?: string;
}

export interface CommandResponse {
  returncode: number;
  output: string;
  command: string;
}

export interface AskResponse extends CommandResponse {
  answer: string;
  written_file: string | null;
}

export interface FilesResponse {
  files: FileMeta[];
  count: number;
}

export interface FileContentResponse {
  content: string | null;
  previewable: boolean;
  note?: string;
}

export interface QaHistoryEntry {
  question: string;
  file: string;
  time: string;
}
