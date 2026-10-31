// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// The complete articles live in ../articles/<slug>/index.md, written by the
// writing app; this project only turns them into bench.auralis-lab.com.
export default defineConfig({
  site: 'https://bench.auralis-lab.com',
  integrations: [sitemap()],
  markdown: {
    shikiConfig: { theme: 'github-light' },
  },
});
