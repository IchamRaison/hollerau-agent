"""uv run python lab/dsh_suppliers.py [--check]  ->  hollerau/dsh/suppliers.json

One record per supplier we have played, from every finished game in `analysis/pegasus_data/`:
who signs, how its offers answered our asks, when its final offer came, what followed a push after
it, what it wrote and what its back office noted. `hollerau.dsh.recognition` compares a live
thread with these records. Offline: reads the archive, opens no session.

--check replays every archived reply as if its case were new (its records left out) and prints how
well the closest records foretold the status and the step of that reply.
"""

import glob
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hollerau.dsh.recognition import SIGNED  # noqa: E402

OUT = ROOT / "hollerau" / "dsh" / "suppliers.json"
DATA = ROOT / "analysis" / "pegasus_data"
BOILER = ("My call:", "Read the buyer's e-mail", "quote attached", "order confirmation attached", "delivery schedule")
CHECKED = (
    (re.compile(r"We checked the (.+?) data you cited; it holds and we took it into account"), "took it into account"),
    (
        re.compile(r"We checked the (.+?) data you cited; it holds, but it does not change"),
        "true, but it changed nothing",
    ),
    (re.compile(r"We have already taken that (.+?) data into account"), "already counted"),
    (re.compile(r"The (.+?) data you cite does not concern"), "not about this part or company"),
    (re.compile(r"The (.+?) figures you cite do not match"), "wrong figure: it cost trust"),
)
MIN_ROWS = 5


def _cases():
    cases = {}
    for name in ("practice", "sandbox"):
        data = json.loads((DATA / f"cases-{name}.json").read_text())
        data = data if isinstance(data, list) else data.get("cases", data)
        for c in data.values() if isinstance(data, dict) else data:
            cases[c["case_id"]] = c
    return cases


def _cost(case, terms, fill):
    from arena_kit.cost import total_cost

    try:
        c = total_cost(case, {**fill, **{k: v for k, v in (terms or {}).items() if v is not None}})
        return None if c == float("inf") else c
    except Exception:
        return None


def threads():
    """Every supplier thread of the archive as recognition steps, with what only a finished game
    shows: the back office, the reasons, the result."""
    cases, out = _cases(), []
    for path in sorted(glob.glob(str(DATA / "sessions" / "*.json"))):
        d = json.loads(Path(path).read_text())
        s = d.get("session") or d
        r, case = s.get("result") or {}, cases.get(s.get("case_id"))
        if not case or not r.get("trace"):
            continue
        trace = r["trace"]
        sups = sorted({e["actor"] for e in trace if e.get("actor") != "buyer"})
        notes = defaultdict(list)
        for m in d.get("backoffice") or []:
            text = str(m.get("text"))
            if not text.startswith(BOILER):
                notes[m.get("supplier_id")].append(
                    re.sub(r"\(.*?\)", "", re.sub(r"\d+(?:[.,]\d+)*", "#", text)).strip()
                )
        by = defaultdict(list)
        for e in trace:
            m = e.get("move") or {}
            if e.get("actor") == "buyer":
                sid = m.get("supplier_id") or (sups[0] if len(sups) == 1 else None)
                if sid:
                    by[sid].append(("B", e, m))
            else:
                by[e["actor"]].append(("S", e, m))
        for sid, events in by.items():
            first = next((m for w, _, m in events if w == "S"), None)
            if not first:
                continue
            fill = {k: v for k, v in (first.get("terms") or {}).items() if k != "unit_price"}
            steps, reasons = [], []
            for w, e, m in events:
                if w == "B":
                    kind = m.get("type") or "message"
                    if kind not in ("message", "timeout"):
                        continue  # our accept or walk-away closes the thread: not an e-mail it answers
                    sheets = m.get("term_sheets") if isinstance(m.get("term_sheets"), list) else []
                    costs = [c for t in sheets if (c := _cost(case, t.get("terms") or t, fill)) is not None]
                    steps.append(
                        {"who": "B", "cost": min(costs) if costs else None, "sheets": len(sheets), "kind": kind}
                    )
                else:
                    terms = m.get("terms") or {}
                    fill = {**fill, **{k: v for k, v in terms.items() if k != "unit_price" and v is not None}}
                    gone = m.get("status") in ("walked_away", "no_bid") or terms.get("unit_price") is None
                    steps.append(
                        {
                            "who": "S",
                            "cost": None if gone else _cost(case, terms, fill),
                            "status": m.get("status"),
                            "text": m.get("text") or "",
                        }
                    )
                    reasons += e.get("reasons") or []
            out.append(
                {
                    "session": s["session_id"],
                    "case": s["case_id"].split(":")[-1],
                    "supplier": sid.split(":")[-1],
                    "case_type": case.get("type"),
                    "category_goal": case["buyer"].get("category_goal"),
                    "bidders": len(sups),
                    "negotiable": case["negotiable"],
                    "score": r.get("score"),
                    "deal_with": (r.get("supplier_id") or "").split(":")[-1] if r.get("deal") else None,
                    "end_reason": s.get("end_reason"),
                    "room": (r["c_open"] - r["c_best"]) / r["c_open"] if r.get("c_open") and r.get("c_best") else None,
                    "steps": steps,
                    "reasons": reasons,
                    "notes": notes.get(sid, []),
                }
            )
    return out


