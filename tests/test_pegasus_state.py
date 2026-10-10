"""Offline tests of the revisable state: statements with their condition, retractions, contradictions."""

import json
from pathlib import Path

from pegasus_helpers import CASES, buyer, opening, supplier

from hollerau.pegasus import economics as eco
from hollerau.pegasus import reader, replay
from hollerau.pegasus.state import ThreadState

P08, P10 = CASES["case:P08"], CASES["case:P10"]
SID = P08["suppliers"][0]
CLAUSE = P08["term_options"]["index_clause"][1]
SESSIONS = Path(__file__).resolve().parents[1] / "analysis" / "pegasus_data" / "sessions"


def terms(case, price, **over):
    base = opening(case, case["suppliers"][0], price)["term_sheets"][0]["terms"]
    return {**base, **over, "unit_price": price}


def hear(state, n, sheet, body, status="open", alternatives=()):
    msg = supplier(SID, n, sheet, status, body, alternatives)
    return state.heard(msg, reader.read(body), reader.denied(body))


def test_a_statement_taken_back_stops_holding():
    state = ThreadState()
    hear(state, 0, terms(P08, 6.05), "Our prices are frozen this year; we can only talk about the terms.")
    assert state.flags()["freeze"]
    hear(state, 1, terms(P08, 6.05), "Our prices are no longer frozen; we can negotiate the price.")
    assert not state.flags()["freeze"]
    assert state.summary()["withdrawn"] == ["price.frozen: taken back in its message 1"]


def test_an_index_clause_required_for_a_long_contract_is_not_required_for_every_contract():
    state = ThreadState()
    hear(state, 0, terms(P08, 6.05, contract_months=12), "Please find our quote attached.")
    hear(state, 1, terms(P08, 5.45, contract_months=36, index_clause=CLAUSE),
         "We cannot offer a fixed price over 36 months, so we must apply the AS-14404 index.")
    assert state.flags()["wants_index"] and state.value("index.required") == "AS-14404"
    assert not state.allowed({"contract_months": 36, "index_clause": None})[0]
    assert state.allowed({"contract_months": 36, "index_clause": CLAUSE})[0]
    assert state.allowed({"contract_months": 12, "index_clause": None})[0]  # said about 36 months only
    assert state.allowed({"contract_months": 24, "index_clause": None})[0]


def test_its_own_offers_outweigh_what_it_said():
    state = ThreadState()
    hear(state, 0, terms(P08, 6.05), "Please find our quote attached.")
    hear(state, 1, terms(P08, 5.45, contract_months=24, index_clause=CLAUSE),
         "We must insist on the AS-14404 index clause for a contract of this length.")
    assert not state.allowed({"contract_months": 24, "index_clause": None})[0]
    hear(state, 2, terms(P08, 5.60, contract_months=24, index_clause=None), "Here is a fixed-price package.")
    assert state.allowed({"contract_months": 24, "index_clause": None})[0] and not state.flags()["wants_index"]
    assert "fixed price" in state.summary()["withdrawn"][0]


def test_a_price_limit_holds_until_the_price_goes_lower():
    state = ThreadState()
    hear(state, 0, terms(P08, 6.05), "Please find our quote attached.")
    hear(state, 1, terms(P08, 5.25), "This is our absolute limit.")
    hear(state, 2, terms(P08, 5.25), "We cannot go lower than this.")
    assert state.floor_hits() == 2
    hear(state, 3, terms(P08, 5.20), "We made one more step.")
    assert state.floor_hits() == 0  # it went under what it called its limit, twice


def test_a_firm_lead_time_binds_until_it_offers_a_shorter_one():
    sid, state = P10["suppliers"][0], ThreadState()
    late = {**opening(P10, sid, 32.2)["term_sheets"][0]["terms"], "lead_time_days": 56}
    body = "Our lead time of 56 days is firm."
    state.heard(supplier(sid, 0, late, body=body), reader.read(body), reader.denied(body))
    assert state.flags()["lead_firm"] and state.flags()["stated"] == {"lead_time_days": 56}
    assert not state.allowed({"lead_time_days": 42})[0] and state.allowed({"lead_time_days": 56})[0]
    state.heard(supplier(sid, 1, {**late, "lead_time_days": 42, "unit_price": 33.6}), set(), set())
    assert state.allowed({"lead_time_days": 42})[0] and not state.flags()["lead_firm"]


def test_memory_is_a_hint_not_a_constraint():
    state = ThreadState()
    state.prior({"wants_index": True, "cash": True, "lead_firm": True}, {"lead_time_days": 56})
    flags = state.flags()
    assert flags["cash"]  # a preference may earn a trade
    assert not flags["wants_index"] and not flags["lead_firm"] and flags["stated"] == {}
    assert state.allowed({"contract_months": 24, "index_clause": None, "lead_time_days": 42})[0]
    hear(state, 0, terms(P08, 5.45, contract_months=24, index_clause=CLAUSE),
         "We must insist on the AS-14404 index clause.")
    assert state.flags()["wants_index"]  # now it said it in this negotiation


def test_two_of_its_quotes_that_differ_only_in_payment_price_its_money():
    state = ThreadState()
    slow, fast = terms(P08, 5.45, payment_days=90), terms(P08, 5.37, payment_days=14)
    state.heard(supplier(SID, 0, slow, alternatives=[fast]))
    assert 0.06 < state.cash_rate() < 0.08  # (5.37 / 5.45 - 1) * 360 / -76
    other = ThreadState().heard(supplier(SID, 0, slow, alternatives=[{**fast, "contract_months": 36}]))
    assert other.cash_rate() is None  # two things changed: nothing to read


def test_a_restart_recovers_the_same_state_from_the_messages():
    events = [
        supplier(SID, 0, terms(P08, 6.05), body="Please find our quote attached."),
        buyer(P08, 4.84, body="First offer.", payment_days=90, contract_months=24),
        supplier(SID, 1, terms(P08, 5.45, contract_months=24, index_clause=CLAUSE),
                 body="We cannot fix prices over 24 months. Faster payment would help us."),
        buyer(P08, 5.01, body="Second offer.", payment_days=90, contract_months=24),
        supplier(SID, 2, terms(P08, 5.36, contract_months=24, index_clause=CLAUSE), "final_offer",
                 "This is our absolute limit."),
    ]
    live = ThreadState()
    for i in range(len(events)):  # as the agent does: one new message at a time
        ThreadState.rebuild(events[: i + 1], start=live, seen=i)
    assert ThreadState.rebuild(events).to_dict() == live.to_dict()
    assert live.flags()["wants_index"] and live.flags()["cash"] and live.floor_hits() == 1
    assert len(live.ours) == 2 and len(live.theirs) == 3


def test_the_state_reads_every_archived_session_without_failing():
    files = sorted(SESSIONS.glob("*.json"))  # practice and sandbox, as played
    assert len(files) > 100
    sandbox = json.loads((Path(__file__).parent / "fixtures/cases/sandbox.json").read_text())
    cases = {**CASES, **{c["case_id"]: c for c in sandbox}}
    threads_read = 0
    for path in files:
        session = replay.load(path)
        case = cases.get(session.get("case_id"))
        for events in replay.threads_of(session).values():
            state = ThreadState.rebuild(events)
            threads_read += 1
            assert isinstance(state.flags()["stated"], dict)
            for structure in eco.grid(case)[:40] if case else []:
                state.allowed(structure)  # never raises on a real structure
            json.dumps(state.to_dict(), default=str)
    assert threads_read > 100
