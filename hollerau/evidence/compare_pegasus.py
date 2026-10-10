"""Offline comparison of the economics lane with Pegasus (`hollerau/pegasus/`) on the 19 practice cases. No session.

    PYTHONDONTWRITEBYTECODE=1 uv run --offline python -m hollerau.evidence.compare_pegasus

Economics: both best packages are priced at the same unit price (the letter's asked price, else the current price:
our lever price, D3) and costed with the same `arena_kit.cost.total_cost` on a complete term sheet. Pegasus has no
lever ranking: for each of our levers we show the value Pegasus picks and what that choice costs against ours.

Claims: Pegasus candidates (`Claims.candidates`, per supplier and part, at the same price) are turned into `Claim`s
(family from the ID prefix, figure read from their sentence) and run through our `check()`, which replicates the
arena's figure check - not its relevance judgement (`irrelevant`). Each ID counts once per case on both sides.
"""

import json
import logging
import math
import re
from pathlib import Path

from arena_kit.cost import complete_offer, must_haves_ok, total_cost
from hollerau.contracts import Claim
from hollerau.pegasus import claims as peg_claims
from hollerau.pegasus import economics as peg_econ

from .compile import compile_evidence
from .economics import compile_case
from .facts import check, facts_of, load_package

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "tests" / "fixtures" / "cases" / "practice.json"
TIE_EUR = 0.01

FAMILY = {
    "idx": "index",
    "doc": "notice",
    "ctr": "notice",
    "cost": "forecast_cost_news",
    "fc": "forecast_cost_news",
    "sc": "scorecard",
    "quote": "quote",
    "offer": "quote",
    "po": "orders",
    "news": "forecast_cost_news",
}
FIGURES = [  # (family, ID prefix, regex on the sentence, unit)
    ("index", "idx", r"changed (-?[\d.]+)%", "%"),
    ("notice", "doc", r"gives (\d+) days", "days"),
    ("forecast_cost_news", "cost", r"is ([\d.]+) EUR", "EUR"),
    ("forecast_cost_news", "fc", r"up ([\d.]+)%", "%"),
    ("scorecard", "sc", r"delivery was ([\d.]+)%", "%"),
    ("scorecard", "sc", r"quality was ([\d.]+) ppm", "ppm"),
]


def as_claim(candidate: dict) -> Claim:
    """A Pegasus candidate as a `Claim`: family from its first ID, figure and unit from its sentence."""
    refs, text = candidate["refs"], candidate["sentence"]
    prefix = refs[0].split(":", 1)[0]
    for family, pre, pattern, unit in FIGURES:
        if prefix == pre and (m := re.search(pattern, text)):
            return Claim(family, refs, float(m.group(1)), unit, text, "price")
    return Claim(FAMILY.get(prefix, prefix), refs, None, "", text, "price")


def pegasus_claims(case: dict, data, price: float) -> list[Claim]:
    """Every Pegasus candidate of the case, each ID once (first come, as Pegasus would send them)."""
    gen, out, seen = peg_claims.Claims(case, data), [], set()
    for supplier in case["suppliers"]:
        for part in case["parts"]:
            for c in gen.candidates(supplier, part, price):
                if seen & set(c["refs"]):
                    continue
                seen |= set(c["refs"])
                out.append(as_claim(c))
    return out


def c_of(case: dict, package: dict, price: float) -> float:
    return total_cost(case, complete_offer(case, {**package, "unit_price": price}))


def compare_case(case: dict, data) -> dict:
    econ = compile_case(case, data=data)
    price = econ.reference_price
    ours = econ.best_package
    ranked = peg_econ.structures(case, complete_offer(case, {"unit_price": price}), {})
    theirs = ranked[0][1] if ranked else {}
    row = {
        "case": case["case_id"].split(":")[1],
        "price": price,
        "c_ours": c_of(case, ours, price),
        "c_peg": c_of(case, theirs, price) if theirs else math.inf,
        "ok_ours": must_haves_ok(case, complete_offer(case, {**ours, "unit_price": price})),
        "ok_peg": bool(theirs) and must_haves_ok(case, complete_offer(case, {**theirs, "unit_price": price})),
        "diff_fields": sorted(f for f in ours if theirs.get(f) != ours.get(f)),
        "levers": [],
    }
    for lv in econ.levers:
        picked = theirs.get(lv.field)
        loss = c_of(case, {**ours, lv.field: picked}, price) - c_of(case, ours, price) if theirs else math.nan
        row["levers"].append((lv.field, lv.cost_of_forgetting_eur, picked == lv.best, round(loss, 2)))
    facts = facts_of(case, data)
    mine = compile_evidence(case, data)
    peg = pegasus_claims(case, data, price)
    row |= {
        "n_ours": len(mine),
        "fam_ours": sorted({c.family for c in mine}),
        "n_peg": len(peg),
        "ok_peg_n": sum(check(c, facts) for c in peg),
        "fam_peg": sorted({c.family for c in peg}),
        "peg_failed": [c.ids for c in peg if not check(c, facts)],
        "only_ours": sorted({i for c in mine for i in c.ids} - {i for c in peg for i in c.ids}),
        "only_peg": sorted({i for c in peg if check(c, facts) for i in c.ids} - {i for c in mine for i in c.ids}),
    }
    return row


