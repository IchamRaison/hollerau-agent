"""Claim families quote, scorecard, orders, forecast_cost_news, and signals(), on the 19 practice cases."""

import copy
import json
import logging
from pathlib import Path

import pytest

from arena_kit.cost import relationship_cost
from hollerau.contracts import Claim
from hollerau.evidence.compile import compile_evidence
from hollerau.evidence.economics import compile_case, estimate_supplier, relationship_risk
from hollerau.evidence.facts import check, facts_of, load_package
from hollerau.evidence.forecast_cost_news import forecast_cost_news_claims
from hollerau.evidence.orders import RAISED_PCT, orders_claims
from hollerau.evidence.quote import quote_claims
from hollerau.evidence.scorecard import scorecard_claims
from hollerau.evidence.signals import signals

ROOT = Path(__file__).resolve().parents[3]
CASES = {c["case_id"]: c for c in json.loads((ROOT / "tests/fixtures/cases/practice.json").read_text())}


@pytest.fixture(scope="module")
def data():
    try:
        return load_package()
    except FileNotFoundError:
        pytest.skip("no data package: run `uv run arena data` or set ARENA_DATA")


def run(family, case_id, data):
    case = CASES[case_id]
    facts = facts_of(case, data)
    claims = family(case, data, facts)
    for c in claims:
        assert check(c, facts), c
        assert all(i in c.sentence for i in c.ids), c
    return claims


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_every_family_claim_is_verifiable(data, case_id):
    case = CASES[case_id]
    facts = facts_of(case, data)
    raw = [
        c
        for f in (quote_claims, scorecard_claims, orders_claims, forecast_cost_news_claims)
        for c in f(case, data, facts)
    ]
    assert all(check(c, facts) for c in raw), [c for c in raw if not check(c, facts)]
    claims = compile_evidence(case, data)
    ids = [i for c in claims for i in c.ids]
    assert len(ids) == len(set(ids))


# --- quote


def test_rival_quote_above_the_stake_is_not_cited(data):
    """P01: the second source quotes 143.22 against 138.55 asked: it argues the supplier's case."""
    assert run(quote_claims, "case:P01", data) == []


def test_cheaper_rival_quote_is_cited(data):
    case = copy.deepcopy(CASES["case:P01"])
    case["refs"].append("quote:HIDDEN-1")
    case["facts"] = {"quote:HIDDEN-1": {"part": "part:310010", "supplier": "sup:70140", "unit_price": 121.0}}
    facts = facts_of(case, data)
    [c] = quote_claims(case, data, facts)
    assert c.ids == ["quote:HIDDEN-1"] and c.figure == 121.0 and c.unit == "EUR" and check(c, facts)


def test_rival_between_current_and_asked_is_not_cited(data):
    """131 is below the 138.55 asked but above today's 126.53: it would anchor the supplier above today's price."""
    case = copy.deepcopy(CASES["case:P01"])
    case["refs"].append("quote:HIDDEN-1")
    case["facts"] = {"quote:HIDDEN-1": {"part": "part:310010", "supplier": "sup:70140", "unit_price": 131.0}}
    assert quote_claims(case, data, facts_of(case, data)) == []


def test_quote_of_another_part_is_not_cited(data):
    case = copy.deepcopy(CASES["case:P01"])
    case["refs"].append("quote:HIDDEN-2")
    case["facts"] = {"quote:HIDDEN-2": {"part": "part:999999", "supplier": "sup:70140", "unit_price": 1.0}}
    assert quote_claims(case, data, facts_of(case, data)) == []


# --- scorecard


def test_p11_red_card_quality_first(data):
    claims = run(scorecard_claims, "case:P11", data)
    assert claims[0].ids == ["sc:70140@2026Q3"] and claims[0].unit == "ppm" and claims[0].figure == 2376
    assert claims[0].supports == "quality"


def test_p09_delivery_card(data):
    [c] = run(scorecard_claims, "case:P09", data)
    assert c.ids == ["sc:70220@2026Q3"] and c.unit == "%" and c.figure == 56.0


def test_green_card_is_not_cited(data):
    assert run(scorecard_claims, "case:P02", data) == []  # green, 273 ppm


