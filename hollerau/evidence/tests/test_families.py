"""Claim families quote, scorecard, orders, forecast_cost_news, and signals(), on the 19 practice cases."""

import copy
import json
from pathlib import Path

import pytest

from hollerau.contracts import Claim
from hollerau.evidence.compile import compile_evidence
from hollerau.evidence.facts import check, facts_of, load_package
from hollerau.evidence.forecast_cost_news import forecast_cost_news_claims
from hollerau.evidence.orders import orders_claims
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
    assert run(scorecard_claims, "case:P01", data) == []  # amber but 712 ppm and 85.2 % on time


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
