# -*- coding: utf-8 -*-
"""Bundle shortlisted post texts into one local file for session hand-off (M2).

Reads data/specs/m2_shortlist.json (committed) and the local archive, writes
data/archive/m2_bundle.txt (PRIVATE — inside the gitignored archive dir, never
committed). The user passes the bundle content to the Claude session directly
(file attachment or paste); it must NOT be committed to the repository.

Usage (PowerShell, repo root, venv active):
  python -m src.extractor.make_bundle            # whole shortlist, one file
  python -m src.extractor.make_bundle --parts 4  # split into N chunk files
"""

from __future__ import annotations

import argparse
import json
import sys

from src.crawler import config
from src.crawler.archiver import load_index

SHORTLIST_PATH = config.REPO_ROOT / "data" / "specs" / "m2_shortlist.json"
BUNDLE_PATH = config.ARCHIVE_DIR / "m2_bundle.txt"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", type=int, default=1,
                    help="split output into N files (m2_bundle_partK.txt)")
    ap.add_argument("--match", nargs="*", default=None,
                    help="only bundle posts whose title contains one of these "
                         "substrings (M6: pull just the posts still needed)")
    ap.add_argument("--out", default=None,
                    help="output filename inside data/archive/ (default m2_bundle.txt)")
    args = ap.parse_args()
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    with open(SHORTLIST_PATH, encoding="utf-8") as f:
        shortlist = json.load(f)["posts"]
    if args.match:
        shortlist = [p for p in shortlist
                     if any(m in p["title"] for m in args.match)]
        if not shortlist:
            print(f"[!] --match {args.match} 에 해당하는 글이 shortlist에 없습니다.")
            return 1
    index = load_index()
    by_url = {r["url"]: r for r in index.values()}

    sections, missing = [], []
    for i, p in enumerate(shortlist, 1):
        rec = by_url.get(p["url"])
        txt_path = config.REPO_ROOT / rec["archived_txt"] if rec else None
        if rec is None or not txt_path.exists():
            missing.append(p["url"])
            continue
        with open(txt_path, encoding="utf-8") as f:
            body = f.read()
        header = (f"{'='*70}\n### POST {i}/{len(shortlist)}\n"
                  f"post_id: {p['post_id']}\ntitle: {p['title']}\nurl: {p['url']}\n"
                  f"published: {rec['published_at']}\ncategory: {p['category_key']}\n"
                  f"image_count: {rec['image_count']}\n"
                  f"image_srcs_count: {len(rec.get('image_srcs', []))}\n{'='*70}\n")
        sections.append(header + body + "\n")

    n = max(1, args.parts)
    per = (len(sections) + n - 1) // n
    paths = []
    for k in range(n):
        chunk = sections[k * per:(k + 1) * per]
        if not chunk:
            break
        base = config.ARCHIVE_DIR / args.out if args.out else BUNDLE_PATH
        path = base if n == 1 else base.with_name(f"{base.stem}_part{k+1}{base.suffix}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(chunk))
        paths.append(path)

    print(f"bundled posts: {len(sections)}/{len(shortlist)} (missing: {len(missing)})")
    for u in missing:
        print(f"  missing: {u}")
    for path in paths:
        size = path.stat().st_size
        print(f"  wrote {path} ({size/1024:.0f} KB)")
    print("\n주의: 이 파일은 data/archive/ 안에 있어 커밋되지 않습니다.")
    print("Claude 세션에 파일 첨부 또는 내용 붙여넣기로만 전달하세요 (저장소 커밋 금지).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
