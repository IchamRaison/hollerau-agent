"""Recognising a supplier from the records of the ones we have played. No model call, no session."""

import pytest

from hollerau.dsh import recognition
from hollerau.dsh.tools import Desk

from .test_pilot import d01


def thread(*pairs, opening=100.0):
    """A thread from (our ask, its offer, its status) triples, in cost units."""
    steps = [
        {"who": "S", "cost": opening, "status": "open", "text": "Our quote.\nGruß\nAnna Muster\nOwner, Muster GmbH"}
    ]
    for ask, offer, status in pairs:
        steps.append({"who": "B", "cost": ask, "sheets": 1 if ask is not None else 0})
        steps.append({"who": "S", "cost": offer, "status": status, "text": ""})
    return steps


def test_a_reply_is_measured_against_the_gap_it_faced():
    rows = recognition.replies(thread((80.0, 96.0, "open"), (82.0, 93.2, "open"), (None, 93.2, "final_offer")))
    first, second, third = rows
    assert first["gap"] == pytest.approx(0.20) and first["step"] == pytest.approx(0.04)
    assert first["share"] == pytest.approx(0.20) and "our_move" not in first
    assert second["gap"] == pytest.approx(0.14) and second["share"] == pytest.approx(0.2)
    assert second["our_move"] == pytest.approx(0.02)
    assert "gap" not in third and third["step"] == pytest.approx(0.0) and third["prev_status"] == "open"
    assert recognition.how_we_answered(third) == "a note without a term sheet"


def test_a_supplier_that_left_keeps_the_offer_it_left_behind():
    rows = recognition.replies(thread((80.0, 96.0, "final_offer"), (85.0, None, "walked_away")))
    assert rows[1]["status"] == "walked_away" and rows[1]["prev_status"] == "final_offer"
    assert "step" not in rows[1] and rows[1]["gap"] == pytest.approx(0.11)


def test_who_signs_and_what_it_writes_are_read_from_the_mail():
    text = (
        "Hallo,\nI can do 15.60 EUR with DAP delivery. Back to the machines now.\n"
        "Gruß\nClaudia Aigner\nOwner, Demo Drehteile GmbH"
    )
    assert recognition.signature(text) == ("Owner", "Demo Drehteile GmbH")
    said = recognition.sentences(text)
    assert "I can do # EUR with DAP delivery." in said and "Back to the machines now." in said


def test_records_exist_for_the_suppliers_we_played_in_units_a_game_shows():
    recs = recognition.records()
    assert len(recs) >= 15 and all(r["who_signs"] for r in recs)
    for r in recs:
        assert "c_best" not in str(r) and r["status_by_reply"]["1"]
        for part in (r["first_reply"], r["later_replies"]):
            assert part["law"]


def test_a_supplier_we_played_is_its_own_record_and_a_hidden_case_is_read_as_new(monkeypatch):
    state = d01(with_reply=True)
    like, found = state.recognise("sup:DEMO-F1")
    top = like["suppliers_it_resembles"][0]
    assert (
        top["supplier"] == "D01/DEMO-F1" and top["weight"] > 0.95 and top["why"] == ["the same supplier in our records"]
    )
    assert top["best_games"] and like["in_this_thread"]["replies"] == 1
    assert "best_games" not in like["suppliers_it_resembles"][1]
    monkeypatch.setenv("PEGASUS_DSH_HIDE_CASE_RECORDS", "1")
    like, _ = state.recognise("sup:DEMO-F1")
    assert all(not m["supplier"].startswith("D01/") for m in like["suppliers_it_resembles"])
    assert sum(w for w, _ in state.recognise("sup:DEMO-F1")[1]["all"]) == pytest.approx(1.0)


def test_the_snapshot_carries_the_resemblance_and_no_figure_in_hidden_units():
    view = d01(with_reply=True).snapshot()["threads"][0]
    assert view["suppliers_like_this_one"]["suppliers_it_resembles"]
    assert "signals_it_gave" not in view and "opening_to_best" not in str(view)


def test_a_deeper_ask_foretells_a_larger_step_from_a_share_of_the_gap_and_the_same_from_a_fixed_step():
    share = {
        "case": "X",
        "supplier": "a",
        "later_replies": {"law": "a share of the gap", "share_of_gap": [0.1, 0.2, 0.3]},
    }
    fixed = {
        "case": "Y",
        "supplier": "b",
        "later_replies": {
            "law": "a fixed step",
            "step_pct_of_its_quote": [1.0, 1.0, 1.0],
            "share_of_gap": [0.1, 0.2, 0.3],
        },
    }
    steps = thread((80.0, 96.0, "open"))
    for rec, near, deep in ((share, 2.0, 4.0), (fixed, 1.0, 1.0)):
        found = recognition.recognise({}, steps, pool=[rec])
        a = recognition.forecast(found, 96.0, 86.0, 100.0)["expected_step_pct_of_its_quote"]
        b = recognition.forecast(found, 96.0, 76.0, 100.0)["expected_step_pct_of_its_quote"]
        assert (a, b) == (pytest.approx(near), pytest.approx(deep))
    assert "note" in recognition.forecast(found, 96.0, 97.0, 100.0)


def test_what_the_thread_has_shown_weighs_on_the_forecast():
    rec = {
        "case": "X",
        "supplier": "a",
        "later_replies": {"law": "a share of the gap", "share_of_gap": [0.1, 0.2, 0.3]},
    }
    steps = thread((60.0, 90.0, "open"), (62.0, 76.0, "open"))  # second reply closed half of the gap
    found = recognition.recognise({}, steps, pool=[rec])
    step = recognition.forecast(found, 76.0, 66.0, 100.0)["expected_step_pct_of_its_quote"]
    assert step == pytest.approx((0.5 * 10 + 0.2 * 10) / 2)


def test_costing_candidate_sheets_also_foretells_the_reply():
    state = d01(with_reply=True)
    desk = Desk()
    decision = desk.open(state, 60)
    ours = {"unit_price": 49.0, "payment_days": 60, "contract_months": 24, "effective_date": "2026-12-01"}
    out = desk.evaluate_offers(decision.id, "sup:DEMO-F1", [{"terms": ours}])
    told = out["its_next_reply_if_you_send_these"]
    low, mid = (
        told["if_it_moves_its_sheet_would_cost_us_eur"]["low_step"],
        told["if_it_moves_its_sheet_would_cost_us_eur"]["expected"],
    )
    assert mid <= low < state.snapshot()["threads"][0]["supplier_sheets"][0]["commercial_eur"]
