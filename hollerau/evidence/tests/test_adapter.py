"""adapter.pegasus_claims and adapter.planner_hints on the 10 hosted practice cases."""

import copy
import json
from pathlib import Path

import pytest

from hollerau.contracts import Claim
from hollerau.evidence import adapter as adapter_mod
from hollerau.evidence.adapter import EFFECT, _rising, effect_rank, pegasus_claims, planner_hints
from hollerau.evidence.economics import lever_price
from hollerau.evidence.facts import check, facts_of, load_package, supplier_price
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


def test_p01_should_cost_leads_the_first_email(data):
    """Regression of the candidate (PEGASUS_TEAM_CLAIMS=1): P01's should-cost was filtered out. Its 0.998 replay
    (3a0b48ea) cited cost:310010, 132.64 below the 138.55 asked, verified, "a fair point". P01 has no rising history,
    so the should-cost opens the e-mail."""
    case = CASES["case:P01"]
    out = pegasus_claims(case, data, raw(case, data), supplier="sup:70110")
    assert out[0].ids == ["cost:310010"] and out[0].figure == 132.64


def test_p10_keeps_its_should_cost(data):
    case = CASES["case:P10"]
    assert "cost:340010" in ids(pegasus_claims(case, data, raw(case, data), supplier="sup:70410")[:3])


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_never_a_should_cost_above_the_price_the_supplier_wants(data, case_id):
    """Ours and Pegasus' alike, for every supplier: a should-cost is cited only below the asked (else today's) price."""
    case = CASES[case_id]
    facts = facts_of(case, data)
    wants = supplier_price(case, facts)
    for out in every_message(case, data).values():
        for c in out:
            if c.ids[0].startswith("cost:"):
                assert wants is not None and facts[c.ids[0]]["unit_cost"] < wants, (c.ids, wants)


def test_pegasus_should_cost_above_the_asked_price_is_dropped(data):
    """P02: Pegasus offers its should-cost (374.95) against a higher offer price; the supplier only asks 370.96."""
    case = CASES["case:P02"]
    cand = {"refs": ["cost:350011"], "sentence": "Our should-cost estimate for this part is 374.95 EUR (cost:350011)."}
    assert "cost:350011" not in ids(pegasus_claims(case, data, [cand]))


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


def test_rival_offer_passes_through_and_comes_second_in_an_rfq(data):
    """P05 is an RFQ: the rival's offer goes right after the strongest claim, whatever else is available."""
    case = CASES["case:P05"]
    rival = Claims(case, data).rival_claim("offer:70250-1", 33.1)[0]
    out = pegasus_claims(case, data, [rival, *raw(case, data)], supplier="sup:70210")
    quote = next(c for c in out if c.ids == ["offer:70250-1"])
    assert quote.family == "quote" and quote.figure == 33.1
    assert out.index(quote) == 1


def test_p06_rival_offer_is_sent_to_70150(data):
    """Review fix: should-cost, ppm and index came first and the 3-claim cap cut the rival's offer for sup:70150."""
    case = CASES["case:P06"]
    gen, price = Claims(case, data), lever_price(case, data)
    rival = gen.rival_claim("offer:70120-1", round(price * 0.97, 2))
    cands = rival + [c for p in case["parts"] for c in gen.candidates("sup:70150", p, price)]
    out = pegasus_claims(case, data, cands, supplier="sup:70150")
    assert ["offer:70120-1"] in [c.ids for c in out[:3]]
    assert out[1].ids == ["offer:70120-1"] and effect_rank(out[0]) < EFFECT.index("rival")


def test_rival_keeps_its_effect_rank_outside_an_rfq(data):
    case = copy.deepcopy(CASES["case:P05"])
    case["type"] = "price_increase"
    rival = Claims(case, data).rival_claim("offer:70250-1", 33.1)[0]
    out = pegasus_claims(case, data, [rival, *raw(case, data)], supplier="sup:70210")
    ranks = [effect_rank(c) for c in out]
    assert ranks == sorted(ranks)


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
    assert h["increase_justified"] is False and h["suppliers"]["sup:70110"]["cash_need"] is True


