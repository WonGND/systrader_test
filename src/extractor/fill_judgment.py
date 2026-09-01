# -*- coding: utf-8 -*-
"""Write the M6 verdicts into each spec's judgment_result (runs LOCALLY).

The schema has carried `judgment_result` since v1.1 with the note "M5/M6에서
채워진다" — this is that step (M6 gate Q21). Numbers come from
reports/m6_results.json, which only exists on the machine that ran the batch;
nothing here recomputes or rounds a verdict.

A spec can have several runs (variants and contrast versions). Only the run
that implements the post's rules **as written** fills judgment_result; the
others are listed in `caveats` so a reader sees the spread without having to
open the batch JSON. Contaminated posts (L-09) get an explicit caveat.

Usage (PowerShell, repo root, venv active):
  python -m src.extractor.fill_judgment
  python -m src.extractor.fill_judgment --results reports/m6_results.json
Then commit data/specs/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC_DIR = REPO / "data" / "specs"
DEFAULT_RESULTS = REPO / "reports" / "m6_results.json"

# The run whose rules are the post's own, per spec. Variants exist to show what
# an ambiguity or an assumption costs — they are evidence, not the verdict.
PRIMARY_RUN = {
    "c01-avg-momentum-score-allocation-14-17": "c01",
    "c02-dynamic-permanent-allweather-72": "c02_permanent",
    "c03-accelerating-dual-momentum-60": "c03",
    "c04-rsi2-counter-trend-39": "c04",
    "c05-multi-ma-breakout-35": "c05",
    "c06-hybrid-asset-allocation-136": "c06",
    "c07-weekday-monthend-seasonality-115": "c07",
    "c08-qqq-tlt-spread-rsi3": "c08",
    "c09-ibs-lower-band-mean-reversion": "c09_qqq",   # 원문 주장이 QQQ 기준
    "c10-connors-rsi2-simple": "c10_spy",             # 원문 규칙 서술이 SPY 기준
    "c12-defense-first-taa": "c12",                   # 원문 서술대로 월말 종가 체결
    "c13-modified-paa-31-ported": "c13",
}


def _caveats(spec_id: str, primary_key: str, runs: dict) -> list:
    out = []
    r = runs[primary_key]
    if r.get("oos_contaminated"):
        out.append(
            f"L-09 OOS 오염: 발행일 {r['published_at']}이 OOS 구간(2019-01-01~) 안이다. "
            "저자가 해당 구간을 이미 보고 규칙을 정했을 수 있어 진정한 "
            "out-of-sample 증거가 아니다. 해석에서 할인할 것.")
        post = r.get("post_publication")
        if post:
            note = (f"참고(판정 아님) 발행 이후 {post['start']}~{post['end']}: "
                    f"CAGR {post['cagr']*100:.2f}%, Sharpe {post['sharpe']:.2f}, "
                    f"리밸 {post['rebalances']}회")
            if post.get("thin_sample"):
                note += " — 표본 부족, 해석 주의"
            spy = post.get("spy_same_window")
            if spy:
                note += f" / 동일구간 SPY CAGR {spy['cagr']*100:.2f}%"
            out.append(note)

    others = [(k, v) for k, v in runs.items()
              if v["spec_id"] == spec_id and k != primary_key]
    for k, v in sorted(others):
        out.append(f"변형 런 {k}: {v['verdict']['verdict']} "
                   f"(OOS CAGR {v['oos']['cagr']*100:.2f}%, "
                   f"Sharpe {v['oos']['sharpe']:.2f})")
    out.append(f"판정 근거 런 = {primary_key} (원문 규칙 그대로 구현한 런)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(DEFAULT_RESULTS))
    args = ap.parse_args()
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    path = Path(args.results)
    if not path.exists():
        print(f"[ERROR] 배치 결과가 없습니다: {path}")
        print("        먼저 실행: python -m src.validate.run_m6 --json reports/m6_results.json")
        return 1
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    runs = payload["strategies"]
    bench = payload["benchmark_spy_oos"]

    updated, skipped = 0, []
    for spec_path in sorted(SPEC_DIR.glob("c*.json")):
        with open(spec_path, encoding="utf-8") as f:
            spec = json.load(f)
        spec_id = spec.get("spec_id")
        key = PRIMARY_RUN.get(spec_id)
        if key is None or key not in runs:
            skipped.append(f"{spec_id} (배치 결과 없음)")
            continue
        r = runs[key]
        v = r["verdict"]
        spec["judgment_result"] = {
            "criteria_version": payload.get("criteria_version", "1.0"),
            "oos_sharpe": round(float(r["oos"]["sharpe"]), 4),
            "oos_mdd": round(float(r["oos"]["mdd"]), 6),
            "oos_cagr": round(float(r["oos"]["cagr"]), 6),
            "benchmark_cagr": round(float(bench["cagr"]), 6),
            "in_sample_mdd_reference": round(float(r["in_sample"]["mdd"]), 6),
            "conditions_met": v["met"] if v["met"] is not None else 0,
            "oos_rebalance_count": int(r["oos"]["rebalances"]),
            "verdict": v["verdict"],
            "caveats": _caveats(spec_id, key, runs),
        }
        with open(spec_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=1)
        updated += 1
        print(f"filled: {spec_path.name:44s} {v['verdict']:20s} "
              f"OOS CAGR {r['oos']['cagr']*100:6.2f}% | Sharpe {r['oos']['sharpe']:.2f}")

    print(f"\nupdated: {updated}, skipped: {len(skipped)}")
    for s in skipped:
        print(f"  skipped: {s}")
    print(f"\n판정 기준: §7 v{payload.get('criteria_version', '1.0')} | "
          f"벤치마크 SPY OOS CAGR {bench['cagr']*100:.2f}%")
    if updated:
        print('\n다음: git add "data/specs" ; git commit -m "Record M6 verdicts in spec '
              'judgment_result" ; git push origin claude/systrader79-validation-pipeline-18lzzr')
    print("\n>>> 위 출력 전체를 Claude에게 전달해 주세요. <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())
