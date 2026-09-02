"use client";

import { usePathname } from "next/navigation";
import { useTheme } from "@/components/ThemeProvider";

const TITLES: Record<string, { title: string; subtitle: string }> = {
  "/": {
    title: "Overview",
    subtitle: "Pipeline health, cost, and rebuild queue",
  },
  "/graph": {
    title: "Dependency graph",
    subtitle: "Artifact DAG with live status",
  },
  "/builds": {
    title: "Builds",
    subtitle: "Current plan and execution history",
  },
  "/experiments": {
    title: "Experiments",
    subtitle: "Optimization runs and build comparison",
  },
  "/registry": {
    title: "Registry",
    subtitle: "Promote and tag versioned artifacts",
  },
  "/cache": {
    title: "Cache",
    subtitle: "Local store and remote sync status",
  },
  "/settings": {
    title: "Settings",
    subtitle: "Team cache, policy, notifications, secrets",
  },
};

export function TopBar() {
  const pathname = usePathname();
  const meta = TITLES[pathname] || TITLES["/"];
  const { theme, toggle } = useTheme();

  return (
    <header className="sticky top-0 z-20 border-b border-surface-border bg-surface/95 px-4 py-3.5 sm:px-6 md:px-8">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0 animate-fade-in">
          <h1 className="truncate text-lg font-semibold tracking-tight text-ink md:text-xl">
            {meta.title}
          </h1>
          <p className="mt-0.5 truncate text-sm text-ink-muted">{meta.subtitle}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="hidden items-center gap-1.5 rounded-md border border-surface-border bg-surface-muted px-2.5 py-1 text-[11px] font-semibold text-ink-secondary sm:inline-flex">
            <span className="h-1.5 w-1.5 rounded-full bg-success" />
            Live
          </span>
          <button
            type="button"
            onClick={toggle}
            className="btn-secondary h-9 w-9 !px-0"
            aria-label="Toggle theme"
            title={theme === "dark" ? "Switch to light" : "Switch to dark"}
          >
            {theme === "dark" ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </div>
    </header>
  );
}

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M12.6 3.4l-1.1 1.1M4.5 11.5l-1.1 1.1"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M13.2 9.2A5.5 5.5 0 0 1 6.8 2.8 5.6 5.6 0 1 0 13.2 9.2Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}
