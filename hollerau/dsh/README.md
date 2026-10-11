# DSH pilot — an LLM-led buyer for the Tacto Negotiation Arena

The model conducts the whole case: it reads the file, decides what to propose and writes every
e-mail. Code does what code is good at - it costs every term sheet, keeps the factual state of
the case, refuses what the arena would refuse and sends what the model committed. There is no
negotiation rule in the code or in the prompt: what we learnt from our past games reaches the
model as measured evidence, and it decides.

The loop runs on DeepSeek Harness (`deepseek-harness-sdk==0.1.5rc1`, extra `dsh`), by default
with `gpt-6.1-sol`.

## Run it

```bash
uv sync --extra dsh
uv run pegasus-dsh preflight --offline            # installation, profile, tool server; no model call, no session

# local simulator (free, no validation)
uv run arena-sim serve --port 8000 &
ARENA_URL=http://127.0.0.1:8000 ARENA_API_KEY=<sim key> uv run pegasus-dsh sandbox S01 S02

# hosted arena: every launch goes through the launch lock
HOLLERAU_VALIDATED="<who validated, for what>" ARENA_URL=<hosted arena> uv run pegasus-dsh sandbox D01 D02
HOLLERAU_VALIDATED="..." ARENA_URL=<hosted arena> uv run pegasus-dsh practice P01 P05
HOLLERAU_VALIDATED="..." ARENA_URL=<hosted arena> uv run pegasus-dsh final
```

`.env` (never committed) holds `ARENA_API_KEY` and the model key (`OPENAI_API_KEY` or
`LLM_API_KEY`). Switches:

| Variable | Effect |
|---|---|
| `PEGASUS_DSH_MODEL`, `PEGASUS_DSH_EFFORT` | model and reasoning effort (default `gpt-6.1-sol`, `medium`) |
| `PEGASUS_DSH_HIDE_CASE_RECORDS=1` | leave out the records of the case being played: a known case is read as a new one, the way the final's cases are |
| `PEGASUS_RUNS` | where the run journals go (default `data/runs`) |

A run writes `data/runs/dsh-<UTC time>/decisions.jsonl`: every turn with who decided it (model
or fallback), the seconds it took, the tools called, the e-mails sent and the replies.
`uv run python lab/dsh_journal.py <journal>` prints it; `uv run python lab/dsh_replay.py <run dir>`
fetches the finished sessions and prints them move by move.

## How a case is played

1. `coordinator.play_case` opens the case and builds a `CaseState` from what the arena answered.
2. When supplier e-mails await an answer, the model gets one turn, sized to the earliest of their
   60-second clocks. It receives the state and works through ten tools: `get_case_state`,
   `read_thread`, `evaluate_offers`, `search_structures`, `lookup_facts`, `query_data`,
   `update_hypotheses`, `set_supplier_estimate`, `prepare_decision`, `commit_decision`.
3. `prepare_decision` validates the whole decision (well-formed sheets, must-haves, citable IDs,
   an acceptable sheet) and returns errors to fix and diagnostics to weigh; text and sheets are
   never rewritten. A committed decision's e-mails leave in parallel.
4. If the model has not committed in time, a fallback keeps the threads alive and the turn is
   marked as such in the journal. Behind a missed first move stands the coded Pegasus agent.
5. The case always ends with a decision: an acceptance, or a walk-away when no signable sheet
   beats the alternative.

| File | Role |
|---|---|
| `cli.py` | the `pegasus-dsh` command, preflight, the launch lock |
| `coordinator.py` | the case loop, the journal, the fallback |
| `runtime.py` | DeepSeek Harness with our profile: one runtime, one conversation per case |
| `tools.py` | the model's tools (an MCP server) and the decision lease |
| `state.py` | the factual state of a case and the snapshot the model reads |
| `economics.py` | costs, term options, structures at a target cost, movement of both sides |
| `validation.py` | what the arena would refuse, and non-blocking diagnostics |
| `evidence.py` | what may be cited to which supplier, and the case's own data |
| `recognition.py`, `suppliers.json` | the records of the suppliers we played, and the comparison with the live thread |
| `patterns.py`, `cues.json`, `observations.json` | the earlier sentence library; no longer shown to the model |
| `../../prompts/tacto_negotiator.md` | the model's instructions |
| `../../configs/dsh/tacto.patch.yml` | the harness profile: OpenAI route over the Responses protocol (Chat Completions refuses tools with reasoning for this model), coding tools off, our tool server over streamable HTTP |

