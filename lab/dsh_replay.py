"""uv run python lab/dsh_replay.py <run dir>  -  the finished games of a DSH run, move by move.

Reads the run's journal for its session ids, fetches each ENDED session from the arena (a read:
it opens nothing) and prints, per supplier thread, our asks and its offers in our cost units,
the checks of our arguments and the supplier's reasons in its own words. Saves the sessions
next to the journal.
"""

import json
import sys
from pathlib import Path

from arena_kit import ArenaClient
from arena_kit.cli import load_env
from arena_kit.cost import total_cost


def cost(case, terms):
    try:
        c = total_cost(case, terms)
        return None if c == float("inf") else round(c)
    except Exception:
        return None


def main(run_dir, full=False):
    load_env()
    run = Path(run_dir)
    opened = [json.loads(line) for line in (run / "decisions.jsonl").read_text().splitlines() if '"opened"' in line]
    client = ArenaClient()
    cases = {c["case_id"]: c for s in ("sandbox", "practice") for c in client.cases(s)}
    (run / "sessions").mkdir(exist_ok=True)
    for o in opened:
        s = client.session(o["session"])
        (run / "sessions" / f"{o['case'].split(':')[-1]}-{o['session']}.json").write_text(json.dumps(s))
        r, case = s.get("result") or {}, cases[o["case"]]
        span = (r.get("c_open") or 0) - (r.get("c_best") or 0)
        print(f"\n===== {o['case']} score {r.get('score'):.3f}  c_open {r.get('c_open')}  c_deal {r.get('c_deal')}  "
              f"c_best {r.get('c_best')}  deal terms {r.get('terms') and {k: v for k, v in r['terms'].items() if k in case['negotiable']}}")
        trace = r.get("trace") or []
        sups = list(dict.fromkeys(e["actor"] for e in trace if e["actor"] != "buyer"))
        for sup in sups:
            print(f"--- {sup}")
            for e in trace:
                m = e.get("move") or {}
                if e["actor"] == "buyer":
                    if (m.get("supplier_id") or sups[0]) != sup:
                        continue
                    if m.get("type") in ("accept", "walk_away"):
                        print(f"  [{e['round']}] WE {m['type']} {m.get('offer_id', '')}")
                        continue
                    sheets = [(t.get("terms", t), cost(case, t.get("terms", t))) for t in m.get("term_sheets") or []]
                    print(f"  [{e['round']}] WE ask {[(t.get('unit_price'), c) for t, c in sheets]} "
                          f"depth {[round(100 * (r['c_open'] - c) / span) for _, c in sheets if c] if span else ''}% refs {m.get('refs')}")
                    if full:
                        print("        ", (m.get("body") or "").replace("\n", " / ")[:1200])
                elif e["actor"] == sup:
                    sheets = [m.get("terms") or {}] + [a.get("terms") or {} for a in m.get("alternatives") or []]
                    cs = [cost(case, t) for t in sheets if t.get("unit_price") is not None]
                    print(f"  [{e['round']}] IT {m.get('status'):11} {[t.get('unit_price') for t in sheets]} cost {cs} "
                          f"at {[round(100 * (r['c_open'] - c) / span) for c in cs if c] if span else ''}%  claims {[c.get('result') for c in m.get('claim_results') or []]}")
                    for reason in e.get("reasons") or []:
                        print("        .", reason[:230])
                    if full:
                        print("        TEXT:", (m.get("text") or "").replace("\n", " / ")[:900])


if __name__ == "__main__":
    main(sys.argv[1], full="--full" in sys.argv)
