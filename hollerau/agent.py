"""OurAgent: the kit's LLMAgent with one extra rule, as a placeholder until the real agent exists.

Design (proposed, nothing of it is built yet): team vault,
`03 Build/Design doc - Mesurer le moteur fournisseur.md`.
The only behaviour added here: on `final_offer`, close at once with the kit's `closing_move`.
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
