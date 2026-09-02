const API_BASE =
  process.env.NEXT_PUBLIC_AIMAKE_API?.replace(/\/$/, "") ||
  "http://127.0.0.1:8765";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(data.error || res.statusText, res.status);
  }
  return data as T;
}

export type Overview = {
  project: { name: string; version: string; root: string };
  stats: {
    artifacts: number;
    to_rebuild: number;
    cached: number;
    stale: number;
    estimated_cost_usd: number;
    estimated_tokens: number;
    builds: number;
    experiments: number;
    registry_entries: number;
  };
  plan: {
    to_run: string[];
    to_skip: string[];
    to_restore: string[];
    entries: PlanEntry[];
  };
  statuses: Record<string, string>;
  recent_builds: BuildRow[];
  cache: Record<string, unknown>;
  recent_experiments: ExperimentRow[];
  registry_preview: RegistryEntry[];
};

export type PlanEntry = {
  name: string;
  action: string;
  status: string;
  reason: string;
  estimated_cost_usd: number | null;
  estimated_tokens: number | null;
};

export type GraphData = {
  nodes: GraphNode[];
  edges: { from: string; to: string }[];
  dot: string;
};

export type GraphNode = {
  name: string;
  type: string;
  depends_on: string[];
  command: string | null;
  outputs: string[];
  status: string;
};

export type BuildRow = {
  id: number;
  status?: string;
  timestamp?: string;
  duration?: number;
  rebuilt?: string[] | string;
  reused?: string[] | string;
  failed?: string[] | string;
  metrics?: Record<string, number>;
  git_commit?: string;
  git_branch?: string;
};

export type ExperimentRow = {
  id: number;
  name?: string;
  status?: string;
  best_value?: number;
  best_build_id?: number;
  created_at?: string;
};

export type RegistryEntry = {
  artifact_name: string;
  version: string;
  stage: string;
  fingerprint: string;
  tags: string[];
  metrics?: Record<string, number>;
  build_id?: number | null;
  created_at?: string | null;
};

export type CompareResult = {
  baseline_id: number;
  candidate_id: number;
  summary: string;
  baseline_metrics: Record<string, number>;
  candidate_metrics: Record<string, number>;
  metric_deltas: {
    name: string;
    baseline: number | null;
    candidate: number | null;
    delta: number | null;
    improved: boolean | null;
  }[];
  parameter_changes: Record<
    string,
    { baseline: unknown; candidate: unknown }
  >;
};

export const api = {
  overview: () => request<Overview>("/api/overview"),
  graph: () => request<GraphData>("/api/graph"),
  builds: (limit = 50) =>
    request<{ builds: BuildRow[] }>(`/api/builds?limit=${limit}`),
  compare: (baseline = "previous", candidate = "latest") =>
    request<CompareResult>(
      `/api/compare?baseline=${encodeURIComponent(baseline)}&candidate=${encodeURIComponent(candidate)}`,
    ),
  experiments: () =>
    request<{ experiments: ExperimentRow[] }>("/api/experiments"),
  experiment: (id: number) =>
    request<{ experiment: ExperimentRow; trials: Record<string, unknown>[] }>(
      `/api/experiments/${id}`,
    ),
  registry: () =>
    request<{
      entries: RegistryEntry[];
      enabled: boolean;
      remote?: { type: string; auto_push_on_promote?: boolean } | null;
      policy?: Record<string, unknown> | null;
    }>("/api/registry"),
  promote: (
    artifact: string,
    version: string,
    stage: string,
    opts?: { force?: boolean; push?: boolean },
  ) =>
    request("/api/registry/promote", {
      method: "POST",
      body: JSON.stringify({ artifact, version, stage, ...opts }),
    }),
  registryPush: (artifact: string, version: string) =>
    request<{ uri: string; backend: string }>("/api/registry/push", {
      method: "POST",
      body: JSON.stringify({ artifact, version }),
    }),
  policyCheck: (artifact: string, version: string, stage = "production") =>
    request<{ ok: boolean; violations: { code: string; message: string }[] }>(
      `/api/policy/check?artifact=${encodeURIComponent(artifact)}&version=${encodeURIComponent(version)}&stage=${encodeURIComponent(stage)}`,
    ),
  tag: (artifact: string, version: string, tags: string[]) =>
    request("/api/registry/tag", {
      method: "POST",
      body: JSON.stringify({ artifact, version, tags }),
    }),
  cache: () => request<Record<string, unknown>>("/api/cache"),
  settings: () => request<Record<string, unknown>>("/api/settings") as Promise<{
    project: { name: string; version: string; root: string };
    cache: Record<string, unknown>;
    registry: { enabled: boolean; remote: { type: string } | null };
    policy: Record<string, unknown> | null;
    notifications: { slack: boolean; discord: boolean; email: boolean };
    schedule_jobs: string[];
    secrets: { dotenv: boolean; providers: string[] };
    attestation?: { enabled: boolean; write_sidecars: boolean };
    lineage?: { enabled: boolean; formats: string[]; auto_export_on_build: boolean };
  }>,
  repro: () => request<Record<string, unknown>>("/api/repro") as Promise<any>,
  lineage: () =>
    request<{
      nodes: {
        name: string;
        type: string;
        fingerprint?: string;
        status?: string;
        depends_on: string[];
      }[];
      edges: { from: string; to: string }[];
      formats: string[];
      enabled: boolean;
    }>("/api/lineage"),
  attestations: () =>
    request<{ enabled: boolean; entries: { artifact: string; path: string | null }[] }>(
      "/api/attestations",
    ),
  probe: () =>
    request<{ findings: Record<string, unknown>[]; drifted: boolean }>("/api/probe"),
  developer: () =>
    request<{
      aimake_version: string;
      python_sdk: { import: string; docs: string; example: string };
      typescript_sdk: { package: string; path: string; example: string };
      docker: {
        image: string;
        tags: string[];
        run_build: string;
        run_serve: string;
      };
      tui: { command: string; keys: string };
    }>("/api/developer"),
  plan: () => request<{ entries: PlanEntry[]; estimated_total_cost_usd: number }>("/api/plan"),
  health: () => request<{ ok: boolean }>("/api/health"),
};

export { API_BASE };
