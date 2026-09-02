"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ErrorState, LoadingState } from "@/components/States";

type DeveloperInfo = {
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
};

export default function DeveloperPage() {
  const [data, setData] = useState<DeveloperInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .developer()
      .then(setData)
      .catch((e) => setError(e.message || "Failed to load developer info"));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;

  return (
    <div className="space-y-4">
      <section className="panel px-5 py-5">
        <p className="label">SDK & tooling</p>
        <h2 className="mt-1 text-xl font-semibold tracking-tight text-ink">
          aimake {data.aimake_version}
        </h2>
        <p className="mt-1 text-sm text-ink-muted">
          Python in-process · TypeScript over HTTP · Docker for CI · TUI for local ops
        </p>
      </section>

      <div className="grid gap-3 lg:grid-cols-2">
        <CodeCard
          label="Python SDK"
          hint={data.python_sdk.import}
          code={data.python_sdk.example}
        />
        <CodeCard
          label="TypeScript SDK"
          hint={data.typescript_sdk.package}
          code={data.typescript_sdk.example}
        />
        <CodeCard
          label="Docker"
          hint={data.docker.image}
          code={`${data.docker.run_build}\n\n${data.docker.run_serve}`}
        />
        <CodeCard
          label="Interactive TUI"
          hint={data.tui.command}
          code={`${data.tui.command}\n\n# ${data.tui.keys}`}
        />
      </div>

      <section className="panel px-5 py-4 text-sm text-ink-secondary">
        <p className="label">Docs</p>
        <ul className="mt-2 space-y-1 font-mono text-xs text-brand-600 dark:text-brand-500">
          <li>docs/SDK.md</li>
          <li>sdk/typescript/</li>
          <li>Dockerfile → ghcr.io</li>
        </ul>
      </section>
    </div>
  );
}

function CodeCard({
  label,
  hint,
  code,
}: {
  label: string;
  hint: string;
  code: string;
}) {
  return (
    <section className="panel overflow-hidden">
      <div className="panel-header">
        <p className="label">{label}</p>
        <p className="mt-0.5 font-mono text-xs text-ink-muted">{hint}</p>
      </div>
      <pre className="overflow-x-auto bg-surface-muted p-4 font-mono text-[11px] leading-relaxed text-ink-secondary">
        {code}
      </pre>
    </section>
  );
}