## Knowing the supplier

`lab/dsh_suppliers.py` builds `suppliers.json` from every finished game in
`analysis/pegasus_data/sessions/` (804 sessions, 988 supplier threads, 15 suppliers on 11 Oct).
One record per supplier, in units a game shows - what a sheet costs us, as a share of the
supplier's opening quote:

- who signs (the role is at the bottom of its opening quote);
- how its offer answered our ask: the share of the gap between its offer and our ask that it
  closed, cut by the depth of our ask, by the width of the gap and by the size of our own move;
- at which reply its final offer came, what followed each kind of e-mail after it, when it left;
- which kinds of cited data it took into account;
- its back-office notes (visible only after a game) and our best games against it.

During a game `recognition.py` measures the live thread the same way and compares it with every
record. The state shows the three closest with their weights and why, the same measures on the
thread so far, and what the closest records imply for the replies to come. `evaluate_offers`
foretells the supplier's next sheet for a candidate ask and where its sheet would stand at its
final offer if we hold the ask or come up half the gap each time.

```bash
uv run python lab/dsh_fetch.py                # read our finished sessions into the archive (opens nothing)
uv run python lab/dsh_suppliers.py            # rebuild suppliers.json
uv run python lab/dsh_suppliers.py --check    # every archived reply foretold from the records of the OTHER cases
```

What the archive shows (associations under the policies we played, not proven effects):

- a supplier's step follows the gap between its offer and our ask more than the size of our move;
- games in which our asks stayed deep ended with deeper offers;
- where we varied our first ask (D01, D02), the first reply is capped: beyond some depth a deeper
  first ask buys no more at that reply;
- over 2,976 e-mails with a term sheet sent to a supplier whose status was open, none was answered
  by leaving; suppliers left after a push on their final offer, or after a turn we let time out;
- the number of replies before the final offer goes with who signs: two or three for inside sales
  and the segment manager, four or five for owners and export managers.

## What is measured, and what is not

Hosted sandbox, off quota, each launch validated by Icham. One game per cell.

| Run | Commit | Records of the case played | D01 | D02 |
|---|---|---|---|---|
| S1, 07:08 | `4240599` | earlier version; its prompt was written after reading D01/D02 replays | 0.9999 | 0.788 |
| S2, 08:52 | `b1b6f72` | included | 0.959 | 0.598 |
| S2, 08:57 | `b1b6f72` | hidden | 0.839 | 0.618 |
| S3, 09:35 | `665c7d2` | hidden | 0.805 | 0.744 |
| S3, 09:40 | `665c7d2` | hidden | 0.823 | 0.640 |

- Every turn of S2 and S3 was decided by the model, 28 seconds at most for a turn.
- The level is not established: the pilot has never played a practice case, and two D02 games of
  the same commit differ by 0.10.
- No gain is shown from the enriched records of `665c7d2` over `b1b6f72`.
- "Hidden" is the mode that resembles the final, where nobody has met the suppliers.

The journals of every run are in `analysis/pegasus_data/dsh-runs/`.

## Tests

```bash
uv run pytest tests/dsh      # the pilot: costs, validation, tools, the case loop on arena-sim, recognition
uv run pytest                # the whole repository
```

No test calls a model or opens a hosted session.

## Offline analyses

`analysis/dsh/` keeps the scripts behind the figures above. They read the archive and open no
session; run them with `uv run python analysis/dsh/<script> .` from the repository root.

| Script | Question |
|---|---|
| `x10_surplus.py`, `x10_moves.py` | is there gain in trading terms, and how often does a supplier move |
| `x11_dynamics.py`, `x11_first_reply.py` | what a supplier does after each of our moves (superseded: they leave out the departures) |
| `x12_cues.py` | which sentences suppliers repeat, and what followed them |
| `x13_labels_coverage.py` | the observable labels of a reply, and how many replies have precedents in other cases |
| `x14_threads.py` | one flat record per supplier thread -> `threads.json`, read by the three below |
| `x14_law.py`, `x14_dyn.py` | the step as a share of the gap; when a supplier holds, gives its final offer, leaves |
| `x15_surface.py` | does the step follow the gap or our move; does the size of our move bring the final offer forward |
| `entire_trim_session.py` | the copy of the Claude Code transcript attached to Entire (the session ran outside the repository) |
