# -*- coding: utf-8 -*-
"""Crawler configuration.

Every value here is either taken from the kickoff spec (CLAUDE.md) or measured
by the read-only probe run on 2026-08-26 (see reports/M0_survey_and_M1_plan.md
§3.3). Nothing below is guessed.
"""

from __future__ import annotations

from pathlib import Path

BASE_URL = "https://stock79.tistory.com"
USER_AGENT = "systrader79-research-crawler/0.1 (personal research; rate-limited)"

# CLAUDE.md hard constraint: >= 2s between requests. Never lowered.
MIN_DELAY_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 30
# Exponential backoff on transient failures (network error / 5xx): 2s, 4s, 8s, 16s.
MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 2.0

# Target categories — measured by probe (advertised counts matched the spec
# exactly: 172 and 181). Both are subcategories of "systrader79 칼럼" (451).
CATEGORIES = {
    "strategy": {
        "name": "실전 투자 전략",
        "url": BASE_URL + "/category/systrader79%20%EC%B9%BC%EB%9F%BC/%EC%8B%A4%EC%A0%84%20%ED%88%AC%EC%9E%90%20%EC%A0%84%EB%9E%B5",
        "expected_count": 172,
        "spec_category": "column_strategy",
    },
    "basics": {
        "name": "투자의 기초",
        "url": BASE_URL + "/category/systrader79%20%EC%B9%BC%EB%9F%BC/%ED%88%AC%EC%9E%90%EC%9D%98%20%EA%B8%B0%EC%B4%88",
        "expected_count": 181,
        "spec_category": "investing_basics",
    },
}

# Pagination — measured: ?page=N with a .pagination widget. The parent category
# (451 posts) showed 16 pages, so ~28-30 posts/page; 40 is a generous safety cap.
PAGE_PARAM = "page"
MAX_LIST_PAGES = 40

# DOM selectors — measured on a live post page. Order matters: first match wins.
# .entry-content was measured and REJECTED (ad text "728x90 반응형" pollutes it).
TITLE_SELECTORS = ["meta[property='og:title']"]
DATE_SELECTORS = ["meta[property='article:published_time']"]  # ISO 8601, unique match
CONTENT_SELECTORS = [".tt_article_useless_p_margin", ".contents_style"]

# Listing chrome filter: links that repeat across this fraction of listing pages
# are sidebar widgets (recent/popular posts), not category members. Measured
# symptom: ~55 links on a page that lists ~28 posts.
CHROME_REPEAT_FRACTION = 0.5

# Paths (repo-relative; data/archive is gitignored — never committed).
REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = REPO_ROOT / "data" / "archive"
POSTS_DIR = ARCHIVE_DIR / "posts"
INDEX_PATH = ARCHIVE_DIR / "index.jsonl"
CHECKPOINT_PATH = ARCHIVE_DIR / "checkpoint.json"
FAILURES_PATH = ARCHIVE_DIR / "failures.jsonl"
