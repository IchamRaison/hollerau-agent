"""Offline tests of the common preparation (dossier) and of the single evaluation of an offer."""

from pegasus_helpers import CASES, opening

from arena_kit.cost import closing_terms, complete_offer, total_cost
from hollerau.pegasus import dossier as dossiers
from hollerau.pegasus import evaluation as ev

P02, P05, P08 = CASES["case:P02"], CASES["case:P05"], CASES["case:P08"]
STD_P02 = {"payment_days": 30, "index_clause": None}


def hypothesis(name, full_cost):
    return {"name": name, "provenance": "test",
            "supplier": {"standard": STD_P02, "interest_rate": 0.08, "full_cost": full_cost}}


def sheet(case, price, **terms):
    return complete_offer(case, {**terms, "unit_price": price})


def test_the_commercial_cost_is_the_published_function_and_the_risk_stays_apart():
    terms = sheet(P02, 350.0, payment_days=90, index_clause=None)
    e = ev.evaluate(P02, terms, STD_P02, [hypothesis("low", 360.0), hypothesis("high", 375.0)])
    assert e.valid and e.known
    assert e.commercial == total_cost(P02, closing_terms(P02, terms, STD_P02))  # no estimate inside
    assert [r["name"] for r in e.risks] == ["low", "high"] and e.risks[0]["eur"] < e.risks[1]["eur"]
    assert e.low == e.commercial + e.risks[0]["eur"] and e.cautious == e.commercial + e.risks[1]["eur"]


def test_an_unknown_risk_is_not_a_zero_risk():
    terms = sheet(P02, 350.0, payment_days=90, index_clause=None)
    unknown = ev.evaluate(P02, terms, STD_P02)  # the charge applies, no hypothesis about the supplier
    assert unknown.valid and not unknown.known and unknown.risks == []
    leverage = ev.evaluate(P08, sheet(P08, 5.25), {}, [hypothesis("ignored", 5.0)])
    assert leverage.known and leverage.risks == []  # no relationship charge in a leverage case


def test_a_choice_that_flips_with_the_hypothesis_is_fragile():
    hyps = [hypothesis("low", 340.0), hypothesis("high", 380.0)]
    prices = [330.0 + 2 * i for i in range(30)]
    evals = [ev.evaluate(P02, sheet(P02, p, payment_days=90, index_clause=None), STD_P02, hyps) for p in prices]
    flips = [(a, b) for a in evals for b in evals if ev.fragile(a, b)]
    assert flips, "two hypotheses 40 EUR apart must disagree on some pair of prices"
    same = [ev.evaluate(P02, sheet(P02, p, payment_days=90, index_clause=None), STD_P02, hyps[:1]) for p in prices]
    assert not any(ev.fragile(a, b) for a in same for b in same)  # one hypothesis: nothing to flip


def test_unpriced_or_invalid_sheets_never_win():
    unpriced = ev.evaluate(P08, {"payment_days": 90}, {})
    assert not unpriced.valid and unpriced.commercial == float("inf")
    late = ev.evaluate(P05, sheet(P05, 20.0, lead_time_days=42) | {"lead_time_days": 52}, {})
    assert not late.valid  # breaks the must-have (lead time <= 42 days), however cheap
    good = ev.evaluate(P05, sheet(P05, 30.0, lead_time_days=35), {})
    assert ev.best([("unpriced", unpriced), ("late", late), ("good", good)])[0] == "good"
    assert ev.best([("unpriced", unpriced)]) is None and ev.better(good, late) and not ev.better(late, good)


def test_without_a_package_the_dossier_says_what_it_could_not_read():
    sid = P08["suppliers"][0]
    d = dossiers.prepare(P08, None, sid, [opening(P08, sid, 6.05)])
    assert d.constraints["negotiable"] == P08["negotiable"] and d.alternative["c_alt"] < float("inf")
    assert d.get("price.asked").status == "statement" and d.get("price.current").status == "fact"
    assert any("no data package" in u for u in d.unknowns)
    assert any("reservation price" in u for u in d.unknowns)  # always unknown


def test_the_dossier_puts_facts_statements_and_estimates_side_by_side(package):
    sid = P08["suppliers"][0]
    body = "AS-14404 rose 5.9 % in twelve months and is 45 % of our cost."
    d = dossiers.prepare(P08, package, sid, [opening(P08, sid, 6.05, body=body)])
    low = d.get("price.orders_low")
    assert low.status == "fact" and low.value < d.get("price.current").value and low.sources[0].startswith("po:")
    assert d.get("price.cost_justified").status == "estimate"
    assert d.get("driver.AS-14404").status == "statement" and d.get("driver.AS-14404").value["share_pct"] == 45.0
    assert d.has("supplier.material_hedged") and d.get("supplier.material_hedged").sources
    assert {lv["field"] for lv in d.levers} >= {"index_clause", "payment_days"}  # the evidence lane's levers
    assert [p for p, _ in dossiers.price_references(d)] == sorted(p for p, _ in dossiers.price_references(d))
    assert d.hypotheses == [] and not d.diagnostics


def test_a_strategic_case_carries_two_cost_hypotheses_with_their_provenance(package):
    sid = P02["suppliers"][0]
    d = dossiers.prepare(P02, package, sid, [opening(P02, sid, 370.96)], STD_P02)
    assert [h["name"] for h in d.hypotheses] == ["should_cost_calibrated", "should_cost_raw"]
    calibrated, raw = (h["supplier"]["full_cost"] for h in d.hypotheses)
    assert calibrated < raw and all(h["provenance"] for h in d.hypotheses)
    assert "standard" not in d.to_dict()["hypotheses"][0]["supplier"]  # the journal keeps the numbers


def test_a_supplier_absent_from_the_package_is_an_unknown_not_a_crash(package):
    case = {**P08, "suppliers": ["sup:99999"]}
    d = dossiers.prepare(case, package, "sup:99999", [opening(case, "sup:99999", 6.05)])
    assert [i for i in d.situation if i.status == "estimate"] == []  # no note to read about it
    assert d.get("price.orders_low") is None and not d.diagnostics
    assert any("absent from the data package" in u for u in d.unknowns)
