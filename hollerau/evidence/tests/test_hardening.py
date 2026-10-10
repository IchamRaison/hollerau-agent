"""Fixes after the /review of 10/10: never raise, must-haves the grid cannot test, null facts, Sunday release,
no cached failure, forecast in capacity cases, index margin, quotes and should-cost that are not comparable,
no default package shared between threads."""

import copy
import json
import logging
import math
import threading
from pathlib import Path

import pytest

from arena_kit.data import DataPackage
from hollerau.evidence import facts as facts_mod
from hollerau.evidence.compile import compile_evidence
from hollerau.evidence.economics import compile_case, estimate_supplier
from hollerau.evidence.facts import check, facts_of, load_package
from hollerau.evidence.forecast_cost_news import forecast_cost_news_claims
from hollerau.evidence.quote import quote_claims
from hollerau.evidence.signals import signals

ROOT = Path(__file__).resolve().parents[3]
CASES = {c["case_id"]: c for c in json.loads((ROOT / "tests/fixtures/cases/practice.json").read_text())}


@pytest.fixture(scope="module")
def data():
    try:
        return load_package()
    except FileNotFoundError:
        pytest.skip("no data package: run `uv run arena data` or set ARENA_DATA")


def ids_of(claims, prefix):
    return [c.ids[0] for c in claims if c.ids[0].startswith(prefix)]


# 1. Golden rule: never raise


CORRUPT_FACTS = {
    "doc:20260911-70110-P01": "not a dict",
    "news:BAD-1": {"supplier": "sup:70110", "topic": "free_capacity", "date": None, "headline": None},
    "news:BAD-2": {"supplier": "sup:70110", "topic": "free_capacity", "date": "yesterday", "headline": "x"},
    "sc:70110@2026Q4": {"supplier": "sup:70110", "ppm": None, "otd_pct": "n/a", "colour": "red"},
    "quote:7200001": {"part": "part:310010", "supplier": "sup:70140", "unit_price": "cheap"},
    "fc:310010@2026-12": {"part": "part:310010", "change_pct": None},
    "cost:310010": {"part": "part:310010", "unit_cost": None},
    "idx:PPI-D351@2026-09": {"series": "PPI-D351", "value": None},
    "ctr:4600070110": {"supplier": "sup:70110", "days": None},
}


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda c: c.update(facts=CORRUPT_FACTS),
        lambda c: c["buyer"].pop("freight_eur_per_unit"),
        lambda c: c.update(negotiable=["unit_price", "no_such_field"], term_options={"no_such_field": [None, 3]}),
        lambda c: c.update(parts=None, suppliers=None),
        lambda c: c.update(buyer=None),
        lambda c: c.clear(),
    ],
)
def test_corrupt_case_never_raises(data, corrupt):
    case = copy.deepcopy(CASES["case:P01"])
    corrupt(case)
    econ = compile_case(case, data=data)
    assert isinstance(econ.levers, list) and isinstance(econ.best_package, dict)
    assert isinstance(econ.cost({"unit_price": 130.0}), float)
    assert isinstance(econ.must_haves_ok({"unit_price": 130.0}), bool)
    claims = compile_evidence(case, data)
    assert all(check(c, facts_of(case, data)) for c in claims)
    assert isinstance(signals(case, data), dict)


def test_corrupt_facts_keep_the_good_claims(data):
    """A family that meets broken facts drops them; the notice and index claims of P01 stay."""
    case = copy.deepcopy(CASES["case:P01"])
    case["facts"] = {k: v for k, v in CORRUPT_FACTS.items() if not k.startswith(("doc:", "ctr:"))}
    families = {c.family for c in compile_evidence(case, data)}
    assert {"notice", "index"} <= families


# 2. Must-haves the term search cannot test


@pytest.mark.parametrize(
    "must_have",
    [
        {"field": "unit_price", "op": "<=", "value": 130},  # the price is the planner's call
        {"field": "ppm_commitment", "op": "<=", "value": 1000},  # only the supplier's quote fills it (round 0)
    ],
)
def test_untestable_must_have_is_left_out_of_the_search(data, caplog, must_have):
    case = copy.deepcopy(CASES["case:P01"])
    case["buyer"]["must_haves"] = [must_have]
    with caplog.at_level(logging.WARNING):
        econ = compile_case(case, data=data)
    assert f"must-have on {must_have['field']} left out" in caplog.text
    assert econ.best_package == compile_case(CASES["case:P01"], data=data).best_package
    assert [lv.field for lv in econ.levers] == ["effective_date", "payment_days"]


