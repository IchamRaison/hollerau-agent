"""Dump one of our ENDED sessions (state with trace, threads, back office) to data/sessions/. Read-only."""

import json
import sys

from _common import ROOT

from arena_kit import ArenaClient
from arena_kit.cli import load_env

load_env()
client, sid = ArenaClient(), sys.argv[1]
state = client.session(sid)
if state.get("status") != "ended":
    raise SystemExit("session still open - this script only reads ended sessions")
out = {
    "state": state,
    "threads": {s: client.thread(sid, s) for s in state["threads"]},
    "backoffice": client.backoffice(sid),
}
path = ROOT / "data" / "sessions" / f"{sid}.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
r = state.get("result") or {}
print(f"{state['case_id']} {state.get('end_reason')} rounds={state.get('rounds')} score={r.get('score')} -> {path}")
