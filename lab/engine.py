"""Campaign engine: play one declarative run on one case, every supplier thread in step, and log each reply.

A run spec is plain JSON, so a campaign manifest can be saved, shuffled, resumed and audited:
  {"run_id": "...", "block": "...", "case_id": "case:D01", "rep": 1, "factors": {...},
   "threads": {"sup:DEMO-F1": [step, ...]},      # or "*": the same steps for every supplier of the case
   "end": {"type": "walk"} | {"type": "accept", "supplier": "sup:..." | "best"}}
A step:
  {"sheets": [{"price": [mode, value], "terms": {...}, "may_exceed": false}, ...],  # 0-3; none = a question-only e-mail
   "body": "text", "refs": ["sc:..."], "wait_s": 0, "action": "accept" | "walk",
   "stop_on": ["agreed", "final_offer"]}         # statuses after which this thread's script stops (the default)
Price modes:
  ["x_opening", 0.90]     0.90 x the supplier's opening price      ["abs", 47.6]          an absolute price
  ["x_standing", 0.99]    0.99 x its standing price                ["ours_plus", 0.16]    our last price + 0.16
  ["x_current", 1.02]     1.02 x the buyer's current price         ["ours_plus_pct", 0.3] + 0.3 % of its opening price
  ["gap", 0.25]           our last price + 25 % of the gap to its standing price
Unless a sheet says "may_exceed", its price is capped one cent below the supplier's standing price:
an offer at or above it makes the supplier agree to OUR price.
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from arena_kit.client import ArenaError
from arena_kit.cost import complete_offer, must_haves_ok, total_cost
from arena_kit.docs import standard_terms
from arena_kit.play import RemoteTable, fetch_documents, latest, standing

ROOT = Path(__file__).resolve().parent.parent
ENDED = {"walked_away", "no_bid"}
DEFAULT_STOP = ("agreed", "final_offer")
BODY = "Thank you for your offer. Please find our proposal in the attached terms."
_io = threading.Lock()


class Thread:
    """One supplier thread of a session."""

    def __init__(self, case, supplier, events):
        self.case, self.supplier, self.events = case, supplier, events
        self.ours, self.stopped, self.sent = None, False, 0
        self.std = standard_terms(events)
        self.opening = dict(standing(events)[1])

    @property
    def status(self):
        return latest(self.events).get("status")

    @property
    def live(self):
        return self.status not in ENDED

    @property
    def standing_id(self):
        return standing(self.events)[0]

    @property
    def terms(self):
        return dict(standing(self.events)[1])

    @property
    def theirs(self):
        """Its standing terms as a complete term sheet (gaps from its standard terms)."""
        return complete_offer(self.case, {**self.std, **self.terms})

    def cost(self, terms=None):
        return total_cost(self.case, self.terms if terms is None else terms, self.std)

    def price(self, spec, may_exceed=False):
        mode, v = spec
        op, st = self.opening.get("unit_price"), self.terms.get("unit_price")
        ours = (self.ours or {}).get("unit_price")
        if mode == "abs":
            p = v
        elif mode == "x_opening":
            p = op * v
        elif mode == "x_standing":
            p = st * v
        elif mode == "x_current":
            p = self.case["buyer"]["current_unit_price"] * v
        elif mode == "ours_plus":
            p = ours + v
        elif mode == "ours_plus_pct":
            p = ours + op * v / 100
        elif mode == "gap":
            p = ours + (st - ours) * v
        else:
            raise ValueError(f"unknown price mode {mode!r}")
        if not may_exceed and st is not None:
            p = min(p, st - 0.01)
        return round(p, 2)

    def message(self, step):
        if step.get("action"):
            kind = {"accept": "accept", "walk": "walk_away"}[step["action"]]
            action = {"type": kind, "term_sheet_id": self.standing_id} if kind == "accept" else {"type": kind}
            return {"action": action}
        sheets = []
        for s in step.get("sheets", []):
            terms = {**self.theirs, **(s.get("terms") or {})}
            if "price" in s:
                terms["unit_price"] = self.price(s["price"], s.get("may_exceed", False))
            sheets.append({"terms": complete_offer(self.case, terms)})
        msg = {"subject": step.get("subject") or self.case["title"], "body": step.get("body") or BODY}
        if sheets:
            msg["term_sheets"] = sheets
        if step.get("refs"):
            msg["refs"] = list(step["refs"])
        return msg


def _send(table, th, msg, wait_s):
    if wait_s:
        time.sleep(wait_s)
    t0 = time.monotonic()
    try:
        reply = table.close(th.supplier, msg) if msg.get("action") else table.send(th.supplier, msg)
        if msg.get("action"):
            reply = {"result": reply}
    except ArenaError as e:
        if e.status == 422:
            return {"error": f"422 {e.detail}"}, time.monotonic() - t0
        if e.status != 409:
            raise
        reply = table.missed(th.supplier, e)
        reply["late_or_closed"] = str(e.detail)
    return reply, time.monotonic() - t0


def _row(spec, th, rnd, msg, reply, took, wait_s, before, since_open):
    sent = [s["terms"] for s in msg.get("term_sheets") or []]
    after = th.terms
    non_price = lambda t: {k: v for k, v in t.items() if k != "unit_price"}  # noqa: E731
    answered = [i for i, t in enumerate(sent) if all(after.get(k) == v for k, v in non_price(t).items())]
    p0, p1 = before.get("unit_price"), after.get("unit_price")
    return {
        "run_id": spec["run_id"],
        "block": spec.get("block"),
        "case_id": spec["case_id"],
        "supplier": th.supplier,
        "rep": spec.get("rep"),
        "factors": spec.get("factors") or {},
        "round": rnd,
        "since_open_s": round(since_open, 1),
        "seconds": round(took, 2),
        "waited_s": wait_s,
        "sent_sheets": sent,
        "sent_refs": msg.get("refs") or [],
        "sent_body": msg.get("body"),
        "status": reply.get("status"),
        "offer_id": th.standing_id,
        "terms": after,
        "terms_before": before,
        "price_move": None if p0 is None or p1 is None else round(p1 - p0, 4),
        "answered_sheet": answered[0] if len(answered) == 1 else (answered or None),
        "agreed_to_ours": reply.get("status") == "agreed" and any(after == {**after, **t} for t in sent),
        "granted": sorted(k for t in sent[:1] for k, v in non_price(t).items() if after.get(k) == v != before.get(k)),
        "claim_results": [c.get("result") for c in reply.get("claim_results") or []],
        "missing_fields": reply.get("missing_fields") or [],
        "signals": reply.get("signals"),
        "attachments": [a.get("name") for a in reply.get("attachments") or []],
        "body": reply.get("body"),
        "late_or_closed": reply.get("late_or_closed"),
        "c_if_signed": th.cost() if p1 is not None else None,
        "must_haves_ok": must_haves_ok(th.case, after, th.std),
    }


def play_run(spec, client, out):
    """Play one run; returns its record. Rows go to <out>/rows.jsonl, the record to <out>/runs/<run_id>.json."""
    table = RemoteTable(client)
    m0, started = time.monotonic(), time.time()
    case, threads = table.open(spec["case_id"])
    open_s = time.monotonic() - m0
    for events in threads.values():
        for m in events:
            fetch_documents(table, m)
    th = {s: Thread(case, s, ev) for s, ev in threads.items()}
    scripts = {s: list(spec["threads"].get(s) or spec["threads"].get("*") or []) for s in th}
    rec = {
        **{k: spec.get(k) for k in ("run_id", "block", "case_id", "rep", "factors", "end")},
        "session_id": table.session_id,
        "started_at": started,
        "open_s": round(open_s, 2),
        "opening": {
            s: {"terms": t.opening, "standard": t.std, "signals": latest(t.events).get("signals")}
            for s, t in th.items()
        },
        "opening_bodies": {s: latest(t.events).get("body") for s, t in th.items()},
        "errors": [],
    }
    rows, result = [], None
    for r in range(max((len(s) for s in scripts.values()), default=0)):
        todo = [(s, scripts[s][r]) for s in th if r < len(scripts[s]) and th[s].live and not th[s].stopped]
        if not todo:
            break
        msgs = {s: th[s].message(step) for s, step in todo}
        before = {s: th[s].terms for s, _ in todo}
        with ThreadPoolExecutor(len(todo)) as pool:
            futs = {s: pool.submit(_send, table, th[s], msgs[s], step.get("wait_s", 0)) for s, step in todo}
        for s, step in todo:
            reply, took = futs[s].result()
            if "error" in reply:
                rec["errors"].append({"round": r + 1, "supplier": s, "error": reply["error"], "sent": msgs[s]})
                th[s].stopped = True
                continue
            if "result" in reply:
                result = reply["result"]
                continue
            fetch_documents(table, reply)
            if msgs[s].get("term_sheets"):
                th[s].ours = msgs[s]["term_sheets"][0]["terms"]
            th[s].events += [{**msgs[s], "from": "buyer"}, reply]
            th[s].sent += 1
            rows.append(
                _row(spec, th[s], r + 1, msgs[s], reply, took, step.get("wait_s", 0), before[s], time.monotonic() - m0)
            )
            if reply.get("status") in step.get("stop_on", DEFAULT_STOP):
                th[s].stopped = True
        if result is not None:
            break
    live = [s for s in th if th[s].live]
    end = spec.get("end") or {"type": "walk"}
    t_close = time.monotonic()
    if result is None and live and end["type"] == "accept":
        ok = [s for s in live if th[s].standing_id and must_haves_ok(case, th[s].terms, th[s].std)]
        want = end.get("supplier", "best")
        pick = want if want in ok else (min(ok, key=lambda s: th[s].cost()) if ok and want == "best" else None)
        if pick:
            result = table.close(pick, {"action": {"type": "accept", "term_sheet_id": th[pick].standing_id}})
    if result is None and live:
        result = table.close(live[0], {"action": {"type": "walk_away"}})
    if result is None:
        result = table.result()
    rec["close_s"] = round(time.monotonic() - t_close, 2)
    rec["total_s"] = round(time.monotonic() - m0, 1)
    rec["final"] = {
        s: {
            "status": t.status,
            "terms": t.terms,
            "sent": t.sent,
            "c_if_signed": t.cost() if t.terms.get("unit_price") else None,
        }
        for s, t in th.items()
    }
    keep = (
        "deal",
        "score",
        "c_open",
        "c_deal",
        "c_best",
        "c_alt",
        "end_reason",
        "supplier_id",
        "terms",
        "cost_breakdown",
        "must_haves_ok",
    )
    rec["result"] = {k: (result or {}).get(k) for k in keep}
    try:
        state = client.session(table.session_id)
        rec["trace"] = (state.get("result") or {}).get("trace")
        rec["backoffice"] = client.backoffice(table.session_id)
    except Exception as e:  # not every simulator case has them
        rec["trace_error"] = str(e)
    rec["rows"] = rows
    with _io:
        (out / "runs").mkdir(parents=True, exist_ok=True)
        (out / "runs" / f"{spec['run_id']}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False, default=str))
        with (out / "rows.jsonl").open("a") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return rec
