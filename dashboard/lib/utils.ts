import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatUsd(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return "—";
  return `$${Number(n).toFixed(2)}`;
}

export function formatDuration(sec: number | null | undefined) {
  if (sec == null) return "—";
  if (sec < 60) return `${sec.toFixed(1)}s`;
  return `${(sec / 60).toFixed(1)}m`;
}

export function shortHash(fp: string | null | undefined) {
  if (!fp) return "—";
  const clean = fp.replace(/^sha256:/, "");
  return clean.slice(0, 12);
}

export function statusTone(status: string) {
  const s = status.toLowerCase();
  if (["up_to_date", "cached", "success"].includes(s))
    return "bg-success-soft text-success border-transparent";
  if (["changed", "stale"].includes(s))
    return "bg-warning-soft text-warning border-transparent";
  if (["failed", "unknown"].includes(s))
    return "bg-danger-soft text-danger border-transparent";
  return "bg-surface-muted text-ink-muted border-surface-border";
}

export function stageTone(stage: string) {
  const s = stage.toLowerCase();
  if (s === "production") return "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-200";
  if (s === "staging") return "bg-warning-soft text-warning";
  return "bg-surface-muted text-ink-muted";
}

export function actionTone(action: string) {
  if (action === "run") return "text-warning";
  if (action === "restore") return "text-brand-600 dark:text-brand-500";
  return "text-ink-muted";
}
