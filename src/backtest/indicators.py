# -*- coding: utf-8 -*-
"""Shared indicators for strategy implementations.

Definitions are fixed here so every strategy uses the same maths and the
choices are auditable in one place.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def month_end_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last trading day of each calendar month present in `index`."""
    s = pd.Series(index, index=index.to_period("M"))
    return pd.DatetimeIndex(s.groupby(level=0).last().values)


def monthly_closes(close: pd.DataFrame) -> pd.DataFrame:
    """Close prices sampled on the last trading day of each month."""
    return close.loc[month_end_dates(close.index)]


def avg_momentum_score(m: pd.DataFrame, lookbacks) -> pd.DataFrame:
    """systrader79's '평균 모멘텀 스코어': fraction of lookbacks with a
    positive return. Range [0, 1]. NaN until the longest lookback is available.
    """
    lookbacks = list(lookbacks)
    hits = None
    for k in lookbacks:
        hit = (m / m.shift(k) > 1).astype(float)
        hits = hit if hits is None else hits + hit
    score = hits / len(lookbacks)
    return score.where(m.shift(max(lookbacks)).notna())


def avg_momentum_return(m: pd.DataFrame, lookbacks) -> pd.DataFrame:
    """Mean of the lookback returns (Antonacci/Keller style momentum)."""
    lookbacks = list(lookbacks)
    tot = None
    for k in lookbacks:
        r = m / m.shift(k) - 1.0
        tot = r if tot is None else tot + r
    out = tot / len(lookbacks)
    return out.where(m.shift(max(lookbacks)).notna())


def wilder_rsi(s: pd.Series, period: int) -> pd.Series:
    """Wilder's RSI (matches TA-Lib's RSI, which the source posts' code used)."""
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = rsi.where(avg_loss > 0, 100.0)              # no losses -> 100
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)  # flat -> 50
    return rsi.where(avg_gain.notna())


def sma(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window).mean()


def state_machine(buy: pd.Series, sell: pd.Series) -> pd.Series:
    """Long/flat position: buy wins on ties, otherwise carry the last state.

    Mirrors the source posts' pandas code:
        pos = where(buy, 1, where(sell, 0, nan)).ffill()
    """
    raw = pd.Series(np.where(buy.fillna(False), 1.0,
                             np.where(sell.fillna(False), 0.0, np.nan)),
                    index=buy.index)
    return raw.ffill().fillna(0.0)


def first_common_date(frames: dict, tickers) -> pd.Timestamp:
    """Earliest date on which every required ticker already has a price."""
    starts = []
    for t in tickers:
        s = frames[t]["Close"].dropna()
        if s.empty:
            raise ValueError(f"no price data for {t}")
        starts.append(s.index[0])
    return max(starts)
