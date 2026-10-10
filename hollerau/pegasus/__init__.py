"""pegasus: the team's code-driven buyer agent (Vincent's lane), with Codex's supplier intelligence and Nevil's evidence adapter.

Modules
- economics: every allowed structure priced with the kit's cost function; relationship model (0.98 x should-cost)
- claims / claims_intel / intel_bridge: verified arguments (ours, Codex's dossiers, Nevil's adapter when present)
- reader / reader_cache: what the supplier said, as typed signals with verified quotes (LLM + keyword fallback, archived)
- adapt: signals -> next offer (required index clause, chargeback cap, firm lead time, longer term, fewer arguments)
- memory: what a supplier taught us in earlier negotiations (two observations before it constrains)
- agent: anchor at the expected deal price, concessions in C, 3 sheets, acceptance rules, closing before the cap
- play: one worker per supplier thread; play_waves for the Live Final
- guard: fail-closed pre-send check (IDs, figures, leaks); prose: optional LLM narrator (off)
- preflight / dryrun_final / bench / cli: checks, offline rehearsal of the final, sandbox bench, runner
Switches (env): PEGASUS_READER=1 (LLM reader), PEGASUS_TEAM_CLAIMS=1 (Nevil's adapter), PEGASUS_FINAL_TRADE, PEGASUS_RFQ_BAFO, ...
"""
