# llmbench — articles

Source of the **llmbench** articles: the complete versions on
[bench.auralis-lab.com](https://bench.auralis-lab.com), the shorter versions on dev.to. Performance benchmarks of small
and medium open-source LLMs on consumer hardware — prefill/decode curves,
time-to-first-token, max context, VRAM and power, across runtimes (llama.cpp,
Ollama, vLLM) pushed to their tuning limits.

How content gets here:

- Articles are written and reviewed in a private writing app, which pushes each
  one straight to `main` as `posts/<slug>/index.md` (dev.to markdown) with its
  charts as PNGs in `posts/<slug>/images/`. Every number and every figure is
  computed from measured results — nothing is hand-typed.
- A push to `posts/` runs the `publish` workflow: each changed post becomes a
  **dev.to draft**, or updates its existing article. Images are served from this
  repo at the commit being synced. Making an article public is done by hand on
  dev.to.
- `.devto/articles.json` maps each post to its dev.to article, so a post is
  created once and updated after that.
- The complete articles arrive the same way in `articles/<slug>/index.md`, with
  their charts in `articles/<slug>/images/`. A push to `articles/` or `site/`
  runs the `site` workflow: `site/` is an [Astro](https://astro.build) project
  that builds the articles into static pages and deploys them to Cloudflare
  Pages (secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`). Run it
  locally with `npm ci && npm run dev` in `site/`.
- `templates/` holds the writing app's series templates.

## About the authoring

The benchmark harness and the chart/article generators behind these posts were
built with [Claude Code](https://claude.com/claude-code) as a pair-programming
tool. Every benchmark was run on my own box, every design decision is mine, and
every article is reviewed by me before it goes live — I am the author of what is
published here.

— Léo Cances
