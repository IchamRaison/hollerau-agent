"""Inspect what the agent understands of a case before it writes - offline, no session, no score.

  uv run python -m hollerau.pegasus.inspect [P01 P08 ...] [--json] [--move]

For each case and supplier: the constraints, what each term is worth to us, the comparable prices
with their sources and standing (fact, statement, estimate), the supplier's situation as read in
the notes, the cost hypotheses, and what stays unknown. The opening quote comes from an archived
session of the case (`analysis/pegasus_data/sessions`): it is an input of the game. Nothing here
reads a result, a score or C_best - the point is to judge the reasoning, not its outcome.
`--move` adds the first move the action policy would make on that opening quote: what it rests on,
the sheets, the e-mail. It is computed locally; nothing is sent.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from arena_kit.cli import load_env
from arena_kit.data import DataPackage

from . import dossier as dossiers
from . import replay
from .agent import supplier_reference
from .intel_bridge import Intelligence

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "tests" / "fixtures" / "cases" / "practice.json"
SESSIONS = ROOT / "analysis" / "pegasus_data" / "sessions"


def render(d):
    """A dossier as text a person can check line by line."""
    lines = [f"{d.case_id}  {d.supplier_id}"]
    c = d.constraints
    lines.append(f"  goal {c.get('category_goal')}, negotiable {', '.join(c.get('negotiable', []))}; "
                 f"must-haves {c.get('must_haves') or 'none'}")
    alt = d.alternative
    lines.append("  alternative: " + ("none" if alt.get("c_alt") == float("inf")
                                      else f"{alt.get('kind')} {alt.get('ref') or ''} C={alt['c_alt']:,.0f}"))
    if d.levers:
        lines.append("  worth to us (EUR if left at its worst value): "
                     + "; ".join(f"{lv['field']} {lv['worst']}->{lv['best']}: {lv['eur']:,.0f}" for lv in d.levers))
    for title, items in (("comparable prices", d.references), ("supplier situation", d.situation),
                         ("it states", d.stated)):
        if items:
            lines.append(f"  {title}:")
            lines += [f"    [{i.status:9}] {i.key} = {i.value}  ({', '.join(map(str, i.sources[:4]))})"
                      + (f"  - {i.note}" if i.note else "") for i in items]
    if d.hypotheses:
        lines.append("  supplier cost hypotheses (relationship charge):")
        lines += [f"    {h['name']}: full cost {h['supplier']['full_cost']:.2f} - {h['provenance']}"
                  for h in d.hypotheses]
    lines.append("  unknown:")
    lines += [f"    - {u}" for u in d.unknowns]
    if d.diagnostics:
        lines += ["  diagnostics:"] + [f"    ! {x}" for x in d.diagnostics]
    return "\n".join(lines)


class Capture:
    """A journal kept in memory."""

    def __init__(self):
        self.lines = []

    def write(self, **entry):
        self.lines.append(entry)


def first_move(case, package, threads, sid):
    """The action policy's first move on this opening, as text. Uses an empty supplier memory: a
    case we have never played is the situation of the final."""
    from . import agent as agent_module
    from . import memory

    was, memory_file = agent_module.POLICY, memory.FILE
    agent_module.POLICY, memory.FILE = "actions", Path(os.devnull).with_name("pegasus-no-memory.json")
    memory._mem.clear()
    try:
        journal = Capture()
        out = agent_module.PegasusAgent(package, journal=journal).decide(case, threads, sid)
    finally:
        agent_module.POLICY, memory.FILE = was, memory_file
        memory._mem.clear()
    move = journal.lines[-1]["considered"][0] if journal.lines else {}
    basis = (move.get("evaluation") or {}).get("basis") or {}
    lines = [f"  first move: {journal.lines[-1]['chosen'] if journal.lines else '?'} - {move.get('why', '')}"]
    if basis.get("others"):
        lines.append("    other prices it could have rested on: "
                     + ", ".join(f"{o['key']} {o['price']}" for o in basis["others"]))
    if basis.get("floored"):
        lines.append(f"    {basis['floored']}")
    for ts in (out.get("message") or {}).get("term_sheets") or []:
        t = ts["terms"]
        terms = {k: ((v or {}).get("series", "none") if k == "index_clause" else v) for k, v in t.items()}
        lines.append(f"    sheet: EUR {t['unit_price']} | "
                     + ", ".join(f"{k}={v}" for k, v in terms.items() if k != "unit_price"))
    body = ((out.get("message") or {}).get("body") or "").split("\n")
    lines += [f"    > {x}" for x in body if x.strip() and not x.startswith(("Dear", "Best regards", "Hollerau"))]
    return "\n".join(lines)


def main(argv=None):
    load_env()
    p = argparse.ArgumentParser(prog="pegasus-inspect")
    p.add_argument("cases", nargs="*", help="e.g. P01 P08 (default: every case with an archived opening)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--move", action="store_true", help="also the action policy's first move (nothing is sent)")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.ERROR)
    cases = {c["case_id"]: c for c in json.loads(CASES.read_text())}
    wanted = [f"case:{c.split(':')[-1]}" for c in a.cases] or sorted(cases)
    data_dir = os.environ.get("ARENA_DATA", "data/package")
    package = DataPackage(data_dir) if (Path(data_dir) / "facts.json").is_file() else None
    intel = Intelligence(package) if package else None
    out = []
    for cid in wanted:
        case = cases.get(cid)
        threads = replay.openings(SESSIONS, cid) if case else {}
        if not threads:
            if a.cases:
                print(f"{cid}: no archived opening quote - nothing to inspect offline", file=sys.stderr)
            continue
        for sid, events in threads.items():
            d = dossiers.prepare(case, package, sid, events, supplier_reference(case, events), intel)
            if a.json:
                out.append(d.to_dict())
            else:
                out.append(render(d) + ("\n" + first_move(case, package, threads, sid) if a.move else ""))
    print(json.dumps(out, indent=1, default=str) if a.json else "\n\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