def test_scorecard_check_uses_the_mean():
    facts = {"sc:1@Q1": {"ppm": 1000, "otd_pct": 80.0}, "sc:1@Q2": {"ppm": 2000, "otd_pct": 60.0}}
    claim = Claim("scorecard", ["sc:1@Q1", "sc:1@Q2"], 1500.0, "ppm", "", "quality")
    assert check(claim, facts)
    assert not check(Claim("scorecard", ["sc:1@Q1", "sc:1@Q2"], 2000.0, "ppm", "", "quality"), facts)
    assert check(Claim("scorecard", ["sc:1@Q1", "sc:1@Q2"], 70.0, "%", "", "other"), facts)


# --- orders


def test_p14_orders_show_the_price_already_rose(data):
    [c] = run(orders_claims, "case:P14", data)
    facts = facts_of(CASES["case:P14"], data)
    first, last = (facts[i] for i in c.ids)
    assert first["part"] == last["part"] == "part:350040"
    assert last["unit_price"] == 316.35 and last["unit_price"] > first["unit_price"] * 1.03
    assert c.figure is None and "per 100 pcs" in c.sentence


def test_orders_without_a_rise_are_not_cited(data):
    assert run(orders_claims, "case:P01", data) == []  # 128.27 -> 126.53: it fell


def test_orders_check_needs_one_part():
    facts = {"po:1": {"part": "part:1", "unit_price": 1.0}, "po:2": {"part": "part:2", "unit_price": 1.0}}
    assert not check(Claim("orders", ["po:1", "po:2"], None, "", "", "price"), facts)
    assert not check(Claim("orders", ["po:1"], None, "", "", "price"), {"po:1": facts["po:1"]})


# --- forecast_cost_news


def test_should_cost_cited_only_with_room(data):
    p06 = [c for c in run(forecast_cost_news_claims, "case:P06", data) if c.ids[0].startswith("cost:")]
    assert [c.ids for c in p06] == [["cost:310070"]] and p06[0].figure == 194.18
    for case_id in ("case:P01", "case:P02", "case:P03", "case:P14"):  # within the should-cost's 15 % error
        claims = run(forecast_cost_news_claims, case_id, data)
        assert not [c for c in claims if c.ids[0].startswith("cost:")], case_id


def test_forecast_growth_is_cited(data):
    [fc] = [c for c in run(forecast_cost_news_claims, "case:P01", data) if c.ids[0].startswith("fc:")]
    assert fc.ids == ["fc:310010@2026-09"] and fc.figure == 10.1 and fc.supports == "volume"


def test_news_only_when_it_weakens_the_supplier(data):
    p05 = [c for c in run(forecast_cost_news_claims, "case:P05", data) if c.ids[0].startswith("news:")]
    assert [c.ids for c in p05] == [["news:20260309-03"]]  # free capacity; not full_order_book (70240)
    p11 = run(forecast_cost_news_claims, "case:P11", data)
    assert not [c for c in p11 if c.ids[0].startswith("news:")]  # restructuring: not ours to cite


def test_fcn_check_rejects_a_wrong_figure():
    facts = {"fc:1@2026-09": {"change_pct": 10.0}, "cost:1": {"unit_cost": 100.0}, "news:1": {"supplier": "sup:1"}}
    assert check(Claim("forecast_cost_news", ["fc:1@2026-09"], 10.4, "%", "", "volume"), facts)
    assert not check(Claim("forecast_cost_news", ["fc:1@2026-09"], 11.0, "%", "", "volume"), facts)
    assert not check(Claim("forecast_cost_news", ["cost:1"], 101.0, "EUR", "", "price"), facts)
    assert not check(Claim("forecast_cost_news", ["news:1"], 1.0, "", "", "other"), facts)


# --- compile order


def test_p01_strongest_first(data):
    families = [c.family for c in compile_evidence(CASES["case:P01"], data)]
    assert families[0] == "notice" and families.index("index") < families.index("forecast_cost_news")


# --- signals


def test_signals_p02_increase_justified(data):
    s = signals(CASES["case:P02"], data)
    assert s["increase_justified"] is True and s["weighted_index_pct"]["part:350011"] > s["asked_pct"]
    assert signals(CASES["case:P01"], data)["increase_justified"] is False
    assert signals(CASES["case:P03"], data)["increase_justified"] is None  # no price letter


def test_signals_material_hedged(data):
    for case_id, sup in (("case:P08", "sup:70710"), ("case:P14", "sup:70560")):
        s = signals(CASES[case_id], data)["suppliers"][sup]
        assert s["material_hedged_until"] == "March 2027" and s["material_hedged"], case_id


