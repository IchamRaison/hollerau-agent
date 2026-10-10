"""adapter.pegasus_claims and adapter.planner_hints on the 10 hosted practice cases."""

import copy
import json
from pathlib import Path

import pytest

from hollerau.contracts import Claim
from hollerau.evidence.adapter import EFFECT, effect_rank, pegasus_claims, planner_hints
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
    ranks = [effect_rank(c) for c in out]
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


def test_rival_offer_passes_through_and_ranks_by_effect(data):
    """A rival's offer (14/21 in X9) comes after the index (7/7) and before the volume forecast and the rest."""
    case = CASES["case:P05"]
    rival = Claims(case, data).rival_claim("offer:70250-1", 33.1)[0]
    out = pegasus_claims(case, data, [rival, *raw(case, data)])
    quote = next(c for c in out if c.ids == ["offer:70250-1"])
    assert quote.family == "quote" and quote.figure == 33.1
    before = [c for c in out if effect_rank(c) < EFFECT.index("rival")]
    after = [c for c in out if effect_rank(c) > EFFECT.index("rival")]
    assert all(out.index(c) < out.index(quote) for c in before)
    assert all(out.index(c) > out.index(quote) for c in after)


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


# --- memory: an offer counts once per supplier, every other ID once per case


def test_p05_same_rival_offer_for_two_suppliers(data):
    from hollerau.evidence.adapter import remember

    case = CASES["case:P05"]  # RFQ with sup:70210, sup:70240, sup:70250
    rival = Claims(case, data).rival_claim("offer:70250-1", 33.1)[0]
    used, by_sup = set(), {}
    first = pegasus_claims(
        case, data, [rival, *raw(case, data)], used=used, supplier="sup:70210", used_by_supplier=by_sup
    )
    assert "offer:70250-1" in ids(first)
    remember(first[:3], "sup:70210", used, by_sup)
    second = pegasus_claims(case, data, [rival], used=used, supplier="sup:70240", used_by_supplier=by_sup)
    assert "offer:70250-1" in ids(second)  # another supplier: cited again
    assert not set(ids(second)) & {i for i in ids(first[:3]) if not i.startswith("offer:")}  # others: once per case
    remember(second[:3], "sup:70240", used, by_sup)
    again = pegasus_claims(case, data, [rival], used=used, supplier="sup:70210", used_by_supplier=by_sup)
    assert "offer:70250-1" not in ids(again)  # already sent to sup:70210
    own = pegasus_claims(case, data, [rival], supplier="sup:70250")
    assert "offer:70250-1" not in ids(own)  # never its own offer


def test_pick_memory_format_is_understood(data):
    """Pegasus `pick` stores a rival offer as (supplier, refs) in Claims.used: passing that set works as is."""
    case = CASES["case:P05"]
    rival = Claims(case, data).rival_claim("offer:70250-1", 33.1)[0]
    used = {("sup:70210", ("offer:70250-1",))}
    assert "offer:70250-1" not in ids(pegasus_claims(case, data, [rival], used=used, supplier="sup:70210"))
    assert "offer:70250-1" in ids(pegasus_claims(case, data, [rival], used=used, supplier="sup:70240"))


# --- second /review of the adapter


@pytest.mark.parametrize("case_id", ["case:P05", "case:P06"])
def test_never_a_competitors_card_or_news(data, case_id):
    case = CASES[case_id]
    facts = facts_of(case, data)
    for supplier in case["suppliers"]:
        out = pegasus_claims(case, data, raw(case, data), supplier=supplier)
        for i in ids(out):
            if i.startswith(("sc:", "news:", "doc:", "ctr:")):
                assert facts[i].get("supplier") in (None, supplier), (supplier, i)
    p05 = pegasus_claims(CASES["case:P05"], data, [], supplier="sup:70210")
    assert "sc:70210@2026Q3" in ids(p05) and "sc:70240@2026Q3" not in ids(p05)


def test_rival_flag_does_not_skip_check_for_other_ids(data):
    case = CASES["case:P01"]
    fake = [
        {"refs": ["cost:310010"], "sentence": "Our should-cost estimate is 1.00 EUR (cost:310010).", "rival": True},
        {"refs": ["idx:NOPE@2026-01"], "sentence": "NOPE changed -9.0% (idx:NOPE@2026-01).", "rival": True},
    ]
    out = ids(pegasus_claims(case, data, fake))
    assert "cost:310010" not in out and "idx:NOPE@2026-01" not in out


def test_refs_must_be_a_list_of_strings(data):
    case = CASES["case:P05"]
    bad = [
        {
            "refs": "offer:70999-1",
            "sentence": "We hold a competing offer at 1.00 EUR per unit (offer:70999-1).",
            "rival": True,
        },
        {"refs": ["offer:x", 5], "sentence": "x", "rival": True},
    ]
    out = ids(pegasus_claims(case, data, bad, supplier="sup:70210"))
    assert "offer:70999-1" not in out and not [i for i in out if len(i) == 1]


@pytest.mark.parametrize(
    ("kwargs", "case_id"),
    [
        ({"used": 5}, "case:P01"),
        ({"used": [["a"]]}, "case:P01"),
        ({"used": {("s", 5)}}, "case:P01"),
        ({"used_by_supplier": [1], "supplier": "sup:70110"}, "case:P01"),
        ({"used_by_supplier": {"sup:70110": 5}, "supplier": "sup:70110"}, "case:P01"),
        ({"supplier": ["unhashable"]}, "case:P01"),
        ({}, None),
    ],
)
def test_pegasus_claims_never_raises(data, kwargs, case_id):
    case = CASES[case_id] if case_id else None
    out = pegasus_claims(case, data, [{"refs": ["offer:x", None], "sentence": "x", "rival": True}], **kwargs)
    assert isinstance(out, list)


