"""Fit, per supplier, the full cost (and cost of money) that reproduce the arena's relationship charges
observed in our ended practice deals. Standard terms per supplier come from Codex's playbook."""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.expanduser("~/tacto/negotiation-arena-kit/starter-kit"))
from arena_kit.cost import RELATIONSHIP_GOALS, _years, closing_terms, relationship_cost, supplier_value  # noqa: E402

KIT = os.path.expanduser("~/tacto/negotiation-arena-kit/starter-kit")
facts = json.load(open(f"{KIT}/data/package/facts.json"))
cases = {c["case_id"]: c for c in json.load(open(os.path.expanduser("~/tacto/codex-work/arena-data/cases-practice.json")))}
pb = json.load(open(os.path.expanduser("~/tacto/codex-work/intel/generated/CASE_PLAYBOOK.json")))
print("cas relationnels :")
for cid, c in cases.items():
    b = c["buyer"]
    if b.get("category_goal") in RELATIONSHIP_GOALS:
        print(f"  {cid} {b['category_goal']} per_point={b.get('relationship_eur_per_point')} sustainable={b.get('sustainable_margin_pct')} buyer rate={b.get('interest_rate')} parts={c.get('parts')} volume={b.get('volume_per_year')}")


def should_cost(case):
    for part in case.get("parts", []):
        f = facts.get(f"cost:{part.split(':')[1]}") or {}
        if f.get("unit_cost") and f.get("price_unit", 1) == 1:
            return f["unit_cost"]
    return None


rows = {}
for f in sorted(glob.glob(os.path.expanduser("~/tacto/codex-work/arena-data/sessions/P*.json"))):
    d = json.load(open(f))
    s = d["session"]
    r = s.get("result") or {}
    if not r.get("deal") or not r.get("terms"):
        continue
    case = cases.get(s["case_id"])
    if not case or case["buyer"].get("category_goal") not in RELATIONSHIP_GOALS:
        continue
    rows.setdefault((s["case_id"], r["supplier_id"]), []).append((r["terms"], (r.get("cost_breakdown") or {}).get("relationship", 0.0), r["score"], r["c_deal"]))

for (cid, sid), deals in rows.items():
    case = cases[cid]
    b = case["buyer"]
    pm = (pb["cases"].get(cid, {}).get("suppliers", {}).get(sid) or {}).get("supplier_model") or {}
    std = (pm.get("supplier") or {}).get("standard")
    if not std:
        print("pas de std playbook pour", cid, sid)
        continue
    sc = should_cost(case)
    per_point, sustainable = b["relationship_eur_per_point"], b["sustainable_margin_pct"]
    print(f"\n== {cid} {sid} should-cost={sc} std={std} | Codex full_cost={pm['supplier'].get('full_cost'):.2f} rate={pm['supplier'].get('interest_rate'):.3f} | notre modèle full_cost={0.98 * sc if sc else float('nan'):.2f}")
    best = None
    for rate in [x / 200 for x in range(2, 61)]:  # 1 % .. 30 %
        fcs = []
        for t, charge, _, _ in deals:
            if charge <= 0:
                continue
            sup = {"standard": std, "interest_rate": rate, "full_cost": 0.0}
            tt = closing_terms(case, t, std)
            yrs = _years(case, tt)
            worth = supplier_value(case, tt, sup)
            soft = charge / (per_point * yrs)
            gap = (soft * 10) ** 0.5 if soft <= 2.5 else soft + 2.5
            margin = sustainable - gap
            fcs.append(worth * (1 - margin / 100))
        if not fcs:
            continue
        fcs.sort()
        for fc in fcs + [sum(fcs) / len(fcs)]:
            sup = {"standard": std, "interest_rate": rate, "full_cost": fc}
            err = sum((relationship_cost(case, t, std, sup) - charge) ** 2 for t, charge, _, _ in deals)
            if best is None or err < best[0]:
                best = (err, rate, fc, fcs)
    if not best:
        print("  aucune pénalité observée")
        continue
    err, rate, fc, fcs = best
    print(f"  ajusté : rate={rate:.3f} full_cost={fc:.2f} ratio/should-cost={fc / sc if sc else float('nan'):.4f} (estimations par accord {min(fcs):.2f}..{max(fcs):.2f}) rmse={(err / len(deals)) ** 0.5:,.0f} €")
    sup = {"standard": std, "interest_rate": rate, "full_cost": fc}
    ours = {"standard": std, "interest_rate": b.get("interest_rate", 0.08), "full_cost": 0.98 * sc} if sc else None
    cdx = pm["supplier"]
    for t, charge, score, c_deal in sorted(deals, key=lambda x: -x[2]):
        print(f"    prix={t['unit_price']:<7} pay={t['payment_days']:<3} {str(t.get('effective_date'))[:7]} lead={t.get('lead_time_days')} mois={t.get('contract_months')} idx={str(t.get('index_clause'))[:6]:<6} score={score:.3f} C={c_deal:,.0f} arène={charge:>8,.0f} ajusté={relationship_cost(case, t, std, sup):>8,.0f} nous={relationship_cost(case, t, std, ours) if ours else float('nan'):>8,.0f} codex={relationship_cost(case, t, std, cdx):>8,.0f}")
