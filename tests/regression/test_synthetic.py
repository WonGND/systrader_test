# -*- coding: utf-8 -*-
"""M3 regression tests on synthetic data (CLAUDE.md §6).

Covered here (no network needed):
- constant-return series: engine compounding matches the analytic value
- 100% cash: exactly zero return
- costs off vs on: direction (worse) and magnitude (= turnover x rate)
- look-ahead detection: shifting the signal into the future produces an
  unrealistic improvement (proves signal/execution separation is real)
- 60/40 static mix with monthly/quarterly/yearly rebalancing behavior
- buy & hold equals the raw price ratio

The remaining §6 item (SPY buy&hold vs externally published CAGR/MDD, real
data) runs locally via tests/regression/run_real_checks.py.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backtest import strategies_basic as sb          # noqa: E402
from src.backtest.engine import run_backtest             # noqa: E402
from src.backtest.metrics import cagr as cagr_fn         # noqa: E402
from src.backtest import settings                        # noqa: E402


def make_prices(returns_by_ticker: dict, start="2015-01-01"):
    """Build gapless synthetic open/close frames: open_t = close_{t-1}."""
    n = len(next(iter(returns_by_ticker.values())))
    idx = pd.bdate_range(start, periods=n)
    closes = {}
    for tkr, rets in returns_by_ticker.items():
        closes[tkr] = 100.0 * np.cumprod(1.0 + np.asarray(rets))
    close = pd.DataFrame(closes, index=idx)
    open_ = close.shift(1)
    open_.iloc[0] = 100.0
    return open_, close


def test_constant_return_matches_analytic_cagr():
    r, n = 0.001, 504
    open_, close = make_prices({"AAA": [r] * n})
    res = run_backtest(close, open_, sb.buy_and_hold(close.index, "AAA"))
    # signal day0 -> executed at open of day1 (= close of day0)
    expected_total = close["AAA"].iloc[-1] / close["AAA"].iloc[0]
    assert res.equity.iloc[-1] == pytest.approx(expected_total, rel=1e-12)
    # analytic CAGR under the documented calendar convention
    days = (close.index[-1] - close.index[0]).days
    analytic = expected_total ** (365.25 / days) - 1
    assert cagr_fn(res.equity) == pytest.approx(analytic, rel=1e-12)


def test_all_cash_returns_exactly_zero():
    open_, close = make_prices({"AAA": np.random.default_rng(0).normal(0.001, 0.02, 300)})
    res = run_backtest(close, open_, sb.all_cash(close.index, "AAA"))
    assert res.equity.iloc[-1] == pytest.approx(1.0, abs=0.0)
    assert res.returns.abs().max() == 0.0
    s = res.summary()
    assert s["cagr"] == 0.0 and s["mdd"] == 0.0 and s["trade_days"] == 0


def test_buy_and_hold_equals_price_ratio():
    rng = np.random.default_rng(1)
    open_, close = make_prices({"AAA": rng.normal(0.0005, 0.01, 750)})
    res = run_backtest(close, open_, sb.buy_and_hold(close.index, "AAA"))
    expected = close["AAA"] / close["AAA"].iloc[0]
    # from execution day onward the equity path is the price path
    assert np.allclose(res.equity.iloc[1:], expected.iloc[1:], rtol=1e-12)


def test_costs_direction_and_magnitude():
    rng = np.random.default_rng(2)
    open_, close = make_prices({"AAA": rng.normal(0.0004, 0.01, 500),
                                "BBB": rng.normal(0.0004, 0.01, 500)})
    # alternate 100% AAA <-> 100% BBB at each month end: one-way turnover 2.0/switch
    ends = sb._period_ends(close.index, "M")
    rows, flip = [], True
    for _ in ends:
        rows.append({"AAA": 1.0 if flip else 0.0, "BBB": 0.0 if flip else 1.0})
        flip = not flip
    targets = pd.DataFrame(rows, index=ends)

    _, slip = settings.costs()      # from config, not hardcoded
    assert slip > 0                 # config sanity (0.05% one-way expected)
    free = run_backtest(close, open_, targets, slippage=0.0)
    paid = run_backtest(close, open_, targets, slippage=slip)

    # direction: costs strictly reduce final equity
    assert paid.equity.iloc[-1] < free.equity.iloc[-1]
    # magnitude: log-ratio equals sum(log(1 - turnover_t * slip)) exactly,
    # and approximately total_turnover * slip
    expected_drag = np.sum(np.log1p(-paid.turnover.values * slip))
    actual_drag = np.log(paid.equity.iloc[-1] / free.equity.iloc[-1])
    assert actual_drag == pytest.approx(expected_drag, rel=1e-6)
    approx_drag = -paid.turnover.sum() * slip
    assert actual_drag == pytest.approx(approx_drag, rel=0.02)


def test_lookahead_detection():
    """Shifting the signal one day into the future must improve results to an
    unrealistic degree — proving execution timing actually separates signal
    from fill (an engine with hidden look-ahead would show no such gap)."""
    rng = np.random.default_rng(3)
    rets = rng.normal(0.0, 0.012, 1000)          # zero-drift random walk
    open_, close = make_prices({"AAA": rets})
    daily = close["AAA"].pct_change()

    # proper strategy: hold when YESTERDAY's return was positive (no edge)
    proper_w = (daily > 0).astype(float)
    proper_targets = pd.DataFrame({"AAA": proper_w}).dropna()
    proper = run_backtest(close, open_, proper_targets, execution="close")

    # cheating strategy: hold when TOMORROW's return is positive (foresight)
    cheat_w = (daily.shift(-1) > 0).astype(float)
    cheat_targets = pd.DataFrame({"AAA": cheat_w}).dropna()
    cheat = run_backtest(close, open_, cheat_targets, execution="close")

    total_up = float(daily[daily > 0].add(1).prod())
    # foresight captures (nearly) every up day; the proper one cannot
    assert cheat.equity.iloc[-1] == pytest.approx(total_up / (1 + daily.dropna().iloc[-1] if cheat_w.iloc[-1] else 1), rel=0.2)
    assert cheat.equity.iloc[-1] > 5 * proper.equity.iloc[-1]
    assert cheat.equity.iloc[-1] > 5 * (close["AAA"].iloc[-1] / close["AAA"].iloc[0])


@pytest.mark.parametrize("freq,min_rebalances,max_rebalances", [
    ("M", 20, 30), ("Q", 7, 10), ("Y", 2, 4)])
def test_6040_static_mix_rebalance_periods(freq, min_rebalances, max_rebalances):
    rng = np.random.default_rng(4)
    open_, close = make_prices({"STK": rng.normal(0.0008, 0.012, 550),
                                "BND": rng.normal(0.0002, 0.004, 550)})
    targets = sb.static_mix(close.index, {"STK": 0.6, "BND": 0.4}, freq=freq)
    res = run_backtest(close, open_, targets)

    # trades happen only on scheduled execution days (next open after signal)
    assert min_rebalances <= res.trade_days <= max_rebalances
    sched = set()
    for d in targets.index:
        pos = close.index.get_loc(d)
        if pos + 1 < len(close.index):
            sched.add(close.index[pos + 1])
    trade_dates = set(res.turnover[res.turnover > 1e-12].index)
    assert trade_dates <= sched

    # on each execution day, realized close weights are near 60/40
    # (exact at open; intraday drift moves them slightly)
    for d in sorted(trade_dates):
        w = res.weights.loc[d, "STK"]
        assert abs(w - 0.6) < 0.02
    # weights drift between rebalances (not pinned at 60/40 every day)
    assert (res.weights["STK"] - 0.6).abs().max() > 0.005
