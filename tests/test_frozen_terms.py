"""PEGASUS_FROZEN_TERMS: the supplier's price list is frozen -> keep its price, ask for the best terms.

Offline: every case is played against the kit's scripted simulator in-process (no network, no session).
`main_sheets.json` holds what pegasus on origin/main (4fabd57) sent in those games: with the flag off the
sheets must be the same, byte for byte. Needs the data package with the Sunday release (data/, ignored by
Git), as the freeze is read from its letters - skipped without it.

    regenerate the reference from a checkout of main:  python tests/test_frozen_terms.py <checkout> > ...
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "package"
CASES = ROOT / "tests" / "fixtures" / "cases" / "practice.json"
REFERENCE = ROOT / "tests" / "fixtures" / "frozen_terms" / "main_sheets.json"
MAX_MOVES = 40


def play(case, pkg, agent):
    """Our moves in one game against the simulator's scripted supplier: action and term sheets."""
    from arena_kit.play import live_threads
    from arena_kit.sim import Fail, Sim

    sim = Sim({case["case_id"]: case}, pkg.facts, no_clock=True)
    opened = sim.open("offline", case["case_id"])
    sid, threads, moves = opened["session_id"], {k: list(v) for k, v in opened["threads"].items()}, []
    for _ in range(MAX_MOVES):
        if sim.sessions[sid]["status"] != "open" or not live_threads(threads):
            break
        decision = agent.decide(case, threads)
        sup, msg = decision["supplier_id"], decision["message"]
        moves.append({"supplier": sup, "action": msg.get("action"),
                      "sheets": [ts["terms"] for ts in msg.get("term_sheets") or []]})
        try:
            reply = sim.message("offline", sid, sup, msg)
        except Fail as e:
            moves.append({"error": e.detail})
            break
        if "result" in reply:
            break
        threads[sup] += [{**msg, "from": "buyer"}, reply]
    return moves


def play_all(memory_file):
    """{case_id: moves} for the 19 practice cases, with a fresh agent and no supplier memory."""
    from arena_kit.data import DataPackage
    from hollerau.pegasus import memory
    from hollerau.pegasus.agent import PegasusAgent

    memory.FILE = Path(memory_file)
    pkg = DataPackage(str(DATA))
    return {c["case_id"]: play(c, pkg, PegasusAgent(package=pkg)) for c in json.loads(CASES.read_text())}


needs_data = pytest.mark.skipif(not (DATA / "facts.json").exists() or not REFERENCE.exists(),
                                reason="needs data/ (arena data, with the Sunday release)")


@pytest.fixture
def games(tmp_path, monkeypatch):
    from hollerau.pegasus import agent

    def run(on):
        monkeypatch.setattr(agent, "FROZEN_TERMS", on)
        return play_all(tmp_path / f"memory-{on}.json")

    return run


@needs_data
def test_flag_off_plays_as_main(games):
    assert games(False) == json.loads(REFERENCE.read_text())


# the frozen price lists in the data: P02 from the Sunday release (PR #17), P03 already in the package
FROZEN = {"case:P02": ("sup:70510", "doc:20261001-70510-S5"),  # "Price list 2027 ... without exception"
          "case:P03": ("sup:70530", "doc:20260826-70530-M1")}  # "head office has frozen all price reductions"


@needs_data
@pytest.mark.parametrize("case_id", sorted(FROZEN))
def test_flag_on_keeps_its_price_on_the_best_terms(games, case_id):
    from arena_kit.data import DataPackage
    from hollerau.evidence.economics import compile_case
    from hollerau.pegasus.intel_bridge import Intelligence

    case = next(c for c in json.loads(CASES.read_text()) if c["case_id"] == case_id)
    pkg = DataPackage(str(DATA))
    supplier, letter = FROZEN[case_id]
    frozen = [s for s in Intelligence(pkg).brief(case, supplier)["signals"] if s["type"] == "price_frozen"]
    assert letter in json.dumps(frozen)

    moves = games(True)[case_id]
    first = moves[0]["sheets"]
    assert len(first) == 1
    assert first[0]["unit_price"] == round(case["buyer"]["current_unit_price"] * 1.10, 2)  # the simulator's ask
    best = compile_case(case, None, pkg).best_package
    assert {f: first[0][f] for f in best} == best
    assert all(s == first[0] for m in moves for s in m["sheets"])  # no price pressure afterwards either


@needs_data
def test_flag_on_changes_no_other_case(games):
    on, main = games(True), json.loads(REFERENCE.read_text())
    assert {c for c in main if on[c] != main[c]} == set(FROZEN)


if __name__ == "__main__":  # the reference, from a checkout of main: python tests/test_frozen_terms.py <checkout>
    import tempfile

    sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
    with tempfile.TemporaryDirectory() as tmp:
        print(json.dumps(play_all(Path(tmp) / "memory.json"), indent=1, sort_keys=True))
