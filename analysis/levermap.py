"""Lever map: for every case, the best package of non-price terms and the cost of forgetting each lever.

Reference price: the price asked in the trigger letter when the data has it, else the current price,
else the alternative's or the fallback price. Only the published cost function is used (no relationship
term: that needs an estimate of the supplier). Values that break a must-have are left out.
"""

import itertools
import json

from _common import facts, load_cases, short

from arena_kit.cost import complete_offer, must_haves_ok, total_cost

FACTS = facts()
HEAD = (
    "Case",
    "Type",
    "Goal",
    "Spend k EUR",
    "Ref price",
    "Range % spend",
    "Best package",
    "Cost of forgetting, % spend",
    "Must-haves",
)


def ref_price(case):
    b = case["buyer"]
    asked = (FACTS.get(case.get("trigger_doc") or "") or {}).get("asked_price")
    alt = ((b.get("alternative") or {}).get("terms") or {}).get("unit_price")
    return asked or b.get("current_unit_price") or alt or b["fallback_unit_price"], "asked" if asked else "current"


def show(v):
    if isinstance(v, dict):
        return f"index {v['series']} deadband {v['deadband_pct']}%"
    return "none" if v is None else str(v)


def row(case):
    b = case["buyer"]
    price, kind = ref_price(case)
    base = complete_offer(case, {"unit_price": price})
    levers = [f for f in case["negotiable"] if f != "unit_price" and case.get("term_options", {}).get(f)]
    values = itertools.product(*(case["term_options"][f] for f in levers))
    combos = [dict(zip(levers, v, strict=True)) for v in values]
    ok = [x for x in combos if must_haves_ok(case, {**base, **x})]

    def cost(x):
        return total_cost(case, {**base, **x})

    best, worst = min(ok, key=cost), max(ok, key=cost)
    spend = b["need_per_year"] * b["horizon_years"] * price
    forget = []
    for f in levers:
        same = [x for x in ok if all(x[g] == best[g] for g in levers if g != f)]
        loss = max(cost(x) for x in same) - cost(best)
        if loss > 0:
            forget.append((loss, f))
    forget.sort(reverse=True)
    return (
        short(case),
        case["type"],
        b["category_goal"],
        f"{spend / 1e3:.0f}",
        kind,
        f"{(cost(worst) - cost(best)) / spend * 100:.1f}",
        ", ".join(f"{f}={show(best[f])}" for f in levers),
        "; ".join(f"{f} {loss / spend * 100:.1f}" for loss, f in forget) or "-",
        json.dumps(b["must_haves"]) if b.get("must_haves") else "",
    )


print("| " + " | ".join(HEAD) + " |")
print("|" + "---|" * len(HEAD))
for c in load_cases():
    print("| " + " | ".join(row(c)) + " |")
print("\n* = practice case that is not hosted (cannot be played).")
