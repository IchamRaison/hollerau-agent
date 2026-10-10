"""Inspect what the agent understands of a case before it writes - offline, no session, no score.

  uv run python -m hollerau.pegasus.inspect [P01 P08 ...] [--json]

For each case and supplier: the constraints, what each term is worth to us, the comparable prices
with their sources and standing (fact, statement, estimate), the supplier's situation as read in
the notes, the cost hypotheses, and what stays unknown. The opening quote comes from an archived
session of the case (`analysis/pegasus_data/sessions`): it is an input of the game. Nothing here
reads a result, a score or C_best - the point is to judge the reasoning, not its outcome.
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


def main(argv=None):
    load_env()
    p = argparse.ArgumentParser(prog="pegasus-inspect")
    p.add_argument("cases", nargs="*", help="e.g. P01 P08 (default: every case with an archived opening)")
    p.add_argument("--json", action="store_true")
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
            out.append(d.to_dict() if a.json else render(d))
    print(json.dumps(out, indent=1, default=str) if a.json else "\n\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
