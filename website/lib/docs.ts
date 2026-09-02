import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { slugify } from "@/lib/utils";

const CONTENT_DIR = path.join(process.cwd(), "content", "docs");

export type DocMeta = {
  title: string;
  description?: string;
  order?: number;
};

export type DocPage = {
  slug: string;
  meta: DocMeta;
  content: string;
};

export function getDocSlugs(): string[] {
  if (!fs.existsSync(CONTENT_DIR)) return [];
  return fs
    .readdirSync(CONTENT_DIR)
    .filter((f) => f.endsWith(".md"))
    .map((f) => f.replace(/\.md$/, ""));
}

export function getDocBySlug(slug: string): DocPage | null {
  const full = path.join(CONTENT_DIR, `${slug}.md`);
  if (!fs.existsSync(full)) return null;
  const raw = fs.readFileSync(full, "utf8");
  const { data, content } = matter(raw);
  return {
    slug,
    meta: {
      title: (data.title as string) || slug,
      description: data.description as string | undefined,
      order: data.order as number | undefined,
    },
    content,
  };
}

export function getAllDocs(): DocPage[] {
  return getDocSlugs()
    .map((slug) => getDocBySlug(slug)!)
    .filter(Boolean);
}

/** Extract h2/h3 headings for on-page TOC */
export function extractHeadings(markdown: string): { id: string; text: string; level: number }[] {
  const lines = markdown.split("\n");
  const out: { id: string; text: string; level: number }[] = [];
  for (const line of lines) {
    const m = /^(#{2,3})\s+(.+)$/.exec(line.trim());
    if (!m) continue;
    const level = m[1].length;
    const text = m[2].replace(/`/g, "").trim();
    const id = slugify(text);
    out.push({ id, text, level });
  }
  return out;
}
