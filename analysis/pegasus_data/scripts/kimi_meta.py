"""Build the meta-prompt (everything we know) and ask Kimi K3 on Nebius, reasoning at max, streaming to files.
Usage: uv run python kimi_meta.py [--dry]   (run from the starter-kit; the LLM key is read from its .env)"""
import glob
import json
import os
import sys
import time

import httpx

from arena_kit.cli import load_env

SP = "/tmp/claude-1000/-home-heezo/59742ee3-ebd1-4af1-9297-9691f27834d9/scratchpad"
KIT = os.path.expanduser("~/tacto/negotiation-arena-kit")
CW = os.path.expanduser("~/tacto/codex-work")
load_env()


def read(p):
    return open(p, encoding="utf-8").read()


def section(title, body, lang=""):
    return f"\n\n<<<<< {title} >>>>>\n" + (f"```{lang}\n{body}\n```" if lang else body) + f"\n<<<<< END {title} >>>>>\n"


def results_table():
    rows = []
    for f in sorted(glob.glob(f"{CW}/arena-data/sessions/P*.json")):
        d = json.load(open(f))
        s = d["session"]
        r = s.get("result") or {}
        if not r.get("ended"):
            continue
        t = r.get("terms") or {}
        idx = t.get("index_clause")
        idx_s = f"{idx.get('series')}/db{idx.get('deadband_pct')}/share{idx.get('material_share')}" if isinstance(idx, dict) else "none"
        cb = r.get("cost_breakdown") or {}
        rows.append(f"{s['case_id'][5:]} {s['session_id'][:8]} score={r.get('score', 0):.3f} end={s.get('end_reason')} rounds={s.get('rounds')} deal={'yes' if r.get('deal') else 'no'} "
                    f"sup={r.get('supplier_id')} price={t.get('unit_price')} pay={t.get('payment_days')} eff={t.get('effective_date')} months={t.get('contract_months')} lead={t.get('lead_time_days')} "
                    f"idx={idx_s} inco={t.get('incoterm')} ppm={t.get('ppm_commitment')} cb={t.get('chargeback_eur_per_complaint')} tool={t.get('tooling_eur')} vol={t.get('volume_per_year')} "
                    f"c_open={r.get('c_open')} c_deal={r.get('c_deal')} c_alt={r.get('c_alt')} c_best={r.get('c_best')} relationship={round(cb.get('relationship', 0))} index_cost={round(cb.get('index_clause', 0) + cb.get('index_risk', 0))} payment_cost={round(cb.get('payment_terms', 0))}")
    return "\n".join(rows)


def live_summary():
    d = json.load(open(f"{SP}/live.json"))
    bots = "\n".join(f"{b['case_id']}: record {b['best']:.3f} by {b.get('holder')}" + (f" ({json.dumps({k: v for k, v in b.items() if k not in ('case_id', 'best', 'holder')})})" if len(b) > 3 else "") for b in d["bots"])
    teams = "\n".join(f"{t.get('rank')}. {t.get('name')}: best_mean {t.get('best_mean')} bots_played {t.get('bots_played')} records {t.get('records')}" for t in d["teams"][:12])
    return f"Practice leaderboard (now):\n{teams}\n\nPer-case records (best score by any team):\n{bots}"


