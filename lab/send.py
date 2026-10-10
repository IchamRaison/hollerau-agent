"""Send prepared messages to one supplier, fast enough for the 60-second clock, and print each reply.

  HOLLERAU_VALIDATED="..." uv run python -m lab.send case:D01 messages.txt [--supplier sup:DEMO-F1] [--label try1]

messages.txt: one or more message bodies separated by a line containing only ---
No term sheet is sent: the supplier's quote stands. The session is closed by a walk-away at the end,
and the full record (replies, trace, back office) goes to data/lab/<label>.json.
"""

import argparse
import time
from pathlib import Path

from arena_kit.cli import load_env
from hollerau.sessions import require_validation

from .harness import run


def main():
    p = argparse.ArgumentParser()
    p.add_argument("case_id")
    p.add_argument("file")
    p.add_argument("--supplier")
    p.add_argument("--label", default=time.strftime("send-%H%M%S"))
    a = p.parse_args()
    load_env()
    bodies = [b.strip() for b in Path(a.file).read_text().split("\n---\n") if b.strip()]
    require_validation(f"send {len(bodies)} message(s) to {a.case_id}", 1, quota=a.case_id.startswith("case:P"))
    script = [lambda ctx, b=b: {"subject": ctx.case["title"], "body": b} for b in bodies]
    rec = run(a.case_id, script, a.label, supplier=a.supplier)
    for r in rec["rounds"]:
        print(f"\n=== reply {r['round']} | status {r['status']} | {r['seconds']} s | terms {r['terms']}\n{r['body']}")
        for att in r["attachments"]:
            print(f"--- attachment {att['name']}\n{att['text'][:1500]}")
    print(f"\nsession {rec['session_id']} -> data/lab/{a.label}.json (trace and back office inside)")


if __name__ == "__main__":
    main()
