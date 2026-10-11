"""Offline tests of the run itself: the gate before a send, the time budget, a restart, the rehearsal."""

import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import pytest
from pegasus_helpers import CASES, opening, supplier

from arena_kit import ArenaClient, RemoteTable
from hollerau.pegasus import agent as agent_module
from hollerau.pegasus import memory, outbox, play, reader
from hollerau.pegasus.agent import PegasusAgent

ROOT = Path(__file__).resolve().parents[1]
P05, P08 = CASES["case:P05"], CASES["case:P08"]
SID = P08["suppliers"][0]


@pytest.fixture(autouse=True)
def hermetic(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_module, "TEAM_CLAIMS", False)
    monkeypatch.setattr(memory, "FILE", tmp_path / "memory.json")
    memory._mem.clear()
    yield
    memory._mem.clear()


class Journal:
    def __init__(self):
        self.lines = []

    def write(self, **entry):
        self.lines.append(entry)


def table(price=5.60, alternative=None, status="open"):
    """A P08 thread after one exchange: its opening, our offer, its reply (and an alternative)."""
    agent = PegasusAgent()
    threads = {SID: [opening(P08, SID, 6.05)]}
    out = agent.decide(P08, threads, SID)
    asked = out["message"]["term_sheets"][0]["terms"]
    threads[SID].append({**out["message"], "from": "buyer"})
    alts = [{**asked, "unit_price": alternative}] if alternative else ()
    threads[SID].append(supplier(SID, 1, {**asked, "unit_price": price}, status, alternatives=alts))
    return agent, threads


def accept(sheet):
    return {"supplier_id": SID, "message": {"action": {"type": "accept", "term_sheet_id": sheet}}}


def test_only_the_standing_sheet_of_a_live_thread_can_be_accepted():
    agent, threads = table(price=5.60, alternative=5.40)
    assert outbox.validate(agent, P08, threads, accept("offer:70710-1")) == (accept("offer:70710-1"), [])
    for wrong in ("offer:70710-1-a", "offer:70710-0", "offer:99999-1"):  # an alternative, a stale sheet, a stranger
        out, problems = outbox.validate(agent, P08, threads, accept(wrong))
        assert problems and "not sup:70710's standing sheet" in problems[0]
        assert out == accept("offer:70710-1")  # the closing move: the sheet that can be closed on


def test_a_sheet_that_breaks_a_must_have_or_loses_to_the_alternative_is_never_accepted():
    sid = P05["suppliers"][0]
    late = {"unit_price": 20.0, "payment_days": 30, "lead_time_days": 52}  # must-have: 42 days at most
    agent, threads = PegasusAgent(), {sid: [supplier(sid, 0, late)]}
    agent._prepare(P05)
    move = {"supplier_id": sid, "message": {"action": {"type": "accept", "term_sheet_id": f"offer:{sid[4:]}-0"}}}
    out, problems = outbox.validate(agent, P05, threads, move)
    assert "breaks a must-have" in problems[0] and out["message"]["action"]["type"] == "walk_away"
    agent, threads = table(price=9.00)  # dearer than buying elsewhere (the case's alternative quote)
    out, problems = outbox.validate(agent, P08, threads, accept("offer:70710-1"))
    assert "no better than the alternative" in problems[0] and out["message"]["action"]["type"] == "walk_away"


def test_we_do_not_walk_away_from_a_sheet_that_clearly_beats_the_alternative_and_the_opening():
    agent, threads = table(price=5.30)
    walk = {"supplier_id": SID, "message": {"action": {"type": "walk_away"}}}
    out, problems = outbox.validate(agent, P08, threads, walk)
    assert problems and out == accept("offer:70710-1")
    agent, threads = table(price=6.20)  # worse than its own opening: leaving is right
    assert outbox.validate(agent, P08, threads, walk) == (walk, [])


def test_an_email_is_filtered_and_a_thread_without_a_message_left_is_closed_instead():
    agent, threads = table()
    sheet = threads[SID][1]["term_sheets"][0]["terms"]
    mail = {"supplier_id": SID, "message": {"subject": "Re", "term_sheets": [{"terms": sheet}],
                                            "body": "Thank you.\nSee idx:FAKE@2026-01.\nWe have no alternative."}}
    out, problems = outbox.validate(agent, P08, threads, mail)
    assert len(problems) == 2 and out["message"]["body"] == "Thank you." and out["message"]["term_sheets"]
    case = {**P08, "round_limit": 1}  # our one message is already sent
    out, problems = outbox.validate(agent, case, threads, mail)
    assert "no message left" in problems[0] and out["message"]["action"]["type"] in ("accept", "walk_away")


