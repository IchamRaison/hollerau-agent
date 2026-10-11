#!/usr/bin/env bash
# PR "runner, garde-fous, banc" (couloir de Vincent) vers IchamRaison/hollerau-agent.
set -euo pipefail
GIT=(git -c credential.helper= -c "credential.helper=!gh auth git-credential")
SRC=~/tacto/negotiation-arena-kit/starter-kit/pegasus
cd ~/tacto/hollerau-agent
git checkout -q main && "${GIT[@]}" pull -q
git checkout -q -B vincent/runner-guard-bench
mkdir -p hollerau/pegasus
cp "$SRC"/{economics,claims,agent,guard,play,cli,bench}.py hollerau/pegasus/
sed -i 's/dict(zip(fields(case), combo))/dict(zip(fields(case), combo, strict=True))/' hollerau/pegasus/economics.py

cat > hollerau/pegasus/__init__.py <<'EOF'
"""pegasus: a complete, code-driven baseline buyer (Vincent's lane: runner, guards, bench).

- `economics`: every allowed non-price structure priced with the kit's cost function
- `claims`: arguments the arena verifies (falling indices, notice, should-cost, forecast, scorecard, rival offer)
- `agent`: anchor, concessions in total cost C, up to 3 iso-C sheets, accept/hold/walk rules
- `guard`: fail-closed pre-send check (IDs known, figures equal the facts, no leak) + `guard_move` for `contracts.Move`
- `play`: one worker per supplier thread (RFQ without timeouts), closing before the wave cap
- `bench` (sandbox) and `cli` (practice/sandbox/final): both call `sessions.require_validation`.
"""
EOF

python3 - <<'EOF'
import pathlib
root = pathlib.Path("hollerau/pegasus")
p = root / "cli.py"; s = p.read_text()
s = s.replace("uv run python -m hollerau.pegasus.cli", "uv run python -m hollerau.pegasus.cli")
s = s.replace("from .agent import PegasusAgent", "from ..sessions import require_validation\nfrom .agent import PegasusAgent")
s = s.replace('''    client = ArenaClient()
    if a.set == "final":''', '''    n = len(a.cases) or 10
    require_validation(f"pegasus {a.set} {' '.join(a.cases)}".strip(), n, quota=a.set == "practice")
    client = ArenaClient()
    if a.set == "final":''')
p.write_text(s)
p = root / "bench.py"; s = p.read_text()
s = s.replace("uv run python -m hollerau.pegasus.bench", "uv run python -m hollerau.pegasus.bench")
s = s.replace("from .agent import PegasusAgent", "from ..sessions import require_validation\nfrom .agent import PegasusAgent")
s = s.replace('''    ids = ["case:D01"] * n + ["case:D02"] * n''', '''    ids = ["case:D01"] * n + ["case:D02"] * n
    require_validation(f"pegasus sandbox bench x{n}", len(ids), quota=False)''')
p.write_text(s)
p = root / "guard.py"; s = p.read_text()
s += '''

def guard_move(move, case, threads, facts):
    """`contracts.guard` for the team's `Move`: the same checks on the message the move would send."""
    if move.intent in ("accept", "walk_away"):
        return move
    offers = {ts["term_sheet_id"] for ev in threads.values() for m in ev
              for ts in (m.get("term_sheets") or []) if ts.get("term_sheet_id")}
    msg, problems = check(case, move.to_message(), facts, offers)
    if problems:
        move.body = msg.get("body", "")
        move.term_sheets = [ts["terms"] for ts in msg.get("term_sheets") or []]
        move.intent = move.intent if move.term_sheets else "hold"
    return move
'''
p.write_text(s)
EOF

cat > tests/test_pegasus.py <<'EOF'
"""Offline tests of the pegasus guard (no network, no session)."""

import json
from pathlib import Path

from arena_kit.cost import complete_offer
from hollerau.pegasus import guard

CASES = {c["case_id"]: c for c in json.loads((Path(__file__).parent / "fixtures/cases/practice.json").read_text())}
FACTS = {
    "idx:PPI-D351@2025-08": {"series": "PPI-D351", "month": "2025-08", "value": 137.0},
    "idx:PPI-D351@2026-08": {"series": "PPI-D351", "month": "2026-08", "value": 131.9},
}