def build(level):
    parts = [read(f"{SP}/kimi_narrative.md")]
    parts.append(section("OFFICIAL BRIEF (brief/brief.md)", read(f"{KIT}/brief/brief.md")))
    parts.append(section("OFFICIAL API AND RULES (brief/api.md)", read(f"{KIT}/brief/api.md")))
    parts.append(section("DATA PACKAGE README", read(f"{KIT}/data/README.md") + "\n\n" + read(f"{KIT}/data/KNOWN_ISSUES.md")))
    parts.append(section("EXACT COST FUNCTION (starter-kit/arena_kit/cost.py, the arena uses the same arithmetic)", read(f"{KIT}/starter-kit/arena_kit/cost.py"), "python"))
    cases = json.load(open(f"{CW}/arena-data/cases-practice.json"))
    parts.append(section("PRACTICE CASE FILES (cases-practice.json, compact)", json.dumps(cases, ensure_ascii=False, separators=(",", ":"))))
    parts.append(section("LIVE LEADERBOARD AND RECORDS", live_summary()))
    parts.append(section("ALL OUR ENDED PRACTICE SESSIONS (one line each; costs in EUR; 'relationship' = relationship charge in the deal)", results_table()))
    parts.append(section("CODEX INTELLIGENCE: LESSONS", read(f"{CW}/intel/generated/LESSONS.md")))
    parts.append(section("CODEX INTELLIGENCE: SUPPLIER PROFILES", read(f"{CW}/intel/generated/PROFILES.md")))
    parts.append(section("CODEX INTELLIGENCE: RULES", read(f"{CW}/intel/generated/RULES.md")))
    # replays: best 2 per case always; failures only at level >= 2
    files = sorted(glob.glob(f"{SP}/traces/*.txt"))
    chosen = []
    for f in files:
        head = read(f).split("\n", 1)[0]
        sc = float(head.split("score ")[1].split(" ")[0])
        chosen.append((f[len(SP) + 8:11], sc, f))
    by = {}
    for cid, sc, f in chosen:
        by.setdefault(cid, []).append((sc, f))
    rep = []
    for cid, lst in sorted(by.items()):
        lst.sort(reverse=True)
        keep = lst[:2] + ([x for x in lst[2:]] if level >= 2 else [])
        for sc, f in keep:
            rep.append(read(f))
    parts.append(section("FULL REPLAYS OF OUR NEGOTIATIONS (team view: e-mails as sent, terms, statuses, claim results; the bot's own words)", "\n\n=====\n\n".join(rep)))
    parts.append(section("OUR CODE: pegasus/economics.py", read(f"{KIT}/starter-kit/pegasus/economics.py"), "python"))
    parts.append(section("OUR CODE: pegasus/adapt.py", read(f"{KIT}/starter-kit/pegasus/adapt.py"), "python"))
    if level >= 1:
        parts.append(section("OUR CODE: pegasus/agent.py (the negotiation logic)", read(f"{KIT}/starter-kit/pegasus/agent.py"), "python"))
    parts.append("\n\nNow produce the full strategic answer in French as requested in MISSION / WHAT WE WANT FROM YOU. Be exhaustive on loopholes and on the general mechanisms; give pseudo-code; cite evidence.")
    return "".join(parts)


def ask(prompt, max_tokens):
    base = os.environ["LLM_BASE_URL"].rstrip("/")
    key = os.environ["LLM_API_KEY"]
    body = {"model": "moonshotai/Kimi-K3", "messages": [
        {"role": "system", "content": "You are a world-class procurement negotiation strategist, game theorist and software architect, and an expert at finding exploitable mechanics in rule-based systems and scripted LLM agents. You reason exhaustively, verify every claim against the evidence given, and answer in French."},
        {"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "reasoning_effort": "max", "stream": True, "stream_options": {"include_usage": True}}
    out_a, out_r = open(f"{SP}/kimi_answer.md", "w"), open(f"{SP}/kimi_reasoning.md", "w")
    n_a = n_r = 0
    t0 = time.time()
    with httpx.Client(timeout=httpx.Timeout(600.0, read=3600.0)) as c, c.stream("POST", f"{base}/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"}) as r:
        if r.status_code != 200:
            r.read()
            print("HTTP", r.status_code, r.text[:800], flush=True)
            return r.status_code, r.text
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
                print("usage:", json.dumps(ch["usage"])[:400], flush=True)
            for choice in ch.get("choices") or []:
                d = choice.get("delta") or {}
                if d.get("reasoning_content"):
                    out_r.write(d["reasoning_content"]); n_r += len(d["reasoning_content"])
                if d.get("content"):
                    out_a.write(d["content"]); n_a += len(d["content"])
                if choice.get("finish_reason"):
                    print("finish:", choice["finish_reason"], flush=True)
            if (n_a + n_r) % 20000 < 50:
                out_a.flush(); out_r.flush()
                print(f"{time.time() - t0:.0f}s reasoning {n_r} chars, answer {n_a} chars", flush=True)
    out_a.close(); out_r.close()
    print(f"done in {time.time() - t0:.0f}s: reasoning {n_r} chars, answer {n_a} chars", flush=True)
    return 200, ""


if __name__ == "__main__":
    level = int(os.environ.get("KIMI_LEVEL", "2"))
    prompt = build(level)
    open(f"{SP}/kimi_prompt.md", "w").write(prompt)
    print(f"prompt: {len(prompt):,} chars (~{len(prompt) // 3.6:,.0f} tokens) at level {level}", flush=True)
    if "--dry" in sys.argv:
        sys.exit(0)
    for max_tokens in (120000, 64000, 32000):
        code, text = ask(prompt, max_tokens)
        if code == 200:
            break
        if "context" in text.lower() or "too long" in text.lower() or "length" in text.lower():
            level -= 1
            if level < 0:
                break
            prompt = build(level)
            print(f"retry at level {level}: {len(prompt):,} chars", flush=True)
        elif "max_tokens" not in text.lower():
            break
