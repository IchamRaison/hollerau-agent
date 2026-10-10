"""One evaluation of a term sheet, used to propose, to compare and to conclude.

Two things of different standing, kept apart:
- `commercial`: what the sheet costs us by the published cost function (`arena_kit.cost`) -
  accounting, as exact as the case file and the supplier's standard terms;
- `risks`: the relationship charge under each hypothesis we hold about the supplier's full cost
  (strategic and bottleneck goals only) - estimates, each with where it comes from.
When the charge applies and we hold no hypothesis the risk is unknown, not zero: `known` is False
and `commercial` is then an optimistic bound. A choice that flips with the hypothesis is `fragile`:
the caller must say so instead of treating one estimate as the truth.
"""

from dataclasses import dataclass, field

from arena_kit.cost import RELATIONSHIP_GOALS, closing_terms, must_haves_ok, relationship_cost, total_cost

INF = float("inf")


@dataclass
class Evaluation:
    valid: bool  # complete, priced and within the must-haves
    commercial: float  # C by the published function, no estimate of the supplier in it
    risks: list = field(default_factory=list)  # [{"name", "eur", "provenance"}], one per hypothesis
    known: bool = True  # False: a relationship charge applies and we cannot estimate it

    @property
    def low(self):
        """Total under the most favourable hypothesis."""
        return self.commercial + min((r["eur"] for r in self.risks), default=0.0)

    @property
    def cautious(self):
        """Total under the least favourable hypothesis: what decisions are taken on."""
        return self.commercial + max((r["eur"] for r in self.risks), default=0.0)

    def summary(self):
        return {"valid": self.valid, "commercial": round(self.commercial, 2), "low": round(self.low, 2),
                "cautious": round(self.cautious, 2), "known": self.known,
                "risks": [{**r, "eur": round(r["eur"], 2)} for r in self.risks]}


def charge_applies(case):
    """The arena charges a relationship cost in this case (strategic and bottleneck goals)."""
    b = case["buyer"]
    return bool(b.get("category_goal") in RELATIONSHIP_GOALS and b.get("relationship_eur_per_point")
                and b.get("sustainable_margin_pct"))


def clean(terms):
    """Without the private keys pegasus keeps next to the supplier's standard terms."""
    return {k: v for k, v in (terms or {}).items() if not k.startswith("_")}


def evaluate(case, terms, std=None, hypotheses=()):
    """`terms`: a term sheet (the supplier's standard terms `std` fill what it leaves out).
    `hypotheses`: [{"name", "supplier", "provenance"}], `supplier` as `arena_kit.cost.supplier_value`
    takes it. Never raises: a sheet that cannot be costed is invalid at an infinite cost."""
    std, terms = clean(std), clean(terms)
    applies = charge_applies(case)
    if terms.get("unit_price") is None:
        return Evaluation(False, INF, [], not applies)
    try:
        closed = closing_terms(case, terms, std)
        commercial = total_cost(case, closed)
        valid = must_haves_ok(case, closed)
    except (KeyError, TypeError, ValueError):
        return Evaluation(False, INF, [], not applies)
    risks = []
    for h in hypotheses if applies else ():
        try:
            eur = relationship_cost(case, closed, supplier=h["supplier"])
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
        risks.append({"name": h["name"], "eur": eur, "provenance": h.get("provenance", "")})
    return Evaluation(valid, commercial, risks, bool(risks) or not applies)


def better(a, b, margin=0.0):
    """`a` beats `b` on the cautious total, by more than `margin` EUR."""
    return a.valid and (not b.valid or a.cautious < b.cautious - margin)


def fragile(a, b):
    """The order of two valid sheets depends on which hypothesis about the supplier is true."""
    if not (a.valid and b.valid):
        return False
    return (a.low < b.low) != (a.cautious < b.cautious)


def best(evaluated):
    """(key, Evaluation) with the lowest cautious total among the valid ones, else None.
    `evaluated`: iterable of (key, Evaluation)."""
    valid = [(k, e) for k, e in evaluated if e.valid]
    return min(valid, key=lambda x: x[1].cautious) if valid else None
