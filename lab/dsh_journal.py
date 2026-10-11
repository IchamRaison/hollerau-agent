"""Lire un journal de partie DSH : qui a décidé chaque tour, délais, outils, mails."""

import json
import sys

ends = {}
lines = [json.loads(line) for line in open(sys.argv[1])]
for e in lines:
    if e["kind"] == "turn_end":
        ends[(e["case"], e["turn"])] = e
short = len(sys.argv) > 2
for e in lines:
    k = e["kind"]
    if k == "opened":
        print("OPENED", e["case"], e["suppliers"], "c_open", e["c_open"])
    elif k == "decision":
        te = ends.get((e["case"], e["turn"])) or {}
        tr = te.get("trace") or {}
        tk = tr.get("tokens") or {}
        print(
            f"\n{e['case']} TURN {e['turn']} source={e['source']} ready={e.get('ready')} budget={e.get('budget_s')} waited={e.get('waited_s')} steps={tr.get('model_steps')} turn_s={tr.get('seconds')} conv={te.get('conversation')} in={tk.get('inputTokens', 0) + tk.get('cacheReadTokens', 0) + tk.get('cacheWriteTokens', 0)} out={tk.get('outputTokens')} errors={tr.get('errors')}"
        )
        print("   tools:", [(t[0], t[1]) for t in e.get("tools") or []])
        b = e.get("batch") or {}
        for m in b.get("emails") or []:
            msg = m["message"]
            print(
                "   MAIL ->",
                m["supplier_id"],
                "| sheets:",
                [ts["terms"] for ts in msg.get("term_sheets", [])],
                "| refs:",
                msg.get("refs"),
            )
            if not short:
                print("      ", (msg.get("body") or "")[:700].replace("\n", " / "))
        if b.get("close"):
            print("   CLOSE", b["close"])
        if b.get("note"):
            print("   note:", b["note"][:300])
    elif k == "reply":
        print(
            "   REPLY",
            e["supplier"],
            e["status"],
            "cost",
            e.get("cost"),
            [(s.get("term_sheet_id"), s.get("terms")) for s in (e.get("sheets") or [])][:3],
            e.get("claim_results"),
        )
    elif k == "arena_error":
        print("   ARENA ERROR", e.get("supplier"), e.get("status"), e.get("detail"))
    elif k == "cap_near":
        print("   CAP NEAR")
    elif k == "result":
        print(
            "\nRESULT", e["case"], {x: e.get(x) for x in ("deal", "score", "c_open", "c_deal", "c_best", "end_reason")}
        )
