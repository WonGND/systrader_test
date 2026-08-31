# -*- coding: utf-8 -*-
"""M4 in-sample reproduction runner (run LOCALLY — needs yfinance).

Scope: Track A only (9 approved strategies, 11 runs incl. variants).
C13 (ported) is excluded by design — see the printed note.

In-sample window: data start (per strategy, after listing + warmup) .. 2018-12-31
Costs: engine defaults from config/backtest_defaults.yaml, and a cost-free run
       for comparison against the posts (which mostly ignore costs).

Usage (PowerShell, repo root, venv active):
  python -m src.validate.run_m4
  python -m src.validate.run_m4 --json reports/m4_results.json
Paste the full output back into the Claude session.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backtest import data, metrics, settings  # noqa: E402
from src.backtest.engine import run_backtest  # noqa: E402
from src.validate import strategies_m4 as S  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
IN_SAMPLE_END = "2018-12-31"
FETCH_START = "2000-01-01"
FETCH_END = "2019-01-10"


def _slice_window(plan, open_, close):
    """Restrict to dates where every ticker is listed and warmup is done."""
    starts = [close[t].dropna().index[0] for t in plan.tickers]
    start = max(starts)
    idx = close.loc[start:].index
    if plan.warmup_days:
        if len(idx) <= plan.warmup_days:
            raise ValueError(f"{plan.key}: not enough history for warmup")
        start = idx[plan.warmup_days]
    if plan.mode == "portfolio" and plan.targets is not None and len(plan.targets):
        start = max(start, plan.targets.index[0])
    o = open_.loc[start:IN_SAMPLE_END]
    c = close.loc[start:IN_SAMPLE_END]
    return o, c


def _run_plan(plan, open_, close, commission, slippage, execution=None):
    execution = execution or plan.execution
    o, c = _slice_window(plan, open_, close)
    if len(c) < 60:
        raise ValueError(f"{plan.key}: window too short ({len(c)} days)")

    if plan.mode == "portfolio":
        tg = plan.targets.reindex(columns=[t for t in plan.targets.columns])
        tg = tg.loc[tg.index.intersection(c.index)]
        res = run_backtest(c[plan.targets.columns], o[plan.targets.columns], tg,
                           execution=execution, commission=commission,
                           slippage=slippage)
        summ = res.summary()
        summ.update(metrics.monthly_summary(res.equity))
        summ["warnings"] = len(res.warnings)
        summ["start"] = str(c.index[0].date())
        summ["end"] = str(c.index[-1].date())
        return summ

    # sleeves: run each independently, then average the equity curves
    eqs, turns, exps = [], [], []
    warn = 0
    for _label, ticker, tg in plan.sleeves:
        tg1 = tg.loc[tg.index.intersection(c.index)]
        if tg1.empty:
            continue
        r = run_backtest(c[[ticker]], o[[ticker]], tg1, execution=execution,
                         commission=commission, slippage=slippage)
        eqs.append(r.equity)
        turns.append(r.turnover)
        exps.append(r.exposure)
        warn += len(r.warnings)
    equity = pd.concat(eqs, axis=1).mean(axis=1)
    turnover = pd.concat(turns, axis=1).mean(axis=1)
    exposure = pd.concat(exps, axis=1).mean(axis=1)
    returns = equity.pct_change().fillna(0.0)
    trade_days = int((turnover > 1e-12).sum())
    summ = metrics.summary(equity, returns, exposure, turnover, trade_days)
    summ.update(metrics.monthly_summary(equity))
    summ["costs_paid"] = float("nan")
    summ["warnings"] = warn
    summ["start"] = str(c.index[0].date())
    summ["end"] = str(c.index[-1].date())
    summ["sleeves"] = len(eqs)
    return summ


def _spy_same_window(plan, open_, close):
    """SPY buy&hold over this strategy's exact window — isolates period effects
    from logic differences when comparing against a post's numbers."""
    from src.backtest import strategies_basic as sb
    o, c = _slice_window(plan, open_, close)
    res = run_backtest(c[["SPY"]], o[["SPY"]], sb.buy_and_hold(c.index, "SPY"))
    s = res.summary()
    s.update(metrics.monthly_summary(res.equity))
    return s


def _reported(spec_id: str) -> dict:
    p = REPO / "data" / "specs" / f"{spec_id}.json"
    if not p.exists():
        return {}
    spec = json.load(open(p, encoding="utf-8"))
    rp = spec.get("reported_performance", {})
    out = {"evidence_type": rp.get("evidence_type")}
    for k in ("cagr", "mdd", "other_metrics"):
        if k in rp and isinstance(rp[k], dict):
            out[k] = rp[k].get("value")
    return out


def _fmt(s: dict) -> str:
    return (f"CAGR {s['cagr']*100:7.2f}% | MDD {s['mdd']*100:8.2f}% | "
            f"Sharpe {s['sharpe']:5.2f} | 승률 {s['win_rate']*100:5.1f}% | "
            f"거래일 {s['trade_days']:5d} | 연회전 {s['turnover_annual_oneway']:5.2f}")


