"""uv run python lab/dsh_archives.py  ->  hollerau/dsh/observations.json

What our finished games say about each case we have played: how far below the opening quote the
best acceptable deal sat. One row per case, from the exact figures of the arena's results
(`c_open`, `c_best`). The pilot shows the model the rows of OTHER cases with the same category
goal: a prior for how much room a kind of case holds - never the row of the case being played.
Offline: reads `analysis/pegasus_data/`, opens no session.
"""

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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


if __name__ == "__main__":
    rows = build()
    OUT.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    print(f"{len(rows)} cases -> {OUT.relative_to(ROOT)}")
    for row in rows:
        print(row)
