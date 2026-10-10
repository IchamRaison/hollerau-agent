"""`hollerau` CLI: the kit's `arena` commands with the first, LLM-driven agent as `--agent ours`.

This is NOT the agent we play: that one is pegasus, `uv run pegasus practice|sandbox|final`
(`hollerau/pegasus/cli.py`). `hollerau play|run` stays for comparison and says so; on the final
set it refuses to start unless `--agent` is passed on purpose.

  uv run hollerau play case:P01 -v
  uv run hollerau run --set practice --parallel 8
`me`, `cases`, `board`, `data`, `mcp` work as in the kit's `arena` command.
"""

import argparse
import sys

from arena_kit import cli as kit_cli

from .sessions import require_validation

_kit_agent_factory = kit_cli.agent_factory


def agent_factory(name, data):
    if name != "ours":
        return _kit_agent_factory(name, data)
    from arena_kit.agents.llm import llm_from_env
    from arena_kit.data import DataPackage

    from .agent import OurAgent

    package = DataPackage(data) if data else None
    if package:
        package.lookup("")  # build the ID index once, before agents share it
    complete = llm_from_env()
    return lambda: OurAgent(complete, package)


def legacy_notice(argv):
    """`hollerau play|run` launches the first agent, not pegasus: say it, and never by accident
    in the Live Final."""
    if not argv or argv[0] not in ("play", "run"):
        return
    explicit = any(a == "--agent" or a.startswith("--agent=") for a in argv)
    if "final" in argv and not explicit:
        sys.exit("REFUSED: `hollerau run --set final` would play the first LLM agent, not pegasus.\n"
                 "The Live Final command is:  uv run pegasus final --parallel 10\n"
                 "To launch the first agent on purpose, pass --agent ours.")
    if not explicit:
        print("[hollerau] this command plays the first LLM agent (hollerau.agent.OurAgent); "
              "the agent we develop is `uv run pegasus ...`", file=sys.stderr)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    kit_cli.load_env()
    legacy_notice(argv)
    if argv and argv[0] == "play":
        case = next((a for a in argv[1:] if a.startswith("case:")), "")
        require_validation(f"play {case}", 1, quota=case.startswith("case:P"))
    elif argv and argv[0] == "run":
        final = "final" in argv
        require_validation("run " + " ".join(argv[1:]), "up to 10 per pass", quota=not final and "sandbox" not in argv)
    orig = argparse.ArgumentParser.add_argument

    def add_argument(self, *a, **kw):  # let the kit's parser accept "ours"
        if "--agent" in a and "choices" in kw:
            kw["choices"] = [*kw["choices"], "ours"]
            kw["default"] = "ours"
        return orig(self, *a, **kw)

    argparse.ArgumentParser.add_argument = add_argument
    kit_cli.agent_factory = agent_factory
    try:
        return kit_cli.main(argv)
    finally:
        argparse.ArgumentParser.add_argument = orig