def _fmt_m(s: dict) -> str:
    return (f"CAGR {s['cagr_m']*100:7.2f}% | MDD {s['mdd_m']*100:8.2f}% | "
            f"Sharpe {s['sharpe_m']:5.2f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None, help="also write results to this JSON path")
    args = ap.parse_args()
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    comm, slip = settings.costs()
    print("=" * 84)
    print(f"M4 인샘플 재현 | 종료일 {IN_SAMPLE_END} | yfinance auto_adjust=True")
    print(f"비용: 무비용(원문 대조용) / 비용반영(수수료 {comm*100:.2f}%, 편도 슬리피지 {slip*100:.2f}%)")
    print(f"대상: Track A 9개 전략 (변형 포함 {len(S.BUILDERS)}개 런). "
          "C13(ported)은 이식 전략이라 M4 제외.")
    print("=" * 84)

    print(f"\n[데이터] {len(S.ALL_TICKERS)}개 티커 로드 중 ({FETCH_START}~{FETCH_END}) ...")
    open_, close = data.load_universe(S.ALL_TICKERS, FETCH_START, FETCH_END)
    print(f"  거래일 {len(close)} | 티커별 데이터 시작일:")
    starts = [f"{t}:{close[t].dropna().index[0].date()}" for t in S.ALL_TICKERS]
    for i in range(0, len(starts), 4):
        print("    " + "  ".join(f"{x:22s}" for x in starts[i:i + 4]).rstrip())

    ohlc = {t: data.fetch_ohlc(t, FETCH_START, FETCH_END) for t in S.ALL_TICKERS}

    results = {}
    for builder in S.BUILDERS:
        plan = builder(ohlc)
        print("\n" + "-" * 84)
        print(f"[{plan.key}] {plan.name}")
        print(f"  spec: {plan.spec_id} | 유니버스: {','.join(plan.tickers)}")
        try:
            free = _run_plan(plan, open_, close, 0.0, 0.0)
            paid = _run_plan(plan, open_, close, comm, slip)
        except Exception as exc:
            print(f"  [ERROR] {type(exc).__name__}: {exc}")
            continue
        print(f"  기간: {free['start']} ~ {free['end']}"
              + (f" | 슬리브 {free['sleeves']}개" if "sleeves" in free else ""))
        print(f"  무비용(일간) : {_fmt(free)}")
        print(f"  무비용(월간) : {_fmt_m(free)}   <- 원문이 R/월간 산출이면 이 줄과 비교")
        print(f"  비용반영(일간): {_fmt(paid)}")
        try:
            spy = _spy_same_window(plan, open_, close)
            print(f"  동일구간 SPY : {_fmt(spy)}")
            print(f"  동일구간 SPY(월간): {_fmt_m(spy)}")
            free["spy_same_window"] = {k: spy[k] for k in
                                       ("cagr", "mdd", "sharpe", "cagr_m", "mdd_m", "sharpe_m")}
        except Exception as exc:
            print(f"  [SPY 대조 ERROR] {exc}")
        if plan.alt_execution:
            try:
                alt = _run_plan(plan, open_, close, 0.0, 0.0, execution=plan.alt_execution)
                print(f"  [민감도] 체결={plan.alt_execution} 무비용: {_fmt(alt)}")
                free["alt_execution"] = plan.alt_execution
                free["alt"] = {k: alt[k] for k in ("cagr", "mdd", "sharpe")}
            except Exception as exc:
                print(f"  [민감도 ERROR] {exc}")
        rep = _reported(plan.spec_id)
        if rep:
            print(f"  원문 주장: {rep}")
        if free.get("warnings"):
            print(f"  경고 {free['warnings']}건 (가격 결측 등)")
        for n in plan.notes:
            print(f"    · {n}")
        yr = {k: round(v * 100, 1) for k, v in sorted(free["yearly_returns"].items())}
        print(f"  연도별(무비용, %): {yr}")
        results[plan.key] = {"name": plan.name, "spec_id": plan.spec_id,
                             "free": free, "paid": paid, "reported": rep,
                             "notes": plan.notes}

    # benchmark over the same in-sample boundary, for context only
    from src.backtest import strategies_basic as sb
    o = open_.loc[:IN_SAMPLE_END]
    c = close.loc[:IN_SAMPLE_END]
    bh = run_backtest(c[["SPY"]], o[["SPY"]], sb.buy_and_hold(c.index, "SPY"))
    print("\n" + "=" * 84)
    print(f"[참고] SPY Buy&Hold {c.index[0].date()}~{c.index[-1].date()} (무비용): {_fmt(bh.summary())}")
    print("       각 전략은 시작일이 달라 이 벤치마크와 직접 비교 불가 — M5에서 구간 정렬 후 판정")
    print("=" * 84)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1, default=str)
        print(f"\n[saved] {args.json}")
    print("\n>>> 위 출력 전체를 Claude에게 전달해 주세요. <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())
