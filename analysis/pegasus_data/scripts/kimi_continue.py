"""Second pass: make Kimi K3 write the full answer from its own notes (the end of its reasoning) and
its truncated beginning, with low reasoning so the output budget goes to the text."""
import json
import os
import sys
import time

import httpx

from arena_kit.cli import load_env

SP = "/tmp/claude-1000/-home-heezo/59742ee3-ebd1-4af1-9297-9691f27834d9/scratchpad"
load_env()
prompt = open(f"{SP}/kimi_prompt.md", encoding="utf-8").read()
partial = open(f"{SP}/kimi_answer.md", encoding="utf-8").read()
reasoning = open(f"{SP}/kimi_reasoning.md", encoding="utf-8").read()
start = int(os.environ.get("NOTES_FROM", "261958"))
notes = reasoning[start:]
user2 = ("Here are your own working notes from your analysis (verbatim, the final synthesis part):\n\n<<<<< NOTES >>>>>\n" + notes +
         "\n<<<<< END NOTES >>>>>\n\nYour answer above was cut off by the output limit right after section 1 began. "
         "Now write the COMPLETE answer in French, all sections 1 to 12 of your plan, in full detail (rules, evidence, pseudo-code, "
         "the loophole table L1-L30 with gain and risk of a 0, the 12-hour plan with the 10 probes and success criteria, the Sunday risks). "
         "Do not re-derive or re-analyse: everything is in your notes. Start directly at '## 1.' and write until the end.")
body = {"model": "moonshotai/Kimi-K3", "messages": [
    {"role": "system", "content": "You are a world-class procurement negotiation strategist, game theorist and software architect, and an expert at finding exploitable mechanics in rule-based systems and scripted LLM agents. You answer in French."},
    {"role": "user", "content": prompt},
    {"role": "assistant", "content": partial},
    {"role": "user", "content": user2}],
    "max_tokens": int(os.environ.get("MAXTOK", "100000")), "reasoning_effort": os.environ.get("EFFORT", "low"), "stream": True, "stream_options": {"include_usage": True}}
print(f"notes: {len(notes):,} chars; total prompt ~{(len(prompt) + len(partial) + len(user2)) // 3.6:,.0f} tokens", flush=True)
if "--dry" in sys.argv:
    sys.exit(0)
base, key = os.environ["LLM_BASE_URL"].rstrip("/"), os.environ["LLM_API_KEY"]
out_a, out_r = open(f"{SP}/kimi_answer2.md", "w"), open(f"{SP}/kimi_reasoning2.md", "w")
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