def _law(rows):
    """How the supplier's step relates to the gap between its offer and our ask, over the replies
    where we asked below its offer and had moved."""
    from hollerau.dsh.recognition import q, spread

    asked = [r for r in rows if r.get("gap", 0) > 0.005 and "step" in r]
    out = {"replies": len(asked)}
    if len(asked) < MIN_ROWS:
        return {**out, "law": "too few replies to say"}
    moved = [r for r in asked if r["step"] > 1e-6]
    out["it_moved"] = round(len(moved) / len(asked), 2)
    dearer = [r for r in asked if r["step"] < -1e-6]
    if len(dearer) > len(asked) / 2:
        out["step_pct_of_its_quote"] = spread([100 * r["step"] for r in asked], 2)
        return {**out, "law": "its sheet came back dearer for us than its previous one: it priced the terms we asked"}
    if moved:
        shares, steps = [r["share"] for r in moved], [r["step"] for r in moved]
        out["share_of_gap"] = spread(shares, 2)
        out["step_pct_of_its_quote"] = spread([100 * x for x in steps], 2)
        tight = lambda v: (q(v, 0.75) - q(v, 0.25)) / q(v, 0.5) if q(v, 0.5) else 9.0  # noqa: E731
        if out["it_moved"] < 0.25:
            out["law"] = "it holds its price"
        elif q(shares, 0.5) >= 0.9:
            out["law"] = "it meets our ask"
        elif tight(steps) < 0.15 and tight(steps) < tight(shares):
            out["law"] = "a fixed step"
        else:
            out["law"] = "a share of the gap"
    else:
        out["law"] = "it holds its price"
    return out


def _bins(rows, key, edges, extra=None):
    """Rows cut by `key` (a share of its quote) into bands: for each band with enough replies, how
    many, the median step, and whatever `extra` adds."""
    out = []
    for lo, hi in zip(edges, edges[1:], strict=False):
        v = [r for r in rows if r.get(key) is not None and lo <= r[key] < hi]
        steps = [r["step"] for r in v if "step" in r]
        if len(v) < 4 or not steps:
            continue
        label = f"{100 * lo:g} to {100 * hi:g} %" if hi < 9 else f"over {100 * lo:g} %"
        row = {"band": label, "replies": len(v), "its_step_pct_of_its_quote": round(100 * median(steps), 2)}
        if extra:
            row.update(extra(v))
        out.append(row)
    return out


