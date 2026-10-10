"""An ended session, as the threads the agent saw while it played it.

The arena returns a finished session as a trace of moves (`client.session(id)`, the files under
`analysis/pegasus_data/sessions/`); the agent reads threads of e-mails. `threads_of` turns the
first into the second, so a decision can be inspected or a state rebuilt on real transcripts.

A replay can check what we would decide in a situation that happened. It cannot tell how the
supplier would have answered an offer that was never sent.
"""

import json
from pathlib import Path


def supplier_message(move):
    """A supplier move of the trace as the e-mail the agent received."""
    sheets = []
    if move.get("offer_id") and (move.get("terms") or {}).get("unit_price") is not None:
        sheets.append({"term_sheet_id": move["offer_id"], "terms": dict(move["terms"])})
    for alt in move.get("alternatives") or []:
        if alt.get("offer_id") and alt.get("terms"):
            sheets.append({"term_sheet_id": alt["offer_id"], "terms": dict(alt["terms"])})
    return {"from": "supplier", "status": move.get("status") or "open", "body": move.get("text") or "",
            "term_sheets": sheets, "attachments": [], "missing_fields": list(move.get("missing_fields") or []),
            "claim_results": list(move.get("claim_results") or [])}


def buyer_message(move):
    """One of our moves of the trace as the message we sent."""
    if move.get("type") in ("accept", "walk_away"):
        action = {"type": move["type"]}
        if move.get("offer_id"):
            action["term_sheet_id"] = move["offer_id"]
        return {"from": "buyer", "action": action}
    out = {"from": "buyer", "subject": move.get("subject") or "", "body": move.get("body") or "",
           "term_sheets": [{"terms": dict(ts.get("terms", ts))} for ts in move.get("term_sheets") or []]}
    if move.get("refs"):
        out["refs"] = list(move["refs"])
    return out


def threads_of(session, upto=None):
    """{supplier_id: [message, ...]} from a session's trace. `upto`: keep only the first `upto`
    trace entries (the situation at that point of the game)."""
    trace = ((session.get("result") or {}).get("trace")) or []
    suppliers = [e["actor"] for e in trace if e.get("actor") != "buyer"]
    threads = {s: [] for s in dict.fromkeys(suppliers)}
    only = next(iter(threads), None)
    for entry in trace[:upto]:
        move = entry.get("move") or {}
        if entry.get("actor") == "buyer":
            sid = move.get("supplier_id") or only
            if sid in threads:
                threads[sid].append(buyer_message(move))
        elif entry["actor"] in threads:
            threads[entry["actor"]].append(supplier_message(move))
    return {s: ev for s, ev in threads.items() if ev}


def load(path):
    """A session file: the arena's session object, or our archive's {"summary", "session", ...}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("session") or data


def openings(directory, case_id):
    """The opening threads of a case from the first archived session of it (the opening quote is
    an input of the game, not a result): {supplier_id: [opening message]}, {} when none is archived."""
    name = case_id.split(":")[-1]
    for path in sorted(Path(directory).glob(f"{name}-*.json")):
        try:
            session = load(path)
        except (OSError, ValueError):
            continue
        threads = threads_of(session)
        first = {s: ev[:1] for s, ev in threads.items() if ev and ev[0].get("from") != "buyer"}
        if first:
            return first
    return {}
