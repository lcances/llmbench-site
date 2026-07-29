#!/usr/bin/env python3
"""Syndicate the published posts to dev.to. Standard library only.

Runs after — and only after — the Pages deploy succeeded, so every article's
`canonical_url` points at a page that exists. Each post is created once and
updated forever after: the dev.to article id is recorded in `.devto/articles.json`
and committed back by the workflow, and a missing id is recovered by matching
canonical URLs against the account's own articles before falling back to creating
one. Duplicating an article is the failure this is built to avoid.

Environment:
    DEVTO_API_KEY   Forem API key. Absent  -> report and exit 0 (nothing published).
    DEVTO_DRY_RUN   Truthy -> print what would be sent, make no requests.
    SITE_URL        Base URL of the deployed site (from the deploy job).
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://dev.to/api"
SERIES = "llmbench"
MAPPING = Path(".devto/articles.json")
POSTS = Path("posts")
PAUSE_S = 3          # Forem throttles article writes; be a good citizen.


def notice(msg):
    print(f"::notice::{msg}")


def fail(msg):
    print(f"::error::{msg}")
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Front matter
# --------------------------------------------------------------------------- #

def split_front_matter(text):
    """(front matter dict, body). The generator controls this format precisely."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw, body = text[4:end], text[end + 5:]
    meta = {}
    for line in raw.splitlines():
        if not line.strip() or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key.strip()] = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key.strip()] = value.strip('"').strip("'")
    return meta, body


def tags_from(categories):
    """dev.to tags: lower-case, alphanumeric, at most four."""
    out = []
    for c in categories or []:
        t = re.sub(r"[^a-z0-9]", "", c.lower())
        if t and t not in out:
            out.append(t)
    return out[:4]


# --------------------------------------------------------------------------- #
# Body transform — ordered, deterministic, and lossy on purpose
# --------------------------------------------------------------------------- #

_SITE_ONLY = re.compile(
    r"<!-- llmbench:site-only:begin -->.*?<!-- llmbench:site-only:end -->",
    re.DOTALL)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_IMG = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)\)(?P<attrs>\{[^}]*\})?")
_LINK_ATTRS = re.compile(r"(\]\([^)\s]+\))\{[^}]*\}")
_HEADING_ATTRS = re.compile(r"^(#{1,6} .*?)\s*\{[^}]*\}\s*$", re.MULTILINE)
_FENCE = re.compile(r"^:{3,}.*$", re.MULTILINE)
_REL_LINK = re.compile(r"\]\((?!https?://|/|#)([^)\s]+)\)")
_SHORTCODE = re.compile(r"\{\{<.*?>\}\}", re.DOTALL)
# The site rescales these spans live from their kWh basis; syndicated copies keep
# the number the post was generated with and drop the wrapper.
_DATA_SPAN = re.compile(r'<span data-kwh-per-1m="[^"]*">(?P<text>[^<]*)</span>')
_BLANKS = re.compile(r"\n{3,}")


def transform(body, post_dir, base_url, slug):
    """Quarto markdown -> dev.to markdown. Order matters; see each step."""
    post_url = f"{base_url}posts/{slug}/"

    # 1. Site-only widgets (the price slider) go before generic comment
    #    stripping, or their markers vanish and the widget ships as dead HTML.
    body = _SITE_ONLY.sub("", body)

    # 2. Sentinel comments carry no reader-facing meaning.
    body = _COMMENT.sub("", body)

    # 3. One theme only: dev.to has no dark/light pairing. Drop the dark image
    #    lines, keep the light ones (their attribute blocks go in step 5).
    body = "\n".join(
        ln for ln in body.splitlines()
        if not (".dark-content" in ln and ln.lstrip().startswith("!["))
    )

    # 4. Any remaining div fences are Quarto-only syntax; keep their contents.
    body = _FENCE.sub("", body)

    # 5. Images: absolute URLs on the deployed site, and PNG instead of SVG —
    #    dev.to proxies images through a CDN that mangles SVG.
    missing = []

    def fix_img(m):
        src, alt = m.group("src"), m.group("alt")
        if src.startswith(("http://", "https://")):
            return f"![{alt}]({src})"
        png = re.sub(r"\.svg$", ".png", src)
        if not (post_dir / png).is_file():
            missing.append(png)
        return f"![{alt}]({post_url}{png})"

    body = _IMG.sub(fix_img, body)
    if missing:
        fail(f"{slug}: no raster for {', '.join(sorted(set(missing)))} — dev.to "
             f"cannot use the SVG, so the pipeline must export a PNG for every "
             f"figure the post shows")

    # 6. Unwrap the interactive-cost spans: without the slider they are inert
    #    markup around a number that is already correct.
    body = _DATA_SPAN.sub(lambda m: m.group("text"), body)

    # 7. Pandoc attribute blocks on links and headings mean nothing to dev.to.
    body = _LINK_ATTRS.sub(r"\1", body)
    body = _HEADING_ATTRS.sub(r"\1", body)

    # 8. Remaining relative links (the companion board page) need the site.
    body = _REL_LINK.sub(lambda m: f"]({post_url}{m.group(1)})", body)

    # 9. Shortcodes would ship as literal braces; the generator emits none, so
    #    finding one means something upstream changed.
    if _SHORTCODE.search(body):
        fail(f"{slug}: body contains a Quarto shortcode, which dev.to cannot render")

    body = _BLANKS.sub("\n\n", body).strip()
    body += (f"\n\n---\n\n*Originally published at [{post_url}]({post_url}), where "
             f"the charts are theme-aware and the cost figures are interactive.*\n")
    return body


