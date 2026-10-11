"""Download the full threads (messages, term sheets, statuses, attachments with text) of our selected
ended sessions, print each supplier's standard terms from its quote PDF, then replay P01/P02/P03
against the recorded bot counters with the real opening message (attachment included)."""
import glob
import json
import logging
import os
import pathlib
import sys
import tempfile
import time

logging.basicConfig(level=logging.WARNING)
from arena_kit.cli import load_env  # noqa: E402

load_env()
from arena_kit.client import ArenaClient  # noqa: E402
from arena_kit.data import DataPackage  # noqa: E402
from arena_kit.docs import quote_terms, read_document  # noqa: E402

import pegasus.memory as M  # noqa: E402

M.FILE = pathlib.Path(tempfile.mktemp(suffix=".json"))
from pegasus import economics as eco  # noqa: E402
from pegasus.agent import PegasusAgent  # noqa: E402

SP = "/tmp/claude-1000/-home-heezo/59742ee3-ebd1-4af1-9297-9691f27834d9/scratchpad"
OUT = f"{SP}/threads"
os.makedirs(OUT, exist_ok=True)
c = ArenaClient()
pkg = DataPackage("data/package")
facts = pkg.facts
cases = {x["case_id"]: x for x in json.load(open(os.path.expanduser("~/tacto/codex-work/arena-data/cases-practice.json")))}

# 1. threads of the 30 selected sessions
sel = sorted(glob.glob(f"{SP}/traces/*.json"))
stds = {}
for f in sel:
    cid, sid = "case:" + os.path.basename(f)[:3], os.path.basename(f)[4:-5]
    out = f"{OUT}/{cid[5:]}-{sid}.json"
    if os.path.exists(out):
        th = json.load(open(out))
    else:
        th = {}
        for sup in cases[cid]["suppliers"]:
            try:
                t = c._call("GET", f"/sessions/{sid}/threads/{sup}")
            except Exception as e:
                print(cid, sid, sup, "thread failed:", str(e)[:80])
                continue
            for m in t.get("messages") or []:
                for att in m.get("attachments") or []:
                    if att.get("attachment_id") and not att.get("text"):
                        try:
                            att["text"] = read_document(att["name"], c.attachment(sid, att["attachment_id"]))
                        except Exception as e:
                            att["text"] = f"<download failed: {e}>"
                        time.sleep(0.2)
            th[sup] = t
        json.dump(th, open(out, "w"), ensure_ascii=False, indent=0)
    for sup, t in th.items():
        for m in t.get("messages") or []:
            for att in m.get("attachments") or []:
                if att.get("name", "").startswith("quote") and att.get("text") and sup not in stds:
                    q = quote_terms(att["text"])
                    stds[sup] = (cid, q.get("standard"), q.get("fixed"), q.get("stated"))
print(len(os.listdir(OUT)), "threads saved")
for sup, (cid, std, fixed, stated) in sorted(stds.items()):
    print(f"{cid} {sup}: standard={std} fixed={fixed} stated={stated}")

# 2. replay P01/P02/P03 with the real opening message
counters = {"case:P01": [({"unit_price": 137.90, "payment_days": 45, "effective_date": "2027-04-01"}, "open"), ({"unit_price": 132.40, "payment_days": 14, "effective_date": "2027-04-01"}, "open"), ({"unit_price": 131.70, "payment_days": 14, "effective_date": "2027-04-01"}, "open"), ({"unit_price": 131.20, "payment_days": 14, "effective_date": "2027-04-01"}, "final_offer")],
            "case:P02": [({"unit_price": 373.88, "payment_days": 90, "index_clause": None}, "open"), ({"unit_price": 373.04, "payment_days": 90, "index_clause": None}, "open"), ({"unit_price": 372.53, "payment_days": 90, "index_clause": None}, "open"), ({"unit_price": 372.23, "payment_days": 90, "index_clause": None}, "final_offer")],
            "case:P03": [({"unit_price": 431.63, "payment_days": 90, "contract_months": 24, "volume_per_year": 4580}, "open"), ({"unit_price": 431.63, "payment_days": 90, "contract_months": 36, "volume_per_year": 4580}, "open"), ({"unit_price": 431.63, "payment_days": 90, "contract_months": 36, "volume_per_year": 4580}, "open")]}
