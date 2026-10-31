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

export function readingMinutes(body: string | undefined): number {
  const words = (body ?? '').split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 230));
}

export function formatDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}
