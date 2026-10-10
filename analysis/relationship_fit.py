"""Fit each relationship-case supplier's full cost on OUR ended practice deals, compare it with the
package's should-cost, and score the floor of `hollerau.pegasus.relationship` against the fit.

Reads the sessions dumped by analysis/session_dump.py into data/sessions. Opens no session.
  uv run python analysis/relationship_fit.py
The fit inverts the published formula (`arena_kit.cost.relationship_cost`) on the relationship cost
the arena charged. It is exact only as far as the supplier's standard terms are known: the opening
quote's payment terms are used, 30 days when it states none.
"""

import json
import math

from _common import PACKAGE, ROOT, load_cases

from arena_kit import cost as kit
from arena_kit.data import DataPackage
from hollerau.pegasus import economics as eco
from hollerau.pegasus import relationship

relationship.ENABLED = True
CASES = {c["case_id"]: c for c in load_cases("practice")}
PKG = DataPackage(PACKAGE)


def margin_gap(charged, case, terms):
    """Margin points below the sustainable margin that a charged relationship cost implies."""
    soft = charged / (case["buyer"]["relationship_eur_per_point"] * kit._years(case, terms))
    return math.sqrt(10 * soft) if soft <= 2.5 else soft + 2.5


def ended_deals():
    out = {}
    for path in sorted((ROOT / "data" / "sessions").glob("*.json")):
        s = json.loads(path.read_text())["state"]
        r, case = s.get("result") or {}, CASES.get(s["case_id"])
        if not case or not r.get("deal") or not relationship.applies(case):
            continue
        seen = out.setdefault(s["case_id"], {"opening": s["opening"][r["supplier_id"]]["terms"], "deals": {}})
        seen["deals"][json.dumps(r["terms"], sort_keys=True)] = r
    return out


def fit(case, standard, charged):
    """(full cost, the supplier's cost of money) that best explain the relationship costs charged."""
    best = None
    for rate in (x / 200 for x in range(61)):
        costs = []
        for r in charged:
            gap = margin_gap(r["cost_breakdown"]["relationship"], case, r["terms"])
            worth = kit.supplier_value(case, r["terms"], {"standard": standard, "interest_rate": rate})
            costs.append(worth * (1 - (case["buyer"]["sustainable_margin_pct"] - gap) / 100))
        spread = max(costs) - min(costs)
        if best is None or spread < best[0]:
            best = (spread, sum(costs) / len(costs), rate)
    return best[1], best[2]


for case_id, seen in sorted(ended_deals().items()):
    case, opening = CASES[case_id], seen["opening"]
    deals = list(seen["deals"].values())
    std = {"payment_days": opening.get("payment_days") or 30}
    standard = {k: v for k, v in kit.closing_terms(case, {}, std).items() if k != "unit_price"}
    best_played = max(r["score"] for r in deals)
    print(f"\n{case_id} ({case['type']}, {case['buyer']['category_goal']}), best score played {best_played:.3f}")
    charged = [r for r in deals if (r["cost_breakdown"]["relationship"] or 0) > 1]
    est = relationship.estimate(case, PKG, std)
    if not charged or not est:
        print("  no deal with a relationship cost charged, or no comparable should-cost: nothing to fit")
        continue
    full_cost, rate = fit(case, standard, charged)
    truth = {"full_cost": full_cost, "interest_rate": rate, "standard": standard}
    should = est["full_cost"] / relationship.FULL_COST_FACTOR
    print(f"  full cost fitted on {len(charged)} deal(s): {full_cost:.2f} (money at {rate:.1%})")
    print(f"  package should-cost: {should:.2f}, {100 * (should / full_cost - 1):+.1f}% above the fit")
    for r in deals:
        again = kit.relationship_cost(case, r["terms"], supplier=truth)
        was = r["cost_breakdown"]["relationship"]
        print(f"    price {r['terms']['unit_price']}: charged {was:.0f}, refitted {again:.0f}, score {r['score']:.3f}")
    ref_terms = {k: v for k, v in eco.closing_terms(case, opening, std).items() if k in eco.fields(case)}
    structure = eco.structures(case, eco.sheet(case, ref_terms, opening["unit_price"]), std)[0][1]
    floor = relationship.floor_price(case, structure, std, est)
    c = kit.total_cost(case, kit.complete_offer(case, {**structure, "unit_price": floor}), std, truth)
    at_floor = kit.score(deals[0]["c_open"], c, deals[0]["c_best"])
    factor = relationship.FULL_COST_FACTOR
    print(f"  floor at factor {factor}: {floor:.2f} -> score {at_floor:.3f} IF the supplier signs there")
