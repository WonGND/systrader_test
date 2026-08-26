# -*- coding: utf-8 -*-
"""Post page parsing using the selectors measured by the probe.

If a measured selector stops matching (skin change), the parser raises
ParseError rather than falling back to guesses — the failure is recorded and
reported, per the no-fabrication constraint.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

from . import config


class ParseError(RuntimeError):
    pass


def post_id_from_url(url: str) -> str:
    """Stable filesystem-safe id from the URL path."""
    path = urlparse(url).path
    if re.fullmatch(r"/\d+", path):
        return f"n{path[1:]}"
    slug = unquote(path[len("/entry/"):]) if path.startswith("/entry/") else unquote(path.strip("/"))
    slug = re.sub(r"[^\w\-가-힣]", "-", slug)[:120].strip("-")
    return slug or hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _select_first(soup, selectors):
    for sel in selectors:
        found = soup.select(sel)
        if found:
            return found[0], sel
    return None, None


def parse_post(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    el, sel = _select_first(soup, config.TITLE_SELECTORS)
    if el is None or not (el.get("content") or "").strip():
        raise ParseError(f"title selector matched nothing: {config.TITLE_SELECTORS}")
    title = el["content"].strip()

    el, _ = _select_first(soup, config.DATE_SELECTORS)
    published_at = (el.get("content") or "").strip() if el is not None else None
    published_date = published_at[:10] if published_at else None  # ISO date part

    content_el, content_sel = _select_first(soup, config.CONTENT_SELECTORS)
    if content_el is None:
        raise ParseError(f"content selector matched nothing: {config.CONTENT_SELECTORS}")
    content_html = str(content_el)
    content_text = re.sub(r"\n{3,}", "\n\n",
                          content_el.get_text("\n", strip=True))

    images = [{"src": img.get("src") or img.get("data-src") or "",
               "alt": (img.get("alt") or "").strip()}
              for img in content_el.select("img")]

    return {
        "post_id": post_id_from_url(url),
        "url": url,
        "title": title,
        "published_at": published_at,
        "published_date": published_date,
        "content_selector_used": content_sel,
        "content_html": content_html,
        "content_text": content_text,
        "image_count": len(images),
        "images": images,
        "content_hash": hashlib.sha256(content_html.encode("utf-8")).hexdigest(),
        "text_length": len(content_text),
    }