def record(games):
    """One supplier's record from all its threads."""
    from hollerau.dsh.recognition import how_we_answered, replies, sentences, signature, spread

    t0 = games[0]
    rows = [(g, replies(g["steps"])) for g in games]
    flat = [r for _, rr in rows for r in rr]
    opening_text = next((s["text"] for s in t0["steps"] if s["who"] == "S"), "")
    role, company = signature(opening_text)
    rec = {
        "supplier": t0["supplier"],
        "case": t0["case"],
        "who_signs": role,
        "company": company,
        "case_type": t0["case_type"],
        "category_goal": t0["category_goal"],
        "bidders": t0["bidders"],
        "negotiable": t0["negotiable"],
        "games": len(games),
        "replies": len(flat),
    }
    rooms = [g["room"] for g in games if g["room"] is not None]
    if rooms:
        rec["best_deal_possible_below_cheapest_quote_pct"] = round(100 * median(rooms), 1)
    first = [r for r in flat if r["k"] == 1]
    rec["first_reply"] = _law(first)
    asks = [100 * r["ask_below_quote"] for r in first if "ask_below_quote" in r]
    if asks:
        rec["first_reply"]["our_asks_were_pct_below_its_quote"] = spread(asks, 1)
        if rec["first_reply"].get("law") and max(asks) - min(asks) < 3:
            rec["first_reply"]["law"] = "our first asks were all alike: its rule is not told apart"
    by_depth = _bins(first, "ask_below_quote", [0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 9.9])
    if len(by_depth) > 1:
        rec["first_reply"]["by_how_far_below_its_quote_we_asked"] = by_depth
    later = [r for r in flat if r["k"] >= 2 and r["prev_status"] == "open" and not r.get("timeout")]
    rec["later_replies"] = _law([r for r in later if r.get("our_move", 1) > 1e-6])
    by_gap = _bins(
        [r for r in later if r.get("our_move", 1) > 1e-6], "gap", [0.005, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20, 9.9]
    )
    if len(by_gap) > 1:
        rec["later_replies"]["by_gap_between_its_offer_and_our_ask"] = by_gap
    by_move = _bins(
        [r for r in later if "our_move" in r and r.get("gap", 0) > 0.005],
        "our_move",
        [-9.9, 1e-6, 0.003, 0.01, 0.03, 9.9],
        lambda v: {
            "it_moved": round(sum(1 for r in v if r.get("step", 0) > 1e-6) / len(v), 2),
            "answered_with_its_final_offer": round(sum(1 for r in v if r["status"] == "final_offer") / len(v), 2),
        },
    )
    labels = {"-990 to 0.0001 %": "we did not move", "0.0001 to 0.3 %": "under 0.3 %", "over 3 %": "over 3 %"}
    for row in by_move:
        row["band"] = labels.get(row["band"], row["band"])
    if by_move:
        rec["later_replies"]["by_size_of_our_move"] = by_move
    still = [r for r in later if "step" in r and r.get("gap", 0) > 0.005 and r.get("our_move", 1) <= 1e-6]
    depth = []
    for g, rr in rows:
        asks_ = [r["ask_below_quote"] for r in rr if "ask_below_quote" in r]
        offers = [r["offer_below_quote"] for r in rr if "offer_below_quote" in r]
        if asks_ and offers:
            depth.append({"ask_below_quote": sum(asks_) / len(asks_), "step": max(offers), "score": g["score"]})
    by_ask = _bins(depth, "ask_below_quote", [0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 9.9])
    if len(by_ask) > 1:
        rec["games_by_depth_of_our_asks"] = [
            {
                "our_asks_averaged_below_its_quote": b["band"],
                "games": b["replies"],
                "its_deepest_offer_pct_below_its_quote": b["its_step_pct_of_its_quote"],
            }
            for b in by_ask
        ]
    if still:
        rec["later_replies"]["when_we_did_not_move"] = {
            "replies": len(still),
            "it_moved": round(sum(1 for r in still if r["step"] > 1e-6) / len(still), 2),
        }
    by = defaultdict(Counter)
    for r in flat:
        by[str(min(r["k"], 8))][r["status"]] += 1
    rec["status_by_reply"] = {k: dict(v) for k, v in sorted(by.items())}
    came = Counter()
    for _, rr in rows:
        k = next((r["k"] for r in rr if r["status"] == "final_offer"), None)
        if k:
            came[str(k)] += 1
    rec["final_offer_came_at_reply"] = dict(sorted(came.items()))
    after = defaultdict(Counter)
    for r in flat:
        if r["prev_status"] == "final_offer":
            after[how_we_answered(r)][r["status"]] += 1
    rec["after_its_final_offer"] = {k: dict(v) for k, v in after.items()}
    left = [r for r in flat if r["status"] in ("walked_away", "no_bid")]
    if left:
        rec["it_left"] = {
            "games": len(left),
            "at_reply": dict(sorted(Counter(str(r["k"]) for r in left).items())),
            "after": dict(Counter(f"its status was {r['prev_status']}; {how_we_answered(r)}" for r in left)),
        }
    agreed = [100 * r["offer_below_quote"] for r in flat if r["status"] == "agreed" and "offer_below_quote" in r]
    if agreed:
        rec["it_agreed_to_our_ask"] = {
            "replies": len(agreed),
            "at_pct_below_its_quote": spread(agreed, 1),
            "note": "it took our number as it stood: that ask was within what it accepts",
        }
    deep = [100 * r["offer_below_quote"] for r in flat if "offer_below_quote" in r]
    if deep:
        rec["deepest_offer_below_its_quote_pct"] = round(max(deep), 1)
    args = defaultdict(Counter)
    for g in games:
        for reason in g["reasons"]:
            for pattern, verdict in CHECKED:
                m = pattern.search(reason)
                if m:
                    args[m.group(1)][verdict] += 1
    rec["arguments"] = {k: dict(v) for k, v in sorted(args.items())}
    notes = Counter(n for g in games for n in g["notes"])
    rec["inside_notes"] = {n: c for n, c in notes.most_common(8)}
    said = Counter()
    mails = 0
    for g in games:
        for s in g["steps"]:
            if s["who"] == "S" and s.get("text"):
                mails += 1
                said.update(x for x in set(sentences(s["text"])) if not SIGNED.match(x))
    rec["_said"] = {s: c / mails for s, c in said.items() if c / mails >= 0.15}
    mine = [g for g in games if g["score"] is not None and (g["bidders"] == 1 or g["deal_with"] == g["supplier"])]
    seen, best = set(), []
    for g, rr in sorted(((g, replies(g["steps"])) for g in mine), key=lambda x: -x[0]["score"]):
        asks_ = tuple(round(100 * r["ask_below_quote"], 1) if "ask_below_quote" in r else None for r in rr)
        if asks_ in seen or not rr:
            continue
        seen.add(asks_)
        best.append(
            {
                "score": round(g["score"], 3),
                "ended": g["end_reason"],
                "our_asks_pct_below_its_quote": list(asks_),
                "its_offers_pct_below_its_quote": [
                    round(100 * r["offer_below_quote"], 1) if "offer_below_quote" in r else None for r in rr
                ],
                "its_status": [r["status"] for r in rr],
                "sheets_per_mail": [r["sheets"] for r in rr],
            }
        )
        if len(best) == 3:
            break
    rec["best_games"] = best
    scores = [g["score"] for g in mine if g["score"] is not None]
    if scores:
        rec["our_scores"] = {"games": len(scores), "median": round(median(scores), 3), "best": round(max(scores), 3)}
    return rec


