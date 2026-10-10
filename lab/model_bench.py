"""Compare LLMs on a recorded negotiation, offline: no arena session is opened.

For every supplier message of the recorded thread, the model gets the same prompt the kit's LLM agent
would get at that point and must answer with the agent's JSON. We measure latency and whether the
answer is usable. Reads tests/fixtures (case files and a recorded P01 session).

  uv run python -m lab.model_bench --name openai-x --base https://api.openai.com/v1 --model <id> \
      --key-env OPENAI_API_KEY --extra '{"reasoning_effort": "medium"}' --repeat 3
  uv run python -m lab.model_bench --name deepseek-flash --base https://api.deepseek.com/v1 \
      --model <id> --key-env DEEPSEEK_API_KEY --extra '{...}' --repeat 3

Results are appended to data/lab/model_bench.jsonl; `--report` prints the comparison table.
The quality of the chosen move is NOT scored here: read the saved answers side by side.
"""

import argparse
import json
import os
import statistics
import time
from pathlib import Path

import httpx

from arena_kit.agents.llm import SYSTEM, LLMAgent, parse
from arena_kit.cli import load_env

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
OUT = ROOT / "data" / "lab" / "model_bench.jsonl"


def prompts(session="P01-naive"):
    """(turn, system, user) for each point where the buyer had to answer."""
    rec = json.loads((FIX / "sessions" / f"{session}.json").read_text())
    case_id = rec["state"]["case_id"]
    cases = json.loads((FIX / "cases" / "practice.json").read_text())
    case = next(c for c in cases if c["case_id"] == case_id)
    agent = LLMAgent(lambda s, u: "")
    agent.case_id, agent.brief = case_id, agent.prepare(case)
    out = []
    for sup, thread in rec["threads"].items():
        msgs = thread["messages"]
        for i, m in enumerate(msgs):
            if m.get("from") != "buyer" and m.get("term_sheets"):
                out.append((len(out), SYSTEM, agent.render(case, {sup: msgs[: i + 1]})))
    return out


def call(base, model, key, system, user, extra, timeout):
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        **extra,
    }
    t0 = time.monotonic()
    r = httpx.post(
        f"{base.rstrip('/')}/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"}, timeout=timeout
    )
    took = time.monotonic() - t0
    r.raise_for_status()
    j = r.json()
    return took, j["choices"][0]["message"].get("content") or "", j.get("usage") or {}


def report():
    rows = [json.loads(x) for x in OUT.read_text().splitlines()] if OUT.exists() else []
    names = list(dict.fromkeys(r["name"] for r in rows))
    print("| Config | Calls | Median s | Worst s | Over 25 s | Valid JSON | Errors | Out tokens (median) |")
    print("|---|---|---|---|---|---|---|---|")
    for n in names:
        rs = [r for r in rows if r["name"] == n]
        ok = [r for r in rs if not r.get("error")]
        secs = sorted(r["seconds"] for r in ok) or [0]
        toks = [r["usage"].get("completion_tokens", 0) for r in ok] or [0]
        print(
            f"| {n} | {len(rs)} | {statistics.median(secs):.1f} | {secs[-1]:.1f} | {sum(s > 25 for s in secs)} "
            f"| {sum(r['valid'] for r in ok)}/{len(ok)} | {len(rs) - len(ok)} | {statistics.median(toks):.0f} |"
        )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report", action="store_true")
    p.add_argument("--name")
    p.add_argument("--base")
    p.add_argument("--model")
    p.add_argument("--key-env", default="LLM_API_KEY")
    p.add_argument("--extra", default="{}", help="JSON merged into the request, e.g. the reasoning setting")
    p.add_argument("--repeat", type=int, default=3)
    p.add_argument("--timeout", type=float, default=90.0)
    a = p.parse_args()
    if a.report:
        return report()
    load_env()
    key, extra = os.environ[a.key_env], json.loads(a.extra)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a") as f:
        for turn, system, user in prompts():
            for rep in range(a.repeat):
                row = {"name": a.name, "model": a.model, "extra": extra, "turn": turn, "rep": rep}
                try:
                    took, text, usage = call(a.base, a.model, key, system, user, extra, a.timeout)
                    try:
                        d = parse(text)
                        valid = d.get("action") in ("send", "accept", "walk_away") and bool(d.get("supplier_id"))
                    except Exception:
                        valid = False
                    row.update(seconds=round(took, 2), valid=valid, usage=usage, answer=text)
                except Exception as e:
                    row.update(error=str(e)[:300])
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                print(
                    a.name,
                    "turn",
                    turn,
                    "rep",
                    rep,
                    row.get("seconds"),
                    "valid" if row.get("valid") else row.get("error", "INVALID"),
                )
    report()


if __name__ == "__main__":
    main()
