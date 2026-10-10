"""Campaign engine: play one declarative run on one case, every supplier thread in step, and log each reply.

A run spec is plain JSON, so a campaign manifest can be saved, shuffled, resumed and audited:
  {"run_id": "...", "block": "...", "case_id": "case:D01", "rep": 1, "factors": {...},
   "threads": {"sup:DEMO-F1": [step, ...]},      # or "*": the same steps for every supplier of the case
   "end": {"type": "walk"} | {"type": "accept", "supplier": "sup:..." | "best"}}
A step:
  {"sheets": [{"price": [mode, value], "terms": {...}, "may_exceed": false}, ...],  # 0-3; none = a question-only e-mail
   "body": "text", "refs": ["sc:..."], "wait_s": 0, "action": "accept" | "walk",
   "stop_on": ["agreed", "final_offer"],         # statuses after which this thread's script stops (the default)
   "fresh": true,                                # add the run's nonce so the server cannot replay a cached reply
   "when": ["final_offer"],                      # send only if the thread is in one of these statuses, else skip the step
   "repeat": {"until": ["final_offer"], "max": 8},   # send again each round until a status shows up
   "rival_line": "... {rival_price} ... {rival_id}"} # appended to the body when another thread has a valid standing offer
Run options: "nonce": "none" | "subject" | "body" | "message_id" (how a fresh step differs from a cached one),
"cap_s": 480 (hard stop), "stop_offers_s": 330 (no new offer after that; the run closes).
Body placeholders: {their_price} {our_price} {opening_price} {rival_price} {rival_id}.
A sheet whose explicit terms are changed by completion or snapping raises TreatmentError: the run is
recorded as failed instead of silently testing another treatment.
Price modes:
  ["x_opening", 0.90]     0.90 x the supplier's opening price      ["abs", 47.6]          an absolute price
  ["x_standing", 0.99]    0.99 x its standing price                ["ours_plus", 0.16]    our last price + 0.16
  ["x_current", 1.02]     1.02 x the buyer's current price         ["ours_plus_pct", 0.3] + 0.3 % of its opening price
  ["gap", 0.25]           our last price + 25 % of the gap to its standing price
Unless a sheet says "may_exceed", its price is capped one cent below the supplier's standing price:
an offer at or above it makes the supplier agree to OUR price.
"""

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from arena_kit.client import ArenaError
from arena_kit.cost import complete_offer, must_haves_ok, total_cost
from arena_kit.docs import standard_terms
from arena_kit.play import RemoteTable, fetch_documents, latest, standing

ROOT = Path(__file__).resolve().parent.parent
ENDED = {"walked_away", "no_bid"}
DEFAULT_STOP = ("agreed", "final_offer")
BODY = "Thank you for your offer. Please find our proposal in the attached terms."
CACHED_BELOW_S = 2.0  # a reply faster than this was replayed from the server's cache, not generated
_io = threading.Lock()


class TreatmentError(Exception):
    """The term sheet that would be sent is not the one the plan asked for."""


class _Blank(dict):
    def __missing__(self, key):
        return ""


def token(run_id, supplier, k):
    """A short reference that is stable for a run, thread and step (a resumed run replays the same text)."""
    return hashlib.sha1(f"{run_id}|{supplier}|{k}".encode()).hexdigest()[:6].upper()


def md5(text):
    return hashlib.md5((text or "").encode()).hexdigest()[:8]


def now():
    return datetime.now(UTC).isoformat(timespec="milliseconds")


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

    def message(self, step, run=None, k=0, rival=None):
        if step.get("action"):
            kind = {"accept": "accept", "walk": "walk_away"}[step["action"]]
            action = {"type": kind, "term_sheet_id": self.standing_id} if kind == "accept" else {"type": kind}
            return {"action": action}
        sheets = []
        for s in step.get("sheets", []):
            asked = dict(s.get("terms") or {})
            terms = {**self.theirs, **asked}
            if "price" in s:
                terms["unit_price"] = self.price(s["price"], s.get("may_exceed", False))
            final = complete_offer(self.case, terms)
            changed = {f: (v, final.get(f)) for f, v in asked.items() if final.get(f) != v}
            if changed:
                raise TreatmentError(f"{self.supplier}: asked terms altered by completion: {changed}")
            sheets.append({"terms": final})
        fill = _Blank(
            their_price=self.terms.get("unit_price"),
            opening_price=self.opening.get("unit_price"),
            our_price=sheets[0]["terms"].get("unit_price") if sheets else (self.ours or {}).get("unit_price"),
            rival_price=(rival or {}).get("price"),
            rival_id=(rival or {}).get("offer_id"),
        )
        body = step.get("body") or BODY
        if rival and step.get("rival_line"):
            body = f"{body}\n\n{step['rival_line']}"
        msg = {"subject": step.get("subject") or self.case["title"], "body": body.format_map(fill)}
        if sheets:
            msg["term_sheets"] = sheets
        refs = list(step.get("refs") or [])
        if rival and step.get("rival_line"):
            refs.append(rival["offer_id"])
        if refs:
            msg["refs"] = refs
        mode = (run or {}).get("nonce") or "none"
        if step.get("fresh") and mode != "none":
            tok = token(run["run_id"], self.supplier, k)
            if mode == "subject":
                msg["subject"] = f"{msg['subject']} [ref {tok}]"
            elif mode == "body":
                msg["body"] = f"{msg['body']}\n\nOur reference: HP-{tok}"
            elif mode == "message_id":
                msg["message_id"] = f"msg:buyer-{tok}"
            else:
                raise ValueError(f"unknown nonce mode {mode!r}")
            msg["_nonce"] = tok
        return msg


