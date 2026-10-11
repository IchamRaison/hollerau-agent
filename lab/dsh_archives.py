"""uv run python lab/dsh_archives.py  ->  hollerau/dsh/observations.json

What our finished games say about each case we have played: how far below the opening quote the
best acceptable deal sat. One row per case, from the exact figures of the arena's results
(`c_open`, `c_best`). The pilot shows the model the rows of OTHER cases with the same category
goal: a prior for how much room a kind of case holds - never the row of the case being played.
Offline: reads `analysis/pegasus_data/`, opens no session.
"""

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "hollerau" / "dsh" / "observations.json"


def build():
    cases = {}
    for name in ("practice", "sandbox"):
        data = json.loads((ROOT / "analysis" / "pegasus_data" / f"cases-{name}.json").read_text())
        data = data if isinstance(data, list) else data.get("cases", data)
        for c in data.values() if isinstance(data, dict) else data:
            cases[c["case_id"]] = c
    rows = {}
    for path in sorted(glob.glob(str(ROOT / "analysis" / "pegasus_data" / "sessions" / "*.json"))):
        d = json.loads(Path(path).read_text())
        s = d.get("session") or d
        r, case = s.get("result") or {}, cases.get(s.get("case_id"))
        if not case or not r.get("c_open") or not r.get("c_best"):
            continue
        row = rows.setdefault(
            case["case_id"],
            {
                "case_id": case["case_id"],
                "type": case.get("type"),
                "category_goal": case["buyer"].get("category_goal"),
                "suppliers": len(case.get("suppliers") or []),
                "games": 0,
                "best_acceptable_deal_below_opening_pct": round(100 * (1 - r["c_best"] / r["c_open"]), 1),
            },
        )
        row["games"] += 1
    return sorted(rows.values(), key=lambda x: x["case_id"])


CUES = ROOT / "hollerau" / "dsh" / "cues.json"
MIN_REPLIES, MIN_SUPPLIERS, KEEP = 8, 2, 40


def _cost(case, terms):
    from arena_kit.cost import total_cost

    try:
        c = total_cost(case, terms)
        return None if c == float("inf") else c
    except Exception:
        return None


def build_cues():
    """The sentences suppliers repeat, and what followed each. Source: the reasons of the archived
    traces - the team view of the replay, the supplier's reasons in its own words. A sentence is
    kept when at least two suppliers said it. Per sentence and per case: how large the supplier's
    NEXT step was (share of c_open - c_best), what it was per euro of our move, and whether the
    next reply was a final offer. Kept per case so that the case being played can be left out."""
    from hollerau.dsh.patterns import normalise

    cases = {}
    for name in ("practice", "sandbox"):
        data = json.loads((ROOT / "analysis" / "pegasus_data" / f"cases-{name}.json").read_text())
        data = data if isinstance(data, list) else data.get("cases", data)
        for c in data.values() if isinstance(data, dict) else data:
            cases[c["case_id"]] = c
    rows = []
    for path in sorted(glob.glob(str(ROOT / "analysis" / "pegasus_data" / "sessions" / "*.json"))):
        d = json.loads(Path(path).read_text())
        s = d.get("session") or d
        r, case = s.get("result") or {}, cases.get(s.get("case_id"))
        if not case or not r.get("c_open") or not r.get("c_best") or r["c_open"] - r["c_best"] <= 1:
            continue
        span, trace = r["c_open"] - r["c_best"], r.get("trace") or []
        suppliers = list(dict.fromkeys(e["actor"] for e in trace if e.get("actor") != "buyer"))
        for sup in suppliers:
            offer = ask = move = None
            seq = []
            for e in trace:
                m = e.get("move") or {}
                if e["actor"] == "buyer":
                    if (m.get("supplier_id") or suppliers[0]) != sup:
                        continue
                    cs = [
                        c for c in (_cost(case, t.get("terms", t)) for t in m.get("term_sheets") or []) if c is not None
                    ]
                    new = min(cs) if cs else None
                    move = (
                        (new - ask) / span
                        if new is not None and ask is not None
                        else (0.0 if ask is not None else None)
                    )
                    ask = new if new is not None else ask
                elif e["actor"] == sup:
                    sheets = [m.get("terms") or {}] + [a.get("terms") or {} for a in m.get("alternatives") or []]
                    cs = [
                        c for c in (_cost(case, t) for t in sheets if t.get("unit_price") is not None) if c is not None
                    ]
                    new = min(cs) if cs else None
                    seq.append(
                        {
                            "case": case["case_id"],
                            "sup": sup,
                            "cues": {normalise(x) for x in e.get("reasons") or []},
                            "step": (offer - new) / span if new is not None and offer is not None else None,
                            "move": move,
                            "status": m.get("status"),
                        }
                    )
                    offer = new if new is not None else offer
            for i, x in enumerate(seq):
                x["next"] = seq[i + 1] if i + 1 < len(seq) else None
            rows += seq
    said, by = {}, {}
    for x in rows:
        for cue in x["cues"]:
            said.setdefault(cue, set()).add(x["sup"])
            cell = by.setdefault(cue, {}).setdefault(
                x["case"], {"replies": 0, "next_step_pct": [], "per_eur_of_our_move": [], "next_final": []}
            )
            cell["replies"] += 1
            nxt = x["next"]
            if nxt is None:
                continue
            cell["next_final"].append(int(nxt["status"] == "final_offer"))
            if nxt["step"] is not None:
                cell["next_step_pct"].append(round(100 * nxt["step"], 1))
                if nxt["move"] and nxt["move"] > 0.005:
                    cell["per_eur_of_our_move"].append(round(nxt["step"] / nxt["move"], 2))
    out = []
    for cue, cells in by.items():
        if len(said[cue]) < MIN_SUPPLIERS or sum(c["replies"] for c in cells.values()) < MIN_REPLIES:
            continue
        for cell in cells.values():  # a bounded sample per case keeps the file small and the medians honest
            for k in ("next_step_pct", "per_eur_of_our_move", "next_final"):
                cell[k] = cell[k][:: max(1, len(cell[k]) // KEEP)][:KEEP]
        out.append({"cue": cue, "suppliers": len(said[cue]), "by_case": cells})
    return sorted(out, key=lambda c: -sum(x["replies"] for x in c["by_case"].values()))


if __name__ == "__main__":
    rows = build()
    OUT.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    print(f"{len(rows)} cases -> {OUT.relative_to(ROOT)}")
    for row in rows:
        print(row)
    cues = build_cues()
    CUES.write_text(json.dumps(cues, indent=0, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(cues)} recurring supplier sentences -> {CUES.relative_to(ROOT)}")
