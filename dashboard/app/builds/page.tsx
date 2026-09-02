"use client";

import { useEffect, useState } from "react";
import { api, type BuildRow, type PlanEntry } from "@/lib/api";
import { StatusBadge } from "@/components/Badge";
import { ErrorState, LoadingState } from "@/components/States";
import { actionTone, formatDuration, formatUsd } from "@/lib/utils";

export default function BuildsPage() {
  const [builds, setBuilds] = useState<BuildRow[] | null>(null);
  const [plan, setPlan] = useState<PlanEntry[] | null>(null);
  const [cost, setCost] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.builds(), api.plan()])
      .then(([b, p]) => {
        setBuilds(b.builds);
        setPlan(p.entries);
        setCost(p.estimated_total_cost_usd || 0);
      })
      .catch((e) => setError(e.message || "Failed to load builds"));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!builds || !plan) return <LoadingState />;

  return (
    <div className="space-y-6">
      <section className="panel">
        <div className="panel-header flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="label">Current plan</p>
            <h3 className="mt-1 text-base font-semibold text-ink">
              Estimated rebuild cost{" "}
              <span className="text-brand-600 dark:text-brand-500">{formatUsd(cost)}</span>
            </h3>
          </div>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Artifact</th>
                <th>Action</th>
                <th>Status</th>
                <th>Est. cost</th>
              </tr>
            </thead>
            <tbody>
              {plan.map((e) => (
                <tr key={e.name}>
                  <td className="font-medium text-ink">{e.name}</td>
                  <td className={`font-mono text-xs font-semibold uppercase ${actionTone(e.action)}`}>
                    {e.action}
                  </td>
                  <td>
                    <StatusBadge status={e.status} />
                  </td>
                  <td className="font-mono text-xs text-ink-muted">
                    {formatUsd(e.estimated_cost_usd)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <p className="label">History</p>
          <h3 className="mt-1 text-base font-semibold text-ink">Past builds</h3>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Git</th>
                <th>Metrics</th>
              </tr>
            </thead>
            <tbody>
              {builds.length === 0 ? (
                <tr>
                  <td colSpan={5} className="!py-10 text-center text-ink-muted">
                    No builds recorded yet
                  </td>
                </tr>
              ) : (
                builds.map((b) => (
                  <tr key={b.id}>
                    <td className="font-mono font-medium text-ink">#{b.id}</td>
                    <td>
                      <StatusBadge status={b.status || "unknown"} />
                    </td>
                    <td className="text-ink-secondary">{formatDuration(b.duration)}</td>
                    <td className="font-mono text-xs text-ink-muted">
                      {b.git_branch || "—"}
                      {b.git_commit ? ` @ ${String(b.git_commit).slice(0, 7)}` : ""}
                    </td>
                    <td className="font-mono text-xs text-ink-muted">
                      {b.metrics && typeof b.metrics === "object"
                        ? Object.entries(b.metrics)
                            .slice(0, 3)
                            .map(([k, v]) => `${k}=${v}`)
                            .join(" · ") || "—"
                        : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
