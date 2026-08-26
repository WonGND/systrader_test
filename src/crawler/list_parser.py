# -*- coding: utf-8 -*-
"""Category listing collection.

Measured problem: a listing page shows ~28 posts but ~55 post-shaped links,
because sidebar widgets (recent/popular posts) repeat on every page. Links that
appear on many pages are widget chrome; genuine list entries appear on exactly
one listing page.

Measured refinement (validation run 2026-08-26): a post that is BOTH a genuine
category member AND featured in a sidebar widget repeats on every page too, so
pure frequency filtering drops it (168/172 and 178/181). Fix: locate each
page's actual list container structurally — the deepest element holding most of
that page's page-unique links — and reclaim any chrome-classified link that
also appears inside that container. No skin selectors are guessed; the
container is measured per page. The final count is still validated against the
advertised count and any remaining mismatch is reported, never corrected.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from . import config


def clean_post_url(href: str, base_url: str = config.BASE_URL):
    """Normalize a candidate href to a canonical post URL, or None."""
    full = urljoin(base_url, href)
    parsed = urlparse(full)
    if parsed.netloc != urlparse(base_url).netloc:
        return None
    path = parsed.path
    if re.fullmatch(r"/\d+", path) or path.startswith("/entry/"):
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    return None


def extract_post_links(html: str, base_url: str = config.BASE_URL) -> list:
    """Return post-shaped links (path /entry/* or /N) in document order."""
    soup = BeautifulSoup(html, "html.parser")
    links, seen = [], set()
    for a in soup.select("a[href]"):
        clean = clean_post_url(a["href"], base_url)
        if clean is None or clean in seen:
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


def _find_list_container(soup, entry_urls: set, base_url: str):
    """Deepest element containing >=80% of this page's entry links (min 3).

    Measured per page from the entry links themselves — no skin assumptions.
    Returns None when the page has too few entry links to give a signal.
    """
    page_entry_anchors = []
    for a in soup.select("a[href]"):
        clean = clean_post_url(a["href"], base_url)
        if clean is not None and clean in entry_urls:
            page_entry_anchors.append(a)
    if len(page_entry_anchors) < 3:
        return None
    counts: dict = {}
    for a in page_entry_anchors:
        for anc in a.parents:
            if anc.name in ("html", "[document]"):
                continue
            el, c = counts.get(id(anc), (anc, 0))
            counts[id(anc)] = (el, c + 1)
    need = max(3, int(len(page_entry_anchors) * 0.8))
    candidates = [el for el, c in counts.values() if c >= need and el.name != "body"]
    if not candidates:
        return None
    return max(candidates, key=lambda el: len(list(el.parents)))


def reclaim_widget_members(page_htmls: list, entries: list, chrome: list,
                           base_url: str = config.BASE_URL) -> tuple:
    """Reclaim chrome links that also appear inside a page's real list container.

    Returns (entries_including_reclaimed, remaining_chrome, reclaimed).
    """
    if not chrome:
        return list(entries), list(chrome), []
    entry_set, chrome_set = set(entries), set(chrome)
    reclaimed: dict = {}
    for page_idx, html in enumerate(page_htmls):
        soup = BeautifulSoup(html, "html.parser")
        container = _find_list_container(soup, entry_set, base_url)
        if container is None:
            continue
        for a in container.select("a[href]"):
            clean = clean_post_url(a["href"], base_url)
            if clean is not None and clean in chrome_set:
                reclaimed.setdefault(clean, page_idx)
    reclaimed_urls = sorted(reclaimed, key=lambda u: reclaimed[u])
    remaining = [u for u in chrome if u not in reclaimed]
    return list(entries) + reclaimed_urls, remaining, reclaimed_urls


def collect_category(fetcher, category_url: str, log=print) -> dict:
    """Walk ?page=1..N; return posts with widget-featured members reclaimed.

    Stops when a page repeats the previous page's links (Tistory serves the
    last page again for out-of-range page numbers) or MAX_LIST_PAGES is hit.
    """
    page_htmls, per_page, prev_set = [], [], None
    page = 0
    while page < config.MAX_LIST_PAGES:
        page += 1
        sep = "&" if "?" in category_url else "?"
        url = f"{category_url}{sep}{config.PAGE_PARAM}={page}"
        html = fetcher.get(url)
        links = extract_post_links(html)
        cur_set = set(links)
        if not links or (prev_set is not None and cur_set == prev_set):
            page -= 1
            break
        log(f"  page {page}: {len(links)} post-shaped links")
        page_htmls.append(html)
        per_page.append(links)
        prev_set = cur_set
    entries, chrome = split_chrome_links(per_page)
    posts, remaining_chrome, reclaimed = reclaim_widget_members(page_htmls, entries, chrome)
    return {"posts": posts, "chrome": remaining_chrome, "reclaimed": reclaimed,
            "pages": page}
