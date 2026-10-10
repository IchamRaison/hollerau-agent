"""Offline tests of the pegasus guard (no network, no session)."""

import json
from pathlib import Path

from arena_kit.cost import complete_offer
from hollerau.pegasus import guard

CASES = {c["case_id"]: c for c in json.loads((Path(__file__).parent / "fixtures/cases/practice.json").read_text())}
FACTS = {
    "idx:PPI-D351@2025-08": {"series": "PPI-D351", "month": "2025-08", "value": 137.0},
    "idx:PPI-D351@2026-08": {"series": "PPI-D351", "month": "2026-08", "value": 131.9},
}


def test_true_index_claim_kept():
    case = CASES["case:P01"]
    body = "PPI-D351 changed -3.7% from 2025-08 to 2026-08 (idx:PPI-D351@2025-08, idx:PPI-D351@2026-08)."
    sheet = complete_offer(case, {"unit_price": 130.0})
    msg, problems = guard.check(case, {"body": body, "term_sheets": [{"terms": sheet}]}, FACTS)
    assert problems == [] and msg["body"] == body


def test_wrong_figure_unknown_id_and_leak_dropped():
    case = CASES["case:P01"]
    body = ("PPI-D351 changed -9.9% (idx:PPI-D351@2025-08, idx:PPI-D351@2026-08).\n"
            "We have no alternative.\nSee idx:FAKE@2026-01.")
    sheet = complete_offer(case, {"unit_price": 130.0})
    msg, problems = guard.check(case, {"body": body, "term_sheets": [{"terms": sheet}]}, FACTS)
    assert len(problems) == 3 and msg["body"] == ""


def test_sheet_far_above_ask_replaced_by_question():
    case = CASES["case:P01"]
    sheet = complete_offer(case, {"unit_price": 999.0})
    msg, problems = guard.check(case, {"body": "x", "term_sheets": [{"terms": sheet}]}, FACTS, ask=138.55)
    assert problems and "term_sheets" not in msg
