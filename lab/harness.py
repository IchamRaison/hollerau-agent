"""Lab harness: play one scripted negotiation and record everything the supplier does.

A script is a list of steps. Each step is a function `step(ctx) -> message or None`; None stops.
Every run ends with a walk-away unless the script closed the case, so no session stays open.
Records go to data/lab/<label>.json (ignored by Git).
"""

import json
import time
from pathlib import Path

from arena_kit import ArenaClient
from arena_kit.cost import complete_offer
from arena_kit.docs import standard_terms
from arena_kit.play import RemoteTable, fetch_documents, latest, live_threads, standing

OUT = Path(__file__).resolve().parent.parent / "data" / "lab"


class Ctx:
    def __init__(self, case, threads, supplier):
        self.case, self.threads, self.supplier = case, threads, supplier
        self.round, self.ours = 0, None  # our last term sheet

    @property
    def events(self):
        return self.threads[self.supplier]

    @property
    def theirs(self):
        """The supplier's standing terms, completed with its standard terms."""
        return complete_offer(self.case, {**standard_terms(self.events), **standing(self.events)[1]})

    @property
    def opening_price(self):
        first = next(m for m in self.events if m.get("from") != "buyer")
        return first["term_sheets"][0]["terms"]["unit_price"]

    def sheet(self, price, **terms):
        return complete_offer(self.case, {**self.theirs, **terms, "unit_price": round(price, 2)})


def run(case_id, script, label, supplier=None, client=None):
    """Play `script` on `case_id`; returns the record (also saved)."""
    table = RemoteTable(client or ArenaClient())
    case, threads = table.open(case_id)
    for events in threads.values():
        for m in events:
            fetch_documents(table, m)
    ctx = Ctx(case, threads, supplier or case["suppliers"][0])
    rec = {"label": label, "case_id": case_id, "session_id": table.session_id, "supplier": ctx.supplier, "rounds": []}
    rec["opening"] = {s: {"terms": standing(ev)[1], "standard": standard_terms(ev)} for s, ev in threads.items()}
    result = None
    for step in script:
        if ctx.supplier not in live_threads(threads):
            break
        if ctx.round and latest(ctx.events).get("status") in ("agreed", "final_offer"):
            break  # do not push past an agreement or a final offer in a scripted run
        msg = step(ctx)
        if msg is None:
            break
        ctx.round += 1
        t0 = time.monotonic()
        if msg.get("action"):
            result = table.close(ctx.supplier, msg)
            break
        reply = fetch_documents(table, table.send(ctx.supplier, msg))
        took = time.monotonic() - t0
        if "result" in reply:
            result = reply["result"]
            break
        if msg.get("term_sheets"):
            ctx.ours = msg["term_sheets"][0]["terms"]
        threads[ctx.supplier] += [{**msg, "from": "buyer"}, reply]
        rec["rounds"].append(
            {
                "round": ctx.round,
                "sent": {k: msg.get(k) for k in ("subject", "body", "term_sheets")},
                "status": reply.get("status"),
                "terms": standing(ctx.events)[1],
                "offer_id": standing(ctx.events)[0],
                "claim_results": reply.get("claim_results"),
                "missing_fields": reply.get("missing_fields"),
                "signals": reply.get("signals"),
                "attachments": [
                    {"name": a.get("name"), "text": a.get("text", "")[:4000]} for a in reply.get("attachments") or []
                ],
                "body": reply.get("body"),
                "seconds": round(took, 2),
            }
        )
    if result is None and live_threads(threads):
        result = table.close(live_threads(threads)[0], {"action": {"type": "walk_away"}})
    rec["final_status"] = latest(ctx.events).get("status")
    rec["result"] = {
        k: (result or {}).get(k) for k in ("deal", "score", "c_open", "c_deal", "c_best", "c_alt", "end_reason")
    }
    try:  # the supplier's reasons and back office, readable once the session has ended
        state = table.client.session(table.session_id)
        rec["trace"] = (state.get("result") or {}).get("trace")
        rec["backoffice"] = table.client.backoffice(table.session_id)
    except Exception as e:  # the simulator has no back office for every case
        rec["trace_error"] = str(e)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{label}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False, default=str))
    return rec


def summary(rec):
    prices = [r["terms"].get("unit_price") for r in rec["rounds"]]
    secs = [r["seconds"] for r in rec["rounds"]]
    return f"{rec['label']:28} {rec['case_id']} rounds={len(prices)} prices={prices} status={rec['final_status']} max_s={max(secs, default=0)}"
