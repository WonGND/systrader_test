# -*- coding: utf-8 -*-
"""M3 real-data regression checks (run LOCALLY — the remote session cannot
reach Yahoo endpoints).

Covers the remaining CLAUDE.md §6 items that need market data:
- SPY single-asset Buy&Hold over a fixed window -> CAGR/MDD to be compared
  against externally published figures (e.g., portfoliovisualizer.com,
  same window, dividends reinvested)
- 60/40 SPY/IEF static mix with monthly / quarterly / yearly rebalancing

Data: yfinance, auto_adjust=True (dividend-reinvested total-return proxy,
DECISIONS 2026-08-26). Cached under cache/yfinance/ (gitignored).

Usage (PowerShell, repo root, venv active):
  python -m tests.regression.run_real_checks
Paste the full output back into the Claude session.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from src.backtest import data, settings, strategies_basic as sb  # noqa: E402
from src.backtest.engine import run_backtest  # noqa: E402

# Fixed comparison window: full calendar years, both ETFs listed well before.
START, END = "2004-12-20", "2025-01-03"
WINDOW_LABEL = "2005-01-01 ~ 2024-12-31"


def fmt(s: dict) -> str:
    return (f"CAGR {s['cagr']*100:6.2f}% | MDD {s['mdd']*100:7.2f}% | "
            f"Sharpe {s['sharpe']:5.2f} | win {s['win_rate']*100:5.1f}% | "
            f"trades {s['trade_days']:4d} | turn/yr {s['turnover_annual_oneway']:5.2f}")


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 76)
    print(f"M3 real-data checks | window {WINDOW_LABEL} | yfinance auto_adjust=True")
    print("costs: engine defaults OFF here (cost-free, to match published figures);")
    print("       cost sensitivity shown separately below")
    print("=" * 76)

    open_, close = data.load_universe(["SPY", "IEF"], START, END)
    open_ = open_.loc["2004-12-31":"2025-01-01"]
    close = close.loc["2004-12-31":"2025-01-01"]
    n_missing = int(close.isna().sum().sum())
    print(f"days: {len(close)} | missing cells: {n_missing} (never interpolated)")

    # --- SPY Buy & Hold ------------------------------------------------------
    bh = run_backtest(close, open_, sb.buy_and_hold(close.index, "SPY"))
    s = bh.summary()
    print("\n[1] SPY Buy&Hold (dividends reinvested)")
    print("    " + fmt(s))
    print("    yearly:", {k: f"{v*100:.1f}%" for k, v in sorted(s["yearly_returns"].items())})
    # internal consistency: engine path == raw adjusted-price ratio
    px = close["SPY"].dropna()
    ratio = float(px.iloc[-1] / px.loc[bh.equity.index[1]:].iloc[0])
    drift = abs(bh.equity.iloc[-1] / ratio - 1)
    print(f"    internal check vs price ratio: drift {drift:.2e} "
          f"({'OK' if drift < 1e-9 else 'FAIL'})")
    print("    ==> 외부 대조: portfoliovisualizer.com에서 SPY 100%,")
    print(f"        {WINDOW_LABEL}, dividends reinvested 로 CAGR/MDD 비교")

    # --- 60/40 SPY/IEF by rebalancing frequency ------------------------------
    print("\n[2] 60/40 SPY/IEF static mix (cost-free)")
    for freq, label in [("M", "monthly"), ("Q", "quarterly"), ("Y", "yearly")]:
        tgt = sb.static_mix(close.index, {"SPY": 0.6, "IEF": 0.4}, freq=freq)
        r = run_backtest(close, open_, tgt)
        print(f"    {label:9s}: " + fmt(r.summary()))

    # --- cost sensitivity (direction check on real data) ---------------------
    comm, slip = settings.costs()
    tgt = sb.static_mix(close.index, {"SPY": 0.6, "IEF": 0.4}, freq="M")
    r0 = run_backtest(close, open_, tgt)
    r1 = run_backtest(close, open_, tgt, commission=comm, slippage=slip)
    print(f"\n[3] cost sensitivity (60/40 monthly, config slippage {slip*100:.2f}% one-way)")
    print(f"    cost-free : {fmt(r0.summary())}")
    print(f"    with cost : {fmt(r1.summary())}")
    diff = r1.summary()['cagr'] - r0.summary()['cagr']
    print(f"    CAGR drag : {diff*100:+.3f}%p  ({'OK: negative & small' if -0.01 < diff < 0 else 'CHECK'})")

    print("\n>>> 위 출력 전체를 Claude에게 전달해 주세요. <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())
