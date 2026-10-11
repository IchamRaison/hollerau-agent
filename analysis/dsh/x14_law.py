"""X14 : la loi « pas = part de l'écart entre son offre et notre demande », à termes constants.
Pour chaque réponse du fournisseur dont les clauses hors prix sont celles de son offre précédente,
et pour laquelle un de nos feuilles porte ces mêmes clauses : pas = p_prec - p_nouv, écart = p_prec - p_demande."""
import json, statistics as st
from pathlib import Path
from collections import defaultdict
T = json.load(open(Path(__file__).with_name("threads.json")))

def nonprice(t):
    return tuple(sorted((k, str(v)) for k, v in (t or {}).items() if k != "unit_price" and v is not None))

rows = defaultdict(list)
for t in T:
    prev = None; ask = None; k = 0; our_prev = None
    for e in t["events"]:
        if e["who"] == "B":
            our_prev, ask = ask, e
            continue
        if prev is not None and ask is not None and e["price"] is not None and prev["price"] is not None:
            k += 1
            same = [s for s in ask["sheets"] if nonprice(s["terms"]) == nonprice(e["terms"])]
            kept = nonprice(e["terms"]) == nonprice(prev["terms"])
            if same and kept:
                pa = float(same[0]["terms"]["unit_price"])
                gap = prev["price"] - pa
                step = prev["price"] - e["price"]
                moved = None
                if our_prev:
                    sp = [s for s in our_prev["sheets"] if nonprice(s["terms"]) == nonprice(e["terms"])]
                    if sp:
                        moved = pa - float(sp[0]["terms"]["unit_price"])
                rows[(t["case"], t["supplier"], t["role"])].append(dict(k=k, gap=gap, step=step, p0=None, moved=moved,
                    status=e["status"], call=e["call"], prev_status=prev["status"], pprev=prev["price"], n=len(ask["sheets"]),
                    notes=e["notes"], verified=sum(1 for c in e["claim_results"] if c == "verified")))
        elif prev is not None and ask is not None:
            k += 1
        if e["price"] is not None:
            prev = e
        ask = None if e["who"] == "S" else ask

def q(v, p):
    v = sorted(v); return v[min(len(v) - 1, int(p * len(v)))] if v else float("nan")

print("fournisseur            rôle                 n   | λ=pas/écart quand il bouge : q25  med  q75 | part des réponses sans pas | écart médian/prix")
for key in sorted(rows):
    R = [r for r in rows[key] if r["gap"] > 1e-9]
    if len(R) < 5:
        print(f"{key[0]}/{key[1]:9} {str(key[2]):20} {len(R):4}  (trop peu)"); continue
    lam = [r["step"] / r["gap"] for r in R if r["step"] > 1e-9]
    hold = sum(1 for r in R if r["step"] <= 1e-9) / len(R)
    print(f"{key[0]}/{key[1]:9} {str(key[2]):20} {len(R):4} | {q(lam,.25):5.2f} {q(lam,.5):5.2f} {q(lam,.75):5.2f} (n={len(lam)}) | {hold:5.2f} | {st.median(r['gap']/r['pprev'] for r in R):.3f}")
print()
print("-- λ selon que nous avons bougé ou non (même feuille, prix relevé de notre côté) --")
for key in sorted(rows):
    R = [r for r in rows[key] if r["gap"] > 1e-9 and r["moved"] is not None]
    mv = [r for r in R if r["moved"] > 1e-9]; no = [r for r in R if r["moved"] <= 1e-9]
    f = lambda X: (f"{st.median(r['step']/r['gap'] for r in X):.2f} (n={len(X)}, sans pas {sum(1 for r in X if r['step']<=1e-9)/len(X):.0%})" if X else "-")
    print(f"{key[0]}/{key[1]:9} nous bougeons: {f(mv):34} nous ne bougeons pas: {f(no)}")
print()
print("-- λ selon le numéro de la réponse (médiane, quand il bouge) --")
for key in sorted(rows):
    R = [r for r in rows[key] if r["gap"] > 1e-9 and r["step"] > 1e-9]
    by = defaultdict(list)
    for r in R:
        by[min(r["k"], 7)].append(r["step"] / r["gap"])
    print(f"{key[0]}/{key[1]:9} " + "  ".join(f"k{k}:{st.median(v):.2f}({len(v)})" for k, v in sorted(by.items())))
