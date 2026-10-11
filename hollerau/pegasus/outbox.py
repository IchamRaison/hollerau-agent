"""One check at the edge of the send, for every move of every branch.

`guard.check` already filters the e-mails that `agent._send` builds. Other branches return their
move directly: an acceptance, a walk-away, the keep-alive question, the alternative sent back.
`validate` is the single gate all of them pass before the runner sends anything:
  e-mail      the guard (IDs known, figures true, nothing leaked, sheets complete and valid) - and
              a thread with no message left gets a closing move, not an e-mail the arena refuses
  accept      only the supplier's standing sheet of a live thread, never one the arena refused,
              never one that breaks a must-have, never one worse than the alternative
  walk away   never while a standing sheet clearly beats both the alternative and the opening
A move that fails is replaced by the agent's closing move (accept the best acceptable sheet, else
walk away): the case is always left in a state the arena accepts. Returns (move, problems).
"""

import logging

from arena_kit.play import live_threads, moves_left, standing

from . import guard
from .evaluation import clean, evaluate

log = logging.getLogger("pegasus")


def _hypotheses(agent, case, sid, st):
    from . import dossier as dossiers

    if "dossier" in st:
        return st["dossier"].hypotheses
    return dossiers.cost_hypotheses(case, agent.pkg, clean(st.get("std")), (st.get("open") or {}).get("unit_price"))


def _table(agent, case, threads):
    """Every live standing sheet with its evaluation, and the cautious cost of the best opening."""
    rows, c_open = [], float("inf")
    for s in live_threads(threads):
        st = agent.state.get(s) or agent._thread(case, s, threads[s])
        std, hyps = clean(st.get("std")), _hypotheses(agent, case, s, st)
        if (st.get("open") or {}).get("unit_price"):
            first = evaluate(case, st["open"], std, hyps)
            if first.valid:
                c_open = min(c_open, first.cautious)
        sheet_id, terms = standing(threads[s])
        if sheet_id and sheet_id not in agent.refused and (terms or {}).get("unit_price"):
            rows.append((s, sheet_id, evaluate(case, terms, std, hyps)))
    return rows, c_open


def _closing(agent, case, threads, problems):
    for p in problems:
        log.warning("%s outbox: %s - closing move instead", case.get("case_id"), p)
    return agent.closing(case, threads)


def validate(agent, case, threads, out):
    """The move as it may be sent, and what was wrong with the one proposed ([] if nothing)."""
    if not out or out.get("wait"):
        return out, []
    sid, msg = out.get("supplier_id"), out.get("message")
    if sid not in threads or not isinstance(msg, dict):
        problem = f"move for an unknown thread or without a message: {sid}"
        return _closing(agent, case, threads, [problem]), [problem]
    live = live_threads(threads)
    action = msg.get("action")
    if action:
        kind = action.get("type")
        rows, c_open = _table(agent, case, threads)
        if kind == "accept":
            row = next((r for r in rows if r[0] == sid and r[1] == action.get("term_sheet_id")), None)
            problems = []
            if sid not in live:
                problems.append(f"accept on an ended thread {sid}")
            elif row is None:
                problems.append(f"accept of {action.get('term_sheet_id')}, which is not {sid}'s standing sheet")
            elif not row[2].valid:
                problems.append(f"accept of {row[1]}, which breaks a must-have or cannot be costed")
            elif row[2].commercial >= agent.c_alt:
                problems.append(f"accept of {row[1]} at C={row[2].commercial:,.0f}, no better than the alternative")
            if problems:
                return _closing(agent, case, threads, problems), problems
            return out, []
        if kind == "walk_away":
            bar = min(agent.c_alt, c_open)
            better = [r for r in rows if r[2].valid and r[2].cautious < bar - 0.002 * abs(bar)]
            if better and bar < float("inf"):
                best = min(better, key=lambda r: r[2].cautious)
                problem = (f"walk away while {best[1]} costs {best[2].cautious:,.0f}, clearly under the "
                           f"alternative and the opening ({bar:,.0f})")
                return _closing(agent, case, threads, [problem]), [problem]
            return out, []
        return _closing(agent, case, threads, [f"unknown action {kind!r}"]), [f"unknown action {kind!r}"]
    if sid not in live or moves_left(case, threads[sid]) <= 0:
        problem = f"e-mail to {sid}, which has ended or has no message left"
        return _closing(agent, case, threads, [problem]), [problem]
    st = agent.state.get(sid) or {}
    alt = (case["buyer"].get("alternative") or {}).get("terms") or {}
    offers = {ts["term_sheet_id"] for ev in threads.values() for m in ev
              for ts in (m.get("term_sheets") or []) if ts.get("term_sheet_id")}
    ask = (standing(threads[sid])[1] or {}).get("unit_price") or (st.get("open") or {}).get("unit_price")
    checked, problems = guard.check(case, msg, agent.pkg.facts if agent.pkg else {}, offers,
                                    ask=ask, alt_price=alt.get("unit_price"))
    for p in problems:
        log.warning("%s %s outbox: %s", case.get("case_id"), sid, p)
    if not (checked.get("body") or "").strip() and not checked.get("term_sheets"):
        checked = {**checked, "body": "Thank you for your offer. Could you confirm your best price on the terms above?"}
    return {**out, "message": checked}, problems


def describe(out):
    """A move in a few words, for the journal."""
    if not out:
        return None
    if out.get("wait"):
        return {"wait": True}
    msg = out.get("message") or {}
    if msg.get("action"):
        return {"supplier": out.get("supplier_id"), **msg["action"]}
    return {"supplier": out.get("supplier_id"), "refs": msg.get("refs") or [],
            "sheets": [ts.get("terms") for ts in msg.get("term_sheets") or []]}
