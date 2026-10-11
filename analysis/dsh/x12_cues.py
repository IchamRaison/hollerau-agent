"""X12 (hors ligne): les phrases que les fournisseurs répètent dans leurs réponses, et ce qui les a
suivies. Source : les « raisons » des traces archivées (la vue d'équipe du replay). Une phrase est
normalisée (chiffres remplacés), comptée par fournisseur et par cas ; pour chaque phrase fréquente :
le pas du fournisseur dans CETTE réponse et dans la SUIVANTE, rapporté à notre coup, et son statut."""
import json, sys, glob, re, statistics as st
from collections import defaultdict, Counter
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
NUM = re.compile(r"\d+(?:[.,]\d+)?")
def norm(s):
    s = NUM.sub("…", s)
    s = re.sub(r"(?:… ?)+", "… ", s).replace("€… ", "€… ")
    s = re.sub(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9…]+)+\b", "<SERIES>", s)
    return re.sub(r"\s+", " ", s).strip()
rows = []  # per supplier reply: cues, step, our move, status, next step, next move
for path in sorted(glob.glob(f"{REPO}/analysis/pegasus_data/sessions/*.json") + glob.glob(f"{REPO}/data/runs/dsh-*/sessions/*.json")):
    d = json.load(open(path)); s = d.get("session") or d
    case = cases.get(s.get("case_id")); r = s.get("result") or {}
    if not case or not r.get("c_open") or not r.get("c_best"): continue
    span = r["c_open"] - r["c_best"]
    if span <= 1: continue
    cid = s["case_id"].split(":")[-1]; tr = r.get("trace") or []
    sups = list(dict.fromkeys(e["actor"] for e in tr if e.get("actor") != "buyer"))
    for sup in sups:
        ev = [e for e in tr if e.get("actor") == sup or (e.get("actor") == "buyer" and ((e.get("move") or {}).get("supplier_id") or sups[0]) == sup)]
        offer = ask = None; pend = None; seq = []
        for e in ev:
            m = e.get("move") or {}
            if e["actor"] == "buyer":
                cs = [c for c in (cost(case, t.get("terms", t)) for t in m.get("term_sheets") or []) if c is not None]
                new_ask = min(cs) if cs else None
                pend = (new_ask - ask) / span if (new_ask is not None and ask is not None) else (None if new_ask is None and ask is None else 0.0 if new_ask is None else None)
                if new_ask is not None: ask = new_ask
            else:
                sheets = [m.get("terms") or {}] + [a.get("terms") or {} for a in m.get("alternatives") or []]
                cs = [c for c in (cost(case, t) for t in sheets if t.get("unit_price") is not None) if c is not None]
                new = min(cs) if cs else None
                step = (offer - new) / span if (new is not None and offer is not None) else None
                seq.append({"case": cid, "sup": sup, "cues": [norm(x) for x in e.get("reasons") or []], "step": step, "move": pend, "status": m.get("status"), "n": len(seq)})
                if new is not None: offer = new
        for i, x in enumerate(seq):
            x["next"] = seq[i + 1] if i + 1 < len(seq) else None
            rows.append(x)
count = Counter(); sup_of = defaultdict(set); case_of = defaultdict(set)
for x in rows:
    for c in set(x["cues"]):
        count[c] += 1; sup_of[c].add(x["sup"]); case_of[c].add(x["case"])
print(f"réponses fournisseur: {len(rows)} ; phrases distinctes (normalisées): {len(count)}")
def med(v): return f"{100*st.median(v):6.1f}" if v else "   n/a"
print(f"\n{'n':>4} {'fourn.':>6} {'cas':>3}  {'pas ICI':>7} {'pas APRÈS':>9} {'ratio APRÈS':>11} {'final APRÈS %':>13}  phrase")
out = []
for c, n in count.most_common(400):
    if n < 8 or len(sup_of[c]) < 2: continue
    here = [x["step"] for x in rows if c in x["cues"] and x["step"] is not None and x["n"] > 0]
    nxt = [x["next"] for x in rows if c in x["cues"] and x["next"] is not None]
    nstep = [y["step"] for y in nxt if y["step"] is not None]
    ratio = [y["step"] / y["move"] for y in nxt if y["step"] is not None and y["move"] and y["move"] > 0.005]
    fin = [y["status"] == "final_offer" for y in nxt]
    out.append({"cue": c, "n": n, "suppliers": len(sup_of[c]), "cases": len(case_of[c])})
    print(f"{n:4d} {len(sup_of[c]):6d} {len(case_of[c]):3d}  {med(here)} {med(nstep):>9} {(f'{st.median(ratio):.2f}' if ratio else 'n/a'):>11} {(f'{100*sum(fin)/len(fin):.0f}' if fin else 'n/a'):>13}  {c[:150]}")
json.dump(out, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
