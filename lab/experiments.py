"""The first lab experiments, on the sandbox case D01 (off quota). See the vault note Expériences, L1-L4 and L10.

  uv run python -m lab.experiments list                # what each experiment opens
  HOLLERAU_VALIDATED="..." uv run python -m lab.experiments L1 [--case case:D01]

Scripts send neutral, identical wording so that only the numbers vary.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor

from arena_kit.cli import load_env
from hollerau.sessions import is_local, require_validation

from .harness import run, summary

BODY = "Thank you for your offer. Please find our proposal in the attached terms."
MAX_PARALLEL = 6  # the key allows 10 open sessions for the whole team


def offer(price_of, **terms):
    """A step: one term sheet at price_of(ctx), other terms as the supplier's unless given."""

    def step(ctx):
        return {
            "subject": ctx.case["title"],
            "body": BODY,
            "term_sheets": [{"terms": ctx.sheet(price_of(ctx), **terms)}],
        }

    return step


def ladder(start, step_pct, rounds):
    """Start at `start` x opening price, then add step_pct % of the opening price each round."""
    return [offer(lambda c, i=i: c.opening_price * (start + i * step_pct / 100)) for i in range(rounds)]


def plans(case):
    opts = case.get("term_options", {})
    levers = [(f, v) for f in case["negotiable"] if f != "unit_price" for v in opts.get(f, [])]
    low = [offer(lambda c: c.opening_price * 0.90)]
    return {
        "L1": [(f"L1-same-{i}", ladder(0.90, 1.0, 6)) for i in (1, 2, 3)],
        "L2": [
            ("L2-hold", ladder(0.90, 0.0, 6)),
            ("L2-small", ladder(0.90, 0.3, 6)),
            ("L2-big", ladder(0.90, 2.0, 5)),
            (
                "L2-shrinking",
                [offer(lambda c, x=x: c.opening_price * x) for x in (0.90, 0.94, 0.96, 0.97, 0.975, 0.9775)],
            ),
        ],
        "L3": [("L3-control", low)]
        + [(f"L3-{f}-{v}", [offer(lambda c: c.opening_price * 0.90, **{f: v})]) for f, v in levers],
        "L4": [(f"L4-three-{f}", [three_sheets(f, opts[f])]) for f in case["negotiable"] if len(opts.get(f, [])) >= 2][
            :3
        ],
    }


def three_sheets(field, values):
    def step(ctx):
        vals = [values[0], values[len(values) // 2], values[-1]]
        sheets = [{"terms": ctx.sheet(ctx.opening_price * 0.90, **{field: v})} for v in dict.fromkeys(vals)]
        return {"subject": ctx.case["title"], "body": BODY, "term_sheets": sheets}

    return step


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name", choices=["list", "L1", "L2", "L3", "L4"])
    p.add_argument("--case", default="case:D01")
    a = p.parse_args()
    load_env()
    from arena_kit import ArenaClient

    client = ArenaClient()
    set_name = "practice" if is_local() or a.case.startswith("case:P") else "sandbox"
    case = next(c for c in client.cases(set_name) if c["case_id"] == a.case)
    todo = plans(case)
    if a.name == "list":
        for k, v in todo.items():
            print(k, f"{len(v)} session(s):", ", ".join(label for label, _ in v))
        return
    runs = todo[a.name]
    require_validation(f"lab {a.name} on {a.case}", len(runs), quota=a.case.startswith("case:P"))
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        for rec in pool.map(lambda r: run(a.case, r[1], f"{a.case.split(':')[1]}-{r[0]}", client=client), runs):
            print(summary(rec))


if __name__ == "__main__":
    main()
