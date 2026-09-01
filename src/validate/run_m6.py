# -*- coding: utf-8 -*-
"""M6 batch runner — the final table (run LOCALLY, needs yfinance).

Same engine, same builders, same §7 v1.0 verdict as M5. What M6 adds:

1. The two strategies approved at the M5 gate (C10, C12) once their specs exist.
2. A **post-publication supplementary slice** for every strategy whose post was
   published after the OOS boundary (L-09). The verdict window stays fixed at
   2019-01-01 — CLAUDE.md §5 forbids per-strategy boundaries — so this slice is
   reported as 참고 정보, never as a verdict.
3. One integrated table (verdict, contamination, risk-adjusted comparison) that
   the final report is written from.

Usage (PowerShell, repo root, venv active):
  python -m src.validate.run_m6 --json reports/m6_results.json
Paste the full output back into the Claude session.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backtest import data, settings  # noqa: E402
from src.validate import run_m5 as M5  # noqa: E402
from src.validate import strategies_m6 as S  # noqa: E402
from src.validate import tee  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
FETCH_START = "2000-01-01"
POST_PUBLICATION_LAG_MONTHS = 1     # 발행 직후 1개월은 제외 (글 공개 시점 여유)


def _spec(spec_id: str) -> dict:
    p = REPO / "data" / "specs" / f"{spec_id}.json"
    return json.load(open(p, encoding="utf-8")) if p.exists() else {}


def _published_at(spec_id: str) -> pd.Timestamp | None:
    v = (_spec(spec_id).get("source") or {}).get("published_at")
    return pd.Timestamp(v) if v else None


def _track(spec_id: str) -> str:
    return (_spec(spec_id).get("scope") or {}).get("track", "?")


def _contaminated(pub: pd.Timestamp | None) -> bool:
    """L-09: the post was published inside the OOS window, so the author could
    already see part of it. Its OOS is not genuinely out of sample."""
    return pub is not None and pub >= M5.OOS_START


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None, help="also write results to this JSON path")
    ap.add_argument("--out", default=None,
                    help="write the console report to this file as UTF-8 "
                         "(do NOT pipe through Tee-Object — that mangles Korean)")
    args = ap.parse_args()
    close_out = tee.start(args.out)

    comm, slip = settings.costs()
    fetch_end = (pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    print("=" * 100)
    print(f"M6 배치 | 인샘플 ~{M5.IN_SAMPLE_END.date()} / OOS {M5.OOS_START.date()}~현재 "
          f"| yfinance auto_adjust=True")
    print(f"판정: §7 v{M5.CRITERIA_VERSION} (M5와 동일, 비용반영 일간). "
          f"발행후 구간은 **참고 정보**이며 판정에 쓰지 않는다 (L-09, §5 구간 고정)")
    print(f"대상: {len(S.BUILDERS)}개 런")
    print("=" * 100)

    print(f"\n[데이터] {len(S.ALL_TICKERS)}개 티커 로드 중 ({FETCH_START}~{fetch_end}) ...")
    open_, close = data.load_universe(S.ALL_TICKERS, FETCH_START, fetch_end)
    print(f"  거래일 {len(close)} | 최종 거래일 {close.index[-1].date()}")
    ohlc = {t: data.fetch_ohlc(t, FETCH_START, fetch_end) for t in S.ALL_TICKERS}

    spy_oos = M5.spy_window(open_, close, M5.OOS_START, comm, slip)
    print(f"\n[벤치마크] SPY B&H {spy_oos['start']}~{spy_oos['end']} (비용반영): "
          f"CAGR {spy_oos['cagr']*100:.2f}% | MDD {spy_oos['mdd']*100:.2f}% "
          f"| Sharpe {spy_oos['sharpe']:.2f}")

    results, rows = {}, []
    for builder in S.BUILDERS:
        plan = builder(ohlc)
        pub = _published_at(plan.spec_id)
        dirty = _contaminated(pub)
        print("\n" + "-" * 100)
        print(f"[{plan.key}] {plan.name}")
        print(f"  spec: {plan.spec_id} | track: {_track(plan.spec_id)} | "
              f"발행: {pub.date() if pub is not None else '?'}"
              + ("  **OOS 오염 (L-09)**" if dirty else "  (OOS 깨끗)"))
        try:
            paid = M5._run_full(plan, open_, close, comm, slip)
        except Exception as exc:
            print(f"  [ERROR] {type(exc).__name__}: {exc}")
            continue
        ins = M5._slice(paid, end=M5.IN_SAMPLE_END)
        oos = M5._slice(paid, start=M5.OOS_START)
        if ins is None or oos is None:
            print("  [SKIP] 인샘플 또는 OOS 구간이 너무 짧음")
            continue

        bench = spy_oos
        if oos["start"] != spy_oos["start"]:
            bench = M5.spy_window(open_, close, pd.Timestamp(oos["start"]), comm, slip)
        v = M5.judge(oos, ins, bench)
        print(f"  인샘플 : CAGR {ins['cagr']*100:6.2f}% | MDD {ins['mdd']*100:7.2f}% "
              f"| Sharpe {ins['sharpe']:5.2f}  ({ins['start']}~{ins['end']})")
        print(f"  OOS    : CAGR {oos['cagr']*100:6.2f}% | MDD {oos['mdd']*100:7.2f}% "
              f"| Sharpe {oos['sharpe']:5.2f} | 리밸 {oos['rebalances']}")
        print(f"  판정   : **{v['verdict']}**"
              + (f" ({v['met']}/3)" if v["met"] is not None else f" — {v['reason']}"))

        post = None
        if dirty:
            start = (pub + pd.DateOffset(months=POST_PUBLICATION_LAG_MONTHS)).normalize()
            post = M5._slice(paid, start=start)
            if post is None:
                print(f"  발행후(참고): 구간이 너무 짧아 산출하지 않음 ({start.date()}~)")
            else:
                pb = M5.spy_window(open_, close, pd.Timestamp(post["start"]), comm, slip)
                thin = post["rebalances"] < M5.MIN_OOS_REBALANCES
                print(f"  발행후(참고, 판정 아님): {post['start']}~{post['end']} | "
                      f"CAGR {post['cagr']*100:6.2f}% | MDD {post['mdd']*100:7.2f}% | "
                      f"Sharpe {post['sharpe']:5.2f} | 리밸 {post['rebalances']}"
                      + ("  [표본 부족 — 해석 주의]" if thin else ""))
                print(f"                          동일구간 SPY: CAGR {pb['cagr']*100:6.2f}% "
                      f"| Sharpe {pb['sharpe']:.2f}")
                post["spy_same_window"] = {k: pb[k] for k in ("cagr", "mdd", "sharpe")}
                post["thin_sample"] = bool(thin)

        results[plan.key] = {"name": plan.name, "spec_id": plan.spec_id,
                             "track": _track(plan.spec_id),
                             "published_at": str(pub.date()) if pub is not None else None,
                             "oos_contaminated": bool(dirty),
                             "in_sample": ins, "oos": oos, "post_publication": post,
                             "verdict": v, "walk_forward": M5.walk_forward(paid),
                             "notes": plan.notes}
        rows.append((plan.key, v, oos, ins, dirty, post))

    # ------------------------------------------------------------ final table
    print("\n" + "=" * 100)
    print("최종 통합 판정표 (§7 v1.0, 비용반영 일간 기준)")
    print(f"{'전략':24s} {'판정':16s} {'OOS CAGR':>9s} {'OOS MDD':>9s} {'Sharpe':>7s} "
          f"{'vsSPY':>6s} {'오염':>5s} {'발행후CAGR':>10s}")
    for key, v, oos, _ins, dirty, post in rows:
        mark = v["verdict"] + (f" ({v['met']}/3)" if v["met"] is not None else "")
        vs = "O" if oos["sharpe"] >= spy_oos["sharpe"] else "X"
        pc = f"{post['cagr']*100:9.2f}%" if post else (" " * 9 + "-")
        print(f"{key:24s} {mark:16s} {oos['cagr']*100:8.2f}% {oos['mdd']*100:8.2f}% "
              f"{oos['sharpe']:7.2f} {vs:>6s} {'Y' if dirty else '·':>5s} {pc}")
    print(f"{'(벤치마크) SPY B&H':24s} {'-':16s} {spy_oos['cagr']*100:8.2f}% "
          f"{spy_oos['mdd']*100:8.2f}% {spy_oos['sharpe']:7.2f}")
    counts: dict = {}
    for _k, v, *_ in rows:
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    print(f"\n판정 분포: {counts}")
    print("vsSPY = OOS Sharpe가 동일구간 SPY 이상인지 (보조 정보, 판정 아님)")
    print("오염 Y = 발행일이 OOS 구간 안 (L-09) — 해당 전략의 OOS는 진정한 OOS가 아님")
    print("=" * 100)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        payload = {"generated_at": str(pd.Timestamp.now()),
                   "criteria_version": M5.CRITERIA_VERSION,
                   "in_sample_end": str(M5.IN_SAMPLE_END.date()),
                   "oos_start": str(M5.OOS_START.date()),
                   "costs": {"commission": comm, "slippage": slip},
                   "benchmark_spy_oos": spy_oos, "verdict_counts": counts,
                   "strategies": results}
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1, default=str)
        print(f"\n[saved] {args.json}")
    if args.out:
        print(f"[saved] {args.out} (UTF-8)")
    print("\n>>> 위 출력 전체를 Claude에게 전달해 주세요. <<<")
    close_out()
    return 0


if __name__ == "__main__":
    sys.exit(main())
