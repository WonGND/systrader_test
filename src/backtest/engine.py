# -*- coding: utf-8 -*-
"""Daily portfolio backtest engine.

Design constraints (CLAUDE.md §5):
- Signal and execution are explicitly separated. Target weights are indexed by
  SIGNAL date; the engine executes them at the NEXT day's open by default
  ("next_open", conservative), or at the same day's close ("close") only when a
  strategy's source post explicitly says so.
- Costs (commission + one-way slippage) are charged on traded notional and come
  from config/backtest_defaults.yaml via settings.py — never hardcoded.
- Missing prices are never interpolated. A target on a ticker with no price at
  execution is dropped to cash and the gap is recorded in `warnings`.

The engine holds currency positions and walks day by day:
  prev close -> today's open (overnight, old weights)
  [execute pending rebalance at open]
  open -> close (intraday, new weights)
  [execute same-day-close rebalance if execution="close"]
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import metrics


@dataclass
class BacktestResult:
    equity: pd.Series
    returns: pd.Series
    weights: pd.DataFrame          # end-of-day realized weights
    exposure: pd.Series            # sum of absolute asset weights (cash excl.)
    turnover: pd.Series            # one-way traded notional / portfolio value
    trade_days: int
    costs_paid: float
    warnings: list = field(default_factory=list)

    def summary(self) -> dict:
        s = metrics.summary(self.equity, self.returns, self.exposure,
                            self.turnover, self.trade_days)
        s["costs_paid"] = self.costs_paid
        return s


def _validate(close: pd.DataFrame, open_: pd.DataFrame) -> None:
    if not close.index.equals(open_.index) or list(close.columns) != list(open_.columns):
        raise ValueError("open/close frames must share index and columns")
    if not close.index.is_monotonic_increasing:
        raise ValueError("price index must be sorted ascending")


def run_backtest(close: pd.DataFrame, open_: pd.DataFrame, targets: pd.DataFrame,
                 execution: str = "next_open", commission: float = 0.0,
                 slippage: float = 0.0, initial: float = 1.0) -> BacktestResult:
    """Run the engine.

    close/open_: price frames (same index/columns). targets: rows indexed by
    signal date (subset of price index), columns subset of price columns,
    weights in [0,1] summing to <=1 (remainder is cash earning 0).
    """
    if execution not in ("next_open", "close"):
        raise ValueError(f"unknown execution convention: {execution}")
    _validate(close, open_)
    bad = [c for c in targets.columns if c not in close.columns]
    if bad:
        raise ValueError(f"targets reference unknown tickers: {bad}")
    if ((targets.fillna(0).sum(axis=1) > 1 + 1e-9) | (targets.fillna(0) < -1e-12).any(axis=1)).any():
        raise ValueError("weights must be >=0 and sum to <=1 (long-only, cash remainder)")

    dates = close.index
    cols = list(close.columns)
    rate = commission + slippage

    cash = initial
    hold = pd.Series(0.0, index=cols)     # currency value per ticker
    pending = None                        # target scheduled for next open
    warnings: list = []

    eq, tos, wts = [], [], []

    def _rebalance(prices_row: pd.Series, target: pd.Series, when: str):
        nonlocal cash, hold
        value = cash + hold.sum()
        tgt = target.reindex(cols).fillna(0.0)
        # drop tickers with no price at execution (never interpolate)
        missing = tgt[(tgt > 0) & prices_row.reindex(cols).isna()]
        for tkr in missing.index:
            warnings.append(f"{when}: {tkr} has no price — weight {missing[tkr]:.4f} left in cash")
        tgt[missing.index] = 0.0
        # size against post-cost value so cash never goes negative:
        # estimate traded notional at pre-cost value, deduct cost, then allocate
        traded = (tgt * value - hold).abs().sum()
        cost = traded * rate
        value_net = value - cost
        hold = tgt * value_net
        cash = value_net - hold.sum()
        return traded / value if value > 0 else 0.0, cost

    total_cost = 0.0
    trade_days = 0
    prev_close_prices = None

    for i, dt in enumerate(dates):
        o = open_.loc[dt]
        c = close.loc[dt]
        day_turnover = 0.0

        # overnight: prev close -> today's open (old holdings)
        if prev_close_prices is not None:
            ratio = (o / prev_close_prices).reindex(cols)
            hold = hold * ratio.where(hold.abs() > 0, 1.0).fillna(1.0)

        # execute pending rebalance at today's open
        if pending is not None:
            to, cost = _rebalance(o, pending, f"{dt.date()} open")
            day_turnover += to
            total_cost += cost
            pending = None

        # intraday: open -> close (new holdings)
        ratio = (c / o).reindex(cols)
        hold = hold * ratio.where(hold.abs() > 0, 1.0).fillna(1.0)

        # signal today
        if dt in targets.index:
            target = targets.loc[dt]
            if isinstance(target, pd.DataFrame):   # duplicate signal dates
                raise ValueError(f"duplicate target rows for {dt}")
            if execution == "close":
                to, cost = _rebalance(c, target, f"{dt.date()} close")
                day_turnover += to
                total_cost += cost
            else:
                pending = target

        value = cash + hold.sum()
        eq.append(value)
        tos.append(day_turnover)
        wts.append((hold / value).values if value > 0 else np.zeros(len(cols)))
        if day_turnover > 1e-12:
            trade_days += 1
        prev_close_prices = c

    equity = pd.Series(eq, index=dates, name="equity")
    turnover = pd.Series(tos, index=dates, name="turnover")
    weights = pd.DataFrame(wts, index=dates, columns=cols)
    returns = equity.pct_change().fillna(0.0)
    exposure = weights.abs().sum(axis=1)
    return BacktestResult(equity=equity, returns=returns, weights=weights,
                          exposure=exposure, turnover=turnover,
                          trade_days=trade_days, costs_paid=total_cost,
                          warnings=warnings)
