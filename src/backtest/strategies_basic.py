# -*- coding: utf-8 -*-
"""Trivial target-weight generators used by regression tests (M3).

These are not blog strategies — they are the known-answer cases from
CLAUDE.md §6 (buy & hold, static mixes with periodic rebalancing, all-cash).
"""

from __future__ import annotations

import pandas as pd


def buy_and_hold(index: pd.DatetimeIndex, ticker: str) -> pd.DataFrame:
    """Single signal on the first day: 100% into ticker, never touched again."""
    return pd.DataFrame({ticker: [1.0]}, index=index[:1])


def all_cash(index: pd.DatetimeIndex, ticker: str) -> pd.DataFrame:
    return pd.DataFrame({ticker: [0.0]}, index=index[:1])


def _period_ends(index: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    """Last trading day of each period. freq: 'M' | 'Q' | 'Y'."""
    key = {"M": index.to_period("M"), "Q": index.to_period("Q"),
           "Y": index.to_period("Y")}[freq]
    s = pd.Series(index, index=key)
    return pd.DatetimeIndex(s.groupby(level=0).last().values)


def static_mix(index: pd.DatetimeIndex, weights: dict, freq: str = "M") -> pd.DataFrame:
    """Fixed-weight portfolio re-signalled at each period end (e.g., 60/40)."""
    ends = _period_ends(index, freq)
    first = index[:1]
    signal_dates = first.union(ends)
    return pd.DataFrame([weights] * len(signal_dates), index=signal_dates)
