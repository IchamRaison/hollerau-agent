"""The action policy: decide by comparing moves, not by counting rounds (PEGASUS_POLICY=actions).

One decision reads one `Situation`: the dossier of the case (prepared once per thread), the
revisable state of the thread (rebuilt from its messages, so a restart recovers it), the sheets
on the table evaluated one way (`evaluation`), every bidder of an RFQ. `actions.build` lists the
moves, `actions.choose` - or the optional strategist - picks one, the journal keeps all of them.
The e-mail is still written by `agent._message`: wording did not need a second implementation.

The schedule policy (`agent._decide_schedule`) stays the default and the fallback: if anything
here raises, it decides. Nothing in this module has been measured against the hosted arena yet.
"""

import logging
import time

from arena_kit.play import latest, live_threads, moves_left, standing

from . import actions as moves
from . import dossier as dossiers
from . import memory, reader, strategist
from .evaluation import clean, evaluate
from .state import ThreadState

log = logging.getLogger("pegasus")

KEEP_ALIVE = ("Thank you for your offer. We are completing our evaluation of all offers and will come back "
              "to you shortly. Could you confirm your earliest lead time?")


def _thread(agent, case, sid, events):
    """The schedule policy's thread record, plus the dossier and the notes of this thread."""
    st = agent._thread(case, sid, events)
    if "dossier" not in st:
        st["dossier"] = dossiers.prepare(case, agent.pkg, sid, events, clean(st["std"]),
                                         getattr(agent, "intel", None))
        st["notes"] = ThreadState()
        st["notes"].prior(*memory.prior_flags(sid, case))
        st["notes"].situation(st["dossier"])
        st["read"] = 0
        _restore_claims(agent, sid, events)

    def read(text):
        cached = agent._observed.pop((sid, text[:200]), None)
        deadline = getattr(agent, "_deadline", None)
        left = None if deadline is None else deadline - time.monotonic()
        signals = cached if cached is not None else reader.read(text, left)
        st.setdefault("signals_read", set()).update(signals)  # what `memory.remember` keeps
        return signals

    ThreadState.rebuild(events, read=read, start=st["notes"], seen=st["read"])
    st["read"] = len(events)
    flags = st["notes"].flags()  # the composer and `adapt.lines` read flags: now from notes that still hold
    st["stated"] = flags.pop("stated")
    st.update(flags)
    return st


def _restore_claims(agent, sid, events):
    """After a restart the arena still remembers what we cited: so must the ledger (an ID once
    per case, a rival's offer once per supplier)."""
    for m in events:
        if m.get("from") != "buyer":
            continue
        for ref in m.get("refs") or []:
            agent.fallback_claims.used.add((sid, (ref,)) if ref.startswith("offer:") else ref)


def _fresh_claim(agent, case, sid, st, price, rival=None):
    """An argument we have not cited yet is available for this supplier: a claim on the data, or
    another bidder's standing offer below its price."""
    from .agent import TEAM_CLAIMS, team_claims

    if rival and price and rival[1] < price and (sid, (rival[0],)) not in agent.fallback_claims.used:
        return True
    try:
        cands = agent.fallback_claims.candidates(sid, case["parts"][0], price, st["drivers"])
        if TEAM_CLAIMS:
            return bool(team_claims.pegasus_claims(case, agent.pkg, cands, used=agent.fallback_claims.used,
                                                   supplier=sid))
        return any(not set(c["refs"]) & agent.fallback_claims.used for c in cands)
    except Exception as e:
        log.warning("%s fresh-claim check failed (%s)", sid, type(e).__name__)
        return False


