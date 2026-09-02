"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ErrorState, LoadingState, EmptyState } from "@/components/States";
import { StatusBadge } from "@/components/Badge";

type LineageNode = {
  name: string;
  type: string;
  fingerprint?: string;
  status?: string;
  depends_on: string[];
};

type LineageData = {
  nodes: LineageNode[];
  edges: { from: string; to: string }[];
  formats: string[];
  enabled: boolean;
};

export default function LineagePage() {
  const [data, setData] = useState<LineageData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .lineage()
      .then(setData)
      .catch((e) => setError(e.message || "Failed to load lineage"));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;

  return (
    <div className="space-y-4">
      <section className="panel px-5 py-4">
        <p className="label">Export</p>
        <p className="mt-1 text-sm text-ink">
          {data.enabled ? "Lineage enabled" : "Configure lineage.enabled: true"} · formats:{" "}
          {(data.formats || []).join(", ") || "openlineage"}
        </p>
        <p className="mt-2 font-mono text-xs text-ink-muted">
          aimake lineage --format openlineage --format mlflow
        </p>
      </section>

      {data.nodes.length === 0 ? (
        <EmptyState title="No artifacts" detail="Define artifacts in aimake.yaml" />
      ) : (
        <section className="panel overflow-hidden">
          <div className="panel-header">
            <p className="label">Artifact graph</p>
            <h3 className="mt-0.5 text-[15px] font-semibold text-ink">
              {data.nodes.length} nodes · {data.edges.length} edges
            </h3>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Artifact</th>
                  <th>Type</th>
                  <th>Depends on</th>
                  <th>Status</th>
                  <th>Fingerprint</th>
                </tr>
              </thead>
              <tbody>
                {data.nodes.map((n) => (
                  <tr key={n.name}>
                    <td className="font-medium text-ink">{n.name}</td>
                    <td className="font-mono text-xs text-ink-muted">{n.type}</td>
                    <td className="font-mono text-xs text-ink-muted">
                      {(n.depends_on || []).join(", ") || "—"}
                    </td>
                    <td>
                      {n.status ? <StatusBadge status={n.status} /> : "—"}
                    </td>
                    <td className="font-mono text-[11px] text-ink-muted">
                      {(n.fingerprint || "").replace(/^sha256:/, "").slice(0, 12) || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
