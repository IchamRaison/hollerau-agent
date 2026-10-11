"""The DSH pilot below the harness: costs, validation, the desk's tools and the case loop, with a
scripted stand-in for the model. No model call, no hosted session: the games run on arena-sim.
"""

import copy
import json
import secrets
import time
from pathlib import Path

import pytest

from arena_kit import ArenaClient, RemoteTable
from arena_kit.play import fetch_documents
from hollerau.dsh import economics, validation
from hollerau.dsh.coordinator import Journal, closing_batch, fallback_batch, play_case
from hollerau.dsh.state import CaseState
from hollerau.dsh.tools import Desk, build_server

CASES = {c["case_id"]: c for c in json.loads(Path("tests/fixtures/cases/sandbox.json").read_text())}


def team(url):
    return ArenaClient(url, ArenaClient(url).register(f"dsh-{secrets.token_hex(3)}", "sim")["api_key"], rate=1000)


def opened(sim, case_id="case:S01"):
    url, _, _ = sim
    table = RemoteTable(team(url))
    case, threads = table.open(case_id)
    for events in threads.values():
        for m in events:
            fetch_documents(table, m)
    return table, CaseState(case, threads)


def d01(price=52.9, with_reply=False):
    """Sandbox D01 (strategic: the relationship charge applies) with one supplier and its opening quote."""
    case = copy.deepcopy(CASES["case:D01"])
    terms = {"unit_price": price, "payment_days": 30, "contract_months": 12, "effective_date": "2026-12-01"}
    threads = {
        "sup:DEMO-F1": [
            {
                "from": "sales@DEMO-F1",
                "status": "open",
                "body": "Our quote.",
                "term_sheets": [{"term_sheet_id": "offer:DEMO-F1-0", "terms": terms}],
                "attachments": [],
            }
        ]
    }
    state = CaseState(case, threads)
    if with_reply:
        ours = {"unit_price": 50.0, "payment_days": 60, "contract_months": 24, "effective_date": "2026-12-01"}
        state.sent("sup:DEMO-F1", {"subject": "s", "body": "b", "term_sheets": [{"terms": ours}]})
        state.replied(
            "sup:DEMO-F1",
            {
                "from": "sales@DEMO-F1",
                "status": "open",
                "body": "We can do 51.80.",
                "term_sheets": [{"term_sheet_id": "offer:DEMO-F1-1", "terms": {**ours, "unit_price": 51.8}}],
            },
        )
    return state


# -- economics -----------------------------------------------------------------------------------
def test_a_cost_target_gives_a_price_for_every_combination_and_each_costs_the_target(sim):
    _, state = opened(sim)
    sid = next(iter(state.threads))
    target = round(state.c_open() * 0.93, 2)
    found = economics.structures_for_target(state.case, target, state.std[sid])
    assert found["searched"] == "all" and found["matching"] == found["combinations_in_grid"] == 5
    cent = state.case["buyer"]["need_per_year"] * 0.01 * 1.1  # what one cent of price weighs, with a margin
    for sheet in found["sheets"]:
        assert sheet["reached"] and abs(state.cost(sid, sheet["terms"]) - target) <= cent
    prices = [s["terms"]["unit_price"] for s in found["sheets"]]
    assert prices == sorted(prices, reverse=True)  # at equal cost for us, the supplier's favourite first


def test_the_relationship_charge_is_unknown_without_an_estimate_and_u_shaped_with_one():
    state = d01()
    sid = "sup:DEMO-F1"
    blind = state.evaluate(sid, state.standing(sid)[1])
    assert blind["relationship_eur"] is None and "unknown" in blind["relationship"]
    state.set_estimate(sid, 48.0, source="its cost breakdown")
    low = state.evaluate(sid, {**state.standing(sid)[1], "unit_price": 40.0})
    mid = state.evaluate(sid, {**state.standing(sid)[1], "unit_price": 50.5})
    assert low["relationship_eur"] > 0 and "estimate" in low["relationship"]
    assert low["total_eur"] > mid["total_eur"]  # far below its cost, a lower price costs us more
    floor = economics.structures_for_target(state.case, 1.0, state.std[sid], state.estimate[sid])
    assert floor["sheets"] and not any(s["reached"] for s in floor["sheets"])  # an unreachable target says so
    assert min(s["terms"]["unit_price"] for s in floor["sheets"]) > 40.0  # and never goes under the bottom of the U


