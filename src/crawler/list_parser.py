# -*- coding: utf-8 -*-
"""Category listing collection.

Measured problem: a listing page shows ~28 posts but ~55 post-shaped links,
because sidebar widgets (recent/popular posts) repeat on every page. Links that
appear on many pages are widget chrome; genuine list entries appear on exactly
one listing page. The final count is validated against the advertised count
(172 / 181) and any mismatch is reported, never silently corrected.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from . import config


def extract_post_links(html: str, base_url: str = config.BASE_URL) -> list:
    """Return post-shaped links (path /entry/* or /N) in document order."""
    soup = BeautifulSoup(html, "html.parser")
    links, seen = [], set()
    for a in soup.select("a[href]"):
        href = urljoin(base_url, a["href"])
        parsed = urlparse(href)
        if parsed.netloc != urlparse(base_url).netloc:
            continue
        path = parsed.path
        if not (re.fullmatch(r"/\d+", path) or path.startswith("/entry/")):
            continue
        clean = f"{parsed.scheme}://{parsed.netloc}{path}"
        if clean in seen:
            continue
        seen.add(clean)
        links.append(clean)
    return links


def split_chrome_links(pages: list) -> tuple:
    """Split links into (list_entries, chrome) by cross-page repetition.

    pages: list of per-page link lists (document order preserved).
    A link seen on more than CHROME_REPEAT_FRACTION of pages is chrome.
    With a single page there is no signal, so nothing is classified as chrome.
    """
    if not pages:
        return [], []
    n_pages = len(pages)
    counts: dict = {}
    first_seen: dict = {}
    for page_idx, links in enumerate(pages):
        for order, link in enumerate(links):
            counts[link] = counts.get(link, 0) + 1
            first_seen.setdefault(link, (page_idx, order))
    if n_pages == 1:
        ordered = sorted(counts, key=lambda u: first_seen[u])
        return ordered, []
    threshold = max(2, int(n_pages * config.CHROME_REPEAT_FRACTION) + 1)
    entries = [u for u, c in counts.items() if c < threshold]
    chrome = [u for u, c in counts.items() if c >= threshold]
    entries.sort(key=lambda u: first_seen[u])
    return entries, chrome


def collect_category(fetcher, category_url: str, log=print) -> dict:
    """Walk ?page=1..N and return {'posts': [...], 'chrome': [...], 'pages': N}.

    Stops when a page repeats the previous page's links (Tistory serves the
    last page again for out-of-range page numbers) or MAX_LIST_PAGES is hit.
    """
    per_page, prev_set = [], None
    page = 0
    while page < config.MAX_LIST_PAGES:
        page += 1
        sep = "&" if "?" in category_url else "?"
        url = f"{category_url}{sep}{config.PAGE_PARAM}={page}"
        links = extract_post_links(fetcher.get(url))
        cur_set = set(links)
        if not links or (prev_set is not None and cur_set == prev_set):
            page -= 1
            break
        log(f"  page {page}: {len(links)} post-shaped links")
        per_page.append(links)
        prev_set = cur_set
    posts, chrome = split_chrome_links(per_page)
    return {"posts": posts, "chrome": chrome, "pages": page}
