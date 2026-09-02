"use client";

import { useState } from "react";
import { DocsSidebar } from "@/components/DocsSidebar";
import { DocsSearch } from "@/components/DocsSearch";

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-7xl">
      {/* Desktop sidebar */}
      <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-60 shrink-0 overflow-y-auto border-r border-surface-border px-4 py-6 lg:block">
        <DocsSearch />
        <DocsSidebar />
      </aside>

      {/* Mobile nav */}
      <div className="fixed bottom-4 left-4 z-30 lg:hidden">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm font-semibold shadow-soft"
        >
          Menu
        </button>
      </div>
      {open ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-ink/40"
            aria-label="Close"
            onClick={() => setOpen(false)}
          />
          <div className="absolute bottom-0 left-0 right-0 max-h-[80vh] overflow-y-auto rounded-t-2xl border border-surface-border bg-surface p-4 shadow-lift">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-semibold">Documentation</p>
              <button type="button" className="text-sm text-ink-muted" onClick={() => setOpen(false)}>
                Close
              </button>
            </div>
            <DocsSearch />
            <DocsSidebar onNavigate={() => setOpen(false)} />
          </div>
        </div>
      ) : null}

      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
