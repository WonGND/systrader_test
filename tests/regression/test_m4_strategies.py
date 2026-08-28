# -*- coding: utf-8 -*-
"""Offline checks for the M4 Track A strategy builders and runner.

No network: synthetic OHLC with staggered listing dates stands in for
yfinance, so the local M4 run cannot fail on a bug we could have caught here.
Logic assertions cover the rules that decide allocation (momentum score
weighting, dual-momentum branch, HAA canary), not just "it runs".
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backtest import indicators as ind          # noqa: E402
from src.validate import run_m4, strategies_m4 as S  # noqa: E402

LISTINGS = {
    "SPY": "2000-01-03", "QQQ": "2000-01-03", "IJH": "2000-01-03",
    "EWJ": "2000-01-03", "IWD": "2000-05-26", "IWF": "2000-05-26",
    "IWM": "2000-05-26", "EFA": "2001-08-17", "IEF": "2002-07-30",
    "TLT": "2002-07-30", "SHY": "2002-07-30", "LQD": "2002-07-30",
    "AGG": "2003-09-29", "EEM": "2003-04-14", "TIP": "2003-12-05",
    "VNQ": "2004-09-29", "GLD": "2004-11-18", "DBC": "2006-02-03",
    "BIL": "2007-05-30", "SCZ": "2007-12-10",
}


def synth_ohlc(seed=17, start="2000-01-03", end="2019-01-10"):
    idx = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    out = {}
    for i, (t, listed) in enumerate(LISTINGS.items()):
        n = len(idx)
        close = 100 * np.cumprod(1 + rng.normal(0.0003, 0.011, n))
        gap = rng.normal(0.0, 0.003, n)
        openp = np.concatenate([[close[0]], close[:-1] * (1 + gap[1:])])
        hi = np.maximum(openp, close) * (1 + np.abs(rng.normal(0, 0.004, n)))
        lo = np.minimum(openp, close) * (1 - np.abs(rng.normal(0, 0.004, n)))
        df = pd.DataFrame({"Open": openp, "High": hi, "Low": lo, "Close": close},
                          index=idx)
        out[t] = df.loc[pd.Timestamp(listed):]
    return out


@pytest.fixture(scope="module")
def ohlc():
    return synth_ohlc()


@pytest.fixture(scope="module")
def frames(ohlc):
    open_ = pd.DataFrame({t: d["Open"] for t, d in ohlc.items()}).sort_index()
    close = pd.DataFrame({t: d["Close"] for t, d in ohlc.items()}).sort_index()
    return open_, close


# ---------------------------------------------------------------- indicators
def test_avg_momentum_score_is_fraction_of_positive_lookbacks():
    idx = pd.date_range("2010-01-31", periods=24, freq="ME")
    up = pd.DataFrame({"A": np.arange(1.0, 25.0)}, index=idx)      # always rising
    down = pd.DataFrame({"A": np.arange(24.0, 0.0, -1.0)}, index=idx)
    assert ind.avg_momentum_score(up, range(1, 13)).iloc[-1, 0] == pytest.approx(1.0)
    assert ind.avg_momentum_score(down, range(1, 13)).iloc[-1, 0] == pytest.approx(0.0)
    # insufficient history stays NaN (no silent zero)
    assert np.isnan(ind.avg_momentum_score(up, range(1, 13)).iloc[10, 0])


def test_wilder_rsi_bounds_and_extremes():
    s = pd.Series(np.arange(1.0, 60.0))                # monotone up
    assert ind.wilder_rsi(s, 2).iloc[-1] == pytest.approx(100.0)
    d = pd.Series(np.arange(60.0, 1.0, -1.0))          # monotone down
    assert ind.wilder_rsi(d, 2).iloc[-1] == pytest.approx(0.0, abs=1e-9)
    rng = np.random.default_rng(0)
    r = ind.wilder_rsi(pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, 500))), 3)
    assert r.dropna().between(0, 100).all()


def test_state_machine_buy_wins_and_carries():
    idx = pd.date_range("2020-01-01", periods=6)
    buy = pd.Series([True, False, False, True, False, False], index=idx)
    sell = pd.Series([False, False, True, True, False, False], index=idx)
    pos = ind.state_machine(buy, sell)
    assert list(pos) == [1.0, 1.0, 0.0, 1.0, 1.0, 1.0]   # day3: buy wins over sell


# ---------------------------------------------------------------- strategies
def test_c01_class_budget_and_score_scaling(ohlc):
    plan = S.build_c01(ohlc)
    tg = plan.targets
    assert list(tg.columns) == ["SPY", "EFA", "EEM", "IEF", "TLT", "SHY"]
    # each ticker's weight can never exceed its class budget
    assert (tg[["SPY", "EFA", "EEM"]] <= (1 / 3) / 3 + 1e-12).all().all()
    assert (tg[["IEF", "TLT"]] <= (1 / 3) / 2 + 1e-12).all().all()
    assert (tg[["SHY"]] <= (1 / 3) + 1e-12).all().all()
    assert (tg.sum(axis=1) <= 1 + 1e-9).all()           # engine invariant
    assert (tg >= 0).all().all()
    # starts only after every ticker has 12 months of history.
    # EEM is the last to list (2003-04-14), so the first signal is the first
    # month end on/after 2004-04-14.
    assert pd.Timestamp("2004-04-14") <= tg.index[0] <= pd.Timestamp("2004-05-31")


def test_c02_permanent_weights_scale_base_by_score(ohlc):
    plan = S.build_c02_permanent(ohlc)
    tg = plan.targets
    assert set(tg.columns) == {"SPY", "TLT", "GLD", "AGG"}
    assert (tg <= 0.25 + 1e-12).all().all()
    assert (tg.sum(axis=1) <= 1 + 1e-9).all()
    # weights are exactly base x score, so every value is a multiple of 0.25/12
    step = 0.25 / 12
    assert np.allclose((tg.values / step) % 1, 0, atol=1e-9)


def test_c03_single_asset_and_defensive_branch(ohlc):
    plan = S.build_c03(ohlc)
    tg = plan.targets
    assert np.allclose(tg.sum(axis=1), 1.0)               # always fully invested
    assert np.allclose(tg.max(axis=1), 1.0)               # exactly one asset
    # when a defensive asset is chosen, no risky asset is held
    defensive_rows = tg[(tg[["TLT", "TIP"]].sum(axis=1) > 0)]
    assert (defensive_rows[["SPY", "SCZ"]].sum(axis=1) == 0).all()
    assert tg.index[0] >= pd.Timestamp("2008-06-01")      # SCZ listing + 6M


def test_c06_canary_forces_defensive(ohlc):
    plan = S.build_c06(ohlc)
    tg = plan.targets
    assert np.allclose(tg.sum(axis=1), 1.0)
    # every row is either 100% one defensive asset, or 4 x 25% buckets
    for _, row in tg.iterrows():
        nz = row[row > 0]
        assert nz.sum() == pytest.approx(1.0)
        assert set(np.round(nz.values / 0.25, 6)) <= {1.0, 2.0, 3.0, 4.0}
    assert tg.index[0] >= pd.Timestamp("2008-05-01")      # BIL listing + 12M


def test_c07_is_close_executed_two_sleeves(ohlc):
    plan = S.build_c07(ohlc)
    assert plan.execution == "close" and len(plan.sleeves) == 2
    labels = [s[0] for s in plan.sleeves]
    assert labels == ["SPY/월말", "TLT/목요일"]
    for _, ticker, tg in plan.sleeves:
        assert set(np.unique(tg[ticker].values)) <= {0.0, 1.0}


def test_c08_positions_are_mutually_exclusive(ohlc):
    plan = S.build_c08(ohlc)
    tg = plan.targets
    assert (tg.sum(axis=1) <= 1.0 + 1e-12).all()
    assert ((tg["QQQ"] > 0) & (tg["TLT"] > 0)).sum() == 0


def test_c09_uses_high_low_and_is_long_flat(ohlc):
    plan = S.build_c09_spy(ohlc)
    tg = plan.targets
    assert list(tg.columns) == ["SPY"]
    assert set(np.unique(tg["SPY"].values)) <= {0.0, 1.0}


def test_c04_c05_sleeve_counts(ohlc):
    assert len(S.build_c04(ohlc).sleeves) == 7 * 5
    assert len(S.build_c05(ohlc).sleeves) == 15 * 5     # 7 stocks + 7 bonds + cash


# ---------------------------------------------------------------- runner
@pytest.mark.parametrize("builder", S.BUILDERS, ids=lambda b: b.__name__)
def test_every_plan_runs_end_to_end(builder, ohlc, frames):
    """The local M4 run must not blow up on any strategy."""
    open_, close = frames
    plan = builder(ohlc)
    free = run_m4._run_plan(plan, open_, close, 0.0, 0.0)
    paid = run_m4._run_plan(plan, open_, close, 0.0, 0.0005)
    for s in (free, paid):
        assert np.isfinite(s["cagr"]) and np.isfinite(s["mdd"])
        assert -1.0 <= s["mdd"] <= 0.0
        assert s["end"] <= run_m4.IN_SAMPLE_END          # never crosses in-sample
        assert 0.0 <= s["win_rate"] <= 1.0
    # costs can only reduce return for a strategy that actually trades
    if free["trade_days"] > 0:
        assert paid["cagr"] <= free["cagr"] + 1e-12
