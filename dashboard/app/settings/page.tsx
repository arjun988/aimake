"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ErrorState, LoadingState } from "@/components/States";

type Settings = {
  project: { name: string; version: string; root: string };
  cache: Record<string, unknown>;
  registry: { enabled: boolean; remote: { type: string } | null };
  policy: Record<string, unknown> | null;
  notifications: { slack: boolean; discord: boolean; email: boolean };
  schedule_jobs: string[];
  secrets: { dotenv: boolean; providers: string[] };
};

export default function SettingsPage() {
  const [data, setData] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .settings()
      .then(setData)
      .catch((e) => setError(e.message || "Failed to load settings"));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;

  const remote = data.cache?.remote as Record<string, unknown> | null | undefined;

  return (
    <div className="space-y-4">
      <section className="panel">
        <div className="panel-header">
          <p className="label">Project</p>
          <h3 className="mt-0.5 text-[15px] font-semibold text-ink">{data.project.name}</h3>
        </div>
        <dl className="divide-y divide-surface-border text-sm">
          <Row label="Version" value={data.project.version} />
          <Row label="Root" value={data.project.root} mono />
        </dl>
      </section>

      <div className="grid gap-3 lg:grid-cols-2">
        <section className="panel">
          <div className="panel-header">
            <p className="label">Team cache</p>
            <h3 className="mt-0.5 text-[15px] font-semibold text-ink">Shared remote</h3>
          </div>
          <dl className="divide-y divide-surface-border text-sm">
            <Row label="Enabled" value={remote ? "yes" : "no"} />
            <Row label="Team" value={String(remote?.team_id || "—")} />
            <Row label="Bucket" value={String(remote?.bucket || "—")} mono />
            <Row label="Prefix" value={String(remote?.prefix || "—")} mono />
          </dl>
        </section>

        <section className="panel">
          <div className="panel-header">
            <p className="label">Registry & policy</p>
            <h3 className="mt-0.5 text-[15px] font-semibold text-ink">Promote gates</h3>
          </div>
          <dl className="divide-y divide-surface-border text-sm">
            <Row label="Registry" value={data.registry.enabled ? "enabled" : "off"} />
            <Row
              label="Remote"
              value={data.registry.remote?.type || "—"}
            />
            <Row
              label="Policy"
              value={data.policy ? JSON.stringify(data.policy) : "none"}
              mono
            />
          </dl>
        </section>

        <section className="panel">
          <div className="panel-header">
            <p className="label">Notifications</p>
            <h3 className="mt-0.5 text-[15px] font-semibold text-ink">Channels</h3>
          </div>
          <dl className="divide-y divide-surface-border text-sm">
            <Row label="Slack" value={data.notifications.slack ? "on" : "off"} />
            <Row label="Discord" value={data.notifications.discord ? "on" : "off"} />
            <Row label="Email" value={data.notifications.email ? "on" : "off"} />
          </dl>
        </section>

        <section className="panel">
          <div className="panel-header">
            <p className="label">Schedule & secrets</p>
            <h3 className="mt-0.5 text-[15px] font-semibold text-ink">Ops</h3>
          </div>
          <dl className="divide-y divide-surface-border text-sm">
            <Row
              label="Jobs"
              value={
                data.schedule_jobs.length
                  ? data.schedule_jobs.join(", ")
                  : "none (use aimake schedule)"
              }
            />
            <Row label=".env" value={data.secrets.dotenv ? "enabled" : "off"} />
            <Row
              label="Providers"
              value={data.secrets.providers.join(", ") || "—"}
            />
          </dl>
        </section>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 px-5 py-3">
      <dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
        {label}
      </dt>
      <dd
        className={`max-w-[70%] break-all text-right text-ink-secondary ${
          mono ? "font-mono text-xs" : "text-sm"
        }`}
      >
        {value}
      </dd>
    </div>
  );
}
