"""What the model wants to send, checked before anything leaves.

`prepare` never rewrites a decision. It returns `errors` (the arena would refuse it, it would
score 0, or it addresses a thread that cannot be answered now: nothing is sent) and
`diagnostics` (facts the model should know before committing - it may keep its choice).
Protocol and mandate are enforced here; tactics are not.
"""

import hashlib
import json
import re

from . import economics

MAX_SUBJECT, MAX_BODY, MAX_SHEETS, MAX_REFS = 300, 8000, 3, 20
ID_RE = re.compile(r"\b(?:idx|quote|sc|qn|po|cost|fc|news|doc|ctr|offer):[A-Za-z0-9_.:@/-]*[A-Za-z0-9]")


def fingerprint(batch):
    return hashlib.sha256(json.dumps(batch, sort_keys=True, default=str).encode()).hexdigest()[:16]


def known_ids(state):
    """IDs a message may cite: the data package, the case's own facts and refs, and the offers
    made in this session."""
    ids = set(state.facts) | set(state.case.get("refs") or [])
    for events in state.threads.values():
        for m in events:
            ids.update(ts["term_sheet_id"] for ts in m.get("term_sheets") or [] if ts.get("term_sheet_id"))
    return ids


def _email(state, mail, seen, errors, diagnostics, costs):
    sid = mail.get("supplier_id")
    where = f"e-mail to {sid}"
    if sid not in state.threads:
        errors.append(f"{where}: unknown supplier; the suppliers of this case are {list(state.threads)}")
        return None
    if sid in seen:
        errors.append(f"{where}: at most one e-mail per supplier in a decision")
        return None
    seen.add(sid)
    if sid not in state.live():
        errors.append(f"{where}: this thread has ended ({state.status(sid)})")
    elif sid in state.inflight:
        errors.append(f"{where}: your previous e-mail is still unanswered - wait for the reply")
    elif state.moves_left(sid) <= 0:
        errors.append(f"{where}: no message left in this thread - you may only accept or walk away")
    subject, body = str(mail.get("subject") or ""), str(mail.get("body") or "")
    if not body.strip():
        errors.append(f"{where}: empty body")
    if len(subject) > MAX_SUBJECT:
        errors.append(f"{where}: subject over {MAX_SUBJECT} characters")
    if len(body) > MAX_BODY:
        errors.append(f"{where}: body over {MAX_BODY} characters")
    sheets = [dict(ts.get("terms", ts)) for ts in mail.get("term_sheets") or []]
    if len(sheets) > MAX_SHEETS:
        errors.append(f"{where}: {len(sheets)} term sheets, at most {MAX_SHEETS}")
    best = state.best_standing()
    movement = economics.movement(state.case, state.threads[sid], state.std.get(sid), state.estimate.get(sid))
    last_ask = (movement.get("our_asks_eur") or [None])[-1]
    evaluated = []
    for n, terms in enumerate(sheets, 1):
        e = state.evaluate(sid, terms)
        for p in e["problems"]:
            errors.append(f"{where}, sheet {n}: {p}")
        evaluated.append(e)
        costs.append(
            {
                "supplier_id": sid,
                "sheet": n,
                "terms": terms,
                "cost_eur": e["total_eur"],
                "commercial_eur": e["commercial_eur"],
                "relationship_eur": e["relationship_eur"],
                "relationship": e["relationship"],
            }
        )
        price = terms.get("unit_price")
        if isinstance(price, int | float) and not any(
            s in body for s in (f"{price:.2f}", f"{price:.2f}".replace(".", ","))
        ):
            diagnostics.append(
                f"{where}, sheet {n}: the price {price:.2f} is not written in the body; "
                "only the term sheet binds, but text and sheet should say the same"
            )
        if e["total_eur"] is not None and best and e["total_eur"] > best[0] + 0.005:
            diagnostics.append(
                f"{where}, sheet {n}: it would cost us {e['total_eur']:.2f} EUR, more than a sheet you can accept "
                f"right now ({best[2]} from {best[1]}: {best[0]:.2f} EUR)"
            )
    asks = [e["total_eur"] for e in evaluated if e["total_eur"] is not None]
    if asks and last_ask is not None:
        step = min(asks) - last_ask
        if step > 0.005:
            since = movement.get("supplier_since_our_last_move_eur")
            moved = "unknown" if since is None else f"{since:.2f} EUR"
            diagnostics.append(
                f"{where}: you concede {step:.2f} EUR against your last ask; "
                f"the supplier's move since that ask: {moved}"
            )
        elif step < -0.005:
            diagnostics.append(
                f"{where}: this asks {-step:.2f} EUR more than your last ask (you are taking back a concession)"
            )
    if state.status(sid) == "final_offer":
        diagnostics.append(
            f"{where}: its last e-mail was marked final_offer - its last word; pushing further may make it walk"
        )
    refs = [str(r) for r in mail.get("refs") or []]
    if len(refs) > MAX_REFS:
        errors.append(f"{where}: {len(refs)} refs, at most {MAX_REFS}")
    known = known_ids(state)
    for ref in sorted(set(refs) | set(ID_RE.findall(body))):
        if ref not in known:
            errors.append(
                f"{where}: {ref} is not a known data ID - an unknown ID is counted as contradicted and costs trust"
            )
        elif ref not in state.facts and not ref.startswith("offer:"):
            diagnostics.append(
                f"{where}: {ref} is named by the case but its value is not in our data - "
                "cite it without a figure, or the figure may be found wrong"
            )
    out = {
        "supplier_id": sid,
        "message": {"subject": subject, "body": body, "term_sheets": [{"terms": t} for t in sheets]},
    }
    if refs:
        out["message"]["refs"] = refs
    return out