def test_every_branch_of_the_agent_passes_the_gate(monkeypatch):
    agent, threads = table(price=5.60, alternative=5.40)
    agent.journal = Journal()
    monkeypatch.setattr(agent, "_decide", lambda *a, **k: accept("offer:70710-1-a"))  # a branch gone wrong
    assert agent.decide(P08, threads, SID) == accept("offer:70710-1")
    assert agent.journal.lines[-1]["outbox"] and agent.journal.lines[-1]["sent"]["term_sheet_id"] == "offer:70710-1"


def test_a_reading_never_outlives_the_decision_it_serves(monkeypatch):
    calls = []
    monkeypatch.setattr(reader, "ENABLED", True)
    monkeypatch.setattr(reader.reader_cache, "MODE", "off")
    monkeypatch.setattr(reader, "_llm", lambda lines, timeout=None: calls.append(timeout) or {"signals": []})
    text = "Faster payment would help us."
    assert "wants_faster_payment" in reader.read(text, timeout=1.0) and calls == []  # too late: keywords stand
    reader.read(text, timeout=7.5)
    reader.read(text)
    assert calls == [7.5, None]
    assert agent_module.time_left(None) is None and agent_module.time_left(time.monotonic() + 30) > 29


def test_the_opening_quotes_are_read_side_by_side_on_one_budget():
    class Table:
        done = None

        def open(self, case_id):
            a, b, c = P05["suppliers"]
            terms = {"unit_price": 30.0, "payment_days": 30, "lead_time_days": 35}
            return P05, {s: [supplier(s, 0, terms, body="Please find our quote.")] for s in (a, b, c)}

        def result(self):
            return {"deal": False}

    class Slow:
        deadlines = True

        def __init__(self):
            self.deadlines_seen = []

        def observe(self, sid, message, deadline=None):
            self.deadlines_seen.append(deadline)
            time.sleep(0.4)

        def decide(self, case, threads, sid=None, busy=(), deadline=None):
            self.deadlines_seen.append(deadline)
            return None  # nothing to send: the worker stops

    agent, t0 = Slow(), time.monotonic()
    assert play.play_case(Table(), "case:P05", agent) == {"deal": False}
    assert time.monotonic() - t0 < 1.0  # three readings of 0.4 s: side by side, not 1.2 s in a row
    assert len(agent.deadlines_seen) == 6 and all(d is not None for d in agent.deadlines_seen)
    assert play.timed(object(), 0.0) == {}  # an agent that takes no deadline is called as before


def test_the_reference_policy_resumes_where_it_was_after_a_restart():
    def exchange(agent, threads, n, price):
        out = agent.decide(P08, threads, SID)
        asked = out["message"]["term_sheets"][0]["terms"]
        threads[SID].append({**out["message"], "from": "buyer"})
        threads[SID].append(supplier(SID, n, {**asked, "unit_price": price}, body="We made a step towards you."))
        return asked["unit_price"]

    first, threads = PegasusAgent(), {SID: [opening(P08, SID, 6.05)]}
    asks = [exchange(first, threads, n, price) for n, price in ((1, 5.80), (2, 5.70), (3, 5.65))]
    assert asks == sorted(asks) and asks[0] == pytest.approx(0.80 * 6.05, abs=0.01)
    expected = first.decide(P08, threads, SID)["message"]["term_sheets"]
    restarted = PegasusAgent().decide(P08, {SID: list(threads[SID])}, SID)["message"]["term_sheets"]
    assert restarted == expected  # not the opening anchor again
    assert restarted[0]["terms"]["unit_price"] > asks[-1]


@pytest.mark.parametrize("policy", ["schedule", "actions"])
def test_the_offline_rehearsal_of_the_final_closes_every_case(policy, tmp_path):
    if not (ROOT / "data" / "package" / "facts.json").is_file():
        pytest.skip("no data package under data/package")
    env = {**os.environ, "PEGASUS_POLICY": policy, "PEGASUS_RUNS": str(tmp_path), "PEGASUS_READER": "0"}
    run = subprocess.run([sys.executable, "-m", "hollerau.pegasus.dryrun_final"], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout[-800:] + run.stderr[-800:]
    assert "RED" not in run.stdout and run.stdout.count("OK") >= 4


@pytest.mark.parametrize("policy", ["schedule", "actions"])
def test_both_policies_play_the_simulator_cases_to_an_end(sim, policy, monkeypatch):
    url, _, _ = sim
    monkeypatch.setattr(agent_module, "POLICY", policy)
    key = ArenaClient(url).register(f"test-{secrets.token_hex(3)}", "sim")["api_key"]
    client = ArenaClient(url, key, rate=1000)
    for case in client.cases("practice"):
        journal = Journal()
        result = play.play_case(RemoteTable(client), case["case_id"], PegasusAgent(journal=journal))
        assert result.get("ended") and "score" in result
        assert client.session(client.sessions("practice")[-1]["session_id"])["status"] == "ended"
        assert journal.lines and all(line["policy"] == policy for line in journal.lines)
