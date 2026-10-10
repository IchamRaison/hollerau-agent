"""Threads for the pegasus tests: a supplier's opening quote, its replies, our messages."""

import json
from pathlib import Path

from arena_kit.cost import complete_offer

CASES = {c["case_id"]: c for c in json.loads((Path(__file__).parent / "fixtures/cases/practice.json").read_text())}


def number(sid):
    return sid.split(":")[1]


def supplier(sid, n, terms, status="open", body="", alternatives=()):
    """The supplier's n-th message: a standing sheet, then its alternatives."""
    sheets = [{"term_sheet_id": f"offer:{number(sid)}-{n}", "terms": dict(terms)}]
    sheets += [{"term_sheet_id": f"offer:{number(sid)}-{n}-{chr(97 + i)}", "terms": dict(t)}
               for i, t in enumerate(alternatives)]
    return {"from": f"sales@{number(sid)}", "status": status, "body": body, "term_sheets": sheets,
            "attachments": [], "claim_results": [], "missing_fields": []}


def opening(case, sid, price, body="Please find our quote attached.", **terms):
    """An opening quote: the first option of every negotiable field unless given."""
    base = {f: (case.get("term_options", {}).get(f) or [None])[0] for f in case["negotiable"] if f != "unit_price"}
    full = complete_offer(case, {**base, **terms, "unit_price": price})
    return supplier(sid, 0, full, body=body)


def buyer(case, price=None, body="", **terms):
    """One of our messages with one complete sheet (none when `price` is None)."""
    msg = {"from": "buyer", "subject": "Re", "body": body}
    if price is not None:
        msg["term_sheets"] = [{"terms": complete_offer(case, {**terms, "unit_price": price})}]
    return msg
