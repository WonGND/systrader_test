# -*- coding: utf-8 -*-
"""Local archive writer (data/archive/ — gitignored, never committed).

Layout:
  data/archive/posts/<post_id>.html   raw page HTML (private)
  data/archive/posts/<post_id>.txt    extracted body text (private)
  data/archive/index.jsonl            one metadata record per post
  data/archive/failures.jsonl         one record per failed URL

All file I/O uses encoding="utf-8" explicitly (CLAUDE.md §9).
"""

from __future__ import annotations

import json
import time

from . import config


def _ensure_dirs() -> None:
    config.POSTS_DIR.mkdir(parents=True, exist_ok=True)


def load_index() -> dict:
    """Return {url: record} from index.jsonl (last record per URL wins)."""
    if not config.INDEX_PATH.exists():
        return {}
    records = {}
    with open(config.INDEX_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rec = json.loads(line)
                records[rec["url"]] = rec
    return records


def archive_post(parsed: dict, raw_html: str, category_key: str) -> dict:
    """Write raw HTML + text, append an index record. Returns the record."""
    _ensure_dirs()
    pid = parsed["post_id"]
    html_path = config.POSTS_DIR / f"{pid}.html"
    txt_path = config.POSTS_DIR / f"{pid}.txt"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(raw_html)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(parsed["content_text"])

    record = {
        "post_id": pid,
        "url": parsed["url"],
        "category_key": category_key,
        "spec_category": config.CATEGORIES[category_key]["spec_category"],
        "title": parsed["title"],
        "published_at": parsed["published_at"],
        "image_count": parsed["image_count"],
        "image_srcs": [i["src"] for i in parsed["images"]],
        "content_hash": parsed["content_hash"],
        "content_selector_used": parsed["content_selector_used"],
        "text_length": parsed["text_length"],
        "archived_html": str(html_path.relative_to(config.REPO_ROOT)),
        "archived_txt": str(txt_path.relative_to(config.REPO_ROOT)),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "status": "archived",
    }
    with open(config.INDEX_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def record_failure(url: str, category_key: str, reason: str) -> None:
    _ensure_dirs()
    with open(config.FAILURES_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "url": url, "category_key": category_key, "reason": reason,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }, ensure_ascii=False) + "\n")
