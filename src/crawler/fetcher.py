# -*- coding: utf-8 -*-
"""Rate-limited, robots-aware HTTP fetcher.

Policy (kickoff spec / CLAUDE.md §11):
  - >= 2s between any two requests, exponential backoff on transient failures.
  - Every URL is checked against robots.txt before fetching.
  - A 403 or 429 is treated as a block signal: raise BlockedError so the run
    stops and reports. No circumvention (no UA rotation, no proxies).
"""

from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urljoin

import requests

from . import config


class BlockedError(RuntimeError):
    """Server signalled blocking (403/429) or robots.txt disallows the URL."""


class FetchError(RuntimeError):
    """Non-block failure that persisted through all retries."""


class Fetcher:
    def __init__(self, delay: float = config.MIN_DELAY_SECONDS):
        self.delay = max(delay, config.MIN_DELAY_SECONDS)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept-Language": "ko,en;q=0.8",
        })
        self._last_request_at = 0.0
        self.request_count = 0
        self._robots = None
        self._robots_loaded = False

    # -- robots ------------------------------------------------------------
    def _load_robots(self) -> None:
        url = urljoin(config.BASE_URL, "/robots.txt")
        resp = self._raw_get(url)
        self._robots_loaded = True
        if resp is not None and resp.status_code == 200:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(resp.text.splitlines())
            self._robots = rp

    def allowed(self, url: str) -> bool:
        if not self._robots_loaded:
            self._load_robots()
        if self._robots is None:
            return True  # robots.txt absent; probe already reported this state
        return (self._robots.can_fetch(config.USER_AGENT, url)
                and self._robots.can_fetch("*", url))

    # -- fetching ----------------------------------------------------------
    def _raw_get(self, url: str):
        wait = max(0.0, self.delay - (time.time() - self._last_request_at))
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.time()
        self.request_count += 1
        try:
            resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException:
            return None
        if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding or "utf-8"
        return resp

    def get(self, url: str) -> str:
        """Fetch a page, honouring robots and retrying transient failures.

        Returns the decoded body text. Raises BlockedError / FetchError.
        """
        if not self.allowed(url):
            raise BlockedError(f"robots.txt disallows: {url}")
        last_status = None
        for attempt in range(config.MAX_RETRIES + 1):
            if attempt > 0:
                time.sleep(config.BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
            resp = self._raw_get(url)
            if resp is None:
                last_status = "network-error"
                continue
            if resp.status_code in (403, 429):
                raise BlockedError(f"HTTP {resp.status_code} (block signal): {url}")
            if resp.status_code >= 500:
                last_status = resp.status_code
                continue
            if resp.status_code != 200:
                raise FetchError(f"HTTP {resp.status_code}: {url}")
            return resp.text
        raise FetchError(f"exhausted retries (last={last_status}): {url}")