pb = json.load(open(os.path.expanduser("~/tacto/codex-work/intel/generated/CASE_PLAYBOOK.json")))
fitted = {"case:P01": 0.096, "case:P02": 0.066, "case:P03": 0.061}
for cid in ("case:P01", "case:P02", "case:P03"):
    case = cases[cid]
    sid_sup = case["suppliers"][0]
    best = sorted(glob.glob(f"{SP}/traces/{cid[5:]}-*.json"), key=lambda x: (json.load(open(x)).get("result") or {}).get("score") or 0)[-1]
    sess = os.path.basename(best)[4:-5]
    th = json.load(open(f"{OUT}/{cid[5:]}-{sess}.json"))[sid_sup]
    res = json.load(open(best))["result"]
    opening = th["messages"][0]
    std0 = dict(pb["cases"][cid]["suppliers"][sid_sup]["supplier_model"]["supplier"]["standard"])
    sc = facts[f"cost:{case['parts'][0].split(':')[1]}"]["unit_cost"]
    exact = {**std0, "_supplier": {"standard": std0, "interest_rate": fitted[cid], "full_cost": sc / 1.02}}

    def score(t, case=case, res=res, exact=exact):
        return (res["c_open"] - eco.cost(case, t, exact)) / (res["c_open"] - res["c_best"])

    ag = PegasusAgent(pkg)
    events = [dict(opening, round=0)]
    op_terms = opening["term_sheets"][0]["terms"]
    print(f"\n### {cid} opening {op_terms.get('unit_price')} (attachments: {[a['name'] for a in opening.get('attachments') or []]})")
    for k, (ct, status) in enumerate([(None, None)] + counters[cid]):
        if ct:
            full = {**op_terms, **ct}
            body = "We have reviewed your offer and can adjust our Angebot as follows."
            if cid == "case:P03" and k == 2:
                body += " Please provide the underlying data for your volume commitment to substantiate this planning certainty. Which figures is that based on?"
            events.append({"from": sid_sup, "term_sheets": [{"term_sheet_id": f"offer:{sid_sup[4:]}-{k}", "terms": full}], "status": status, "body": body, "round": k})
            print(f"  bot r{k} {status}: {ct}  (score if accepted {score(full):.3f})")
        dec = ag.decide(case, {sid_sup: events}, sid_sup)
        m = dec["message"] if dec else None
        if not m:
            print("  -> no decision")
            break
        if m.get("action"):
            print(f"  -> us: {m['action']} {m.get('term_sheet_id') or ''}")
            break
        sheets = [t["terms"] for t in m.get("term_sheets") or []]
        if k == 0:
            st = ag.state[sid_sup]
            print("  std:", {kk: v for kk, v in st["std"].items() if not kk.startswith("_")}, "| model:", {kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in st["std"]["_floor"].items() if kk != "standard"})
        extra = (" [pièce jointe: " + ", ".join(x["name"] for x in m.get("attachments") or []) + "]" if m.get("attachments") else "") + (" [NUDGE]" if "ready to close" in (m.get("body") or "") else "") + (" [substantiation]" if "To substantiate" in (m.get("body") or "") else "")
        print(f"  -> us r{k + 1}:{extra} " + " | ".join(f"{t['unit_price']}/{t.get('payment_days')}/{str(t.get('effective_date') or t.get('contract_months') or '')[:7]}{'/idx' if t.get('index_clause') else ''} ({score(t):.3f})" for t in sheets) + ("  [empty]" if not sheets else ""))
        events.append({"from": "buyer", "term_sheets": m.get("term_sheets") or [], "status": "message", "body": m.get("body", ""), "round": k + 1})
