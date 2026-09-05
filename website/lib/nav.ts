export type NavItem = {
  title: string;
  href: string;
};

export type NavSection = {
  title: string;
  items: NavItem[];
};

/** Sidebar navigation — mirrors content/docs/*.md order */
export const DOCS_NAV: NavSection[] = [
  {
    title: "Get started",
    items: [
      { title: "Introduction", href: "/docs/introduction" },
      { title: "Installation", href: "/docs/installation" },
      { title: "Quick start", href: "/docs/quick-start" },
      { title: "Core concepts", href: "/docs/concepts" },
    ],
  },
  {
    title: "Guides",
    items: [
      { title: "How aimake works", href: "/docs/how-it-works" },
      { title: "Writing aimake.yaml", href: "/docs/configuration" },
      { title: "Fingerprints & caching", href: "/docs/caching" },
      { title: "CI/CD", href: "/docs/ci-cd" },
      { title: "Migration", href: "/docs/migration" },
    ],
  },
  {
    title: "Features",
    items: [
      { title: "CLI reference", href: "/docs/cli" },
      { title: "Remote & team cache", href: "/docs/remote-cache" },
      { title: "GPU & workers", href: "/docs/workers" },
      { title: "Experiments", href: "/docs/experiments" },
      { title: "Artifact registry", href: "/docs/registry" },
      { title: "Trust & reproducibility", href: "/docs/trust" },
      { title: "Team & production", href: "/docs/team" },
      { title: "Dashboard", href: "/docs/dashboard" },
    ],
  },
  {
    title: "Integrations",
    items: [
      { title: "Plugins overview", href: "/docs/plugins" },
      { title: "Adapters", href: "/docs/adapters" },
      { title: "Comparison", href: "/docs/comparison" },
    ],
  },
  {
    title: "SDK & tooling",
    items: [
      { title: "Python SDK", href: "/docs/sdk-python" },
      { title: "TypeScript SDK", href: "/docs/sdk-typescript" },
      { title: "Docker", href: "/docs/docker" },
      { title: "Interactive TUI", href: "/docs/tui" },
      { title: "VS Code / Cursor", href: "/docs/vscode-extension" },
    ],
  },
  {
    title: "Project",
    items: [
      { title: "Architecture", href: "/docs/architecture" },
      { title: "Security", href: "/docs/security" },
      { title: "Contributing", href: "/docs/contributing" },
      { title: "Changelog", href: "/docs/changelog" },
    ],
  },
];

export function flattenNav(): NavItem[] {
  return DOCS_NAV.flatMap((s) => s.items);
}

export function getAdjacent(href: string): {
  prev: NavItem | null;
  next: NavItem | null;
} {
  const flat = flattenNav();
  const i = flat.findIndex((x) => x.href === href);
  return {
    prev: i > 0 ? flat[i - 1] : null,
    next: i >= 0 && i < flat.length - 1 ? flat[i + 1] : null,
  };
}