def across(games):
    """What held whoever the supplier was: when suppliers left, and when they never did."""
    from hollerau.dsh.recognition import how_we_answered, replies

    left, sheet_while_open, timeouts = Counter(), 0, 0
    for g in games:
        for r in replies(g["steps"]):
            timeouts += bool(r.get("timeout"))
            if r["prev_status"] == "open" and "gap" in r:
                sheet_while_open += 1
            if r["status"] in ("walked_away", "no_bid"):
                left[f"its status was {r['prev_status']}; {how_we_answered(r)}"] += 1
    return {
        "threads": len(games),
        "suppliers": len({(g["case"], g["supplier"]) for g in games}),
        "e_mails_with_a_term_sheet_sent_while_its_status_was_open": sheet_while_open,
        "of_which_it_answered_by_leaving": sum(
            c
            for k, c in left.items()
            if k.startswith("its status was open") and "60 seconds" not in k and "note" not in k
        ),
        "turns_we_let_time_out": timeouts,
        "when_suppliers_left": dict(left.most_common()),
    }


def build(games=None):
    games = games or threads()
    by = defaultdict(list)
    for g in games:
        by[(g["case"], g["supplier"])].append(g)
    recs = [record(v) for _, v in sorted(by.items())]
    writers = Counter(s for r in recs for s in r["_said"])
    for r in recs:
        said = r.pop("_said")
        # a sentence weighs by how few suppliers write it: the persona shows in what only it says
        r["writes"] = {s: round(1 / writers[s], 2) for s, _ in sorted(said.items(), key=lambda x: -x[1])[:40]}
    return recs


