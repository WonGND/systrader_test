# -*- coding: utf-8 -*-
"""Offline unit tests for crawler parsers. No network access."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.crawler import config, list_parser, post_parser  # noqa: E402

BASE = config.BASE_URL


def _listing_page(unique_posts, chrome_posts):
    unique = "".join(f'<a href="{u}">post</a>' for u in unique_posts)
    chrome = "".join(f'<a href="{u}">widget</a>' for u in chrome_posts)
    return f"<html><body><div id='list'>{unique}</div><aside>{chrome}</aside></body></html>"


CHROME = [f"{BASE}/entry/%EC%9C%84%EC%A0%AF-{i}" for i in range(3)] + [f"{BASE}/999{i}" for i in range(2)]


def test_extract_post_links_shapes_and_dedup():
    html = _listing_page([f"{BASE}/entry/%EA%B8%80-1", f"{BASE}/1234",
                          f"{BASE}/entry/%EA%B8%80-1",          # duplicate
                          "https://other.example/entry/x",      # foreign host
                          f"{BASE}/category/whatever"],         # not a post
                         [])
    links = list_parser.extract_post_links(html)
    assert links == [f"{BASE}/entry/%EA%B8%80-1", f"{BASE}/1234"]


def test_chrome_filter_across_pages():
    pages = []
    for p in range(4):
        uniques = [f"{BASE}/entry/%ED%8E%98%EC%9D%B4%EC%A7%80{p}-%EA%B8%80{i}" for i in range(5)]
        pages.append(list_parser.extract_post_links(_listing_page(uniques, CHROME)))
    posts, chrome = list_parser.split_chrome_links(pages)
    assert len(posts) == 20, posts          # 4 pages x 5 unique posts
    assert set(chrome) == set(CHROME)
    # document order of first appearance is preserved
    assert posts[0].endswith("0-%EA%B8%800") and posts[5].endswith("1-%EA%B8%800")


def test_chrome_filter_single_page_keeps_everything():
    page = list_parser.extract_post_links(
        _listing_page([f"{BASE}/entry/only-%EA%B8%80"], CHROME))
    posts, chrome = list_parser.split_chrome_links([page])
    assert len(posts) == 6 and chrome == []


POST_HTML = """
<html><head>
<meta property="og:title" content="듀얼 모멘텀 전략의 이해"/>
<meta property="article:published_time" content="2016-03-01T10:00:00+09:00"/>
</head><body>
<div class="entry-content">728x90 반응형
  <div class="tt_article_useless_p_margin contents_style">
    <p>12개월 모멘텀 기준으로 상위 자산을 매수한다.</p>
    <p>매월 말 리밸런싱한다.</p>
    <img src="chart1.png" alt="백테스트 결과"/><img src="chart2.png"/>
  </div>
</div>
<aside><img src="ad.png"/><span class="date">2016. 3. 1.</span></aside>
</body></html>
"""


def test_parse_post_uses_measured_selectors():
    p = post_parser.parse_post(POST_HTML, f"{BASE}/entry/%EB%93%80%EC%96%BC-%EB%AA%A8%EB%A9%98%ED%85%80")
    assert p["title"] == "듀얼 모멘텀 전략의 이해"
    assert p["published_at"] == "2016-03-01T10:00:00+09:00"
    assert p["published_date"] == "2016-03-01"
    assert p["content_selector_used"] == ".tt_article_useless_p_margin"
    assert "12개월 모멘텀" in p["content_text"] and "728x90" not in p["content_text"]
    assert p["image_count"] == 2                       # aside ad image excluded
    assert p["images"][0] == {"src": "chart1.png", "alt": "백테스트 결과"}
    assert p["post_id"] == "듀얼-모멘텀"
    assert len(p["content_hash"]) == 64


def test_parse_post_raises_without_measured_selectors():
    import pytest
    with pytest.raises(post_parser.ParseError):
        post_parser.parse_post("<html><body><p>no known structure</p></body></html>",
                               f"{BASE}/entry/x")


def test_post_id_from_numeric_url():
    assert post_parser.post_id_from_url(f"{BASE}/1234") == "n1234"
