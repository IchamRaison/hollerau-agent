"""compile_case on the 19 practice cases (tests/fixtures/cases/practice.json), plan in PLAN-compile_case.md."""

import copy
import itertools
import json
import logging
import math
from pathlib import Path

import pytest

from arena_kit.cost import complete_offer, cost_breakdown, total_cost
from hollerau.evidence.economics import compile_case, estimate_supplier, lever_price, relationship_risk
from hollerau.evidence.facts import asked_price, facts_of, load_package

ROOT = Path(__file__).resolve().parents[3]
CASES = {c["case_id"]: c for c in json.loads((ROOT / "tests/fixtures/cases/practice.json").read_text())}
SESSION = json.loads((ROOT / "tests/fixtures/sessions/P01-naive.json").read_text())


@pytest.fixture(scope="module")
def data():
    try:
        return load_package()
    except FileNotFoundError:
        pytest.skip("no data package: run `uv run arena data` or set ARENA_DATA")


def priced(econ, terms):
    return {**terms, "unit_price": econ.reference_price}


def p01_standard():
    """The supplier's standard terms of the P01 session: deal fields neither negotiable nor fixed by the case
    (the quote PDF itself is not stored in the fixture)."""
    case, deal = CASES["case:P01"], SESSION["state"]["result"]["terms"]
    return {k: v for k, v in deal.items() if k not in case["negotiable"] and k not in case["fixed_terms"]}


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_every_case_compiles(case_id):
    case = CASES[case_id]
    econ = compile_case(case)
    assert econ.case_id == case_id
    asked = asked_price(case, facts_of(case))
    assert econ.reference_price == (asked or case["buyer"]["current_unit_price"])
    best = priced(econ, econ.best_package)
    assert "unit_price" not in econ.best_package
    assert econ.must_haves_ok(best)
    reference = complete_offer(case, {"unit_price": econ.reference_price})
    if econ.must_haves_ok(reference):
        assert econ.cost(best) <= econ.cost(reference)


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_levers_sorted_and_allowed(case_id):
    case = CASES[case_id]
    econ = compile_case(case)
    losses = [lv.cost_of_forgetting_eur for lv in econ.levers]
    assert losses == sorted(losses, reverse=True)
    assert {lv.field for lv in econ.levers} == {f for f in case["negotiable"] if f != "unit_price"}
    for lv in econ.levers:
        options = case["term_options"][lv.field]
        assert lv.best in options and lv.worst in options
        assert lv.best == econ.best_package[lv.field]
        for value in (lv.best, lv.worst):
            assert econ.must_haves_ok(priced(econ, {**econ.best_package, lv.field: value}))
        assert lv.cost_of_forgetting_eur >= 0


def test_best_package_is_the_grid_minimum():
    """P03: exhaustive check of the 5 x 3 x 3 grid."""
    case = CASES["case:P03"]
    econ = compile_case(case)
    fields = [f for f in case["negotiable"] if f != "unit_price"]
    costs = [
        econ.cost(priced(econ, dict(zip(fields, combo, strict=True))))
        for combo in itertools.product(*(case["term_options"][f] for f in fields))
    ]
    assert econ.cost(priced(econ, econ.best_package)) == min(costs)


@pytest.mark.parametrize(
    ("case_id", "field", "ok"),
    [
        ("case:P05", "lead_time_days", lambda v: v <= 42),
        ("case:P10", "volume_per_year", lambda v: v >= 22230),
        ("case:P11", "ppm_commitment", lambda v: v <= 1500),
    ],
)
def test_must_haves_hold(case_id, field, ok):
    econ = compile_case(CASES[case_id])
    assert ok(econ.best_package[field])
    lever = next(lv for lv in econ.levers if lv.field == field)
    assert ok(lever.best) and ok(lever.worst)


def test_no_valid_package_warns_and_returns_the_cheapest(caplog):
    """Never raise (golden rule): the cheapest combination, a warning, and must_haves_ok says it is not compatible."""
    case = copy.deepcopy(CASES["case:P05"])
    case["buyer"]["must_haves"] = [{"field": "lead_time_days", "op": "<=", "value": 1}]
    with caplog.at_level(logging.WARNING):
        econ = compile_case(case)
    assert "no combination" in caplog.text
    assert econ.best_package and not econ.must_haves_ok(priced(econ, econ.best_package))


@pytest.mark.parametrize("case_id", ["case:P05", "case:P06", "case:P10", "case:P14", "case:P17"])
def test_no_alternative_costs_infinity(case_id):
    assert compile_case(CASES[case_id]).c_alt == math.inf


def test_current_contract_alternative_is_costed():
    case = CASES["case:P07"]
    assert case["buyer"]["alternative"]["kind"] == "current_contract"
    econ = compile_case(case)
    assert econ.c_alt == total_cost(case, case["buyer"]["alternative"]["terms"])
    assert math.isfinite(econ.c_alt)


def test_alternative_without_price_costs_infinity():
    case = copy.deepcopy(CASES["case:P01"])
    case["buyer"]["alternative"]["terms"].pop("unit_price")
    assert compile_case(case).c_alt == math.inf


def test_two_year_horizon_prefers_covering_it():
    """P03: 12 months leave a year of need at the fallback price plus its risk."""
    case = CASES["case:P03"]
    econ = compile_case(case)
    assert econ.best_package["contract_months"] == 24  # 36 is beyond the horizon: neither costs nor earns
    short = priced(econ, {**econ.best_package, "contract_months": 12})
    b = case["buyer"]
    parts = cost_breakdown(case, short)
    assert parts["uncovered_need"] == pytest.approx(b["need_per_year"] * b["fallback_unit_price"])
    assert parts["fallback_risk"] == pytest.approx(parts["uncovered_need"] * b["fallback_risk_pct"] / 100)
    assert econ.cost(short) > econ.cost(priced(econ, econ.best_package))


