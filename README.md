# Hollerau buyer agent — Tacto Negotiation Arena (EHL Finale 2026)

An AI buyer for Hollerau Pumpenwerke that negotiates by e-mail with tacto's supplier bots.
Code computes (total cost C, levers in EUR, fair price, verified claims); the LLM argues and writes.

Built on the tacto starter kit: `arena_kit/` is the kit, unmodified (MIT). Our code lives in
`hollerau/` and `eval/`. The kit's own README is `KIT_README.md`.

## Run

Requirements: Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras
cp .env.example .env        # ARENA_API_KEY, and an LLM key (ANTHROPIC_API_KEY or LLM_API_KEY)
uv run arena data           # data package (+ the Sunday release once public) -> data/package
uv run arena me             # key works, practice quota
uv run pegasus practice P01 -v                        # one practice case with pegasus, the agent we play
uv run pegasus practice --parallel 10                 # all hosted practice cases
```

Live Final (Sunday 12:00; started before 12:00 from the submitted commit, no human in the loop):

```bash
uv run python -m hollerau.pegasus.preflight           # everything the runner needs, checked in one go
uv run pegasus final --parallel 10 2>&1 | tee final.log
```

`pegasus` is the one official command (`hollerau/pegasus/cli.py`). Before any session opens it writes the
resolved configuration to `data/runs/<time>-<set>-<fingerprint>/config.json`: code commit, every setting,
the data package, the initial supplier memory, the reader cache - no secret. Decisions (`decisions.jsonl`)
and results (`results.json`) land next to it, so a score can be traced to the version that produced it.

`uv run hollerau play|run` still exists: it plays the first, LLM-driven agent (`hollerau/agent.py`), kept for
comparison. It says so when it starts and refuses the final set unless `--agent` is passed on purpose.

Offline plumbing without a key: `uv run arena-sim serve --no-clock`, then
`ARENA_URL=http://127.0.0.1:8000 uv run arena register team sim` and
`ARENA_URL=http://127.0.0.1:8000 ARENA_API_KEY=<sim key> uv run hollerau play case:S01 --agent naive -v`.

Environment variables: see `.env.example` (never commit `.env`).

## Rule: no session without validation

Practice sessions are limited (200 per team per 24 h). Nothing in this repo opens a session on the hosted
arena unless the launch was validated by the team lead: `hollerau`, `lab.experiments` and `lab.send` refuse to
run without `HOLLERAU_VALIDATED="<who validated, for what>"`. The local simulator is free.
Do not call `uv run arena play|run` directly against arena.tacto.ai: it bypasses this check.

## Approach

`docs/approach.md` (the short description for the submission) and the team vault design doc.
