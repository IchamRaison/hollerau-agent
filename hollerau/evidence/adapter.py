"""Adapter for Pegasus (`hollerau/pegasus/`, Vincent's agent): our claims and planner hints, without touching its code.

pegasus_claims(case, package, pegasus_claims_list, used=None) -> list[Claim]
    The union of our claims (`compile_evidence`) and Pegasus candidates (`Claims.candidates` / `rival_claim` dicts:
    `refs`, `sentence`, optional `rival`), each ID once, strongest first. Our filters apply to the Pegasus ones:
    no should-cost unless clearly below the price at stake, no volume growth in a capacity case or to a saturated
    supplier, scorecards only past our thresholds, no index claim when the increase is justified, and every claim
    must pass `check()` - except a rival's session offer (`offer:`), which the arena checks itself. At most 3 per
    message: the caller slices. `used`: IDs already sent in this case, left out.
planner_hints(case, data, standard=None) -> dict
    What the planner needs in one place: levers in EUR, best package, price floor and its confidence, and the
    signals that change a move (pricing committee, cash need, material covered, increase justified).

Never raises: on any failure, our own claims (or empty hints), logged.
"""

import logging
import re

from hollerau.contracts import Claim

from .compile import compile_evidence
from .economics import compile_case
from .facts import check, comparable, facts_of, has, price_letter, stake_price
from .forecast_cost_news import CAPACITY_TYPES, COST_ERROR, FC_GROWTH_PCT, NEWS_TOPICS
from .index import asked_pct, driver_moves, increase_justified, weighted_move_pct
from .scorecard import dimension_ok
from .signals import saturated, signals

log = logging.getLogger(__name__)

RANK = {"notice": 0, "quote": 1, "scorecard": 2, "index": 3, "orders": 4, "forecast_cost_news": 5}
FAMILY = {
    "idx": "index",
    "doc": "notice",
    "ctr": "notice",
    "cost": "forecast_cost_news",
    "fc": "forecast_cost_news",
    "sc": "scorecard",
    "quote": "quote",
    "offer": "quote",
    "po": "orders",
    "news": "forecast_cost_news",
}
FIGURES = [  # (family, ID prefix, regex on a Pegasus sentence, unit)
    ("index", "idx", r"changed (-?[\d.]+)%", "%"),
    ("notice", "doc", r"gives (\d+) days", "days"),
    ("forecast_cost_news", "cost", r"is ([\d.]+) EUR", "EUR"),
    ("forecast_cost_news", "fc", r"up ([\d.]+)%", "%"),
    ("scorecard", "sc", r"delivery was ([\d.]+)%", "%"),
    ("scorecard", "sc", r"quality was ([\d.]+) ppm", "ppm"),
    ("quote", "offer", r"offer at ([\d.]+) EUR", "EUR"),
]
SUPPORTS = {"index": "price", "notice": "effective_date", "quote": "price", "orders": "price"}


def as_claim(candidate: dict) -> Claim:
    """A Pegasus candidate as a `Claim`: family from its first ID, figure and unit read from its sentence."""
    refs, text = list(candidate["refs"]), candidate["sentence"]
    prefix = refs[0].split(":", 1)[0]
    family = FAMILY.get(prefix, prefix)
    supports = {"sc": "other", "fc": "volume"}.get(prefix, SUPPORTS.get(family, "price"))
    for fam, pre, pattern, unit in FIGURES:
        if prefix == pre and (m := re.search(pattern, text)):
            return Claim(fam, refs, float(m.group(1)), unit, text, "quality" if unit == "ppm" else supports)
    return Claim(family, refs, None, "", text, supports)


def _justified(case: dict, data, facts: dict) -> bool:
    """The supplier's increase is explained by its cost drivers (within a point): index claims argue its case."""
    asked = asked_pct(case, facts)
    if asked is None:
        return False
    return any(
        increase_justified(weighted_move_pct(moves), asked)
        for part in case["parts"]
        if (moves := driver_moves(part, data, facts))
    )