# --------------------------------------------------------------------------- #
# Forem API
# --------------------------------------------------------------------------- #

def request(method, path, key, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method,
                                 headers={"api-key": key,
                                          "Content-Type": "application/json",
                                          "Accept": "application/vnd.forem.api-v1+json",
                                          "User-Agent": "llmbench-publisher"})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or "{}")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 1:
                notice("dev.to rate limit hit; waiting 30 s")
                time.sleep(30)
                continue
            fail(f"dev.to {method} {path} failed: {e.code} {e.read()[:400]!r}")
        except urllib.error.URLError as e:
            fail(f"dev.to {method} {path} unreachable: {e.reason}")


def existing_by_canonical(key):
    """canonical_url -> id over the account's own articles.

    Recovers from a run that created an article and died before the mapping was
    committed — without this, the next run would create a duplicate.
    """
    out = {}
    for page in (1, 2):
        got = request("GET", f"/articles/me/all?per_page=100&page={page}", key) or []
        for a in got:
            if a.get("canonical_url"):
                out[a["canonical_url"].rstrip("/")] = a["id"]
        if len(got) < 100:
            break
    return out


def main():
    base_url = (os.environ.get("SITE_URL")
                or "https://lcances.github.io/llmbench-site/")
    if not base_url.endswith("/"):
        base_url += "/"
    dry_run = (os.environ.get("DEVTO_DRY_RUN") or "").strip().lower() \
        not in ("", "0", "false", "no")
    key = (os.environ.get("DEVTO_API_KEY") or "").strip()

    posts = sorted(p for p in POSTS.glob("*/index.qmd")) if POSTS.is_dir() else []
    if not posts:
        notice("no posts to syndicate yet")
        return
    if not key and not dry_run:
        notice("DEVTO_API_KEY is not set — skipping dev.to syndication. "
               "Add the secret and re-run this workflow to publish.")
        return

    mapping = json.loads(MAPPING.read_text()) if MAPPING.is_file() else {}
    recovered = {} if (dry_run or not key) else existing_by_canonical(key)

    for qmd in posts:
        slug = qmd.parent.name
        meta, body = split_front_matter(qmd.read_text())
        if not meta.get("title"):
            fail(f"{slug}: post has no title in its front matter")
        canonical = f"{base_url}posts/{slug}/"
        article = {
            "title": meta["title"],
            "body_markdown": transform(body, qmd.parent, base_url, slug),
            "published": True,
            "series": SERIES,
            "canonical_url": canonical,
            "tags": tags_from(meta.get("categories")),
        }
        if meta.get("description"):
            article["description"] = meta["description"]
        if meta.get("image"):
            article["main_image"] = f"{canonical}{meta['image']}"

        article_id = (mapping.get(slug) or {}).get("id") \
            or recovered.get(canonical.rstrip("/"))
        if dry_run:
            notice(f"[dry run] would {'update ' + str(article_id) if article_id else 'create'}"
                   f" {slug}")
            print(json.dumps({k: (v if k != "body_markdown" else v[:600] + " …")
                              for k, v in article.items()}, indent=2))
            continue

        if article_id:
            got = request("PUT", f"/articles/{article_id}", key, {"article": article})
            notice(f"updated {slug} -> {got.get('url')}")
        else:
            got = request("POST", "/articles", key, {"article": article})
            article_id = got.get("id")
            notice(f"created {slug} -> {got.get('url')}")
        # Written after every article, not at the end: a crash must not lose an
        # id we have already spent a creation on.
        mapping[slug] = {"id": article_id, "url": got.get("url"), "series": SERIES}
        MAPPING.parent.mkdir(parents=True, exist_ok=True)
        MAPPING.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n")
        time.sleep(PAUSE_S)


if __name__ == "__main__":
    main()
