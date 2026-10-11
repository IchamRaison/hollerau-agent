"""Focused follow-up to Kimi K3: the early-final distributor bots (P04/P07/P08/P18) and P11, with the
lot I threads (r15) and the best earlier threads. Same big context as the first call."""
import glob
import json
import os
import re
import sys
import time

import httpx

from arena_kit.cli import load_env

SP = "/tmp/claude-1000/-home-heezo/59742ee3-ebd1-4af1-9297-9691f27834d9/scratchpad"
load_env()
prompt = open(f"{SP}/kimi_prompt.md", encoding="utf-8").read()
plan = open(f"{SP}/kimi_answer.md", encoding="utf-8").read() + "\n\n" + open(f"{SP}/kimi_answer2.md", encoding="utf-8").read()


def compact_thread(path, body_chars=700):
    d = json.load(open(path))
    out = []
    for m in d.get("messages") or []:
        who = "BUYER" if m.get("from") == "buyer" else m.get("from", "?")
        sheets = [t.get("terms") for t in (m.get("term_sheets") or [])]
        body = re.sub(r"\s+", " ", m.get("body") or "")[:body_chars]
        cr = m.get("claim_results")
        out.append(f"[{who}] status={m.get('status') or (m.get('action') or {}).get('type') or 'message'} sheets={json.dumps(sheets)}"
                   + (f" claim_results={json.dumps(cr)}" if cr else "") + f"\n  body: {body}")
    return "\n".join(out)


parts = []
for f in sorted(glob.glob(f"{SP}/lotI/*.json")):
    cid = os.path.basename(f)[:3]
    if cid in ("P04", "P07", "P08", "P18", "P11", "P03"):
        parts.append(f"===== LOT I (r15, last night) {os.path.basename(f)} =====\n" + compact_thread(f))
for f in sorted(glob.glob(f"{SP}/threads/*.json")):
    cid = os.path.basename(f)[:3]
    if cid in ("P04", "P07", "P08", "P18", "P11"):
        th = json.load(open(f))
        for sup, t in th.items():
            tmp = f"{SP}/_tmp_thread.json"
            json.dump(t, open(tmp, "w"))
            parts.append(f"===== EARLIER SESSION {os.path.basename(f)} {sup} =====\n" + compact_thread(tmp, 500))
threads_txt = "\n\n".join(parts)
question = f"""Lot I results with your mechanisms implemented (r15): P01 0.956, P02 0.735 (our new best, exactly the clause package at 361.21/90), P03 0.903, P04 0.860, P05 0.732, P07 0.676, P08 0.471, P10 0.686, P11 0.710, P18 0.319. Mean 70.5 - below our previous bests on P01/P03/P07/P08/P11/P18. We then fixed (r16): all decisions in C_rel for strategic suppliers (P01's packages had drifted to 45/60-day payment), the nudge only when our schedule converged (on P11 a big step on a stall produced 'we are almost there' and a final at 45.50 instead of 45.00), and every alternative the bot ever listed is a mirror candidate (P08/P18 finals dropped the deadband-5 variants).

FOCUS NOW on the 'Dear customer' distributor bots and P11, the cases where we lose the most: P04 (sup:70620, record 0.874, we 0.860), P07 (sup:70610, record 0.812, we 0.676-0.715), P08 (sup:70710, record 0.916, we 0.471-0.659), P18 (sup:70740, record 0.727, we 0.319-0.575), P11 (sup:70140, record 0.885, we 0.710-0.794). Below are the full lot I threads for these cases (and P03) plus our best earlier threads. These bots send final_offer at round 2-3, so only our first two messages matter.

Derive from the threads, as precisely as you can: (1) how each bot computes its round-1 counter from our round-1 package (price, payment, months, index clause, deadband) and its final from our round-2 package; (2) what makes its final LOWER (anchor level, step size, which package it picks, deadband, contract months, payment rank, claims, answering its questions, the 'binding volume' line, asking for approval); (3) the exact round-1 and round-2 policy per bot family that reaches the record, expressed as GENERAL rules the agent can apply on a hidden case from the signals in the opening mail and the first reply (persona 'Dear customer', 'Preisliste and discount tiers', index clause offered, 'as a distributor', etc.); (4) for P08/P18: the fixed-price-vs-clause decision and how to get the deadband-5 or fixed price instead of deadband 0; (5) for P11: the exact concession path and wording that reached 45.00 (0.794) versus 45.50, and how to reach 44.4 (record). Answer in French, concrete numbers from the threads, pseudo-code for agent.py where useful, and a short probe plan (we have ~200 practice sessions left, 4 teammates). Keep it under 25,000 characters."""
body = {"model": "moonshotai/Kimi-K3", "messages": [
    {"role": "system", "content": "You are a world-class procurement negotiation strategist and reverse-engineer of scripted agents. You answer in French, concretely, with evidence from the threads."},
    {"role": "user", "content": prompt},
    {"role": "assistant", "content": plan},
    {"role": "user", "content": question + "\n\n<<<<< THREADS >>>>>\n" + threads_txt + "\n<<<<< END THREADS >>>>>"}],
    "max_tokens": int(os.environ.get("MAXTOK", "60000")), "reasoning_effort": os.environ.get("EFFORT", "high"), "stream": True, "stream_options": {"include_usage": True}}
print(f"threads: {len(threads_txt):,} chars; total ~{(len(prompt) + len(plan) + len(question) + len(threads_txt)) // 3.6:,.0f} tokens", flush=True)
if "--dry" in sys.argv:
    sys.exit(0)
base, key = os.environ["LLM_BASE_URL"].rstrip("/"), os.environ["LLM_API_KEY"]
out_a, out_r = open(f"{SP}/kimi_focus_answer.md", "w"), open(f"{SP}/kimi_focus_reasoning.md", "w")
n_a = n_r = 0
t0 = time.time()
with httpx.Client(timeout=httpx.Timeout(600.0, read=3600.0)) as c, c.stream("POST", f"{base}/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"}) as r:
    if r.status_code != 200:
        r.read()
        print("HTTP", r.status_code, r.text[:600], flush=True)
        sys.exit(1)
    for line in r.iter_lines():
        if not line.startswith("data: "):
            continue
        data = line[6:].strip()
        if data == "[DONE]":
            break
        try:
            ch = json.loads(data)
        except Exception:
            continue
        if ch.get("usage"):
            print("usage:", json.dumps(ch["usage"])[:300], flush=True)
        for choice in ch.get("choices") or []:
            d = choice.get("delta") or {}
            if d.get("reasoning_content"):
                out_r.write(d["reasoning_content"]); n_r += len(d["reasoning_content"])
            if d.get("content"):
                out_a.write(d["content"]); n_a += len(d["content"])
            if choice.get("finish_reason"):
                print("finish:", choice["finish_reason"], flush=True)
        if (n_a + n_r) % 20000 < 40:
            out_a.flush(); out_r.flush()
            print(f"{time.time() - t0:.0f}s reasoning {n_r} chars, answer {n_a} chars", flush=True)
out_a.close(); out_r.close()
print(f"done in {time.time() - t0:.0f}s: reasoning {n_r} chars, answer {n_a} chars", flush=True)
