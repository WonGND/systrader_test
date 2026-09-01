# -*- coding: utf-8 -*-
"""Offline checks for the M6 batch runner.

The things that can go wrong in M6 and would be invisible until the final
report: the post-publication slice being treated as a verdict, the
contamination flag drifting from the specs' published_at, and the batch set
quietly losing (or inventing) strategies.
"""

import sys
from pathlib import Path

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
