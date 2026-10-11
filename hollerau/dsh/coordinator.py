"""Play one case with the DSH pilot: the model decides for the whole case, this loop executes.

One loop per case. When supplier e-mails await an answer it gives the model one turn, sized to
the earliest of their 60-second clocks; the committed decision's e-mails leave in parallel, one
request per supplier, and replies arriving meanwhile are added to the state for the next turn.
If the model has not committed in time, a fallback keeps the threads alive (it is marked as
such in the journal: a score obtained by fallbacks says nothing about the model).
"""

import json
import logging
import os
import threading
import time
from pathlib import Path

from arena_kit.client import ArenaError
from arena_kit.play import CLOSE_BEFORE_CAP_S, ROUND_MARGIN_S, fetch_documents

from . import economics
from .state import CaseState

log = logging.getLogger("pegasus.dsh")

SEND_MARGIN_S = float(
    os.environ.get("PEGASUS_DSH_SEND_MARGIN_S", "12")
)  # kept for validation, fallback and the network
MIN_TURN_S = 8.0  # with less than this the model is not asked at all
HOLDING_LINE = "We maintain the proposal below and look forward to your answer."
OPENING_QUESTION = (
    "Thank you for your quote. Before we answer in detail, could you send us the cost breakdown behind your price?"
)


class Journal:
    """One JSON line per event of the game, next to the run's other files. Writing never raises."""

    def __init__(self, path=None):
        self.path, self.lock = (Path(path) if path else None), threading.Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, kind, **entry):
        if not self.path:
            return
        try:
            with self.lock, self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"t": round(time.time(), 2), "kind": kind, **entry}, default=str) + "\n")
        except OSError as e:
            log.warning("journal not written (%s)", e)


def closing_batch(state):
    """With no time or no message left: accept the cheapest signable sheet if it beats the
    alternative (or there is none), else walk away."""
    best, alt = state.best_standing(), economics.alternative(state.case)
    if best and (alt is None or best[0] < alt):
        return {
            "emails": [],
            "close": {"supplier_id": best[1], "message": {"action": {"type": "accept", "term_sheet_id": best[2]}}},
            "note": "fallback closing",
        }
    live = state.live()
    if not live:
        return None
    return {
        "emails": [],
        "close": {"supplier_id": live[0], "message": {"action": {"type": "walk_away"}}},
        "note": "fallback closing",
    }


def fallback_batch(state, ready, coded=None):
    """Keep the threads alive without the model: repeat our last sheets (what a timeout would do,
    without the lost patience); on a first move the coded agent's opening if one is given, else a
    question. A thread with no message left can only be closed."""
    emails = []
    for sid in ready:
        if state.moves_left(sid) <= 0:
            continue
        last = next(
            (m for m in reversed(state.threads[sid]) if m.get("from") == "buyer" and m.get("term_sheets")), None
        )
        if last:
            emails.append(
                {
                    "supplier_id": sid,
                    "message": {
                        "subject": last.get("subject") or "Our proposal",
                        "body": HOLDING_LINE,
                        "term_sheets": last["term_sheets"],
                    },
                }
            )
            continue
        move = None
        if coded is not None:
            try:
                move = coded.decide(state.case, state.threads, sid)
            except Exception:
                log.exception("%s %s: coded fallback failed", state.case["case_id"], sid)
        if move and move.get("message") and not move["message"].get("action") and move.get("supplier_id") == sid:
            emails.append({"supplier_id": sid, "message": move["message"]})
        else:
            emails.append(
                {"supplier_id": sid, "message": {"subject": "Your quote", "body": OPENING_QUESTION, "term_sheets": []}}
            )
    if emails:
        return {"emails": emails, "close": None, "note": "fallback"}
    return closing_batch(state)