def _close(state, close, errors, diagnostics):
    kind = close.get("type")
    alt = economics.alternative(state.case)
    if kind == "walk_away":
        best = state.best_standing()
        if best and (alt is None or best[0] < alt):
            diagnostics.append(
                f"walking away gives up a signable sheet at {best[0]:.2f} EUR ({best[2]}); "
                + ("without a deal this case scores 0" if alt is None else f"the alternative costs {alt:.2f} EUR")
            )
        live = state.live()
        if not live:
            errors.append("no live thread to close")
            return None
        return {"supplier_id": live[0], "message": {"action": {"type": "walk_away"}}}
    if kind != "accept":
        errors.append("close.type must be accept or walk_away")
        return None
    sid, sheet_id = close.get("supplier_id"), close.get("term_sheet_id")
    if sid not in state.threads or sid not in state.live():
        errors.append(f"accept: {sid} is not a live supplier of this case")
        return None
    standing_id, terms = state.standing(sid)
    if sheet_id != standing_id:
        errors.append(
            f"accept: only the supplier's standing sheet can be accepted, which is {standing_id} for {sid}; "
            "a package it only describes must first come back as its standing offer"
        )
        return None
    if sid in state.inflight:
        errors.append(f"accept: your e-mail to {sid} is still unanswered and may change its offer - wait for the reply")
    e = state.evaluate(sid, terms)
    if e["must_haves_ok"] is False:
        errors.append("accept: this sheet breaks a must-have - the deal would score 0")
    best = state.best_standing()
    if best and e["total_eur"] is not None and best[0] < e["total_eur"] - 0.005:
        diagnostics.append(
            f"accept: {best[2]} from {best[1]} is signable and cheaper ({best[0]:.2f} against {e['total_eur']:.2f} EUR)"
        )
    if alt is not None and e["total_eur"] is not None and e["total_eur"] > alt:
        diagnostics.append(
            f"accept: this deal costs {e['total_eur']:.2f} EUR, "
            f"more than the alternative without a deal ({alt:.2f} EUR)"
        )
    waiting = sorted(state.inflight - {sid})
    if waiting:
        diagnostics.append(f"accept: replies from {waiting} are still on their way; accepting ends the case for all")
    return {
        "supplier_id": sid,
        "message": {"action": {"type": "accept", "term_sheet_id": sheet_id}},
        "cost_eur": e["total_eur"],
    }


def prepare(state, decision):
    """{"ok", "errors", "diagnostics", "costs", "batch"}; `batch` is what would be sent, None on errors."""
    errors, diagnostics, costs = [], [], []
    if not isinstance(decision, dict):
        return {
            "ok": False,
            "errors": ["decision must be an object with `emails` or `close`"],
            "diagnostics": [],
            "costs": [],
            "batch": None,
        }
    emails, close = decision.get("emails") or [], decision.get("close")
    if emails and close:
        errors.append("a decision is either e-mails or a close (accept / walk_away), never both")
    if not emails and not close:
        errors.append("empty decision: give `emails` or `close`")
    batch = {"emails": [], "close": None, "note": str(decision.get("note") or "")[:600]}
    with state.lock:
        seen = set()
        for mail in emails if not close else []:
            if isinstance(mail, dict) and (m := _email(state, mail, seen, errors, diagnostics, costs)):
                batch["emails"].append(m)
        if close and not emails:
            batch["close"] = _close(state, close if isinstance(close, dict) else {}, errors, diagnostics)
        unanswered = [s for s in state.ready() if s not in seen] if emails else []
        if unanswered:
            diagnostics.append(
                f"no e-mail for {unanswered}: their 60-second clocks keep running; "
                "a thread left unanswered times out and repeats your last offer"
            )
    ok = not errors
    return {"ok": ok, "errors": errors, "diagnostics": diagnostics, "costs": costs, "batch": batch if ok else None}
