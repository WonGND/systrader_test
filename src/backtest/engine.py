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
  execution is dropped to cash, and a held position whose price goes missing is
  carried flat; both cases are recorded in `warnings`.

The engine holds currency positions and walks day by day:
  prev close -> today's open (overnight, old weights)
  [execute pending rebalance at open]
  open -> close (intraday, new weights)
  [execute same-day-close rebalance if execution="close"]

The inner loop runs on numpy arrays: with 75-sleeve strategies the pandas
version took ~9s per run, which made the M4 batch impractical.
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
    if targets.index.has_duplicates:
        raise ValueError("targets index has duplicate signal dates")
    filled = targets.fillna(0.0)
    if ((filled.sum(axis=1) > 1 + 1e-9) | (filled < -1e-12).any(axis=1)).any():
        raise ValueError("weights must be >=0 and sum to <=1 (long-only, cash remainder)")

    dates = close.index
    cols = list(close.columns)
    k = len(cols)
    rate = commission + slippage

    O = open_.to_numpy(dtype=float)
    C = close.to_numpy(dtype=float)

    # map each signal date to its row position; drop targets outside the window
    pos_of = {d: i for i, d in enumerate(dates)}
    plan: dict = {}
    for d, row in filled.reindex(columns=cols).fillna(0.0).iterrows():
        if d in pos_of:
            plan[pos_of[d]] = row.to_numpy(dtype=float)

    cash = float(initial)
    hold = np.zeros(k)
    pending = None
    warnings: list = []

    eq = np.empty(len(dates))
    tos = np.zeros(len(dates))
    W = np.zeros((len(dates), k))
    total_cost = 0.0
    trade_days = 0

    def _rebalance(prices: np.ndarray, target: np.ndarray, when: str):
        nonlocal cash, hold
        value = cash + hold.sum()
        tgt = target
        missing = (tgt > 0) & ~np.isfinite(prices)
        if missing.any():
            tgt = tgt.copy()
            for j in np.flatnonzero(missing):
                warnings.append(f"{when}: {cols[j]} has no price — "
                                f"weight {tgt[j]:.4f} left in cash")
            tgt[missing] = 0.0
        # size against post-cost value so cash never goes negative:
        # estimate traded notional at pre-cost value, deduct cost, then allocate
        traded = float(np.abs(tgt * value - hold).sum())
        cost = traded * rate
        value_net = value - cost
        hold = tgt * value_net
        cash = value_net - hold.sum()
        return (traded / value if value > 0 else 0.0), cost

    prev_c = None
    for i in range(len(dates)):
        o = O[i]
        c = C[i]
        day_turnover = 0.0
        held = hold != 0.0

        # overnight: prev close -> today's open (old holdings)
        if prev_c is not None:
            ratio = o / prev_c
            ok = np.isfinite(ratio)
            stale = held & ~ok
            if stale.any():
                d = dates[i].date()
                for j in np.flatnonzero(stale):
                    warnings.append(f"{d} overnight: {cols[j]} price missing — "
                                    f"position value held flat (not interpolated)")
            hold = hold * np.where(held & ok, ratio, 1.0)

        # execute pending rebalance at today's open
        if pending is not None:
            to, cost = _rebalance(o, pending, f"{dates[i].date()} open")
            day_turnover += to
            total_cost += cost
            pending = None

        # intraday: open -> close (new holdings)
        held = hold != 0.0
        ratio = c / o
        ok = np.isfinite(ratio)
        stale = held & ~ok
        if stale.any():
            d = dates[i].date()
            for j in np.flatnonzero(stale):
                warnings.append(f"{d} intraday: {cols[j]} price missing — "
                                f"position value held flat (not interpolated)")
        hold = hold * np.where(held & ok, ratio, 1.0)

        # signal today
        if i in plan:
            target = plan[i]
            if execution == "close":
                to, cost = _rebalance(c, target, f"{dates[i].date()} close")
                day_turnover += to
                total_cost += cost
            else:
                pending = target

        value = cash + hold.sum()
        eq[i] = value
        tos[i] = day_turnover
        if value > 0:
            W[i] = hold / value
        if day_turnover > 1e-12:
            trade_days += 1
        prev_c = c

    equity = pd.Series(eq, index=dates, name="equity")
    turnover = pd.Series(tos, index=dates, name="turnover")
    weights = pd.DataFrame(W, index=dates, columns=cols)
    returns = equity.pct_change().fillna(0.0)
    exposure = weights.abs().sum(axis=1)
    return BacktestResult(equity=equity, returns=returns, weights=weights,
                          exposure=exposure, turnover=turnover,
                          trade_days=trade_days, costs_paid=total_cost,
                          warnings=warnings)
