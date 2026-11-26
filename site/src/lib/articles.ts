import { getCollection, type CollectionEntry } from 'astro:content';

export type Article = CollectionEntry<'articles'>;

/** Newest first; undated articles last, then by title (getCollection's order is not stable). */
export async function allArticles(): Promise<Article[]> {
  const list = await getCollection('articles');
  return list.sort((a, b) => {
    const da = a.data.date?.getTime() ?? -Infinity;
    const db = b.data.date?.getTime() ?? -Infinity;
    return db - da || a.data.title.localeCompare(b.data.title);
  });
}

/** URL segment for a family page: "Qwen3.5" → "qwen3-5". */
export function familySlug(series: string): string {
  return series.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

/** Families in first-seen order of the (sorted) list, with their articles. */
export function byFamily(list: Article[]): Map<string, Article[]> {
  const out = new Map<string, Article[]>();
  for (const a of list) {
    if (!a.data.series) continue;
    out.set(a.data.series, [...(out.get(a.data.series) ?? []), a]);
  }
  return out;
}

/** URL segment for a setup page: "Single GPU" → "single-gpu". */
export const setupSlug = familySlug;

/** Setups in the order they first published an article, with their articles. */
export function bySetup(list: Article[]): Map<string, Article[]> {
  const out = new Map<string, Article[]>();
  for (const a of [...list].reverse()) {
    if (!a.data.setup) continue;
    out.set(a.data.setup, [...(out.get(a.data.setup) ?? []), a]);
  }
  return out;
}

/** Smallest model first: qwen3.5-4b, qwen3.5-9b, qwen3.5-35b-a3b. No model sorts last. */
export function compareModels(a: string | undefined, b: string | undefined): number {
  if (!a || !b) return a ? -1 : b ? 1 : 0;
  return a.localeCompare(b, 'en', { numeric: true, sensitivity: 'base' });
}

export function sameModel(a: string | undefined, b: string | undefined): boolean {
  return !!a && !!b && a.toLowerCase() === b.toLowerCase();
}

export function readingMinutes(body: string | undefined): number {
  const words = (body ?? '').split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 230));
}

export function formatDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}
