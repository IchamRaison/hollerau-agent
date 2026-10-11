"""X10 (hors ligne): quand un fournisseur propose plusieurs feuilles dans le même mail, combien
de points de score sépare la meilleure de la pire pour nous ? Mesure le gain disponible en
choisissant la structure, avec les taux d'échange réels des bots (pas un modèle)."""
import json, sys, glob, statistics as st
from collections import defaultdict
REPO = sys.argv[1]
sys.path.insert(0, REPO)
from arena_kit.cost import total_cost, must_haves_ok

cases = {}
for name in ("practice", "sandbox"):
    d = json.load(open(f"{REPO}/analysis/pegasus_data/cases-{name}.json"))
    d = d if isinstance(d, list) else d.get("cases", d)
    for c in (d.values() if isinstance(d, dict) else d):
        cases[c["case_id"]] = c

rows = defaultdict(list)      # case -> [(spread_pts, main_is_best, n_sheets, gain_pts)]
msgs = defaultdict(int); with_alt = defaultdict(int); sessions = defaultdict(int)
for path in sorted(glob.glob(f"{REPO}/analysis/pegasus_data/sessions/*.json")):
    d = json.load(open(path)); s = d.get("session") or d
    case = cases.get(s.get("case_id")); r = s.get("result") or {}
    if not case or not r.get("c_open") or not r.get("c_best"):
        continue
    span = r["c_open"] - r["c_best"]
    if span <= 1:
        continue
    cid = s["case_id"].split(":")[-1]; sessions[cid] += 1
    for e in r.get("trace") or []:
        if e.get("actor") == "buyer":
            continue
        m = e.get("move") or {}
        sheets = []
        if (m.get("terms") or {}).get("unit_price") is not None:
            sheets.append(m["terms"])
        sheets += [a["terms"] for a in m.get("alternatives") or [] if (a.get("terms") or {}).get("unit_price") is not None]
        if not sheets:
            continue
        msgs[cid] += 1
        if len(sheets) < 2:
            continue
        with_alt[cid] += 1
        costs = []
        for t in sheets:
            try:
                if must_haves_ok(case, t):
                    costs.append(total_cost(case, t))
            except Exception:
                pass
        if len(costs) < 2:
            continue
        spread = (max(costs) - min(costs)) / span
        gain_vs_main = (costs[0] - min(costs)) / span if len(costs) == len(sheets) else None
        rows[cid].append((spread, costs[0] == min(costs), len(sheets), gain_vs_main))

print(f"{'cas':5} {'sess':>4} {'mails':>5} {'avec alt.':>9} {'écart médian':>12} {'écart max':>9} {'principale = meilleure':>22} {'gain médian si on prend la meilleure':>36}")
tot = []
for cid in sorted(rows, key=lambda x: (x[0], int(x[1:]))):
    sp = [x[0] for x in rows[cid]]; best = sum(1 for x in rows[cid] if x[1]); g = [x[3] for x in rows[cid] if x[3] is not None]
    tot += sp
    print(f"{cid:5} {sessions[cid]:4d} {msgs[cid]:5d} {with_alt[cid]:9d} {st.median(sp):12.3f} {max(sp):9.3f} {best:10d}/{len(sp):<10d} {st.median(g) if g else float('nan'):20.3f}")
for cid in sorted(set(msgs) - set(rows)):
    print(f"{cid:5} {sessions[cid]:4d} {msgs[cid]:5d} {with_alt[cid]:9d}   (aucun mail à plusieurs feuilles évaluables)")
print("tous cas: n=%d médiane=%.3f p90=%.3f" % (len(tot), st.median(tot), sorted(tot)[int(len(tot)*0.9)]))
