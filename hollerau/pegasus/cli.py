"""uv run pegasus practice [P01 P04 ...] | sandbox D01 | final        (the official command)

Plays with the pegasus agent and prints one line per case (score, C) plus the replay links.
`--playbook file.json`: per case {"target_c": ...} learnt from practice results.
Before any session opens, the resolved configuration is written under data/runs/ (`runconfig`):
code commit, settings, data, initial memory, reader cache. Decisions and results go next to it.
"""

import argparse
import json
import logging
import os
import sys

from arena_kit import ArenaClient
from arena_kit.cli import load_env
from arena_kit.data import DataPackage
from arena_kit.play import hosted

from ..sessions import require_validation
from . import runconfig
from .agent import PegasusAgent
from .play import play_cases, play_waves


def main(argv=None):
    load_env()
    p = argparse.ArgumentParser(prog="pegasus")
    p.add_argument("set", choices=["practice", "sandbox", "final"])
    p.add_argument("cases", nargs="*", help="e.g. P01 P04 (default: every hosted case)")
    p.add_argument("--parallel", type=int, default=5)
    p.add_argument("--playbook")
    p.add_argument("--push-after-final", action="store_true")
    p.add_argument("-v", action="store_true")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.v else logging.WARNING, format="%(asctime)s %(message)s",
                        datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    data_dir = os.environ.get("ARENA_DATA", "data/package")
    base = DataPackage(data_dir)  # fail now, before any session opens, if the package is missing
    index = base._ids  # the ID index, built once here: read-only from now on, so the agents can share it
    playbook = json.load(open(a.playbook)) if a.playbook else {}

    def package():
        """One package per agent: a DataPackage holds a single SQLite connection, not safe to share
        between the parallel cases (R1: "no such table: None"). The ID index is the base's: built
        by each agent at once, it took 3.5 s with 6 agents and 14 s with 10 (0.02 s shared)."""
        p = DataPackage(data_dir)
        p.__dict__["_ids"] = index  # a cached_property lives in the instance's __dict__
        return p

    n = len(a.cases) or 10
    require_validation(f"pegasus {a.set} {' '.join(a.cases)}".strip(), n, quota=a.set == "practice")
    run_dir, cfg = runconfig.record(a.set, a.cases, a.parallel, a.playbook, data_dir)
    print(f"[{runconfig.describe(cfg)}] -> {run_dir or 'not written'}", file=sys.stderr)
    journal = runconfig.Journal(run_dir)
    new_agent = lambda: PegasusAgent(package(), playbook, a.push_after_final, journal=journal)  # noqa: E731
    client = ArenaClient()
    if a.set == "final":
        results = play_waves(client, new_agent, parallel=a.parallel)
    else:
        ids = [c if c.startswith("case:") else f"case:{c}" for c in a.cases]
        if not ids:
            ids = [c["case_id"] for c in hosted(client.cases(a.set))]
        results = play_cases(client, ids, new_agent, parallel=a.parallel)
    scores = []
    for cid, r in sorted(results.items()):
        if isinstance(r, Exception):
            print(f"{cid}: ERROR {r}")
            continue
        scores.append(r.get("score") or 0)
        print(f"{cid}: score={r.get('score')} deal={r.get('deal')} c_deal={r.get('c_deal')} "
              f"c_open={r.get('c_open')} c_best={r.get('c_best')} terms={json.dumps(r.get('terms'))}")
    if scores:
        print(f"mean score: {100 * sum(scores) / len(scores):.1f}")
    runconfig.save(run_dir, "results.json", {cid: (str(r) if isinstance(r, Exception) else r)
                                             for cid, r in results.items()})
    try:
        print("practice left:", client.me()["practice"]["left"])
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
