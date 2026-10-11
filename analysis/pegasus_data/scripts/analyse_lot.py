"""Analyse d'un lot practice : nouveau score vs meilleur précédent vs record, termes, dernière raison.
Usage (depuis starter-kit) : uv run python analyse_lot.py <log du lot> <dossier arena-data>"""
import glob
import json
import re
import sys
import urllib.request

from arena_kit import ArenaClient
from arena_kit.cli import load_env

load_env()
log_path, data_dir = sys.argv[1], sys.argv[2]
played = re.findall(r"^case:(P\d+): score=([0-9.]+|None)", open(log_path).read(), re.M)
errors = re.findall(r"^case:(P\d+): ERROR (.*)$", open(log_path).read(), re.M)

# meilleur précédent par cas, d'après les exports déjà sur disque (avant ce lot)
prev = {}
for f in glob.glob(f"{data_dir}/sessions/P*.json"):
    d = json.load(open(f))
    cid = d["summary"]["case_id"][5:]
    prev[cid] = max(prev.get(cid, 0.0), d["summary"].get("score") or 0.0)

live = json.load(urllib.request.urlopen("https://arena.tacto.ai/v1/live"))
record = {b["case_id"][5:]: (b["best"], b["holder"]) for b in live["bots"]}

c = ArenaClient()
rows = []
for cid, score in played:
    s = sorted([x for x in c.sessions("practice") if x["case_id"] == f"case:{cid}"], key=lambda r: r["created_at"])[-1]
    st = c.session(s["session_id"])
    r = st.get("result") or {}
    terms = r.get("terms") or {}
    sup = [t for t in (r.get("trace") or []) if t["actor"] != "buyer"]
    last = " / ".join((sup[-1].get("reasons") or [])[:2])[:140] if sup else ""
    sc = float(score) if score != "None" else 0.0
    rec, holder = record.get(cid, (0, "?"))
    rows.append((cid, sc, prev.get(cid, 0.0), rec, holder, s.get("end_reason"), s.get("rounds"),
                 {k: terms.get(k) for k in ("unit_price", "payment_days", "contract_months", "lead_time_days",
                                            "ppm_commitment", "chargeback_eur_per_complaint") if terms.get(k) is not None},
                 bool(terms.get("index_clause")), last))
rows.sort(key=lambda x: x[1] - x[2])
print(f"{'cas':5} {'nouveau':>8} {'avant':>6} {'record':>7} {'détenteur':12} {'fin':10} rds  termes")
for cid, sc, pv, rec, holder, end, rds, terms, idx, last in rows:
    flag = "RECORD" if sc > rec + 1e-9 else ("+" if sc > pv + 1e-9 else ("=" if abs(sc - pv) < 1e-9 else "-"))
    print(f"{cid:5} {sc:8.3f} {pv:6.3f} {rec:7.3f} {holder[:12]:12} {str(end):10} {rds!s:>3}  {terms}{' +index' if idx else ''}  [{flag}]")
    if last:
        print(f"      dernière raison: {last}")
for cid, err in errors:
    print(f"{cid:5} ERREUR {err[:100]}")
me = c.me()
print(f"\nmoyenne lot: {100 * sum(r[1] for r in rows) / max(len(rows), 1):.1f} | quota restant: {me['practice']['left']}")
