"""Properties that must hold on a case we have never seen: they check the reasoning, not a score."""

import copy
import json
import random

import pytest
from pegasus_helpers import CASES, opening, supplier

from hollerau.pegasus import agent as agent_module
from hollerau.pegasus import economics as eco
from hollerau.pegasus import memory
from hollerau.pegasus.agent import PegasusAgent

P08 = CASES["case:P08"]
SID = P08["suppliers"][0]
CLAUSE = P08["term_options"]["index_clause"][1]
MONEY = ("current_unit_price", "fallback_unit_price", "late_cost_per_day", "cost_per_defect")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_module, "POLICY", "actions")
    monkeypatch.setattr(agent_module, "TEAM_CLAIMS", False)
    monkeypatch.setattr(memory, "FILE", tmp_path / "memory.json")
    memory._mem.clear()
    yield
    memory._mem.clear()


class Journal:
    def __init__(self):
        self.lines = []

    def write(self, **entry):
        self.lines.append(entry)


def canonical(structures):
    return sorted(json.dumps(s, sort_keys=True) for s in structures)


def test_a_grid_beyond_the_cap_does_not_depend_on_how_the_case_lists_its_options():
    options = {"payment_days": list(range(10, 60)), "contract_months": list(range(1, 51))}  # 2 500 combinations
    case = {**P08, "negotiable": ["unit_price", "payment_days", "contract_months"], "term_options": options}
    rng = random.Random(7)
    shuffled = {**case, "negotiable": ["unit_price", "contract_months", "payment_days"],
                "term_options": {k: rng.sample(v, len(v)) for k, v in options.items()}}
    assert len(eco.grid(case)) == eco.MAX_GRID == len(eco.grid(shuffled))
    assert canonical(eco.grid(case)) == canonical(eco.grid(shuffled))


def test_below_the_cap_the_grid_is_complete_and_in_the_order_of_the_case():
    for case in CASES.values():
        structures = eco.grid(case)
        sizes = [len(case.get("term_options", {}).get(f) or [0]) for f in eco.fields(case)]
        expected = 1
        for n in sizes:
            expected *= n
        assert len(structures) == expected <= 75
        first = {f: (case.get("term_options", {}).get(f) or [structures[0][f]])[0] for f in eco.fields(case)}
        assert structures[0] == first


def scaled(case, k):
    """The same case in another currency unit: every amount of money times `k`."""
    out = copy.deepcopy(case)
    b = out["buyer"]
    for f in MONEY:
        if b.get(f) is not None:
            b[f] *= k
    b["freight_eur_per_unit"] = {i: v * k for i, v in b["freight_eur_per_unit"].items()}
    if (b.get("alternative") or {}).get("terms", {}).get("unit_price"):
        b["alternative"]["terms"]["unit_price"] *= k
    return out


def asks(case, prices, k=1.0):
    """Our unit prices against a supplier that answers with `prices` in turn."""
    agent, threads, out = PegasusAgent(), {SID: [opening(case, SID, 6.05 * k)]}, []
    for n, price in enumerate(prices, 1):
        move = agent.decide(case, threads, SID)
        asked = move["message"]["term_sheets"][0]["terms"]
        out.append(asked["unit_price"])
        threads[SID].append({**move["message"], "from": "buyer"})
        threads[SID].append(supplier(SID, n, {**asked, "unit_price": round(price * k, 2)}, body="We made a step."))
    return out


def test_the_decisions_do_not_depend_on_the_unit_of_money():
    plain = asks(P08, [5.75, 5.70])
    tenfold = asks(scaled(P08, 10), [5.75, 5.70], k=10)
    assert plain[0] == 5.45 and len(plain) == 2
    # the same decisions, to the rounding of a price to the cent in each unit (half a cent, times ten)
    assert tenfold == pytest.approx([p * 10 for p in plain], abs=0.06)


def test_a_fact_added_to_the_case_changes_the_demand_and_is_cited(package, monkeypatch):
    monkeypatch.setattr(agent_module, "TEAM_CLAIMS", True)
    quote = {"type": "quote", "part": P08["parts"][0], "supplier": "sup:79999", "unit_price": 4.95, "price_unit": 1}
    case = {**P08, "refs": [*P08["refs"], "quote:9900001"], "facts": {"quote:9900001": quote}}
    agent = PegasusAgent(package, journal=Journal())
    out = agent.decide(case, {SID: [opening(case, SID, 6.05)]}, SID)
    basis = agent.journal.lines[-1]["considered"][0]["evaluation"]["basis"]
    assert basis["reference"] == "price.quote" and basis["sources"] == ["quote:9900001"]
    assert out["message"]["term_sheets"][0]["terms"]["unit_price"] == 4.95
    assert "quote:9900001" in out["message"].get("refs", [])


def test_what_memory_says_of_a_supplier_is_a_hint_in_the_action_policy(tmp_path, monkeypatch):
    remembered = {SID: {"signals": {"requires_index_clause": 3, "wants_faster_payment": 2}, "stated": {}, "deals": []}}
    (tmp_path / "memory.json").write_text(json.dumps(remembered))
    agent = PegasusAgent(journal=Journal())
    out = agent.decide(P08, {SID: [opening(P08, SID, 6.05)]}, SID)
    sheets = [ts["terms"] for ts in out["message"]["term_sheets"]]
    assert sheets[0]["index_clause"] is None  # it has not asked for a clause in this negotiation
    assert any(s["payment_days"] < sheets[0]["payment_days"] for s in sheets[1:])  # a preference earns a trade
    state = agent.journal.lines[-1]["state"]
    assert "hypothesis: payment.faster" in state["holds"]
    # the remembered clause requirement did not survive its own quote: a fixed price, in this negotiation
    assert state["withdrawn"] == ["index.required: it offered a fixed price for that contract length"]
    memory._mem.clear()
    monkeypatch.setattr(agent_module, "POLICY", "schedule")  # the reference: the same memory is a constraint
    legacy = PegasusAgent().decide(P08, {SID: [opening(P08, SID, 6.05)]}, SID)
    assert all(ts["terms"]["index_clause"] is not None for ts in legacy["message"]["term_sheets"])


@pytest.mark.parametrize("policy", ["schedule", "actions"])
def test_a_supplier_the_package_has_never_heard_of_is_negotiated_with_all_the_same(package, policy, monkeypatch):
    monkeypatch.setattr(agent_module, "POLICY", policy)
    monkeypatch.setattr(agent_module, "TEAM_CLAIMS", True)
    stranger = "sup:99999"
    case = {**P08, "suppliers": [stranger]}
    agent = PegasusAgent(package, journal=Journal())
    threads = {stranger: [opening(case, stranger, 6.05)]}
    out = agent.decide(case, threads, stranger)
    assert out["supplier_id"] == stranger and out["message"]["term_sheets"][0]["terms"]["unit_price"] < 6.05
    if policy == "actions":
        line = agent.journal.lines[-1]
        assert any("absent from the data package" in u for u in line["unknowns"]) and not line["diagnostics"]
    asked = out["message"]["term_sheets"][0]["terms"]
    threads[stranger].append({**out["message"], "from": "buyer"})
    reply = supplier(stranger, 1, {**asked, "unit_price": 5.70, "index_clause": CLAUSE}, "final_offer",
                     "We cannot fix prices over 24 months. This is our final offer.")
    threads[stranger].append(reply)
    assert agent.decide(case, threads, stranger)["message"]["action"]["type"] in ("accept", "walk_away")
