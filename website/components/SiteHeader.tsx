"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "@/components/ThemeProvider";
import { cn } from "@/lib/utils";

export function SiteHeader() {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const onDocs = pathname.startsWith("/docs");

  return (
    <header className="sticky top-0 z-40 border-b border-surface-border bg-surface/90 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-2.5 shrink-0">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-600 text-sm font-bold text-white">
            a
          </span>
          <span className="font-display text-[15px] font-semibold tracking-tight text-ink">
            aimake
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          <NavLink href="/docs/introduction" active={onDocs}>
            Docs
          </NavLink>
          <NavLink href="/docs/cli">CLI</NavLink>
          <NavLink href="/docs/sdk-python">SDK</NavLink>
          <NavLink href="/docs/comparison">Compare</NavLink>
          <a
            href="https://github.com/arjun988/aimake"
            target="_blank"
            rel="noreferrer"
            className="rounded-md px-3 py-1.5 text-sm font-medium text-ink-muted transition hover:bg-surface-muted hover:text-ink"
          >
            GitHub
          </a>
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <Link
            href="/docs/quick-start"
            className="hidden rounded-md bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-brand-700 sm:inline-flex"
          >
            Get started
          </Link>
          <button
            type="button"
            onClick={toggle}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-surface-border text-ink-muted transition hover:bg-surface-muted hover:text-ink"
            aria-label="Toggle theme"
          >
            {theme === "dark" ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                <path d="M21 14.5A8.5 8.5 0 1 1 9.5 3a7 7 0 0 0 11.5 11.5z" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}

function NavLink({
  href,
  children,
  active,
}: {
  href: string;
  children: React.ReactNode;
  active?: boolean;
}) {
  const pathname = usePathname();
  const isActive = active ?? pathname === href;
  return (
    <Link
      href={href}
      className={cn(
        "rounded-md px-3 py-1.5 text-sm font-medium transition",
        isActive
          ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-400"
          : "text-ink-muted hover:bg-surface-muted hover:text-ink",
      )}
    >
      {children}
    </Link>
  );
}
