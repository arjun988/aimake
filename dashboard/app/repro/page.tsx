"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ErrorState, LoadingState } from "@/components/States";

type ReproArtifact = {
  name: string;
  status?: string;
  fingerprint?: string;
  fingerprint_matches_stored?: boolean;
  fingerprint_matches_lock?: boolean | null;
  probes?: { drifted?: boolean; name?: string; pinned?: string; live?: string }[];
};

type ReproReport = {
  generated_at: string;
  aimake_version: string;
  project: { name: string; version: string; root: string };
  environment: { python: string; platform: string; environment_mode: string };
  git: { available: boolean; commit?: string; branch?: string; dirty?: boolean };
  artifacts: ReproArtifact[];
  attestations: { artifact: string; path: string }[];
  attestation_enabled: boolean;
  lineage_enabled: boolean;
};

export default function ReproPage() {
  const [data, setData] = useState<ReproReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .repro()
      .then(setData)
      .catch((e) => setError(e.message || "Failed to load repro report"));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;

  return (
    <div className="space-y-4">
      <section className="panel">
        <div className="panel-header flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="label">Reproducibility</p>
            <h3 className="mt-0.5 text-[15px] font-semibold text-ink">
              {data.project.name} · aimake {data.aimake_version}
            </h3>
          </div>
          <p className="font-mono text-[11px] text-ink-muted">{data.generated_at}</p>
        </div>
        <dl className="grid gap-0 sm:grid-cols-2">
          <Row label="Python" value={data.environment.python} />
          <Row label="Platform" value={data.environment.platform} />
          <Row label="Env mode" value={data.environment.environment_mode} />
          <Row
            label="Git"
            value={
              data.git.available
                ? `${data.git.branch} @ ${String(data.git.commit || "").slice(0, 12)}${data.git.dirty ? " (dirty)" : ""}`
                : "n/a"
            }
            mono
          />
        </dl>
      </section>

      <section className="panel overflow-hidden">
        <div className="panel-header">
          <p className="label">Artifacts</p>
          <h3 className="mt-0.5 text-[15px] font-semibold text-ink">Fingerprints & drift</h3>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>vs stored</th>
                <th>vs lock</th>
                <th>Drift</th>
              </tr>
            </thead>
            <tbody>
              {data.artifacts.map((a) => {
                const drifted = (a.probes || []).some((p) => p.drifted);
                return (
                  <tr key={a.name}>
                    <td className="font-medium text-ink">{a.name}</td>
                    <td className="font-mono text-xs text-ink-muted">{a.status}</td>
                    <td className="text-xs">{String(a.fingerprint_matches_stored)}</td>
                    <td className="text-xs">{String(a.fingerprint_matches_lock)}</td>
                    <td className={`text-xs font-semibold ${drifted ? "text-warning" : "text-ink-muted"}`}>
                      {drifted ? "yes" : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid gap-3 md:grid-cols-2">
        <section className="panel px-5 py-4">
          <p className="label">Attestations</p>
          <p className="mt-1 text-sm text-ink">
            {data.attestation_enabled ? "enabled" : "off"} · {data.attestations.length} latest
          </p>
          <ul className="mt-2 space-y-1 font-mono text-[11px] text-ink-muted">
            {data.attestations.map((a) => (
              <li key={a.artifact}>
                {a.artifact}: {a.path}
              </li>
            ))}
          </ul>
        </section>
        <section className="panel px-5 py-4">
          <p className="label">CLI</p>
          <p className="mt-2 font-mono text-xs text-ink-secondary">
            aimake repro --format markdown
          </p>
          <p className="mt-1 font-mono text-xs text-ink-secondary">aimake probe</p>
        </section>
      </div>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-surface-border px-5 py-3">
      <dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</dt>
      <dd className={`max-w-[70%] break-all text-right text-ink-secondary ${mono ? "font-mono text-xs" : "text-sm"}`}>
        {value}
      </dd>
    </div>
  );
}
