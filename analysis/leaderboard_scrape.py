"""Public intel scrape (A4): what the arena exposes without opening a session.

Read-only GETs against public endpoints (leaderboard, events feed, replays) plus our own
session lists. No session is opened; nothing touches the practice quota.

Findings (10/10 evening):
  - /v1/events is PUBLIC (no key): every team's session_key, case, supplier, status per
    message, both practice and sandbox modes. Text is null: no message bodies leak.
  - /replay/{sid} is PUBLIC (no key) - but needs the full 16-hex session id; events only
    carry a 12-hex session_key, so foreign replays stay unreachable (id-space too large).
  - /v1/sessions and /v1/sessions/{sid}/backoffice are scoped to our key (verified 404).
  - Our own sandbox history (~90 sessions) shows scores repeated to 16 decimals across
    sessions: strong determinism evidence (feeds B1).

Run: uv run python analysis/leaderboard_scrape.py
"""

import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE = os.environ.get("ARENA_URL", "https://arena.tacto.ai")
OUT = Path(__file__).resolve().parent.parent / "data" / "leaderboard"
OUT.mkdir(parents=True, exist_ok=True)


def call(method, path, key=None, raw=False):
    req = urllib.request.Request(BASE + path, method=method)
    if key:
        req.add_header("X-API-Key", key)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            return r.status, data if raw else json.loads(data or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}
    except Exception as e:  # noqa: BLE001
        return 0, {"error": str(e)}


def key_from_env():
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ARENA_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    return os.environ.get("ARENA_API_KEY")


def walk_events():
    """Pull the whole public event history via before_id pagination."""
    st, first = call("GET", "/v1/events")
    events, lo = list(first["events"]), min(e["id"] for e in first["events"])
    while True:
        st, page = call("GET", f"/v1/events?before_id={lo}")
        if st != 200 or not page.get("events"):
            break
        batch = page["events"]
        events += batch
        lo = min(e["id"] for e in batch)
        if len(batch) < 200:
            break
    return events


def main():
    key = key_from_env()
    have = f"yes (...{key[-4:]})" if key else "NONE"
    print(f"arena: {BASE}  key: {have}")

    # 1. public leaderboard
    st, board = call("GET", "/v1/leaderboard?set=practice")
    teams = board.get("teams", []) if isinstance(board, dict) else []
    print(f"\nleaderboard: {st}, {len(teams)} teams")
    for t in teams[:12]:
        print(f"  #{t.get('rank')} {t.get('team_name')}: total={t.get('total')} played={t.get('played')} "
              f"deals={t.get('deals')} rounds={t.get('rounds')}")
    (OUT / "leaderboard.json").write_text(json.dumps(board, indent=1))

    # 2. our sessions (practice + sandbox): the determinism evidence
    ours = {}
    if key:
        for set_ in ("practice", "sandbox"):
            st, sess = call("GET", f"/v1/sessions?set={set_}", key)
            if st == 200 and isinstance(sess, list):
                ours[set_] = sess
        (OUT / "our_sessions.json").write_text(json.dumps(ours, indent=1))
        for set_, sess in ours.items():
            per_case = {}
            for s in sess:
                per_case.setdefault(s["case_id"], []).append(s["score"])
            print(f"\nour {set_} sessions: {len(sess)}")
            for case, scores in sorted(per_case.items()):
                counts = Counter(round(sc, 16) for sc in scores)
                dupes = {f"{sc:.4f}": n for sc, n in counts.items() if n > 1}
                print(f"  {case}: n={len(scores)} best={max(scores):.4f} "
                      f"distinct={len(counts)} exact-dupes={dupes or '-'}")

    # 3. public events feed: full history
    events = walk_events()
    (OUT / "events.json").write_text(json.dumps(events, indent=1))
    teams_seen = Counter(e["team"] for e in events)
    kinds = Counter(e["kind"] for e in events)
    print(f"\nevents: {len(events)} pulled; kinds={dict(kinds)}")
    print(f"active teams: {dict(teams_seen.most_common(10))}")

    # 4. scope checks, recorded honestly
    checks = {}
    if key and ours.get("practice"):
        sid = ours["practice"][0]["session_id"]
        st, _ = call("GET", f"/replay/{sid}")
        checks["replay_no_key"] = st
    st, _ = call("GET", "/v1/sessions/0000000000000000/backoffice", key)
    checks["foreign_backoffice_with_key"] = st
    st, _ = call("GET", "/replay/0000000000000000")
    checks["replay_unknown_id_no_key"] = st
    (OUT / "scope_checks.json").write_text(json.dumps(checks, indent=1))
    print(f"\nscope checks: {checks}")

    print(f"\nsaved -> {OUT}")


main()