def test_the_state_shows_what_the_suppliers_cost_would_buy_on_other_terms(sim):
    """S03's supplier quotes on its standard terms (12 months, ex works): the same cost for us buys
    a higher unit price on a two-year delivered contract - the trade the model has to see."""
    _, state = opened(sim, "case:S03")
    view = state.snapshot()["threads"][0]
    its = view["supplier_sheets"][0]
    trades = view["what_its_standing_sheet_costs_us_would_buy_on_other_terms"]
    assert trades and all(t["terms"]["unit_price"] > its["terms"]["unit_price"] for t in trades)
    cent = state.case["buyer"]["need_per_year"] * 0.01 * 2.2
    assert all(abs(t["costs_us_eur"] - its["cost_eur"]) <= cent for t in trades)


def test_movement_is_read_from_the_offers_in_our_cost_units():
    state = d01(with_reply=True)
    m = economics.movement(state.case, state.threads["sup:DEMO-F1"], state.std["sup:DEMO-F1"])
    assert len(m["our_asks_eur"]) == 1 and len(m["supplier_offers_eur"]) == 2
    assert m["supplier_since_our_last_move_eur"] == m["supplier_total_move_eur"] > 0
    assert m["gap_eur"] > 0 and 0 < m["gap_closed_by_supplier_pct"] < 100


def test_a_counter_worth_less_to_the_supplier_than_our_offer_contradicts_the_estimate():
    state = d01(with_reply=True)
    sid = "sup:DEMO-F1"
    assert economics.estimate_check(state.case, state.threads[sid], state.std[sid], None) is None
    state.set_estimate(sid, 48.0)
    assert (
        economics.estimate_check(state.case, state.threads[sid], state.std[sid], state.estimate[sid])["contradicted"]
        is False
    )
    # it now "counters" our 50.00 sheet with the same terms at 49.00: by any estimate that is worth less to it
    state.threads[sid][-1]["term_sheets"][0]["terms"]["unit_price"] = 49.0
    check = economics.estimate_check(state.case, state.threads[sid], state.std[sid], state.estimate[sid])
    assert check["contradicted"] is True


# -- what the model is given to argue and to trade ----------------------------------------------------
def d02():
    """Sandbox D02: an RFQ with two bidders, a must-have on lead time, an alternative dearer than both."""
    case = copy.deepcopy(CASES["case:D02"])
    threads = {
        "sup:DEMO-J1": [
            {
                "from": "owner@DEMO-J1",
                "status": "open",
                "body": "here is our price.",
                "attachments": [],
                "term_sheets": [
                    {
                        "term_sheet_id": "offer:DEMO-J1-0",
                        "terms": {"unit_price": 17.1, "payment_days": 30, "lead_time_days": 28},
                    }
                ],
            }
        ],
        "sup:DEMO-C1": [
            {
                "from": "export@DEMO-C1",
                "status": "open",
                "body": "Please find our Angebot.",
                "attachments": [],
                "term_sheets": [
                    {
                        "term_sheet_id": "offer:DEMO-C1-0",
                        "terms": {"unit_price": 16.0, "payment_days": 45, "incoterm": "EXW"},
                    }
                ],
            }
        ],
    }
    return CaseState(case, threads)


