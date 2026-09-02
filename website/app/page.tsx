import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <section className="relative overflow-hidden border-b border-surface-border">
        <div className="hero-grid absolute inset-0" aria-hidden />
        <div className="relative mx-auto max-w-5xl px-4 pb-20 pt-16 sm:px-6 sm:pt-24 lg:px-8 lg:pb-28">
          <p className="animate-fade-up font-mono text-xs font-semibold uppercase tracking-[0.14em] text-brand-600 dark:text-brand-400">
            Documentation
          </p>
          <h1 className="animate-fade-up mt-4 font-display text-5xl font-semibold tracking-tight text-ink sm:text-6xl md:text-7xl">
            aimake
          </h1>
          <p className="animate-fade-up mt-5 max-w-xl text-lg leading-relaxed text-ink-muted sm:text-xl">
            The incremental build system for AI pipelines. Skip unchanged steps.
            Cache embeddings and evals. See cost before you run.
          </p>
          <div className="animate-fade-up mt-8 flex flex-wrap gap-3">
            <Link
              href="/docs/quick-start"
              className="inline-flex items-center rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white shadow-soft transition hover:bg-brand-700"
            >
              Get started
            </Link>
            <Link
              href="/docs/introduction"
              className="inline-flex items-center rounded-lg border border-surface-border bg-surface px-5 py-2.5 text-sm font-semibold text-ink transition hover:bg-surface-muted"
            >
              Read the docs
            </Link>
            <a
              href="https://pypi.org/project/aimake/"
              className="inline-flex items-center rounded-lg px-5 py-2.5 font-mono text-sm text-ink-muted transition hover:text-ink"
            >
              pip install aimake
            </a>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 py-16 sm:px-6 lg:px-8">
        <h2 className="font-display text-2xl font-semibold tracking-tight text-ink">
          Start here
        </h2>
        <p className="mt-2 max-w-2xl text-ink-muted">
          Structured like Node.js and OpenCV docs — concepts first, then guides,
          then reference.
        </p>
        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[
            {
              href: "/docs/quick-start",
              title: "Quick start",
              body: "Install, init a project, and run your first incremental build in minutes.",
            },
            {
              href: "/docs/concepts",
              title: "Core concepts",
              body: "Artifacts, fingerprints, the DAG, cache hits, and why plans show cost.",
            },
            {
              href: "/docs/cli",
              title: "CLI reference",
              body: "Every command — build, plan, explain, registry, schedule, tui, and more.",
            },
            {
              href: "/docs/sdk-python",
              title: "Python & TypeScript SDKs",
              body: "Embed aimake in CI scripts and control planes with a stable API.",
            },
            {
              href: "/docs/comparison",
              title: "Compare tools",
              body: "How aimake relates to Make, DVC, Airflow, Prefect, and MLflow.",
            },
            {
              href: "/docs/docker",
              title: "Docker & GHCR",
              body: "Run reproducible builds in CI with the official container image.",
            },
          ].map((card) => (
            <Link
              key={card.href}
              href={card.href}
              className="group block border-t border-surface-border pt-4 transition hover:border-brand-500"
            >
              <h3 className="font-display text-lg font-semibold text-ink group-hover:text-brand-600 dark:group-hover:text-brand-400">
                {card.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-muted">{card.body}</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="border-t border-surface-border bg-surface-muted">
        <div className="mx-auto max-w-5xl px-4 py-14 sm:px-6 lg:px-8">
          <h2 className="font-display text-2xl font-semibold text-ink">Install</h2>
          <pre className="mt-4 overflow-x-auto rounded-lg border border-surface-border bg-[#0b1220] p-4 font-mono text-sm text-slate-100">
            {`pip install aimake
aimake init
aimake plan
aimake build`}
          </pre>
          <p className="mt-4 text-sm text-ink-muted">
            Requires Python 3.11+. Optional extras:{" "}
            <code className="font-mono text-brand-600">s3</code>,{" "}
            <code className="font-mono text-brand-600">huggingface</code>,{" "}
            <code className="font-mono text-brand-600">wandb</code>,{" "}
            <code className="font-mono text-brand-600">experiments</code>.
          </p>
        </div>
      </section>

      <footer className="border-t border-surface-border">
        <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-8 text-sm text-ink-muted sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p>aimake · Apache-2.0</p>
          <div className="flex gap-4">
            <a href="https://github.com/arjun988/aimake" className="hover:text-ink">
              GitHub
            </a>
            <a href="https://pypi.org/project/aimake/" className="hover:text-ink">
              PyPI
            </a>
            <Link href="/docs/changelog" className="hover:text-ink">
              Changelog
            </Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
