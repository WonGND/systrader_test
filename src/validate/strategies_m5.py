# -*- coding: utf-8 -*-
"""M5 judgment set = the Track A builders from M4, plus C13 (Track B, ported).

C13 is excluded from M4 (its reported numbers are KRX/KRW and cannot be
reproduced from a USD port) but IS judged out-of-sample, per CLAUDE.md §3:
"Track B `ported`: 국내 대상이나 로직이 자산군 독립적 → M5 OOS만".

Everything else — costs, execution convention, in-sample boundary — is shared
with M4 by importing the same builders, so nothing about the strategies changes
between the two windows (that is the point of an OOS test).
"""

from __future__ import annotations

import pandas as pd

from src.backtest import indicators as ind
from src.backtest.engine import run_backtest
from src.validate.strategies_m4 import (ALL_TICKERS as TRACK_A_TICKERS,
                                        BUILDERS as TRACK_A_BUILDERS,
                                        StrategyPlan)

C13_SPEC = "c13-modified-paa-31-ported"
C13_RISK = ["SPY", "EFA"]      # 원문 1단계 국가 지수 예시의 화이트리스트 매핑
C13_SAFE = "IEF"               # 10년 국고채
C13_CASH = "SHY"               # 3년 국고채 = 현금


def _c13_equity_gate(close: pd.DataFrame, open_: pd.DataFrame,
                     targets: pd.DataFrame) -> pd.Series:
    """6-month momentum of the strategy's OWN equity curve (step 5).

    The ungated strategy is run cost-free through the same engine, its equity is
    sampled at month end, and the gate at month end t compares equity_t against
    equity_{t-6}. Only past equity enters the comparison, and the gated position
    is executed at the next open like every other signal, so no look-ahead.
    Cost-free on purpose: the gate must not depend on our slippage assumption.
    """
    res = run_backtest(close, open_, targets, execution="next_open")
    m = ind.monthly_closes(res.equity.to_frame("eq"))["eq"]
    gate = (m / m.shift(6) > 1.0)
    return gate.where(m.shift(6).notna())


def _c13(ohlc: dict, score_safe: bool, key: str, label: str) -> StrategyPlan:
    tickers = C13_RISK + [C13_SAFE, C13_CASH]
    close = pd.DataFrame({t: ohlc[t]["Close"] for t in tickers}).dropna()
    open_ = pd.DataFrame({t: ohlc[t]["Open"] for t in tickers}).loc[close.index]

    m = ind.monthly_closes(close)
    rel = ind.avg_momentum_return(m[C13_RISK], range(1, 13))   # 2단계 상대 모멘텀
    score = ind.avg_momentum_score(m, range(1, 13))            # 3단계 절대 모멘텀

    # 룩백이 모두 확보된 월만 신호를 낸다 (부족분은 NaN 유지 — 무보간)
    ready = rel.dropna(how="any").index.intersection(score.dropna(how="any").index)
    winner = rel.loc[ready].idxmax(axis=1)                     # 상위 1/2 (비율 유지)

    weights = pd.DataFrame(0.0, index=ready, columns=tickers)
    for dt, w in winner.items():
        weights.loc[dt, w] = 0.5 * score.loc[dt, w]            # 4단계 위험:안전 1:1
        weights.loc[dt, C13_SAFE] = 0.5 * (score.loc[dt, C13_SAFE] if score_safe else 1.0)
    # 잔여분은 유니버스의 현금 자산으로 (M4에서 확정한 원문 (72) 예시 산식)
    weights[C13_CASH] = weights[C13_CASH] + (1.0 - weights.sum(axis=1))

    gate = _c13_equity_gate(close, open_, weights)              # 5단계 수익곡선 모멘텀
    on = gate.reindex(weights.index)
    gated = weights.loc[on.notna()].copy()                     # 게이트 미정의 구간 제외
    off_dates = gated.index[~on.loc[gated.index].astype(bool)]
    gated.loc[off_dates, :] = 0.0                              # 하락 시 전액 현금화
    gated.loc[off_dates, C13_CASH] = 1.0

    return StrategyPlan(
        key=key, spec_id=C13_SPEC,
        name=f"Modified PAA (31) 이식판{label}",
        tickers=tickers, mode="portfolio", execution="next_open", targets=gated,
        notes=[
            "이식 설계(M2 승인): S&P500/KOSPI200→SPY, Nikkei/Eurostoxx→EFA, "
            "10년 국고채→IEF, 3년 국고채(현금)→SHY. 국내 섹터·팩터는 화이트리스트 밖이라 제외",
            "2단계 상대 모멘텀: 1~12개월 평균 모멘텀 상위 1/2 (원문 6/19≈30% 비율 유지 — 가정값)",
            "3단계 절대 모멘텀: 12개월 평균 모멘텀 스코어 x 자산군 비중, 잔여분은 현금 자산 SHY",
            ("4단계 안전자산군도 스코어 스케일 적용 (대조판 — 원문 미명시)" if score_safe
             else "4단계 위험:안전 1:1, 안전자산군은 고정 50% (원문 3단계는 '선정된 종목' 대상)"),
            "5단계 6개월 수익곡선 모멘텀: 자기 수익곡선이 6개월 전 대비 하락이면 전액 SHY (현금화)",
            "체결 시점 원문 미명시 → 엔진 기본 익일 시가 (가정값)",
            "원문 수치(MPAA1 8%/-5%, MPAA2 9%/-6%)는 국내·원화 기준 — 이식판과 대조 불가",
        ])


def build_c13(ohlc: dict) -> StrategyPlan:
    return _c13(ohlc, score_safe=False, key="c13", label="")


def build_c13_score_safe(ohlc: dict) -> StrategyPlan:
    """Contrast: the momentum-score mix applied to the safe class as well.
    The post's step 3 says '선정된 종목' (the relative-momentum winners), so this
    reading is not the primary one — it is here to show what the ambiguity costs.
    """
    return _c13(ohlc, score_safe=True, key="c13_score_safe", label=" (안전자산군 스코어 적용 대조판)")


BUILDERS = list(TRACK_A_BUILDERS) + [build_c13, build_c13_score_safe]

ALL_TICKERS = sorted(set(TRACK_A_TICKERS) | set(C13_RISK) | {C13_SAFE, C13_CASH})
