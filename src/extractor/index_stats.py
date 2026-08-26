# -*- coding: utf-8 -*-
"""Offline archive index statistics (no network; reads data/archive/index.jsonl).

Prints only aggregate metadata (counts, dates, lengths) — no post content —
so the output is safe to paste back into the session and into reports.

Usage (PowerShell, repo root, venv active):
  python -m src.extractor.index_stats
"""

from __future__ import annotations

import statistics
import sys
from collections import Counter

from src.crawler import config
from src.crawler.archiver import load_index


def bucket_images(n: int) -> str:
    if n == 0:
        return "0"
    if n <= 2:
        return "1-2"
    if n <= 5:
        return "3-5"
    if n <= 10:
        return "6-10"
    return ">10"


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    index = load_index()
    if not index:
        print(f"[ERROR] index not found or empty: {config.INDEX_PATH}")
        return 1
    records = list(index.values())

    print("=" * 68)
    print("archive index statistics")
    print("=" * 68)
    print(f"total unique posts: {len(records)}")

    by_cat = Counter(r["category_key"] for r in records)
    for key, cnt in sorted(by_cat.items()):
        expected = config.CATEGORIES[key]["expected_count"]
        print(f"  {key}: {cnt} (advertised {expected})")

    dup_hashes = Counter(r["content_hash"] for r in records)
    dups = {h: c for h, c in dup_hashes.items() if c > 1}
    print(f"duplicate content hashes: {len(dups)}")
    if dups:
        for h, c in list(dups.items())[:10]:
            urls = [r["url"] for r in records if r["content_hash"] == h]
            print(f"  x{c}: {urls}")

    missing_date = [r for r in records if not r.get("published_at")]
    print(f"posts missing published_at: {len(missing_date)}")
    years = Counter((r["published_at"] or "?")[:4] for r in records)
    print("posts per year:")
    for y in sorted(years):
        print(f"  {y}: {years[y]}")

    img_buckets = Counter(bucket_images(r["image_count"]) for r in records)
    with_img = sum(1 for r in records if r["image_count"] > 0)
    print(f"posts with >=1 image: {with_img} ({with_img/len(records)*100:.1f}%)")
    print("image count buckets:")
    for b in ["0", "1-2", "3-5", "6-10", ">10"]:
        print(f"  {b}: {img_buckets.get(b, 0)}")

    lengths = [r["text_length"] for r in records]
    print("text length (chars): "
          f"min {min(lengths)}, median {int(statistics.median(lengths))}, "
          f"mean {int(statistics.mean(lengths))}, max {max(lengths)}")
    short = sum(1 for x in lengths if x < 500)
    print(f"posts with text < 500 chars: {short}")

    sel = Counter(r["content_selector_used"] for r in records)
    print(f"content selector usage: {dict(sel)}")

    numeric = sum(1 for r in records if r["post_id"].startswith("n") and r["post_id"][1:].isdigit())
    print(f"numeric-URL posts: {numeric}")
    print(">>> 위 출력 전체를 Claude에게 전달해 주세요. <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())
