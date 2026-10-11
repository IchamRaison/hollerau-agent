"""uv run python lab/dsh_fetch.py  ->  analysis/pegasus_data/sessions/<case>-<sid>.json

Every ENDED session of our team that is not in the archive yet: its state with the trace and the
supplier's back office, in the archive's format. Read-only: lists and reads finished sessions,
opens none. Slow on purpose - the key is shared by the team (10 calls per second in all).
"""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "analysis" / "pegasus_data" / "sessions"
PAUSE = 0.4


def main():
    from arena_kit import ArenaClient
    from arena_kit.cli import load_env

    load_env(str(ROOT / ".env"))
    if os.environ.get("ARENA_HOSTED_URL"):
        os.environ["ARENA_URL"] = os.environ["ARENA_HOSTED_URL"]
    client = ArenaClient()
    have = {p.stem.split("-", 1)[1] for p in OUT.glob("*.json")}
    listed, new, skipped = 0, 0, 0
    for set_ in ("practice", "sandbox"):
        rows = client.sessions(set_)
        rows = rows if isinstance(rows, list) else rows.get("sessions", [])
        listed += len(rows)
        todo = [r for r in rows if r.get("status") == "ended" and r["session_id"] not in have]
        print(f"{set_}: {len(rows)} listed, {len(todo)} ended and not archived", flush=True)
        for r in todo:
            sid = r["session_id"]
            try:
                time.sleep(PAUSE)
                state = client.session(sid)
                time.sleep(PAUSE)
                back = client.backoffice(sid)
            except Exception as e:
                skipped += 1
                print(f"  {sid}: {type(e).__name__} {str(e)[:120]}", flush=True)
                continue
            back = back if isinstance(back, list) else back.get("backoffice", back.get("messages", back))
            case = str(state.get("case_id", r.get("case_id", "case:unknown"))).split(":")[-1]
            path = OUT / f"{case}-{sid}.json"
            path.write_text(json.dumps({"summary": r, "session": state, "backoffice": back}, ensure_ascii=False))
            new += 1
            if new % 25 == 0:
                print(f"  {new} written", flush=True)
    print(f"done: {listed} listed, {new} written, {skipped} skipped, archive now {len(list(OUT.glob('*.json')))}")


if __name__ == "__main__":
    main()
