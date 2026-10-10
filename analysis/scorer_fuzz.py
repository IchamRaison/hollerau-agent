"""Scorer fuzz (A1): hunt anomalies in the published cost function, offline, no session.

Three passes over every case:
1. Enumerate the full option space (term_options cartesian product, must-haves respected)
   -> the true offline optimum C and its package.
2. Continuous scan of each numeric field far beyond its options -> monotonicity, sign
   inversions, kinks (the API may or may not enforce term_options; that is schema_fuzz's
   question, here we map what the scorer itself would pay).
3. Clamp analysis against every c_best we know from finished sessions.

Detectors: C below a known c_best; fields where C decreases without bound or in the
"wrong" direction; discontinuities; what exactly saturates the score.

Run: uv run python analysis/scorer_fuzz.py   (writes data/fuzz/scorer_fuzz.json)
"""

import itertools
import json
import math
import sys
from pathlib import Path

from _common import facts, load_cases, short

from arena_kit.cost import complete_offer, cost_breakdown, must_haves_ok, score, total_cost

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
OUT = Path(__file__).resolve().parent.parent / "data" / "fuzz"
OUT.mkdir(parents=True, exist_ok=True)

# c_best revealed by finished sessions (analysis/session_dump.py). Vault: P01 = 1,096,815.78.
KNOWN_CBEST = {"P01": 1_096_815.78}
FACTS = facts()


def ref_price(case):
    b = case["buyer"]
    asked = (FACTS.get(case.get("trigger_doc") or "") or {}).get("asked_price")
    alt = ((b.get("alternative") or {}).get("terms") or {}).get("unit_price")
    return asked or b.get("current_unit_price") or alt or b["fallback_unit_price"]


def enumerate_optimum(case):
    """Full option-space search for the offline min C."""
    price = ref_price(case)
    base = complete_offer(case, {"unit_price": price})
    levers = [f for f in case["negotiable"] if f != "unit_price" and case.get("term_options", {}).get(f)]
    space = 1
    for f in levers:
        space *= len(case["term_options"][f])
    combos = []
    if space <= 60_000:
        for v in itertools.product(*(case["term_options"][f] for f in levers)):
            combos.append(dict(zip(levers, v, strict=True)))
    else:  # corners + singles + pairs, exhaustive would be noise anyway
        for v in itertools.product(*( [case["term_options"][f][0], case["term_options"][f][-1]] for f in levers)):
            combos.append(dict(zip(levers, v, strict=True)))
    best, best_c = None, math.inf
    for x in combos:
        sheet = {**base, **x}
        if not must_haves_ok(case, sheet):
            continue
        c = total_cost(case, sheet)
        if c < best_c:
            best, best_c = sheet, c
    return base, best, best_c, space


def scan_field(case, base, field, lo, hi, n=161):
    """C as a function of one field, others frozen at base. Returns samples + anomalies."""
    xs, ys, anomalies = [], [], []
    for i in range(n):
        v = lo + (hi - lo) * i / (n - 1)
        if field == "effective_date":
            v = base[field]  # dates: scanned separately below
            break
        sheet = {**base, field: round(v, 4)}
        try:
            y = total_cost(case, sheet)
        except Exception:
            continue
        xs.append(v)
        ys.append(y)
    if len(ys) < 3:
        return xs, ys, anomalies
    # monotonicity + inversions: slope sign over the traversal
    slopes = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(len(ys) - 1) if xs[i + 1] > xs[i]]
    signs = {math.copysign(1, s) for s in slopes if abs(s) > 1e-9}
    if len(signs) > 1:  # non-monotone: there is an interior optimum or a kink
        k = min(range(len(ys)), key=lambda i: ys[i])
        anomalies.append(f"{field}: non-monotone, min at {xs[k]:.2f} (C={ys[k]:.0f}), ends C={ys[-1]:.0f}")
    # kinks: biggest slope change
    if len(slopes) > 2:
        d2 = [abs(slopes[i + 1] - slopes[i]) for i in range(len(slopes) - 1)]
        j = max(range(len(d2)), key=lambda i: d2[i])
        if d2[j] > 1e-6 and slopes[j] * slopes[j + 1] <= 0:
            anomalies.append(f"{field}: kink at {xs[j + 1]:.2f} slope {slopes[j]:+.1f} -> {slopes[j + 1]:+.1f}")
    # free wins: C at the extreme away from the options beats C at the base
    if ys[-1] < ys[0] - 0.01 and xs[-1] > xs[0]:
        anomalies.append(f"{field}: pushing to {xs[-1]:.0f} LOWERS C by {ys[0] - ys[-1]:.0f} vs base {xs[0]:.0f}")
    if ys[0] < ys[-1] - 0.01 and xs[0] < xs[-1]:
        anomalies.append(f"{field}: pushing to {xs[0]:.0f} LOWERS C by {ys[-1] - ys[0]:.0f} vs base {xs[-1]:.0f}")
    return xs, ys, anomalies