def test_quote_field_must_have_is_tested_once_the_standard_is_known(data):
    case = copy.deepcopy(CASES["case:P01"])
    case["buyer"]["must_haves"] = [{"field": "ppm_commitment", "op": "<=", "value": 1000}]
    econ = compile_case(case, {"ppm_commitment": 900}, data=data)
    assert econ.must_haves_ok({**econ.best_package, "unit_price": 130.0})
    assert not compile_case(case, {"ppm_commitment": 1200}, data=data).must_haves_ok({"unit_price": 130.0})


# 3. Null values in the facts


def test_null_rows_are_skipped(data):
    case = copy.deepcopy(CASES["case:P11"])
    case["facts"] = {
        "sc:70140@2026Q4": {"supplier": "sup:70140", "ppm": None, "otd_pct": None, "colour": "red"},
        "news:NULL-1": {"supplier": "sup:70140", "topic": "free_capacity", "date": None, "headline": "x"},
    }
    claims = compile_evidence(case, data)
    assert ids_of(claims, "sc:")[0] == "sc:70140@2026Q3"  # the null quarter is skipped, not cited
    assert "news:NULL-1" not in ids_of(claims, "news:")
    assert "news:NULL-1" not in signals(case, data)["suppliers"]["sup:70140"]["free_capacity"]


# 4. Sunday release


@pytest.fixture
def release_data(data, tmp_path):
    """A fake Sunday release: a news item and a letter of early October about sup:70110 (P01)."""
    (tmp_path / "data").mkdir()
    (tmp_path / "correspondence").mkdir()
    news = {
        "news:20261005-90": {
            "date": "2026-10-05",
            "headline": "Brandlhuber has free capacity",
            "supplier": "sup:70110",
            "topic": "free_capacity",
        }
    }
    letter = {"doc:20261006-70110-S1": {"date": "2026-10-06", "supplier": "sup:70110", "type": "letter"}}
    (tmp_path / "facts.json").write_text(json.dumps(news | letter))
    (tmp_path / "correspondence" / "20261006-70110-S1.md").write_text(
        "# Annual review\n\nletter - 2026-10-06 - Brandlhuber\n\n"
        "Their key account manager explained that price changes above 1 % need the approval of their pricing "
        "committee, which meets every two weeks.\n"
    )
    (tmp_path / "data" / "documents.csv").write_text(
        "id,date,kind,supplier_id,part_ids,subject,author,file\n"
        "doc:20261006-70110-S1,2026-10-06,letter,sup:70110,,Annual review,,correspondence/20261006-70110-S1.md\n"
    )
    return DataPackage(data.root, release=tmp_path)


def test_release_news_reaches_claims_and_signals(release_data):
    case = CASES["case:P01"]  # its letter is of 2026-09-11: the release is later, yet before the case starts
    assert "news:20261005-90" in ids_of(compile_evidence(case, release_data), "news:")
    s = signals(case, release_data)["suppliers"]["sup:70110"]
    assert "news:20261005-90" in s["free_capacity"]


def test_release_letters_reach_signals(release_data):
    s = signals(CASES["case:P01"], release_data)["suppliers"]["sup:70110"]
    assert s["committee_above_pct"] == 1.0 and "doc:20261006-70110-S1" in s["committee"]


def test_news_after_the_case_start_is_not_used(release_data):
    case = copy.deepcopy(CASES["case:P01"])
    case["start_date"] = "2026-10-01"
    assert "news:20261005-90" not in ids_of(compile_evidence(case, release_data), "news:")


# 5. No cached failure


def test_a_failed_load_is_not_cached(data, monkeypatch):
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise FileNotFoundError("not downloaded yet")
        return data

    monkeypatch.setattr(facts_mod, "load_package", flaky)
    monkeypatch.setattr(facts_mod, "_local", threading.local())
    assert facts_of(CASES["case:P01"]) == {}  # first call: no package yet
    assert compile_case(CASES["case:P01"]).reference_price == 138.55  # second call loads it: D3 works
    assert len(calls) == 2


# 6. Forecast growth never told to a saturated supplier


@pytest.mark.parametrize("case_id", ["case:P09", "case:P10"])
def test_no_forecast_claim_in_capacity_cases(data, case_id):
    case = CASES[case_id]
    assert ids_of(forecast_cost_news_claims(case, data, facts_of(case, data)), "fc:") == []


