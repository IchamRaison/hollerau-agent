"""Which suppliers we have played does this one resemble, and what did those do next.

`suppliers.json` (built by `lab/dsh_suppliers.py` from every finished game we hold) is one record
per supplier we have met: who signs, how its offers answered our asks, when its final offer came,
what followed a push after it, what it wrote. During a game the same measures are taken on the
live thread and compared with each record. The closest records, with their weights, and what they
imply for the next reply are evidence for the model - what suppliers like this one did, never an
instruction.

Everything is in units a game shows: our cost of a sheet as a share of the supplier's opening
quote. A thread is a list of steps, ours and its:

    {"who": "B", "cost": cheapest sheet we sent (EUR, None without a sheet), "sheets": n}
    {"who": "S", "cost": its standing sheet (EUR, None when it left), "status": ..., "text": ...}
"""

import json
import math
import re
from functools import lru_cache
from pathlib import Path

RECORDS = Path(__file__).with_name("suppliers.json")
MIN_GAP = 0.005  # below half a percent of its quote, the gap between its offer and our ask says nothing
SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
SIGNED = re.compile(r"^([A-Z][A-Za-z ]{2,40}),\s+(.{3,80})$")
PRICED = ("our terms:", "alternatively", "our current angebot", "for this item")


def q(values, p):
    v = sorted(values)
    return v[min(len(v) - 1, int(p * len(v)))] if v else None


def spread(values, digits=3):
    """[q25, median, q75] of a list, None when empty."""
    return [round(q(values, p), digits) for p in (0.25, 0.5, 0.75)] if values else None


def sentences(text):
    """The sentences of an e-mail with their figures blanked, so that the same sentence said with
    another price is the same sentence. Lines that only state an offer are left out."""
    out = []
    for raw in SPLIT.split(text or ""):
        s = NUMBER.sub("#", raw.strip())
        if len(s) >= 12 and not s.lower().startswith(PRICED):
            out.append(s)
    return out


def signature(text):
    """(role, company) from the last line of an e-mail that reads `Role, Company`."""
    for line in reversed([x.strip() for x in (text or "").splitlines() if x.strip()]):
        m = SIGNED.match(line)
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return None, None


def replies(steps):
    """One row per supplier reply to one of our e-mails. `gap` is what stood between its previous
    offer and our ask, `step` what it gave, `share` the part of the gap it closed, `our_move` how
    far our ask came up since our previous one - all as shares of its opening quote."""
    opening = next((s["cost"] for s in steps if s["who"] == "S" and s.get("cost")), None)
    rows, prev, ask_prev, pending, k = [], None, None, None, 0
    for s in steps:
        if s["who"] == "B":
            pending = s
            continue
        if prev is None or pending is None:
            prev = s if s.get("cost") is not None or prev is None else prev
            continue
        k += 1
        ask, offer, before = pending.get("cost"), s.get("cost"), prev.get("cost")
        row = {"k": k, "status": s.get("status"), "prev_status": prev.get("status"), "sheets": pending.get("sheets", 0)}
        if opening and before is not None:
            if ask is not None:
                row["gap"] = (before - ask) / opening
                row["ask_below_quote"] = (opening - ask) / opening
                if ask_prev is not None:
                    row["our_move"] = (ask - ask_prev) / opening
            if offer is not None:
                row["step"] = (before - offer) / opening
                row["offer_below_quote"] = (opening - offer) / opening
                if row.get("gap", 0) > MIN_GAP:
                    row["share"] = row["step"] / row["gap"]
        rows.append(row)
        ask_prev = ask if ask is not None else ask_prev
        prev = s if offer is not None else {**prev, "status": s.get("status")}
        pending = None
    return rows


def how_we_answered(row):
    """What our e-mail did, as the supplier may read it."""
    if "gap" not in row:
        return "a note without a term sheet"
    if row["gap"] <= 1e-6:
        return "we came up to its offer"
    return (
        "we asked below its offer and had moved"
        if row.get("our_move", 1) > 1e-6
        else "we asked below its offer without moving"
    )