def play_case(table, case_id, pilot, package=None, deadline=None, journal=None, coded=None):
    """Play one case to its end and return the arena's result. `deadline`: a Live Final wave's cap
    (time.time(), or a function returning it). `coded`: a coded agent used for a first move the
    model missed."""
    journal = journal or Journal()
    case, threads = table.open(case_id)
    if getattr(table, "done", None):
        return table.done
    for events in threads.values():
        for m in events:
            fetch_documents(table, m)
    state = CaseState(case, threads, package)
    box, wake = {}, threading.Condition()
    slowest, turn = [0.0], 0
    journal.write(
        "opened",
        case=case_id,
        session=getattr(table, "session_id", None),
        suppliers=list(threads),
        c_open=state.c_open(),
    )

    def send(sid, message, t0):
        try:
            reply = table.send(sid, message)
        except ArenaError as e:
            journal.write("arena_error", case=case_id, supplier=sid, status=e.status, detail=str(e.detail)[:400])
            if e.status == 409:
                reply = table.missed(sid, e)
            else:  # 422: nothing happened, no round used - the model sees why on its next turn
                state.refused(sid, message, e.detail)
                with wake:
                    wake.notify_all()
                return
        except Exception as e:
            log.exception("%s %s: send failed", case_id, sid)
            state.refused(sid, message, f"send failed: {type(e).__name__}")
            with wake:
                wake.notify_all()
            return
        if "result" in reply:
            box["result"] = reply["result"]
        else:
            state.replied(sid, fetch_documents(table, reply))
            slowest[0] = max(slowest[0], time.monotonic() - t0)
            journal.write(
                "reply",
                case=case_id,
                supplier=sid,
                status=reply.get("status"),
                sheets=reply.get("term_sheets"),
                claim_results=reply.get("claim_results"),
                cost=state.cost(sid, state.standing(sid)[1]) if state.standing(sid)[0] else None,
            )
        with wake:
            wake.notify_all()

    def close(batch):
        target = batch["close"]
        try:
            box["result"] = table.close(target["supplier_id"], target["message"])
            return True
        except ArenaError as e:
            journal.write(
                "arena_error",
                case=case_id,
                supplier=target["supplier_id"],
                status=e.status,
                detail=str(e.detail)[:400],
                closing=True,
            )
            if table.client.session(table.session_id).get("status") == "ended":
                box["result"] = table.result()
                return True
            state.errors[target["supplier_id"]] = f"close refused: {e.detail}"[:600]
            return False

    idle_since = None
    while "result" not in box:
        if not state.live():
            break
        cap = deadline() if callable(deadline) else deadline
        ready = state.ready()
        if cap and time.time() > cap - max(CLOSE_BEFORE_CAP_S, slowest[0] + ROUND_MARGIN_S):
            journal.write("cap_near", case=case_id)
            batch = closing_batch(state)
            if batch is None or close(batch):
                break
            continue
        if not ready:
            if not state.inflight:
                # nothing awaits us and nothing is out: threads we may not write to any more
                idle_since = idle_since or time.monotonic()
                if time.monotonic() - idle_since > 2:
                    batch = closing_batch(state)
                    if batch is None or close(batch):
                        break
            with wake:
                wake.wait(timeout=0.5)
            continue
        idle_since = None
        turn += 1
        t0 = time.monotonic()
        budget = min(state.seconds_left(s) for s in ready) - SEND_MARGIN_S
        decision, source = None, "model"
        if budget >= MIN_TURN_S:
            decision = pilot.decide(
                case_id,
                state,
                budget,
                on_trace=lambda d, n=turn: journal.write(
                    "turn_end",
                    case=case_id,
                    turn=n,
                    conversation=getattr(d, "conversation", None),
                    status=d.status,
                    tools=d.calls,
                    trace=d.trace,
                ),
            )
        if decision is not None and decision.status == "committed":
            batch = decision.batch
        else:
            source = "fallback"
            batch = fallback_batch(state, state.ready(), coded if turn == 1 else None)
        journal.write(
            "decision",
            case=case_id,
            turn=turn,
            source=source,
            ready=ready,
            budget_s=round(budget, 1),
            waited_s=getattr(decision, "waited_s", None),
            tools=list(getattr(decision, "calls", None) or []),
            batch=batch,
        )
        if batch is None:
            break
        if batch.get("close"):
            if close(batch):
                break
            continue
        if not batch["emails"]:
            # the model answered nobody: do not spin on the same state
            fb = fallback_batch(state, state.ready())
            journal.write("decision", case=case_id, turn=turn, source="fallback", note="empty decision", batch=fb)
            if fb is None:
                break
            if fb.get("close"):
                if close(fb):
                    break
                continue
            batch = fb
        for mail in batch["emails"]:
            sid = mail["supplier_id"]
            if sid not in state.ready():
                continue
            state.sent(sid, mail["message"])
            threading.Thread(target=send, args=(sid, mail["message"], t0), name=f"send-{sid}", daemon=True).start()
    result = box.get("result") or table.result()
    journal.write(
        "result",
        case=case_id,
        **{k: result.get(k) for k in ("deal", "score", "c_open", "c_deal", "c_best", "c_alt", "end_reason", "terms")},
    )
    return result
