"""Score grid of one case at a fixed price across two levers, using c_open and c_best of a played session.

Example (P01, session 360a06b60a033bda):
  uv run python analysis/grid.py case:P01 --price 138.55 --c-open 1153779.74 --c-best 1096815.78 \
      --rows effective_date --cols payment_days --std ppm_commitment=900 chargeback_eur_per_complaint=0
"""

import argparse

from _common import load_cases

from arena_kit.cost import score, total_cost

p = argparse.ArgumentParser()
p.add_argument("case_id")
p.add_argument("--price", type=float, required=True)
p.add_argument("--c-open", type=float, required=True)
p.add_argument("--c-best", type=float, required=True)
p.add_argument("--rows", required=True)
p.add_argument("--cols", required=True)
p.add_argument("--std", nargs="*", default=[], help="supplier standard terms, field=value")
a = p.parse_args()

case = next(c for c in load_cases() if c["case_id"] == a.case_id)
std = {k: float(v) for k, v in (s.split("=") for s in a.std)}
opts = case["term_options"]


def cost(price, r, c):
    return total_cost(case, {"unit_price": price, a.rows: r, a.cols: c}, std)


print(f"{a.case_id}: score at unit price {a.price} (rows {a.rows}, columns {a.cols})")
print(" " * 14 + "".join(f"{str(c):>9}" for c in opts[a.cols]))
for r in opts[a.rows]:
    print(f"{str(r):14}" + "".join(f"{score(a.c_open, cost(a.price, r, c), a.c_best):9.2f}" for c in opts[a.cols]))

print("\nUnit price that reaches c_best exactly (score 1.0):")
for r in opts[a.rows]:
    line = []
    for c in opts[a.cols]:
        lo, hi = a.price * 0.5, a.price * 1.5
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (lo, mid) if cost(mid, r, c) > a.c_best else (mid, hi)
        line.append(lo)
    print(f"{str(r):14}" + "".join(f"{x:9.2f}" for x in line))
