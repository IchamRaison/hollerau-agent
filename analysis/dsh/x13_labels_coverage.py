"""X13 (hors ligne, lecture seule) : deux comptages pour le plan de reconnaissance, v3.
1. Étiquettes observables de chaque réponse fournisseur : type (départ, maintien, nouvelle offre,
   sans feuille) x statut API. « Maintien » = mêmes termes et mêmes champs laissés au standard que
   sa feuille précédente (avant complétion par les standards : quelques maintiens peuvent manquer).
2. Borne haute de la couverture de la règle d'abstention proposée par Codex au tour 3 : part des
   réponses qui ont des précédents dans au moins trois AUTRES cas, sous des conditions de plus en
   plus proches de la règle. Ne regarde aucune réponse : seulement le préfixe et notre mail."""
import json, sys, glob
from collections import Counter, defaultdict

REPO = sys.argv[1]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

rows = []      # one per supplier reply to one of our mails
labels = Counter()
for path in sorted(glob.glob(f"{REPO}/analysis/pegasus_data/sessions/*.json")):
    d = json.load(open(path)); s = d.get("session") or d
    r = s.get("result") or {}
    case = s["case_id"].split(":")[-1]
    trace = r.get("trace") or []
    suppliers = sorted({e["actor"] for e in trace if e.get("actor") != "buyer"})
    rfq = len(suppliers) > 1
    th = defaultdict(list)
    for e in trace:
        m = e.get("move") or {}
        if e.get("actor") == "buyer":
            sid = m.get("supplier_id") or (suppliers[0] if len(suppliers) == 1 else None)
            if sid:
                th[sid].append(("B", m))
        else:
            th[e["actor"]].append(("S", m))
    for sid, ev in th.items():
        opening = next((m for w, m in ev if w == "S"), None)
        p0 = num(((opening or {}).get("terms") or {}).get("unit_price"))
        prev_s = None      # supplier's previous message
        prev_b = None      # our previous mail
        pending = None     # our mail awaiting its reply
        k = 0
        for w, m in ev:
            if w == "B":
                if pending is not None:
                    prev_b = pending
                pending = m
                continue
            if pending is None:      # opening quote, or a supplier message we did not prompt
                prev_s = m
                continue
            k += 1
            status = m.get("status")
            terms = m.get("terms") or {}
            if status in ("walked_away", "no_bid"):
                kind = "départ"
            elif terms.get("unit_price") is None:
                kind = "sans feuille"
            else:
                same = prev_s is not None and (prev_s.get("terms") or {}) == terms and \
                    sorted(prev_s.get("missing_fields") or []) == sorted(m.get("missing_fields") or [])
                kind = "maintien" if same else "nouvelle offre"
            labels[(kind, status)] += 1
            sheets = pending.get("term_sheets") or []
            if isinstance(sheets, str):
                sheets = []
            prices = [num((t.get("terms") or t).get("unit_price")) for t in sheets]
            norm = tuple(round(p / p0, 4) if p and p0 else None for p in prices)
            pb = [num((t.get("terms") or t).get("unit_price")) for t in ((prev_b or {}).get("term_sheets") or [])] if prev_b else []
            pb = [p for p in pb if p]
            cur = [p for p in prices if p]
            move = round((min(cur) - min(pb)) / p0, 4) if cur and pb and p0 else None
            interp = pending.get("interpreted") or {}
            claims = frozenset(c.get("type") for c in (interp.get("claims") or []) if isinstance(c, dict)) if isinstance(interp, dict) else frozenset()
            rows.append(dict(case=case, sid=sid, rfq=rfq, k=k, prev=(prev_s or {}).get("status"),
                             n=len(sheets), norm=norm, move=move, claims=claims, first=(prev_b is None)))
            prev_s, prev_b, pending = m, pending, None

print(f"réponses fournisseur à l'un de nos mails : {len(rows)}")
print("\n-- 1. étiquettes observables : type x statut --")
kinds = ["départ", "maintien", "nouvelle offre", "sans feuille"]
stats = sorted({s for _, s in labels}, key=str)
print(f"{'':16}" + "".join(f"{str(s):>14}" for s in stats) + f"{'total':>10}")
for kd in kinds:
    print(f"{kd:16}" + "".join(f"{labels[(kd, s)]:>14}" for s in stats) + f"{sum(labels[(kd, s)] for s in stats):>10}")

def near_k(a, b):
    if a["first"] or b["first"]:
        return a["first"] and b["first"]
    return abs(a["k"] - b["k"]) <= 1

def c1(a, b):
    return a["rfq"] == b["rfq"] and a["prev"] == b["prev"] and near_k(a, b) and a["n"] == b["n"]

def c2(a, b):
    if not c1(a, b):
        return False
    for x, y in zip(a["norm"], b["norm"]):
        if x is None or y is None or abs(x - y) > 0.05:
            return False
    if not a["first"]:
        if (a["move"] is None) != (b["move"] is None):
            return False
        if a["move"] is not None and abs(a["move"] - b["move"]) > 0.02:
            return False
    return True

def c3(a, b):
    return c2(a, b) and a["claims"] == b["claims"]

print("\n-- 2. borne haute de couverture : précédents dans >= 3 autres cas --")
print("   (la règle complète exige en plus : mêmes changements de clauses, mêmes questions, nouveauté des arguments)")
by_case = defaultdict(list)
for r in rows:
    by_case[r["case"]].append(r)
for name, cond in (("contexte + statut précédent + numéro + nombre de feuilles", c1),
                   ("... + prix à 0,05 près et mouvement à 0,02 près", c2),
                   ("... + mêmes familles d'arguments", c3)):
    covered = Counter(); total = Counter(); first_cov = first_tot = 0
    for a in rows:
        others = {b["case"] for c, lst in by_case.items() if c != a["case"] for b in lst if cond(a, b)}
        ok = len(others) >= 3
        total[a["case"]] += 1; covered[a["case"]] += ok
        if a["first"]:
            first_tot += 1; first_cov += ok
    n = sum(total.values()); cv = sum(covered.values())
    per_case = sum(covered[c] / total[c] for c in total) / len(total)
    print(f"\n{name}\n   toutes réponses : {cv}/{n} = {100*cv/n:.1f} % ; moyenne par cas : {100*per_case:.1f} % ; "
          f"premières réponses : {first_cov}/{first_tot} = {100*first_cov/max(first_tot,1):.1f} %")
    print("   par cas : " + "  ".join(f"{c} {covered[c]}/{total[c]}" for c in sorted(total)))
