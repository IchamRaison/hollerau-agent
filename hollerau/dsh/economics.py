"""One economic façade for the DSH pilot: the model, the validation and the fallback read the
same numbers here.

Nothing is re-derived: C is the kit's published function (`arena_kit.cost`), the cost-to-price
inversion and the grid of structures are Pegasus' (`pegasus.economics`). What this module adds is
the standing of each number: `commercial` is exact accounting from the case file and the
supplier's standard terms; the relationship charge (strategic and bottleneck goals) depends on
the supplier's full cost, which we only estimate - it is reported apart, with where the estimate
comes from, and as unknown when we hold none.
"""

import json

from arena_kit.cost import RELATIONSHIP_GOALS, cost_breakdown, must_haves_ok, supplier_value

from ..pegasus import economics as eco

INF = float("inf")


def charge_applies(case):
    """The arena charges for a squeezed supplier in this case (stabilise, secure_supply)."""
    b = case["buyer"]
    return bool(
        b.get("category_goal") in RELATIONSHIP_GOALS
        and b.get("relationship_eur_per_point")
        and b.get("sustainable_margin_pct")
    )


def clean(terms):
    return {k: v for k, v in (terms or {}).items() if not k.startswith("_")}


def _est(estimate):
    """The estimate as `arena_kit.cost.supplier_value` takes it (our bookkeeping keys dropped)."""
    return clean(estimate) or None


def problems(case, terms):
    """Why the arena would refuse this term sheet (422), [] when it is well formed."""
    out, opts = [], case.get("term_options", {})
    for f in case["negotiable"]:
        if terms.get(f) is None and not (f == "index_clause" and f in terms):
            out.append(f"missing field {f}")
    for f, v in terms.items():
        if f not in case["negotiable"]:
            out.append(f"{f} is not negotiable in this case")
        elif f == "unit_price":
            if not isinstance(v, int | float) or isinstance(v, bool) or v != v or v <= 0 or v in (INF, -INF):
                out.append("unit_price must be a positive number")
            elif round(v, 2) != v:
                out.append("unit_price takes 2 decimals")
        elif opts.get(f) and v not in opts[f]:
            out.append(f"{f}={v!r} is not an allowed option {opts[f]}")
    return out


def evaluate(case, terms, std=None, estimate=None):
    """What a term sheet costs the buyer. `std`: the supplier's standard terms, which fill what
    the sheet leaves out; `estimate`: our estimate of the supplier (`supplier_value`'s argument)
    or None. Never raises: a sheet that cannot be costed is invalid at an unknown cost."""
    terms, std = clean(terms), clean(std)
    out = {
        "terms": terms,
        "problems": problems(case, terms),
        "must_haves_ok": None,
        "commercial_eur": None,
        "relationship_eur": None,
        "relationship": "does not apply",
        "total_eur": None,
        "breakdown": None,
    }
    if terms.get("unit_price") is None:
        out["problems"].append("no unit_price: a sheet without a price has no cost")
        return out
    try:
        parts = cost_breakdown(case, terms, std, _est(estimate))
        out["must_haves_ok"] = must_haves_ok(case, terms, std)
    except (KeyError, TypeError, ValueError) as e:
        out["problems"].append(f"cannot be costed: {type(e).__name__} {e}")
        return out
    rel = parts.pop("relationship", 0.0)
    out["breakdown"] = {k: round(v, 2) for k, v in parts.items() if abs(v) >= 0.005}
    out["commercial_eur"] = round(sum(parts.values()), 2)
    if charge_applies(case):
        if estimate:
            out["relationship_eur"] = round(rel, 2)
            out["relationship"] = "estimated from our estimate of the supplier's full cost - not a fact"
        else:
            out["relationship"] = (
                "applies, unknown: we hold no estimate of the supplier's full cost; "
                "commercial_eur is then an optimistic bound"
            )
    out["total_eur"] = round(out["commercial_eur"] + (out["relationship_eur"] or 0.0), 2)
    if out["must_haves_ok"] is False:
        out["problems"].append("breaks a must-have: a deal on it scores 0")
    return out


