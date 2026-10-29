#!/usr/bin/env python3
"""Sync the posts a push changed to dev.to, as drafts. Standard library only.

The writing app pushes `posts/<slug>/index.md` (dev.to markdown) and its PNGs in
`posts/<slug>/images/` straight to main after its own review; this turns each
changed post into a dev.to article. An article is created once, unpublished, and
updated forever after — publishing it is done by hand on dev.to, and an update
never sends `published`, so it can't pull a live article back to draft.

The dev.to article id is recorded in `.devto/articles.json` and committed back by
the workflow. A missing id is recovered by matching titles against the account's
own articles, drafts included, before falling back to creating one: duplicating
an article is the failure this is built to avoid.

Environment:
    DEVTO_API_KEY       Forem API key. Absent  -> report and exit 0 (nothing sent).
    DEVTO_DRY_RUN       Truthy -> print what would be sent, make no requests.
    GITHUB_REPOSITORY   owner/repo the images are served from (set by Actions).
    BEFORE              Commit main was at before the push. Absent, or not a
                        commit (a manual run) -> sync every post.
"""

import json
import os
import re
import subprocess
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
# Which posts
# --------------------------------------------------------------------------- #

def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def changed_posts(before):
    """index.md of every post the push touched, or of every post at all."""
    every = sorted(POSTS.glob("*/index.md")) if POSTS.is_dir() else []
    if not before or set(before) == {"0"}:
        return every
    try:
        names = git("diff", "--name-only", before, "HEAD", "--", str(POSTS)).splitlines()
    except subprocess.CalledProcessError:
        notice(f"cannot diff from {before}; syncing every post")
        return every
    slugs = {Path(n).parts[1] for n in names if len(Path(n).parts) > 2}
    # A post deleted from the repo is left alone on dev.to.
    return [p for p in every if p.parent.name in slugs]


# --------------------------------------------------------------------------- #
# Front matter
# --------------------------------------------------------------------------- #

def split_front_matter(text):
    """(front matter dict, body). The writing app controls this format precisely:
    flat `key: value` lines, lists as `[a, b]`, text in one pair of quotes that is
    stripped as a pair — quotes inside the value are kept as written."""
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
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            meta[key.strip()] = value
    return meta, body


def tags_from(tags):
    """dev.to tags: lower-case, alphanumeric, at most four."""
    out = []
    for c in tags or []:
        t = re.sub(r"[^a-z0-9]", "", c.lower())
        if t and t not in out:
            out.append(t)
    return out[:4]


# --------------------------------------------------------------------------- #
# Body
# --------------------------------------------------------------------------- #

_IMG = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)\)")
_BLANKS = re.compile(r"\n{3,}")


def image_url(src, post_dir, base, slug, missing):
    """A post-relative image as a raw GitHub URL. SVG never reaches dev.to: its
    image CDN mangles it, and the writing app draws a PNG for every chart."""
    if src.lower().endswith(".svg"):
        fail(f"{slug}: links {src}, an SVG — dev.to needs a PNG")
    if not (post_dir / src).is_file():
        missing.append(src)
    return f"{base}{src}"


def transform(body, post_dir, base, slug):
    """Post markdown -> dev.to markdown: images become absolute URLs."""
    missing = []

    def fix_img(m):
        src, alt = m.group("src"), m.group("alt")
        if src.startswith(("http://", "https://")):
            return m.group(0)
        return f"![{alt}]({image_url(src, post_dir, base, slug, missing)})"

    body = _IMG.sub(fix_img, body)
    if missing:
        fail(f"{slug}: no file for {', '.join(sorted(set(missing)))}")
    return _BLANKS.sub("\n\n", body).strip() + "\n"


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


def existing_by_title(key):
    """title -> id over the account's own articles, drafts included.

    Recovers from a run that created an article and died before the mapping was
    committed — without this, the next run would create a duplicate.
    """
    out = {}
    for page in range(1, 11):
        got = request("GET", f"/articles/me/all?per_page=100&page={page}", key) or []
        for a in got:
            out.setdefault(a.get("title"), a["id"])
        if len(got) < 100:
            break
    return out


def main():
    dry_run = (os.environ.get("DEVTO_DRY_RUN") or "").strip().lower() \
        not in ("", "0", "false", "no")
    key = (os.environ.get("DEVTO_API_KEY") or "").strip()
    repo = (os.environ.get("GITHUB_REPOSITORY") or "").strip()
    if not repo:
        fail("GITHUB_REPOSITORY is not set — cannot tell where the images live")

    posts = changed_posts((os.environ.get("BEFORE") or "").strip())
    if not posts:
        notice("no changed posts to sync")
        return
    if not key and not dry_run:
        notice("DEVTO_API_KEY is not set — skipping dev.to sync. "
               "Add the secret and re-run this workflow to sync every post.")
        return

    # Images are served at the exact commit being synced, so a later push can't
    # change what an article already shows.
    sha = git("rev-parse", "HEAD")
    mapping = json.loads(MAPPING.read_text()) if MAPPING.is_file() else {}
    recovered = None

    for md in posts:
        slug = md.parent.name
        meta, body = split_front_matter(md.read_text())
        if not meta.get("title"):
            fail(f"{slug}: post has no title in its front matter")
        base = f"https://raw.githubusercontent.com/{repo}/{sha}/{POSTS}/{slug}/"
        article = {
            "title": meta["title"],
            "body_markdown": transform(body, md.parent, base, slug),
            "series": SERIES,
            "tags": tags_from(meta.get("tags")),
        }
        if meta.get("description"):
            article["description"] = meta["description"]
        if meta.get("cover"):
            missing = []
            article["main_image"] = image_url(meta["cover"], md.parent, base, slug, missing)
            if missing:
                fail(f"{slug}: no file for the cover {meta['cover']}")

        article_id = (mapping.get(slug) or {}).get("id")
        if not article_id and key and not dry_run:
            if recovered is None:
                recovered = existing_by_title(key)
            article_id = recovered.get(meta["title"])

        if dry_run:
            notice(f"[dry run] would {'update ' + str(article_id) if article_id else 'create a draft for'}"
                   f" {slug}")
            print(json.dumps({k: (v if k != "body_markdown" else v[:600] + " …")
                              for k, v in article.items()}, indent=2))
            continue

        if article_id:
            got = request("PUT", f"/articles/{article_id}", key, {"article": article})
            notice(f"updated {slug} -> {got.get('url')}")
        else:
            got = request("POST", "/articles", key, {"article": {**article, "published": False}})
            article_id = got.get("id")
            notice(f"created a draft for {slug} -> {got.get('url')}")
        # Written after every article, not at the end: a crash must not lose an
        # id we have already spent a creation on.
        mapping[slug] = {"id": article_id, "url": got.get("url"), "series": SERIES}
        MAPPING.parent.mkdir(parents=True, exist_ok=True)
        MAPPING.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n")
        time.sleep(PAUSE_S)


if __name__ == "__main__":
    main()