def test_signals_p11_cash_need(data):
    s = signals(CASES["case:P11"], data)["suppliers"]["sup:70140"]
    assert "doc:20260715-70140-M1" in s["cash_need"]


def test_signals_committee_capacity_single_source_payments(data):
    p17 = signals(CASES["case:P17"], data)["suppliers"]["sup:70550"]
    assert p17["committee_above_pct"] == 2.0 and p17["single_source"] is True
    p01 = signals(CASES["case:P01"], data)["suppliers"]["sup:70110"]
    assert p01["single_source"] is False  # sup:70140 is qualified for part:310010
    assert signals(CASES["case:P19"], data)["suppliers"]["sup:70640"]["free_capacity"]
    pay = p01["our_late_payments"]
    assert pay["invoices"] > 0 and 0 <= pay["late_share"] <= 1


def test_signals_read_notes_up_to_the_case_start(data):
    """Notes after the supplier's letter but before the case starts count; none after the start."""
    case = copy.deepcopy(CASES["case:P01"])
    case["start_date"] = "2026-09-10"  # an explicit case start bounds the window
    early = signals(case, data)["suppliers"]["sup:70110"]
    ids = [i for v in early.values() if isinstance(v, list) for i in v]
    assert all(i.split(":")[1][:8] <= "20260910" for i in ids if i.startswith("doc:"))
    late = signals(CASES["case:P01"], data)["suppliers"]["sup:70110"]  # start = latest fact date
    assert "doc:20260902-70110-M2" in late["cash_need"]


# --- supplier letter (material covered) and orders without a price letter


def hedge_letters(claims):
    """forecast_cost_news claims citing a supplier `doc` (the material-covered letter)."""
    return [c for c in claims if c.family == "forecast_cost_news" and c.ids[0].startswith("doc:")]


def test_p08_raw_material_gets_letter_and_orders(data):
    case = CASES["case:P08"]  # no asked_price: the supplier proposes an index clause
    claims = compile_evidence(case, data)
    assert len(claims) >= 2
    [letter] = hedge_letters(claims)
    assert letter.ids == ["doc:20260706-70710-M1"] and letter.figure is None and letter.supports == "price"
    assert "March 2027" in letter.sentence
    [orders] = [c for c in claims if c.family == "orders"]
    facts = facts_of(case, data)
    assert all(facts[i]["unit_price"] <= case["buyer"]["current_unit_price"] for i in orders.ids)
    assert orders.supports == "price"


def test_hedge_letter_needs_no_price_letter(data):
    case = copy.deepcopy(CASES["case:P08"])
    case["trigger_doc"] = "doc:HIDDEN-P08"
    case["facts"] = {"doc:HIDDEN-P08": {"supplier": "sup:70710", "date": "2026-09-12", "asked_price": 5.9}}
    assert hedge_letters(compile_evidence(case, data)) == []  # a price letter: not this case


def test_call_notes_are_never_cited_as_letters(data):
    """P14: the copper cover comes from our own call note (context, not a check)."""
    assert hedge_letters(compile_evidence(CASES["case:P14"], data)) == []


def test_supplier_letter_check():
    facts = {"doc:1": {"type": "letter"}, "doc:2": {"type": "call_note"}}
    assert check(Claim("forecast_cost_news", ["doc:1"], None, "", "", "other"), facts)
    assert not check(Claim("forecast_cost_news", ["doc:1"], 1.0, "", "", "other"), facts)
    assert not check(Claim("forecast_cost_news", ["doc:2"], None, "", "", "other"), facts)


@pytest.mark.parametrize("case_id", ["case:P03", "case:P18"])
def test_orders_without_a_price_letter_stay_at_or_below_today(data, case_id):
    case = CASES[case_id]
    facts = facts_of(case, data)
    [orders] = [c for c in compile_evidence(case, data) if c.family == "orders"]
    assert len({facts[i]["part"] for i in orders.ids}) == 1
    assert all(facts[i]["unit_price"] <= case["buyer"]["current_unit_price"] for i in orders.ids)
    low, last = (facts[i]["unit_price"] for i in orders.ids)
    assert (last / low - 1) * 100 >= RAISED_PCT  # the price rose by 3 % or more


