# -*- coding: utf-8 -*-
"""Verify every source_quote in every spec against the archived post text.

CLAUDE.md §1-2: a value written without a real quote from the post is invalid.
This checks that mechanically instead of by eye. It runs LOCALLY because the
archive is private (data/archive/ is gitignored and never committed).

Whitespace is normalised on both sides before comparing — the archive text
wraps lines and contains NBSP, which would otherwise fail an exact match —
but nothing else is relaxed: no fuzzy matching, no substring-of-substring.

Usage (PowerShell, repo root, venv active):
  python -m src.extractor.verify_quotes
  python -m src.extractor.verify_quotes --spec c10 c12   # only these
Exit code is non-zero if any quote fails, so a bad spec cannot pass silently.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys

from src.crawler import config
from src.crawler.archiver import load_index

SPEC_DIR = config.REPO_ROOT / "data" / "specs"
_WS = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Collapse every run of whitespace (incl. NBSP) to a single space."""
    return _WS.sub(" ", text.replace(" ", " ")).strip()


def walk_quotes(node, path="") -> list:
    """[(field_path, quote)] for every evidence object carrying a quote."""
    out = []
    if isinstance(node, dict):
        q = node.get("source_quote")
        if isinstance(q, str) and q.strip():
            out.append((path, q))
        for k, v in node.items():
            if k != "source_quote":
                out += walk_quotes(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += walk_quotes(v, f"{path}[{i}]")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", nargs="*", default=None,
                    help="only specs whose filename starts with one of these")
    args = ap.parse_args()
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    index = load_index()
    if not index:
        print(f"[ERROR] 아카이브 인덱스가 비어 있습니다: {config.INDEX_PATH}")
        print("        M1 크롤링을 실행한 PC에서 돌리거나, 해당 글을 먼저 수집하세요:")
        print('        python -m src.crawler.run --category strategy --from-shortlist "<제목 일부>"')
        return 1

    paths = sorted(glob.glob(str(SPEC_DIR / "c*.json")))
    if args.spec:
        paths = [p for p in paths
                 if any(p.replace("\\", "/").split("/")[-1].startswith(s) for s in args.spec)]
    if not paths:
        print("[ERROR] 대상 스펙이 없습니다.")
        return 1

    total, failed = 0, 0
    for path in paths:
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
        name = path.replace("\\", "/").split("/")[-1]
        rec = index.get(spec["source"]["post_url"])
        if rec is None:
            print(f"\n[{name}] SKIP — 인덱스에 원문이 없습니다 (이 PC에 미수집)")
            continue
        txt_path = config.REPO_ROOT / rec["archived_txt"]
        if not txt_path.exists():
            print(f"\n[{name}] SKIP — 본문 파일 없음: {txt_path}")
            continue
        with open(txt_path, encoding="utf-8") as f:
            # the archived .txt holds the body only, but the title is part of
            # the post too (specs quote it for strategy.name)
            body = normalise(rec["title"] + "\n" + f.read())

        quotes = walk_quotes(spec.get("strategy", {}), "strategy")
        quotes += walk_quotes(spec.get("reported_performance", {}), "reported_performance")
        bad = [(p, q) for p, q in quotes if normalise(q) not in body]
        total += len(quotes)
        failed += len(bad)
        mark = "OK" if not bad else f"FAIL {len(bad)}건"
        print(f"\n[{name}] 인용 {len(quotes)}건 — {mark}")
        for p, q in bad:
            print(f"  MISMATCH {p}")
            print(f"    quote: {q[:120]}")

        hashed = spec["source"]["content_hash"]
        if hashed != rec["content_hash"]:
            print(f"  [주의] content_hash 불일치/미충전 — fill_spec_meta 실행 필요"
                  f" (spec={hashed[:16]}..., index={rec['content_hash'][:16]}...)")

    print(f"\n=== 인용 대조: 총 {total}건, 불일치 {failed}건 ===")
    if failed:
        print("불일치가 있으면 스펙 값은 무효입니다 (CLAUDE.md §1-2). 위 출력을 Claude에게 전달하세요.")
    print(">>> 위 출력 전체를 Claude에게 전달해 주세요. <<<")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
