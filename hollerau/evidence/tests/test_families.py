"""Claim families quote, scorecard, orders, forecast_cost_news, and signals(), on the 19 practice cases."""

import copy
import json
import math
from pathlib import Path

import pytest

from arena_kit.cost import relationship_cost
from hollerau.contracts import Claim
from hollerau.evidence.compile import compile_evidence
from hollerau.evidence.economics import estimate_supplier, relationship_risk
from hollerau.evidence.facts import check, facts_of, load_package, supplier_price
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


def test_should_cost_cited_below_the_price_the_supplier_wants(data):
    """No margin any more (X9: should-cost taken into account 11/13; P01's 0.998 cited 132.64 against 138.55)."""
    cited = {
        case_id: [
            (c.ids[0], c.figure) for c in run(forecast_cost_news_claims, case_id, data) if c.ids[0].startswith("cost:")
        ]
        for case_id in ("case:P01", "case:P02", "case:P03", "case:P05", "case:P06", "case:P10", "case:P14", "case:P17")
    }
    assert cited["case:P01"] == [("cost:310010", 132.64)]  # asked 138.55 (today 126.53)
    assert cited["case:P06"] == [("cost:310070", 194.18)]
    assert cited["case:P10"] == [("cost:340010", 24.31)]
    assert cited["case:P03"] == [("cost:350020", 403.21)] and cited["case:P14"] == [("cost:350040", 304.49)]
    for case_id in ("case:P02", "case:P05", "case:P17"):  # above what the supplier wants: 374.95, 36.87, 37.24
        assert cited[case_id] == [], case_id


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


def test_d1_relationship_figures_are_reproduced(data):
    """D1 in NOTES.md: 1,430 EUR of relationship cost on the P01 deal (4,055 at a 30-day standard)."""
    session = json.loads((ROOT / "tests/fixtures/sessions/P01-naive.json").read_text())["state"]["result"]
    case, supplier = CASES["case:P01"], estimate_supplier(CASES["case:P01"], data=data)
    assert session["cost_breakdown"]["relationship"] == 0.0
    assert relationship_risk(case, session["terms"], supplier=supplier) == pytest.approx(1430.46, abs=0.01)
    thirty = {**supplier, "standard": {**supplier["standard"], "payment_days": 30}}
    assert relationship_cost(case, session["terms"], None, thirty) == pytest.approx(4055.21, abs=0.01)


# --- fixes after the second /review


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


# --- second review: supplier_price and a letter with a percentage only


@pytest.mark.parametrize("bad", [True, False, math.inf, -math.inf, math.nan, -5.0, 0, "138.55", None])
def test_supplier_price_refuses_what_is_not_a_price(bad):
    case = {"buyer": {"current_unit_price": bad}, "trigger_doc": None}
    assert supplier_price(case, {}) is None


def test_supplier_price_asked_then_current():
    case = {"buyer": {"current_unit_price": 126.53}, "trigger_doc": "doc:L"}
    assert supplier_price(case, {"doc:L": {"asked_price": 138.55}}) == 138.55
    assert supplier_price(case, {"doc:L": {"asked_price": None, "asked_pct": 9.5}}) == 126.53
    assert supplier_price(case, {"doc:L": {"asked_price": math.inf}}) == 126.53  # inf falls back, never cited above


def test_letter_with_a_percentage_only_compares_the_should_cost_with_todays_price(data):
    """P01 with an asked % but no asked price: 132.64 is above today's 126.53, so it is not cited (the stricter side:
    the supplier's target is not known in EUR)."""
    case = copy.deepcopy(CASES["case:P01"])
    case["trigger_doc"] = "doc:PCT-ONLY"
    case["facts"] = {
        "doc:PCT-ONLY": {"supplier": "sup:70110", "date": "2026-09-11", "asked_pct": 9.5, "asked_price": None}
    }
    claims = forecast_cost_news_claims(case, data, facts_of(case, data))
    assert not [c for c in claims if c.ids[0].startswith("cost:")]
    case["buyer"] = {**case["buyer"], "current_unit_price": 140.0}
    assert [
        c.ids for c in forecast_cost_news_claims(case, data, facts_of(case, data)) if c.ids[0].startswith("cost:")
    ] == [["cost:310010"]]