def test_no_forecast_claim_to_a_supplier_that_allocates(data):
    case = copy.deepcopy(CASES["case:P01"])
    assert ids_of(forecast_cost_news_claims(case, data, facts_of(case, data)), "fc:")  # growth cited normally
    case["facts"] = {
        "news:ALLOC-1": {
            "date": "2026-09-01",
            "headline": "Brandlhuber allocates",
            "supplier": "sup:70110",
            "topic": "allocation",
        }
    }
    assert ids_of(forecast_cost_news_claims(case, data, facts_of(case, data)), "fc:") == []


# 7. Index: an increase within 1 point of the weighted move is justified


def test_p17_increase_within_a_point_is_justified(data):
    case = CASES["case:P17"]  # weighted +7.95 % against +8.0 % asked
    assert [c for c in compile_evidence(case, data) if c.family == "index"] == []
    assert signals(case, data)["increase_justified"] is True


# 8. Quotes and should-cost only when comparable with the case price


def test_quote_in_another_price_unit_is_not_cited(data):
    case = copy.deepcopy(CASES["case:P14"])  # motor cable, priced per 100
    case["refs"].append("quote:HIDDEN-PU")
    case["facts"] = {
        "quote:HIDDEN-PU": {"part": "part:350040", "supplier": "sup:70999", "unit_price": 3.10, "price_unit": 1}
    }
    assert quote_claims(case, data, facts_of(case, data)) == []
    case["facts"]["quote:HIDDEN-PU"] |= {"unit_price": 300.0, "price_unit": 100}
    assert ids_of(quote_claims(case, data, facts_of(case, data)), "quote:") == ["quote:HIDDEN-PU"]


def test_no_quote_or_should_cost_in_a_bundle(data):
    case = copy.deepcopy(CASES["case:P07"])  # a kit of four parts, one price
    case["refs"].append("quote:HIDDEN-KIT")
    case["facts"] = {
        "quote:HIDDEN-KIT": {"part": "part:360010", "supplier": "sup:70999", "unit_price": 1.0, "price_unit": 100},
        "cost:360010": {"part": "part:360010", "unit_cost": 1.0, "price_unit": 100},
    }
    facts = facts_of(case, data)
    assert quote_claims(case, data, facts) == []
    assert ids_of(forecast_cost_news_claims(case, data, facts), "cost:") == []
    assert estimate_supplier(case, data=data)["estimated"]


def test_should_cost_in_another_price_unit_is_not_used(data):
    case = copy.deepcopy(CASES["case:P14"])
    case["facts"] = {"cost:350040": {"part": "part:350040", "unit_cost": 2.0, "price_unit": 1}}
    facts = facts_of(case, data)
    assert ids_of(forecast_cost_news_claims(case, data, facts), "cost:") == []
    supplier = estimate_supplier(case, data=data)
    assert supplier["estimated"] and not math.isclose(supplier["full_cost"], 2.0)


# 9. The default package is never shared between threads (R1: parallel cases crashed on one SQLite connection)

THREADS, ROUNDS = 6, 4


def numbers(case, data=None):
    """What the lane computes from the package (Economics also holds functions, which do not compare)."""
    e = compile_case(case, data=data)
    return facts_of(case, data), e.levers, e.best_package, e.c_alt, e.reference_price


def one_round(case):
    """THREADS threads released at once, each on the default package of a fresh process."""
    start, errors, packages, results = threading.Barrier(THREADS), [], [], []

    def work():
        start.wait()
        try:
            p = facts_mod.package()
            packages.append(p)
            p.ids("idx:")
            p.query("SELECT series_id, weight FROM cost_drivers WHERE part_id = ?", ("part:310010",))
            results.append(numbers(case))  # on the default package
        except Exception as e:  # noqa: BLE001 - the test reports any failure of any thread
            errors.append(f"{type(e).__name__}: {e}")

    threads = [threading.Thread(target=work) for _ in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors, packages, results


def test_default_package_is_one_per_thread(data, monkeypatch):
    """Like runner-repro/hammer.py: threads released at once build the ID index and query the default package.
    With one package shared by all threads this fails in nearly every round (no such table: None, IndexError)."""
    case = CASES["case:P01"]
    expected = numbers(case, data)
    for _ in range(ROUNDS):
        monkeypatch.setattr(facts_mod, "_local", threading.local())  # a fresh process: nothing loaded yet
        errors, packages, results = one_round(case)
        assert errors == []
        assert len({id(p) for p in packages}) == THREADS
        assert results == [expected] * THREADS
