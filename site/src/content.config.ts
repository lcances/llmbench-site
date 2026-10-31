import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

// One entry per articles/<slug>/index.md. The id is the folder name, so the
// URL matches the slug the writing app pinned on first publish.
const articles = defineCollection({
  loader: glob({
    base: '../articles',
    pattern: '*/index.md',
    generateId: ({ entry }) => entry.split('/')[0],
  }),
  schema: ({ image }) =>
    z.object({
      title: z.string(),
      description: z.string(),
      tags: z.array(z.string()).default([]),
      cover: image().optional(),
      // Owning issue in the writing app; not shown.
      issue: z.string().optional(),
      date: z.coerce.date().optional(),
      // Model family, e.g. "Qwen3.5" — groups articles on a family page.
      series: z.string().optional(),
      // Link to the reduced version on dev.to, when there is one.
      devto: z.string().url().optional(),
    }),
});

export const collections = { articles };
