"""forecast_cost_news family: our demand forecast (`fc`), our should-cost (`cost`), news about the supplier.

The arena checks the recorded change of an `fc` (a %), the estimate of a `cost` (EUR), and that a `news`
item is about this supplier (brief/api.md). Guards:
- `cost`: cited only when the price at stake (the lower of today's and the asked price) exceeds it by more than
  the should-cost's own error (5-15 %, KNOWN_ISSUES 14), and only when comparable (one part, same price unit).
- `fc`: our latest forecast for the part, cited when it grows: volume is our leverage. Never in a capacity case or
  with a supplier whose order book is full or that allocates: there, more volume is the supplier's leverage.
- `news`: only topics that weaken the supplier's position (free capacity, a new plant), from the 12 months before
  the case starts (Sunday release included, even after the supplier's letter).
"""

from datetime import timedelta

from hollerau.contracts import Claim

from .facts import _day, case_start, comparable, has, stake_price
from .signals import saturated

COST_ERROR = 0.15
FC_GROWTH_PCT = 5.0
NEWS_TOPICS = {"free_capacity", "new_plant"}
NEWS_DAYS = 365
CAPACITY_TYPES = {"capacity"}


def _number(ref: str) -> str:
    return ref.split(":", 1)[1]


def cost_claims(case: dict, data, facts: dict) -> list[Claim]:
    stake = stake_price(case, facts)
    claims = []
    for part in case["parts"]:
        cid = f"cost:{_number(part)}"
        row = facts.get(cid)
        if not has(row, "unit_cost") or stake is None or not comparable(case, data, row):
            continue
        if row["unit_cost"] * (1 + COST_ERROR) >= stake:
            continue
        claims.append(
            Claim(
                family="forecast_cost_news",
                ids=[cid],
                figure=row["unit_cost"],
                unit="EUR",
                sentence=f"Our should-cost estimate for {part} is {row['unit_cost']:.2f} EUR ({cid}).",
                supports="price",
            )
        )
    return claims


def forecast_claims(case: dict, data, facts: dict) -> list[Claim]:
    if case.get("type") in CAPACITY_TYPES or any(saturated(case, data, facts, s) for s in case["suppliers"]):
        return []
    claims = []
    for part in case["parts"]:
        ids = sorted(i for i in facts if i.startswith(f"fc:{_number(part)}@") and has(facts[i], "change_pct"))
        if not ids or facts[ids[-1]]["change_pct"] < FC_GROWTH_PCT:
            continue
        fid, change = ids[-1], facts[ids[-1]]["change_pct"]
        claims.append(
            Claim(
                family="forecast_cost_news",
                ids=[fid],
                figure=change,
                unit="%",
                sentence=f"Our latest forecast for {part} grows {change:+.1f}% ({fid}).",
                supports="volume",
            )
        )
    return claims


def news_claims(case: dict, facts: dict) -> list[Claim]:
    until = case_start(case, facts)
    since = until - timedelta(days=NEWS_DAYS) if until else None
    claims = []
    for nid in sorted((i for i in facts if i.startswith("news:")), reverse=True):
        n = facts[nid]
        if not has(n, "date", "headline", "supplier", "topic"):
            continue
        if n["supplier"] not in case["suppliers"] or n["topic"] not in NEWS_TOPICS:
            continue
        day = _day(n["date"])
        if day is None or (since and day < since) or (until and day > until):
            continue
        claims.append(
            Claim(
                family="forecast_cost_news",
                ids=[nid],
                figure=None,
                unit="",
                sentence=f"We read that {n['headline'].rstrip('.')} ({nid}).",
                supports="volume" if n["topic"] == "free_capacity" else "other",
            )
        )
    return claims


def forecast_cost_news_claims(case: dict, data, facts: dict) -> list[Claim]:
    return cost_claims(case, data, facts) + forecast_claims(case, data, facts) + news_claims(case, facts)
