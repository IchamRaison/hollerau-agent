"""Schema fuzz (A3): map the accepted message/term-sheet space against the local arena-sim.

Free, offline, no quota. Registers a team, opens sessions on the served case, fires malformed
and boundary messages, and records the exact server answer (status + detail) for each.
Re-opens a fresh session whenever one closes, so every trial runs.

Findings so far (sim): 422s leak the allowed option list; price must be > 0 (0, negatives,
NaN rejected); a message with no term sheet is valid; 422/500 consume no round.

Run: uv run python analysis/schema_fuzz.py
"""

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

sys = __import__("sys")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import load_cases  # noqa: E402

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent.parent / "data" / "fuzz"
OUT.mkdir(parents=True, exist_ok=True)


def call(method, path, key=None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    if key:
        req.add_header("X-API-Key", key)
    data = json.dumps(body).encode() if body is not None else None
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {"raw": str(e)}


CASES = {c["case_id"]: c for c in load_cases("sandbox")}


class Arena:
    def __init__(self):
        st, reg = call("POST", "/v1/register", body={"team_name": f"schema-fuzz-{int(time.time())}", "event_code": "sim"})
        self.key = reg.get("api_key")
        st, served = call("GET", "/v1/cases", self.key)
        served = served if isinstance(served, list) else []
        c = served[0] if served else next(iter(CASES.values()))
        self.case, self.sup = c["case_id"], c["suppliers"][0]
        self.neg, self.opts = c["negotiable"], c.get("term_options", {})
        self.sid = None
        self.open()

    def open(self):
        st, resp = call("POST", "/v1/sessions", self.key, {"case_id": self.case})
        self.sid = resp.get("session_id")
        return self.sid

    def send(self, message):
        """Send, healing a closed session or a late thread; returns (status, detail, sid)."""
        st, detail = 0, ""
        for _ in range(4):
            st, resp = call("POST", f"/v1/sessions/{self.sid}/threads/{self.sup}/messages", self.key, {"message": message})
            detail = resp.get("detail") if isinstance(resp, dict) else ""
            if st == 200:
                return st, "", self.sid
            if "has ended" in str(detail) or "round limit" in str(detail):
                self.open()
                continue
            if "late" in str(detail).lower():
                call("GET", f"/v1/sessions/{self.sid}/threads/{self.sup}", self.key)
                continue
            return st, str(detail), self.sid
        return st, str(detail), self.sid

    def sheet(self, **over):
        t = {}
        for f in self.neg:
            o = self.opts.get(f)
            default = over.get("unit_price", 100.0) if f == "unit_price" else (o[0] if o else 42)
            t[f] = over.get(f, default)
        return t

    def msg(self, sheets=None, **kw):
        """sheets: list of term dicts, or [] for none, or [{}] for an empty sheet."""
        m = {"subject": "Test", "body": "Hello, we look forward to your terms.", "refs": [], "term_sheets": []}
        m.update(kw)
        for s in sheets or []:
            m["term_sheets"].append({"term_sheet_id": None, "terms": s})
        return m


def trials(a):
    S = lambda **over: a.sheet(**over)  # noqa: E731
    m = lambda **kw: a.msg(**kw)  # noqa: E731
    neg2 = a.neg[1] if len(a.neg) > 1 else "payment_days"
    opts2 = a.opts.get(neg2, [14, 30, 45, 60, 90])
    return [
        # -- structure: expected 422, no round consumed ------------------------------------
        ("missing one field", m(sheets=[{f: v for f, v in S().items() if f != neg2}])),
        ("price zero", m(sheets=[S(unit_price=0)])),
        ("price negative", m(sheets=[S(unit_price=-10.5)])),
        ("price NaN", m(sheets=[S(unit_price=float("nan"))])),
        ("price Infinity", m(sheets=[S(unit_price=float("inf"))])),
        ("price as string", m(sheets=[S(unit_price="100")])),
        ("price as bool", m(sheets=[S(unit_price=True)])),
        ("price None", m(sheets=[S(unit_price=None)])),
        (f"{neg2} out of range", m(sheets=[S(**{neg2: opts2[-1] + 55})])),
        (f"{neg2} negative", m(sheets=[S(**{neg2: -30})])),
        (f"{neg2} as string", m(sheets=[S(**{neg2: str(opts2[0])})])),
        ("unknown extra field", m(sheets=[{**S(), "surprise": 1}])),
        ("field not negotiable here", m(sheets=[{**S(), "volume_per_year": 100}])),
        ("4 term sheets", m(sheets=[S(), S(), S(), S()])),
        ("3 term sheets", m(sheets=[S(), S(), S()])),
        ("body 8001 chars", m(sheets=[S()], body="x" * 8001)),
        ("body exactly 8000", m(sheets=[S()], body="x" * 8000)),
        ("21 refs", m(sheets=[S()], refs=[f"doc:{i}" for i in range(21)])),
        ("20 refs", m(sheets=[S()], refs=[f"doc:{i}" for i in range(20)])),
        ("refs bad format", m(sheets=[S()], refs=["not-an-id", "quote:9", "??"])),
        ("subject 301 chars", m(sheets=[S()], subject="s" * 301)),
        ("subject 300 chars", m(sheets=[S()], subject="s" * 300)),
        ("subject missing", {k: v for k, v in m(sheets=[S()]).items() if k != "subject"}),
        ("no body", {k: v for k, v in m(sheets=[S()]).items() if k != "body"}),
        ("body not a string", m(sheets=[S()], body=12345)),
        ("refs not a list", m(sheets=[S()], refs="doc:1")),
        ("unknown top field", {**m(sheets=[S()]), "mystery": True}),
        ("action unknown type", {**m(sheets=[S()]), "action": {"type": "explode"}}),
        ("attachments array of 6", {**m(sheets=[S()]), "attachments": [{"name": f"a{i}.md", "content_b64": ""} for i in range(6)]}),
        ("attachments array of 5", {**m(sheets=[S()]), "attachments": [{"name": f"a{i}.md", "content_b64": ""} for i in range(5)]}),
        ("attachment md with body text", {**m(sheets=[S()]), "attachments": [{"name": "note.md", "content_b64": "aGk="}]}),
        # -- accepted shapes: consume a round ------------------------------------------------
        ("valid minimal", m(sheets=[S()])),
        ("no term sheet, question only", m(sheets=[])),
        ("empty terms sheet", m(sheets=[{}])),
        ("price 0.01", m(sheets=[S(unit_price=0.01)])),
        ("price very high", m(sheets=[S(unit_price=999999.0)])),
        ("body with inline IDs", m(sheets=[S()], body="quote:7200001 and doc:1 and idx:PPI-C241 inline")),
        ("empty everything", {"subject": "", "body": "", "refs": [], "term_sheets": []}),
    ]


def main():
    a = Arena()
    print(f"fuzzing {a.case} supplier {a.sup} negotiable={a.neg}")
    results = []
    for name, message in trials(a):
        st, detail, sid = a.send(message)
        results.append({"trial": name, "status": st, "accepted": st == 200, "detail": detail[:220], "session": sid})
        time.sleep(0.12)
    (OUT / "schema_fuzz.json").write_text(json.dumps(results, indent=1))

    print(f"\n{'TRIAL':34} {'STATUS':7} DETAIL")
    for r in results:
        print(f"{r['trial']:34} {'ACCEPT' if r['accepted'] else r['status']:7} {r['detail'][:110]}")
    n_ok = sum(r["accepted"] for r in results)
    print(f"\n{n_ok}/{len(results)} accepted -> data/fuzz/schema_fuzz.json")


main()
