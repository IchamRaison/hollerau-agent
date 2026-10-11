#!/usr/bin/env bash
# PR "données d'analyse" vers IchamRaison/hollerau-agent : traces, c_best des 10 cas, fiches Codex.
set -euo pipefail
GIT=(git -c credential.helper= -c "credential.helper=!gh auth git-credential" -c user.name=redjohn-sudo -c user.email=257271535+redjohn-sudo@users.noreply.github.com)
SRC=~/tacto/codex-work
cd ~/tacto/hollerau-agent
git checkout -q main && "${GIT[@]}" pull -q
git checkout -q -B vincent/pegasus-data
D=analysis/pegasus_data
mkdir -p $D/sessions $D/sandbox-ab $D/intel
cp $SRC/arena-data/cases-practice.json $SRC/arena-data/cases-sandbox.json $D/
cp $SRC/arena-data/sessions/*.json $D/sessions/
cp $SRC/arena-data/sandbox-ab/*.json $D/sandbox-ab/
cp $SRC/intel/generated/{LESSONS.md,CASE_PLAYBOOK.json,PROFILES.md,RULES.md} $D/intel/

cat > $D/README.md <<'EOF'
# Données d'analyse pegasus (Vincent)

Lecture seule, aucune clé. Tout vient de nos propres sessions (`GET /v1/sessions/{sid}` après la fin, `/backoffice`) et de l'analyse hors ligne de Codex.

| Fichier | Contenu |
|---|---|
| `cases-practice.json`, `cases-sandbox.json` | Fiches des 19 cas d'entraînement (dont les 10 hébergés) et des 2 cas sandbox |
| `sessions/<cas>-<sid>.json` | Pour chaque partie terminée : `summary`, `session.result`, et `backoffice`. Le résultat contient `c_open`, `c_deal`, `c_alt`, `c_best`, `score`, `cost_breakdown` et `trace` (raisons du fournisseur à chaque coup). On y trouve l'agent LLM du kit (16:56), le naïf et les lots pegasus (~18:40 et ~19:25). |
| `sandbox-ab/` | Comparaison sandbox : A = pegasus, B = version complète de Codex |
| `intel/CASE_PLAYBOOK.json` | Par cas : leviers chiffrés et packages compatibles avec `c_best`. Calculé ex post, réservé à l'entraînement : aucune valeur ne doit être codée en dur dans l'agent. |
| `intel/LESSONS.md`, `RULES.md`, `PROFILES.md` | Leçons tirées des traces, règles générales, profils fournisseurs |

## `c_best` connus (tous les cas hébergés)
P01 1 096 815,78 · P02 2 235 514,05 · P03 3 909 043,10 · P04 196 529,32 · P05 223 424,17 · P07 299 241,49 · P08 960 309,33 · P10 1 328 926,89 · P11 722 500,02 · P18 222 651,27

## Meilleurs scores pegasus (agent général, sans playbook)
P01 0,995 (record) · P03 0,923 · P04 0,860 · P05 0,734 · P07 0,676 · P08 0,659 · P10 0,562 · P18 0,520 · P02 0,502 · P11 0,474
EOF

"${GIT[@]}" add $D
"${GIT[@]}" commit -qm "analysis: pegasus session traces, c_best of all hosted cases, Codex case playbook and lessons (read-only data, no keys)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
"${GIT[@]}" push -q -u origin vincent/pegasus-data
gh pr create --repo IchamRaison/hollerau-agent --base main --head vincent/pegasus-data \
  --title "Données : traces des 10 cas, c_best connus, fiches et leçons de Codex" \
  --body "$(cat <<'EOF'
Données d'analyse en lecture seule, dans `analysis/pegasus_data/`. Il n'y a aucune clé et aucun code d'agent.

- **Les `c_best` des 10 cas hébergés.** Les scripts `scorer_fuzz.py` et `pareto.py` n'avaient que celui de P01.
- **131 parties terminées** : résultat, trace avec les raisons du fournisseur à chaque coup, et back office. On y trouve l'agent LLM du kit, l'agent naïf et deux lots pegasus.
- **Le playbook de Codex** : leviers chiffrés et packages compatibles avec `c_best`. Il est réservé à l'entraînement et ne doit pas être codé en dur.
- **Les leçons, règles et profils fournisseurs** tirés des traces.

Constat du panel d'Icham, vérifié sur ces données : la citation hors sujet « offer:… » venait de l'agent LLM du kit. Sur les 20 parties pegasus, les citations donnent 87 `verified`, 6 `duplicate` et 0 `irrelevant`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
git checkout -q main
