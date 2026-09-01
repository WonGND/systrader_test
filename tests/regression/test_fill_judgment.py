# -*- coding: utf-8 -*-
"""Offline checks for the judgment writer (M6 Q21).

The verdicts end up inside the committed specs, so a bug here would put a
wrong verdict into the project's permanent record. These run against a
temporary copy of the specs with a synthetic batch result.
"""

import json
import shutil
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.extractor import fill_judgment as F  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def _run(spec_id, key, cagr, sharpe, mdd, reb, is_mdd, verdict, met,
         pub, dirty, post=None):
    return {"name": key, "spec_id": spec_id, "track": "native_overseas",
            "published_at": pub, "oos_contaminated": dirty,
            "in_sample": {"mdd": is_mdd, "cagr": 0.03, "sharpe": 0.5},
            "oos": {"cagr": cagr, "mdd": mdd, "sharpe": sharpe, "rebalances": reb},
            "verdict": {"verdict": verdict, "met": met, "criteria_version": "1.0"},
            "post_publication": post}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    specs = tmp_path / "specs"
    shutil.copytree(REPO / "data" / "specs", specs)
    monkeypatch.setattr(F, "SPEC_DIR", specs)
    payload = {
        "criteria_version": "1.0",
        "benchmark_spy_oos": {"cagr": 0.1753, "mdd": -0.3372, "sharpe": 0.94},
        "strategies": {
            "c01": _run("c01-avg-momentum-score-allocation-14-17", "c01",
                        0.0407, 0.89, -0.0914, 92, -0.0492, "dead", 1,
                        "2014-05-07", False),
            "c01_zero_cash": _run("c01-avg-momentum-score-allocation-14-17",
                                  "c01_zero_cash", 0.0391, 0.91, -0.0629, 92,
                                  -0.0506, "weak", 2, "2014-05-07", False),
            "c12": _run("c12-defense-first-taa", "c12", 0.1668, 1.48, -0.1037,
                        92, -0.1246, "weak", 2, "2025-07-28", True,
                        {"cagr": 0.2918, "sharpe": 1.88, "rebalances": 13,
                         "start": "2025-08-28", "end": "2026-08-31",
                         "thin_sample": False,
                         "spy_same_window": {"cagr": 0.1934}}),
        },
    }
    results = tmp_path / "m6_results.json"
    results.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["fill_judgment", "--results", str(results)])
    return specs


def _spec(specs, name):
    return json.load(open(specs / name, encoding="utf-8"))


def test_verdict_is_copied_verbatim_from_the_batch(workspace):
    assert F.main() == 0
    j = _spec(workspace, "c01-avg-momentum-score-allocation-14-17.json")["judgment_result"]
    assert j["verdict"] == "dead" and j["conditions_met"] == 1
    assert j["oos_cagr"] == pytest.approx(0.0407)
    assert j["oos_sharpe"] == pytest.approx(0.89)
    assert j["in_sample_mdd_reference"] == pytest.approx(-0.0492)
    assert j["benchmark_cagr"] == pytest.approx(0.1753)
    assert j["oos_rebalance_count"] == 92
    assert j["criteria_version"] == "1.0"


def test_primary_run_decides_and_variants_are_recorded_as_caveats(workspace):
    F.main()
    j = _spec(workspace, "c01-avg-momentum-score-allocation-14-17.json")["judgment_result"]
    assert j["verdict"] == "dead"                      # c01 is the primary run
    joined = " ".join(j["caveats"])
    assert "c01_zero_cash" in joined and "weak" in joined
    assert "판정 근거 런 = c01" in joined


def test_contaminated_spec_carries_the_l09_caveat(workspace):
    F.main()
    j = _spec(workspace, "c12-defense-first-taa.json")["judgment_result"]
    joined = " ".join(j["caveats"])
    assert "L-09" in joined and "2025-07-28" in joined
    assert "발행 이후" in joined and "29.18%" in joined


def test_clean_spec_has_no_l09_caveat(workspace):
    F.main()
    j = _spec(workspace, "c01-avg-momentum-score-allocation-14-17.json")["judgment_result"]
    assert not any("L-09" in c for c in j["caveats"])


def test_written_specs_still_validate(workspace):
    F.main()
    schema = json.load(open(REPO / "schemas" / "strategy_spec.schema.json",
                            encoding="utf-8"))
    v = jsonschema.Draft202012Validator(schema)
    for path in sorted(workspace.glob("c*.json")):
        errors = list(v.iter_errors(json.load(open(path, encoding="utf-8"))))
        assert errors == [], f"{path.name}: {[e.message for e in errors][:3]}"


def test_specs_without_batch_results_are_left_alone(workspace):
    F.main()
    untouched = _spec(workspace, "c03-accelerating-dual-momentum-60.json")
    assert "judgment_result" not in untouched     # no batch entry -> no verdict


def test_every_spec_has_a_declared_primary_run():
    """A new spec must be given a primary run explicitly, not guessed."""
    ids = {json.load(open(p, encoding="utf-8"))["spec_id"]
           for p in (REPO / "data" / "specs").glob("c*.json")}
    assert ids == set(F.PRIMARY_RUN), ids ^ set(F.PRIMARY_RUN)
