# -*- coding: utf-8 -*-
"""M1 crawler entry point (run locally; the remote session cannot reach the blog).

Usage (PowerShell, venv active, from the repo root):
  python -m src.crawler.run --category all --limit 5     # validation run
  python -m src.crawler.run --category all               # full run (M1, after approval)
  python -m src.crawler.run --category strategy --dry-run

Behaviour:
  - Listing collection filters sidebar chrome and compares the final post count
    against the advertised counts (172/181); mismatches are REPORTED, not fixed.
  - Resumable: already-archived URLs (checkpoint) are skipped on re-run.
  - Individual post failures never abort the batch; they go to failures.jsonl.
  - A block signal (robots / 403 / 429) aborts immediately with a report.
"""

from __future__ import annotations

import argparse
import sys
import time

from . import archiver, checkpoint, config, list_parser, post_parser
from .fetcher import BlockedError, FetchError, Fetcher


def crawl_category(fetcher, key: str, limit, dry_run: bool, state: dict) -> dict:
    cat = config.CATEGORIES[key]
    print(f"\n### category '{key}' — {cat['name']} (expected {cat['expected_count']})")

    listing = list_parser.collect_category(fetcher, cat["url"])
    posts, chrome, pages = listing["posts"], listing["chrome"], listing["pages"]
    print(f"  listing pages walked: {pages}")
    print(f"  chrome links filtered (sidebar widgets): {len(chrome)}")
    print(f"  candidate posts: {len(posts)} vs advertised {cat['expected_count']}"
          f"  -> {'MATCH' if len(posts) == cat['expected_count'] else 'MISMATCH — report, do not correct'}")

    state.setdefault("listings", {})[key] = {
        "collected": len(posts), "advertised": cat["expected_count"],
        "pages": pages, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    checkpoint.save(state)

    todo = posts[:limit] if limit else posts
    stats = {"archived": 0, "skipped": 0, "failed": 0,
             "collected": len(posts), "advertised": cat["expected_count"]}

    for i, url in enumerate(todo, 1):
        if url in state["done"]:
            stats["skipped"] += 1
            continue
        try:
            raw = fetcher.get(url)
            parsed = post_parser.parse_post(raw, url)
            if dry_run:
                print(f"  [dry-run {i}/{len(todo)}] {parsed['title'][:60]}"
                      f" | date={parsed['published_date']} | imgs={parsed['image_count']}"
                      f" | text={parsed['text_length']}ch")
                continue
            archiver.archive_post(parsed, raw, key)
            checkpoint.mark_done(state, url, parsed["content_hash"])
            stats["archived"] += 1
            if i % 10 == 0 or i == len(todo):
                print(f"  progress: {i}/{len(todo)} (archived {stats['archived']},"
                      f" skipped {stats['skipped']}, failed {stats['failed']})")
        except BlockedError:
            raise  # abort the whole run: block signals are never retried around
        except (FetchError, post_parser.ParseError) as exc:
            stats["failed"] += 1
            print(f"  [FAIL] {url} -> {exc}")
            if not dry_run:
                archiver.record_failure(url, key, str(exc))
                checkpoint.mark_failed(state, url, str(exc))
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="systrader79 blog crawler (M1)")
    ap.add_argument("--category", choices=[*config.CATEGORIES, "all"], default="all")
    ap.add_argument("--limit", type=int, default=None,
                    help="max posts per category (validation runs)")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse only; write nothing")
    ap.add_argument("--delay", type=float, default=config.MIN_DELAY_SECONDS,
                    help="seconds between requests (floor 2.0, cannot be lowered)")
    args = ap.parse_args()

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    keys = list(config.CATEGORIES) if args.category == "all" else [args.category]
    fetcher = Fetcher(delay=args.delay)
    state = checkpoint.load()
    started = time.time()
    summary = {}
    try:
        for key in keys:
            summary[key] = crawl_category(fetcher, key, args.limit, args.dry_run, state)
    except BlockedError as exc:
        print(f"\n[ABORT] block signal — stopping immediately, no circumvention: {exc}")
        print("이 출력을 그대로 Claude에게 전달해 주세요.")
        return 2

    print("\n=== SUMMARY ===")
    for key, s in summary.items():
        print(f"  {key}: collected {s['collected']} (advertised {s['advertised']}),"
              f" archived {s['archived']}, skipped {s['skipped']}, failed {s['failed']}")
    print(f"  requests: {fetcher.request_count}, elapsed: {time.time()-started:.0f}s")
    print(f"  archive dir: {config.ARCHIVE_DIR} (gitignored — 커밋되지 않음)")
    print(">>> 위 출력 전체를 Claude에게 전달해 주세요. <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())
