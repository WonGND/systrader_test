# -*- coding: utf-8 -*-
"""Offline checks for the M5 OOS runner and the C13 (ported) builder.

The local M5 run must not be the place where a slicing or verdict bug is first
seen, so the window slicing, the §7 verdict table, the walk-forward summary and
the C13 rules are all exercised here against synthetic prices.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backtest import metrics, settings  # noqa: E402
from src.backtest.engine import run_backtest  # noqa: E402
from src.validate import run_m5, strategies_m5 as S5  # noqa: E402
from tests.regression.test_m4_strategies import synth_ohlc  # noqa: E402


@pytest.fixture(scope="module")
def ohlc():
    # far enough past the boundary that the OOS window is a real sample
    return synth_ohlc(seed=23, end="2024-12-31")


@pytest.fixture(scope="module")
def frames(ohlc):
    open_ = pd.DataFrame({t: d["Open"] for t, d in ohlc.items()}).sort_index()
    close = pd.DataFrame({t: d["Close"] for t, d in ohlc.items()}).sort_index()
    return open_, close


# ------------------------------------------------------------------ config
def test_thresholds_come_from_config_not_code():
    j = settings.load()["judgment"]
    assert run_m5.SHARPE_MIN == float(j["oos_sharpe_min"])
    assert run_m5.MDD_MULT == float(j["oos_mdd_max_vs_insample"])
    assert run_m5.MIN_OOS_REBALANCES == int(j["min_oos_rebalances"])
    assert str(run_m5.IN_SAMPLE_END.date()) == settings.load()["periods"]["in_sample_end"]
    assert str(run_m5.OOS_START.date()) == settings.load()["periods"]["oos_start"]


def test_config_auto_adjust_matches_code():
    """A documented convention that disagrees with the code is a bug (§9)."""
    from src.backtest import data
    assert settings.load()["data"]["auto_adjust"] is data.AUTO_ADJUST


# ------------------------------------------------------------------ slicing
def _fake_run(equity: pd.Series) -> dict:
    ret = equity.pct_change().fillna(0.0)
    return {"equity": equity, "returns": ret,
            "exposure": pd.Series(1.0, index=equity.index),
            "turnover": pd.Series(0.0, index=equity.index),
            "warnings": 0, "sleeves": None}


def test_slice_windows_do_not_overlap_and_carry_the_boundary_bar():
    idx = pd.bdate_range("2015-01-01", "2021-12-31")
    eq = pd.Series(np.linspace(1.0, 2.0, len(idx)), index=idx)
    run = _fake_run(eq)
    ins = run_m5._slice(run, end=run_m5.IN_SAMPLE_END)
    oos = run_m5._slice(run, start=run_m5.OOS_START)
    assert ins["end"] <= "2018-12-31"
    # the reported OOS start is the first day INSIDE the window, while the
    # equity base bar sits on the last in-sample day so day one's return counts
    assert oos["start"] >= "2019-01-01"
    assert oos["base_bar"] <= "2018-12-31"
    assert min(oos["yearly_returns"]) == 2019
    assert max(ins["yearly_returns"]) == 2018


def test_oos_drawdown_is_referenced_to_the_window_not_to_history():
    """A crash before 2019 must not count against the OOS drawdown."""
    idx = pd.bdate_range("2015-01-01", "2021-12-31")
    eq = pd.Series(1.0, index=idx)
    eq.loc["2016-01-01":"2016-06-30"] = 0.4          # -60% inside the in-sample
    eq.loc["2016-07-01":] = 1.0
    eq.loc["2020-03-01":"2020-04-30"] = 0.9          # -10% inside the OOS
    eq.loc["2020-05-01":] = 1.0
    run = _fake_run(eq)
    assert run_m5._slice(run, end=run_m5.IN_SAMPLE_END)["mdd"] == pytest.approx(-0.6)
    assert run_m5._slice(run, start=run_m5.OOS_START)["mdd"] == pytest.approx(-0.1)


def test_running_once_keeps_a_position_open_across_the_boundary(frames):
    """Restarting the engine in 2019 would flatten a position held since 2018
    and invent a trade. The full run must not do that."""
    open_, close = frames
    tickers = ["SPY"]
    tg = pd.DataFrame({"SPY": [1.0]}, index=[close.index[300]])   # buy once, hold
    res = run_backtest(close[tickers], open_[tickers], tg)
    oos = run_m5._slice(_fake_run(res.equity), start=run_m5.OOS_START)
    price = close["SPY"]
    first = price.index[price.index >= run_m5.OOS_START][0]
    expected = price.iloc[-1] / price.loc[:first].iloc[-2] - 1
    assert oos["total_return"] == pytest.approx(expected, rel=1e-9)
    assert oos["rebalances"] == 0            # no trade manufactured at the seam


# ------------------------------------------------------------------ verdict
def _stub(sharpe, mdd, cagr, rebal=24):
    return {"sharpe": sharpe, "mdd": mdd, "cagr": cagr, "rebalances": rebal}


@pytest.mark.parametrize("sharpe,mdd,cagr,expected", [
    (0.8, -0.15, 0.12, "alive"),          # 3/3
    (0.8, -0.15, 0.05, "weak"),           # CAGR below SPY
    (0.2, -0.40, 0.12, "dead"),           # only CAGR passes -> 1/3 is dead (§7)
    (0.2, -0.40, 0.05, "dead"),           # 0/3
    (0.50, -0.15, 0.10, "alive"),         # thresholds are inclusive
])
def test_verdict_table(sharpe, mdd, cagr, expected):
    ins, spy = _stub(1.0, -0.10, 0.08), _stub(0.6, -0.34, 0.10)
    assert run_m5.judge(_stub(sharpe, mdd, cagr), ins, spy)["verdict"] == expected


def test_mdd_criterion_uses_1_5x_of_in_sample():
    ins, spy = _stub(1.0, -0.10, 0.08), _stub(0.6, -0.34, 0.10)
    at_limit = run_m5.judge(_stub(0.8, -0.15, 0.12), ins, spy)
    over = run_m5.judge(_stub(0.8, -0.1501, 0.12), ins, spy)
    assert at_limit["criteria"]["mdd_vs_in_sample"]["pass"]
    assert not over["criteria"]["mdd_vs_in_sample"]["pass"]


def test_thin_sample_is_held_not_judged():
    ins, spy = _stub(1.0, -0.10, 0.08), _stub(0.6, -0.34, 0.10)
    v = run_m5.judge(_stub(2.0, -0.01, 0.50, rebal=11), ins, spy)
    assert v["verdict"] == "insufficient_sample" and v["met"] is None
    assert run_m5.judge(_stub(2.0, -0.01, 0.50, rebal=12), ins, spy)["verdict"] == "alive"


def test_walk_forward_reports_both_windows_without_refitting():
    idx = pd.bdate_range("2005-01-01", "2024-12-31")
    eq = pd.Series(np.cumprod(np.full(len(idx), 1.0003)), index=idx)
    wf = run_m5.walk_forward(_fake_run(eq))
    assert set(wf) == {"in_sample", "oos"}
    for tag in wf:
        assert wf[tag]["share_positive"] == 1.0          # monotone series
        assert wf[tag]["cagr_min"] > 0


# ---------------------------------------------------------------------- C13
def test_c13_is_in_the_m5_set_but_not_the_m4_set():
    from src.validate import strategies_m4 as S4
    m4 = {b.__name__ for b in S4.BUILDERS}
    m5 = {b.__name__ for b in S5.BUILDERS}
    assert not any("c13" in n for n in m4)      # Track B는 M4 재현 대상이 아니다
    assert m5 >= m4 | {"build_c13", "build_c13_score_safe"}


def test_c13_weights_respect_the_ported_design(ohlc):
    plan = S5.build_c13(ohlc)
    tg = plan.targets
    assert list(tg.columns) == ["SPY", "EFA", "IEF", "SHY"]
    assert np.allclose(tg.sum(axis=1), 1.0)               # 잔여분은 SHY로
    assert (tg >= -1e-12).all().all()
    # 상대 모멘텀 상위 1개만 보유 → 두 위험자산을 동시에 들지 않는다
    assert ((tg["SPY"] > 1e-12) & (tg["EFA"] > 1e-12)).sum() == 0
    # 위험자산군 예산 50%, 안전자산군 고정 50%
    assert (tg[["SPY", "EFA"]].max(axis=1) <= 0.5 + 1e-12).all()
    assert set(np.round(tg["IEF"].unique(), 9)) <= {0.0, 0.5}   # 0.0 = 게이트 현금화


def test_c13_equity_gate_moves_everything_to_cash(ohlc):
    plan = S5.build_c13(ohlc)
    tg = plan.targets
    off = tg["SHY"] >= 1.0 - 1e-12
    assert off.any(), "게이트가 한 번도 작동하지 않으면 5단계가 검증되지 않는다"
    assert (tg.loc[off, ["SPY", "EFA", "IEF"]].sum(axis=1) == 0).all()


def test_c13_gate_uses_only_past_equity(ohlc):
    """Shifting the whole price history later must not change the gate pattern
    at the corresponding dates — a look-ahead gate would react differently."""
    plan = S5.build_c13(ohlc)
    shifted = {t: d.copy() for t, d in ohlc.items()}
    cutoff = pd.Timestamp("2020-01-01")
    for t, d in shifted.items():                 # perturb only the future
        d.loc[cutoff:, ["Open", "High", "Low", "Close"]] *= 1.5
    plan2 = S5.build_c13(shifted)
    a = plan.targets.loc[:"2019-06-30"]
    b = plan2.targets.loc[:"2019-06-30"]
    assert a.index.equals(b.index)
    assert np.allclose(a.values, b.values)


def test_c13_safe_score_variant_differs(ohlc):
    a = S5.build_c13(ohlc).targets
    b = S5.build_c13_score_safe(ohlc).targets
    common = a.index.intersection(b.index)
    assert not np.allclose(a.loc[common].values, b.loc[common].values)


# ------------------------------------------------------------------- runner
@pytest.mark.parametrize("builder", S5.BUILDERS, ids=lambda b: b.__name__)
def test_every_plan_runs_and_is_judged(builder, ohlc, frames):
    open_, close = frames
    plan = builder(ohlc)
    run = run_m5._run_full(plan, open_, close, 0.0, 0.0005)
    ins = run_m5._slice(run, end=run_m5.IN_SAMPLE_END)
    oos = run_m5._slice(run, start=run_m5.OOS_START)
    assert ins is not None and oos is not None
    assert ins["end"] <= "2018-12-31" and oos["start"] >= "2019-01-01"
    for s in (ins, oos):
        assert np.isfinite(s["cagr"]) and -1.0 <= s["mdd"] <= 0.0
    spy = {"cagr": 0.10}
    v = run_m5.judge(oos, ins, spy)
    assert v["verdict"] in {"alive", "weak", "dead", "insufficient_sample"}
    wf = run_m5.walk_forward(run)
    assert "in_sample" in wf
