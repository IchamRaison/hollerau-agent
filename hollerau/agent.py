"""OurAgent: the kit's LLMAgent plus our dossier, packages and closing rules.

Design: vault `03 Build/Design doc - Agent acheteur tacto.md`.
  prepare()  -> inject the dossier (levers in EUR, fair price, <=3 verified claims)
  decide()   -> on `final_offer` apply the closing rule at once; validate the e-mail
Approach A (kit + dossier) is the safety net; approach B (iso-value packages) only if it beats A
on the paired bench.
"""

import logging

from arena_kit.agents.llm import LLMAgent
from arena_kit.play import closing_move, latest, live_threads

log = logging.getLogger("arena")


class OurAgent(LLMAgent):
    def decide(self, case, threads):
        # Design-doc rule: on final_offer, close now (accept the cheapest valid standing sheet that
        # beats the alternative, else walk away) instead of pushing and losing the deal.
        if any(latest(threads[s]).get("status") == "final_offer" for s in live_threads(threads)):
            move = closing_move(case, threads)
            log.info("final_offer seen - closing with %s", move["message"].get("action"))
            return move
        return super().decide(case, threads)
