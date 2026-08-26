# -*- coding: utf-8 -*-
"""Resumable checkpoint (data/archive/checkpoint.json — gitignored).

Atomic write (tmp + replace) so an interrupted run never corrupts the file.
"""

from __future__ import annotations

import json
import os

from . import config


def load() -> dict:
    if not config.CHECKPOINT_PATH.exists():
        return {"done": {}, "failed": {}, "listings": {}}
    with open(config.CHECKPOINT_PATH, encoding="utf-8") as f:
        return json.load(f)


def save(state: dict) -> None:
    config.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(config.CHECKPOINT_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, config.CHECKPOINT_PATH)


def mark_done(state: dict, url: str, content_hash: str) -> None:
    state["done"][url] = content_hash
    state["failed"].pop(url, None)
    save(state)


def mark_failed(state: dict, url: str, reason: str) -> None:
    state["failed"][url] = reason
    save(state)
