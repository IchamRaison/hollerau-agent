"""What the model can cite, and what our records say about a supplier.

A supplier asks "which figures is that based on?" - the answer is in the data the case points to.
`citable` lists, for one supplier, every data ID that is safe to cite: the IDs the case itself
names (also when their value is not in our package: the arena then takes the data's own value),
the other bidders' offers of this session, and for suppliers our package knows the arguments
the team's evidence code has already computed and checked. Nothing here decides what to argue:
it is the model's library, with what the arena checks for each kind of ID.
"""

import json
import logging
import re
from pathlib import Path

log = logging.getLogger("pegasus.dsh")

ID_RE = re.compile(r"\b(?:idx|quote|sc|qn|po|cost|fc|news|doc|ctr|offer):[A-Za-z0-9_.:@/#-]*[A-Za-z0-9]")
# "<SERIES> rose 3.1 % in twelve months and is 28 % of our cost" - how suppliers state a cost driver
DRIVER_RE = re.compile(
    r"\b([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)\s+(rose|fell|changed)\s+(-?\d+(?:[.,]\d+)?)\s*%\s+in twelve months"
    r"\s+and is\s+(\d+(?:[.,]\d+)?)\s*% of our cost"
)
CHECKED_AS = {
    "idx": "two IDs of one series, at most 12 months apart: the change in %",
    "quote": "its unit price for the same part, in EUR",
    "offer": "another bidder's offer in this session: its unit price in EUR - citing it shows it to this supplier",
    "sc": "the supplier's mean on-time delivery in %, or its mean ppm when you speak of quality",
    "qn": "the supplier's mean ppm",
    "po": "2 to 8 orders of the same part: the order prices",
    "cost": "our should-cost estimate of the part, in EUR per unit",
    "fc": "the recorded change of our demand forecast for the part, in %",
    "news": "that the news is about this supplier",
    "doc": "with the contract (ctr:) in the same sentence: the notice the letter gives, in days",
    "ctr": "with the letter (doc:) in the same sentence: the notice the contract requires, in days",
}
NO_FIGURE = "value not in our data: cite the ID without a figure - the arena then takes the data's own value"


OBSERVATIONS = Path(__file__).with_name("observations.json")


def similar_cases(case):
    """What other cases of the same category goal showed in our finished games: how far below the
    opening quote the best acceptable deal sat. The case being played is never in the list. A
    prior for how much room this kind of case holds, not a figure for this supplier."""
    try:
        rows = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    goal = case["buyer"].get("category_goal")
    same = [r for r in rows if r["case_id"] != case["case_id"] and r["category_goal"] == goal]
    if not same:
        return {"cases_of_this_category_goal": [], "note": "no other case of this category goal in our records"}
    room = sorted(r["best_acceptable_deal_below_opening_pct"] for r in same)
    return {
        "category_goal": goal,
        "cases_of_this_category_goal": [
            {k: r[k] for k in ("type", "suppliers", "best_acceptable_deal_below_opening_pct")} for r in same
        ],
        "best_acceptable_deal_below_opening_pct_range": [room[0], room[-1]],
        "note": (
            f"{len(same)} other case(s), exact figures from finished games; few cases: a prior, not a law. "
            "Other category goals in our records: "
            + "; ".join(f"{g}: {lo}-{hi} %" for g, lo, hi in _by_goal(rows, case["case_id"]) if g != goal)
        ),
    }


def _by_goal(rows, skip):
    goals = {}
    for r in rows:
        if r["case_id"] != skip:
            goals.setdefault(r["category_goal"], []).append(r["best_acceptable_deal_below_opening_pct"])
    return [(g, min(v), max(v)) for g, v in sorted(goals.items())]


def cited(state):
    """{ID: suppliers we cited it to}: an ID counts once per case (a rival's offer once per supplier)."""
    out = {}
    for sid, events in state.threads.items():
        for m in events:
            if m.get("from") == "buyer":
                for ref in set(m.get("refs") or []) | set(ID_RE.findall(m.get("body") or "")):
                    out.setdefault(ref, set()).add(sid)
    return out


def _about(fact, sid, parts):
    """Is a known fact about this supplier or this part? None when the fact does not say."""
    if not isinstance(fact, dict):
        return None
    sup, part = fact.get("supplier"), fact.get("part")
    num = sid.split(":")[-1]
    if sup is not None and str(sup).split(":")[-1] != num:
        return False
    if part is not None and parts and not any(str(part).split(":")[-1] == p.split(":")[-1] for p in parts):
        return False
    return True


