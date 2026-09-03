# aimake docs website

Public documentation site for [aimake](https://github.com/arjun988/aimake) — Next.js App Router, Tailwind, markdown under `content/docs/`.

The marketing homepage and docs share this app. Doc pages are loaded from `content/docs/*.md` with YAML frontmatter (`title`, `description`). Sidebar order is defined in `lib/nav.ts`.

## Requirements

- Node.js 18+ (20+ recommended)
- npm

## Setup

```bash
cd website
npm install
```

## Development

```bash
npm run dev
```

Open **[http://localhost:3001](http://localhost:3001)**.

The dev server is bound to port **3001** (`next dev -p 3001`) so it can run beside the dashboard (typically port 3000) and `aimake serve` (8765).

## Production build

```bash
npm run build
npm start          # also serves on port 3001
```

## Analytics

[Vercel Analytics](https://vercel.com/docs/analytics) is enabled via `<Analytics />` in `app/layout.tsx`. Page views are collected on production deployments (e.g. [aimake-doc.vercel.app](https://aimake-doc.vercel.app/)). Local `npm run dev` does not send production traffic.

## Project layout

| Path | Purpose |
|------|---------|
| `app/` | Next.js routes (home, `/docs`, `/docs/[slug]`) |
| `content/docs/` | Markdown documentation sources |
| `components/` | Docs sidebar, search, markdown renderer, TOC |
| `lib/docs.ts` | Frontmatter load + heading extraction |
| `lib/nav.ts` | Docs navigation sections |

## Editing docs

1. Add or edit `content/docs/<slug>.md`
2. Include frontmatter:

   ```yaml
   ---
   title: Page title
   description: One-line summary for SEO / cards
   ---
   ```

3. Register the page in `lib/nav.ts` if it is new
4. Cross-link with site paths, e.g. `[Plugins](/docs/plugins)`

## Lint

```bash
npm run lint
```

## Related

- Python package / CLI: repo root `README.md`
- Dashboard UI: `../dashboard/`
- TypeScript client: `../sdk/typescript/`