def test_planner_hints_signals(data):
    p02 = planner_hints(CASES["case:P02"], data)
    assert p02["increase_justified"] is True and p02["suppliers"]["sup:70510"]["committee_above_pct"] == 2.0
    p08 = planner_hints(CASES["case:P08"], data)["suppliers"]["sup:70710"]
    assert p08["material_hedged_until"] == "March 2027" and p08["sources"]["material_hedged"]
    assert planner_hints(CASES["case:P11"], data)["suppliers"]["sup:70140"]["cash_need"] is True
    assert planner_hints(CASES["case:P04"], data)["price_floor_hint"] is None  # routine


def test_planner_hints_floor_is_pegasus_own(data, monkeypatch):
    """One floor calculation, Pegasus's: 360.32 on P02 (supplier standard at 30 days), None with PEGASUS_REL off."""
    from hollerau.pegasus import relationship

    std = {"payment_days": 30}
    monkeypatch.setattr(relationship, "ENABLED", False)
    assert planner_hints(CASES["case:P02"], data, std)["price_floor_hint"] is None
    monkeypatch.setattr(relationship, "ENABLED", True)
    assert planner_hints(CASES["case:P02"], data, std)["price_floor_hint"] == 360.32
    assert planner_hints(CASES["case:P04"], data, std)["price_floor_hint"] is None  # routine


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
    out = pegasus_claims(case, data, fake)
    assert not [c for c in out if c.ids == ["cost:310010"] and c.figure != 132.64]  # ours (132.64) only, not 1.00
    assert "idx:NOPE@2026-01" not in ids(out)


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
    """rising history > should-cost > notice (provisional) > ppm > index > rival quote > volume forecast > the rest
    > OTD."""
    kinds = [
        Claim("scorecard", ["sc:1@2026Q3"], 78.0, "%", "OTD", "other"),
        Claim("forecast_cost_news", ["news:1"], None, "", "news", "other"),
        Claim("notice", ["doc:1", "ctr:1"], 30.0, "days", "notice", "effective_date"),
        Claim("forecast_cost_news", ["fc:1@2027"], 8.0, "%", "volume", "volume"),
        Claim("quote", ["quote:1"], 9.0, "EUR", "rival", "price"),
        Claim("index", ["idx:A@2026-01", "idx:A@2026-09"], -3.0, "%", "index", "price"),
        Claim("scorecard", ["sc:1@2026Q2"], 1500.0, "ppm", "ppm", "quality"),
        Claim("forecast_cost_news", ["cost:1"], 5.0, "EUR", "should-cost", "price"),
        Claim("orders", ["po:1", "po:2"], None, "", "history", "price"),
    ]
    assert [effect_rank(c) for c in kinds] == [8, 7, 2, 6, 5, 4, 3, 1, 0]
    assert [c.sentence for c in sorted(kinds, key=effect_rank)] == [
        "history",
        "should-cost",
        "notice",
        "ppm",
        "index",
        "rival",
        "volume",
        "news",
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


def test_never_another_suppliers_orders(data):
    """Review fix (critical): po: lines belong to one supplier, like its scorecard; no other supplier gets them."""
    case = copy.deepcopy(CASES["case:P08"])
    case["suppliers"] = ["sup:70710", "sup:70740"]
    facts = facts_of(case, data)
    for sup in case["suppliers"]:
        for c in pegasus_claims(case, data, [], supplier=sup):
            assert all(facts[i]["supplier"] == sup for i in c.ids if i.startswith("po:")), (sup, c.ids)
    assert any(c.family == "orders" for c in pegasus_claims(case, data, [], supplier="sup:70710"))


def po_ids(data, supplier, part, *prices_by_date):
    """IDs of `supplier`'s order lines of `part`, one per wanted price, in date order."""
    rows = sorted(
        (f["date"], i, f["unit_price"])
        for i, f in data.facts.items()
        if i.startswith("po:") and f.get("supplier") == supplier and f.get("part") == part
    )
    out = []
    for price in prices_by_date:
        out.append(next(i for d, i, p in rows if p == price and (not out or d > data.facts[out[-1]]["date"])))
    return out


def test_rising_is_read_by_date_one_supplier_one_part(data):
    """Review fix: listed order does not matter; a fall is a fall; two suppliers or two parts are not a history."""
    facts = data.facts
    up = po_ids(data, "sup:70710", "part:370010", 5.17, 5.45)
    assert _rising(up, facts) and _rising(list(reversed(up)), facts)
    down = po_ids(data, "sup:70710", "part:370010", 6.06, 5.45)
    assert not _rising(down, facts) and not _rising(list(reversed(down)), facts)
    mixed = [up[1], po_ids(data, "sup:70740", "part:370010", 5.84)[0]]  # 5.45 (70710) then 5.84 (70740)
    assert not _rising(mixed, facts)
    two_parts = {  # one supplier, two parts: two arguments, not one history
        "po:A": {"date": "2025-01-01", "unit_price": 1.0, "supplier": "sup:1", "part": "part:1"},
        "po:B": {"date": "2026-01-01", "unit_price": 2.0, "supplier": "sup:1", "part": "part:2"},
        "po:C": {"date": "2026-01-01", "unit_price": 2.0, "supplier": "sup:1", "part": "part:1"},
    }
    assert _rising(["po:A", "po:C"], two_parts) and not _rising(["po:A", "po:B"], two_parts)


# --- second review: the fallback, dates, supplier_price


def broken(*_args, **_kwargs):
    raise RuntimeError("main path down")


def test_fallback_never_sends_another_suppliers_orders(data, monkeypatch):
    """When the main path raises, the fallback keeps the delivery filters (po: of another supplier, rising history)."""
    monkeypatch.setattr(adapter_mod, "_pegasus_claims", broken)
    case = copy.deepcopy(CASES["case:P08"])
    case["suppliers"] = ["sup:70710", "sup:70740"]
    facts = facts_of(case, data)
    assert not [c for c in pegasus_claims(case, data, [], supplier="sup:70740") if c.family == "orders"]
    out = pegasus_claims(case, data, [], supplier="sup:70710")
    assert out[0].family == "orders" and all(facts[i]["supplier"] == "sup:70710" for i in out[0].ids)


def test_fallback_is_ranked_and_puts_the_rival_second(data, monkeypatch):
    monkeypatch.setattr(adapter_mod, "_pegasus_claims", broken)
    case = CASES["case:P01"]
    out = pegasus_claims(case, data, [], supplier="sup:70110")
    assert out[0].ids == ["cost:310010"] and [effect_rank(c) for c in out] == sorted(effect_rank(c) for c in out)
    rfq = copy.deepcopy(CASES["case:P06"])
    first = [c.family for c in pegasus_claims(rfq, data, [], supplier="sup:70150")]
    assert "quote" not in first or first.index("quote") <= 1


def test_fallback_without_facts_sends_nothing(data, monkeypatch):
    """No facts, no filter: nothing rather than claims that may be about another supplier."""
    monkeypatch.setattr(adapter_mod, "_pegasus_claims", broken)
    monkeypatch.setattr(adapter_mod, "facts_of", broken)
    assert pegasus_claims(CASES["case:P08"], data, [], supplier="sup:70710") == []


def test_rising_refuses_dates_that_are_not_iso():
    """A date that cannot be read is never ordered as text: "2025-9-05" would sort after "2025-12-01"."""
    row = {"supplier": "sup:1", "part": "part:1"}
    facts = {
        "po:SEP": {**row, "date": "2025-9-05", "unit_price": 5.0},
        "po:DEC": {**row, "date": "2025-12-01", "unit_price": 4.0},
        "po:JAN": {**row, "date": "2026-01-02", "unit_price": 6.0},
    }
    assert not _rising(["po:DEC", "po:SEP"], facts) and not _rising(["po:SEP", "po:DEC"], facts)
    assert _rising(["po:DEC", "po:JAN"], facts)
    facts["po:DEC"]["date"] = "2025-12-01T08:00:00"  # an ISO timestamp is a date
    assert _rising(["po:JAN", "po:DEC"], facts)
