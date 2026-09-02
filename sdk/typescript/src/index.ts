/**
 * @aimake/sdk — TypeScript client mirroring the Python Project API.
 *
 * Talks to `aimake serve` (HTTP JSON). Use alongside the Python SDK for CI.
 *
 * @example
 * ```ts
 * import { Aimake } from "@aimake/sdk";
 *
 * const ai = new Aimake({ baseUrl: "http://127.0.0.1:8765" });
 * const plan = await ai.plan();
 * const overview = await ai.overview();
 * ```
 */

export type AimakeOptions = {
  baseUrl?: string;
  fetch?: typeof fetch;
};

export class AimakeError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
  ) {
    super(message);
    this.name = "AimakeError";
  }
}

export type PlanEntry = {
  name: string;
  action: string;
  status: string;
  reason: string;
  estimated_cost_usd: number | null;
  estimated_tokens: number | null;
};

export type Plan = {
  to_run: string[];
  to_skip: string[];
  to_restore: string[];
  estimated_total_cost_usd: number;
  estimated_total_tokens: number;
  entries: PlanEntry[];
};

export type Overview = {
  project: { name: string; version: string; root: string };
  stats: Record<string, number>;
  plan: Plan;
  statuses: Record<string, string>;
  recent_builds: Record<string, unknown>[];
};

export type GraphData = {
  nodes: {
    name: string;
    type: string;
    depends_on: string[];
    status: string;
  }[];
  edges: { from: string; to: string }[];
  dot?: string;
};

export type Lineage = {
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
};

export class Aimake {
  readonly baseUrl: string;
  private readonly _fetch: typeof fetch;

  constructor(options: AimakeOptions = {}) {
    this.baseUrl = (options.baseUrl || "http://127.0.0.1:8765").replace(
      /\/$/,
      "",
    );
    this._fetch = options.fetch || fetch;
  }

  private async request<T>(
    path: string,
    init?: RequestInit,
  ): Promise<T> {
    const res = await this._fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new AimakeError(
        (data as { error?: string }).error || res.statusText,
        res.status,
        data,
      );
    }
    return data as T;
  }

  /** Health check — mirrors a lightweight ping before builds. */
  health(): Promise<{ ok: boolean; service?: string }> {
    return this.request("/api/health");
  }

  /** Project snapshot — like reading Project metadata + plan + status. */
  overview(): Promise<Overview> {
    return this.request("/api/overview");
  }

  /** Incremental build plan — mirrors `Project.plan()`. */
  plan(): Promise<Plan> {
    return this.request("/api/plan");
  }

  /** Dependency graph — mirrors `Project.graph_dict()` / graph API. */
  graph(): Promise<GraphData> {
    return this.request("/api/graph");
  }

  builds(limit = 50): Promise<{ builds: Record<string, unknown>[] }> {
    return this.request(`/api/builds?limit=${limit}`);
  }

  lineage(): Promise<Lineage> {
    return this.request("/api/lineage");
  }

  repro(): Promise<Record<string, unknown>> {
    return this.request("/api/repro");
  }

  settings(): Promise<Record<string, unknown>> {
    return this.request("/api/settings");
  }

  cache(): Promise<Record<string, unknown>> {
    return this.request("/api/cache");
  }

  registry(params?: {
    artifact?: string;
    stage?: string;
  }): Promise<{ entries: Record<string, unknown>[]; enabled: boolean }> {
    const q = new URLSearchParams();
    if (params?.artifact) q.set("artifact", params.artifact);
    if (params?.stage) q.set("stage", params.stage);
    const qs = q.toString();
    return this.request(`/api/registry${qs ? `?${qs}` : ""}`);
  }

  promote(
    artifact: string,
    version: string,
    stage = "production",
    opts?: { force?: boolean },
  ): Promise<Record<string, unknown>> {
    return this.request("/api/registry/promote", {
      method: "POST",
      body: JSON.stringify({ artifact, version, stage, ...opts }),
    });
  }
}

export default Aimake;
