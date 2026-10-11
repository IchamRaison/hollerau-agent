"""X11 (hors ligne): que fait le fournisseur après chacun de nos coups ? Sur les sessions archivées,
par fil : notre concession (en coût pour nous), son pas en réponse, l'écart restant, le statut.
Questions : son pas dépend-il de la taille du nôtre ? descend-il sous notre demande ? quand dit-il
« offre finale » ? combien de messages utilisons-nous ?"""
import json, sys, glob, statistics as st
from collections import defaultdict
REPO = sys.argv[1]
sys.path.insert(0, REPO)
from arena_kit.cost import total_cost

cases = {}
for name in ("practice", "sandbox"):
    d = json.load(open(f"{REPO}/analysis/pegasus_data/cases-{name}.json"))
    d = d if isinstance(d, list) else d.get("cases", d)
    for c in (d.values() if isinstance(d, dict) else d):
        cases[c["case_id"]] = c

def cost(case, terms):
    try:
        return total_cost(case, terms)
    except Exception:
        return None

rows = []   # (case, k, our_move, its_step, gap_before, status_after, span)
ends = defaultdict(list)
for path in sorted(glob.glob(f"{REPO}/analysis/pegasus_data/sessions/*.json") + sys.argv[2:]):
    d = json.load(open(path)); s = d.get("session") or d
    case = cases.get(s.get("case_id")); r = s.get("result") or {}
    if not case or not r.get("c_open") or not r.get("c_best"):
        continue
    span = r["c_open"] - r["c_best"]
    if span <= 1:
        continue
    cid = s["case_id"].split(":")[-1]
    threads = defaultdict(list)
    only = None
    for e in r.get("trace") or []:
        m = e.get("move") or {}
        if e.get("actor") != "buyer":
            only = only or e["actor"]
    for e in r.get("trace") or []:
        m = e.get("move") or {}
        if e.get("actor") == "buyer":
            sid = m.get("supplier_id") or only
            cs = [cost(case, t.get("terms", t)) for t in m.get("term_sheets") or []]
            cs = [c for c in cs if c is not None and c != float("inf")]
            threads[sid].append(("B", min(cs) if cs else None, None))
        else:
            sheets = [m.get("terms") or {}] + [a.get("terms") or {} for a in m.get("alternatives") or []]
            cs = [cost(case, t) for t in sheets if t.get("unit_price") is not None]
            cs = [c for c in cs if c is not None and c != float("inf")]
            threads[e["actor"]].append(("S", min(cs) if cs else None, m.get("status")))
    for sid, ev in threads.items():
        ask_prev = offer_prev = None; k = 0; ours = 0
        last_ask = None
        for i, (who, c, status) in enumerate(ev):
            if who == "B":
                ours += 1
                if c is not None:
                    last_ask, ask_before = c, last_ask
                    pending = (c - ask_before) if ask_before is not None else None
                else:
                    pending = 0.0 if last_ask is not None else None
                    ask_before = last_ask
            else:
                if c is not None and offer_prev is not None and ours and last_ask is not None:
                    k += 1
                    rows.append((cid, k, pending, offer_prev - c, offer_prev - last_ask, status, span, c - last_ask))
                if c is not None:
                    offer_prev = c
        final = [x for x in ev if x[0] == "S"][-1][2] if any(x[0] == "S" for x in ev) else None
        ends[cid].append((ours, final))

def pct(x): return f"{100*x:5.1f}"
print(f"réponses fournisseur analysées: {len(rows)} (fils: {sum(len(v) for v in ends.values())})")
below = sum(1 for r in rows if r[7] < -1e-6)
agreed = sum(1 for r in rows if r[5] == "agreed")
print(f"son offre passe SOUS notre demande: {below} fois ; statut 'agreed' (il accepte nos termes): {agreed}")
print("\n-- son pas (en % de l'écart d'ouverture c_open-c_best) selon la taille de notre coup --")
buckets = [("nous ne bougeons pas (<=0)", lambda m: m is not None and m <= 1e-6), ("petit coup (0-2 % de l'écart)", lambda m: m is not None and 1e-6 < m), ]
def b(m, span):
    if m is None: return "premier coup"
    x = m / span
    if x <= 1e-6: return "0 ou recul"
    if x <= 0.03: return "0-3 %"
    if x <= 0.08: return "3-8 %"
    if x <= 0.20: return "8-20 %"
    return "> 20 %"
by = defaultdict(list)
for r in rows:
    by[b(r[2], r[6])].append(r[3] / r[6])
for name in ("premier coup", "0 ou recul", "0-3 %", "3-8 %", "8-20 %", "> 20 %"):
    v = by.get(name) or []
    if v:
        print(f"  notre coup {name:14} n={len(v):4d}  son pas: médiane {pct(st.median(v))} %  moyenne {pct(st.mean(v))} %  part de pas nuls {pct(sum(1 for x in v if x <= 1e-6)/len(v))} %")
print("\n-- par numéro de réponse (après notre k-ième message) --")
byk = defaultdict(list)
for r in rows: byk[min(r[1], 7)].append(r)
for k in sorted(byk):
    v = byk[k]
    fin = sum(1 for r in v if r[5] in ("final_offer",)) / len(v); ag = sum(1 for r in v if r[5] == "agreed") / len(v); wa = sum(1 for r in v if r[5] in ("walked_away", "no_bid")) / len(v)
    print(f"  réponse {k}{'+' if k==7 else ' '} n={len(v):4d} son pas médian {pct(st.median(r[3]/r[6] for r in v))} %  écart restant médian {pct(st.median(r[7]/r[6] for r in v))} %  final_offer {pct(fin)} %  agreed {pct(ag)} %  parti {pct(wa)} %")
print("\n-- écart (son offre - notre demande, en % de l'écart d'ouverture) juste avant sa réponse, selon le statut qu'il donne --")
bys = defaultdict(list)
for r in rows: bys[r[5]].append(r[4] / r[6])
for s_, v in sorted(bys.items(), key=lambda x: -len(x[1])):
    print(f"  {str(s_):12} n={len(v):4d} écart avant: médiane {pct(st.median(v))} %  p10 {pct(sorted(v)[len(v)//10])} %  p90 {pct(sorted(v)[9*len(v)//10])} %")
print("\n-- messages utilisés par fil et statut final --")
for cid in sorted(ends):
    v = ends[cid]
    c = defaultdict(int)
    for _, f in v: c[f] += 1
    print(f"  {cid:4} fils {len(v):4d} messages envoyés médiane {st.median(x[0] for x in v):.0f} max {max(x[0] for x in v)}  statuts finaux {dict(c)}")
