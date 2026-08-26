# -*- coding: utf-8 -*-
"""Derived-feature generator for M2 first-pass screening (runs locally).

Reads the local archive (data/archive/, private) and writes ONLY committable
derived metadata to data/specs/post_features.jsonl: titles, keyword-group hit
counts, parameter-pattern densities, ticker mentions, market hints. No body
text or quotes are emitted — the file is safe to commit (kickoff constraint:
the repo carries metadata and derived specs only).

Keyword hits are a screening signal ONLY. They never populate a strategy spec:
spec fields require verbatim source quotes read by a human/LLM pass (M2 step 2).

Usage (PowerShell, repo root, venv active):
  python -m src.extractor.features
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter

from src.crawler import config
from src.crawler.archiver import load_index

OUT_PATH = config.REPO_ROOT / "data" / "specs" / "post_features.jsonl"

# Screening vocabulary. Groups mirror the strategy_type enum in the spec schema.
KEYWORD_GROUPS = {
    "momentum": ["모멘텀", "듀얼모멘텀", "듀얼 모멘텀", "상대강도", "상대 강도", "절대 모멘텀"],
    "mean_reversion": ["평균회귀", "평균 회귀", "역추세", "RSI", "과매도", "과매수", "볼린저"],
    "asset_allocation": ["자산배분", "자산 배분", "포트폴리오", "리밸런싱", "60/40",
                         "영구 포트폴리오", "올웨더", "올 웨더", "정적배분", "동적배분",
                         "동적 자산", "정적 자산"],
    "trend_following": ["추세추종", "추세 추종", "이동평균", "이평선", "돌파", "신고가",
                        "채널", "터틀", "모멘텀 돌파"],
    "volatility": ["변동성", "타겟 변동성", "변동성 조절", "변동성 돌파", "켈리", "ATR"],
    "market_timing": ["마켓타이밍", "마켓 타이밍", "종가 베팅", "시가 베팅", "오버나잇",
                      "갭 상승", "갭 하락", "요일 효과", "월말", "월초"],
}

OVERSEAS_HINTS = ["미국", "S&P", "S&P500", "SP500", "나스닥", "다우", "글로벌", "선진국",
                  "신흥국", "달러", "미 국채", "미국채", "해외 ETF", "해외 주식", "월드"]
DOMESTIC_HINTS = ["코스피", "코스닥", "KOSPI", "KOSDAQ", "국내", "한국", "원화",
                  "거래소", "동시호가", "상한가", "하한가", "공매도", "증권거래세"]

# Explicit US tickers worth flagging (whitelist tickers + common leveraged ones).
TICKERS = ["SPY", "VTI", "QQQ", "EFA", "EEM", "IEF", "TLT", "SHY", "BIL", "AGG",
           "BND", "GLD", "IAU", "VNQ", "DBC", "SSO", "UPRO", "TQQQ", "SQQQ",
           "SHV", "IWM", "DIA", "VWO", "VEA", "LQD", "HYG", "TIP"]

PERF_TERMS = ["CAGR", "MDD", "샤프", "sharpe", "수익률", "승률", "최대 낙폭", "낙폭",
              "백테스트", "백테스팅"]

RE_DAYS = re.compile(r"\d+\s*일")
RE_MONTHS = re.compile(r"\d+\s*개월")
RE_PCT = re.compile(r"\d+(?:\.\d+)?\s*%")
RE_SERIES_NO = re.compile(r"\((\d+)\)")


def count_hits(text: str, terms) -> int:
    total = 0
    lower = text.lower()
    for t in terms:
        total += lower.count(t.lower())
    return total


def extract_features(rec: dict, text: str) -> dict:
    kw = {g: count_hits(text, terms) for g, terms in KEYWORD_GROUPS.items()}
    ticker_hits = {}
    for t in TICKERS:
        n = len(re.findall(rf"(?<![A-Za-z]){t}(?![A-Za-z])", text))
        if n:
            ticker_hits[t] = n
    m = RE_SERIES_NO.search(rec["title"])
    return {
        "post_id": rec["post_id"],
        "url": rec["url"],
        "title": rec["title"],
        "category_key": rec["category_key"],
        "year": (rec["published_at"] or "?")[:4],
        "published_date": (rec["published_at"] or "")[:10] or None,
        "image_count": rec["image_count"],
        "text_length": rec["text_length"],
        "kw": kw,
        "kw_total": sum(kw.values()),
        "dominant_group": max(kw, key=kw.get) if any(kw.values()) else None,
        "overseas_hits": count_hits(text, OVERSEAS_HINTS),
        "domestic_hits": count_hits(text, DOMESTIC_HINTS),
        "ticker_hits": ticker_hits,
        "param_day_mentions": len(RE_DAYS.findall(text)),
        "param_month_mentions": len(RE_MONTHS.findall(text)),
        "pct_mentions": len(RE_PCT.findall(text)),
        "perf_term_hits": count_hits(text, PERF_TERMS),
        "series_no": int(m.group(1)) if m else None,
    }


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

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows, missing = [], []
    for rec in index.values():
        txt_path = config.REPO_ROOT / rec["archived_txt"]
        if not txt_path.exists():
            missing.append(rec["url"])
            continue
        with open(txt_path, encoding="utf-8") as f:
            text = f.read()
        rows.append(extract_features(rec, text))

    rows.sort(key=lambda r: (r["category_key"], r["published_date"] or ""))
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("=" * 68)
    print(f"features written: {len(rows)} records -> {OUT_PATH.relative_to(config.REPO_ROOT)}")
    print(f"posts with missing txt files: {len(missing)}")
    for u in missing[:10]:
        print(f"  missing: {u}")
    dom = Counter(r["dominant_group"] for r in rows)
    print(f"dominant keyword group distribution: {dict(dom)}")
    ticker_posts = sum(1 for r in rows if r["ticker_hits"])
    print(f"posts mentioning explicit US tickers: {ticker_posts}")
    overseas_lean = sum(1 for r in rows if r["overseas_hits"] > r["domestic_hits"])
    print(f"posts with overseas_hits > domestic_hits: {overseas_lean}")
    print("\n다음 단계: 아래 명령으로 특징 파일을 커밋·푸시해 주세요.")
    print('  git add "data/specs/post_features.jsonl"')
    print('  git commit -m "Add derived post features for M2 screening"')
    print("  git push origin claude/systrader79-validation-pipeline-18lzzr")
    return 0


if __name__ == "__main__":
    sys.exit(main())
