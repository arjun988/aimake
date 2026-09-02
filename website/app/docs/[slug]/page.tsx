import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Markdown } from "@/components/Markdown";
import { TableOfContents } from "@/components/TableOfContents";
import { extractHeadings, getDocBySlug, getDocSlugs } from "@/lib/docs";
import { getAdjacent } from "@/lib/nav";

type Props = { params: Promise<{ slug: string }> };

export async function generateStaticParams() {
  return getDocSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const doc = getDocBySlug(slug);
  if (!doc) return { title: "Not found" };
  return {
    title: doc.meta.title,
    description: doc.meta.description,
  };
}

export default async function DocPage({ params }: Props) {
  const { slug } = await params;
  const doc = getDocBySlug(slug);
  if (!doc) notFound();

  const headings = extractHeadings(doc.content);
  const { prev, next } = getAdjacent(`/docs/${slug}`);

  return (
    <div className="flex gap-10 px-4 py-8 sm:px-6 lg:px-10">
      <article className="min-w-0 flex-1 pb-16">
        <p className="mb-2 font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-600 dark:text-brand-400">
          Documentation
        </p>
        <h1 className="mb-3 font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          {doc.meta.title}
        </h1>
        {doc.meta.description ? (
          <p className="mb-8 text-lg leading-relaxed text-ink-muted">{doc.meta.description}</p>
        ) : (
          <div className="mb-8" />
        )}
        <Markdown content={doc.content} />

        <nav className="mt-14 flex flex-col gap-3 border-t border-surface-border pt-6 sm:flex-row sm:justify-between">
          {prev ? (
            <Link
              href={prev.href}
              className="rounded-lg border border-surface-border px-4 py-3 text-sm transition hover:border-brand-500"
            >
              <span className="block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                Previous
              </span>
              <span className="font-medium text-ink">{prev.title}</span>
            </Link>
          ) : (
            <span />
          )}
          {next ? (
            <Link
              href={next.href}
              className="rounded-lg border border-surface-border px-4 py-3 text-right text-sm transition hover:border-brand-500"
            >
              <span className="block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                Next
              </span>
              <span className="font-medium text-ink">{next.title}</span>
            </Link>
          ) : null}
        </nav>
      </article>

      <aside className="hidden w-52 shrink-0 xl:block">
        <TableOfContents headings={headings} />
      </aside>
    </div>
  );
}