def _send(table, th, msg, wait_s):
    if wait_s:
        time.sleep(wait_s)
    wire = {k: v for k, v in msg.items() if not k.startswith("_")}
    sent_at, t0 = now(), time.monotonic()
    try:
        reply = table.close(th.supplier, wire) if wire.get("action") else table.send(th.supplier, wire)
        if wire.get("action"):
            reply = {"result": reply}
    except ArenaError as e:
        if e.status == 422:
            return {"error": f"422 {e.detail}"}, time.monotonic() - t0, sent_at
        if e.status != 409:
            raise
        reply = table.missed(th.supplier, e)
        reply["late_or_closed"] = str(e.detail)
    return reply, time.monotonic() - t0, sent_at


def _row(spec, th, rnd, k, msg, reply, took, sent_at, wait_s, before, since_open):
    sent = [s["terms"] for s in msg.get("term_sheets") or []]
    after = th.terms
    non_price = lambda t: {f: v for f, v in t.items() if f != "unit_price"}  # noqa: E731
    answered = [i for i, t in enumerate(sent) if all(after.get(f) == v for f, v in non_price(t).items())]
    p0, p1 = before.get("unit_price"), after.get("unit_price")
    return {
        "run_id": spec["run_id"],
        "block": spec.get("block"),
        "case_id": spec["case_id"],
        "supplier": th.supplier,
        "rep": spec.get("rep"),
        "factors": spec.get("factors") or {},
        "round": rnd,
        "thread_round": th.sent,
        "step": k,
        "sent_at": sent_at,
        "received_at": now(),
        "since_open_s": round(since_open, 1),
        "seconds": round(took, 2),
        "cached": took < CACHED_BELOW_S and not wait_s,
        "waited_s": wait_s,
        "nonce": msg.get("_nonce"),
        "sent_subject": msg.get("subject"),
        "sent_sheets": sent,
        "sent_refs": msg.get("refs") or [],
        "sent_body": msg.get("body"),
        "sent_md5": md5(json.dumps([msg.get("subject"), msg.get("body"), sent, msg.get("refs")], sort_keys=True)),
        "status": reply.get("status"),
        "offer_id": th.standing_id,
        "terms": after,
        "terms_before": before,
        "returned_sheets": reply.get("term_sheets") or [],
        "price_move": None if p0 is None or p1 is None else round(p1 - p0, 4),
        "answered_sheet": answered[0] if len(answered) == 1 else (answered or None),
        "agreed_to_ours": reply.get("status") == "agreed" and any(after == {**after, **t} for t in sent),
        "granted": sorted(f for t in sent[:1] for f, v in non_price(t).items() if after.get(f) == v != before.get(f)),
        "claim_results": [c.get("result") for c in reply.get("claim_results") or []],
        "missing_fields": reply.get("missing_fields") or [],
        "signals": reply.get("signals"),
        "attachments": [a.get("name") for a in reply.get("attachments") or []],
        "body": reply.get("body"),
        "body_md5": md5(reply.get("body")),
        "late_or_closed": reply.get("late_or_closed"),
        "c_if_signed": th.cost() if p1 is not None else None,
        "must_haves_ok": must_haves_ok(th.case, after, th.std),
    }


def _rival(th, me):
    """The cheapest valid standing offer among the other live threads, as {offer_id, price, supplier}."""
    best = None
    for s, t in th.items():
        if s == me or not t.live or not t.standing_id or t.terms.get("unit_price") is None:
            continue
        if not must_haves_ok(t.case, t.terms, t.std):
            continue
        c = t.cost()
        if best is None or c < best[0]:
            best = (c, {"offer_id": t.standing_id, "price": t.terms["unit_price"], "supplier": s})
    return best[1] if best else None