def test_true_index_claim_kept():
    case = CASES["case:P01"]
    body = "PPI-D351 changed -3.7% from 2025-08 to 2026-08 (idx:PPI-D351@2025-08, idx:PPI-D351@2026-08)."
    sheet = complete_offer(case, {"unit_price": 130.0})
    msg, problems = guard.check(case, {"body": body, "term_sheets": [{"terms": sheet}]}, FACTS)
    assert problems == [] and msg["body"] == body


def test_wrong_figure_unknown_id_and_leak_dropped():
    case = CASES["case:P01"]
    body = ("PPI-D351 changed -9.9% (idx:PPI-D351@2025-08, idx:PPI-D351@2026-08).\n"
            "We have no alternative.\nSee idx:FAKE@2026-01.")
    sheet = complete_offer(case, {"unit_price": 130.0})
    msg, problems = guard.check(case, {"body": body, "term_sheets": [{"terms": sheet}]}, FACTS)
    assert len(problems) == 3 and msg["body"] == ""


def test_sheet_far_above_ask_replaced_by_question():
    case = CASES["case:P01"]
    sheet = complete_offer(case, {"unit_price": 999.0})
    msg, problems = guard.check(case, {"body": "x", "term_sheets": [{"terms": sheet}]}, FACTS, ask=138.55)
    assert problems and "term_sheets" not in msg
EOF

uv run pytest -q tests/test_pegasus.py
uv run ruff check hollerau/pegasus tests/test_pegasus.py --fix

git add hollerau/pegasus tests/test_pegasus.py
git -c user.name=redjohn-sudo -c user.email=257271535+redjohn-sudo@users.noreply.github.com commit -qm "pegasus: per-thread runner, fail-closed guard, sandbox bench and a complete baseline agent (Vincent's lane)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
"${GIT[@]}" push -q -u origin vincent/runner-guard-bench

gh pr create --repo IchamRaison/hollerau-agent --base main --head vincent/runner-guard-bench \
  --title "Couloir Vincent : runner par fil, garde-fous, banc sandbox + agent de base pegasus" \
  --body "$(cat <<'EOF'
## Quoi
`hollerau/pegasus/` : le couloir **runner, garde-fous, banc**, et un agent de base complet qui s'en sert.

- **`play.py` : un worker par fil fournisseur.** En appel d'offres, aucun fil n'attend la réponse d'un autre, donc plus de timeouts (P05 perdu à cause de ça dans la baseline). Aucune acceptation d'une offre périmée : si la meilleure offre est sur un fil qui a un message en vol, on attend sa réponse. Sur un 409/422, le fil est resynchronisé depuis l'arène. Clôture avant le cap de vague.
- **`guard.py`, fail-closed avant chaque envoi.**
  - Chaque ID doit exister dans facts, dans le cas ou dans une offre de la session.
  - Chaque chiffre doit égaler le fait, à la tolérance de l'arène.
  - Aucune fuite : alternative, budget, urgence.
  - Une sheet invalide est remplacée par une question.
  - `guard_move()` applique le même contrôle aux `contracts.Move`.
- **`agent.py`, agent de base sans LLM.**
  - Structures non-prix classées avec le coût du kit.
  - Concessions en C avec un pas minimum visible.
  - Jusqu'à 3 sheets iso-C.
  - Lecture des alternatives `offer:X-n-a`.
  - Appel d'offres : les fournisseurs restent en concurrence jusqu'à ce qu'aucun ne bouge.
  - Réglages `PEGASUS_*`.
- **`bench.py` et `cli.py`** appellent `sessions.require_validation` : aucune session sans `HOLLERAU_VALIDATED`.

## Mesures (sandbox, hors quota)
| | Départ | Maintenant |
|---|---|---|
| D01 | 0,914 | **0,969** |
| D02 (appel d'offres) | 0,33 | **0,723** |

Réglage `PEGASUS_ANCHOR=0.80 PEGASUS_PI_ANCHOR=0.94`. Aucune session d'entraînement utilisée pour ces mesures.

## Non fait
- Pas de LLM dans la boucle : la couche LLM est le couloir de Safoan. `guard_move` est prévu pour se brancher derrière son stratège.
- Les fiches fournisseurs et 22 correctifs de revue de Codex sont en cours de portage. Tacto a dit sur Discord, à 17:39, qu'en finale ce seront 40 fournisseurs du jeu de données : les fiches serviront donc en finale.

## Tests
`uv run pytest tests/test_pegasus.py` : garde-fou hors ligne. `arena_kit/` reste inchangé.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
