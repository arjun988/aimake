"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { flattenNav } from "@/lib/nav";

export function DocsSearch() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const items = useMemo(() => flattenNav(), []);
  const results = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return [];
    return items.filter((i) => i.title.toLowerCase().includes(query)).slice(0, 8);
  }, [q, items]);

  return (
    <div className="relative mb-6">
      <input
        type="search"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Search docs…"
        className="w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-ink outline-none transition placeholder:text-ink-muted focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
      />
      {open && results.length > 0 ? (
        <ul className="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-lg border border-surface-border bg-surface-raised shadow-lift">
          {results.map((r) => (
            <li key={r.href}>
              <Link
                href={r.href}
                className="block px-3 py-2 text-sm text-ink-soft hover:bg-surface-muted hover:text-ink"
                onClick={() => {
                  setQ("");
                  setOpen(false);
                }}
              >
                {r.title}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