def cost(case, terms, std=None, estimate=None):
    """C in EUR (relationship estimate included when we hold one), inf when it cannot be costed."""
    e = evaluate(case, terms, std, estimate)
    return INF if e["total_eur"] is None else e["total_eur"]


def alternative(case):
    """C of what the buyer gets without a deal, None when there is no alternative."""
    c = eco.alt_cost(case)
    return None if c == INF else round(c, 2)


def structures_for_target(case, target_eur, std=None, estimate=None, restrict=None, limit=12):
    """Every allowed combination of the non-price terms, each at the unit price that makes it cost
    the buyer `target_eur`. At equal cost for us the highest such price is returned: it is the
    sheet the supplier likes most. `restrict`: {field: [allowed values]} chosen by the caller.
    A combination that cannot get as cheap as the target comes back with `reached: false` and its
    cheapest attainable cost (the bottom of the U when a relationship charge applies)."""
    std = clean(std)
    priced_std = {**std, "_supplier": _est(estimate)} if estimate else std
    grid = eco.grid(case)
    out = []
    for structure in grid:
        if restrict and any(f in restrict and structure.get(f) not in restrict[f] for f in structure):
            continue
        price = eco.price_for(case, structure, target_eur, priced_std)
        terms = eco.sheet(case, structure, price)
        e = evaluate(case, terms, std, estimate)
        if e["total_eur"] is None or e["must_haves_ok"] is False or e["problems"]:
            continue
        # a price has two decimals: the target is reached when it lies within one cent of price
        cent = abs(cost(case, {**terms, "unit_price": round(price + 0.01, 2)}, std, estimate) - e["total_eur"])
        out.append(
            {
                "terms": terms,
                "total_eur": e["total_eur"],
                "commercial_eur": e["commercial_eur"],
                "relationship_eur": e["relationship_eur"],
                "reached": abs(e["total_eur"] - target_eur) <= max(1.0, cent),
            }
        )
    out.sort(key=lambda x: (not x["reached"], -x["terms"]["unit_price"]))
    return {
        "target_eur": target_eur,
        "combinations_in_grid": len(grid),
        "searched": "all" if len(grid) < eco.MAX_GRID else f"first {eco.MAX_GRID} only",
        "returned": min(limit, len(out)),
        "matching": len(out),
        "sheets": out[:limit],
    }


def levers(case, base_terms, std=None, estimate=None):
    """What each option of each non-price term costs the buyer, the other terms held as in
    `base_terms` (the supplier's standing sheet): EUR more than the cheapest option of that term.
    A term that costs us little may be worth much to the supplier - that is what a trade is made of.
    An option that breaks a must-have is marked: a deal on it scores 0."""
    std = clean(std)
    base = {k: v for k, v in clean(base_terms).items() if k in case["negotiable"]}
    if base.get("unit_price") is None:
        return {}
    out = {}
    for field in eco.fields(case):
        options = case.get("term_options", {}).get(field)
        if not options or len(options) < 2:
            continue
        costs = {}
        for option in options:
            e = evaluate(case, {**base, field: option}, std, estimate)
            key = json.dumps(option) if isinstance(option, dict | list) or option is None else str(option)
            if e["must_haves_ok"] is False:
                costs[key] = "breaks a must-have"
            elif e["total_eur"] is not None:
                costs[key] = e["total_eur"]
        numbers = [v for v in costs.values() if isinstance(v, int | float)]
        if len(numbers) < 2:
            continue
        low = min(numbers)
        out[field] = {k: (round(v - low, 2) if isinstance(v, int | float) else v) for k, v in costs.items()}
    return out


def _asked(case, msg, std, estimate):
    costs = [cost(case, ts.get("terms", ts), std, estimate) for ts in msg.get("term_sheets") or []]
    costs = [c for c in costs if c != INF]
    return min(costs) if costs else None


