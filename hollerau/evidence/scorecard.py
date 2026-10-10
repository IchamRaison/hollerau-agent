"""Scorecard family: the supplier's rolling 12-month scorecard (`sc:<supplier>@<quarter>`) when it is not green.

The arena checks the mean on-time delivery of the cited rows, or their mean ppm if we speak of quality
(brief/api.md). Each `sc` row is already a rolling 12-month figure (P11 letter), so one row is one argument.
OTD is low across the package (KNOWN_ISSUES 1: it depends on the reference date): only a red or amber card
and a clear gap are cited.
"""

from hollerau.contracts import Claim

from .facts import has

PPM_LIMIT = 1000  # above this, the quality argument
OTD_LIMIT = 80.0  # below this %, the delivery argument
QUALITY_TYPES = {"quality"}


def supplier_cards(supplier: str, facts: dict) -> list[str]:
    """The supplier's scorecard IDs, latest first."""
    prefix = "sc:" + supplier.split(":", 1)[1] + "@"
    return sorted((i for i in facts if i.startswith(prefix)), reverse=True)


def _claim(sc_id: str, row: dict, quality: bool) -> Claim:
    quarter = sc_id.rsplit("@", 1)[1]
    if quality:
        return Claim(
            family="scorecard",
            ids=[sc_id],
            figure=float(row["ppm"]),
            unit="ppm",
            sentence=f"Your rolling quality to {quarter} stands at {row['ppm']} ppm ({sc_id}).",
            supports="quality",
        )
    return Claim(
        family="scorecard",
        ids=[sc_id],
        figure=row["otd_pct"],
        unit="%",
        sentence=f"Your rolling on-time delivery to {quarter} stands at {row['otd_pct']:.1f}% ({sc_id}).",
        supports="other",
    )


def scorecard_claims(case: dict, data, facts: dict) -> list[Claim]:
    claims = []
    for supplier in case["suppliers"]:
        cards = [i for i in supplier_cards(supplier, facts) if has(facts[i], "ppm", "otd_pct")]  # null rows skipped
        if not cards or facts[cards[0]].get("colour") == "green":
            continue
        row = facts[cards[0]]
        bad = []  # (quality?) in order of strength for this case
        if row["ppm"] > PPM_LIMIT:
            bad.append(True)
        if row["otd_pct"] < OTD_LIMIT:
            bad.append(False)
        if case.get("type") not in QUALITY_TYPES:
            bad.sort()  # delivery first outside quality cases
        # each ID counts once: the second argument uses the previous quarter, if it is bad on that dimension too
        for n, quality in enumerate(bad):
            if n >= len(cards):
                break
            sc_id, r = cards[n], facts[cards[n]]
            if (quality and r["ppm"] > PPM_LIMIT) or (not quality and r["otd_pct"] < OTD_LIMIT):
                claims.append(_claim(sc_id, r, quality))
    return claims
