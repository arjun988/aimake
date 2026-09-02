"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ErrorState, LoadingState } from "@/components/States";

export default function CachePage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .cache()
      .then(setData)
      .catch((e) => setError(e.message || "Failed to load cache"));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;

  const local = (data.local as Record<string, unknown>) || data;
  const remote = data.remote as Record<string, unknown> | null | undefined;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <section className="panel">
          <div className="panel-header">
            <p className="label">Local</p>
            <h3 className="mt-1 text-base font-semibold text-ink">
              Content-addressable cache
            </h3>
          </div>
          <dl className="divide-y divide-surface-border">
            {Object.entries(local).map(([k, v]) => (
              <div key={k} className="flex items-start justify-between gap-4 px-5 py-3">
                <dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  {k}
                </dt>
                <dd className="max-w-[65%] break-all text-right font-mono text-xs text-ink-secondary">
                  {typeof v === "object" ? JSON.stringify(v) : String(v)}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="panel">
          <div className="panel-header">
            <p className="label">Remote</p>
            <h3 className="mt-1 text-base font-semibold text-ink">S3 / shared store</h3>
          </div>
          {!remote ? (
            <p className="px-5 py-8 text-sm text-ink-muted">
              No remote cache configured. Add{" "}
              <code className="font-mono text-brand-600 dark:text-brand-500">cache.remote</code>{" "}
              in aimake.yaml.
            </p>
          ) : (
            <dl className="divide-y divide-surface-border">
              {Object.entries(remote).map(([k, v]) => (
                <div key={k} className="flex items-start justify-between gap-4 px-5 py-3">
                  <dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                    {k}
                  </dt>
                  <dd className="max-w-[65%] break-all text-right font-mono text-xs text-ink-secondary">
                    {typeof v === "object" ? JSON.stringify(v) : String(v)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </section>
      </div>

      <section className="panel">
        <div className="panel-header">
          <p className="label">Raw payload</p>
        </div>
        <pre className="overflow-x-auto border-t border-surface-border bg-surface-muted p-4 font-mono text-[11px] leading-relaxed text-ink-secondary">
          {JSON.stringify(data, null, 2)}
        </pre>
      </section>
    </div>
  );
}