@lru_cache(maxsize=1)
def records():
    try:
        return json.loads(RECORDS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _near(value, band, tolerance):
    """Log-weight of an observed value against a record's [q25, median, q75]: 0 inside the band,
    falling with the distance outside it, in units of `tolerance`."""
    if value is None or not band:
        return 0.0
    lo, _, hi = band
    d = max(lo - value, value - hi, 0.0)
    return -min(d / tolerance, 4.0)


def compare(context, rows, said, rec):
    """(log-weight, why) of one record against the live thread. Context first - who signs, the kind
    of case, how the supplier writes - then every reply it has given: its status at that reply, the
    share of the gap it closed."""
    w, why = 0.0, []
    if context.get("supplier") and context["supplier"] == rec["supplier"]:
        return 12.0, ["the same supplier in our records"]
    for key, gain, label in (
        ("who_signs", 1.4, "signed by the same role"),
        ("case_type", 0.7, "the same kind of case"),
        ("category_goal", 0.4, "the same category goal"),
    ):
        if context.get(key) and context[key] == rec.get(key):
            w += gain
            why.append(label)
    if context.get("bidders") and (context["bidders"] > 1) == (rec.get("bidders", 1) > 1):
        w += 0.4
    ours, theirs = set(context.get("negotiable") or []), set(rec.get("negotiable") or [])
    if ours and theirs:
        w += 0.8 * len(ours & theirs) / len(ours | theirs)
    known = rec.get("writes") or {}
    if said and known:
        hit = sum(known[s] for s in said if s in known)
        if hit:
            w += min(2.0, 0.5 * hit)
            why.append("writes the same sentences")
    for row in rows:
        by = (rec.get("status_by_reply") or {}).get(str(min(row["k"], 8))) or {}
        n = sum(by.values())
        if n:
            w += math.log((by.get(row["status"], 0) + 0.5) / (n + 2.0)) - math.log(1 / 4)
        band = (rec.get("first_reply") if row["k"] == 1 else rec.get("later_replies") or {}) or {}
        if "share" in row and band.get("share_of_gap"):
            fit = _near(row["share"], band["share_of_gap"], 0.15)
            w += 0.6 + fit
            if fit == 0.0:
                why.append(f"reply {row['k']} closed the same share of the gap")
    return w, why


def recognise(context, steps, said=(), hide_case=None, top=3, pool=None):
    """The records closest to this supplier, with weights that sum to 1 over every record compared.
    `hide_case` leaves out the records of one case - to play a known case as if it were new."""
    rows = replies(steps)
    scored = []
    for rec in records() if pool is None else pool:
        if hide_case and rec["case"] == hide_case:
            continue
        w, why = compare(context, rows, set(said), rec)
        scored.append((w, why, rec))
    if not scored:
        return {"replies_so_far": len(rows), "resembles": [], "rows": rows}
    peak = max(w for w, _, _ in scored)
    total = sum(math.exp(w - peak) for w, _, _ in scored)
    ranked = sorted(scored, key=lambda x: -x[0])
    return {
        "replies_so_far": len(rows),
        "rows": rows,
        "resembles": [
            {"weight": round(math.exp(w - peak) / total, 3), "why": why, "record": rec} for w, why, rec in ranked[:top]
        ],
        "all": [(math.exp(w - peak) / total, rec) for w, _, rec in ranked],
    }


def _mix(pairs):
    """Weighted median of (weight, value) pairs."""
    pairs = sorted((v, w) for w, v in pairs if v is not None and w > 0)
    total, run = sum(w for _, w in pairs), 0.0
    for v, w in pairs:
        run += w
        if run >= total / 2:
            return v
    return None


def outlook(found):
    """What the closest records say about the replies still to come: when their final offer came,
    which status followed at the next reply, what followed our e-mails after a final offer."""
    k, pool = found["replies_so_far"], found.get("all") or []
    nxt, finals, total = {}, {}, 0.0
    for w, rec in pool:
        by = (rec.get("status_by_reply") or {}).get(str(min(k + 1, 8))) or {}
        n = sum(by.values())
        for status, c in by.items():
            nxt[status] = nxt.get(status, 0.0) + w * c / n
        total += w if n else 0.0
        came = {int(a): c for a, c in (rec.get("final_offer_came_at_reply") or {}).items() if int(a) > k}
        m = sum(came.values())
        for a, c in came.items():
            finals[a] = finals.get(a, 0.0) + w * c / m
    out = {}
    if total:
        out["status_of_its_next_reply"] = {s: round(v / total, 2) for s, v in sorted(nxt.items(), key=lambda x: -x[1])}
    if finals:
        norm = sum(finals.values())
        out["its_final_offer_came_at_reply"] = {str(a): round(v / norm, 2) for a, v in sorted(finals.items())}
    return out


def forecast(found, standing, ask, opening):
    """Its next standing sheet, in our cost, if our cheapest sheet costs `ask`: the share of the
    gap it closed so far in this thread when it has shown one, mixed with what the closest records
    closed at this reply. Records that give a fixed step whatever the gap answer with that step."""
    if standing is None or ask is None or not opening:
        return None
    gap = (standing - ask) / opening
    if gap <= MIN_GAP:
        return {"note": "this sheet does not ask below its standing offer: it can only agree or hold"}
    k = found["replies_so_far"] + 1
    seen = [r["share"] for r in found["rows"] if r["k"] >= 2 and "share" in r and r.get("our_move", 1) > 1e-6]
    lows, mids, highs = [], [], []
    for w, rec in found.get("all") or []:
        part = rec.get("first_reply") if k == 1 else rec.get("later_replies")
        if not part:
            continue
        if part.get("law") == "a fixed step" and part.get("step_pct_of_its_quote"):
            band = [x / 100 for x in part["step_pct_of_its_quote"]]
        elif part.get("share_of_gap"):
            band = [x * gap for x in part["share_of_gap"]]
        else:
            continue
        lows.append((w, band[0]))
        mids.append((w, band[1]))
        highs.append((w, band[2]))
    if not mids:
        return None
    low, mid, high = _mix(lows), _mix(mids), _mix(highs)
    basis = "what the closest records gave at this reply"
    if seen and k >= 2:
        own = sorted(seen)[len(seen) // 2] * gap
        mid = (len(seen) * own + mid) / (len(seen) + 1)
        low, high = min(low, own, mid), max(high, own, mid)
        basis = f"the share of the gap it closed in this thread ({len(seen)} replies), mixed with the closest records"
    return {
        "if_it_moves_its_sheet_would_cost_us_eur": {
            "low_step": round(standing - low * opening, 2),
            "expected": round(standing - mid * opening, 2),
            "high_step": round(standing - high * opening, 2),
        },
        "expected_step_pct_of_its_quote": round(100 * mid, 2),
        "from": basis,
    }


def brief(rec):
    """A record as the model reads it: no bookkeeping, only what the supplier did."""
    keep = (
        "who_signs",
        "company",
        "case_type",
        "category_goal",
        "bidders",
        "games",
        "first_reply",
        "later_replies",
        "final_offer_came_at_reply",
        "after_its_final_offer",
        "it_left",
        "it_agreed_to_our_ask",
        "deepest_offer_below_its_quote_pct",
        "arguments",
        "inside_notes",
        "best_games",
    )
    return {
        "supplier": f"{rec['case']}/{rec['supplier']}",
        **{k: rec[k] for k in keep if rec.get(k) not in (None, {}, [])},
    }


def view(context, steps, said=(), hide_case=None):
    """What the state shows the model about one supplier."""
    found = recognise(context, steps, said, hide_case)
    if not found["resembles"]:
        return None, found
    rows = found["rows"]
    live = {
        "replies": len(rows),
        "share_of_gap_it_closed": [round(r["share"], 2) for r in rows if "share" in r],
        "its_steps_pct_of_its_quote": [round(100 * r["step"], 2) for r in rows if "step" in r],
        "it_held_when": [how_we_answered(r) for r in rows if r.get("step") is not None and r["step"] <= 1e-6],
    }
    out = {
        "note": "suppliers we have played that this one resembles, with weights; what they did is "
        "evidence, a new supplier may do otherwise",
        "suppliers_it_resembles": [
            {"weight": m["weight"], "why": m["why"], **brief(m["record"])}
            if i == 0
            else {
                "weight": m["weight"],
                "why": m["why"],
                **{k: v for k, v in brief(m["record"]).items() if k != "best_games"},
            }
            for i, m in enumerate(found["resembles"])
        ],
        "in_this_thread": live,
        **outlook(found),
    }
    return out, found
