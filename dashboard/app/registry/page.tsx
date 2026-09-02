"use client";

import { useEffect, useState } from "react";
import { api, type RegistryEntry } from "@/lib/api";
import { Badge } from "@/components/Badge";
import { ErrorState, LoadingState, EmptyState } from "@/components/States";
import { shortHash, stageTone } from "@/lib/utils";

type PolicyInfo = {
  stages?: string[];
  metrics?: Record<string, { minimum?: number | null; maximum?: number | null }>;
  max_cost_usd?: number | null;
  require_tag?: string | null;
  require_approval_env?: string | null;
} | null;

export default function RegistryPage() {
  const [entries, setEntries] = useState<RegistryEntry[] | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [remote, setRemote] = useState<{ type: string } | null>(null);
  const [policy, setPolicy] = useState<PolicyInfo>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const r = await api.registry();
    setEntries(r.entries);
    setEnabled(r.enabled);
    setRemote(r.remote || null);
    setPolicy(r.policy || null);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || "Failed to load registry"));
  }, []);

  async function promote(entry: RegistryEntry, stage: string, force = false) {
    const key = `${entry.artifact_name}@${entry.version}`;
    setBusy(key);
    setMessage(null);
    try {
      const check = await api.policyCheck(entry.artifact_name, entry.version, stage);
      if (!check.ok && !force) {
        setMessage(
          `Policy blocked → ${stage}: ${check.violations.map((v) => v.message).join("; ")}`,
        );
        return;
      }
      const res = (await api.promote(entry.artifact_name, entry.version, stage, {
        force,
      })) as { remote_push?: { uri: string } };
      const pushNote = res.remote_push ? ` · pushed ${res.remote_push.uri}` : "";
      setMessage(`Promoted ${key} → ${stage}${pushNote}`);
      await load();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Promote failed");
    } finally {
      setBusy(null);
    }
  }

  async function pushRemote(entry: RegistryEntry) {
    const key = `${entry.artifact_name}@${entry.version}`;
    setBusy(key);
    setMessage(null);
    try {
      const res = await api.registryPush(entry.artifact_name, entry.version);
      setMessage(`Pushed ${key} → ${res.uri}`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Push failed");
    } finally {
      setBusy(null);
    }
  }

  async function tagBest(entry: RegistryEntry) {
    const key = `${entry.artifact_name}@${entry.version}`;
    setBusy(key);
    setMessage(null);
    try {
      await api.tag(entry.artifact_name, entry.version, ["best"]);
      setMessage(`Tagged ${key} with best`);
      await load();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Tag failed");
    } finally {
      setBusy(null);
    }
  }

  if (error) return <ErrorState message={error} />;
  if (!entries) return <LoadingState />;

  return (
    <div className="space-y-4">
      {!enabled ? (
        <div className="panel border-warning/30 bg-warning-soft px-5 py-4 text-sm text-ink-secondary">
          Registry is disabled. Enable with{" "}
          <code className="font-mono text-warning">registry.enabled: true</code> in{" "}
          <code className="font-mono">aimake.yaml</code>.
        </div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        <div className="panel px-5 py-4 text-sm text-ink-secondary">
          <p className="label">Remote</p>
          <p className="mt-1 font-medium text-ink">
            {remote ? remote.type : "Not configured"}
          </p>
          <p className="mt-1 text-xs text-ink-muted">
            S3 / Hugging Face / W&B push on promote
          </p>
        </div>
        <div className="panel px-5 py-4 text-sm text-ink-secondary">
          <p className="label">Promote policy</p>
          {policy ? (
            <ul className="mt-1 space-y-0.5 text-xs text-ink-muted">
              <li>stages: {(policy.stages || []).join(", ") || "—"}</li>
              {policy.max_cost_usd != null ? (
                <li>max cost: ${policy.max_cost_usd}</li>
              ) : null}
              {policy.require_tag ? <li>require tag: {policy.require_tag}</li> : null}
              {policy.require_approval_env ? (
                <li>approval env: {policy.require_approval_env}</li>
              ) : null}
            </ul>
          ) : (
            <p className="mt-1 text-xs text-ink-muted">No promote gates configured</p>
          )}
        </div>
      </div>

      {message ? (
        <div className="panel border-brand-200 bg-brand-50 px-5 py-3 text-sm text-brand-700 dark:border-brand-500/30 dark:bg-brand-500/10 dark:text-brand-200">
          {message}
        </div>
      ) : null}

      {entries.length === 0 ? (
        <EmptyState
          title="Registry is empty"
          detail="Build with registry.auto_register: true to populate versions."
        />
      ) : (
        <section className="panel overflow-hidden">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Artifact</th>
                  <th>Version</th>
                  <th>Stage</th>
                  <th>Fingerprint</th>
                  <th>Tags</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => {
                  const key = `${e.artifact_name}@${e.version}`;
                  const busyRow = busy === key;
                  return (
                    <tr key={key}>
                      <td className="font-medium text-ink">{e.artifact_name}</td>
                      <td className="font-mono text-xs">{e.version}</td>
                      <td>
                        <Badge className={stageTone(e.stage)}>{e.stage}</Badge>
                      </td>
                      <td className="font-mono text-xs text-ink-muted">
                        {shortHash(e.fingerprint)}
                      </td>
                      <td className="text-xs text-ink-muted">
                        {(e.tags || []).join(", ") || "—"}
                      </td>
                      <td>
                        <div className="flex flex-wrap gap-1.5">
                          <button
                            type="button"
                            disabled={busyRow}
                            className="btn-secondary !px-2 !py-1 text-xs"
                            onClick={() => promote(e, "staging")}
                          >
                            Staging
                          </button>
                          <button
                            type="button"
                            disabled={busyRow}
                            className="btn-primary !px-2 !py-1 text-xs"
                            onClick={() => promote(e, "production")}
                          >
                            Production
                          </button>
                          <button
                            type="button"
                            disabled={busyRow}
                            className="btn-ghost !px-2 !py-1 text-xs"
                            onClick={() => tagBest(e)}
                          >
                            Tag best
                          </button>
                          {remote ? (
                            <button
                              type="button"
                              disabled={busyRow}
                              className="btn-ghost !px-2 !py-1 text-xs"
                              onClick={() => pushRemote(e)}
                            >
                              Push
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