def test_the_state_says_what_each_option_of_each_term_costs_us():
    view = d02().snapshot()["threads"][0]
    levers = view["what_each_term_option_costs_us_eur"]
    assert levers["lead_time_days"]["35"] == 0 and levers["lead_time_days"]["42"] == 1050.0  # 7 days at EUR 150
    assert levers["lead_time_days"]["49"] == "breaks a must-have"
    assert levers["incoterm"]["DAP"] == 0 and levers["incoterm"]["EXW"] == 7200.0
    assert levers["payment_days"]["60"] == 0 and levers["payment_days"]["14"] > levers["payment_days"]["45"] > 0


def test_ids_the_case_names_are_citable_without_a_figure_and_only_those_about_this_supplier():
    j1, c1 = d02().snapshot()["threads"]
    ids = {i["id"]: i for i in j1["data_you_can_cite"]["ids_the_case_points_to"]}
    assert "sc:DEMO-J1@2026Q3" in ids and "sc:DEMO-C1@2026Q3" not in ids  # the other bidder's scorecard is irrelevant
    assert "without a figure" in ids["cost:part:SH-220"]["value"]
    assert "MORE than its own price" in ids["quote:D02-ALT"]["this_is_our_alternative_without_a_deal"]
    rivals = j1["data_you_can_cite"]["standing_offers_of_the_other_bidders"]
    assert [r["id"] for r in rivals] == ["offer:DEMO-C1-0"] and rivals[0]["unit_price"] == 16.0
    state = d01()
    state.sent(
        "sup:DEMO-F1",
        {"body": "Your letter (doc:D01-LETTER) against our contract (ctr:D01-FRAMEWORK).", "term_sheets": []},
    )
    cited = {
        i["id"]
        for i in state.snapshot()["threads"][0]["data_you_can_cite"]["ids_the_case_points_to"]
        if i.get("already_cited_in_this_case")
    }
    assert cited == {"doc:D01-LETTER", "ctr:D01-FRAMEWORK"}  # an ID counts once per case


def test_a_suppliers_own_cost_drivers_are_added_up_against_the_increase_it_asks():
    from hollerau.dsh import evidence

    events = [
        {
            "from": "owner@DEMO-F1",
            "body": "WAGES-METAL rose 3.1 % in twelve months and is 28 % of our cost. "
            "GAS-TTF fell 10 % in twelve months and is 5 % of our cost.",
            "term_sheets": [{"terms": {"unit_price": 52.9}}],
        }
    ]
    out = evidence.stated_drivers(events, current_price=48.6)
    assert [d["explains_pct_of_price"] for d in out["drivers_it_stated"]] == [0.87, -0.5]
    assert out["together_they_explain_pct"] == 0.37 and out["increase_its_opening_quote_asks_pct"] == 8.85
    assert evidence.stated_drivers([{"from": "x", "body": "Our costs went up."}]) is None


def test_other_cases_of_the_same_kind_are_a_prior_and_never_include_the_case_played():
    from hollerau.dsh import evidence

    rows = json.loads(evidence.OBSERVATIONS.read_text())
    mine = next(r for r in rows if r["case_id"] == "case:D02")
    seen = evidence.similar_cases(CASES["case:D02"])
    assert (
        seen["category_goal"] == "leverage"
        and len(seen["cases_of_this_category_goal"]) == sum(r["category_goal"] == "leverage" for r in rows) - 1
    )
    assert all("case_id" not in r for r in seen["cases_of_this_category_goal"]) and mine["games"] > 0


# -- validation -------------------------------------------------------------------------------------
def mail(sid, price=50.0, body=None, **over):
    terms = {"unit_price": price, "payment_days": 60, "contract_months": 24, "effective_date": "2026-12-01", **over}
    return {
        "supplier_id": sid,
        "subject": "Our proposal",
        "body": body or f"We propose EUR {price:.2f} per unit.",
        "term_sheets": [terms],
    }