def test_p04_rise_below_three_percent_is_not_cited(data):
    """Review fix: 4.29 -> 4.39 is +2.3 %, below RAISED_PCT (X9 measured rises of 5.4 % and 11 %)."""
    assert [c for c in compile_evidence(CASES["case:P04"], data) if c.family == "orders"] == []


@pytest.mark.parametrize("case_id", ["case:P09", "case:P10", "case:P11", "case:P12", "case:P16"])
def test_no_orders_claim_when_the_price_did_not_rise(data, case_id):
    """Their lowest recent order is at today's price: two orders at one price, 0 effect out of 24 (X9)."""
    assert [c for c in compile_evidence(CASES[case_id], data) if c.family == "orders"] == []


def test_no_orders_claim_in_a_bundle(data):
    for case_id in ("case:P07", "case:P15"):
        assert [c for c in compile_evidence(CASES[case_id], data) if c.family == "orders"] == []


# --- price floor hint


def test_p02_price_floor_hint(data):
    case = CASES["case:P02"]
    floor = signals(case, data)["price_floor_hint"]
    assert floor == pytest.approx(365, abs=3)  # 366.87: below it the relationship cost outgrows the saving
    econ, supplier = compile_case(case, data=data), estimate_supplier(case, data=data)

    def total(p):
        t = {**econ.best_package, "unit_price": p}
        return econ.cost(t) + relationship_risk(case, t, supplier=supplier)

    assert total(floor) <= min(total(floor - 1), total(floor + 1), total(floor - 0.01), total(floor + 0.01))


def test_price_floor_never_above_the_asked_or_current_price(data):
    """P03 (renewal, no price letter): capped at today's 412.74 (424.75 uncapped). P01: at most the 138.55 asked."""
    assert signals(CASES["case:P03"], data)["price_floor_hint"] <= 412.74
    for case_id in ("case:P01", "case:P02", "case:P06", "case:P09", "case:P10", "case:P14", "case:P17"):
        s, case = signals(CASES[case_id], data), CASES[case_id]
        assert s["price_floor_hint"] <= (s["asked_price"] or case["buyer"]["current_unit_price"]), case_id


def test_price_floor_confidence_is_low_with_its_reason(data):
    s = signals(CASES["case:P02"], data)
    assert s["price_floor_confidence"] == "low"
    assert "P01" in s["price_floor_reason"] and "135.40" in s["price_floor_reason"]
    routine = signals(CASES["case:P04"], data)
    assert routine["price_floor_confidence"] is None and routine["price_floor_reason"] is None


def test_price_floor_reason_figures_are_reproduced(data):
    """The figures quoted in the reason: 1,430 EUR of relationship cost on the P01 deal (4,055 at a 30-day standard)."""
    session = json.loads((ROOT / "tests/fixtures/sessions/P01-naive.json").read_text())["state"]["result"]
    case, supplier = CASES["case:P01"], estimate_supplier(CASES["case:P01"], data=data)
    assert session["cost_breakdown"]["relationship"] == 0.0
    assert relationship_risk(case, session["terms"], supplier=supplier) == pytest.approx(1430.46, abs=0.01)
    thirty = {**supplier, "standard": {**supplier["standard"], "payment_days": 30}}
    assert relationship_cost(case, session["terms"], None, thirty) == pytest.approx(4055.21, abs=0.01)


def test_price_floor_only_for_relationship_goals(data):
    assert signals(CASES["case:P04"], data)["price_floor_hint"] is None  # routine
    assert signals(CASES["case:P08"], data)["price_floor_hint"] is None  # leverage


# --- fixes after the second /review


def test_floor_none_when_cost_cannot_be_computed(data, caplog):
    from hollerau.evidence.signals import NO_COST

    case = copy.deepcopy(CASES["case:P02"])
    case["buyer"].pop("fallback_unit_price")  # every C is infinite
    with caplog.at_level(logging.ERROR):
        s = signals(case, data)
    assert s["price_floor_hint"] is None and s["price_floor_confidence"] is None
    assert s["price_floor_reason"] == NO_COST
    assert len(caplog.records) < 10  # no longer one traceback per grid point (501 before)


def test_floor_none_when_the_minimum_stays_on_the_edge(data):
    case = copy.deepcopy(CASES["case:P02"])
    case["buyer"]["relationship_eur_per_point"] = 1  # the relationship hardly costs: the minimum is the lowest price
    s = signals(case, data)
    assert s["price_floor_hint"] is None and s["price_floor_reason"].startswith("edge")


