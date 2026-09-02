"use client";

import { useEffect, useState } from "react";
import { api, type RegistryEntry } from "@/lib/api";
import { Badge } from "@/components/Badge";
import { ErrorState, LoadingState, EmptyState } from "@/components/States";
import { shortHash, stageTone } from "@/lib/utils";

export default function RegistryPage() {
  const [entries, setEntries] = useState<RegistryEntry[] | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const r = await api.registry();
    setEntries(r.entries);
    setEnabled(r.enabled);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || "Failed to load registry"));
  }, []);

  async function promote(entry: RegistryEntry, stage: string) {
    const key = `${entry.artifact_name}@${entry.version}`;
    setBusy(key);
    setMessage(null);
    try {
      await api.promote(entry.artifact_name, entry.version, stage);
      setMessage(`Promoted ${key} → ${stage}`);
      await load();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Promote failed");
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
          <div className="panel-header">
            <p className="label">Versions</p>
            <h3 className="mt-1 text-base font-semibold text-ink">
              {entries.length} registered artifact{entries.length === 1 ? "" : "s"}
            </h3>
          </div>
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
                  return (
                    <tr key={key}>
                      <td className="font-medium text-ink">{e.artifact_name}</td>
                      <td className="font-mono text-xs text-ink-muted">{e.version}</td>
                      <td>
                        <Badge className={stageTone(e.stage)}>{e.stage}</Badge>
                      </td>
                      <td className="font-mono text-xs text-ink-muted">
                        {shortHash(e.fingerprint)}
                      </td>
                      <td className="font-mono text-xs text-ink-muted">
                        {e.tags?.length ? e.tags.join(", ") : "—"}
                      </td>
                      <td>
                        <div className="flex flex-wrap gap-1.5">
                          <button
                            type="button"
                            disabled={busy === key}
                            onClick={() => promote(e, "staging")}
                            className="btn-secondary !px-2 !py-1 text-[11px]"
                          >
                            Staging
                          </button>
                          <button
                            type="button"
                            disabled={busy === key}
                            onClick={() => promote(e, "production")}
                            className="btn-primary !px-2 !py-1 text-[11px]"
                          >
                            Production
                          </button>
                          <button
                            type="button"
                            disabled={busy === key}
                            onClick={() => tagBest(e)}
                            className="btn-ghost !px-2 !py-1 text-[11px]"
                          >
                            Tag best
                          </button>
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
