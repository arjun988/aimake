"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/graph", label: "Graph" },
  { href: "/builds", label: "Builds" },
  { href: "/registry", label: "Registry" },
  { href: "/cache", label: "Cache" },
  { href: "/settings", label: "Settings" },
];

export function MobileNav() {
  const pathname = usePathname();
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-30 flex border-t border-surface-border bg-surface px-1 py-1.5 md:hidden">
      {LINKS.map((l) => {
        const active =
          l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
        return (
          <Link
            key={l.href}
            href={l.href}
            className={cn(
              "flex-1 rounded-md py-2.5 text-center text-[11px] font-semibold",
              active
                ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-200"
                : "text-ink-muted",
            )}
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
