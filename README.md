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

### How the next move is decided

Two policies share the same runner, guard, arguments and e-mail templates. The choice is recorded in the run
configuration.

- `PEGASUS_POLICY=schedule` (default) - the reference: an opening at a share of the supplier's ask, then
  concessions on a decreasing schedule. It sends the same messages as before this work (checked move by move
  against a scripted supplier on the 19 practice case files).
- `PEGASUS_POLICY=actions` - each round compares moves that differ in substance: accept, send back its better
  alternative, trade a term it asked for at the price that pays us back, answer its move by no more than it
  moved, hold with something new, walk. The opening rests on the lowest price the dossier can point to (an
  order, a quote, a rival's offer to beat). A concession needs a counterpart or a move of the supplier.
  If anything in it fails, the schedule policy decides. `PEGASUS_STRATEGIST=1` lets an LLM pick one of the
  listed moves (never a number); off by default.

**The action policy has not been played on the hosted arena.** Its opening level and its steps
(`PEGASUS_OPEN_BASIS`, `PEGASUS_OPEN_MARGIN`, `PEGASUS_UNDERCUT`, `PEGASUS_ASK_FLOOR`, `PEGASUS_RECIP`,
`PEGASUS_RECIP_SHARE`, `PEGASUS_INSIST_STEP`, `PEGASUS_HOLDS_MAX`, see `hollerau/pegasus/actions.py`) are stated
choices, not measurements. It should replace the reference only after a comparison of the two, frozen, on the
same cases.

What it reasons on can be read offline, without any session, score or C_best:

```bash
uv run python -m hollerau.pegasus.inspect P08          # the dossier: facts, statements, estimates, unknowns
uv run python -m hollerau.pegasus.inspect P08 --move   # plus the first move it would make, and why
```

Both policies pass one gate before anything is sent (`outbox.py`), get the time by which the move must have left
(`PEGASUS_DECISION_BUDGET_S`, 40 s), and resume from the arena's messages after a restart.

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
