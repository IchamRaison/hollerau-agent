"""forecast_cost_news family: our demand forecast (`fc`), our should-cost (`cost`), news about the supplier, and the
supplier's own letter saying its material is covered (`doc`).

The arena checks the recorded change of an `fc` (a %), the estimate of a `cost` (EUR), and that a `news`
item is about this supplier (brief/api.md). Guards:
- `cost`: cited only when the price at stake (the lower of today's and the asked price) exceeds it by more than
  the should-cost's own error (5-15 %, KNOWN_ISSUES 14), and only when comparable (one part, same price unit).
- `fc`: our latest forecast for the part, cited when it grows: volume is our leverage. Never in a capacity case or
  with a supplier whose order book is full or that allocates: there, more volume is the supplier's leverage.
- `news`: only topics that weaken the supplier's position (free capacity, a new plant), from the 12 months before
  the case starts (Sunday release included, even after the supplier's letter).
- `doc` (material covered, signal material_hedged): only without a price letter, only the supplier's own letters
  and e-mails (our call and meeting notes are context, not checks), only while the cover still runs. The arena has
  no row for a letter cited alone: its result is not known yet (no figure, so at worst `irrelevant`).
"""

from datetime import date, datetime, timedelta

from hollerau.contracts import Claim

from .facts import _day, asked_price, case_start, comparable, has, package, stake_price
from .signals import HEDGED, saturated

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


SUPPLIER_DOCS = {"letter", "email"}


def _until(text: str) -> tuple[str, date] | None:
    """('March 2027', 2027-03-01) from "... at fixed prices until March 2027 ...", else None."""
    if not (m := HEDGED.search(text)):
        return None
    try:
        return m.group(1), datetime.strptime(m.group(1), "%B %Y").date()
    except ValueError:
        return None


def letter_claims(case: dict, data, facts: dict) -> list[Claim]:
    """The supplier's own letter or e-mail saying its material is covered until a date still to come, without a
    price letter (raw material, renewal). No figure, supports `other` (the index clause)."""
    if asked_price(case, facts) is not None:
        return []
    p, start = package(data), case_start(case, facts)
    if p is None:
        return []
    claims = []
    for doc_id in sorted(i for i in facts if i.startswith("doc:")):
        doc = facts[doc_id]
        if not has(doc, "supplier", "date", "type") or doc["supplier"] not in case["suppliers"]:
            continue
        sent = _day(doc["date"])
        if doc["type"] not in SUPPLIER_DOCS or sent is None or (start and sent > start):
            continue
        try:
            hedge = _until(" ".join(p.document(doc_id).split()))
        except (FileNotFoundError, OSError, ValueError):
            continue
        if hedge is None or (start and hedge[1] < start.replace(day=1)):
            continue  # no cover, or it has already run out
        claims.append(
            Claim(
                family="forecast_cost_news",
                ids=[doc_id],
                figure=None,
                unit="",
                sentence=f"Your letter of {doc['date']} ({doc_id}) says your material is covered until {hedge[0]}.",
                supports="other",
            )
        )
    return claims


def forecast_cost_news_claims(case: dict, data, facts: dict) -> list[Claim]:
    return (
        cost_claims(case, data, facts)
        + letter_claims(case, data, facts)
        + forecast_claims(case, data, facts)
        + news_claims(case, facts)
    )