def check(games):
    """Each archived reply foretold from the records of the OTHER cases: the weight given to the
    status that came, and the error on the step, against two plain guesses."""
    from hollerau.dsh import recognition as rec

    all_recs = build(games)
    by_case = defaultdict(list)
    for g in games:
        by_case[g["case"]].append(g)
    lines = []
    for case, gs in sorted(by_case.items()):
        others = [r for r in all_recs if r["case"] != case]  # the records of the other cases only
        flat_shares = [x for r in others for x in ([(r["later_replies"].get("share_of_gap") or [None] * 3)[1]]) if x]
        plain = median(flat_shares) if flat_shares else 0.15
        hit, base, err, err_plain, n_status, n_step = 0.0, 0.0, [], [], 0, 0
        for g in gs[:60]:
            steps = g["steps"]
            opening = next((s["cost"] for s in steps if s["who"] == "S" and s.get("cost")), None)
            first_text = next((s["text"] for s in steps if s["who"] == "S"), "")
            context = {
                "who_signs": rec.signature(first_text)[0],
                "case_type": g["case_type"],
                "category_goal": g["category_goal"],
                "bidders": g["bidders"],
                "negotiable": g["negotiable"],
            }
            idx = [i for i, s in enumerate(steps) if s["who"] == "S"]
            for i in idx[1:]:
                if steps[i - 1]["who"] != "B":
                    continue
                prefix = steps[: i - 1]
                said = {x for s in prefix if s["who"] == "S" for x in rec.sentences(s.get("text"))}
                found = rec.recognise(context, prefix, said, pool=others)
                look = rec.outlook(found).get("status_of_its_next_reply") or {}
                actual = steps[i]
                hit += look.get(actual["status"], 0.0)
                base += 0.25
                n_status += 1
                standing = next((s["cost"] for s in reversed(prefix) if s["who"] == "S" and s.get("cost")), None)
                ask = steps[i - 1].get("cost")
                if standing and ask and actual.get("cost") and opening and (standing - ask) / opening > 0.005:
                    f = rec.forecast(found, standing, ask, opening)
                    if f and "if_it_moves_its_sheet_would_cost_us_eur" in f:
                        predicted = f["if_it_moves_its_sheet_would_cost_us_eur"]["expected"]
                        err.append(abs(predicted - actual["cost"]) / opening)
                        err_plain.append(abs(standing - plain * (standing - ask) - actual["cost"]) / opening)
                        n_step += 1
        if n_status:
            lines.append(
                f"{case}: {n_status} replies; weight on the status that came {hit / n_status:.2f} "
                f"(even guess {base / n_status:.2f}); step error, share of its quote: "
                f"records {100 * median(err):.2f} % against one share for all {100 * median(err_plain):.2f} % ({n_step} steps)"
                if err
                else f"{case}: {n_status} replies; weight on the status that came {hit / n_status:.2f}"
            )
    return lines


if __name__ == "__main__":
    games = threads()
    if "--check" in sys.argv:
        print("\n".join(check(games)))
    else:
        recs = build(games)
        doc = {"suppliers": recs, "across_all_suppliers": across(games)}
        OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(doc["across_all_suppliers"], indent=1))
        print(f"{len(recs)} suppliers from {len(games)} threads -> {OUT.relative_to(ROOT)}")
        for r in recs:
            print(
                f"  {r['case']}/{r['supplier']:8} {str(r['who_signs']):20} games {r['games']:3}  first: {r['first_reply'].get('law')}"
                f"  later: {r['later_replies'].get('law')} {r['later_replies'].get('share_of_gap')}"
                f"  final at {r['final_offer_came_at_reply']}"
            )
