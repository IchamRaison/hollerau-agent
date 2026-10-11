"""X15 : de quoi dépend son pas — de l'écart (son offre - notre demande) ou de notre mouvement ?
Et de quoi dépend l'arrivée de son offre finale — du numéro de la réponse ou de la taille de notre mouvement ?
Réponses k>=2, statut précédent ouvert, écart > 0,5 % du devis. Tout en part de son devis (coût pour nous)."""
import json, statistics as st
from pathlib import Path
from collections import defaultdict
T = json.load(open(Path(__file__).with_name("threads.json")))
R = defaultdict(list)
for t in T:
    C0 = next((e["cost"] for e in t["events"] if e["who"] == "S" and e["cost"]), None)
    if not C0: continue
    prev = None; pend = None; k = 0; last_ask = None
    for e in t["events"]:
        if e["who"] == "B":
            cs = [s["cost"] for s in e["sheets"] if s["cost"] is not None]
            pend = (min(cs) if cs else None, len(e["sheets"]), len(e["claims"])); continue
        if prev is None: prev = e; continue
        k += 1
        if pend and pend[0] is not None and prev["cost"] is not None:
            gap = (prev["cost"] - pend[0]) / C0
            move = None if last_ask is None else (pend[0] - last_ask) / C0
            step = None if e["cost"] is None else (prev["cost"] - e["cost"]) / C0
            R[f"{t['case']}/{t['supplier']}"].append(dict(k=k, gap=gap, move=move, step=step, status=e["status"], prev=prev["status"],
                 ver=sum(1 for c in e["claim_results"] if c == "verified")))
        if pend and pend[0] is not None: last_ask = pend[0]
        if e["cost"] is not None: prev = e
        else: prev = {**prev, "status": e["status"]}
        pend = None

def ols(X, y):
    import itertools
    n, p = len(X), len(X[0])
    A = [[sum(X[r][i] * X[r][j] for r in range(n)) for j in range(p)] for i in range(p)]
    b = [sum(X[r][i] * y[r] for r in range(n)) for i in range(p)]
    for i in range(p):
        piv = A[i][i] or 1e-12
        for j in range(i + 1, p):
            f = A[j][i] / piv
            A[j] = [A[j][c] - f * A[i][c] for c in range(p)]; b[j] -= f * b[i]
    x = [0.0] * p
    for i in reversed(range(p)):
        x[i] = (b[i] - sum(A[i][j] * x[j] for j in range(i + 1, p))) / (A[i][i] or 1e-12)
    pred = [sum(X[r][i] * x[i] for i in range(p)) for r in range(n)]
    ybar = sum(y) / n
    ss = sum((yy - ybar) ** 2 for yy in y) or 1e-12
    return x, 1 - sum((yy - pp) ** 2 for yy, pp in zip(y, pred)) / ss

print("fournisseur     n   | pas ~ a*écart : a, R2 | pas ~ b*mouvement : b, R2 | pas ~ a*écart + b*mouvement : a, b, R2 | corr(écart, mouvement)")
for key in sorted(R):
    rows = [r for r in R[key] if r["k"] >= 2 and r["prev"] == "open" and r["gap"] > 0.005 and r["move"] is not None and r["step"] is not None and r["move"] > 1e-6]
    if len(rows) < 12:
        print(f"{key:14} {len(rows):3}  (trop peu)"); continue
    g = [r["gap"] for r in rows]; m = [r["move"] for r in rows]; s = [r["step"] for r in rows]
    (a1,), r1 = ols([[x] for x in g], s)
    (b1,), r2 = ols([[x] for x in m], s)
    (a2, b2), r3 = ols([[x, y] for x, y in zip(g, m)], s)
    mg, mm = st.mean(g), st.mean(m)
    cov = sum((x - mg) * (y - mm) for x, y in zip(g, m)); cor = cov / ((sum((x - mg) ** 2 for x in g) * sum((y - mm) ** 2 for y in m)) ** 0.5 or 1e-12)
    print(f"{key:14} {len(rows):3} | {a1:5.2f} {r1:5.2f} | {b1:5.2f} {r2:5.2f} | {a2:5.2f} {b2:5.2f} {r3:5.2f} | {cor:5.2f}")
print()
print("offre finale à la réponse k selon la taille de notre mouvement (part du devis) : n, part d'offres finales")
B = [("aucun", lambda m: m <= 1e-6), ("<0,3 %", lambda m: 1e-6 < m < 0.003), ("0,3-1 %", lambda m: 0.003 <= m < 0.01), ("1-3 %", lambda m: 0.01 <= m < 0.03), (">3 %", lambda m: m >= 0.03)]
for key in sorted(R):
    out = []
    for k in (2, 3, 4, 5):
        cells = []
        for name, f in B:
            v = [r for r in R[key] if r["k"] == k and r["prev"] == "open" and r["move"] is not None and f(r["move"])]
            if len(v) >= 4:
                cells.append(f"{name}: {sum(1 for r in v if r['status'] == 'final_offer')}/{len(v)}")
        if cells:
            out.append(f"k{k} [" + " ; ".join(cells) + "]")
    print(f"{key:14} " + "  ".join(out))
