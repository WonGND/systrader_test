# -*- coding: utf-8 -*-
"""M5 out-of-sample validation runner (run LOCALLY — needs yfinance).

The question this milestone answers is CLAUDE.md §0's: is the strategy still
alive out of sample since 2019? Nothing about the strategies changes between
windows — the same builders, the same assumption values, the same costs.

Method
------
Each strategy is run ONCE over its full available history and the metrics are
then computed on two slices:
    in-sample  : first signal .. 2018-12-31
    OOS        : 2019-01-01   .. latest close
Running once (rather than restarting the engine in 2019) is what keeps a
position opened in 2018 alive across the boundary; restarting would flatten it
and manufacture a trade the strategy never made.

Verdict — CLAUDE.md §7 v1.0, on COST-APPLIED daily metrics (Q11: 일간 고정):
    (1) OOS Sharpe >= 0.5
    (2) |OOS MDD| <= |in-sample MDD| * 1.5
    (3) OOS CAGR >= SPY CAGR over the same window and same cost assumption
    3 met -> alive / 2 -> weak / <=1 -> dead
    fewer than 12 OOS rebalances -> insufficient_sample (판정 보류)

Usage (PowerShell, repo root, venv active):
  python -m src.validate.run_m5
  python -m src.validate.run_m5 --json reports/m5_results.json
Paste the full output back into the Claude session.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backtest import data, metrics, settings  # noqa: E402
from src.backtest.engine import run_backtest  # noqa: E402
from src.backtest import strategies_basic as sb  # noqa: E402
from src.validate import strategies_m5 as S  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
_CFG = settings.load()
IN_SAMPLE_END = pd.Timestamp(_CFG["periods"]["in_sample_end"])
OOS_START = pd.Timestamp(_CFG["periods"]["oos_start"])
# 판정 임계값도 config에서만 읽는다 (§5 하드코딩 금지, §7 v1.0)
_J = _CFG["judgment"]
CRITERIA_VERSION = str(_J["criteria_version"])
SHARPE_MIN = float(_J["oos_sharpe_min"])
MDD_MULT = float(_J["oos_mdd_max_vs_insample"])
MIN_OOS_REBALANCES = int(_J["min_oos_rebalances"])
FETCH_START = "2000-01-01"
WF_WINDOW_MONTHS = 36            # 워크포워드 롤링 창 (재적합 없음)


# --------------------------------------------------------------- run one plan
def _plan_window(plan, open_, close):
    """Full usable history for this plan: every ticker listed + warmup done."""
    start = max(close[t].dropna().index[0] for t in plan.tickers)
    idx = close.loc[start:].index
    if plan.warmup_days:
        if len(idx) <= plan.warmup_days:
            raise ValueError(f"{plan.key}: not enough history for warmup")
        start = idx[plan.warmup_days]
    if plan.mode == "portfolio" and plan.targets is not None and len(plan.targets):
        start = max(start, plan.targets.index[0])
    return open_.loc[start:], close.loc[start:]


def _run_full(plan, open_, close, commission, slippage):
    """One continuous run over the whole history; returns the raw series."""
    o, c = _plan_window(plan, open_, close)
    if len(c) < 60:
        raise ValueError(f"{plan.key}: window too short ({len(c)} days)")

    if plan.mode == "portfolio":
        cols = list(plan.targets.columns)
        tg = plan.targets.loc[plan.targets.index.intersection(c.index)]
        r = run_backtest(c[cols], o[cols], tg, execution=plan.execution,
                         commission=commission, slippage=slippage)
        return {"equity": r.equity, "returns": r.returns, "exposure": r.exposure,
                "turnover": r.turnover, "warnings": len(r.warnings), "sleeves": None}

    eqs, turns, exps = [], [], []
    warn = 0
    for _label, ticker, tg in plan.sleeves:
        tg1 = tg.loc[tg.index.intersection(c.index)]
        if tg1.empty:
            continue
        r = run_backtest(c[[ticker]], o[[ticker]], tg1, execution=plan.execution,
                         commission=commission, slippage=slippage)
        eqs.append(r.equity)
        turns.append(r.turnover)
        exps.append(r.exposure)
        warn += len(r.warnings)
    equity = pd.concat(eqs, axis=1).mean(axis=1)
    return {"equity": equity, "returns": equity.pct_change().fillna(0.0),
            "exposure": pd.concat(exps, axis=1).mean(axis=1),
            "turnover": pd.concat(turns, axis=1).mean(axis=1),
            "warnings": warn, "sleeves": len(eqs)}


def _slice(run: dict, start=None, end=None) -> dict | None:
    """Metrics on one window of an already-run equity curve.

    The equity series starts one bar BEFORE the window so the first day's return
    is measured against the last price outside it, and so drawdown is referenced
    to the window's opening value rather than to an all-time peak carried in.
    """
    eq, ret = run["equity"], run["returns"]
    idx = eq.index
    lo = idx[0] if start is None else start
    base = idx[idx < lo]
    eq_w = eq.loc[(base[-1] if len(base) else lo):end]
    ret_w = ret.loc[lo:end]
    if len(eq_w) < 30:
        return None
    exp_w = run["exposure"].loc[lo:end]
    to_w = run["turnover"].loc[lo:end]
    s = metrics.summary(eq_w, ret_w, exp_w, to_w, int((to_w > 1e-12).sum()))
    s.update(metrics.monthly_summary(eq_w))
    s["start"] = str(ret_w.index[0].date())       # first day INSIDE the window
    s["base_bar"] = str(eq_w.index[0].date())     # the bar its return is measured from
    s["end"] = str(ret_w.index[-1].date())
    s["rebalances"] = int((to_w > 1e-12).sum())
    return s


# ------------------------------------------------------------------- verdict
def judge(oos: dict, ins: dict, spy_oos: dict) -> dict:
    """CLAUDE.md §7 v1.0 on cost-applied daily metrics."""
    if oos["rebalances"] < MIN_OOS_REBALANCES:
        return {"verdict": "insufficient_sample", "met": None,
                "criteria": {}, "reason":
                f"OOS 리밸런싱 {oos['rebalances']}회 < {MIN_OOS_REBALANCES}회 — 판정 보류"}
    c1 = oos["sharpe"] >= SHARPE_MIN
    c2 = abs(oos["mdd"]) <= abs(ins["mdd"]) * MDD_MULT
    c3 = oos["cagr"] >= spy_oos["cagr"]
    met = int(c1) + int(c2) + int(c3)
    verdict = "alive" if met == 3 else ("weak" if met == 2 else "dead")
    return {"verdict": verdict, "met": met, "criteria_version": CRITERIA_VERSION,
            "criteria": {
                "sharpe_min": {"pass": bool(c1), "oos": oos["sharpe"], "min": SHARPE_MIN},
                "mdd_vs_in_sample": {"pass": bool(c2), "oos": oos["mdd"],
                                     "limit": -abs(ins["mdd"]) * MDD_MULT},
                "cagr_ge_spy": {"pass": bool(c3), "oos": oos["cagr"],
                                "spy": spy_oos["cagr"]},
            }, "reason": None}


def walk_forward(run: dict) -> dict:
    """Rolling-window stability, NOT re-optimization.

    No parameter in this project is fitted — every value comes from the source
    post — so a walk-forward re-fit would have nothing to re-fit. What is worth
    knowing is whether performance is carried by a few windows: rolling 36-month
    CAGR/Sharpe across the whole history, split at the OOS boundary.
    """
    eq = run["equity"]
    ends = pd.Series(eq.index, index=eq.index.to_period("M")).groupby(level=0).last()
    m = eq.loc[pd.DatetimeIndex(ends.values)]
    out = {}
    for tag, sl in (("in_sample", m.loc[:IN_SAMPLE_END]), ("oos", m.loc[OOS_START:])):
        rets = []
        for i in range(len(m) - WF_WINDOW_MONTHS):
            a, b = m.index[i], m.index[i + WF_WINDOW_MONTHS]
            if not (sl.index[0] <= b <= sl.index[-1]):
                continue
            rets.append((m.loc[b] / m.loc[a]) ** (12 / WF_WINDOW_MONTHS) - 1)
        if rets:
            r = np.array(rets, dtype=float)
            out[tag] = {"windows": len(r), "cagr_min": float(r.min()),
                        "cagr_med": float(np.median(r)), "cagr_max": float(r.max()),
                        "share_positive": float((r > 0).mean())}
    return out


# -------------------------------------------------------------------- output
def _fmt(s: dict) -> str:
    return (f"CAGR {s['cagr']*100:7.2f}% | MDD {s['mdd']*100:8.2f}% | "
            f"Sharpe {s['sharpe']:5.2f} | 승률 {s['win_rate']*100:5.1f}% | "
            f"리밸 {s['rebalances']:5d} | 연회전 {s['turnover_annual_oneway']:5.2f}")


def _fmt_wf(wf: dict, tag: str) -> str:
    d = wf.get(tag)
    if not d:
        return "창 부족"
    return (f"{d['windows']:3d}창 | CAGR 최저 {d['cagr_min']*100:6.2f}% / "
            f"중앙 {d['cagr_med']*100:6.2f}% / 최고 {d['cagr_max']*100:6.2f}% | "
            f"양(+) 비율 {d['share_positive']*100:5.1f}%")


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
    fetch_end = (pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    print("=" * 92)
    print(f"M5 OOS 검증 | 인샘플 ~{IN_SAMPLE_END.date()} / OOS {OOS_START.date()}~현재 "
          f"| yfinance auto_adjust=True")
    print(f"비용: 수수료 {comm*100:.2f}%, 편도 슬리피지 {slip*100:.2f}% "
          f"(판정은 비용반영 일간 기준 — Q11 승인)")
    print(f"대상: Track A 9 + Track B(C13) 1 = 10개 전략, 변형 포함 {len(S.BUILDERS)}개 런")
    print(f"판정: §7 v{CRITERIA_VERSION} — Sharpe>={SHARPE_MIN} / "
          f"|MDD|<=인샘플x{MDD_MULT} / CAGR>=동일구간 SPY, "
          f"OOS 리밸 <{MIN_OOS_REBALANCES}회면 insufficient_sample")
    print("=" * 92)

    print(f"\n[데이터] {len(S.ALL_TICKERS)}개 티커 로드 중 ({FETCH_START}~{fetch_end}) ...")
    open_, close = data.load_universe(S.ALL_TICKERS, FETCH_START, fetch_end)
    print(f"  거래일 {len(close)} | 최종 거래일 {close.index[-1].date()}")
    ohlc = {t: data.fetch_ohlc(t, FETCH_START, fetch_end) for t in S.ALL_TICKERS}

    # benchmark: SPY buy&hold on the OOS window, same cost assumption (§7)
    def spy_window(start):
        o, c = open_.loc[start:], close.loc[start:]
        r = run_backtest(c[["SPY"]], o[["SPY"]], sb.buy_and_hold(c.index, "SPY"),
                         commission=comm, slippage=slip)
        s = metrics.summary(r.equity, r.returns, r.exposure, r.turnover, r.trade_days)
        s.update(metrics.monthly_summary(r.equity))
        s["rebalances"] = r.trade_days
        s["start"] = str(c.index[0].date())
        s["end"] = str(c.index[-1].date())
        return s

    spy_oos = spy_window(OOS_START)
    spy_c = close.loc[OOS_START:]
    print(f"\n[벤치마크] SPY Buy&Hold {spy_c.index[0].date()}~{spy_c.index[-1].date()} "
          f"(비용반영): {_fmt(spy_oos)}")
    print(f"           월간 기준: CAGR {spy_oos['cagr_m']*100:.2f}% | "
          f"MDD {spy_oos['mdd_m']*100:.2f}% | Sharpe {spy_oos['sharpe_m']:.2f}")

    results, table = {}, []
    for builder in S.BUILDERS:
        plan = builder(ohlc)
        print("\n" + "-" * 92)
        print(f"[{plan.key}] {plan.name}")
        print(f"  spec: {plan.spec_id} | 유니버스: {','.join(plan.tickers)}")
        try:
            paid = _run_full(plan, open_, close, comm, slip)
            free = _run_full(plan, open_, close, 0.0, 0.0)
        except Exception as exc:
            print(f"  [ERROR] {type(exc).__name__}: {exc}")
            continue
        ins = _slice(paid, end=IN_SAMPLE_END)
        oos = _slice(paid, start=OOS_START)
        oos_free = _slice(free, start=OOS_START)
        if ins is None or oos is None:
            print("  [SKIP] 인샘플 또는 OOS 구간이 너무 짧음")
            continue

        # every strategy here has history well before 2019, so the OOS windows
        # coincide; if one ever started later, judge it against ITS window's SPY
        bench = spy_oos
        if oos["start"] != spy_oos["start"]:
            bench = spy_window(pd.Timestamp(oos["start"]))
            print(f"  [주의] OOS 시작일이 벤치마크와 달라 구간 정렬 SPY로 판정 "
                  f"({bench['start']}~, CAGR {bench['cagr']*100:.2f}%)")
        v = judge(oos, ins, bench)
        wf = walk_forward(paid)
        print(f"  인샘플({ins['start']}~{ins['end']}) : {_fmt(ins)}")
        print(f"  OOS   ({oos['start']}~{oos['end']}) : {_fmt(oos)}")
        print(f"  OOS 무비용                          : {_fmt(oos_free)}")
        print(f"  OOS 월간 : CAGR {oos['cagr_m']*100:6.2f}% | MDD {oos['mdd_m']*100:7.2f}% "
              f"| Sharpe {oos['sharpe_m']:5.2f}")
        if v["verdict"] == "insufficient_sample":
            print(f"  판정: **{v['verdict']}** — {v['reason']}")
        else:
            c = v["criteria"]
            print(f"  판정: **{v['verdict']}** ({v['met']}/3)"
                  f"  (1) Sharpe {c['sharpe_min']['oos']:.2f}>={SHARPE_MIN:.2f} "
                  f"{'O' if c['sharpe_min']['pass'] else 'X'}"
                  f"  (2) MDD {c['mdd_vs_in_sample']['oos']*100:.2f}% >= "
                  f"{c['mdd_vs_in_sample']['limit']*100:.2f}% "
                  f"{'O' if c['mdd_vs_in_sample']['pass'] else 'X'}"
                  f"  (3) CAGR {c['cagr_ge_spy']['oos']*100:.2f}% >= "
                  f"SPY {c['cagr_ge_spy']['spy']*100:.2f}% "
                  f"{'O' if c['cagr_ge_spy']['pass'] else 'X'}")
        print(f"  워크포워드 36개월 롤링 | 인샘플: {_fmt_wf(wf, 'in_sample')}")
        print(f"                         | OOS   : {_fmt_wf(wf, 'oos')}")
        if oos.get("warnings") or paid["warnings"]:
            print(f"  경고 {paid['warnings']}건 (가격 결측 등)")
        yr = {k: round(x * 100, 1) for k, x in sorted(oos["yearly_returns"].items())}
        print(f"  OOS 연도별(비용반영, %): {yr}")

        results[plan.key] = {"name": plan.name, "spec_id": plan.spec_id,
                             "in_sample": ins, "oos": oos, "oos_free": oos_free,
                             "verdict": v, "walk_forward": wf, "notes": plan.notes}
        table.append((plan.key, v, oos, ins))

    print("\n" + "=" * 92)
    print("판정 요약 (비용반영 일간 기준)")
    print(f"{'전략':24s} {'판정':20s} {'OOS CAGR':>9s} {'OOS MDD':>9s} "
          f"{'Sharpe':>7s} {'인샘플MDD':>10s} {'리밸':>5s}")
    for key, v, oos, ins in table:
        mark = v["verdict"] + (f" ({v['met']}/3)" if v["met"] is not None else "")
        print(f"{key:24s} {mark:20s} {oos['cagr']*100:8.2f}% {oos['mdd']*100:8.2f}% "
              f"{oos['sharpe']:7.2f} {ins['mdd']*100:9.2f}% {oos['rebalances']:5d}")
    print(f"{'(벤치마크) SPY B&H':24s} {'-':20s} {spy_oos['cagr']*100:8.2f}% "
          f"{spy_oos['mdd']*100:8.2f}% {spy_oos['sharpe']:7.2f}")
    print("=" * 92)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        payload = {"generated_at": str(pd.Timestamp.now()),
                   "in_sample_end": str(IN_SAMPLE_END.date()),
                   "oos_start": str(OOS_START.date()),
                   "costs": {"commission": comm, "slippage": slip},
                   "benchmark_spy_oos": spy_oos, "strategies": results}
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1, default=str)
        print(f"\n[saved] {args.json}")
    print("\n>>> 위 출력 전체를 Claude에게 전달해 주세요. <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())
