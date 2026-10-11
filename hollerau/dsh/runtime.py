"""DeepSeek Harness with the tacto profile: one runtime, one conversation per case.

`Pilot.decide` gives the model one turn on a case: it opens a decision lease on the desk, sends
the state to the case's conversation and waits until the model has committed a decision or the
lease has run out. A decision that arrives after its lease is refused by the desk; if the model
is still going when the next turn comes, that turn starts a fresh conversation.

The runtime gets only what the model route and our tool server need: the arena key stays in
this process.
"""

import json
import logging
import os
import stat
import threading
import time
from pathlib import Path

from .tools import Desk, ToolServer

log = logging.getLogger("pegasus.dsh")

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "configs" / "dsh" / "tacto.patch.yml"
PROMPT = ROOT / "prompts" / "tacto_negotiator.md"
PROVIDER = "tacto-openai"
# never handed to the harness runtime, whatever this process holds
WITHHELD = (
    "ARENA_API_KEY",
    "ARENA_TEST_KEY",
    "ARENA_URL",
    "ARENA_HOSTED_URL",
    "ANTHROPIC_API_KEY",
    "LLM_API_KEY",
    "HOLLERAU_VALIDATED",
)


def model_key():
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY") or ""


def turn_message(decision, state, note=""):
    ready = [f"{s} ({state.seconds_left(s):.0f} s left, {state.moves_left(s)} message(s) left)" for s in state.ready()]
    head = [
        f"decision_id: {decision.id}",
        f"You have {decision.seconds_left():.0f} seconds for this turn.",
        "Suppliers awaiting your answer: " + (", ".join(ready) if ready else "none"),
    ]
    if note:
        head.append(note)
    return (
        "\n".join(head) + "\n\nSTATE OF THE CASE\n" + json.dumps(state.snapshot(), separators=(",", ":"), default=str)
    )


