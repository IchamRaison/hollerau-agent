"""Orders family: the supplier already raised its price on our orders of the same part.

The arena checks 2-8 `po` lines of one part against their order prices (brief/api.md); lines of different
parts are separate arguments. We cite the first order of the last 24 months and the latest one, when the
price already rose by RAISED_PCT or more in between. Lines at an outdated price (`stale_condition`,
KNOWN_ISSUES 6) are skipped. Prices stay per the part's price_unit, as in the data.
"""

from datetime import date

from hollerau.contracts import Claim

from .facts import package, release_rows

WINDOW_DAYS = 730
RAISED_PCT = 3.0
COLUMNS = "id, order_date, price, price_unit, price_note, part_id, supplier_id"


def _row(r: dict) -> dict | None:
    """An order line with a usable date and price (release CSV rows hold strings), else None."""
    try:
        price, unit = float(r["price"]), int(float(r.get("price_unit") or 1))
        return {**r, "price": price, "price_unit": unit, "day": date.fromisoformat(r["order_date"])}
    except (KeyError, TypeError, ValueError):
        return None


def _lines(data, part: str, supplier: str, facts: dict) -> list[dict]:
    """The supplier's order lines for the part, package then Sunday release, oldest first."""
    p = package(data)
    rows = []
    if p is not None and p.db is not None:
        rows = p.query(
            f"SELECT {COLUMNS} FROM po_lines WHERE part_id = ? AND supplier_id = ? ORDER BY order_date, id",
            (part, supplier),
            limit=10_000,
        )
    rows += [r for r in release_rows(data, "po_lines") if r.get("part_id") == part and r.get("supplier_id") == supplier]
    lines = [x for r in rows if r.get("price_note") != "stale_condition" and r.get("id") in facts and (x := _row(r))]
    return sorted((x for x in lines if x["price"] > 0), key=lambda x: (x["day"], x["id"]))


def orders_claims(case: dict, data, facts: dict) -> list[Claim]:
    claims = []
    for supplier in case["suppliers"]:
        for part in case["parts"]:
            lines = _lines(data, part, supplier, facts)
            if len(lines) < 2:
                continue
            last = lines[-1]
            since = last["day"].toordinal() - WINDOW_DAYS
            first = next(r for r in lines if r["day"].toordinal() >= since)
            rise = (last["price"] / first["price"] - 1) * 100
            if first is last or rise < RAISED_PCT:
                continue
            per = f" per {last['price_unit']} pcs" if (last.get("price_unit") or 1) > 1 else ""
            claims.append(
                Claim(
                    family="orders",
                    ids=[first["id"], last["id"]],
                    figure=None,  # the arena takes the order prices themselves
                    unit="",
                    sentence=(
                        f"Our orders of {part} already went from {first['price']:.2f} ({first['id']}, "
                        f"{first['order_date'][:7]}) to {last['price']:.2f} EUR{per} ({last['id']}, "
                        f"{last['order_date'][:7]})."
                    ),
                    supports="price",
                )
            )
    return claims
