# -*- coding: utf-8 -*-
"""Performance metrics (CLAUDE.md §5 required set).

Conventions (documented for reproducibility):
- CAGR uses calendar time: (end/start)^(365.25/days_spanned) - 1.
- Sharpe: daily mean/std * sqrt(252), risk-free rate 0.
- win_rate: share of positive daily returns among days with market exposure.
- yearly returns: calendar-year compounding of daily returns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2 or equity.iloc[0] <= 0:
        return 0.0
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (365.25 / days) - 1)


def max_drawdown(equity: pd.Series) -> float:
    if len(equity) == 0:
        return 0.0
    dd = equity / equity.cummax() - 1.0
    return float(dd.min())


def sharpe(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * np.sqrt(TRADING_DAYS))


def win_rate(returns: pd.Series, exposure: pd.Series) -> float:
    invested = returns[(exposure > 1e-12) & returns.notna()]
    if len(invested) == 0:
        return 0.0
    return float((invested > 0).mean())


def yearly_returns(returns: pd.Series) -> dict:
    out = {}
    for year, grp in returns.dropna().groupby(returns.dropna().index.year):
        out[int(year)] = float((1 + grp).prod() - 1)
    return out


def summary(equity: pd.Series, returns: pd.Series, exposure: pd.Series,
            turnover: pd.Series, trade_days: int) -> dict:
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    return {
        "cagr": cagr(equity),
        "mdd": max_drawdown(equity),
        "sharpe": sharpe(returns),
        "win_rate": win_rate(returns, exposure),
        "yearly_returns": yearly_returns(returns),
        "trade_days": trade_days,
        "turnover_total_oneway": float(turnover.sum()),
        "turnover_annual_oneway": float(turnover.sum() / years),
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1),
    }


def monthly_summary(equity: pd.Series) -> dict:
    """Metrics recomputed on MONTH-END sampled equity.

    Several source posts report figures produced by R/PerformanceAnalytics on
    monthly series. Daily and monthly conventions differ materially: SPY's GFC
    drawdown is about -55% daily but about -51% month-end, and Sharpe scales by
    sqrt(12) instead of sqrt(252). Reporting both makes it visible whether a
    gap against a post's numbers is a convention difference or a logic one.
    """
    idx = equity.index
    ends = pd.Series(idx, index=idx.to_period("M")).groupby(level=0).last().values
    m = equity.loc[pd.DatetimeIndex(ends)]
    r = m.pct_change().dropna()
    if len(r) < 2 or r.std(ddof=1) == 0:
        sh = 0.0
    else:
        sh = float(r.mean() / r.std(ddof=1) * np.sqrt(12))
    return {"cagr_m": cagr(m), "mdd_m": max_drawdown(m), "sharpe_m": sh}
