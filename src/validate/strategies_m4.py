# -*- coding: utf-8 -*-
"""Track A strategy implementations for M4 in-sample reproduction.

Each builder translates one approved spec (data/specs/c*.json) into target
weights. Rules come only from fields the spec backs with a source quote;
anything the post left unspecified uses the engine/project default and is
listed in `notes` so the report can label it an assumption.

Two execution modes are produced:
- "portfolio": one target-weight vector per signal date (asset-allocation
  strategies). The engine rebalances the whole book.
- "sleeves": independent single-asset sub-strategies whose equity curves are
  averaged. The source posts for C4/C5/C7 combine sub-strategies exactly this
  way (`a.mean(axis=1)` in their code), i.e. capital is split once at the
  start and sleeves are never rebalanced against each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.backtest import indicators as ind


@dataclass
class StrategyPlan:
    key: str
    spec_id: str
    name: str
    tickers: list
    mode: str                       # "portfolio" | "sleeves"
    execution: str                  # "next_open" | "close"
    targets: pd.DataFrame | None = None
    sleeves: list = field(default_factory=list)   # [(label, ticker, targets)]
    notes: list = field(default_factory=list)
    alt_execution: str | None = None             # sensitivity run, if relevant
    warmup_days: int = 0                         # trading days of indicator warmup


def _changes_only(pos: pd.Series, ticker: str) -> pd.DataFrame:
    """Emit a target row only when the desired position changes."""
    keep = pos.ne(pos.shift())
    keep.iloc[0] = True
    return pd.DataFrame({ticker: pos[keep]})


# --------------------------------------------------------------------------
# C1 — 자산군 비중 배분 x 평균 모멘텀 스코어 (14)(17)
# --------------------------------------------------------------------------
def build_c01(ohlc: dict) -> StrategyPlan:
    # residual goes into the universe's cash asset (SHY), per the method's own
    # worked example in post (72): "남는 비중은 현금으로 대치 (현금 비중에 추가)"
    return _c01(ohlc, with_cash_class=True, residual_to="SHY")


def build_c01_zero_cash(ohlc: dict) -> StrategyPlan:
    """Same rules but the unallocated weight sits in 0%-yield cash — kept as a
    contrast so the effect of the residual convention is visible."""
    return _c01(ohlc, with_cash_class=True, residual_to=None)


def build_c01_stock_bond(ohlc: dict) -> StrategyPlan:
    """The post reports CAGR 9% / MDD -8.52% for the CASH-EXCLUDED variant
    ("주식:채권만으로 구성된 모멘텀 포트폴리오"), so that configuration is the
    one those two numbers can actually be compared against."""
    return _c01(ohlc, with_cash_class=False)


def _c01(ohlc: dict, with_cash_class: bool, residual_to: str | None = None) -> StrategyPlan:
    classes = {"equity": ["SPY", "EFA", "EEM"], "bond": ["IEF", "TLT"], "cash": ["SHY"]}
    if not with_cash_class:
        classes.pop("cash")
    tickers = [t for v in classes.values() for t in v]
    close = pd.DataFrame({t: ohlc[t]["Close"] for t in tickers})
    m = ind.monthly_closes(close)
    score = ind.avg_momentum_score(m, range(1, 13))

    weights = pd.DataFrame(index=m.index, columns=tickers, dtype=float)
    for members in classes.values():
        base = (1.0 / len(classes)) / len(members)
        for t in members:
            weights[t] = base * score[t]
    if residual_to:
        weights[residual_to] = weights[residual_to] + (1.0 - weights.sum(axis=1))
    targets = weights.dropna(how="any")
    n = len(classes)
    return StrategyPlan(
        key="c01" if with_cash_class else "c01_stock_bond",
        spec_id="c01-avg-momentum-score-allocation-14-17",
        name=("자산군 비중 배분 x 평균 모멘텀 스코어 (14)(17)" if with_cash_class
              else "자산군 배분 x 평균 모멘텀 스코어 — 현금군 제외판 (원문 9%/-8.52% 대조용)"),
        tickers=tickers, mode="portfolio", execution="next_open", targets=targets,
        notes=[f"자산군 배분 {':'.join(['1']*n)}, 종목 비중 = (1/{n})/자산군내 종목수 x 12개월 평균 모멘텀 스코어",
               (f"미배분 잔여분을 현금 자산 {residual_to}에 가산 (원문 (72) 예시 산식 그대로)"
                if residual_to else "미배분 잔여분은 수익률 0% 현금 (현금 자산 없는 구성)"),
               "체결 시점 원문 미명시 → 엔진 기본값 익일 시가 (가정값)"])


# --------------------------------------------------------------------------
# C2 — 동적 영구 / 올웨더 포트폴리오 (72)
# --------------------------------------------------------------------------
def _c02(ohlc: dict, base: dict, key: str, label: str,
         residual_to: str | None = None) -> StrategyPlan:
    tickers = list(base)
    close = pd.DataFrame({t: ohlc[t]["Close"] for t in tickers})
    m = ind.monthly_closes(close)
    score = ind.avg_momentum_score(m, range(1, 13))
    weights = pd.DataFrame({t: base[t] * score[t] for t in tickers})
    if residual_to:
        weights[residual_to] = weights[residual_to] + (1.0 - weights.sum(axis=1))
    targets = weights.dropna(how="any")
    return StrategyPlan(
        key=key, spec_id="c02-dynamic-permanent-allweather-72",
        name=f"동적 {label} 포트폴리오 (72)",
        tickers=tickers, mode="portfolio", execution="next_open", targets=targets,
        notes=[f"기본 배분 {base} x 12개월 평균 모멘텀 스코어",
               (f"잔여 비중을 현금 자산 {residual_to}에 가산 — 원문 예시: 스코어 0.7/0.5/0.2/1 → "
                "17.5/12.5/5/25(합 60%), 남는 40%를 현금에 더해 최종 17.5/12.5/5/65"
                if residual_to else
                "유니버스에 '현금' 자산이 없어 잔여 비중은 수익률 0% 현금 (원문 미명시 — 가정값)"),
               "원문은 '다음날 마감 동시호가 종가' 체결을 언급 → 엔진 기본 익일 시가로 대체(가정값)"])


def build_c02_permanent(ohlc):
    # the post's universe labels AGG as the 현금 line, and its worked example
    # adds the unallocated weight to that line
    return _c02(ohlc, {"SPY": .25, "TLT": .25, "GLD": .25, "AGG": .25},
                "c02_permanent", "영구", residual_to="AGG")


def build_c02_permanent_zero_cash(ohlc):
    return _c02(ohlc, {"SPY": .25, "TLT": .25, "GLD": .25, "AGG": .25},
                "c02_permanent_zero_cash", "영구(잔여=0% 현금 대조판)")


def build_c02_allweather(ohlc):
    return _c02(ohlc, {"SPY": .30, "IEF": .15, "TLT": .40, "GLD": .075, "DBC": .075},
                "c02_allweather", "올웨더")


# --------------------------------------------------------------------------
# C3 — Accelerating dual momentum (60)
# --------------------------------------------------------------------------
def build_c03(ohlc: dict) -> StrategyPlan:
    risky, safe = ["SPY", "SCZ"], ["TLT", "TIP"]
    tickers = risky + safe
    close = pd.DataFrame({t: ohlc[t]["Close"] for t in tickers})
    m = ind.monthly_closes(close)
    mom = ind.avg_momentum_return(m[risky], [1, 3, 6])
    one_month = (m[safe] / m[safe].shift(1) - 1.0)

    rows = {}
    for dt in m.index:
        mr, ms = mom.loc[dt], one_month.loc[dt]
        if mr.isna().any() or ms.isna().any():
            continue
        w = {t: 0.0 for t in tickers}
        winner = mr.idxmax()
        if mr[winner] > 0:
            w[winner] = 1.0
        else:
            w[ms.idxmax()] = 1.0
        rows[dt] = w
    targets = pd.DataFrame.from_dict(rows, orient="index")[tickers]
    return StrategyPlan(
        key="c03", spec_id="c03-accelerating-dual-momentum-60",
        name="Accelerating dual momentum (60)",
        tickers=tickers, mode="portfolio", execution="next_open", targets=targets,
        notes=["SPY/SCZ 1·3·6개월 수익률 평균의 승자, 평균 모멘텀>0이면 매수",
               "음수면 TLT/TIP 중 최근 1개월 수익률 상위 자산 100%",
               "'월말 매수'의 정확한 체결 시점 원문 미명시 → 익일 시가 (가정값)",
               "SCZ 상장 2007-12 → 백테스트 시작일이 그 이후로 늦춰짐"])


# --------------------------------------------------------------------------
# C4 — 역추세 전략 RSI(2) system (39)
# --------------------------------------------------------------------------
def build_c04(ohlc: dict, rsi_threshold: float = 20.0) -> StrategyPlan:
    tickers = ["SPY", "EFA", "IWD", "IWF", "IJH", "IWM", "EWJ"]
    long_periods = [90, 120, 150, 180, 200]
    sleeves = []
    for t in tickers:
        c = ohlc[t]["Close"]
        rsi2 = ind.wilder_rsi(c, 2)
        sma5 = ind.sma(c, 5)
        for p in long_periods:
            buy = (c > ind.sma(c, p)) & (rsi2 < rsi_threshold) & (c < sma5)
            sell = c > sma5.shift(1)
            pos = ind.state_machine(buy, sell)
            sleeves.append((f"{t}/{p}", t, _changes_only(pos, t)))
    return StrategyPlan(
        key="c04", spec_id="c04-rsi2-counter-trend-39",
        name="역추세 전략 RSI(2) system (39)",
        tickers=tickers, mode="sleeves", execution="next_open",
        alt_execution="close", sleeves=sleeves, warmup_days=200,
        notes=[f"매수: 종가>장기이평(90/120/150/180/200) & RSI(2)<{rsi_threshold:g} & 종가<5일이평",
               "매도: 종가 > 전일 5일이평 (원문 코드 shift(1) 그대로)",
               "RSI 역치 20 = 원문 시뮬레이션값(원판 규칙은 5)",
               f"{len(tickers)}종목 x {len(long_periods)}기간 = {len(sleeves)}개 슬리브 균등 분산, 슬리브 간 리밸런싱 없음",
               "원문 코드는 당일 종가 체결 구조 → alt로 close 체결 민감도 병기"])


# --------------------------------------------------------------------------
# C5 — 단순 이평선 돌파 (35), multi-asset x multi-timeframe
# --------------------------------------------------------------------------
def build_c05(ohlc: dict) -> StrategyPlan:
    stocks = ["SPY", "EFA", "IWD", "IWF", "IJH", "IWM", "EWJ"]
    bonds = ["IEF", "TLT", "LQD", "IEF", "TLT", "LQD", "IEF"]   # 원문 코드 그대로(중복 포함)
    cash = ["SHY"]
    entries = stocks + bonds + cash
    periods = [20, 60, 90, 120, 200]
    sleeves = []
    for i, t in enumerate(entries):
        c = ohlc[t]["Close"]
        for p in periods:
            pos = (c > ind.sma(c, p)).astype(float).where(ind.sma(c, p).notna())
            pos = pos.ffill().fillna(0.0)
            sleeves.append((f"{i}:{t}/{p}", t, _changes_only(pos, t)))
    return StrategyPlan(
        key="c05", spec_id="c05-multi-ma-breakout-35",
        name="단순 이평선 돌파 (35) — 멀티에셋 x 멀티프레임",
        tickers=sorted(set(entries)), mode="sleeves", execution="next_open",
        alt_execution="close", sleeves=sleeves, warmup_days=200,
        notes=["종가 > n일 이평이면 보유, 아래면 현금 (n = 20/60/90/120/200)",
               "원문 코드의 채권 리스트 중복(IEF,TLT,LQD,IEF,TLT,LQD,IEF)을 그대로 사용 → 주식:채권 1:1",
               f"{len(entries)}개 엔트리 x {len(periods)}기간 = {len(sleeves)}개 슬리브 균등, 슬리브 간 리밸런싱 없음",
               "원문 코드는 당일 종가 체결 구조 → alt로 close 체결 민감도 병기"])


# --------------------------------------------------------------------------
# C6 — Hybrid asset allocation (136)
# --------------------------------------------------------------------------
def build_c06(ohlc: dict) -> StrategyPlan:
    offensive = ["SPY", "IWM", "EFA", "EEM", "VNQ", "DBC", "IEF", "TLT"]
    defensive = ["BIL", "IEF"]
    canary = "TIP"
    tickers = sorted(set(offensive + defensive + [canary]))
    close = pd.DataFrame({t: ohlc[t]["Close"] for t in tickers})
    m = ind.monthly_closes(close)
    mom = ind.avg_momentum_return(m, [1, 3, 6, 12])

    rows = {}
    for dt in m.index:
        mo = mom.loc[dt]
        if mo[offensive + defensive + [canary]].isna().any():
            continue
        w = {t: 0.0 for t in tickers}
        best_def = mo[defensive].idxmax()
        if mo[canary] <= 0:
            w[best_def] = 1.0
        else:
            top4 = mo[offensive].nlargest(4).index
            for t in top4:
                pick = t if mo[t] > 0 else best_def
                w[pick] += 0.25
        rows[dt] = w
    targets = pd.DataFrame.from_dict(rows, orient="index")[tickers]
    return StrategyPlan(
        key="c06", spec_id="c06-hybrid-asset-allocation-136",
        name="Hybrid asset allocation (136)",
        tickers=tickers, mode="portfolio", execution="next_open", targets=targets,
        notes=["카나리아 TIP 모멘텀<=0 → 방어자산(BIL/IEF) 중 모멘텀 상위 100%",
               "그 외 공격형 상위 4개 동일비중(25%), 개별 모멘텀<=0이면 방어자산으로 대체",
               "모멘텀 = 1·3·6·12개월 수익률의 평균 (Keller HAA 정의). 원문 표현은 "
               "'평균 모멘텀 스코어'이나 '0 이하' 비교가 성립하는 해석을 채택 — 가정값",
               "공격형 8자산은 원문 비인용(Q7 사용자 승인, Keller 원논문 유니버스)",
               "BIL 상장 2007-05, DBC 2006-02 → 시작일 지연"])


# --------------------------------------------------------------------------
# C7 — 주중/월말 계절성 절대 수익 전략 (115)
# --------------------------------------------------------------------------
def build_c07(ohlc: dict) -> StrategyPlan:
    spy, tlt = ohlc["SPY"], ohlc["TLT"]
    sc, tc = spy["Close"], tlt["Close"]

    is_month_end = pd.Series(False, index=sc.index)
    is_month_end.loc[ind.month_end_dates(sc.index)] = True
    spy_buy = is_month_end & (sc > ind.sma(sc, 200))
    spy_sell = sc > spy["High"].shift(1)
    spy_pos = ind.state_machine(spy_buy, spy_sell)

    is_thu = pd.Series(tc.index.dayofweek == 3, index=tc.index)
    tlt_buy = is_thu & (tc < ind.sma(tc, 5))
    tlt_sell = tc > tlt["High"].shift(1)
    tlt_pos = ind.state_machine(tlt_buy, tlt_sell)

    return StrategyPlan(
        key="c07", spec_id="c07-weekday-monthend-seasonality-115",
        name="주중·월말 계절성 절대 수익 전략 (115)",
        tickers=["SPY", "TLT"], mode="sleeves", execution="close",
        sleeves=[("SPY/월말", "SPY", _changes_only(spy_pos, "SPY")),
                 ("TLT/목요일", "TLT", _changes_only(tlt_pos, "TLT"))],
        warmup_days=200,
        notes=["SPY: 월말 종가 > 200일 이평 → 월말 종가 매수",
               "TLT: 목요일 종가 < 5일 이평 → 목요일 종가 매수",
               "매도: 당일 종가 > 전일 고가 → 종가 매도 (원문 명시)",
               "체결 = 당일 종가 (원문 명시)",
               "Q8 승인: 두 슬리브에 자본 50:50 최초 분할, 슬리브 간 리밸런싱 없음 — 가정값"])


# --------------------------------------------------------------------------
# C8 — 나스닥/국채 스프레드 역추세
# --------------------------------------------------------------------------
def build_c08(ohlc: dict) -> StrategyPlan:
    tickers = ["QQQ", "TLT"]
    q, t = ohlc["QQQ"]["Close"], ohlc["TLT"]["Close"]
    spread = q / t
    rsi3 = ind.wilder_rsi(spread, 3)
    pos_q = ind.state_machine(rsi3 < 15, rsi3 > 70)
    pos_t = ind.state_machine(rsi3 > 85, rsi3 < 30)
    w = pd.DataFrame({"QQQ": pos_q, "TLT": pos_t}).fillna(0.0)
    over = w.sum(axis=1) > 1.0
    w.loc[over] = w.loc[over].div(w.loc[over].sum(axis=1), axis=0)  # safety, should not trigger
    keep = (w != w.shift()).any(axis=1)
    keep.iloc[0] = True
    return StrategyPlan(
        key="c08", spec_id="c08-qqq-tlt-spread-rsi3",
        name="나스닥·국채 스프레드 역추세 (원판)",
        tickers=tickers, mode="portfolio", execution="next_open",
        targets=w[keep], warmup_days=10,
        notes=["스프레드 = QQQ/TLT 가격 비율, 3일 RSI(Wilder)",
               "RSI<15 → QQQ 매수 / RSI>70 → QQQ 청산",
               "RSI>85 → TLT 매수 / RSI<30 → TLT 청산",
               "레버리지 개선판(QLD/UBT)은 화이트리스트 금지군이라 원판만 재현",
               "포지션 크기 원문 미명시 → 신호 자산 100% (가정값)",
               "체결 시점 원문 미명시 → 익일 시가 (가정값)"])


# --------------------------------------------------------------------------
# C9 — IBS·하한선 역추세 (원판, 단일 ETF)
# --------------------------------------------------------------------------
def _c09(ohlc: dict, ticker: str, gate_entry: bool = False) -> StrategyPlan:
    df = ohlc[ticker]
    h, l, c = df["High"], df["Low"], df["Close"]
    range_ma = (h - l).rolling(25).mean()
    lower = h.rolling(10).mean() - 2.5 * range_ma
    ibs = (c - l) / (h - l).replace(0, np.nan)
    above300 = c > ind.sma(c, 300)
    buy = (c < lower) & (ibs < 0.3)
    if gate_entry:
        buy = buy & above300
    sell = (c > h.shift(1)) | ~above300
    pos = ind.state_machine(buy, sell)
    return StrategyPlan(
        key=f"c09_{ticker.lower()}" + ("_gated" if gate_entry else ""),
        spec_id="c09-ibs-lower-band-mean-reversion",
        name=f"IBS·하한선 역추세 (원판, {ticker})" + (" — 300일선 진입필터판" if gate_entry else ""),
        tickers=[ticker], mode="portfolio", execution="next_open",
        targets=_changes_only(pos, ticker), warmup_days=300,
        notes=["하한선 = 10일 고가 이동평균 - 2.5 x 25일 (고가-저가) 이동평균",
               "IBS = (종가-저가)/(고가-저가), 매수: 종가<하한선 & IBS<0.3",
               "청산: 종가 > 전일 고가, 또는 종가 < 300일 이평",
               "개별주 확장판은 point-in-time 구성종목 부재로 생존편향 제거 불가 → 원판만",
               "포지션 크기·체결 시점 원문 미명시 → 100% / 익일 시가 (가정값)",
               ("300일선을 진입 필터로도 적용(가정값) — 원문은 청산 조건으로만 서술"
                if gate_entry else
                "300일선은 원문대로 청산 조건으로만 적용 → 하락추세 중 진입이 가능")])


def build_c09_spy(ohlc):
    return _c09(ohlc, "SPY")


def build_c09_qqq(ohlc):
    return _c09(ohlc, "QQQ")


def build_c09_qqq_gated(ohlc):
    return _c09(ohlc, "QQQ", gate_entry=True)


BUILDERS = [
    build_c01, build_c01_zero_cash, build_c01_stock_bond,
    build_c02_permanent, build_c02_permanent_zero_cash, build_c02_allweather,
    build_c03, build_c04, build_c05, build_c06, build_c07, build_c08,
    build_c09_spy, build_c09_qqq, build_c09_qqq_gated,
]

ALL_TICKERS = sorted({
    "SPY", "EFA", "EEM", "IEF", "TLT", "SHY", "GLD", "AGG", "DBC", "SCZ",
    "TIP", "IWD", "IWF", "IJH", "IWM", "EWJ", "LQD", "VNQ", "BIL", "QQQ",
})
