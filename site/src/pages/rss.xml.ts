import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { allArticles } from '../lib/articles';

export async function GET(context: APIContext) {
  const list = await allArticles();
  return rss({
    title: 'Auralis Lab Bench',
    description: 'Complete performance benchmarks of open LLMs on consumer GPUs.',
    site: context.site!,
    items: list.map((a) => ({
      title: a.data.title,
      description: a.data.description,
      pubDate: a.data.date,
      link: `/${a.id}/`,
      categories: a.data.tags,
    })),
  });
}
