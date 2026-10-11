"""uv run pegasus-dsh preflight --offline | sandbox D01 D02 | practice P01 ... | final

The DSH pilot: gpt-6.1-sol (by default) negotiates each case through DeepSeek Harness and our
tools. `preflight --offline` checks the installation without calling a model or opening a
session. Every command that opens a session on a hosted arena goes through the launch lock
(`hollerau.sessions`): it refuses without HOLLERAU_VALIDATED; the local simulator is free.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from arena_kit.cli import load_env

from ..sessions import require_validation
from . import runtime
from .tools import Desk, build_server

EXPECTED_TOOLS = [
    "commit_decision",
    "evaluate_offers",
    "get_case_state",
    "lookup_facts",
    "prepare_decision",
    "query_data",
    "read_thread",
    "search_structures",
    "set_supplier_estimate",
    "update_hypotheses",
]
# rows of the shipped profile that give a coding agent its hands: none may reach the model
FORBIDDEN_ROWS = [
    "tool-bash",
    "tool-fs",
    "tool-fs-search",
    "tool-web",
    "tool-subagent",
    "tool-workflow",
    "tool-jobs",
    "tool-skill",
    "agent-instructions",
    "session-telemetry-otel",
    "session-log-deepseek",
]


def preflight(offline=True):
    """[(check, ok, detail)] - nothing here calls a model or opens a session."""
    import anyio

    out = []

    def check(name, fn):
        try:
            out.append((name, True, fn() or ""))
        except Exception as e:
            out.append((name, False, f"{type(e).__name__}: {e}"[:300]))

    check(
        "harness profile patch",
        lambda: str(runtime.PATCH.relative_to(runtime.ROOT)) if runtime.PATCH.is_file() else 1 / 0,
    )
    check("negotiator prompt", lambda: f"{len(runtime.PROMPT.read_text(encoding='utf-8'))} characters")

    def versions():
        from importlib.metadata import version

        return f"deepseek-harness-sdk {version('deepseek-harness-sdk')}, mcp {version('mcp')}"

    check("pinned packages", versions)

    def tools():
        names = sorted(t.name for t in anyio.run(build_server(Desk()).list_tools))
        if names != EXPECTED_TOOLS:
            raise ValueError(f"tools {names} differ from the expected {EXPECTED_TOOLS}")
        return f"{len(names)} tools"

    check("tool server", tools)

    def profile():
        from deepseek_harness_runtime import resolve_bundled_launch_args

        home = runtime.ROOT / "data" / "dsh" / "preflight"
        home.mkdir(parents=True, exist_ok=True)
        env = {
            **os.environ,
            "DSH_HOME": str(home),
            "TACTO_PROMPT": "preflight",
            "TACTO_MCP_URL": "http://127.0.0.1:9/mcp",
        }
        r = subprocess.run(
            [resolve_bundled_launch_args()[0], "--profile", "sdk", "--patch", str(runtime.PATCH), "--dump-config"],
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
            cwd=str(home),
        )
        if r.returncode:
            raise RuntimeError(r.stderr.strip()[-300:])
        rows, live = r.stdout.split("\n- id: "), []
        for row in rows[1:]:
            name = row.split("\n", 1)[0].strip()
            if name in FORBIDDEN_ROWS and "disabled: true" not in row:
                live.append(name)
        if live:
            raise ValueError(f"profile rows still enabled: {live}")
        if "mcp-tacto" not in r.stdout or runtime.PROVIDER not in r.stdout:
            raise ValueError("the patch did not add our tool server or the model route")
        return f"{len(rows) - 1} rows, coding tools off"

    check("harness profile composes", profile)

    def boots():
        """The real runtime with our profile and our tool server: starts, discovers the tools, stops."""
        t0 = time.monotonic()
        with runtime.Pilot(home=runtime.ROOT / "data" / "dsh" / "preflight"):
            return f"runtime and tool server up in {time.monotonic() - t0:.1f} s"

    if runtime.model_key():
        check("harness starts with our profile", boots)
    check("model key present", lambda: "set" if runtime.model_key() else 1 / 0)

    def lock():
        from .. import sessions

        if sessions.is_local("https://arena.tacto.ai/v1") or not sessions.is_local("http://127.0.0.1:8000"):
            raise ValueError("the launch lock does not tell hosted from local")
        return "hosted launches need HOLLERAU_VALIDATED"

    check("launch lock", lock)
    return out


def _package():
    from arena_kit.data import DataPackage

    data_dir = os.environ.get("ARENA_DATA", "data/package")
    base = DataPackage(data_dir)
    index = base._ids

    def new():
        p = DataPackage(data_dir)
        p.__dict__["_ids"] = index
        return p

    return new


def main(argv=None):
    load_env()
    p = argparse.ArgumentParser(prog="pegasus-dsh", description=__doc__.split("\n\n")[0])
    p.add_argument("command", choices=["preflight", "sandbox", "practice", "final"])
    p.add_argument("cases", nargs="*", help="e.g. D01 D02")
    p.add_argument("--offline", action="store_true", help="preflight: no model call, no session")
    p.add_argument("--parallel", type=int, default=10)
    p.add_argument("--no-coded-opening", action="store_true", help="no coded agent behind a missed first move")
    p.add_argument("-v", action="store_true")
    a = p.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if a.v else logging.WARNING, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
    )
    for noisy in ("httpx", "mcp", "uvicorn"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if a.command == "preflight":
        checks = preflight(a.offline)
        for name, ok, detail in checks:
            print(f"{'ok  ' if ok else 'FAIL'} {name}: {detail}")
        failed = [n for n, ok, _ in checks if not ok]
        print("preflight " + ("FAILED: " + ", ".join(failed) if failed else "passed (no model call, no session)"))
        return 1 if failed else 0

    from arena_kit import ArenaClient
    from arena_kit.play import RemoteTable, hosted

    from ..pegasus.agent import PegasusAgent
    from .coordinator import Journal, play_case

    n = len(a.cases) or 10
    require_validation(f"pegasus-dsh {a.command} {' '.join(a.cases)}".strip(), n, quota=a.command == "practice")
    new_package = _package()
    client = ArenaClient()
    run_dir = Path(os.environ.get("PEGASUS_RUNS", "data/runs")) / time.strftime("dsh-%Y%m%dT%H%M%SZ", time.gmtime())
    journal = Journal(run_dir / "decisions.jsonl")
    with runtime.Pilot() as pilot:

        def one(case_or_id, deadline=None):
            cid = case_or_id["case_id"] if isinstance(case_or_id, dict) else case_or_id
            table = RemoteTable(client, case_or_id if isinstance(case_or_id, dict) else None)
            pkg = new_package()
            coded = None if a.no_coded_opening else PegasusAgent(pkg)
            try:
                return cid, play_case(table, cid, pilot, pkg, deadline, journal, coded)
            except Exception as e:
                logging.getLogger("pegasus.dsh").exception("%s failed", cid)
                return cid, e

        if a.command == "final":
            results = _waves(client, one, a.parallel)
        else:
            ids = [c if c.startswith("case:") else f"case:{c}" for c in a.cases]
            if not ids:
                ids = [c["case_id"] for c in hosted(client.cases(a.command))]
            with ThreadPoolExecutor(max_workers=a.parallel) as pool:
                results = dict(pool.map(one, ids))
    scores = []
    for cid, r in sorted(results.items()):
        if isinstance(r, Exception):
            print(f"{cid}: ERROR {r}")
            continue
        scores.append(r.get("score") or 0)
        print(
            f"{cid}: score={r.get('score')} deal={r.get('deal')} c_deal={r.get('c_deal')} c_open={r.get('c_open')} "
            f"c_best={r.get('c_best')} terms={json.dumps(r.get('terms'))}"
        )
    if scores:
        print(f"mean score: {100 * sum(scores) / len(scores):.1f}")
    print(f"journal: {journal.path}")
    return 0


def _waves(client, one, parallel, waves=5, poll=5.0):
    """The Live Final: every case of a started wave, in parallel, until the last wave has closed."""
    import functools

    from arena_kit.client import ArenaError

    started, closed, caps = {}, set(), {}
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        while len(closed) < waves or not all(f.done() for f in started.values()):
            try:
                cases = client.cases("final")
            except ArenaError as e:
                if e.status != 403:
                    raise
                cases = []
            for case in cases:
                if not case.get("open"):
                    closed.add(case["wave"])
                    continue
                if case.get("seconds_left") is not None:
                    caps[case["wave"]] = time.time() + case["seconds_left"]
                if case["case_id"] not in started and case.get("seconds_left"):
                    started[case["case_id"]] = pool.submit(one, case, functools.partial(caps.get, case["wave"]))
            time.sleep(poll)
    return dict(f.result() for f in started.values())


if __name__ == "__main__":
    sys.exit(main())