@pytest.mark.parametrize(
    "case_id", ["case:P01", "case:P02", "case:P03", "case:P06", "case:P09", "case:P10", "case:P14", "case:P17"]
)
def test_floor_is_never_the_grid_edge(data, case_id):
    """P06 used to report 202.36, below the 0.8 x current edge (202.55): widening finds 196.31 inside the grid."""
    from hollerau.evidence.signals import FLOOR_LOWS

    case = CASES[case_id]
    floor = signals(case, data)["price_floor_hint"]
    assert floor is not None and floor > FLOOR_LOWS[-1] * case["buyer"]["current_unit_price"]
    econ, supplier = compile_case(case, data=data), estimate_supplier(case, data=data)

    def total(p):
        t = {**econ.best_package, "unit_price": p}
        return econ.cost(t) + relationship_risk(case, t, supplier=supplier)

    cap = signals(case, data)["asked_price"] or case["buyer"]["current_unit_price"]
    if floor < cap:  # an interior minimum, not the cap
        assert total(floor) <= min(total(round(floor - 0.01, 2)), total(round(floor + 0.01, 2)))


def test_hedge_letter_needs_cover_beyond_the_effective_date(data):
    case = copy.deepcopy(CASES["case:P08"])
    case["fixed_terms"]["effective_date"] = "2027-04-01"  # the cover ends in March 2027
    assert hedge_letters(compile_evidence(case, data)) == []


def test_hedge_letter_not_when_the_index_falls(data):
    case = copy.deepcopy(CASES["case:P08"])
    case["buyer"]["index_paths"] = {"AS-14404": -0.10}
    assert hedge_letters(compile_evidence(case, data)) == []


def test_asked_pct_alone_is_a_price_letter(data):
    """A letter with an asked % but no asked price: no hedge letter, no held-price orders."""
    case = copy.deepcopy(CASES["case:P08"])
    case["trigger_doc"] = "doc:HIDDEN-P08"
    case["facts"] = {
        "doc:HIDDEN-P08": {"supplier": "sup:70710", "date": "2026-09-12", "asked_pct": 8.0, "asked_price": None}
    }
    claims = compile_evidence(case, data)
    assert hedge_letters(claims) == [] and [c for c in claims if c.family == "orders"] == []


def test_no_orders_in_an_rfq(data):
    case = copy.deepcopy(CASES["case:P03"])  # has orders normally
    assert orders_claims(case, data, facts_of(case, data))
    case["type"] = "rfq"
    assert orders_claims(case, data, facts_of(case, data)) == []


def test_orders_without_buyer_keep_the_rise_claim(data):
    case = copy.deepcopy(CASES["case:P14"])
    del case["buyer"]
    [c] = orders_claims(case, data, facts_of(case, data))
    assert "already went from" in c.sentence


def test_one_failing_sub_family_keeps_the_others(data, monkeypatch):
    from hollerau.evidence import forecast_cost_news as fcn

    def boom(*args):
        raise RuntimeError("letter broken")

    monkeypatch.setattr(fcn, "letter_claims", boom)
    case = CASES["case:P01"]
    claims = fcn.forecast_cost_news_claims(case, data, facts_of(case, data))
    assert ids_of_prefix(claims, "fc:") == ["fc:310010@2026-09"]


def ids_of_prefix(claims, prefix):
    return [c.ids[0] for c in claims if c.ids[0].startswith(prefix)]


def test_amber_card_weak_on_both_counts_is_cited(data):
    """P01: amber, 85.2 % on time and 712 ppm - neither past the strong limits, both weak at once."""
    [c] = run(scorecard_claims, "case:P01", data)
    assert c.ids == ["sc:70110@2026Q3"] and c.unit == "%" and c.figure == 85.2 and c.supports == "other"


def test_amber_card_weak_on_one_count_only_is_not_cited(data):
    case = copy.deepcopy(CASES["case:P01"])
    case["facts"] = {"sc:70110@2026Q4": {"supplier": "sup:70110", "ppm": 400, "otd_pct": 85.0, "colour": "amber"}}
    assert scorecard_claims(case, data, facts_of(case, data)) == []  # 400 ppm: quality is fine
    case["facts"]["sc:70110@2026Q4"] |= {"ppm": 712, "otd_pct": 91.0}
    assert scorecard_claims(case, data, facts_of(case, data)) == []  # 91 % on time: delivery is fine
