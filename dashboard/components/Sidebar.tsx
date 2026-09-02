"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Overview", icon: OverviewIcon },
  { href: "/graph", label: "Graph", icon: GraphIcon },
  { href: "/builds", label: "Builds", icon: BuildsIcon },
  { href: "/experiments", label: "Experiments", icon: ExperimentsIcon },
  { href: "/registry", label: "Registry", icon: RegistryIcon },
  { href: "/cache", label: "Cache", icon: CacheIcon },
  { href: "/settings", label: "Settings", icon: SettingsIcon },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 hidden h-screen w-[232px] shrink-0 flex-col bg-nav px-3 py-5 md:flex">
      <Link href="/" className="mb-8 flex items-center gap-2.5 px-3">
        <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-600 text-[13px] font-bold text-white">
          a
        </span>
        <div>
          <div className="text-[15px] font-semibold tracking-tight text-white">
            aimake
          </div>
          <div className="text-[11px] font-medium text-nav-muted">Console</div>
        </div>
      </Link>

      <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.1em] text-nav-muted">
        Workspace
      </p>

      <nav className="flex flex-1 flex-col gap-0.5">
        {NAV.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "relative flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium transition",
                active
                  ? "bg-nav-active text-white"
                  : "text-nav-muted hover:bg-nav-hover hover:text-white",
              )}
            >
              {active ? (
                <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-brand-500" />
              ) : null}
              <Icon active={active} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="mx-1 mt-auto rounded-lg border border-nav-border bg-white/[0.03] px-3 py-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-nav-muted">
          API
        </p>
        <p className="mt-1 break-all font-mono text-[10px] leading-relaxed text-white/70">
          {process.env.NEXT_PUBLIC_AIMAKE_API || "http://127.0.0.1:8765"}
        </p>
      </div>
    </aside>
  );
}

function OverviewIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden className={active ? "text-brand-500" : ""}>
      <rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.4" />
      <rect x="9" y="1.5" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.4" />
      <rect x="1.5" y="9" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.4" />
      <rect x="9" y="9" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

function GraphIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden className={active ? "text-brand-500" : ""}>
      <circle cx="3.5" cy="3.5" r="1.6" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="12.5" cy="3.5" r="1.6" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="8" cy="12.5" r="1.6" stroke="currentColor" strokeWidth="1.4" />
      <path d="M5 4.2 L11 4.2 M4.2 5 L7.2 11 M11.8 5 L8.8 11" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function BuildsIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden className={active ? "text-brand-500" : ""}>
      <path d="M2.5 4h11M2.5 8h11M2.5 12h7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function ExperimentsIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden className={active ? "text-brand-500" : ""}>
      <path d="M6 2.5h4M7 2.5v4.2L4.2 13.2a1.2 1.2 0 0 0 1 1.8h5.6a1.2 1.2 0 0 0 1-1.8L9 6.7V2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function RegistryIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden className={active ? "text-brand-500" : ""}>
      <rect x="2" y="2.5" width="12" height="3.2" rx="1" stroke="currentColor" strokeWidth="1.4" />
      <rect x="2" y="6.4" width="12" height="3.2" rx="1" stroke="currentColor" strokeWidth="1.4" />
      <rect x="2" y="10.3" width="12" height="3.2" rx="1" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

function CacheIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden className={active ? "text-brand-500" : ""}>
      <ellipse cx="8" cy="4.2" rx="5.2" ry="1.8" stroke="currentColor" strokeWidth="1.4" />
      <path d="M2.8 4.2v3.8c0 1 2.3 1.8 5.2 1.8s5.2-.8 5.2-1.8V4.2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M2.8 8v3.8c0 1 2.3 1.8 5.2 1.8s5.2-.8 5.2-1.8V8" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

function SettingsIcon({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden className={active ? "text-brand-500" : ""}>
      <circle cx="8" cy="8" r="2.2" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M8 1.5v1.4M8 13.1V14.5M1.5 8H2.9M13.1 8H14.5M3.4 3.4l1 1M11.6 11.6l1 1M12.6 3.4l-1 1M4.4 11.6l-1 1"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
