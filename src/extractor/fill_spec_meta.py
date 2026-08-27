# -*- coding: utf-8 -*-
"""Fill spec source.content_hash from the local archive index (runs locally).

The remote session cannot read data/archive/, so generated specs carry
content_hash = "PENDING_LOCAL_INDEX". This script replaces it with the real
sha256 recorded in index.jsonl, matching each spec by post_url.

Usage (PowerShell, repo root, venv active):
  python -m src.extractor.fill_spec_meta
Then commit the updated data/specs/*.json.
"""

from __future__ import annotations

import glob
import json
import sys

from src.crawler import config
from src.crawler.archiver import load_index


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
    updated, missing = 0, []
    for path in sorted(glob.glob(str(config.REPO_ROOT / "data" / "specs" / "c*.json"))):
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
        url = spec["source"]["post_url"]
        rec = index.get(url)
        if rec is None:
            missing.append(url)
            continue
        if spec["source"]["content_hash"] != rec["content_hash"]:
            spec["source"]["content_hash"] = rec["content_hash"]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(spec, f, ensure_ascii=False, indent=1)
            updated += 1
            print(f"filled: {path.split('/')[-1].split(chr(92))[-1]}")
    print(f"\nupdated: {updated}, not found in index: {len(missing)}")
    for u in missing:
        print(f"  missing: {u}")
    if updated:
        print('\n다음: git add "data/specs" ; git commit -m "Fill spec content hashes from local index" ; git push origin claude/systrader79-validation-pipeline-18lzzr')
    return 0


if __name__ == "__main__":
    sys.exit(main())
