# -*- coding: utf-8 -*-
"""M6 batch set = the M5 judgment set, plus the two candidates added at the
M5 gate (Q15): C10 (Larry Connors RSI(2), 단순판) and C12 (Defense First).

C11/C14/C15 from the M2 shortlist are NOT here and will not be added:
- C11 상관관계 상품 모멘텀 — 숏 포지션이 전략 정체성. 엔진은 롱온리다.
- C14 비대칭 모멘텀 — 국내 섹터·팩터·레버리지·인버스 등 화이트리스트 밖 치환 다수.
- C15 마켓타이밍+변동성 조절 — 파라미터가 "코스닥 특성" 근거라 이식 시 정체성 훼손.
사유는 reports/M6_final_report.md와 docs/DECISIONS.md에 기록한다.

The builders for C10/C12 land here once their specs exist (data/specs/c10*.json,
c12*.json). Until then this module is the M5 set — no placeholder rules are
invented (CLAUDE.md §1-1).
"""

from __future__ import annotations

import pandas as pd

from src.backtest import indicators as ind
from src.validate.strategies_m4 import StrategyPlan, _changes_only
from src.validate.strategies_m5 import (ALL_TICKERS as M5_TICKERS,
                                        BUILDERS as M5_BUILDERS)


# --------------------------------------------------------------------------
# C10 — Larry Connors RSI(2), 단순판 (단일 ETF)
# --------------------------------------------------------------------------
def _c10(ohlc: dict, ticker: str) -> StrategyPlan:
    """종가>200MA & RSI(2)<5 → 익일 시가 매수.
    종가>전일 고가 또는 종가<200MA → 익일 시가 매도. 전부 원문 명시.

    Buy wins ties (indicators.state_machine): on a day that is both an exit and
    an entry the position is held rather than sold and re-bought at the same
    open — same exposure, without inventing a round trip the post never makes.
    """
    df = ohlc[ticker]
    close, high = df["Close"], df["High"]
    ma200 = ind.sma(close, 200)
    rsi2 = ind.wilder_rsi(close, 2)

    buy = (close > ma200) & (rsi2 < 5)
    sell = (close > high.shift(1)) | (close < ma200)
    pos = ind.state_machine(buy.fillna(False), sell.fillna(False))
    pos = pos.where(ma200.notna() & rsi2.notna(), 0.0)

    return StrategyPlan(
        key=f"c10_{ticker.lower()}", spec_id="c10-connors-rsi2-simple",
        name=f"Larry Connors RSI(2) 역추세 — 단순판 ({ticker})",
        tickers=[ticker], mode="portfolio", execution="next_open",
        targets=_changes_only(pos, ticker),
        notes=[
            "매수: 종가 > 200일 이평 & RSI(2) < 5 (원문 명시)",
            "매도: 종가 > 전일 고가, 또는 종가 < 200일 이평 (원문 명시)",
            "체결: 익일 시가 — 원문이 '다음 날 시가'로 명시",
            "포지션 크기 원문 미명시 → 신호 시 100% (가정값)",
            ("QQQ판은 200일선·RSI를 QQQ 자체 가격으로 계산 — 원문은 규칙을 "
             "S&P500 기준으로 서술했다(가정값)" if ticker != "SPY" else
             "원문 규칙 서술과 동일하게 SPY 자체 가격 기준"),
            "TQQQ 적용판은 화이트리스트 금지군(레버리지)이라 제외",
            "개별주 확장판(연 30.3%)은 point-in-time 구성종목 부재로 재현 대상 아님",
        ])


def build_c10_spy(ohlc):
    return _c10(ohlc, "SPY")


def build_c10_qqq(ohlc):
    return _c10(ohlc, "QQQ")


# --------------------------------------------------------------------------
# C12 — "Defense First" 방어자산 모멘텀 TAA
# --------------------------------------------------------------------------
C12_DEFENSIVE = ["TLT", "GLD", "PDBC", "UUP"]
C12_RISKY = "SPY"
C12_RF = "BIL"
C12_RANK_WEIGHTS = [0.40, 0.30, 0.20, 0.10]     # 1위 → 4위


def _c12(ohlc: dict, execution: str, key: str, label: str) -> StrategyPlan:
    tickers = C12_DEFENSIVE + [C12_RISKY, C12_RF]
    close = pd.DataFrame({t: ohlc[t]["Close"] for t in tickers}).dropna()
    m = ind.monthly_closes(close)
    mom = ind.avg_momentum_return(m, [1, 3, 6, 12])      # 1·3·6·12개월 평균
    ready = mom.dropna(how="any").index

    rows = {}
    for dt in ready:
        w = {t: 0.0 for t in tickers}
        order = mom.loc[dt, C12_DEFENSIVE].sort_values(ascending=False).index
        rf = mom.loc[dt, C12_RF]
        for rank, t in enumerate(order):
            base = C12_RANK_WEIGHTS[rank]
            if mom.loc[dt, t] < rf:          # 절대 모멘텀 미달 → SPY로 전환
                w[C12_RISKY] += base
            else:
                w[t] += base
        rows[dt] = w
    targets = pd.DataFrame.from_dict(rows, orient="index")[tickers]

    return StrategyPlan(
        key=key, spec_id="c12-defense-first-taa",
        name=f"Defense First 방어자산 모멘텀 TAA{label}",
        tickers=tickers, mode="portfolio", execution=execution, targets=targets,
        alt_execution="next_open" if execution == "close" else None,
        notes=[
            "모멘텀 = 1·3·6·12개월 수익률의 산술평균 (원문 명시)",
            "방어 4종 순위별 40/30/20/10% 배분 (원문 명시)",
            "방어자산 모멘텀 < BIL 기준이면 그 비중을 SPY로 전환 (원문 명시). "
            "BIL 기준값은 동일 산식으로 계산 — 원문이 산출 방식을 명시하지 않음(가정값)",
            "체결: 원문이 '매월 마지막 거래일에 월 1회 실행'이라 종가 체결을 본안으로, "
            "익일 시가를 민감도로 병기 (가정값)",
            "PDBC 상장 2014-02 → 인샘플이 약 4년으로 짧다. 판정 기준 (2)의 기준값 불안정",
            "원문 본문은 DBC/PDBC를 혼용하나 규칙 서술의 PDBC를 채택",
            "원문 개선안(주식 모멘텀 2차 필터, UUP→현금 대체)은 저자 제안이라 미적용",
            "원문 인용 비용 가정은 왕복 0.2%(편도 0.1%) — 본 프로젝트 기본값(편도 0.05%)의 2배",
        ])


def build_c12(ohlc):
    return _c12(ohlc, "close", "c12", "")


def build_c12_next_open(ohlc):
    """Same rules executed at the next open — the project default convention,
    kept as a contrast because the post only says 'executed on the last
    trading day' without naming a fill price."""
    return _c12(ohlc, "next_open", "c12_next_open", " (익일 시가 체결 대조판)")


PENDING_BUILDERS: list = [build_c10_spy, build_c10_qqq, build_c12, build_c12_next_open]
PENDING_TICKERS: set = {"SPY", "QQQ", *C12_DEFENSIVE, C12_RF}

BUILDERS = list(M5_BUILDERS) + PENDING_BUILDERS
ALL_TICKERS = sorted(set(M5_TICKERS) | PENDING_TICKERS)