RANGES = {  # far beyond term_options: what the scorer itself would pay
    "payment_days": (0, 365),
    "lead_time_days": (1, 120),
    "volume_per_year": (1, 60_000),
    "contract_months": (1, 60),
    "ppm_commitment": (0, 5_000),
    "chargeback_eur_per_complaint": (0, 50_000),
    "tooling_eur": (0, 200_000),
    "unit_price": (-50, 500),
}


def main():
    report = []
    for case in load_cases():
        cid = short(case)
        base, best, best_c, space = enumerate_optimum(case)
        entry = {"case": cid, "option_space": space, "best_C": round(best_c, 2), "best_package": best}
        # 1. below known c_best?
        if cid in KNOWN_CBEST:
            cb = KNOWN_CBEST[cid]
            entry["known_c_best"] = cb
            entry["offline_min_minus_cbest"] = round(best_c - cb, 2)
            entry["score_at_offline_min"] = score(
                total_cost(case, {**complete_offer(case, {"unit_price": ref_price(case)})}), best_c, cb
            )
        # 2. continuous scans
        anomalies = []
        for f in RANGES:
            if f not in case["negotiable"] and f not in case.get("fixed_terms", {}):
                continue
            if f == "unit_price":
                continue
            _, _, a = scan_field(case, base, f, *RANGES[f])
            anomalies += a
        # 3. effective date scan: later date = fewer units at the new price
        opts = case.get("term_options", {}).get("effective_date")
        if opts:
            for d in opts:
                c = total_cost(case, {**base, "effective_date": d})
                anomalies.append(f"effective_date {d}: C={c:,.0f}")
        entry["scan_anomalies"] = anomalies
        # 4. negative/zero price clamp
        c0 = total_cost(case, {**base, "unit_price": 0.0})
        entry["C_at_price_zero"] = round(c0, 2)
        cneg = total_cost(case, {**base, "unit_price": -10.0})
        entry["C_at_price_minus10"] = round(cneg, 2)
        entry["score_clamps_to_1"] = cneg < 0 or c0 < entry.get("known_c_best", math.inf)
        report.append(entry)

    (OUT / "scorer_fuzz.json").write_text(json.dumps(report, indent=1, default=str))

    print("| Case | Opt. C | Known c_best | Min - c_best | Price<0 C | Flags |")
    print("|---|---|---|---|---|---|")
    for e in report:
        flags = []
        if e.get("offline_min_minus_cbest") is not None and e["offline_min_minus_cbest"] < -0.01:
            flags.append(f"BELOW c_best by {-e['offline_min_minus_cbest']:,.0f}")
        if e.get("score_clamps_to_1"):
            flags.append("price<=0 clamps score to 1")
        n_anom = len(e["scan_anomalies"])
        if n_anom:
            flags.append(f"{n_anom} scan notes")
        print(f"| {e['case']} | {e['best_C']:,.0f} | {e.get('known_c_best', '-')} | "
              f"{e.get('offline_min_minus_cbest', '-')} | {e['C_at_price_minus10']:,.0f} | {'; '.join(flags) or 'clean'} |")
    print(f"\nFull detail: data/fuzz/scorer_fuzz.json ({len(report)} cases)")


main()