def movement(case, events, std=None, estimate=None):
    """How far each side has moved, in our cost units. For every message that carried term sheets,
    the cheapest of them for us. `exchanges` pairs each of our moves with the supplier's step that
    answered it: the supplier's pattern shows in how its step relates to ours."""
    ours = [
        (i, c)
        for i, m in enumerate(events)
        if m.get("from") == "buyer" and (c := _asked(case, m, std, estimate)) is not None
    ]
    theirs = [
        (i, c)
        for i, m in enumerate(events)
        if m.get("from") != "buyer" and (c := _asked(case, m, std, estimate)) is not None
    ]
    out = {"our_asks_eur": [round(c, 2) for _, c in ours], "supplier_offers_eur": [round(c, 2) for _, c in theirs]}
    if not theirs:
        return out
    now = theirs[-1][1]
    out["supplier_total_move_eur"] = round(theirs[0][1] - now, 2)
    exchanges, ask, offer, pending = [], None, None, None
    for m in events:
        c = _asked(case, m, std, estimate)
        if m.get("from") == "buyer":
            pending = {"our_move_eur": None if ask is None or c is None else round(c - ask, 2)}
            ask = c if c is not None else ask
        elif c is not None:
            if pending is not None and offer is not None:
                pending["its_step_eur"] = round(offer - c, 2)
                if pending["our_move_eur"] and pending["our_move_eur"] > 0.5:
                    pending["its_step_per_eur_of_our_move"] = round(
                        pending["its_step_eur"] / pending["our_move_eur"], 2
                    )
                elif pending["our_move_eur"] is None:
                    pending["note"] = "its answer to our first ask"
                exchanges.append(pending)
            offer, pending = c, None
    if exchanges:
        out["exchanges"] = exchanges
    if ours:
        last_i, last_c = ours[-1]
        before = [c for i, c in theirs if i < last_i]
        after = [c for i, c in theirs if i > last_i]
        if before and after:
            out["supplier_since_our_last_move_eur"] = round(before[-1] - after[-1], 2)
        if len(ours) > 1:
            out["our_last_move_eur"] = round(last_c - ours[-2][1], 2)
        out["gap_eur"] = round(now - last_c, 2)
        first_gap = theirs[0][1] - ours[0][1]
        if first_gap > 0:
            out["gap_at_our_first_ask_eur"] = round(first_gap, 2)
            out["gap_closed_by_supplier_pct"] = round(100 * (theirs[0][1] - now) / first_gap, 1)
            out["gap_closed_by_us_pct"] = round(100 * (last_c - ours[0][1]) / first_gap, 1)
    return out


def estimate_check(case, events, std=None, estimate=None):
    """Does the supplier's own counter-offer contradict our estimate of it? Under the estimate,
    what each of our last sheets and its counter are worth to the supplier per unit. If its counter
    is worth LESS to it than a sheet we offered, the estimate (its cost of money, what it gains
    from a term) is wrong somewhere - it would not refuse more for less. None when we hold no
    estimate or the exchange has not happened yet."""
    if not estimate:
        return None
    ours = next((m for m in reversed(events) if m.get("from") == "buyer" and m.get("term_sheets")), None)
    if ours is None:
        return None
    after = events[len(events) - 1 - events[::-1].index(ours) + 1 :]
    theirs = next((m for m in after if m.get("from") != "buyer" and m.get("term_sheets")), None)
    if theirs is None:
        return None
    try:
        offered = [supplier_value(case, clean(ts.get("terms", ts)), _est(estimate)) for ts in ours["term_sheets"]]
        counter = supplier_value(case, clean(theirs["term_sheets"][0].get("terms") or {}), _est(estimate))
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    best = max(offered)
    return {
        "value_to_supplier_of_our_best_sheet": round(best, 2),
        "value_to_supplier_of_its_counter": round(counter, 2),
        "contradicted": counter < best - 0.005,
        "meaning": (
            "its counter is worth less to it than what we offered, by our estimate: the estimate is wrong somewhere"
            if counter < best - 0.005
            else "consistent with our estimate"
        ),
    }