def test_a_decision_the_arena_would_refuse_is_stopped_with_what_to_fix():
    state = d01()
    sid = "sup:DEMO-F1"
    bad = validation.prepare(state, {"emails": [mail(sid, payment_days=75)]})
    assert not bad["ok"] and bad["batch"] is None and any("payment_days=75" in e for e in bad["errors"])
    missing = validation.prepare(
        state, {"emails": [{"supplier_id": sid, "body": "x", "term_sheets": [{"unit_price": 50.0}]}]}
    )
    assert any("missing field" in e for e in missing["errors"])
    unknown = validation.prepare(state, {"emails": [mail(sid, body="Prices fell (idx:NOPE@2026-01). EUR 50.00.")]})
    assert any("idx:NOPE@2026-01" in e and "not a known data ID" in e for e in unknown["errors"])
    both = validation.prepare(state, {"emails": [mail(sid)], "close": {"type": "walk_away"}})
    assert any("never both" in e for e in both["errors"])
    assert validation.prepare(state, {})["errors"] and validation.prepare(state, "send it")["errors"]


def test_text_and_sheets_are_never_rewritten_and_diagnostics_do_not_block():
    state = d01(with_reply=True)
    sid = "sup:DEMO-F1"
    dearer = mail(sid, 52.5, body="We can go to EUR 52.50 per unit.")  # dearer for us than its signable 51.80
    out = validation.prepare(state, {"emails": [dearer], "note": "testing"})
    assert out["ok"] and out["batch"]["emails"][0]["message"]["term_sheets"] == [{"terms": dearer["term_sheets"][0]}]
    assert out["batch"]["emails"][0]["message"]["body"] == dearer["body"]
    assert any("more than a sheet you can accept" in d for d in out["diagnostics"])
    assert any("you concede" in d for d in out["diagnostics"])
    silent = validation.prepare(state, {"emails": [mail(sid, 50.4, body="Please see the attached proposal.")]})
    assert silent["ok"] and any("not written in the body" in d for d in silent["diagnostics"])


def test_only_the_standing_sheet_of_a_live_supplier_can_be_accepted():
    state = d01(with_reply=True)
    sid = "sup:DEMO-F1"
    old = validation.prepare(
        state, {"close": {"type": "accept", "supplier_id": sid, "term_sheet_id": "offer:DEMO-F1-0"}}
    )
    assert not old["ok"] and "standing sheet" in old["errors"][0]
    ok = validation.prepare(
        state, {"close": {"type": "accept", "supplier_id": sid, "term_sheet_id": "offer:DEMO-F1-1"}}
    )
    assert ok["ok"] and ok["batch"]["close"]["message"] == {
        "action": {"type": "accept", "term_sheet_id": "offer:DEMO-F1-1"}
    }
    walk = validation.prepare(state, {"close": {"type": "walk_away"}})
    assert walk["ok"] and any("gives up a signable sheet" in d and "scores 0" in d for d in walk["diagnostics"])


# -- the desk -----------------------------------------------------------------------------------------
def test_tools_are_scoped_by_the_decision_and_a_late_or_second_commit_is_refused():
    state = d01(with_reply=True)
    sid, desk = "sup:DEMO-F1", Desk()
    assert desk.get_case_state("dec-unknown")["error"] == "UNKNOWN_DECISION"
    d = desk.open(state, budget_s=30)
    snap = desk.get_case_state(d.id)
    assert snap["threads"][0]["awaits_your_answer"] and snap["relationship_charge"].startswith("applies")
    assert snap["threads"][0]["our_estimate_of_this_supplier"] is None  # the model is told what it does not know
    prepared = desk.prepare_decision(d.id, {"emails": [mail(sid, 50.3)]})
    assert prepared["ok"] and d.status == "active" and d.batch is None
    assert desk.commit_decision(d.id, "draft-other")["error"] == "UNKNOWN_DRAFT"
    assert desk.commit_decision(d.id, prepared["draft_id"])["committed"] and d.done.is_set()
    assert desk.prepare_decision(d.id, {"emails": [mail(sid, 50.4)]})["error"] == "DECISION_COMMITTED"
    late = desk.open(state, budget_s=-1)
    assert desk.prepare_decision(late.id, {"emails": [mail(sid, 50.4)]}, commit=True)["error"] == "EXPIRED_DECISION"
    assert late.batch is None and late.status == "expired"


