# analysis

Offline studies that back the notes in the team vault. **None of these scripts opens a session**: they only
read the data package, the case files (`GET /v1/cases`) and sessions that already ended.

| Script | What it does | Needs |
|---|---|---|
| `fetch_cases.py` | Saves the practice and sandbox case files to `data/cases/` | arena key |
| `levermap.py` | For every case: the best package of non-price terms and what forgetting each lever costs | `data/cases/` |
| `grid.py` | Score of one case at a given price across two levers, from a played session's `c_open`/`c_best` | `data/cases/` |
| `coverage.py` | Which detailed suppliers of the package appear in practice cases, and candidate triggers among the others | `data/package`, `data/cases/` |
| `session_dump.py` | Thread, trace and back office of one ended session to `data/sessions/` | arena key |

Run from the repo root, e.g. `uv run python analysis/levermap.py`. `data/` is ignored by Git.
