"""X14 : quand tient-il, quand passe-t-il en offre finale, quand part-il ? Par fournisseur."""
import json, statistics as st
from pathlib import Path
from collections import defaultdict, Counter
T = json.load(open(Path(__file__).with_name("threads.json")))
R = defaultdict(list)
for t in T:
    C0 = next((e["cost"] for e in t["events"] if e["who"] == "S" and e["cost"] is not None), None)
    if not C0:
        continue
    prev = None; ask = None; last_ask = None; k = 0; pending = None
    for e in t["events"]:
        if e["who"] == "B":
            cs = [s["cost"] for s in e["sheets"] if s["cost"] is not None]
            pending = dict(cost=min(cs) if cs else None, n=len(e["sheets"]), action=e.get("action"), claims=len(e["claims"]))
            continue
        if pending is None:
            prev = e if e["cost"] is not None else prev
            continue
        k += 1
        move = None
        if pending["cost"] is not None and last_ask is not None:
            move = (pending["cost"] - last_ask) / C0          # > 0 : nous concédons
        gap = (prev["cost"] - pending["cost"]) / C0 if (prev and prev["cost"] is not None and pending["cost"] is not None) else None
        step = (prev["cost"] - e["cost"]) / C0 if (prev and prev["cost"] is not None and e["cost"] is not None) else None
        R[(t["case"], t["supplier"])].append(dict(k=k, move=move, gap=gap, step=step, status=e["status"], call=e["call"],
            prev=prev["status"] if prev else None, n=pending["n"], first=last_ask is None, notes=e["notes"],
            ver=sum(1 for c in e["claim_results"] if c == "verified"), role=t["role"]))
        if pending["cost"] is not None:
            last_ask = pending["cost"]
        if e["cost"] is not None:
            prev = e
        pending = None

def bucket(m):
    if m is None: return "sans feuille"
    if m <= 1e-6: return "aucun (<=0)"
    if m < 0.002: return "<0,2 %"
    if m < 0.01: return "0,2-1 %"
    if m < 0.03: return "1-3 %"
    return ">3 %"
order = ["sans feuille", "aucun (<=0)", "<0,2 %", "0,2-1 %", "1-3 %", ">3 %"]
for key in sorted(R):
    rows = R[key]
    print(f"\n=== {key[0]}/{key[1]} ({rows[0]['role']}) {len(rows)} réponses")
    later = [r for r in rows if not r["first"] and r["prev"] == "open"]
    by = defaultdict(list)
    for r in later:
        by[bucket(r["move"])].append(r)
    print("  notre mouvement (part de son devis, en coût) -> part des réponses où il fait un pas ; pas médian ; statut")
    for b in order:
        v = by.get(b)
        if not v: continue
        steps = [r["step"] for r in v if r["step"] is not None]
        pos = [s for s in steps if s > 1e-6]
        print(f"    {b:13} n={len(v):3}  bouge {len(pos)/max(len(steps),1):4.0%}  pas méd {100*st.median(pos) if pos else 0:5.2f} %  statuts {dict(Counter(r['status'] for r in v))}")
    print("  statut par numéro de réponse :", "  ".join(f"k{k}:{dict(Counter(r['status'][:3] for r in rows if r['k']==k))}" for k in range(1, 9) if any(r['k']==k for r in rows)))
    fin = [r for r in rows if r["prev"] == "final_offer"]
    if fin:
        print("  après son offre finale : ", dict(Counter((bucket(r['move']) if r['gap'] is None or r['gap'] > 1e-6 else 'nous reprenons son offre', r['status']) for r in fin)))
    first = [r for r in rows if r["first"] and r["step"] is not None]
    if first:
        print(f"  première réponse : pas médian {100*st.median(r['step'] for r in first):.2f} % du devis (q10 {100*sorted(r['step'] for r in first)[len(first)//10]:.2f}, q90 {100*sorted(r['step'] for r in first)[9*len(first)//10]:.2f}) ; écart demandé médian {100*st.median(r['gap'] for r in first if r['gap'] is not None):.1f} %")