def situation(agent, case, threads, sid, busy=()):
    """What a decision on thread `sid` reads."""
    from .agent import offered

    if case["case_id"] != agent.case_id:
        agent._prepare(case)
    events = threads[sid]
    st = _thread(agent, case, sid, events)
    std, d = clean(st["std"]), st["dossier"]
    last = latest(events)
    sheet_id, terms = standing(events)
    if (terms or {}).get("unit_price"):
        st["ask"], st["last_terms"] = terms["unit_price"], terms
    offers = [(i, t, evaluate(case, t, std, d.hypotheses)) for i, t in offered(events) if i not in agent.refused]
    table, c_open, rival = [], float("inf"), None
    for s in live_threads(threads):
        other = agent.state.get(s) or agent._thread(case, s, threads[s])
        ostd = clean(other["std"])
        hyps = other["dossier"].hypotheses if "dossier" in other else dossiers.cost_hypotheses(
            case, agent.pkg, ostd, (other.get("open") or {}).get("unit_price"))
        if (other.get("open") or {}).get("unit_price"):
            first = evaluate(case, other["open"], ostd, hyps)
            if first.valid:
                c_open = min(c_open, first.cautious)
        oid, ot = standing(threads[s])
        if oid and oid not in agent.refused and (ot or {}).get("unit_price"):
            e = evaluate(case, ot, ostd, hyps)
            table.append((s, oid, e, latest(threads[s]).get("status") in ("final_offer", "agreed")))
            if s != sid and e.valid and (rival is None or ot["unit_price"] < rival[1]):
                rival = (oid, ot["unit_price"])
    # another bidder can still improve: live, messages left, not at its last word, not given up on
    others = [s for s in live_threads(threads) if s != sid and not (agent.state.get(s) or {}).get("done")
              and moves_left(case, threads[s]) > 1
              and latest(threads[s]).get("status") not in ("final_offer", "agreed")]
    price = st.get("ask") or (st.get("open") or {}).get("unit_price")
    return st, moves.Situation(
        case=case, supplier_id=sid, std=std, dossier=d, state=st["notes"], hypotheses=d.hypotheses, offers=offers,
        status=last.get("status") or "open", moves_left=moves_left(case, events), c_alt=agent.c_alt, c_open=c_open,
        table=table, others_moving=bool(others), busy=tuple(busy), rival=rival,
        fresh_claim=_fresh_claim(agent, case, sid, st, price, rival), ask=price,
        default_demand=st.get("anchor"), default_structure=st.get("anchor_structure"))


def _to_message(agent, case, threads, sid, st, sit, action):
    """The arena message of a move."""
    if action.kind == "accept":
        return {"supplier_id": action.supplier_id or sid,
                "message": {"action": {"type": "accept", "term_sheet_id": action.sheet_id}}}
    if action.kind == "walk":
        return {"supplier_id": sid, "message": {"action": {"type": "walk_away"}}}
    if action.kind == "wait":
        st["done"] = True  # this thread has gone as far as it will; the others may still improve
        return {"wait": True}
    if action.kind == "keep":
        st["done"] = True
        return {"supplier_id": sid, "message": {"subject": f"Re: {case['title']}", "body": KEEP_ALIVE}}
    if action.kind == "ask":
        body = ("Thank you for your offer. " + " ".join(action.lines)
                + "\n\nBest regards\nHollerau Pumpenwerke GmbH, Purchasing")
        return {"supplier_id": sid, "message": {"subject": f"Re: {case['title']}", "body": body}}
    if action.kind == "mirror":
        body = ("Thank you for your offer. " + " ".join(action.lines)
                + "\n\nBest regards\nHollerau Pumpenwerke GmbH, Purchasing")
        return {"supplier_id": sid, "message": {"subject": f"Re: {case['title']}", "body": body,
                                                "term_sheets": [{"terms": t} for t in action.sheets]}}
    k = len(sit.state.ours)
    st["offers"], st["seen"] = k + 1, sit.their_costs()  # what the composer reads
    msg = agent._message(case, threads, sid, st, action.demand, k, sheets=action.sheets,
                         prefer=action.refs, extra=action.lines)
    return {"supplier_id": sid, "message": msg}


def decide(agent, case, threads, sid=None, busy=(), deadline=None):
    live = live_threads(threads)
    if not live:
        return None
    sid = sid if sid in live else live[0]
    st, sit = situation(agent, case, threads, sid, busy)
    options = moves.build(sit)
    chosen, by, reason = moves.choose(options, sit), "rule", ""
    if strategist.ENABLED:
        left = None if deadline is None else deadline - time.monotonic()
        index, reason = strategist.choose(sit, options, latest(threads[sid]).get("body", ""), left)
        if index is not None:
            chosen, by = options[index], "strategist"
    out = _to_message(agent, case, threads, sid, st, sit, chosen)
    repeated = chosen.kind == "wait" and st.get("waiting")  # the runner asks again every second: one line
    st["waiting"] = chosen.kind == "wait"
    if agent.journal and not repeated:
        agent.journal.write(policy="actions", case=case["case_id"], supplier=sid, status=sit.status,
                            offer=len(sit.state.ours) + 1, moves_left=sit.moves_left,
                            considered=[a.to_dict() for a in options], chosen=chosen.kind, by=by, reason=reason,
                            state=sit.state.summary(), unknowns=sit.dossier.unknowns,
                            diagnostics=sit.dossier.diagnostics)
    log.info("%s %s: %s (%s)", case["case_id"], sid, chosen.kind, chosen.why)
    return out
