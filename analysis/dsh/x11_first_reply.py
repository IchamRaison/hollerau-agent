"""X11 bis (hors ligne): qu'est-ce qui fait la taille de la première réponse du fournisseur, et de
ses pas suivants ? Variables : profondeur de notre demande, arguments vérifiés, nombre de feuilles."""
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
        c = total_cost(case, terms); return None if c == float("inf") else c
    except Exception:
        return None
first, later = [], []
for path in sorted(glob.glob(f"{REPO}/analysis/pegasus_data/sessions/*.json") + sys.argv[2:]):
    d = json.load(open(path)); s = d.get("session") or d
    case = cases.get(s.get("case_id")); r = s.get("result") or {}
    if not case or not r.get("c_open") or not r.get("c_best"): continue
    span = r["c_open"] - r["c_best"]
    if span <= 1: continue
    cid = s["case_id"].split(":")[-1]
    tr = r.get("trace") or []
    sups = list(dict.fromkeys(e["actor"] for e in tr if e.get("actor") != "buyer"))
    for sup in sups:
        ev = [e for e in tr if e.get("actor") == sup or (e.get("actor") == "buyer" and ((e.get("move") or {}).get("supplier_id") or sups[0]) == sup)]
        offer = ask = None; n_buyer = 0; pend = None
        for e in ev:
            m = e.get("move") or {}
            if e["actor"] == "buyer":
                n_buyer += 1
                cs = [c for c in (cost(case, t.get("terms", t)) for t in m.get("term_sheets") or []) if c is not None]
                new_ask = min(cs) if cs else None
                pend = {"n": n_buyer, "sheets": len(cs), "move": (new_ask - ask) if (new_ask is not None and ask is not None) else None,
                        "ask": new_ask if new_ask is not None else ask, "chars": len(m.get("body") or "")}
                if new_ask is not None: ask = new_ask
            else:
                sheets = [m.get("terms") or {}] + [a.get("terms") or {} for a in m.get("alternatives") or []]
                cs = [c for c in (cost(case, t) for t in sheets if t.get("unit_price") is not None) if c is not None]
                new = min(cs) if cs else None
                if pend and new is not None and offer is not None:
                    res = [x.get("result") for x in m.get("claim_results") or []]
                    row = {"case": cid, "step": (offer - new) / span, "ver": res.count("verified"), "bad": res.count("contradicted") + res.count("irrelevant"),
                           "sheets": pend["sheets"], "status": m.get("status"),
                           "depth": ((r["c_open"] - pend["ask"]) / span) if pend["ask"] is not None else None,
                           "move": (pend["move"] / span) if pend["move"] is not None else None, "n": pend["n"]}
                    (first if pend["n"] == 1 else later).append(row)
                    pend = None
                if new is not None: offer = new
def med(v): return f"{100*st.median(v):6.1f}" if v else "   n/a"
print(f"premières réponses: {len(first)} ; suivantes: {len(later)}")
print("\n-- PREMIÈRE réponse : son pas (en % de c_open-c_best) selon la profondeur de notre demande (100 % = nous demandons c_best) --")
bk = [("pas de feuille", lambda d: d is None), ("< 60 %", lambda d: d is not None and d < .6), ("60-100 %", lambda d: d is not None and .6 <= d < 1.0),
      ("100-150 %", lambda d: d is not None and 1.0 <= d < 1.5), ("150-250 %", lambda d: d is not None and 1.5 <= d < 2.5), (">= 250 %", lambda d: d is not None and d >= 2.5)]
for name, f in bk:
    v = [x for x in first if f(x["depth"])]
    if v: print(f"  demande {name:14} n={len(v):4d} pas médian {med([x['step'] for x in v])} %  p25 {100*sorted(x['step'] for x in v)[len(v)//4]:6.1f}  p75 {100*sorted(x['step'] for x in v)[3*len(v)//4]:6.1f}  cas: {dict((c, sum(1 for x in v if x['case']==c)) for c in sorted(set(x['case'] for x in v)))}")
print("\n-- PREMIÈRE réponse selon les arguments vérifiés du premier mail --")
for k in (0, 1, 2, 3):
    v = [x["step"] for x in first if x["ver"] == k and x["bad"] == 0]
    if v: print(f"  {k} vérifié(s), 0 rejeté   n={len(v):4d} pas médian {med(v)} %")
v = [x["step"] for x in first if x["bad"] > 0]
if v: print(f"  au moins un rejeté        n={len(v):4d} pas médian {med(v)} %")
print("\n-- PREMIÈRE réponse selon le nombre de feuilles envoyées --")
for k in (0, 1, 2, 3):
    v = [x["step"] for x in first if x["sheets"] == k]
    if v: print(f"  {k} feuille(s) n={len(v):4d} pas médian {med(v)} %")
print("\n-- réponses SUIVANTES : son pas selon notre coup (en % de l'écart), par tranche fine --")
for lo, hi in ((-9, 1e-6), (1e-6, .01), (.01, .02), (.02, .04), (.04, .06), (.06, .10), (.10, .20), (.20, 9)):
    v = [x for x in later if x["move"] is not None and lo < x["move"] <= hi]
    if v:
        ratio = [x["step"] / x["move"] for x in v if x["move"] > 1e-6]
        print(f"  notre coup {100*max(lo,0):5.1f}-{100*min(hi,9):5.1f} % n={len(v):4d} son pas médian {med([x['step'] for x in v])} %  rapport son pas / notre coup: {st.median(ratio) if ratio else float('nan'):.2f}")
print("\n-- réponses SUIVANTES selon les arguments vérifiés dans notre mail --")
for k in (0, 1, 2, 3):
    v = [x["step"] for x in later if x["ver"] == k and x["move"] is not None and x["move"] > 1e-6]
    if v: print(f"  {k} vérifié(s) n={len(v):4d} pas médian {med(v)} %")
print("\n-- la même chose par cas pour la première réponse (pour voir si un seul cas porte tout) --")
for cid in sorted(set(x["case"] for x in first)):
    v = [x for x in first if x["case"] == cid]
    print(f"  {cid:4} n={len(v):4d} pas médian {med([x['step'] for x in v])} %  profondeur médiane {med([x['depth'] for x in v if x['depth'] is not None])} %")