def test_d3_levers_valued_at_the_asked_price(data):
    """P01: the letter asks 138.55; a later effective date keeps 126.53 on the units bought before it."""
    case = CASES["case:P01"]
    econ = compile_case(case, data=data)
    assert econ.reference_price == 138.55
    base = priced(econ, {**econ.best_package, "effective_date": "2026-11-01"})
    gain_jan = econ.cost(base) - econ.cost({**base, "effective_date": "2027-01-01"})
    gain_apr = econ.cost(base) - econ.cost({**base, "effective_date": "2027-04-01"})
    assert gain_jan == pytest.approx(16_000, rel=0.1)
    assert gain_apr == pytest.approx(40_000, rel=0.1)
    ranks = [lv.field for lv in econ.levers]
    assert ranks.index("effective_date") <= 1
    lever = econ.levers[ranks.index("effective_date")]
    assert (lever.best, lever.worst) == ("2027-04-01", "2026-11-01")
    assert lever.cost_of_forgetting_eur == pytest.approx(gain_apr, abs=0.01)


def test_d3_falls_back_to_the_current_price():
    """No price letter (P03 renewal), or a hidden case whose letter gives no asked_price."""
    assert lever_price(CASES["case:P03"]) == CASES["case:P03"]["buyer"]["current_unit_price"]
    case = copy.deepcopy(CASES["case:P01"])
    case["trigger_doc"] = "doc:HIDDEN-X"
    case["facts"] = {"doc:HIDDEN-X": {"supplier": "sup:70110", "days": 20, "asked_price": None}}
    assert lever_price(case) == 126.53


def test_d3_hidden_case_asked_price():
    case = copy.deepcopy(CASES["case:P01"])
    case["trigger_doc"] = "doc:HIDDEN-X"
    case["facts"] = {"doc:HIDDEN-X": {"supplier": "sup:70110", "days": 20, "asked_price": 140.0}}
    assert compile_case(case).reference_price == 140.0


def test_should_cost_is_per_price_unit_like_the_case(data):
    """P14 (motor cable, priced per 100): should-cost 304.49 per 100 against a case price of 316.35 per 100."""
    supplier = estimate_supplier(CASES["case:P14"], data=data)
    assert supplier["full_cost"] == 304.49 and not supplier["estimated"]


def test_relationship_risk_is_a_warning_not_cost(data):
    case = CASES["case:P01"]
    supplier = estimate_supplier(case, data=data)
    assert supplier["full_cost"] == 132.64 and not supplier["estimated"]  # should-cost cost:310010
    terms = complete_offer(case, {"unit_price": 126.53})
    assert relationship_risk(case, terms, supplier=supplier) > 0  # below its full cost
    assert compile_case(case).cost(terms) == total_cost(case, terms)  # arena C: no relationship term


def test_supplier_estimate_without_should_cost(data):
    case = CASES["case:P04"]  # no cost:360020 in the package
    supplier = estimate_supplier(case, data=data)
    assert supplier["estimated"]
    assert supplier["full_cost"] == pytest.approx(4.39)  # routine case: no sustainable margin
    assert supplier["interest_rate"] == case["buyer"]["interest_rate"]


def test_quote_standard_terms_change_quality_cost():
    case, std = CASES["case:P01"], p01_standard()
    assert std["ppm_commitment"] == 900
    terms = {k: SESSION["state"]["result"]["terms"][k] for k in case["negotiable"]}
    gap = compile_case(case, std).cost(terms) - compile_case(case).cost(terms)
    assert gap == pytest.approx(SESSION["state"]["result"]["cost_breakdown"]["quality"], abs=0.01)


def test_p01_session_cross_check():
    """We count like the arena: the recorded deal, completed with the quote's standard terms."""
    case, result = CASES["case:P01"], SESSION["state"]["result"]
    econ = compile_case(case, p01_standard())
    terms = {k: result["terms"][k] for k in case["negotiable"]}
    assert econ.cost(terms) == pytest.approx(result["c_deal"], abs=0.01)
    assert econ.cost(result["terms"]) == pytest.approx(result["c_deal"], abs=0.01)
    assert econ.c_alt == pytest.approx(result["c_alt"], abs=0.01)
    assert econ.must_haves_ok(terms) == result["must_haves_ok"]


def test_missing_price_is_infinite_and_levers_survive():
    case = copy.deepcopy(CASES["case:P01"])
    case["buyer"]["current_unit_price"] = None
    case["trigger_doc"] = None
    econ = compile_case(case)
    assert econ.cost({"payment_days": 60}) == math.inf
    assert econ.reference_price == case["buyer"]["fallback_unit_price"]
    assert {lv.field for lv in econ.levers} == {"effective_date", "payment_days"}


def test_field_without_options_warns(caplog):
    case = copy.deepcopy(CASES["case:P01"])
    del case["term_options"]["payment_days"]
    with caplog.at_level(logging.WARNING):
        econ = compile_case(case)
    assert "payment_days" in caplog.text and "case:P01" in caplog.text
    assert [lv.field for lv in econ.levers] == ["effective_date"]
    assert econ.best_package["payment_days"] == case["buyer"]["reference_payment_days"]  # buyer's plan
