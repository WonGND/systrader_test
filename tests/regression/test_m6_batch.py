# -*- coding: utf-8 -*-
"""Offline checks for the M6 batch runner.

The things that can go wrong in M6 and would be invisible until the final
report: the post-publication slice being treated as a verdict, the
contamination flag drifting from the specs' published_at, and the batch set
quietly losing (or inventing) strategies.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.validate import run_m5 as M5  # noqa: E402
from src.validate import run_m6, strategies_m5 as S5, strategies_m6 as S6  # noqa: E402
from tests.regression.test_m5_oos import _fake_run  # noqa: E402


@pytest.fixture(scope="module")
def ohlc():
    from tests.regression.test_m4_strategies import synth_ohlc
    return synth_ohlc(seed=31, end="2024-12-31")


# ------------------------------------------------------------------ batch set
def test_batch_set_contains_every_m5_run():
    """M6 may add strategies; it must never silently drop one."""
    assert {b.__name__ for b in S6.BUILDERS} >= {b.__name__ for b in S5.BUILDERS}
    assert set(S6.ALL_TICKERS) >= set(S5.ALL_TICKERS)


def test_rejected_candidates_stay_out():
    """C11/C14/C15 were excluded with reasons at the M5 gate."""
    names = " ".join(b.__name__ for b in S6.BUILDERS)
    for rejected in ("c11", "c14", "c15"):
        assert rejected not in names


def test_no_placeholder_builders():
    """A pending strategy must be absent, not stubbed with invented rules."""
    assert S6.PENDING_BUILDERS == [] or all(callable(b) for b in S6.PENDING_BUILDERS)
    assert len(S6.BUILDERS) == len(S5.BUILDERS) + len(S6.PENDING_BUILDERS)


# -------------------------------------------------------------- contamination
def test_contamination_flag_follows_the_oos_boundary():
    assert run_m6._contaminated(pd.Timestamp("2019-01-01")) is True
    assert run_m6._contaminated(pd.Timestamp("2024-10-21")) is True
    assert run_m6._contaminated(pd.Timestamp("2018-12-31")) is False
    assert run_m6._contaminated(None) is False


def test_published_dates_come_from_the_specs():
    """The L-09 table in the report must match what the specs actually say."""
    expected = {
        "c01-avg-momentum-score-allocation-14-17": ("2014-05-07", False),
        "c02-dynamic-permanent-allweather-72": ("2020-02-27", True),
        "c03-accelerating-dual-momentum-60": ("2018-09-28", False),
        "c04-rsi2-counter-trend-39": ("2017-04-04", False),
        "c05-multi-ma-breakout-35": ("2017-03-26", False),
        "c06-hybrid-asset-allocation-136": ("2023-04-05", True),
        "c07-weekday-monthend-seasonality-115": ("2021-07-05", True),
        "c08-qqq-tlt-spread-rsi3": ("2024-10-21", True),
        "c09-ibs-lower-band-mean-reversion": ("2024-10-25", True),
        "c13-modified-paa-31-ported": ("2017-02-05", False),
    }
    for spec_id, (date, dirty) in expected.items():
        pub = run_m6._published_at(spec_id)
        assert str(pub.date()) == date, spec_id
        assert run_m6._contaminated(pub) is dirty, spec_id


def test_track_is_read_from_the_spec_not_guessed():
    assert run_m6._track("c13-modified-paa-31-ported") == "ported"
    assert run_m6._track("c01-avg-momentum-score-allocation-14-17") == "native_overseas"
    assert run_m6._track("does-not-exist") == "?"


# ---------------------------------------------------- post-publication slice
def test_post_publication_slice_starts_after_the_post_and_is_not_a_verdict():
    idx = pd.bdate_range("2015-01-01", "2026-08-31")
    eq = pd.Series(range(len(idx)), index=idx, dtype=float) / len(idx) + 1.0
    run = _fake_run(eq)
    pub = pd.Timestamp("2021-07-05")
    start = (pub + pd.DateOffset(months=run_m6.POST_PUBLICATION_LAG_MONTHS)).normalize()
    post = M5._slice(run, start=start)
    assert post["start"] >= "2021-08-05"
    # the OOS slice used for the verdict is unaffected by it
    oos = M5._slice(run, start=M5.OOS_START)
    assert oos["start"] <= "2019-01-05"
    assert post["start"] > oos["start"]


def test_verdict_uses_the_fixed_window_even_for_contaminated_posts(ohlc):
    """§5 forbids per-strategy boundaries: the verdict must be computed on the
    2019-01-01 slice, never on the post-publication one."""
    open_ = pd.DataFrame({t: d["Open"] for t, d in ohlc.items()}).sort_index()
    close = pd.DataFrame({t: d["Close"] for t, d in ohlc.items()}).sort_index()
    plan = S5.build_c13(ohlc)
    run = M5._run_full(plan, open_, close, 0.0, 0.0005)
    oos = M5._slice(run, start=M5.OOS_START)
    post = M5._slice(run, start=pd.Timestamp("2022-01-01"))
    ins = M5._slice(run, end=M5.IN_SAMPLE_END)
    spy = {"cagr": 0.10}
    assert M5.judge(oos, ins, spy) != M5.judge(post, ins, spy) or \
        oos["cagr"] == pytest.approx(post["cagr"])   # differ unless identical
    assert M5.judge(oos, ins, spy)["criteria"]["cagr_ge_spy"]["oos"] == oos["cagr"]


# ------------------------------------------------------------- C10 (Connors)
def test_c10_is_long_flat_and_respects_both_exits(ohlc):
    from src.backtest import indicators as ind
    plan = S6.build_c10_spy(ohlc)
    tg = plan.targets
    assert list(tg.columns) == ["SPY"] and plan.execution == "next_open"
    assert set(np.unique(tg["SPY"].values)) <= {0.0, 1.0}

    close, high = ohlc["SPY"]["Close"], ohlc["SPY"]["High"]
    ma200, rsi2 = ind.sma(close, 200), ind.wilder_rsi(close, 2)
    pos = tg["SPY"].reindex(close.index).ffill().fillna(0.0)
    # never long while below the 200-day line (the post's bear-market exit)
    below = (close < ma200) & ma200.notna()
    assert (pos[below] == 0.0).all()
    # entry days must satisfy both conditions
    entries = pos.index[(pos.diff() > 0)]
    for d in entries:
        assert close[d] > ma200[d] and rsi2[d] < 5


def test_c10_qqq_uses_its_own_price_not_spy(ohlc):
    spy = S6.build_c10_spy(ohlc).targets["SPY"]
    qqq = S6.build_c10_qqq(ohlc).targets["QQQ"]
    assert not spy.index.equals(qqq.index) or not np.array_equal(spy.values, qqq.values)


def test_c10_holds_nothing_before_the_200day_average_exists(ohlc):
    plan = S6.build_c10_spy(ohlc)
    pos = plan.targets["SPY"]
    first_long = pos[pos > 0].index[0]
    assert first_long >= ohlc["SPY"].index[199]


# ------------------------------------------------------ C12 (Defense First)
def test_c12_is_always_fully_invested_in_rank_weights(ohlc):
    tg = S6.build_c12(ohlc).targets
    assert list(tg.columns) == ["TLT", "GLD", "PDBC", "UUP", "SPY", "BIL"]
    assert np.allclose(tg.sum(axis=1), 1.0)
    # every weight is a sum of the 40/30/20/10 buckets
    allowed = {round(x, 4) for x in
               (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)}
    assert set(np.round(tg.values.ravel(), 4)) <= allowed


def test_c12_never_holds_the_risk_free_proxy(ohlc):
    """BIL is the comparison yardstick, not an asset the strategy buys."""
    tg = S6.build_c12(ohlc).targets
    assert (tg["BIL"] == 0.0).all()


def test_c12_routes_weak_defensive_weight_into_spy(ohlc):
    from src.backtest import indicators as ind
    tg = S6.build_c12(ohlc).targets
    close = pd.DataFrame({t: ohlc[t]["Close"] for t in
                          ["TLT", "GLD", "PDBC", "UUP", "SPY", "BIL"]}).dropna()
    mom = ind.avg_momentum_return(ind.monthly_closes(close), [1, 3, 6, 12])
    checked = 0
    for dt in tg.index:
        weak = [t for t in ["TLT", "GLD", "PDBC", "UUP"]
                if mom.loc[dt, t] < mom.loc[dt, "BIL"]]
        # a defensive asset below the risk-free bar is never held
        for t in weak:
            assert tg.loc[dt, t] == 0.0
        if len(weak) == 4:
            assert tg.loc[dt, "SPY"] == pytest.approx(1.0)   # the post's worst case
            checked += 1
    assert checked > 0, "합의 신호(4개 전부 약세) 구간이 없으면 전환 규칙이 검증되지 않는다"


def test_c12_execution_variants_differ_only_in_convention(ohlc):
    a, b = S6.build_c12(ohlc), S6.build_c12_next_open(ohlc)
    assert a.execution == "close" and a.alt_execution == "next_open"
    assert b.execution == "next_open"
    assert np.allclose(a.targets.values, b.targets.values)   # same signals


def test_c12_starts_only_after_its_last_listing_plus_momentum(ohlc):
    """PDBC lists in 2014, so the in-sample window is short - the report has to
    say so, and this pins the fact."""
    tg = S6.build_c12(ohlc).targets
    assert tg.index[0] >= pd.Timestamp("2015-01-31")
    in_sample = tg.loc[:M5.IN_SAMPLE_END]
    assert len(in_sample) < 60          # fewer than 5 years of monthly signals


# ------------------------------------------------------------------- specs
@pytest.mark.parametrize("spec_id,published,tickers", [
    ("c10-connors-rsi2-simple", "2024-10-23", ["SPY", "QQQ"]),
    ("c12-defense-first-taa", "2025-07-28",
     ["TLT", "GLD", "PDBC", "UUP", "SPY", "BIL"]),
])
def test_new_specs_are_wired_to_the_runner(spec_id, published, tickers):
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "data" / "specs"
    spec = [json.load(open(p, encoding="utf-8"))
            for p in path.glob("c*.json")
            if json.load(open(p, encoding="utf-8"))["spec_id"] == spec_id][0]
    assert spec["source"]["published_at"] == published
    assert str(run_m6._published_at(spec_id).date()) == published
    assert run_m6._contaminated(run_m6._published_at(spec_id)) is True   # L-09
    assert spec["strategy"]["universe"]["resolved_tickers"] == tickers
    assert spec["scope"]["track"] == "native_overseas"
    # every value field must carry a quote unless it is explicitly an assumption
    from src.extractor.verify_quotes import walk_quotes
    assert len(walk_quotes(spec["strategy"], "strategy")) >= 15
