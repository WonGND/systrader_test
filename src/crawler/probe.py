# -*- coding: utf-8 -*-
"""Read-only structure probe for the target Tistory blog (STEP 3 / pre-M1).

This script performs the six survey items required before building the crawler:
  1. robots.txt contents and whether crawling is allowed  (checked FIRST)
  2. pagination scheme and parameters
  3. post URL pattern
  4. body DOM structure (title / content / date selector candidates)
  5. programmatic detectability of embedded images
  6. actual post counts vs the expected ~172 / ~181

Strictly read-only: nothing is archived, no post bodies are saved.
It prints a structural report (metadata only: URLs, titles, counts, selectors).

Hard limits:
  - At most ~10 HTTP requests total.
  - >= 2 seconds delay between requests (never lowered below 2).
  - Every URL is checked against robots.txt before fetching.
  - If robots.txt disallows the paths we need, the probe STOPS and reports.

Usage (PowerShell):
  python "src\\crawler\\probe.py" --out "reports\\probe_output.txt"
  python "src\\crawler\\probe.py" --selftest   # offline parser check, no network
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

DEFAULT_BASE_URL = "https://stock79.tistory.com"
USER_AGENT = "systrader79-research-probe/0.1 (personal research; read-only survey)"
MIN_DELAY_SECONDS = 2.0
MAX_REQUESTS = 10

# Candidate selectors seen across common Tistory skins. The probe only REPORTS
# which ones match; the real crawler will use the measured winners, never guesses.
TITLE_CANDIDATES = [
    "meta[property='og:title']",
    ".hgroup h1", "h1.title", ".tit_post", ".entry-title", "h2.tit_blogview",
    "h3.tit_view", ".article_header h1", ".titleWrap h3", ".post-header h1",
]
CONTENT_CANDIDATES = [
    ".tt_article_useless_p_margin", ".contents_style", ".entry-content",
    ".article_view", "#article", ".area_view", "#content .article", ".post-content",
]
DATE_CANDIDATES = [
    "meta[property='article:published_time']",
    ".article_info .date", "span.date", ".date", ".post-header .date",
    ".hgroup .date", ".txt_info", "time",
]


@dataclass
class ProbeState:
    request_count: int = 0
    last_request_at: float = 0.0
    lines: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def emit(self, text: str = "") -> None:
        self.lines.append(text)
        print(text)


def polite_get(state: ProbeState, session, url: str, delay: float):
    """Rate-limited GET. Returns response or None. Never retries a 4xx."""
    if state.request_count >= MAX_REQUESTS:
        state.emit(f"[SKIP] request budget ({MAX_REQUESTS}) exhausted: {url}")
        return None
    wait = max(0.0, delay - (time.time() - state.last_request_at))
    if wait > 0:
        time.sleep(wait)
    state.last_request_at = time.time()
    state.request_count += 1
    try:
        resp = session.get(url, timeout=30)
    except Exception as exc:  # network-level failure: report, do not retry here
        state.emit(f"[ERROR] GET {url} -> {type(exc).__name__}: {exc}")
        return None
    state.emit(f"[HTTP {resp.status_code}] GET {url}")
    if resp.encoding is None or resp.encoding.lower() in ("iso-8859-1",):
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp


def load_robots(state: ProbeState, session, base_url: str, delay: float):
    """Fetch robots.txt FIRST. Returns (robotparser|None, raw_text|None, fetched_ok)."""
    url = urljoin(base_url, "/robots.txt")
    resp = polite_get(state, session, url, delay)
    if resp is None:
        return None, None, False
    if resp.status_code != 200:
        # Missing robots.txt (404) conventionally means "no restrictions",
        # but we report the raw fact and let the human decide.
        return None, None, True
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(resp.text.splitlines())
    return rp, resp.text, True


def robots_allows(rp, url: str) -> bool:
    if rp is None:
        return True  # no robots.txt retrieved; caller already reported that fact
    return rp.can_fetch(USER_AGENT, url) and rp.can_fetch("*", url)


def find_category_links(soup, base_url: str) -> list:
    """Enumerate category links (name, url, advertised_count) from any page."""
    results, seen = [], set()
    for a in soup.select("a[href*='/category/']"):
        href = urljoin(base_url, a.get("href", ""))
        parsed = urlparse(href)
        if parsed.netloc != urlparse(base_url).netloc:
            continue
        if "page=" in (parsed.query or ""):
            continue  # pagination link inside a category, not a category itself
        name = " ".join(a.get_text(" ", strip=True).split())
        if not name or href in seen:
            continue
        seen.add(href)
        m = re.search(r"\((\d+)\)\s*$", name)
        results.append({
            "name": re.sub(r"\s*\(\d+\)\s*$", "", name),
            "url": href,
            "advertised_count": int(m.group(1)) if m else None,
        })
    return results


def find_post_links(soup, base_url: str) -> list:
    """Collect same-host links that look like individual posts."""
    posts, seen = [], set()
    for a in soup.select("a[href]"):
        href = urljoin(base_url, a["href"])
        parsed = urlparse(href)
        if parsed.netloc != urlparse(base_url).netloc:
            continue
        path = parsed.path
        if re.fullmatch(r"/\d+", path) or path.startswith("/entry/"):
            if href in seen:
                continue
            seen.add(href)
            title = " ".join(a.get_text(" ", strip=True).split())
            posts.append({"url": href, "anchor_text": title[:80]})
    return posts


def classify_url_pattern(post_urls: list) -> str:
    numeric = sum(1 for p in post_urls if re.fullmatch(r"/\d+", urlparse(p["url"]).path))
    entry = sum(1 for p in post_urls if urlparse(p["url"]).path.startswith("/entry/"))
    return f"numeric(/N): {numeric}, slug(/entry/...): {entry}"


def probe_selectors(soup, candidates: list) -> list:
    """Report which candidate selectors match, with match count and evidence size."""
    hits = []
    for sel in candidates:
        try:
            found = soup.select(sel)
        except Exception:
            continue
        if not found:
            continue
        el = found[0]
        if el.name == "meta":
            evidence = (el.get("content") or "")[:80]
        else:
            evidence = " ".join(el.get_text(" ", strip=True).split())[:80]
        hits.append({"selector": sel, "matches": len(found), "first_match_excerpt": evidence})
    return hits


def count_images(soup, content_hits: list) -> dict:
    """Count <img> globally and inside the best-matching content container."""
    total = len(soup.select("img"))
    in_content = None
    if content_hits:
        el = soup.select(content_hits[0]["selector"])
        if el:
            in_content = len(el[0].select("img"))
    return {"img_total_on_page": total, "img_in_first_content_match": in_content}


def detect_pagination(soup, category_url: str, base_url: str) -> dict:
    """Look for ?page=N style links and numbered pagination widgets."""
    page_params, widgets = set(), []
    for a in soup.select("a[href]"):
        href = urljoin(base_url, a["href"])
        m = re.search(r"[?&]page=(\d+)", href)
        if m and href.startswith(category_url.split("?")[0]):
            page_params.add(int(m.group(1)))
    for sel in [".pagination", "#paging", ".paging", ".blog-pagination", "#pagination"]:
        if soup.select(sel):
            widgets.append(sel)
    return {
        "page_param_values_seen": sorted(page_params)[:10],
        "pagination_widget_selectors": widgets,
        "scheme_guess": "?page=N" if page_params else "not detected on this page",
    }


def run_probe(base_url: str, delay: float, out_path: str | None) -> int:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:
        print(f"[FATAL] missing dependency: {exc}. Run: pip install -r requirements.txt")
        return 2

    delay = max(delay, MIN_DELAY_SECONDS)
    state = ProbeState()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ko,en;q=0.8"})

    state.emit("=" * 72)
    state.emit("systrader79 blog structure probe (read-only)  v0.1")
    state.emit(f"base_url={base_url}  delay={delay}s  max_requests={MAX_REQUESTS}")
    state.emit("=" * 72)

    # --- [1/6] robots.txt (FIRST) -------------------------------------------
    state.emit("\n### [1/6] robots.txt")
    rp, robots_text, fetched = load_robots(state, session, base_url, delay)
    if not fetched:
        state.emit("[STOP] robots.txt could not be fetched (network failure). Aborting probe.")
        return finalize(state, out_path, aborted=True)
    if robots_text is not None:
        state.emit("--- robots.txt (verbatim) ---")
        for line in robots_text.splitlines():
            state.emit(f"    {line}")
        state.emit("--- end robots.txt ---")
    else:
        state.emit("robots.txt not present (non-200). Reporting fact; proceeding cautiously.")
    root_ok = robots_allows(rp, urljoin(base_url, "/"))
    cat_ok = robots_allows(rp, urljoin(base_url, "/category/anything"))
    state.emit(f"allow('/') = {root_ok} | allow('/category/*') = {cat_ok}  (UA='{USER_AGENT}' and '*')")
    state.summary["robots"] = {"present": robots_text is not None,
                               "allows_root": root_ok, "allows_category": cat_ok}
    if not (root_ok and cat_ok):
        state.emit("[STOP] robots.txt disallows required paths. NOT crawling. Report this to the user.")
        return finalize(state, out_path, aborted=True)

    # --- main page: enumerate categories ------------------------------------
    state.emit("\n### category enumeration (main page)")
    resp = polite_get(state, session, base_url, delay)
    if resp is None or resp.status_code != 200:
        state.emit("[STOP] main page unreachable. Aborting probe.")
        return finalize(state, out_path, aborted=True)
    soup = BeautifulSoup(resp.text, "html.parser")
    categories = find_category_links(soup, base_url)
    if categories:
        for c in categories:
            cnt = f" (count shown: {c['advertised_count']})" if c["advertised_count"] is not None else ""
            state.emit(f"  - {c['name']}{cnt}\n      {c['url']}")
    else:
        state.emit("  (no /category/ links found on main page — skin may hide them; report as-is)")
    state.summary["categories"] = categories

    # Pick target categories by name; fall back to the first one found.
    targets = [c for c in categories
               if ("칼럼" in c["name"] or "실전" in c["name"] or "기초" in c["name"])]
    if not targets:
        targets = categories[:1]
    targets = targets[:2]
    state.emit(f"\nselected target categories for sampling: {[t['name'] for t in targets] or 'NONE'}")

    # --- [2/6][3/6][6/6] category pages: pagination, URL pattern, counts ----
    state.summary["category_samples"] = []
    post_url_for_dom = None
    for tgt in targets:
        state.emit(f"\n### [2/6][3/6][6/6] category sample: {tgt['name']}")
        if not robots_allows(rp, tgt["url"]):
            state.emit(f"[SKIP] robots.txt disallows {tgt['url']}")
            continue
        resp = polite_get(state, session, tgt["url"], delay)
        if resp is None or resp.status_code != 200:
            continue
        csoup = BeautifulSoup(resp.text, "html.parser")
        posts = find_post_links(csoup, base_url)
        pagination = detect_pagination(csoup, tgt["url"], base_url)
        state.emit(f"  posts found on page 1: {len(posts)}")
        for p in posts[:5]:
            state.emit(f"    - {p['url']}  | {p['anchor_text']}")
        state.emit(f"  URL pattern breakdown: {classify_url_pattern(posts)}")
        state.emit(f"  pagination: {pagination}")
        state.summary["category_samples"].append({
            "category": tgt["name"], "url": tgt["url"],
            "advertised_count": tgt["advertised_count"],
            "posts_on_page1": len(posts), "pagination": pagination,
            "sample_post_urls": [p["url"] for p in posts[:5]],
        })
        if posts and post_url_for_dom is None:
            post_url_for_dom = posts[0]["url"]

    # --- [4/6][5/6] one post page: DOM selectors + image detectability ------
    state.emit("\n### [4/6][5/6] post page DOM structure")
    if post_url_for_dom and robots_allows(rp, post_url_for_dom):
        resp = polite_get(state, session, post_url_for_dom, delay)
        if resp is not None and resp.status_code == 200:
            psoup = BeautifulSoup(resp.text, "html.parser")
            title_hits = probe_selectors(psoup, TITLE_CANDIDATES)
            content_hits = probe_selectors(psoup, CONTENT_CANDIDATES)
            date_hits = probe_selectors(psoup, DATE_CANDIDATES)
            images = count_images(psoup, content_hits)
            for label, hits in [("title", title_hits), ("content", content_hits), ("date", date_hits)]:
                state.emit(f"  {label} selector candidates that matched:")
                if hits:
                    for h in hits:
                        state.emit(f"    - {h['selector']}  (x{h['matches']})  '{h['first_match_excerpt']}'")
                else:
                    state.emit("    - NONE matched (custom skin — report raw HTML sample needed)")
            state.emit(f"  image detectability: {images}")
            state.summary["dom"] = {"probed_url": post_url_for_dom,
                                    "title": title_hits, "content": content_hits,
                                    "date": date_hits, "images": images}
    else:
        state.emit("  (no post URL available from category sampling — cannot probe DOM)")

    return finalize(state, out_path, aborted=False)


def finalize(state: ProbeState, out_path: str | None, aborted: bool) -> int:
    state.summary["aborted"] = aborted
    state.summary["requests_made"] = state.request_count
    state.emit("\n### machine-readable summary (JSON)")
    state.emit(json.dumps(state.summary, ensure_ascii=False, indent=2))
    state.emit("\n" + "=" * 72)
    state.emit(">>> 위 출력 전체를 복사해서 Claude에게 붙여넣어 주세요. <<<")
    state.emit("=" * 72)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(state.lines) + "\n")
        print(f"\n[saved] {out_path} (encoding=utf-8)")
    return 1 if aborted else 0


# ---------------------------------------------------------------------------
# Offline self-test: verifies parser functions on embedded sample HTML.
# No network access. Safe to run anywhere.
# ---------------------------------------------------------------------------
SELFTEST_LIST_HTML = """
<html><body>
<ul><li><a href="/category/systrader79 칼럼">systrader79 칼럼/실전 투자 전략 (172)</a></li>
<li><a href="/category/투자의 기초">투자의 기초 (181)</a></li></ul>
<div class="pagination"><a href="/category/x?page=2">2</a><a href="/category/x?page=3">3</a></div>
<a href="/1234">듀얼 모멘텀 전략의 이해</a>
<a href="/entry/some-post-slug">변동성 조절 전략</a>
<a href="https://other-site.example/999">external</a>
</body></html>
"""

SELFTEST_POST_HTML = """
<html><head><meta property="og:title" content="듀얼 모멘텀 전략의 이해"/>
<meta property="article:published_time" content="2016-03-01T10:00:00+09:00"/></head>
<body><div class="hgroup"><h1>듀얼 모멘텀 전략의 이해</h1><span class="date">2016. 3. 1.</span></div>
<div class="tt_article_useless_p_margin"><p>12개월 모멘텀 기준으로…</p>
<img src="a.png"/><img src="b.png"/></div></body></html>
"""


def run_selftest() -> int:
    from bs4 import BeautifulSoup
    base = "https://stock79.tistory.com"
    lsoup = BeautifulSoup(SELFTEST_LIST_HTML, "html.parser")
    psoup = BeautifulSoup(SELFTEST_POST_HTML, "html.parser")

    cats = find_category_links(lsoup, base)
    assert len(cats) == 2, cats
    assert cats[0]["advertised_count"] == 172 and cats[1]["advertised_count"] == 181, cats
    assert cats[0]["name"].endswith("실전 투자 전략"), cats

    posts = find_post_links(lsoup, base)
    assert len(posts) == 2, posts  # external link excluded
    assert classify_url_pattern(posts) == "numeric(/N): 1, slug(/entry/...): 1"

    pg = detect_pagination(lsoup, f"{base}/category/x", base)
    assert pg["page_param_values_seen"] == [2, 3], pg
    assert ".pagination" in pg["pagination_widget_selectors"], pg

    th = probe_selectors(psoup, TITLE_CANDIDATES)
    ch = probe_selectors(psoup, CONTENT_CANDIDATES)
    dh = probe_selectors(psoup, DATE_CANDIDATES)
    assert th and th[0]["selector"] == "meta[property='og:title']", th
    assert th[0]["first_match_excerpt"] == "듀얼 모멘텀 전략의 이해", th
    assert ch and ch[0]["selector"] == ".tt_article_useless_p_margin", ch
    assert any(h["selector"] == "meta[property='article:published_time']" for h in dh), dh

    img = count_images(psoup, ch)
    assert img == {"img_total_on_page": 2, "img_in_first_content_match": 2}, img

    print("SELFTEST OK — all parser functions behave as expected (offline).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only Tistory structure probe (pre-M1).")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--delay", type=float, default=MIN_DELAY_SECONDS,
                    help="seconds between requests (floor: 2.0, cannot be lowered)")
    ap.add_argument("--out", default=None, help="also write the report to this file (utf-8)")
    ap.add_argument("--selftest", action="store_true", help="run offline parser self-test only")
    args = ap.parse_args()
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if args.selftest:
        return run_selftest()
    return run_probe(args.base_url, args.delay, args.out)


if __name__ == "__main__":
    sys.exit(main())
