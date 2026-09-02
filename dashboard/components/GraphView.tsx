"use client";

import { useMemo } from "react";
import type { GraphData } from "@/lib/api";
import { StatusBadge } from "@/components/Badge";
import { useTheme } from "@/components/ThemeProvider";

type LayoutNode = {
  name: string;
  type: string;
  status: string;
  x: number;
  y: number;
};

function layout(graph: GraphData): LayoutNode[] {
  const levels = new Map<string, number>();
  const indeg = new Map<string, number>();
  graph.nodes.forEach((n) => indeg.set(n.name, 0));
  graph.edges.forEach((e) => indeg.set(e.to, (indeg.get(e.to) || 0) + 1));

  const queue = graph.nodes
    .filter((n) => (indeg.get(n.name) || 0) === 0)
    .map((n) => n.name);
  queue.forEach((n) => levels.set(n, 0));
  const adj = new Map<string, string[]>();
  graph.edges.forEach((e) => {
    if (!adj.has(e.from)) adj.set(e.from, []);
    adj.get(e.from)!.push(e.to);
  });

  while (queue.length) {
    const cur = queue.shift()!;
    const nextLevel = (levels.get(cur) || 0) + 1;
    for (const nxt of adj.get(cur) || []) {
      levels.set(nxt, Math.max(levels.get(nxt) || 0, nextLevel));
      indeg.set(nxt, (indeg.get(nxt) || 1) - 1);
      if ((indeg.get(nxt) || 0) === 0) queue.push(nxt);
    }
  }

  const byLevel = new Map<number, string[]>();
  graph.nodes.forEach((n) => {
    const lvl = levels.get(n.name) || 0;
    if (!byLevel.has(lvl)) byLevel.set(lvl, []);
    byLevel.get(lvl)!.push(n.name);
  });

  const nodeW = 176;
  const nodeH = 68;
  const gapX = 48;
  const gapY = 44;
  const result: LayoutNode[] = [];

  byLevel.forEach((names, lvl) => {
    names.forEach((name, i) => {
      const node = graph.nodes.find((n) => n.name === name)!;
      result.push({
        name,
        type: node.type,
        status: node.status,
        x: i * (nodeW + gapX) + 24,
        y: lvl * (nodeH + gapY) + 24,
      });
    });
  });

  return result;
}

function strokeFor(status: string, dark: boolean) {
  if (status === "changed" || status === "stale") return dark ? "#FBBF24" : "#C27803";
  if (status === "up_to_date" || status === "cached") return dark ? "#4B9FFF" : "#1A73E8";
  if (status === "failed") return dark ? "#F87171" : "#E02424";
  return dark ? "#2C3B55" : "#D0D7E2";
}

export function GraphView({ data }: { data: GraphData }) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const nodes = useMemo(() => layout(data), [data]);
  const pos = useMemo(() => {
    const m = new Map<string, LayoutNode>();
    nodes.forEach((n) => m.set(n.name, n));
    return m;
  }, [nodes]);

  const width = Math.max(720, ...nodes.map((n) => n.x + 220), 0);
  const height = Math.max(360, ...nodes.map((n) => n.y + 120), 0);
  const nodeW = 168;
  const nodeH = 60;
  const edge = isDark ? "#2C3B55" : "#C5D0E0";
  const fill = isDark ? "#131B2E" : "#FFFFFF";
  const title = isDark ? "#EEF2F8" : "#0B1220";
  const subtitle = isDark ? "#8090A8" : "#6B7A90";

  return (
    <div className="panel overflow-hidden">
      <div className="overflow-auto bg-surface-muted p-2">
        <svg
          width={width}
          height={height}
          className="min-w-full"
          role="img"
          aria-label="Pipeline dependency graph"
        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill={edge} />
            </marker>
          </defs>

          {data.edges.map((e) => {
            const a = pos.get(e.from);
            const b = pos.get(e.to);
            if (!a || !b) return null;
            const x1 = a.x + nodeW / 2;
            const y1 = a.y + nodeH;
            const x2 = b.x + nodeW / 2;
            const y2 = b.y;
            const mid = (y1 + y2) / 2;
            return (
              <path
                key={`${e.from}-${e.to}`}
                d={`M ${x1} ${y1} C ${x1} ${mid}, ${x2} ${mid}, ${x2} ${y2}`}
                fill="none"
                stroke={edge}
                strokeWidth="1.5"
                markerEnd="url(#arrow)"
              />
            );
          })}

          {nodes.map((n) => (
            <g key={n.name} transform={`translate(${n.x}, ${n.y})`}>
              <rect
                width={nodeW}
                height={nodeH}
                rx={10}
                fill={fill}
                stroke={strokeFor(n.status, isDark)}
                strokeWidth={1.5}
              />
              <text
                x={14}
                y={24}
                fill={title}
                style={{ fontSize: 13, fontWeight: 600 }}
              >
                {n.name.length > 18 ? `${n.name.slice(0, 16)}…` : n.name}
              </text>
              <text
                x={14}
                y={44}
                fill={subtitle}
                style={{ fontSize: 11, fontFamily: "ui-monospace, monospace" }}
              >
                {n.type}
              </text>
            </g>
          ))}
        </svg>
      </div>

      <div className="flex flex-wrap gap-2 border-t border-surface-border px-4 py-3">
        {data.nodes.map((n) => (
          <div
            key={n.name}
            className="flex items-center gap-2 rounded-lg border border-surface-border bg-surface px-2.5 py-1.5"
          >
            <span className="text-sm font-medium text-ink">{n.name}</span>
            <StatusBadge status={n.status} />
          </div>
        ))}
      </div>
    </div>
  );
}