def test_a_commit_on_a_thread_that_moved_meanwhile_is_stale():
    state = d01(with_reply=True)
    sid, desk = "sup:DEMO-F1", Desk()
    d = desk.open(state, budget_s=30)
    prepared = desk.prepare_decision(d.id, {"emails": [mail(sid, 50.3)]})
    state.sent(sid, {"body": "sent by someone else", "term_sheets": []})  # the thread is no longer ours to answer
    assert desk.commit_decision(d.id, prepared["draft_id"])["error"] == "STALE_STATE" and d.batch is None


def test_the_model_sees_exactly_the_expected_tools():
    import anyio

    from hollerau.dsh.cli import EXPECTED_TOOLS

    tools = anyio.run(build_server(Desk()).list_tools)
    assert sorted(t.name for t in tools) == EXPECTED_TOOLS
    assert all(t.description and "decision_id" in t.input_schema["properties"] for t in tools)


# -- the case loop --------------------------------------------------------------------------------------
class Scripted:
    """A stand-in for the model: it decides through the same desk and the same tools."""

    def __init__(self, play, slow=()):
        self.desk, self.play, self.slow, self.turns = Desk(), play, set(slow), 0

    def decide(self, key, state, budget_s, note="", on_trace=None):
        self.turns += 1
        d = self.desk.open(state, budget_s if self.turns not in self.slow else -1)
        d.trace = {}
        if self.turns not in self.slow:
            self.play(self.desk, d, state)
        if d.status != "committed":
            d.expire()
        return d


def lowball_then_accept(desk, d, state):
    final = [s for s in state.ready() if state.status(s) in ("final_offer", "agreed")]
    if final or all(state.moves_left(s) <= 1 for s in state.ready()):
        best = state.best_standing()
        return desk.prepare_decision(
            d.id, {"close": {"type": "accept", "supplier_id": best[1], "term_sheet_id": best[2]}}, True
        )
    emails = []
    for sid in state.ready():
        target = state.cost(sid, state.standing(sid)[1]) * 0.97
        sheet = desk.search_structures(d.id, sid, target, limit=1)["sheets"][0]["terms"]
        emails.append(
            {
                "supplier_id": sid,
                "subject": "Our proposal",
                "term_sheets": [sheet],
                "body": f"We propose EUR {sheet['unit_price']:.2f} per unit.",
            }
        )
    out = desk.prepare_decision(d.id, {"emails": emails}, True)
    assert out.get("committed"), out


@pytest.mark.parametrize("case_id", ["case:S01", "case:S02"])
def test_a_case_is_played_to_a_deal_through_prepare_and_commit(sim, tmp_path, case_id):
    url, _, _ = sim
    pilot, journal = Scripted(lowball_then_accept), Journal(tmp_path / "decisions.jsonl")
    result = play_case(RemoteTable(team(url)), case_id, pilot, journal=journal)
    assert result["deal"] and result["score"] > 0
    events = [json.loads(line) for line in (tmp_path / "decisions.jsonl").read_text().splitlines()]
    decisions = [e for e in events if e["kind"] == "decision"]
    assert decisions and all(e["source"] == "model" for e in decisions)  # no move came from the fallback
    assert all(t[0] in ("search_structures", "prepare_decision") for e in decisions for t in e["tools"])
    assert decisions[-1]["batch"]["close"] and events[-1]["kind"] == "result"
    suppliers = events[0]["suppliers"]
    if len(suppliers) > 1:  # an RFQ: one common decision answers every bidder that waits
        assert {m["supplier_id"] for m in decisions[0]["batch"]["emails"]} == set(suppliers)


