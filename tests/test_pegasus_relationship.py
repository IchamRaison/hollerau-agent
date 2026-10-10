"""Offline tests of the relationship floor (no network, no session).

The figures come from our ended practice sessions of P02: the relationship cost the arena charged on
three deals, and the full cost of the supplier fitted on them (367.62 EUR, money at 6.5 %).
"""

import json
from pathlib import Path

import pytest

from arena_kit import cost as kit
from hollerau.pegasus import economics as eco
from hollerau.pegasus import relationship
from hollerau.pegasus.agent import PegasusAgent

CASES = {c["case_id"]: c for c in json.loads((Path(__file__).parent / "fixtures/cases/practice.json").read_text())}
P02 = CASES["case:P02"]
SUPPLIER = P02["suppliers"][0]
STD = {"payment_days": 30}  # the supplier's standard payment terms, from its opening quote
CLAUSE = P02["term_options"]["index_clause"][1]
CAREFUL = {"unit_price": 371.92, "payment_days": 90, "index_clause": None}  # scored 0.50, charged 612
TOO_LOW = {"unit_price": 349.36, "payment_days": 45, "index_clause": CLAUSE}  # scored 0.23, charged 112 075
FAR_TOO_LOW = {"unit_price": 344.2, "payment_days": 14, "index_clause": CLAUSE}  # scored 0, charged 143 194
C_OPEN, C_BEST = 2282867.0, 2235514.0  # the arena's, from the same sessions
FITTED = {
    "full_cost": 367.62,
    "interest_rate": 0.065,
    "standard": {k: v for k, v in kit.closing_terms(P02, {}, STD).items() if k != "unit_price"},
}
SHOULD_COST = {"cost:350011": {"part": "part:350011", "price_unit": 1, "unit_cost": 374.95}}
BEST_STRUCTURE = {"payment_days": 90, "index_clause": None}


class Package:
    """The few things the supplier estimate reads from the data package."""

    db = release = None

    def __init__(self, facts):
        self.facts = facts


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(relationship, "ENABLED", True)


def true_cost(terms):
    return kit.total_cost(P02, terms, STD, FITTED)


def score(c):
    return (C_OPEN - c) / (C_OPEN - C_BEST)


def test_fitted_supplier_reproduces_what_the_arena_charged():
    assert relationship.cost(P02, TOO_LOW, STD, FITTED) == pytest.approx(112075, rel=0.01)
    assert relationship.cost(P02, FAR_TOO_LOW, STD, FITTED) == pytest.approx(143194, rel=0.01)
    assert relationship.cost(P02, CAREFUL, STD, FITTED) == pytest.approx(612, abs=100)


def test_floor_is_the_bottom_of_the_u():
    floor = relationship.floor_price(P02, BEST_STRUCTURE, STD, FITTED)
    assert TOO_LOW["unit_price"] < floor < CAREFUL["unit_price"]
    at = true_cost({**BEST_STRUCTURE, "unit_price": floor})
    assert at <= true_cost({**BEST_STRUCTURE, "unit_price": floor - 1})
    assert at <= true_cost({**BEST_STRUCTURE, "unit_price": floor + 1})
    assert at < true_cost(CAREFUL) and at < true_cost(TOO_LOW)
    assert score(at) >= 0.95


def test_no_floor_when_switched_off(monkeypatch):
    monkeypatch.setattr(relationship, "ENABLED", False)
    assert relationship.estimate(P02, Package(SHOULD_COST), STD) is None


def test_estimate_needs_a_relationship_case_and_a_should_cost(on):
    est = relationship.estimate(P02, Package(SHOULD_COST), STD)
    assert est["full_cost"] == pytest.approx(374.95 * relationship.FULL_COST_FACTOR)
    assert relationship.estimate(P02, Package({}), STD) is None  # no should-cost: no floor
    routine = CASES["case:P04"]
    part = routine["parts"][0]
    facts = {"cost:" + part.split(":")[1]: {"part": part, "price_unit": 1, "unit_cost": 4.0}}
    assert relationship.estimate(routine, Package(facts)) is None  # no relationship cost in a routine case


def test_floor_from_the_should_cost_beats_both_recorded_deals(on):
    est = relationship.estimate(P02, Package(SHOULD_COST), STD)
    floor = relationship.floor_price(P02, BEST_STRUCTURE, STD, est)
    at = true_cost({**BEST_STRUCTURE, "unit_price": floor})
    assert at < true_cost(CAREFUL) and at < true_cost(TOO_LOW) and at < true_cost(FAR_TOO_LOW)
    assert score(at) >= 0.85


def _thread_state(sup):
    opening = eco.sheet(P02, {"payment_days": 30, "index_clause": None}, 370.96)
    return {"std": STD, "open": opening, "ask": 370.96, "sup": sup, "ranked": eco.structures(P02, opening, STD)}


def test_agent_never_asks_below_the_floor(on):
    agent = PegasusAgent(Package(SHOULD_COST))
    est = relationship.estimate(P02, agent.pkg, STD)
    low_target = 2_000_000.0  # a C far below anything the supplier can accept
    sheets = agent._sheets(P02, _thread_state(est), low_target)
    assert sheets
    for t in sheets:
        structure = {k: v for k, v in t.items() if k != "unit_price"}
        assert t["unit_price"] >= relationship.floor_price(P02, structure, STD, est)
        assert t["unit_price"] <= 370.96
    without = agent._sheets(P02, _thread_state(None), low_target)
    assert min(t["unit_price"] for t in without) < min(t["unit_price"] for t in sheets)


def test_agent_accepts_the_cheapest_deal_not_the_lowest_price(on):
    offers = [
        {"term_sheet_id": "offer:low", "terms": FAR_TOO_LOW},
        {"term_sheet_id": "offer:careful", "terms": CAREFUL},
    ]
    threads = {SUPPLIER: [{"from": SUPPLIER, "status": "open", "body": "", "term_sheets": offers}]}
    agent = PegasusAgent(Package(SHOULD_COST))
    agent.c_alt = eco.alt_cost(P02)

    def accepted(sup):
        agent.state = {SUPPLIER: {"std": STD, "sup": sup}}
        return agent._accept_best(P02, threads)["message"]["action"]["term_sheet_id"]

    assert accepted(None) == "offer:low"  # on the commercial C alone: the deal that scored 0
    assert accepted(relationship.estimate(P02, agent.pkg, STD)) == "offer:careful"
