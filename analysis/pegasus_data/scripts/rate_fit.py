"""Fine fit of each supplier's cost of money (full_cost fixed at should-cost / 1.02) on the arena's observed
relationship charges; compare with Codex's cash-equivalence inference; exact U bottoms per structure."""
import glob
import json
import os

from arena_kit.cost import RELATIONSHIP_GOALS, closing_terms, relationship_cost
from pegasus import economics as eco

cases = {c["case_id"]: c for c in json.load(open(os.path.expanduser("~/tacto/codex-work/arena-data/cases-practice.json")))}
pb = json.load(open(os.path.expanduser("~/tacto/codex-work/intel/generated/CASE_PLAYBOOK.json")))
facts = json.load(open("data/package/facts.json"))
SESS = os.path.expanduser("~/tacto/codex-work/arena-data/sessions")


def deals_of(cid):
    out = []
    for f in sorted(glob.glob(f"{SESS}/{cid[5:]}-*.json")):
        d = json.load(open(f))
        r = d["session"].get("result") or {}
        if r.get("deal") and r.get("terms"):
            out.append((r["terms"], (r.get("cost_breakdown") or {}).get("relationship", 0.0), r["score"], d["session"]["opening"], r))
    return out


fitted = {}
for cid in ("case:P01", "case:P02", "case:P03"):
    case = cases[cid]
    sid = case["suppliers"][0]
    pm = pb["cases"][cid]["suppliers"][sid]["supplier_model"]
    std = dict(pm["supplier"]["standard"])
    sc = facts[f"cost:{case['parts'][0].split(':')[1]}"]["unit_cost"]
    deals = deals_of(cid)
    surface = []
    for i in range(300, 1600):
        rate = i / 10000
        sup = {"standard": std, "interest_rate": rate, "full_cost": sc / 1.02}
        err = sum((relationship_cost(case, t, std, sup) - ch) ** 2 for t, ch, _, _, _ in deals)
        surface.append(((err / len(deals)) ** 0.5, rate))
    surface.sort()
    fitted[cid] = surface[0][1]
    within = [r for e, r in surface if e <= surface[0][0] * 2 + 20]
    print(f"{cid} {sid}: taux ajusté {surface[0][1]:.4f} (rmse {surface[0][0]:,.0f} €) ; plage compatible {min(within):.3f}..{max(within):.3f} ; Codex {pm['cash_rate_assumption']['value']:.4f} ({pm['cash_rate_assumption']['reason'][:60]})")
    obs = pm.get("cash_equivalence_observations") or []
    for o in obs[:6]:
        print("    obs:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in o.items() if k in ("rate", "old_price", "old_payment", "new_price", "new_payment", "source", "round")})

print("\n=== creux exacts par structure (full_cost = should-cost/1.02, taux ajusté) vs notre modèle (0.98, 8 %) ===")
for cid, rate in fitted.items():
    case = cases[cid]
    sid = case["suppliers"][0]
    deals = deals_of(cid)
    op = deals[-1][3][sid]
    res = deals[-1][4]
    std = dict(pb["cases"][cid]["suppliers"][sid]["supplier_model"]["supplier"]["standard"])
    sc = facts[f"cost:{case['parts'][0].split(':')[1]}"]["unit_cost"]
    ours = eco.supplier_model(case, std, op["terms"]["unit_price"], facts)
    exact = {"standard": std, "interest_rate": rate, "full_cost": sc / 1.02}
    structs = eco.structures(case, op["terms"], std)
    structs = [next(x for x in s if isinstance(x, dict)) if isinstance(s, tuple) else s for s in structs]
    print(f"\n{cid} ouverture {op['terms']['unit_price']} | c_open={res['c_open']:,.0f} c_best={res['c_best']:,.0f} | {len(structs)} structures")
    for label, sup in (("exact", exact), ("nôtre", ours)):
        s2 = {**std, "_supplier": sup}
        rows = []
        for s in structs:
            hi = 2 * op["terms"]["unit_price"]
            p = eco.cheapest_price(case, s, s2, 0.01, hi)
            t = eco.sheet(case, s, p)
            c = eco.cost(case, t, s2)
            c_true = eco.cost(case, t, {**std, "_supplier": exact})
            rows.append((c, p, c_true, {k: (str(v)[:7] if v is not None else None) for k, v in s.items() if k in ("payment_days", "effective_date", "contract_months", "lead_time_days", "index_clause", "incoterm")}))
        rows.sort(key=lambda r: r[0])
        print(f"  [{label}] 4 meilleurs creux :")
        for c, p, c_true, s in rows[:4]:
            print(f"     C_modèle={c:,.0f} C_vrai={c_true:,.0f} (score si accepté {(res['c_open'] - c_true) / (res['c_open'] - res['c_best']):.3f}) prix={p} {s}")
