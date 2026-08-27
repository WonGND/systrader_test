# -*- coding: utf-8 -*-
"""Backtest settings loaded from config/backtest_defaults.yaml.

No cost/execution parameter is hardcoded anywhere in the engine (CLAUDE.md §5);
everything comes from this loader.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "backtest_defaults.yaml"


def load() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def costs() -> tuple:
    """(commission_pct, slippage_oneway_pct) — both fractions, labeled assumed."""
    c = load()["costs"]
    return float(c["commission_pct"]), float(c["slippage_oneway_pct"])
