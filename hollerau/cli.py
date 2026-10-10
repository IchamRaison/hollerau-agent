"""`hollerau` CLI: the kit's `arena` commands with our agent as `--agent ours` (the default).

  uv run hollerau play case:P01 -v
  uv run hollerau run --set practice --parallel 8
  uv run hollerau run --set final --parallel 10        # the Live Final
`me`, `cases`, `board`, `data`, `mcp` work as in the kit's `arena` command.
"""

import argparse
import sys

from arena_kit import cli as kit_cli

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


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
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
