"""adapter.pegasus_claims and adapter.planner_hints on the 10 hosted practice cases."""

import copy
import json
from pathlib import Path

import pytest

from hollerau.evidence.adapter import pegasus_claims, planner_hints
from hollerau.evidence.economics import lever_price
from hollerau.evidence.facts import check, facts_of, load_package
from hollerau.pegasus.claims import Claims

ROOT = Path(__file__).resolve().parents[3]
CASES = {c["case_id"]: c for c in json.loads((ROOT / "tests/fixtures/cases/practice.json").read_text())}
HOSTED = sorted(cid for cid, c in CASES.items() if c.get("hosted"))


@pytest.fixture(scope="module")
def data():
    try:
        return load_package()
    except FileNotFoundError:
        pytest.skip("no data package: run `uv run arena data` or set ARENA_DATA")


def raw(case, data):
    """Every Pegasus candidate of the case at our lever price, as its agent would build them."""
    gen, price = Claims(case, data), lever_price(case, data)
    return [c for s in case["suppliers"] for p in case["parts"] for c in gen.candidates(s, p, price)]


def ids(claims):
    return [i for c in claims for i in c.ids]


@pytest.mark.parametrize("case_id", HOSTED)
def test_union_is_checked_unique_and_ranked(data, case_id):
    case = CASES[case_id]
    out = pegasus_claims(case, data, raw(case, data))
    facts = facts_of(case, data)
    assert all(check(c, facts) for c in out)
    assert len(ids(out)) == len(set(ids(out)))
    ranks = [["notice", "quote", "scorecard", "index", "orders", "forecast_cost_news"].index(c.family) for c in out]
    assert ranks == sorted(ranks)


def test_p01_drops_the_should_cost_above_todays_price(data):
    case = CASES["case:P01"]
    candidates = raw(case, data)
    assert any("cost:310010" in c["refs"] for c in candidates)  # Pegasus would send it
    assert "cost:310010" not in ids(pegasus_claims(case, data, candidates))  # 132.64 against 126.53 today


@pytest.mark.parametrize("case_id", ["case:P09", "case:P10"])
def test_no_volume_claim_in_capacity_cases(data, case_id):
    case = CASES[case_id]
    candidates = raw(case, data)
    assert any(r.startswith("fc:") for c in candidates for r in c["refs"])  # Pegasus would send one
    assert not [i for i in ids(pegasus_claims(case, data, candidates)) if i.startswith("fc:")]


def test_scorecards_only_past_our_thresholds(data):
    case = CASES["case:P03"]  # green card, 84.6 % on time: Pegasus cites it, we do not
    out = pegasus_claims(case, data, raw(case, data))
    assert not [i for i in ids(out) if i.startswith("sc:")]
    p01 = pegasus_claims(CASES["case:P01"], data, raw(CASES["case:P01"], data))
    assert "sc:70110@2026Q3" in ids(p01)  # amber, weak on both counts: ours cites it too


def test_rival_offer_passes_through_and_ranks_high(data):
    case = CASES["case:P05"]
    rival = Claims(case, data).rival_claim("offer:70250-1", 33.1)[0]
    out = pegasus_claims(case, data, [rival, *raw(case, data)])
    quote = next(c for c in out if c.ids == ["offer:70250-1"])
    assert quote.family == "quote" and quote.figure == 33.1
    assert out.index(quote) < min(out.index(c) for c in out if c.family in {"index", "forecast_cost_news"})


def test_used_ids_are_left_out(data):
    case = CASES["case:P01"]
    out = pegasus_claims(case, data, raw(case, data), used={"doc:20260911-70110-P01"})
    assert "doc:20260911-70110-P01" not in ids(out) and out


@pytest.mark.parametrize(
    "bad_list",
    [None, [None], ["text"], [{"refs": []}], [{"refs": ["idx:X@2026-01"], "sentence": None}], 42],
)
def test_never_raises_on_bad_candidates(data, bad_list):
    case = CASES["case:P01"]
    out = pegasus_claims(case, data, bad_list)
    assert {c.family for c in out} >= {"notice", "index"}  # ours kept


@pytest.mark.parametrize("case_id", HOSTED)
def test_never_raises_on_a_broken_case(data, case_id):
    case = copy.deepcopy(CASES[case_id])
    candidates = raw(case, data)
    case.pop("buyer")
    assert isinstance(pegasus_claims(case, data, candidates), list)
    assert isinstance(planner_hints(case, data), dict)
    assert isinstance(pegasus_claims({}, data, candidates), list)
    assert isinstance(planner_hints({}, data), dict)


def test_planner_hints_p01(data):
    h = planner_hints(CASES["case:P01"], data)
    assert h["reference_price"] == 138.55
    assert h["levers"][0]["field"] == "effective_date" and h["levers"][0]["eur"] == pytest.approx(40256.98)
    assert h["price_floor_hint"] == 137.42 and h["price_floor_confidence"] == "low"
    assert h["increase_justified"] is False and h["suppliers"]["sup:70110"]["cash_need"] is True


def test_planner_hints_signals(data):
    p02 = planner_hints(CASES["case:P02"], data)
    assert p02["increase_justified"] is True and p02["suppliers"]["sup:70510"]["committee_above_pct"] == 2.0
    p08 = planner_hints(CASES["case:P08"], data)["suppliers"]["sup:70710"]
    assert p08["material_hedged_until"] == "March 2027" and p08["sources"]["material_hedged"]
    assert planner_hints(CASES["case:P11"], data)["suppliers"]["sup:70140"]["cash_need"] is True
    assert planner_hints(CASES["case:P04"], data)["price_floor_hint"] is None  # routine


def test_compare_pegasus_runs(data):
    """Smoke test of the offline comparison script (it has no other test)."""
    from hollerau.evidence.compare_pegasus import compare_case, report

    rows = [compare_case(CASES[c], data) for c in ("case:P01", "case:P10")]
    assert rows[0]["c_ours"] == rows[0]["c_peg"]
    assert "## Résumé" in report(rows)
