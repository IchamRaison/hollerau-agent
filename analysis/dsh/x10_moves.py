"""X10 bis (hors ligne): combien de coups de prix un fournisseur joue par session, et quelle part
de sa concession totale tient dans le premier ? (nombre de points disponibles pour ajuster un
modèle de concession à l'intérieur d'une partie)"""
import json, sys, glob, statistics as st
from collections import defaultdict
REPO = sys.argv[1]
per = defaultdict(list)
for path in sorted(glob.glob(f"{REPO}/analysis/pegasus_data/sessions/*.json")):
    d = json.load(open(path)); s = d.get("session") or d
    r = s.get("result") or {}
    cid = (s.get("case_id") or "").split(":")[-1]
    by = defaultdict(list)
    for e in r.get("trace") or []:
        if e.get("actor") == "buyer":
            continue
        m = e.get("move") or {}
        sheets = [m.get("terms") or {}] + [a.get("terms") or {} for a in m.get("alternatives") or []]
        prices = [t["unit_price"] for t in sheets if t.get("unit_price") is not None]
        if prices:
            by[e["actor"]].append(min(prices))
    for sup, p in by.items():
        if len(p) < 2:
            continue
        low = [p[0]]
        for x in p[1:]:
            low.append(min(low[-1], x))
        steps = sum(1 for a, b in zip(low, low[1:]) if b < a - 1e-9)
        total = low[0] - low[-1]
        first = (low[0] - low[1]) / total if total > 1e-9 else None
        per[cid].append((len(p) - 1, steps, first, total / low[0]))
print(f"{'cas':5} {'fils':>4} {'réponses (méd.)':>15} {'baisses de prix (méd./max)':>27} {'part de la 1re réponse (méd.)':>29} {'baisse totale (méd.)':>21}")
alls = []
for cid in sorted(per, key=lambda x: (x[0], int(x[1:]))):
    v = per[cid]; f = [x[2] for x in v if x[2] is not None]; alls += [x[1] for x in v]
    print(f"{cid:5} {len(v):4d} {st.median(x[0] for x in v):15.1f} {st.median(x[1] for x in v):18.1f} / {max(x[1] for x in v):<6d} {st.median(f) if f else float('nan'):24.2f} {100*st.median(x[3] for x in v):19.1f} %")
print("tous: baisses de prix par fil, médiane %.1f, p90 %d" % (st.median(alls), sorted(alls)[int(len(alls)*0.9)]))
