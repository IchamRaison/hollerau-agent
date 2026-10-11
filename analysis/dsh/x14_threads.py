"""X14 (hors ligne, lecture seule) : un enregistrement par fil fournisseur de l'archive.
python threads.py <racine du worktree>  ->  threads.json à côté de ce script.
Chaque fil : nos mails et ses réponses, en coût pour nous (arena_kit.cost.total_cost), avec le statut,
la décision interne (« My call »), les notes internes et les raisons du replay."""
import json, sys, glob, re
from collections import defaultdict
from pathlib import Path

REPO = sys.argv[1]
sys.path.insert(0, REPO)
from arena_kit.cost import total_cost

cases = {}
for name in ("practice", "sandbox"):
    d = json.load(open(f"{REPO}/analysis/pegasus_data/cases-{name}.json"))
    d = d if isinstance(d, list) else d.get("cases", d)
    for c in (d.values() if isinstance(d, dict) else d):
        cases[c["case_id"]] = c


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def cost(case, terms, fill):
    t = {**fill, **{k: v for k, v in (terms or {}).items() if v is not None}}
    try:
        c = total_cost(case, t)
        return None if c == float("inf") else round(c, 2)
    except Exception:
        return None


BOILER = ("My call:", "Read the buyer's e-mail", "quote attached", "order confirmation attached")
out = []
for path in sorted(glob.glob(f"{REPO}/analysis/pegasus_data/sessions/*.json")):
    d = json.load(open(path)); s = d.get("session") or d
    r = s.get("result") or {}
    case = cases.get(s.get("case_id"))
    if not case or not r.get("trace"):
        continue
    cid = s["case_id"].split(":")[-1]
    trace = r["trace"]
    sups = sorted({e["actor"] for e in trace if e.get("actor") != "buyer"})
    notes = defaultdict(lambda: defaultdict(list)); calls = defaultdict(dict); roles = {}
    for m in d.get("backoffice") or []:
        sid, rd, txt = m.get("supplier_id"), int(m.get("round") or 0), str(m.get("text"))
        if m.get("to") == "team" and sid not in roles:
            roles[sid] = m.get("from")
        if txt.startswith("My call:"):
            calls[sid][rd] = txt[9:].strip(". ")
        elif not txt.startswith(BOILER):
            notes[sid][rd].append(f"{m.get('from')}>{m.get('to')}: {txt}")
    th = defaultdict(list)
    for e in trace:
        m = e.get("move") or {}
        if e.get("actor") == "buyer":
            sid = m.get("supplier_id") or (sups[0] if len(sups) == 1 else None)
            if sid:
                th[sid].append(("B", e, m))
        else:
            th[e["actor"]].append(("S", e, m))
    for sid, ev in th.items():
        first = next((m for w, e, m in ev if w == "S"), None)
        if not first:
            continue
        fill = {k: v for k, v in (first.get("terms") or {}).items() if k != "unit_price"}
        rec = {"session": s["session_id"], "case": cid, "supplier": sid.split(":")[-1], "role": roles.get(sid),
               "rfq": len(sups) > 1, "n_suppliers": len(sups), "type": case.get("type"),
               "goal": case["buyer"].get("category_goal"), "score": r.get("score"), "deal": bool(r.get("deal")),
               "deal_supplier": (r.get("supplier_id") or "").split(":")[-1], "end_reason": s.get("end_reason"),
               "c_open": r.get("c_open"), "c_best": r.get("c_best"), "c_deal": r.get("c_deal"), "c_alt": r.get("c_alt"),
               "created_at": (d.get("summary") or {}).get("created_at"), "negotiable": case["negotiable"], "events": []}
        for w, e, m in ev:
            if w == "B":
                sheets = m.get("term_sheets") or []
                sheets = sheets if isinstance(sheets, list) else []
                interp = m.get("interpreted") if isinstance(m.get("interpreted"), dict) else {}
                rec["events"].append({"who": "B", "round": e.get("round"), "action": m.get("type"),
                    "sheets": [{"terms": (t.get("terms") or t), "cost": cost(case, t.get("terms") or t, fill)} for t in sheets],
                    "claims": [c.get("type") for c in (interp.get("claims") or []) if isinstance(c, dict)],
                    "refs": m.get("refs") or [], "body": m.get("body") or ""})
            else:
                terms = m.get("terms") or {}
                fill = {**fill, **{k: v for k, v in terms.items() if k != "unit_price" and v is not None}}
                rd = int(e.get("round") or 0)
                rec["events"].append({"who": "S", "round": rd, "status": m.get("status"), "terms": terms,
                    "missing": m.get("missing_fields") or [], "cost": cost(case, terms, fill) if terms.get("unit_price") is not None else None,
                    "price": num(terms.get("unit_price")),
                    "alts": [{"terms": a.get("terms"), "cost": cost(case, a.get("terms"), fill)} for a in (m.get("alternatives") or [])],
                    "claim_results": [c.get("result") for c in (m.get("claim_results") or [])],
                    "reasons": e.get("reasons") or [], "call": calls[sid].get(rd), "notes": notes[sid].get(rd, []),
                    "text": m.get("text") or "", "signals": m.get("signals") or {}})
        out.append(rec)
Path(__file__).with_name("threads.json").write_text(json.dumps(out, ensure_ascii=False))
print(len(out), "fils ;", len({r['session'] for r in out}), "sessions ;", len({(r['case'], r['supplier']) for r in out}), "fournisseurs")