class Pilot:
    def __init__(self, model=None, effort=None, home=None, max_tokens=6000):
        self.model = model or os.environ.get("PEGASUS_DSH_MODEL") or os.environ.get("LLM_MODEL") or "gpt-6.1-sol"
        self.effort = effort or os.environ.get("PEGASUS_DSH_EFFORT") or "medium"
        self.home = Path(home or os.environ.get("PEGASUS_DSH_HOME") or ROOT / "data" / "dsh").resolve()
        self.max_tokens = max_tokens
        self.desk, self.tools, self.harness = Desk(), None, None
        self.lock = threading.Lock()
        self.running, self.generation = {}, {}
        # conversations are stored in the harness home: an id must never be reused across launches
        self.run_id = time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + "-" + os.urandom(3).hex()

    # -- lifecycle ---------------------------------------------------------------------------
    def _wrapper(self):
        """The runtime binary behind `env -u`: our process's secrets are not its business."""
        from deepseek_harness_runtime import resolve_bundled_launch_args

        binary = resolve_bundled_launch_args()[0]
        path = self.home / "dsh-runtime"
        unset = " ".join(f"-u {name}" for name in WITHHELD)
        path.write_text(f'#!/bin/sh\nexec env {unset} "{binary}" "$@"\n', encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return str(path)

    def start(self):
        from deepseek_harness import DeepSeekHarness

        if not model_key():
            raise RuntimeError("no model key: set OPENAI_API_KEY (or LLM_API_KEY) in .env")
        work = self.home / "work"
        work.mkdir(parents=True, exist_ok=True)
        self.tools = ToolServer(self.desk).start()
        env = {
            "OPENAI_API_KEY": model_key(),
            "TACTO_MCP_URL": self.tools.url,
            "TACTO_PROMPT": PROMPT.read_text(encoding="utf-8"),
            "TACTO_LLM_MODEL": self.model,
        }
        if os.environ.get("PEGASUS_DSH_BASE_URL"):
            env["TACTO_LLM_BASE_URL"] = os.environ["PEGASUS_DSH_BASE_URL"]
        self.harness = DeepSeekHarness(
            provider=PROVIDER,
            model=self.model,
            reasoning_effort=self.effort,
            max_tokens=self.max_tokens,
            cwd=str(work),
            dsh_home=str(self.home / "home"),
            profile="sdk",
            patches=(str(PATCH),),
            dsh_bin=self._wrapper(),
            env=env,
            initialize_timeout_seconds=90,
        )
        self.harness.start()
        log.info("harness up: %s %s, tools at %s", self.model, self.effort, self.tools.url)
        return self

    def stop(self):
        with self.lock:
            threads = list(self.running.values())
        for thread in threads:  # let the last closing lines end before the runtime goes
            thread.join(timeout=5)
        try:
            if self.harness:
                self.harness.close()
        finally:
            if self.tools:
                self.tools.stop()

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    # -- turns ---------------------------------------------------------------------------------
    def _conversation(self, key, patience_s=0.0):
        """The case's conversation. After a commit the model still writes its closing line: the
        next turn waits for that, up to `patience_s`; a turn still running then is left behind
        and the case continues in a fresh conversation (its notes and the state carry over)."""
        with self.lock:
            thread = self.running.get(key)
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, patience_s))
        with self.lock:
            if thread is not None and thread.is_alive():
                self.generation[key] = self.generation.get(key, 0) + 1
                log.warning("%s: previous turn still running - fresh conversation", key)
            gen = self.generation.get(key, 0)
        safe = "".join(c if c.isalnum() else "-" for c in key)
        return f"{self.run_id}-{safe}-{gen}"

    def _run(self, session_id, text, decision):
        t0 = time.monotonic()
        try:
            result = self.harness.start_session(session_id).run(text)
            usage = [
                ((e.get("data") or {}).get("usage") or {})
                for e in result.events
                if e.get("type") == "assistant/message"
            ]
            decision.trace = {
                "finish": result.finish_reason,
                "final_text": (result.final_response or "")[:400],
                "model_steps": len(usage),
                "seconds": round(time.monotonic() - t0, 2),
                "tokens": {
                    k: sum(u.get(k, 0) or 0 for u in usage)
                    for k in ("inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens")
                },
                "errors": [
                    json.dumps(((e.get("data") or {}).get("reason") or {}).get("error"), default=str)[:300]
                    for e in result.events
                    if e.get("type") == "turn/end"
                    and ((e.get("data") or {}).get("reason") or {}).get("kind") == "error"
                ],
            }
        except Exception as e:  # the model's turn failing is a fallback case, never a crash of the game
            decision.trace = {
                "finish": "exception",
                "errors": [f"{type(e).__name__}: {e}"[:300]],
                "seconds": round(time.monotonic() - t0, 2),
            }
            log.warning("turn failed: %s", decision.trace["errors"][0])
        finally:
            decision.finished.set()
            if decision.on_trace:
                try:
                    decision.on_trace(decision)
                except Exception:
                    log.exception("trace callback failed")

    def decide(self, key, state, budget_s, note="", on_trace=None):
        """One turn of the model on this case. Returns the decision: `status` is "committed" (its
        `batch` is to be sent) or "expired" (nothing may be sent for it). `on_trace(decision)` is
        called when the model's turn has really ended, which may be after this returns."""
        t_wait = time.monotonic()
        session_id = self._conversation(key, patience_s=min(8.0, budget_s / 4))
        budget_s -= time.monotonic() - t_wait
        decision = self.desk.open(state, budget_s)
        decision.trace, decision.finished, decision.on_trace = {}, threading.Event(), on_trace
        decision.conversation = session_id
        thread = threading.Thread(
            target=self._run,
            args=(session_id, turn_message(decision, state, note), decision),
            name=f"dsh-turn-{key}",
            daemon=True,
        )
        with self.lock:
            self.running[key] = thread
        thread.start()
        while decision.seconds_left() > 0 and not decision.done.is_set():
            if decision.finished.wait(timeout=0.1):  # the turn ended without a commit: no need to wait on
                break
        decision.done.wait(timeout=0.2)
        if decision.status != "committed":
            decision.expire()
        decision.waited_s = round(time.monotonic() - decision.opened, 2)
        return decision
