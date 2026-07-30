"use client";

import type { ReactNode } from "react";
import type { CommandResponse, Recommendation } from "@/types";
import { useStatus } from "@/lib/StatusContext";

/* ── SectionCard ────────────────────────────────────────────── */

export function SectionCard({
  title,
  description,
  children,
  accent = false,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  accent?: boolean;
}) {
  return (
    <div className={`bg-white rounded shadow-sm border border-zinc-200 p-4 md:p-6 ${accent ? "border-l-2 border-l-violet-500" : ""} transition-colors duration-150 ease-out`}>
      <h2 className="text-lg font-semibold text-zinc-900 mb-2 tracking-tight">{title}</h2>
      {description && (
        <p className="text-sm text-zinc-500 mb-4">{description}</p>
      )}
      {children}
    </div>
  );
}

/* ── CommandResultPanel ─────────────────────────────────────── */

export function CommandResultPanel({
  result,
  maxHeight = "max-h-64",
}: {
  result: Pick<CommandResponse, "returncode" | "output"> | null;
  maxHeight?: string;
}) {
  if (!result) return null;
  return (
    <div className="bg-zinc-800 rounded p-4 transition-colors duration-150 ease-out">
      <div className="flex items-center gap-2 mb-2">
        {result.returncode === 0 ? (
          <span className="text-green-400 text-sm">Done</span>
        ) : (
          <span className="text-red-400 text-sm">
            Failed (exit {result.returncode})
          </span>
        )}
      </div>
      <pre className={`text-xs text-zinc-300 overflow-auto ${maxHeight}`}>
        {result.output}
      </pre>
    </div>
  );
}

/* ── ModelSelect ────────────────────────────────────────────── */

/** Short provider name used for disambiguating prefixes. Must match
 *  `list_models()` / `resolve_provider()` in local_kb/llamacpp.py. */
function providerShort(name: string): string {
  return name === "llamacpp" ? "local" : name.replace("llamacpp_", "");
}

export function ModelSelect({
  value,
  onChange,
  label = "Model",
  tone = "light",
}: {
  value?: string;
  onChange?: (model: string) => void;
  label?: string;
  /** "dark" for the sidebar; tabs render on white SectionCards. */
  tone?: "light" | "dark";
}) {
  const { status, model: globalModel, setModel: setGlobalModel } = useStatus();
  const current = value ?? globalModel;
  const handleChange = onChange ?? setGlobalModel;

  const selectClass = `w-full mt-1 px-2 py-1.5 border rounded text-sm focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition-colors duration-150 ease-out ${
    tone === "dark"
      ? "bg-zinc-800 text-zinc-100 border-zinc-700"
      : "bg-white text-zinc-900 border-zinc-300"
  }`;

  const providers = (status?.providers ?? []).filter((p) => p.models.length > 0);

  if (providers.length > 0) {
    // Mirror list_models(): only a name served by more than one provider gets
    // a `short/model` prefix, so option values stay unambiguous.
    const counts = new Map<string, number>();
    for (const p of providers)
      for (const m of p.models) counts.set(m, (counts.get(m) ?? 0) + 1);

    return (
      <div>
        <label className="text-xs text-zinc-500">{label}</label>
        <select value={current} onChange={(e) => handleChange(e.target.value)} className={selectClass}>
          {providers.map((p) => {
            const short = providerShort(p.name);
            const groupLabel = short.charAt(0).toUpperCase() + short.slice(1);
            return (
              <optgroup key={p.name} label={p.running ? groupLabel : `${groupLabel} (offline)`}>
                {p.models.map((m) => {
                  const v = (counts.get(m) ?? 0) > 1 ? `${short}/${m}` : m;
                  return (
                    <option key={v} value={v}>
                      {m}
                    </option>
                  );
                })}
              </optgroup>
            );
          })}
        </select>
      </div>
    );
  }

  // Fallback: flat list (backend without a `providers` payload).
  if (status?.llamacpp.models && status.llamacpp.models.length > 0) {
    return (
      <div>
        <label className="text-xs text-zinc-500">{label}</label>
        <select value={current} onChange={(e) => handleChange(e.target.value)} className={selectClass}>
          {status.llamacpp.models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div>
      <label className="text-xs text-zinc-500">{label}</label>
      <input
        type="text"
        value={current}
        onChange={(e) => handleChange(e.target.value)}
        className="w-full mt-1 px-2 py-1.5 border border-zinc-300 rounded text-sm bg-zinc-50 text-zinc-400 cursor-not-allowed"
        placeholder="No models available"
        disabled
      />
    </div>
  );
}

/* ── StatusBadge ────────────────────────────────────────────── */

const BADGE_STYLES: Record<string, { dot: string; text: string; label: string }> = {
  ready: { dot: "bg-green-500", text: "text-green-400", label: "Ready" },
  running: { dot: "bg-green-500", text: "text-green-400", label: "Running" },
  stale: { dot: "bg-yellow-500", text: "text-yellow-400", label: "Stale" },
  not_built: { dot: "bg-zinc-500", text: "text-zinc-400", label: "Not Built" },
  not_running: { dot: "bg-red-500", text: "text-red-400", label: "Not Running" },
  not_installed: { dot: "bg-zinc-500", text: "text-zinc-500", label: "Not installed" },
};

export function StatusBadge({ value }: { value: string }) {
  const style = BADGE_STYLES[value];
  if (!style) return <span className="text-xs text-zinc-500">{value}</span>;
  return (
    <div className="flex items-center gap-2">
      <span className={`w-2 h-2 rounded-full ${style.dot}`} />
      <span className={`text-sm ${style.text}`}>{style.label}</span>
    </div>
  );
}

/* ── RecommendationBar ──────────────────────────────────────── */

export function RecommendationBar({
  recommendations,
  onAction,
  loading,
}: {
  recommendations: Recommendation[];
  onAction?: (rec: Recommendation) => void;
  loading?: boolean;
}) {
  if (!recommendations.length) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {recommendations.map((rec, i) => (
        <div
          key={i}
          className="flex items-center gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded transition-colors duration-150 ease-out"
        >
          <span className="text-sm text-amber-800">{rec.message}</span>
          {rec.action && onAction && (
            <button
              onClick={() => onAction(rec)}
              disabled={loading}
              className="px-2 py-1 bg-amber-200 text-amber-900 rounded text-xs font-medium hover:bg-amber-300 disabled:opacity-50 transition-colors duration-150 ease-out"
            >
              Go
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

/* ── ActionButton ───────────────────────────────────────────── */

export function ActionButton({
  onClick,
  loading,
  disabled,
  loadingText,
  children,
  variant = "primary",
}: {
  onClick: () => void;
  loading?: boolean;
  disabled?: boolean;
  loadingText?: string;
  children: ReactNode;
  variant?: "primary" | "secondary";
}) {
  const base =
    variant === "primary"
      ? "bg-violet-600 text-white hover:bg-violet-500"
      : "bg-zinc-700 text-white hover:bg-zinc-600";
  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      className={`px-4 py-2 rounded text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150 ease-out ${base}`}
    >
      {loading ? (loadingText ?? "Working...") : children}
    </button>
  );
}
