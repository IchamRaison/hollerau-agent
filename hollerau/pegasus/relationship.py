"""Relationship-aware price floor for stabilise / secure_supply cases (off unless PEGASUS_REL=on).

There the arena charges a relationship cost when a deal leaves the supplier below its sustainable
margin (`arena_kit.cost.relationship_cost`), so C is U-shaped in the price: below the bottom of the
U a lower price costs us more. Our ended P02 deals show both slopes: 371.92 scored 0.50 (too
careful), 349.36 scored 0.23 and 344.20 scored 0 (too low). `floor_price` is that bottom on our
estimate of the supplier: the agent never asks below it, and ranks standing offers by C including
the estimated relationship cost.

The estimate is the economics lane's (`hollerau.evidence.economics.estimate_supplier`), kept only
when it rests on the package's should-cost. Fitted on our ended deals of P01, P02 and P03, that
should-cost sits 2.0 to 2.4 % above the full cost the arena charges on. FULL_COST_FACTOR corrects
it, a little on the low side because the two errors are not alike: a floor that is too low only
fails to bind, one that is too high stops the negotiation early. Three suppliers is a thin sample:
measure before relying on it. Without a comparable should-cost there is no floor, nothing changes.
"""

import logging
import math
import os

from arena_kit import cost as kit

from ..evidence.economics import estimate_supplier

log = logging.getLogger("pegasus")

ENABLED = os.environ.get("PEGASUS_REL", "off") == "on"
FULL_COST_FACTOR = float(os.environ.get("PEGASUS_FULL_COST_FACTOR", "0.975"))


def applies(case):
    """The arena charges a relationship cost in this case."""
    b = case["buyer"]
    return bool(
        b.get("category_goal") in kit.RELATIONSHIP_GOALS
        and b.get("relationship_eur_per_point")
        and b.get("sustainable_margin_pct")
    )


def estimate(case, package=None, std=None):
    """Our estimate of the supplier for the relationship term (`arena_kit.cost.supplier_value`),
    or None: feature off, no relationship cost in this case, or no comparable should-cost.
    `std`: the supplier's standard terms from its quote."""
    if not ENABLED or not applies(case):
        return None
    try:
        sup = estimate_supplier(case, package, std)
    except Exception:
        log.exception("%s: supplier estimate failed, no relationship floor", case.get("case_id"))
        return None
    if sup.get("estimated") or not sup.get("full_cost"):
        return None  # the fallback (current price less the margin) can be far too high: P10
    return {**sup, "full_cost": sup["full_cost"] * FULL_COST_FACTOR}


def cost(case, terms, std, sup):
    """The estimated relationship cost of a term sheet in EUR, 0 without an estimate."""
    if not sup:
        return 0.0
    return kit.relationship_cost(case, kit.closing_terms(case, terms, std), supplier=sup)


def floor_price(case, structure, std, sup):
    """The unit price at the bottom of the U for `structure` (the non-price terms): C including the
    estimated relationship cost is convex in the price, so a ternary search finds it."""
    base = kit.complete_offer(case, {**structure, "unit_price": 1.0})

    def total(price):
        return kit.total_cost(case, {**base, "unit_price": price}, std, sup)

    lo, hi = 0.5 * sup["full_cost"], 2.0 * sup["full_cost"]
    for _ in range(80):
        a, b = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if total(a) > total(b):
            lo = a
        else:
            hi = b
    return math.ceil((lo + hi) / 2 * 100 - 1e-6) / 100
