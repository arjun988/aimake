"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type Overview } from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/Badge";
import { ErrorState, LoadingState } from "@/components/States";
import { formatDuration, formatUsd } from "@/lib/utils";

export default function OverviewPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .overview()
      .then(setData)
      .catch((e) => setError(e.message || "Failed to load"));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;

  return (
    <div className="space-y-5">
      <section className="panel">
        <div className="flex flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="label">Project</p>
            <h2 className="mt-1 truncate text-xl font-semibold tracking-tight text-ink">
              {data.project.name}
            </h2>
            <p className="mt-1 truncate font-mono text-xs text-ink-muted">
              {data.project.root}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md border border-surface-border bg-surface-muted px-2.5 py-1 text-xs font-semibold text-ink-secondary">
              v{data.project.version}
            </span>
            <Link href="/graph" className="btn-primary">
              View graph
            </Link>
          </div>
        </div>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Artifacts"
          value={String(data.stats.artifacts)}
          hint={`${data.stats.cached} cached · ${data.stats.stale} need attention`}
        />
        <StatCard
          label="To rebuild"
          value={String(data.stats.to_rebuild)}
          tone={data.stats.to_rebuild > 0 ? "warning" : "brand"}
          hint="From current plan"
        />
        <StatCard
          label="Est. cost"
          value={formatUsd(data.stats.estimated_cost_usd)}
          tone="brand"
          hint={`${data.stats.estimated_tokens.toLocaleString()} tokens`}
        />
        <StatCard
          label="Registry"
          value={String(data.stats.registry_entries)}
          hint={`${data.stats.experiments} experiments · ${data.stats.builds} builds`}
        />
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <section className="panel">
          <div className="panel-header flex items-center justify-between">
            <div>
              <p className="label">Build plan</p>
              <h3 className="mt-0.5 text-[15px] font-semibold text-ink">What will run</h3>
            </div>
            <Link
              href="/builds"
              className="text-xs font-semibold text-brand-600 hover:underline dark:text-brand-500"
            >
              All builds →
            </Link>
          </div>
          <div className="divide-y divide-surface-border">
            {data.plan.entries.map((e) => (
              <div
                key={e.name}
                className="flex items-center justify-between gap-3 px-5 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">{e.name}</p>
                  <p className="font-mono text-[11px] text-ink-muted">
                    {e.reason || e.action}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {e.estimated_cost_usd != null ? (
                    <span className="font-mono text-xs text-ink-muted">
                      {formatUsd(e.estimated_cost_usd)}
                    </span>
                  ) : null}
                  <StatusBadge status={e.status} />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <p className="label">Recent builds</p>
            <h3 className="mt-0.5 text-[15px] font-semibold text-ink">Execution log</h3>
          </div>
          <div className="divide-y divide-surface-border">
            {data.recent_builds.length === 0 ? (
              <p className="px-5 py-8 text-sm text-ink-muted">
                No builds yet. Run{" "}
                <code className="font-mono text-brand-600">aimake build</code>.
              </p>
            ) : (
              data.recent_builds.map((b) => (
                <div key={b.id} className="flex items-center justify-between px-5 py-3">
                  <div>
                    <p className="text-sm font-medium text-ink">Build #{b.id}</p>
                    <p className="font-mono text-[11px] text-ink-muted">
                      {b.git_branch || "—"} · {formatDuration(b.duration)}
                    </p>
                  </div>
                  <StatusBadge status={b.status || "unknown"} />
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
