"use client";

export function EmptyState({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className="panel flex flex-col items-center justify-center px-8 py-14 text-center">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-surface-muted text-ink-muted">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
          <circle cx="9" cy="9" r="7" stroke="currentColor" strokeWidth="1.5" />
          <path d="M9 5.5v4M9 12.2h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>
      <p className="text-base font-semibold text-ink">{title}</p>
      <p className="mt-1.5 max-w-sm text-sm text-ink-muted">{detail}</p>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="panel border-danger/30 bg-danger-soft px-6 py-7">
      <p className="label text-danger">Connection</p>
      <p className="mt-2 text-lg font-semibold text-ink">API unavailable</p>
      <p className="mt-1.5 text-sm text-ink-secondary">{message}</p>
      <pre className="mt-4 overflow-x-auto rounded-lg border border-surface-border bg-surface p-3 font-mono text-xs text-ink-secondary">
        {`aimake serve --port 8765\ncd dashboard && npm run dev`}
      </pre>
    </div>
  );
}

export function LoadingState() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="panel h-[108px] animate-pulse bg-surface-muted"
          style={{ animationDelay: `${i * 60}ms` }}
        />
      ))}
    </div>
  );
}