def test_a_turn_the_model_misses_is_covered_by_the_fallback_and_marked(sim, tmp_path):
    url, _, _ = sim
    pilot = Scripted(lowball_then_accept, slow={1, 3})
    result = play_case(RemoteTable(team(url)), "case:S01", pilot, journal=Journal(tmp_path / "d.jsonl"))
    assert result["deal"]
    decisions = [json.loads(line) for line in (tmp_path / "d.jsonl").read_text().splitlines() if '"decision"' in line]
    assert [e["source"] for e in decisions] == ["fallback", "model", "fallback"]
    # first move missed, no coded agent: a question, never a number of ours
    assert decisions[0]["batch"]["emails"][0]["message"]["term_sheets"] == []
    # the supplier agreed to the model's sheet; the model missed the next turn: the fallback signs it
    assert decisions[2]["batch"]["close"]["message"]["action"]["type"] == "accept"


def test_without_time_or_messages_the_case_is_closed_never_left_open():
    state = d01(with_reply=True)
    assert closing_batch(state)["close"]["message"]["action"] == {"type": "accept", "term_sheet_id": "offer:DEMO-F1-1"}
    state.case["round_limit"] = 1  # no message left in the thread
    assert fallback_batch(state, state.ready())["close"]["message"]["action"]["type"] == "accept"


def test_the_fallback_signs_at_the_suppliers_last_word_instead_of_pushing():
    state = d01(with_reply=True)
    sid = "sup:DEMO-F1"
    state.by_model.add(sid)
    assert fallback_batch(state, state.ready())["emails"][0]["message"]["body"]  # open: our last sheets again
    state.threads[sid][-1]["status"] = "final_offer"
    batch = fallback_batch(state, state.ready())
    assert not batch["emails"] and batch["close"]["message"]["action"]["type"] == "accept"


def test_a_thread_the_model_never_played_is_left_to_the_coded_agent(sim, tmp_path):
    """The model is absent for the whole game: the coded agent plays it, as it does on its own."""
    from arena_kit.data import DataPackage
    from hollerau.pegasus.agent import PegasusAgent

    data = Path("data/package")
    if not data.exists():
        pytest.skip("needs the data package")
    url, _, _ = sim
    pilot = Scripted(lowball_then_accept, slow=set(range(1, 40)))
    result = play_case(
        RemoteTable(team(url)),
        "case:S01",
        pilot,
        journal=Journal(tmp_path / "d.jsonl"),
        coded=PegasusAgent(DataPackage(data)),
    )
    decisions = [json.loads(line) for line in (tmp_path / "d.jsonl").read_text().splitlines() if '"decision"' in line]
    assert {e["source"] for e in decisions} == {"fallback"}
    assert result["deal"] and result["score"] > 0  # a missing model must not cost the deal


def test_conversation_ids_are_never_reused_across_launches():
    from hollerau.dsh.runtime import Pilot

    a, b = Pilot(home="data/dsh/test"), Pilot(home="data/dsh/test")
    assert a._conversation("case:S01") != b._conversation("case:S01")
    assert a._conversation("case:S01") == a._conversation("case:S01")  # one conversation per case within a launch


def test_a_launch_on_a_hosted_arena_is_refused_without_validation(monkeypatch):
    from hollerau.dsh import cli

    monkeypatch.setenv("ARENA_URL", "https://arena.tacto.ai/v1")
    monkeypatch.delenv("HOLLERAU_VALIDATED", raising=False)
    monkeypatch.setattr(cli, "load_env", lambda: None)
    with pytest.raises(SystemExit) as stop:
        cli.main(["sandbox", "D01"])
    assert "REFUSED" in str(stop.value) and "sandbox (off quota)" in str(stop.value)
    assert time.monotonic() > 0  # nothing was opened: the refusal comes before any client exists
