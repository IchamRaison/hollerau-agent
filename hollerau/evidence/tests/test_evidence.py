"""compile_evidence on the 10 hosted practice cases (tests/fixtures/cases/practice.json)."""

import copy
import json
from pathlib import Path

import pytest

from arena_kit.data import DataPackage
from hollerau.evidence.compile import compile_evidence
from hollerau.evidence.facts import check, facts_of, load_package

ROOT = Path(__file__).resolve().parents[3]
CASES = {c["case_id"]: c for c in json.loads((ROOT / "tests/fixtures/cases/practice.json").read_text())}
HOSTED = sorted(cid for cid, c in CASES.items() if c.get("hosted"))


@pytest.fixture(scope="module")
def data():
    try:
        return load_package()
    except FileNotFoundError:
        pytest.skip("no data package: run `uv run arena data` or set ARENA_DATA")


def by_family(claims, family):
    return [c for c in claims if c.family == family]


def test_ten_hosted_cases():
    assert HOSTED == [f"case:P{n}" for n in ("01", "02", "03", "04", "05", "07", "08", "10", "11", "18")]


@pytest.mark.parametrize("case_id", HOSTED)
def test_every_claim_is_verifiable(data, case_id):
    case = CASES[case_id]
    facts = facts_of(case, data)
    claims = compile_evidence(case, data)
    ids = [i for c in claims for i in c.ids]
    assert len(ids) == len(set(ids)), "each ID counts once per case"
    for c in claims:
        assert all(i in facts for i in c.ids), c
        assert check(c, facts), c
        assert all(i in c.sentence for i in c.ids), "IDs sit next to the figure"
        assert c.supports in {"price", "effective_date", "payment", "quality", "volume", "other"}


def test_p01_notice_beats_the_announced_date(data):
    notice = by_family(compile_evidence(CASES["case:P01"], data), "notice")
    assert len(notice) == 1
    c = notice[0]
    assert c.ids == ["doc:20260911-70110-P01", "ctr:4600070110"]
    assert c.figure == 51 and c.unit == "days" and c.supports == "effective_date"


def test_p01_index_cites_power_and_labour_not_steel(data):
    claims = by_family(compile_evidence(CASES["case:P01"], data), "index")
    series = {c.ids[0].split(":")[1].split("@")[0] for c in claims}
    assert series == {"PPI-D351", "LCI-C"}  # steel rose +6.5 % against +9.5 % asked: more than half the demand


def test_p01_sentences_are_short(data):
    for c in by_family(compile_evidence(CASES["case:P01"], data), "index"):
        assert len(c.sentence) < 160, c.sentence


def test_p02_justified_increase_gets_no_index_claim(data):
    claims = compile_evidence(CASES["case:P02"], data)
    assert by_family(claims, "index") == []  # copper +47.7 %: the weighted move exceeds the 6.5 % asked
    assert by_family(claims, "notice") == []  # 109 days' notice against 90 in the contract


def test_hidden_case_facts_are_used(data):
    """A hidden case may cite a letter that exists only in the case file."""
    case = copy.deepcopy(CASES["case:P01"])
    case["trigger_doc"] = "doc:HIDDEN-70110-X"
    case["facts"] = {
        "doc:HIDDEN-70110-X": {
            "supplier": "sup:70110",
            "date": "2026-10-05",
            "days": 20,
            "asked_pct": 6.0,
            "asked_price": 134.12,
            "type": "letter",
        }
    }
    notice = by_family(compile_evidence(case, data), "notice")
    assert notice and notice[0].ids[0] == "doc:HIDDEN-70110-X" and notice[0].figure == 20
    assert "doc:HIDDEN-70110-X" not in data.facts  # really case-only


def test_sunday_release_extends_the_index_window(data, tmp_path):
    """The Sunday release adds new IDs; an index window must end on its latest month."""
    later = "idx:PPI-D351@2026-09"
    assert later not in data.facts
    fact = {"series": "PPI-D351", "month": "2026-09", "value": 120.0}
    (tmp_path / "facts.json").write_text(json.dumps({later: fact}))
    with_release = DataPackage(data.root, release=tmp_path)
    power = [c for c in compile_evidence(CASES["case:P01"], with_release) if "PPI-D351" in c.ids[0]]
    assert power and power[0].ids == ["idx:PPI-D351@2025-09", later]
    assert check(power[0], facts_of(CASES["case:P01"], with_release))
