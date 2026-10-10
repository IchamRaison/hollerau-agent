"""Run a campaign: a plan module turns the case files into run specs; this runner orders, resumes and executes them.

  uv run python -m lab.campaign <plan> --list
  HOLLERAU_VALIDATED="who, what" uv run python -m lab.campaign <plan> --pilot 6
  HOLLERAU_VALIDATED="who, what" uv run python -m lab.campaign <plan> --run --parallel 6

A plan is `lab/plans/<plan>.py` with `runs(cases) -> list[run spec]` (see lab/engine.py) and optionally
`CASE_SET = "sandbox"`. Outputs go to data/campaign/<plan>/: manifest.json, rows.jsonl (one line per
supplier reply), runs/<run_id>.json (full record with trace and back office), log.txt.
The runner never opens a session without validation, stops if the practice quota moves during a sandbox
campaign, and stops after 5 failed runs in a row.
"""

import argparse
import importlib
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from arena_kit import ArenaClient
from arena_kit.cli import load_env
from hollerau.sessions import is_local, require_validation

from .engine import ROOT, play_run


def order(specs, seed):
    """Seeded order that spreads every block over the whole campaign (guards against drift in time)."""
    rng = random.Random(seed)
    by_block = {}
    for s in specs:
        by_block.setdefault(s.get("block"), []).append(s)
    keyed = []
    for runs in by_block.values():
        rng.shuffle(runs)
        keyed += [((i + rng.random()) / len(runs), s) for i, s in enumerate(runs)]
    return [s for _, s in sorted(keyed, key=lambda k: k[0])]


def pilot(specs, n):
    """One run per block, in turn, until n runs."""
    seen, out = {}, []
    for s in specs:
        seen.setdefault(s.get("block"), []).append(s)
    while len(out) < n and any(seen.values()):
        for runs in seen.values():
            if runs and len(out) < n:
                out.append(runs.pop(0))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("plan")
    p.add_argument("--list", action="store_true")
    p.add_argument("--pilot", type=int)
    p.add_argument("--run", action="store_true")
    p.add_argument("--only", help="comma-separated blocks")
    p.add_argument("--parallel", type=int, default=6)
    p.add_argument("--seed", type=int, default=1)
    a = p.parse_args()
    load_env()
    plan = importlib.import_module(f"lab.plans.{a.plan}")
    client = ArenaClient()
    case_set = "practice" if is_local() else getattr(plan, "CASE_SET", "sandbox")
    cases = {c["case_id"]: c for c in client.cases(case_set)}
    specs = order(plan.runs(cases), a.seed)
    ids = [s["run_id"] for s in specs]
    assert len(ids) == len(set(ids)), "duplicate run_id in the plan"
    if a.only:
        specs = [s for s in specs if s.get("block") in a.only.split(",")]
    out = ROOT / "data" / "campaign" / a.plan
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(specs, indent=1, ensure_ascii=False))
    blocks = {}
    for s in specs:
        blocks[s.get("block")] = blocks.get(s.get("block"), 0) + 1
    print(f"plan {a.plan}: {len(specs)} runs on {case_set} | blocks: {blocks}")
    if a.list or not (a.run or a.pilot):
        return
    todo = [
        s for s in (pilot(specs, a.pilot) if a.pilot else specs) if not (out / "runs" / f"{s['run_id']}.json").exists()
    ]
    quota = any(s["case_id"].startswith("case:P") for s in todo) and not is_local()
    require_validation(f"campaign {a.plan}" + (f" (pilot {a.pilot})" if a.pilot else ""), len(todo), quota=quota)
    used0 = None if is_local() else client.me()["practice"]["used"]
    stop, bad, done, t0 = threading.Event(), [0], [0], time.monotonic()

    def one(spec):
        if stop.is_set():
            return spec, None, "skipped"
        try:
            return spec, play_run(spec, client, out), None
        except Exception as e:  # one broken run must not stop the campaign
            return spec, None, f"{type(e).__name__}: {e}"

    log = (out / "log.txt").open("a")
    with ThreadPoolExecutor(max_workers=min(a.parallel, 6)) as pool:
        for fut in as_completed([pool.submit(one, s) for s in todo]):
            spec, rec, err = fut.result()
            done[0] += 1
            if err == "skipped":
                continue
            if err:
                bad[0] += 1
                line = f"[{done[0]}/{len(todo)}] {spec['run_id']} FAILED {err}"
                with (out / "failures.jsonl").open("a") as f:
                    f.write(json.dumps({"run_id": spec["run_id"], "error": err}) + "\n")
                if bad[0] >= 5:
                    stop.set()
            else:
                bad[0] = 0
                res, fin = rec["result"], rec["final"]
                score = "-" if res.get("score") is None else f"{res['score']:.2f}"
                line = (
                    f"[{done[0]}/{len(todo)}] {spec['run_id']} deal={res.get('deal')} score={score} "
                    f"rounds={[v['sent'] for v in fin.values()]} status={[v['status'] for v in fin.values()]} {rec['total_s']}s"
                    + (f" ERRORS={len(rec['errors'])}" if rec["errors"] else "")
                )
            print(line, flush=True)
            log.write(line + "\n")
            log.flush()
            if used0 is not None and not quota and done[0] % 40 == 0 and client.me()["practice"]["used"] != used0:
                print("STOP: the practice quota moved during a sandbox campaign", flush=True)
                stop.set()
    elapsed = time.monotonic() - t0
    tail = f"done: {done[0]} runs in {elapsed / 60:.1f} min, stopped early: {stop.is_set()}"
    if used0 is not None:
        tail += f", practice sessions used before/after: {used0}/{client.me()['practice']['used']}"
    print(tail)
    log.write(tail + "\n")
    sys.exit(1 if stop.is_set() else 0)


if __name__ == "__main__":
    main()
