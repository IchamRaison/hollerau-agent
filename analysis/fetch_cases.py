"""Save the practice and sandbox case files (GET /v1/cases - no session, no quota)."""

import json

from _common import CASES

from arena_kit import ArenaClient
from arena_kit.cli import load_env

load_env()
client = ArenaClient()
CASES.mkdir(parents=True, exist_ok=True)
for name in ("practice", "sandbox"):
    cases = client.cases(name)
    (CASES / f"{name}.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False, default=str))
    print(f"{name}: {len(cases)} case files -> {CASES / (name + '.json')}")
