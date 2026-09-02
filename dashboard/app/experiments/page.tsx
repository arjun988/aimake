"use client";

import { useEffect, useState } from "react";
import {
  api,
  type CompareResult,
  type ExperimentRow,
} from "@/lib/api";
import { StatusBadge } from "@/components/Badge";
import { ErrorState, LoadingState, EmptyState } from "@/components/States";
import { cn } from "@/lib/utils";

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<ExperimentRow[] | null>(null);
  const [compare, setCompare] = useState<CompareResult | null>(null);
  const [baseline, setBaseline] = useState("previous");
  const [candidate, setCandidate] = useState("latest");
  const [error, setError] = useState<string | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [trials, setTrials] = useState<Record<string, unknown>[] | null>(null);

  useEffect(() => {
    api
      .experiments()
      .then((r) => setExperiments(r.experiments))
      .catch((e) => setError(e.message || "Failed to load"));
    runCompare();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function runCompare() {
    setCompareError(null);
    api
      .compare(baseline, candidate)
      .then(setCompare)
      .catch((e) => setCompareError(e.message || "Compare failed"));
  }

  async function openExperiment(id: number) {
    setSelected(id);
    const detail = await api.experiment(id);
    setTrials(detail.trials);
  }

  if (error) return <ErrorState message={error} />;
  if (!experiments) return <LoadingState />;

  return (
    <div className="space-y-6">
      <section className="panel">
        <div className="panel-header">
          <p className="label">Compare builds</p>
          <h3 className="mt-1 text-base font-semibold text-ink">Metric deltas</h3>
        </div>
        <div className="flex flex-wrap items-end gap-3 border-b border-surface-border px-5 py-4">
          <label className="text-xs font-medium text-ink-muted">
            Baseline
            <input
              value={baseline}
              onChange={(e) => setBaseline(e.target.value)}
              className="input mt-1.5 w-40 font-mono"
              placeholder="previous"
            />
          </label>
          <label className="text-xs font-medium text-ink-muted">
            Candidate
            <input
              value={candidate}
              onChange={(e) => setCandidate(e.target.value)}
              className="input mt-1.5 w-40 font-mono"
              placeholder="latest"
            />
          </label>
          <button type="button" onClick={runCompare} className="btn-primary">
            Compare
          </button>
        </div>

        {compareError ? (
          <p className="px-5 py-6 text-sm text-ink-muted">{compareError}</p>
        ) : compare ? (
          <div className="px-5 py-4">
            <p className="text-sm text-ink-secondary">{compare.summary}</p>
            <div className="table-wrap mt-4">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Baseline</th>
                    <th>Candidate</th>
                    <th>Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {compare.metric_deltas.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="!py-8 text-center text-ink-muted">
                        No overlapping metrics to compare
                      </td>
                    </tr>
                  ) : (
                    compare.metric_deltas.map((d) => (
                      <tr key={d.name}>
                        <td className="font-medium text-ink">{d.name}</td>
                        <td className="font-mono text-xs text-ink-muted">
                          {d.baseline ?? "—"}
                        </td>
                        <td className="font-mono text-xs text-ink-muted">
                          {d.candidate ?? "—"}
                        </td>
                        <td
                          className={cn(
                            "font-mono text-xs font-semibold",
                            d.improved === true && "text-success",
                            d.improved === false && "text-danger",
                            d.improved == null && "text-ink-muted",
                          )}
                        >
                          {d.delta == null
                            ? "—"
                            : d.delta > 0
                              ? `+${d.delta}`
                              : d.delta}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <p className="px-5 py-6 text-sm text-ink-muted">
            Run a comparison to see deltas.
          </p>
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <p className="label">Optimization</p>
          <h3 className="mt-1 text-base font-semibold text-ink">Experiment runs</h3>
        </div>
        {experiments.length === 0 ? (
          <div className="p-5">
            <EmptyState
              title="No experiments yet"
              detail="Run `aimake optimize` to populate this view."
            />
          </div>
        ) : (
          <div className="divide-y divide-surface-border">
            {experiments.map((exp) => (
              <button
                key={exp.id}
                type="button"
                onClick={() => openExperiment(exp.id)}
                className="flex w-full items-center justify-between px-5 py-3 text-left hover:bg-surface-muted"
              >
                <div>
                  <p className="text-sm font-medium text-ink">
                    #{exp.id} {exp.name || "unnamed"}
                  </p>
                  <p className="font-mono text-[11px] text-ink-muted">
                    best={exp.best_value ?? "—"} · build #{exp.best_build_id ?? "—"}
                  </p>
                </div>
                <StatusBadge status={exp.status || "unknown"} />
              </button>
            ))}
          </div>
        )}
      </section>

      {selected != null && trials ? (
        <section className="panel">
          <div className="panel-header">
            <p className="label">Experiment #{selected}</p>
            <h3 className="mt-1 text-base font-semibold text-ink">Trials</h3>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Trial</th>
                  <th>Objective</th>
                  <th>Build</th>
                  <th>Params</th>
                </tr>
              </thead>
              <tbody>
                {trials.map((t, i) => (
                  <tr key={i}>
                    <td className="font-mono text-ink">
                      {String(t.trial_number ?? i)}
                    </td>
                    <td className="font-mono text-xs text-ink-muted">
                      {String(t.objective_value ?? "—")}
                    </td>
                    <td className="font-mono text-xs text-ink-muted">
                      #{String(t.build_id ?? "—")}
                    </td>
                    <td className="max-w-xs truncate font-mono text-[11px] text-ink-muted">
                      {typeof t.parameters === "string"
                        ? t.parameters
                        : JSON.stringify(t.parameters ?? {})}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
