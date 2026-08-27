# -*- coding: utf-8 -*-
"""yfinance adapter with local cache (runs on the user's machine; the remote
session's network policy blocks Yahoo endpoints).

Conventions (CLAUDE.md §4, DECISIONS 2026-08-26):
- Single source: yfinance. auto_adjust=True — adjusted OHLC approximates
  dividend-reinvested total return. Stated in every report.
- Missing data is never interpolated; gaps stay NaN and are reported.
- Responses are cached under cache/yfinance/ (gitignored) for reproducibility.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "cache" / "yfinance"
AUTO_ADJUST = True  # decision recorded in docs/DECISIONS.md and L-05


def _cache_path(ticker: str, start: str, end: str) -> Path:
    return CACHE_DIR / f"{ticker}_{start}_{end}_adj{int(AUTO_ADJUST)}.csv"


def fetch_ohlc(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Return a DataFrame with columns Open/High/Low/Close (auto-adjusted)."""
    path = _cache_path(ticker, start, end)
    if path.exists():
        df = pd.read_csv(path, index_col=0, parse_dates=True)
    else:
        import yfinance as yf
        df = yf.download(ticker, start=start, end=end, auto_adjust=AUTO_ADJUST,
                         progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close"]]
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, encoding="utf-8")
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def load_universe(tickers: list, start: str, end: str) -> tuple:
    """(open_frame, close_frame) aligned on the union of trading days.

    Days where a ticker has no listing stay NaN (no interpolation)."""
    opens, closes = {}, {}
    for t in tickers:
        df = fetch_ohlc(t, start, end)
        opens[t] = df["Open"]
        closes[t] = df["Close"]
    open_ = pd.DataFrame(opens)
    close = pd.DataFrame(closes)
    return open_.sort_index(), close.sort_index()