def citable(state, sid, computed=None):
    """What may be cited to supplier `sid` now. `computed`: arguments already built and checked by
    the team's evidence code for this supplier ([{"sentence", "refs"}]), when our package knows it."""
    case, used = state.case, cited(state)
    items = []
    for ref in dict.fromkeys(list(case.get("refs") or []) + ([case["trigger_doc"]] if case.get("trigger_doc") else [])):
        kind = ref.split(":")[0]
        fact = state.facts.get(ref)
        about = _about(fact, sid, case.get("parts"))
        others = [o.split(":")[-1] for o in case.get("suppliers") or [] if o != sid]
        if about is False or (any(o in ref for o in others) and sid.split(":")[-1] not in ref):
            continue  # about another supplier or part: the arena would call it irrelevant
        item = {"id": ref, "the_arena_checks": CHECKED_AS.get(kind, "context, not a check")}
        if fact is not None:
            item["value"] = {k: v for k, v in fact.items() if k not in ("id",)} if isinstance(fact, dict) else fact
        else:
            item["value"] = NO_FIGURE
        if ref in used:
            item["already_cited_in_this_case"] = True
        alt = case["buyer"].get("alternative") or {}
        if alt.get("ref") == ref:
            alt_price, its_price = (
                (alt.get("terms") or {}).get("unit_price"),
                (state.standing(sid)[1] or {}).get("unit_price"),
            )
            item["this_is_our_alternative_without_a_deal"] = (
                f"its unit price is {alt_price}; citing it shows this supplier what we would otherwise pay"
                + (" - which is MORE than its own price" if alt_price and its_price and alt_price > its_price else "")
            )
        items.append(item)
    rivals = []
    for other in state.threads:
        if other == sid:
            continue
        sheet_id, terms = state.standing(other) if state.threads[other] else (None, {})
        if sheet_id and terms.get("unit_price") is not None:
            rivals.append(
                {
                    "id": sheet_id,
                    "unit_price": terms["unit_price"],
                    "terms": terms,
                    "already_cited_to_this_supplier": sid in used.get(sheet_id, ()),
                    "the_arena_checks": CHECKED_AS["offer"],
                }
            )
    out = {"ids_the_case_points_to": items}
    if rivals:
        out["standing_offers_of_the_other_bidders"] = rivals
    ready = [
        {"sentence": c["sentence"], "refs": c["refs"]}
        for c in computed or []
        if c.get("sentence") and c.get("refs") and not any(r in used for r in c["refs"])
    ]
    if ready:
        out["arguments_already_computed_and_checked"] = ready[:8]
    out["rules"] = (
        "at most 3 arguments are read per e-mail, one per sentence, the ID in the sentence; an ID counts once "
        "per case; never cite an ID that is not listed here or that you have not looked up"
    )
    return out


def stated_drivers(events, current_price=None):
    """The cost drivers a supplier stated in its own e-mails ("X rose 3.1 % in twelve months and is
    28 % of our cost") and what they add up to: by its own figures, how much of a price increase do
    they explain? Arithmetic on its statements, no data of ours."""
    seen = {}
    for m in events:
        if m.get("from") == "buyer":
            continue
        for series, verb, change, share in DRIVER_RE.findall(m.get("body") or ""):
            change, share = float(change.replace(",", ".")), float(share.replace(",", "."))
            if verb == "fell" and change > 0:
                change = -change
            seen[series] = {
                "series": series,
                "change_pct_it_states": change,
                "share_of_its_cost_pct": share,
                "explains_pct_of_price": round(change * share / 100, 2),
            }
    if not seen:
        return None
    out = {
        "drivers_it_stated": list(seen.values()),
        "together_they_explain_pct": round(sum(d["explains_pct_of_price"] for d in seen.values()), 2),
    }
    first = next((m for m in events if m.get("from") != "buyer"), {})
    sheets = first.get("term_sheets") or []
    opening = (sheets[0].get("terms") or {}).get("unit_price") if sheets else None
    if current_price and opening:
        out["increase_its_opening_quote_asks_pct"] = round(100 * (opening / current_price - 1), 2)
    return out


class Records:
    """What our package knows about the suppliers of a case: arguments the team's evidence code has
    built and checked, and signals read from notes, letters and news. Everything is optional: a
    supplier our package does not know simply has none."""

    def __init__(self, case, package):
        self.case, self.pkg = case, package
        self.claims = self.intel = None
        if package is None:
            return
        try:
            from ..pegasus.claims import Claims
            from ..pegasus.intel_bridge import Intelligence

            self.claims = Claims(case, package)
            self.intel = Intelligence(package)
        except Exception:
            log.exception("%s: evidence code unavailable", case.get("case_id"))

    def arguments(self, sid, price, drivers_text=""):
        if self.claims is None:
            return []
        out = []
        for part in self.case.get("parts") or [None]:
            try:
                out += self.claims.candidates(sid, part, price, drivers_text)
            except Exception:
                log.exception("%s %s: candidates failed", self.case.get("case_id"), sid)
        return sorted(out, key=lambda c: -c.get("weight", 0))

    def signals(self, sid):
        """[{type, confidence, explanation}] read from our notes, letters and news about this supplier."""
        if self.intel is None:
            return []
        try:
            brief = self.intel.brief(self.case, sid)
        except Exception:
            log.exception("%s %s: brief failed", self.case.get("case_id"), sid)
            return []
        return [
            {
                "type": s.get("type"),
                "confidence": s.get("confidence"),
                "explanation": s.get("explanation"),
                "sources": [e.get("ref") for e in s.get("evidence") or [] if e.get("ref")][:4],
            }
            for s in brief.get("signals") or []
        ]