def winner(a: float, b: float) -> str:
    if abs(a - b) <= TIE_EUR or (math.isinf(a) and math.isinf(b)):
        return "="
    return "ours" if a < b else "pegasus"


def report(rows: list[dict]) -> str:
    lines = [
        "| Cas | Prix | C ours | C pegasus | Δ (peg − ours) | Mieux | Must-haves o/p | Champs différents | "
        "Leviers où Pegasus ≠ notre best (coût) | Claims ours (familles) | Claims peg vérifiés / total (familles) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        missed = [f"{f} ({loss:,.0f} €)" for f, _, same, loss in r["levers"] if not same]
        lines.append(
            f"| {r['case']} | {r['price']:.2f} | {r['c_ours']:,.2f} | {r['c_peg']:,.2f} | "
            f"{r['c_peg'] - r['c_ours']:+,.2f} | {winner(r['c_ours'], r['c_peg'])} | "
            f"{'✓' if r['ok_ours'] else '✗'}/{'✓' if r['ok_peg'] else '✗'} | {', '.join(r['diff_fields']) or '-'} | "
            f"{', '.join(missed) or '-'} | {r['n_ours']} ({', '.join(r['fam_ours']) or '-'}) | "
            f"{r['ok_peg_n']} / {r['n_peg']} ({', '.join(r['fam_peg']) or '-'}) |"
        )
    w = [winner(r["c_ours"], r["c_peg"]) for r in rows]
    gap = sum(r["c_peg"] - r["c_ours"] for r in rows if math.isfinite(r["c_peg"]))
    ours_ok = sum(r["n_ours"] for r in rows)
    peg_ok = sum(r["ok_peg_n"] for r in rows)
    peg_all = sum(r["n_peg"] for r in rows)
    more = [r["case"] for r in rows if r["n_ours"] > r["ok_peg_n"]]
    fewer = [r["case"] for r in rows if r["n_ours"] < r["ok_peg_n"]]
    failed = [f"{r['case']}: {', '.join('+'.join(i) for i in r['peg_failed'])}" for r in rows if r["peg_failed"]]
    lines += [
        "",
        "## Résumé",
        "",
        f"- **C le plus bas** : ours {w.count('ours')}, Pegasus {w.count('pegasus')}, égalité {w.count('=')} "
        f"(sur {len(rows)} cas). Écart cumulé (Pegasus − ours) : {gap:+,.2f} €.",
        f"- **Claims vérifiables** (`check()`, chiffres seulement) : ours {ours_ok}, Pegasus {peg_ok} sur {peg_all} "
        f"candidats.",
        f"- Plus de claims vérifiables chez nous : {', '.join(more) or '-'} ; "
        f"chez Pegasus : {', '.join(fewer) or '-'}.",
        f"- Candidats Pegasus qui échouent à `check()` : {'; '.join(failed) or 'aucun'}.",
        "",
        "## Où chacun est meilleur (IDs vérifiables cités par l'un et pas par l'autre)",
        "",
    ]
    for r in rows:
        if r["only_ours"] or r["only_peg"]:
            lines.append(
                f"- {r['case']} : seulement ours {', '.join(r['only_ours']) or '-'} ; "
                f"seulement Pegasus {', '.join(r['only_peg']) or '-'}"
            )
    return "\n".join(lines)


def main() -> None:
    logging.disable(logging.WARNING)
    data = load_package()
    rows = [compare_case(c, data) for c in json.loads(CASES.read_text())]
    print(report(rows))


if __name__ == "__main__":
    main()
