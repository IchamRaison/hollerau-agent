"""Shared helpers for the offline studies."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases"
PACKAGE = ROOT / "data" / "package"


def load_cases(*sets):
    out = []
    for s in sets or ("practice", "sandbox"):
        path = CASES / f"{s}.json"
        if not path.exists():
            raise SystemExit(f"{path} is missing - run: uv run python analysis/fetch_cases.py")
        out += json.loads(path.read_text())
    return out


def short(case):
    return case["case_id"].split(":")[1] + ("" if case.get("hosted", True) else "*")


def facts():
    return json.loads((PACKAGE / "facts.json").read_text()) if (PACKAGE / "facts.json").exists() else {}