def _calls(backoffice):
    """The supplier's discrete decision per round, from the back office: counter, hold, final_offer, walk_away, agree."""
    out = {}
    for b in backoffice or []:
        text = b.get("text") or ""
        call = text[9:].strip(". ") if text.startswith("My call:") else ("agree" if "we agree" in text else None)
        if call:
            out.setdefault(b.get("supplier_id"), {})[b.get("round")] = call
    return out


def play_run(spec, client, out):
    """Play one run; returns its record. Rows go to <out>/rows.jsonl, the record to <out>/runs/<run_id>.json."""
    table = RemoteTable(client)
    m0, started = time.monotonic(), now()
    case, threads = table.open(spec["case_id"])
    open_s = time.monotonic() - m0
    for events in threads.values():
        for m in events:
            fetch_documents(table, m)
    th = {s: Thread(case, s, ev) for s, ev in threads.items()}
    scripts = {s: list(spec["threads"].get(s) or spec["threads"].get("*") or []) for s in th}
    ptr, reps = dict.fromkeys(th, 0), dict.fromkeys(th, 0)
    cap_s, stop_offers_s = spec.get("cap_s"), spec.get("stop_offers_s")
    rec = {
        **{f: spec.get(f) for f in ("run_id", "block", "case_id", "rep", "factors", "end", "nonce", "cap_s")},
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
    rows, result, rnd = [], None, 0

    def next_step(s):
        """The next step this thread should send now, skipping steps whose `when` does not match."""
        while th[s].live and not th[s].stopped and ptr[s] < len(scripts[s]):
            step = scripts[s][ptr[s]]
            if step.get("when") and th[s].status not in step["when"]:
                ptr[s] += 1
                reps[s] = 0
                continue
            return step
        return None

    while result is None:
        elapsed = time.monotonic() - m0
        if stop_offers_s and elapsed > stop_offers_s:
            rec["errors"].append(
                {"round": rnd, "note": f"no new offer after {stop_offers_s}s (elapsed {elapsed:.0f}s)"}
            )
            break
        todo = [(s, step) for s in th if (step := next_step(s)) is not None]
        if not todo:
            break
        rnd += 1
        try:
            msgs = {s: th[s].message(step, spec, ptr[s] * 100 + reps[s], _rival(th, s)) for s, step in todo}
        except TreatmentError as e:
            rec["errors"].append({"round": rnd, "error": f"treatment: {e}"})
            break
        before = {s: th[s].terms for s, _ in todo}
        with ThreadPoolExecutor(len(todo)) as pool:
            futs = {s: pool.submit(_send, table, th[s], msgs[s], step.get("wait_s", 0)) for s, step in todo}
        for s, step in todo:
            reply, took, sent_at = futs[s].result()
            if "error" in reply:
                rec["errors"].append({"round": rnd, "supplier": s, "error": reply["error"], "sent": msgs[s]})
                th[s].stopped = True
                continue
            if "result" in reply:
                result = reply["result"]
                if msgs[s].get("action") or not reply.get("status"):
                    continue  # our own closing action, or no supplier e-mail came with the end
                # the supplier's last e-mail ended the case (e.g. it walked away after our push): keep the row
            fetch_documents(table, reply)
            if msgs[s].get("term_sheets"):
                th[s].ours = msgs[s]["term_sheets"][0]["terms"]
            wire = {f: v for f, v in msgs[s].items() if not f.startswith("_")}
            th[s].events += [{**wire, "from": "buyer"}, reply]
            th[s].sent += 1
            rows.append(
                _row(
                    spec,
                    th[s],
                    rnd,
                    ptr[s],
                    msgs[s],
                    reply,
                    took,
                    sent_at,
                    step.get("wait_s", 0),
                    before[s],
                    time.monotonic() - m0,
                )
            )
            status = reply.get("status")
            rep = step.get("repeat")
            if rep and status not in rep.get("until", []) and reps[s] + 1 < rep.get("max", 8):
                reps[s] += 1  # same step again next round
            else:
                ptr[s] += 1
                reps[s] = 0
            if status in step.get("stop_on", DEFAULT_STOP):
                th[s].stopped = True
        if cap_s and time.monotonic() - m0 > cap_s:
            rec["errors"].append({"round": rnd, "note": f"cap of {cap_s}s reached"})
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
        "offer_id",
        "terms",
        "cost_breakdown",
        "must_haves_ok",
    )
    rec["result"] = {f: (result or {}).get(f) for f in keep}
    try:
        state = client.session(table.session_id)
        rec["trace"] = (state.get("result") or {}).get("trace")
        rec["backoffice"] = client.backoffice(table.session_id)
        rec["calls"] = _calls(rec["backoffice"])
        for row in rows:
            row["call"] = (rec["calls"].get(row["supplier"]) or {}).get(row["thread_round"])
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
