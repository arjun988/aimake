"use client";

import { useEffect, useState } from "react";
import { api, type GraphData } from "@/lib/api";
import { GraphView } from "@/components/GraphView";
import { ErrorState, LoadingState } from "@/components/States";

export default function GraphPage() {
  const [data, setData] = useState<GraphData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .graph()
      .then(setData)
      .catch((e) => setError(e.message || "Failed to load graph"));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-ink-muted">
          <span className="font-semibold text-ink">{data.nodes.length}</span> nodes
          <span className="mx-2 text-surface-border-strong">·</span>
          <span className="font-semibold text-ink">{data.edges.length}</span> edges
        </p>
        <div className="flex gap-3 text-[11px] font-medium text-ink-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-brand-500" /> Cached
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-warning" /> Stale
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-danger" /> Failed
          </span>
        </div>
      </div>
      <GraphView data={data} />
    </div>
  );
}