@pytest.mark.parametrize(
    ("claims", "used"),
    [
        ([{"sentence": "no refs"}], set()),
        ([{"refs": [5]}], set()),
        ([{"refs": ["a"]}], None),
        ([{"refs": ["a"]}], frozenset()),
        (None, set()),
        ([object()], set()),
    ],
)
def test_remember_never_raises(claims, used):
    from hollerau.evidence.adapter import remember

    remember(claims, "sup:70110", used)


def test_rival_offer_survives_a_failing_filter(data, monkeypatch):
    from hollerau.evidence import adapter

    def boom(*args):
        raise RuntimeError("index check broken")

    monkeypatch.setattr(adapter, "_justified", boom)
    case = CASES["case:P05"]
    rival = Claims(case, data).rival_claim("offer:70250-1", 33.1)[0]
    out = ids(adapter.pegasus_claims(case, data, [rival, *raw(case, data)], supplier="sup:70210"))
    assert "offer:70250-1" in out


def test_rival_quote_once_per_supplier_never_to_its_own(data):
    from hollerau.evidence.adapter import remember

    case = copy.deepcopy(CASES["case:P05"])
    case["facts"] = {"quote:HIDDEN-Q": {"part": "part:320070", "supplier": "sup:70250", "unit_price": 30.0}}
    cand = [{"refs": ["quote:HIDDEN-Q"], "sentence": "We hold a quote at 30.00 EUR (quote:HIDDEN-Q)."}]
    used = set()
    first = pegasus_claims(case, data, cand, used=used, supplier="sup:70210")
    assert "quote:HIDDEN-Q" in ids(first)
    remember(first[:3], "sup:70210", used)
    assert "quote:HIDDEN-Q" in ids(pegasus_claims(case, data, cand, used=used, supplier="sup:70240"))
    assert "quote:HIDDEN-Q" not in ids(pegasus_claims(case, data, cand, used=used, supplier="sup:70210"))
    assert "quote:HIDDEN-Q" not in ids(pegasus_claims(case, data, cand, supplier="sup:70250"))


# --- X9: the argument of the first e-mail, by the effect measured on 202 practice sessions


def every_message(case, data):
    """pegasus_claims for each supplier of the case, with Pegasus' candidates: what each first e-mail could carry."""
    cands = raw(case, data)
    return {s: pegasus_claims(case, data, cands, supplier=s) for s in case["suppliers"]}


@pytest.mark.parametrize(("case_id", "low", "high"), [("case:P08", 5.17, 5.45), ("case:P18", 5.26, 5.84)])
def test_rising_price_history_leads_the_first_email(data, case_id, low, high):
    case, facts = CASES[case_id], facts_of(CASES[case_id], data)
    for out in every_message(case, data).values():
        first = out[0]
        assert first.family == "orders"
        assert [facts[i]["unit_price"] for i in first.ids] == [low, high]


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_never_an_order_history_at_the_same_price(data, case_id):
    """0 effect out of 24 in X9 (P09, P10, P11, P12 and P16 used to get one)."""
    case, facts = CASES[case_id], facts_of(CASES[case_id], data)
    for out in every_message(case, data).values():
        for c in out:
            if c.family == "orders":
                prices = [facts[i]["unit_price"] for i in c.ids]
                assert prices[-1] > prices[0], (c.ids, prices)


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_otd_never_leads_and_comes_last(data, case_id):
    for out in every_message(CASES[case_id], data).values():
        otd = [c for c in out if effect_rank(c) == EFFECT.index("otd")]
        assert not out or effect_rank(out[0]) != EFFECT.index("otd") or len(out) == len(otd)
        assert out[len(out) - len(otd) :] == otd  # all OTD claims at the end


def test_effect_order_on_every_kind():
    """rising history > should-cost > ppm > index > rival quote > volume forecast > the rest > OTD."""
    kinds = [
        Claim("scorecard", ["sc:1@2026Q3"], 78.0, "%", "OTD", "other"),
        Claim("notice", ["doc:1"], 30.0, "days", "notice", "effective_date"),
        Claim("forecast_cost_news", ["fc:1@2027"], 8.0, "%", "volume", "volume"),
        Claim("quote", ["quote:1"], 9.0, "EUR", "rival", "price"),
        Claim("index", ["idx:A@2026-01", "idx:A@2026-09"], -3.0, "%", "index", "price"),
        Claim("scorecard", ["sc:1@2026Q2"], 1500.0, "ppm", "ppm", "quality"),
        Claim("forecast_cost_news", ["cost:1"], 5.0, "EUR", "should-cost", "price"),
        Claim("orders", ["po:1", "po:2"], None, "", "history", "price"),
    ]
    assert [effect_rank(c) for c in kinds] == [7, 6, 5, 4, 3, 2, 1, 0]
    assert [c.sentence for c in sorted(kinds, key=effect_rank)] == [
        "history",
        "should-cost",
        "ppm",
        "index",
        "rival",
        "volume",
        "notice",
        "OTD",
    ]


def test_a_same_price_history_from_pegasus_is_dropped(data):
    """Whoever builds it (intel's dossier cited six orders at one price): never sent."""
    case = CASES["case:P09"]
    facts = facts_of(case, data)
    same = sorted(
        i
        for i, f in facts.items()
        if i.startswith("po:") and f.get("part") == case["parts"][0] and f.get("unit_price") == 16.02
    )[:2]
    assert len(same) == 2
    cand = {"refs": same, "sentence": f"Our orders were placed at 16.02 EUR ({same[0]}, {same[1]})."}
    assert not set(same) & set(ids(pegasus_claims(case, data, [cand])))