def _keep(case: dict, data, facts: dict, claim: Claim, justified: bool) -> bool:
    """Our filters, applied to one Pegasus claim (not a rival's offer)."""
    if not check(claim, facts):
        return False
    prefix = claim.ids[0].split(":", 1)[0]
    row = facts.get(claim.ids[0])
    if prefix == "cost":
        stake = stake_price(case, facts)
        return (
            has(row, "unit_cost")
            and stake is not None
            and comparable(case, data, row)
            and row["unit_cost"] * (1 + COST_ERROR) < stake
        )
    if prefix == "fc":
        if case.get("type") in CAPACITY_TYPES or any(saturated(case, data, facts, s) for s in case["suppliers"]):
            return False
        return has(row, "change_pct") and row["change_pct"] >= FC_GROWTH_PCT
    if prefix == "sc":
        return dimension_ok(row, claim.unit == "ppm")
    if prefix == "idx":
        return not justified
    if prefix == "news":
        return has(row, "topic") and row["topic"] in NEWS_TOPICS
    if prefix == "doc" and claim.family == "forecast_cost_news":
        return not price_letter(case, facts)
    return prefix in {"doc", "ctr", "quote", "po"}


def pegasus_claims(case: dict, package, pegasus_claims_list, used=None) -> list[Claim]:
    used = set(used or ())
    try:
        ours = compile_evidence(case, package)
    except Exception:
        log.exception("%s: our claims failed", case.get("case_id") if isinstance(case, dict) else None)
        ours = []
    try:
        facts = facts_of(case, package)
        justified = _justified(case, package, facts)
        theirs = []
        for candidate in pegasus_claims_list or []:
            try:
                claim = as_claim(candidate)
                if candidate.get("rival") or _keep(case, package, facts, claim, justified):
                    theirs.append(claim)
            except Exception:
                log.warning("%s: Pegasus candidate skipped: %r", case.get("case_id"), candidate)
    except Exception:
        log.exception("%s: Pegasus claims dropped, ours kept", case.get("case_id"))
        theirs = []
    out, seen = [], set(used)
    for claim in sorted(ours + theirs, key=lambda c: RANK.get(c.family, len(RANK))):  # stable: ours first
        if seen & set(claim.ids):
            continue  # each ID counts once per case
        seen |= set(claim.ids)
        out.append(claim)
    return out


def planner_hints(case: dict, data, standard=None) -> dict:
    out = {
        "reference_price": None,
        "best_package": {},
        "levers": [],
        "c_alt": None,
        "price_floor_hint": None,
        "price_floor_confidence": None,
        "price_floor_reason": None,
        "asked_pct": None,
        "increase_justified": None,
        "suppliers": {},
    }
    try:
        econ = compile_case(case, standard, data)
        out["reference_price"], out["best_package"], out["c_alt"] = econ.reference_price, econ.best_package, econ.c_alt
        out["levers"] = [
            {"field": lv.field, "best": lv.best, "worst": lv.worst, "eur": lv.cost_of_forgetting_eur}
            for lv in econ.levers
        ]
    except Exception:
        log.exception("%s: economics hints failed", case.get("case_id") if isinstance(case, dict) else None)
    try:
        s = signals(case, data)
        for key in (
            "price_floor_hint",
            "price_floor_confidence",
            "price_floor_reason",
            "asked_pct",
            "increase_justified",
        ):
            out[key] = s.get(key)
        for sup, sig in (s.get("suppliers") or {}).items():
            out["suppliers"][sup] = {
                "committee_above_pct": sig.get("committee_above_pct"),
                "cash_need": bool(sig.get("cash_need")),
                "material_hedged_until": sig.get("material_hedged_until"),
                "full_order_book": bool(sig.get("full_order_book")),
                "free_capacity": bool(sig.get("free_capacity")),
                "single_source": sig.get("single_source"),
                "sources": {k: sig.get(k) for k in ("committee", "cash_need", "material_hedged") if sig.get(k)},
            }
    except Exception:
        log.exception("%s: signal hints failed", case.get("case_id") if isinstance(case, dict) else None)
    return out
