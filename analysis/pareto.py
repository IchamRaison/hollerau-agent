"""Pareto solver (A5): the buyer-optimal package at supplier indifference, offline.

Model: a supplier accepts a package when it is worth at least as much as its standing
opening offer (the realistic first-order acceptance boundary; its hard floor is its full
cost, below this). supplier_value() is the published exchange rate between terms; we
bisect the unit price that holds the supplier exactly at the value of its opening offer,
for every allowed package, then minimise OUR total_cost.

Anchors: the opening offer from a recorded session when we have one (P01: 138.55 EUR,
30 days, effect 2026-11-01), else the trigger-letter price at case standard. The implied
interest rate that aligns the indifference optimum with the revealed c_best is the fitted
parameter - a law (rate per archetype), not an instance.

Run: uv run python analysis/pareto.py [case:P01]
"""

import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import facts, load_cases  # noqa: E402

from arena_kit.cost import complete_offer, must_haves_ok, supplier_value, total_cost  # noqa: E402

FACTS = facts()
KNOWN_CBEST = {"case:P01": 1_096_815.78}


def ref_price(case):
    b = case["buyer"]
    asked = (FACTS.get(case.get("trigger_doc") or "") or {}).get("asked_price")
    alt = ((b.get("alternative") or {}).get("terms") or {}).get("unit_price")
    return asked or b.get("current_unit_price") or alt or b["fallback_unit_price"]


def standard_from_case(case):
    std = {}
    for f in case["negotiable"][1:]:
        o = case.get("term_options", {}).get(f)
        std[f] = o[0] if o else (case.get("fixed_terms", {}) or {}).get(f)
    return std


def opening_offer(session_file):
    """The supplier's opening terms from a recorded session, if we have one."""
    if session_file and Path(session_file).exists():
        sess = json.loads(Path(session_file).read_text())
        threads = sess.get("threads") or sess.get("case", {}).get("threads") or {}
        for th in (threads.values() if isinstance(threads, dict) else threads):
            for m in (th or {}).get("messages", []):
                if m.get("term_sheets"):
                    t = dict(m["term_sheets"][0].get("terms", {}))
                    if t.get("unit_price"):
                        return t
    return None


def solve(case, anchor, supplier_extra=None, verbose=True):
    price0 = ref_price(case)
    base = complete_offer(case, {"unit_price": price0})
    std = standard_from_case(case)
    extra = supplier_extra or {}
    anchor_terms = {**std, **{k: v for k, v in anchor.items() if k != "unit_price"}, "unit_price": anchor["unit_price"]}

    levers = [f for f in case["negotiable"] if f != "unit_price" and case.get("term_options", {}).get(f)]
    combos = [dict(zip(levers, v, strict=True)) for v in itertools.product(*(case["term_options"][f] for f in levers))]
    ok = [x for x in combos if must_haves_ok(case, {**base, **x})]

    def best_rows(rate):
        sup = {"standard": std, "interest_rate": rate, "ppm": std.get("ppm_commitment") or 0, **extra}
        anchor_value = supplier_value(case, anchor_terms, sup)
        rows = []
        for x in ok:
            sheet = {**base, **x}
            lo, hi = 0.01, max(price0, anchor["unit_price"]) * 1.5
            for _ in range(44):  # supplier_value is increasing in unit_price
                mid = (lo + hi) / 2
                if supplier_value(case, {**sheet, "unit_price": mid}, sup) >= anchor_value:
                    hi = mid
                else:
                    lo = mid
            p = round(hi, 2)
            rows.append((total_cost(case, {**sheet, "unit_price": p}), p, x))
        rows.sort()
        return rows

    if verbose:
        print(f"case {case['case_id']}  anchor (opening): {anchor_terms}")
    return best_rows


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else "case:P01"
    case = next(c for c in load_cases() if c["case_id"] == want)
    sess = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sessions" / "P01-naive.json"
    opening = opening_offer(sess) or {"unit_price": ref_price(case)}

    # Two anchors, both reported honestly:
    #  - opening: its first offer (conservative; the real supplier concedes below it)
    #  - floor: the observed concession limit (P01: ~133.5 EUR at Nov/60, std payment 30 from the quote PDF)
    floor = {"effective_date": "2026-11-01", "payment_days": 60, "unit_price": 133.5}
    std30 = {"payment_days": 30}

    c_best = KNOWN_CBEST.get(want)
    report = {"opening": [], "floor": []}
    print(f"case {want}  c_best {c_best:,.2f}" if c_best else f"case {want}")
    for label, anchor, extra in (("opening", opening, None), ("floor", floor, std30)):
        best_rows = solve(case, anchor, supplier_extra=extra, verbose=False)
        print(f"\nanchor={label} {anchor}")
        print("rate   C at indifference   price   gap vs c_best   best terms")
        for rate in (0.02, 0.04, 0.06, 0.08, 0.12):
            c, p, x = best_rows(rate)[0]
            gap = (c - c_best) / c_best * 100 if c_best else float("nan")
            print(f"{rate:4.0%}  {c:>12,.0f}  {p:7.2f}  {gap:+6.2f} %  {x}")
            report[label].append({"rate": rate, "C": c, "price": p, "terms": x,
                                  "gap_pct": round(gap, 3) if c_best else None})
        if label == "floor":
            rows = best_rows(0.04)
            print("top-3 packages at 4 % (C, indifference price, terms):")
            for c, p, x in rows[:3]:
                print(f"  {c:>12,.0f}  {p:7.2f}  {x}")

    out = Path(__file__).resolve().parent.parent / "data" / "fuzz"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"pareto_{want.replace(':', '_')}.json").write_text(json.dumps(report, indent=1, default=str))
    if c_best:
        g_open = min(abs(r["gap_pct"]) for r in report["opening"])
        g_floor = min(abs(r["gap_pct"]) for r in report["floor"])
        print(f"\ncriterion (<2 % vs c_best): opening anchor {g_open:+.2f} % "
              f"({'PASS' if g_open < 2 else 'FAIL'}), floor anchor {g_floor:+.2f} % "
              f"({'PASS' if g_floor < 2 else 'FAIL'})")
        print("note: the floor anchor's two parameters (floor price, cash rate) are exactly what "
              "Belief.update estimates online; the opening anchor needs no estimation but is conservative.")


main()
