"""The moves open to us at one point of a negotiation, each with what it costs and why.

The schedule policy (`agent.SCHEDULE`) concedes a share of the gap because a round has passed.
Here every round compares a few moves that differ in substance:
  accept       its standing sheet, if it beats the alternative and its own opening
  mirror       send back its own better alternative, which only a standing sheet can close
  open         the first demand, at the lowest price we can point to in the dossier
  trade        give a term it asked for, at the price that pays us back - our cost unchanged
  reciprocate  move towards it by no more than it just moved towards us
  hold         keep the demand and show something new: a fresh argument, a fresh package
  ask          a question, when its offer is no better than its opening and we have nothing new
  keep         an RFQ thread kept alive with a question while another bidder still moves
  wait         nothing to send yet: another bidder's reply is on its way, or it is still moving
  walk         leave: nothing on the table beats the alternative
A concession needs a counterpart or a move of the supplier; the round number is not a reason.
Every number comes from `evaluation` (the published cost function, hypotheses kept apart) and
`economics`; `choose` is the computed decision, also the fallback of the optional LLM strategist.
"""

import os
from dataclasses import asdict, dataclass, field

from . import economics as eco
from .dossier import price_references
from .evaluation import evaluate

# The opening. None of these four is measured yet: they are the policy's stated choices of risk.
OPEN_BASIS = os.environ.get("PEGASUS_OPEN_BASIS", "reference")  # "default": keep the schedule policy's opening
OPEN_MARGIN = float(os.environ.get("PEGASUS_OPEN_MARGIN", "0"))  # open this share under the reference
UNDERCUT = float(os.environ.get("PEGASUS_UNDERCUT", "0.03"))  # a bidder is asked to beat the best rival by this
ASK_FLOOR = os.environ.get("PEGASUS_ASK_FLOOR", "low")  # which hypothesis bounds our asks: "low" or "cautious"
EXPECT = float(os.environ.get("PEGASUS_EXPECT", "0.67"))  # as agent.EXPECT: where we expect to sign
RECIP = float(os.environ.get("PEGASUS_RECIP", "1.0"))  # our step, as a share of the supplier's last step
RECIP_SHARE = float(os.environ.get("PEGASUS_RECIP_SHARE", "0.25"))  # and never more than this share of the gap
INSIST_STEP = float(os.environ.get("PEGASUS_INSIST_STEP", "0.05"))  # the visible step of a hold
HOLDS_MAX = int(os.environ.get("PEGASUS_HOLDS_MAX", "2"))  # holds in a row against a supplier that does not move
CLEAR = 0.002  # a deal must beat the opening by this share of it, unless it is the supplier's last word
EPS = 0.5  # EUR of C: below this nothing moved


@dataclass
class Action:
    kind: str
    sheets: list = field(default_factory=list)  # our complete term sheets, the main one first
    sheet_id: str | None = None  # the supplier's sheet an accept closes on
    supplier_id: str | None = None  # where it applies (an accept may close on another bidder)
    demand: float | None = None  # the C our main sheet asks for
    evaluation: dict | None = None  # of the sheet at stake
    gives: list = field(default_factory=list)  # what we concede, in words
    asks: list = field(default_factory=list)  # what we ask in return
    why: str = ""  # the fact or hypothesis that makes the move relevant
    refs: list = field(default_factory=list)  # data IDs the e-mail should cite first
    lines: list = field(default_factory=list)  # sentences for the e-mail
    fragile: bool = False  # it only pays under the favourable hypothesis about the supplier

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v not in (None, [], "", False)}


@dataclass
class Situation:
    """Everything a decision reads, in one place."""
    case: dict
    supplier_id: str
    std: dict  # the supplier's standard terms (no private key)
    dossier: object
    state: object
    hypotheses: list
    offers: list  # its sheets now: [(sheet_id, terms, Evaluation)], the standing one first
    status: str = "open"
    moves_left: int = 10
    c_alt: float = float("inf")
    c_open: float = float("inf")  # cautious cost of the best opening quote: the score's zero
    table: list = field(default_factory=list)  # every live bidder: [(supplier_id, sheet_id, Evaluation, final)]
    others_moving: bool = False  # RFQ: another thread can still improve
    busy: tuple = ()
    rival: tuple | None = None  # RFQ: (offer id, price) of the best other standing offer
    fresh_claim: bool = False  # an argument not cited yet is available
    ask: float | None = None  # its current price
    default_demand: float | None = None  # the schedule policy's opening target, when no price can be pointed to
    default_structure: dict | None = None

    @property
    def standing(self):
        return self.offers[0] if self.offers else None

    def cost(self, terms):
        return evaluate(self.case, terms, self.std, self.hypotheses)

    def our_demands(self):
        """The C asked by the main sheet of each of our offers so far."""
        return [self.cost(o["sheets"][0]).commercial for o in self.state.ours if o["sheets"]]

    def their_costs(self):
        """The cheapest valid sheet of each supplier message so far (commercial C)."""
        out = []
        for m in self.state.theirs:
            costs = [e.commercial for e in (self.cost(t) for _, t in m["sheets"]) if e.valid]
            if costs:
                out.append(min(costs))
        return out

    def structure(self, terms):
        return {f: terms.get(f) for f in eco.fields(self.case)}

    def proposed(self):
        return [self.structure(s) for o in self.state.ours for s in o["sheets"]]


def relationship_floor(sit, structure, hi):
    """The price under which the relationship charge outgrows the saving, under the least
    favourable hypothesis (0.01 when no charge applies or none can be estimated), and the same
    under the most favourable one: between the two, a lower price is a bet."""
    floors = [eco.cheapest_price(sit.case, structure, {**sit.std, "_supplier": h["supplier"]}, 0.01, hi)
              for h in sit.hypotheses]
    return (max(floors), min(floors)) if floors else (0.01, 0.01)


def allowed_structures(sit):
    """Structures of the case that respect what the supplier currently states."""
    return [s for s in eco.grid(sit.case) if sit.state.allowed(s)[0]]


def main_structure(sit, demand, keep=None):
    """The structure that leaves the supplier the highest price at our demand - price is what it
    values most, so this is the cheapest way for us to give it some. `keep`: our previous main
    structure, kept while it is still allowed (a package that changes every round reads as noise)."""
    if keep is not None and sit.state.allowed(keep)[0] and sit.cost(eco.sheet(sit.case, keep, 1.0)).valid:
        return keep
    rows = []
    current = sit.structure(sit.standing[1]) if sit.standing else {}
    for s in allowed_structures(sit):
        p = eco.price_for(sit.case, s, demand, sit.std)
        if p > 0.01 and sit.cost(eco.sheet(sit.case, s, p)).valid:
            rows.append((-round(p, 2), eco.distance(sit.case, s, current), s))
    return min(rows, key=lambda r: (r[0], r[1]))[2] if rows else None


def ask_floor(sit, structure, hi):
    """(the floor our asks respect, the cautious floor, the favourable one). An ask is not an
    acceptance: by default it only stays above the price that is a loss even under the favourable
    hypothesis; whether a deal is worth signing is judged on the cautious total (`eligible`)."""
    cautious, low = relationship_floor(sit, structure, hi)
    return (cautious if ASK_FLOOR == "cautious" else low), cautious, low


def priced(sit, structure, demand):
    """A complete sheet of `structure` at the price that costs us `demand`: never above its ask,
    never under the relationship floor our asks respect."""
    p = eco.price_for(sit.case, structure, demand, sit.std)
    hi = max(10 * (sit.ask or p or 1.0), 1.0)
    p = max(p, ask_floor(sit, structure, hi)[0])
    if sit.ask:
        p = min(p, sit.ask)
    return eco.sheet(sit.case, structure, p)


def opening_demand(sit):
    """(demand, structure, basis): the first demand rests on the lowest price we can point to -
    an order we placed, a quote, a rival's standing offer - not on a share of its ask. Without
    any such price below its ask, `basis["basis"]` is "none" and the caller keeps its default."""
    ask = sit.ask
    if OPEN_BASIS != "reference":
        return None, None, {"basis": "none", "why": "PEGASUS_OPEN_BASIS keeps the schedule policy's opening"}
    refs = [(p, i) for p, i in price_references(sit.dossier) if not ask or p < ask - 0.005]
    if sit.case.get("type") == "rfq":  # our order prices would tell the rivals what we pay
        refs = [(p, i) for p, i in refs if not i.key.startswith("price.orders")]
    if sit.rival and (not ask or sit.rival[1] < ask - 0.005):
        refs.append((sit.rival[1] * (1 - UNDERCUT), None))  # a bidder is asked to beat the rival, not to match it
    if not refs or not ask:
        return None, None, {"basis": "none", "why": "no comparable price below its ask in the dossier"}
    price, item = min(refs, key=lambda r: r[0])
    price *= 1 - OPEN_MARGIN
    expected = price + EXPECT * max(ask - price, 0)
    current = sit.structure(sit.standing[1]) if sit.standing else None
    best = eco.best_at_price(sit.case, expected, sit.std, current)
    if not best:
        return None, None, {"basis": "none", "why": "no valid structure at the expected price"}
    structure = best[1] if sit.state.allowed(best[1])[0] else (main_structure(sit, best[0]) or best[1])
    floor, cautious, low = ask_floor(sit, structure, max(10 * ask, 1.0))
    floored = max(price, floor)
    demand = sit.cost(eco.sheet(sit.case, structure, floored)).commercial
    basis = {"basis": "reference", "reference": item.key if item else "rival.offer", "price": round(price, 4),
             "sources": list(item.sources) if item else [sit.rival[0]], "opening_price": round(floored, 2),
             "others": [{"key": i.key if i else "rival.offer", "price": p}
                        for p, i in sorted(refs, key=lambda r: r[0])[1:4]]}
    if cautious > 0.01:
        basis["relationship_floor"] = {"favourable": low, "cautious": cautious, "asks_respect": ASK_FLOOR}
    if floored > price:
        basis["floored"] = (f"raised to {floored:.2f}: under it the relationship charge outgrows the saving "
                            f"(the bottom sits between {low:.2f} and {cautious:.2f} depending on the hypothesis)")
    return demand, structure, basis


GIVE = {  # subject -> (field, direction of what the supplier wants, words)
    "payment.faster": ("payment_days", -1, "payment in {new} days instead of {old}"),
    "contract.longer": ("contract_months", +1, "a {new}-month agreement instead of {old}"),
    "volume.commitment": ("volume_per_year", +1, "a binding volume of {new:,} per year instead of {old:,}"),
}


def trades(sit, demand, main):
    """Packages that give the supplier a term it asked for, at the price that pays us back:
    [(structure, give in words, why)]. Our cost is the demand either way - what moves is who gets
    what. A term is only given if the case lets us, the supplier's statements allow the package,
    and we have not proposed it yet."""
    out, proposed = [], sit.proposed()
    wants = sit.state.wants()
    hinted = {s for s in GIVE if sit.state.holds(s, kinds=("hypothesis",)) and s not in wants}
    need = sit.case["buyer"].get("need_per_year")
    for subject in list(wants) + sorted(hinted):
        if subject == "index.required":
            clause = (sit.standing[1].get("index_clause") if sit.standing else None)
            if not isinstance(clause, dict) or "index_clause" not in main or main.get("index_clause") == clause:
                continue
            s, give = {**main, "index_clause": clause}, f"the {clause.get('series')} index clause you ask for"
        else:
            f, way, words = GIVE[subject]
            options = sorted(o for o in sit.case.get("term_options", {}).get(f) or [] if isinstance(o, (int, float)))
            old = main.get(f)
            if old is None or not options:
                continue
            better = [o for o in options if (o < old if way < 0 else o > old)]
            if f == "volume_per_year" and need:
                better = [o for o in better if o <= need]  # volume beyond the need is bought for nothing
            if not better:
                continue
            new = min(better)  # the fastest payment it could wish for; the next longer term or larger volume
            if f == "payment_days":
                rate, ours = sit.state.cash_rate(), sit.case["buyer"].get("interest_rate", 0.08)
                if rate is not None and rate <= ours:
                    continue  # its money is no dearer than ours: paying faster cannot pay both sides
            s, give = {**main, f: new}, words.format(new=new, old=old)
        if s in proposed or s == main or not sit.state.allowed(s)[0]:
            continue
        said = subject in wants
        out.append((s, give, ("you asked for it" if said else "the dossier suggests it would help you")))
    return out


def package(sit, demand, main, limit=3):
    """The sheets of an offer at `demand`: the main structure, then one sheet per trade - each a
    readable exchange, not a variant picked because a grid ranks it first."""
    sheets, gives, lines = [priced(sit, main, demand)], [], []
    for s, give, why in trades(sit, demand, main):
        if len(sheets) >= limit:
            break
        t = priced(sit, s, demand)
        if t in sheets or not sit.cost(t).valid or t["unit_price"] < 0.9 * sheets[0]["unit_price"]:
            continue
        sheets.append(t)
        gives.append(give)
        lines.append(f"Since {why}: one package offers {give}, at EUR {t['unit_price']:.2f} per unit; "
                     f"the first one keeps our terms at EUR {sheets[0]['unit_price']:.2f}.")
    return sheets, gives, lines


def eligible(sit, e, final):
    """Whether a deal on this evaluation is worth closing: it must beat the alternative and the
    opening (a deal no better than the opening scores nothing). Returns (ok, fragile)."""
    if not e.valid:
        return False, False
    bar = min(sit.c_alt, sit.c_open)
    margin = 0.0 if final else CLEAR * abs(sit.c_open if sit.c_open < float("inf") else e.cautious)
    if e.cautious < bar - margin:
        return True, False
    if final and e.low < bar and sit.c_alt >= sit.c_open:
        return True, True  # only under the favourable hypothesis - and walking would score nothing either
    if sit.c_alt == float("inf") and (final or sit.moves_left <= 1):
        return True, True  # no alternative: a deal at worst scores what no deal scores
    return False, False


def closing(sit, final):
    """The end of this thread's road: mirror its own better alternative (only a standing sheet can
    be accepted), else accept the best sheet on the whole table if it is worth it, else wait for
    another bidder (RFQ) or walk."""
    rows = sorted((r for r in sit.table if r[2].valid), key=lambda r: r[2].cautious)
    best = rows[0] if rows else None
    alts = [(i, t, e) for i, t, e in sit.offers[1:] if e.valid]
    if alts and sit.moves_left > 1 and sit.supplier_id not in sit.busy:
        i, t, e = min(alts, key=lambda r: r[2].cautious)
        back = eco.sheet(sit.case, sit.structure(t), t["unit_price"])
        sent = [x for o in sit.state.ours for x in o["sheets"]]
        if (best is None or e.cautious < best[2].cautious - EPS) and eligible(sit, e, final)[0] and back not in sent:
            return Action("mirror", sheets=[back], supplier_id=sit.supplier_id, evaluation=e.summary(),
                          why=f"its alternative {i} costs us less than any standing sheet: sent back to be confirmed",
                          lines=["We are ready to accept your alternative package as attached. Please confirm it."])
    if sit.others_moving:
        # An RFQ is closed by the last thread that can still improve, never by one that has run out
        # of things to say: closing now would take another bidder's sheet in the middle of its
        # negotiation (sandbox D02, 11/10: only the reply in flight kept that from happening).
        if sit.moves_left > 2 and sit.supplier_id not in sit.busy:
            return Action("keep", supplier_id=sit.supplier_id,
                          why="another bidder is still moving: this offer is our lever on it")
        return Action("wait", supplier_id=sit.supplier_id, why="another bidder is still moving")
    if best is not None:
        sid, sheet_id, e, _ = best
        ok, weak = eligible(sit, e, final)
        if ok:
            if sid in sit.busy:
                return Action("wait", supplier_id=sit.supplier_id,
                              why="the best sheet is on a thread whose reply is on its way")
            return Action("accept", sheet_id=sheet_id, supplier_id=sid, evaluation=e.summary(), fragile=weak,
                          why="the best standing sheet beats the alternative and the opening"
                          + (" only under the favourable hypothesis" if weak else ""))
    return Action("walk", supplier_id=sit.supplier_id, why="nothing on the table beats the alternative or the opening")


def stalled(theirs):
    """How many of its latest messages brought no better sheet than the one before."""
    n = 0
    for i in range(len(theirs) - 1, 0, -1):
        if theirs[i - 1] - theirs[i] > EPS:
            break
        n += 1
    return n


def build(sit):
    """Every move worth comparing now, the computed choice first."""
    standing = sit.standing
    final = sit.status in ("final_offer", "agreed")
    close = closing(sit, final or sit.moves_left <= 1)
    if final or sit.moves_left <= 1:
        return [close]  # its last word, or our last message: pushing on makes it walk

    demands, theirs = sit.our_demands(), sit.their_costs()
    if not demands:  # our first offer
        demand, structure, basis = opening_demand(sit)
        why = None
        if demand is None and sit.default_demand is not None:
            demand = sit.default_demand
            structure = sit.default_structure or main_structure(sit, demand)
            why = basis["why"] + ": the default opening applies (a share of its ask)"
            basis = {**basis, "basis": "default"}
        if demand is None or structure is None:
            return [close]
        sheets, gives, lines = package(sit, demand, structure)
        return [Action("open", sheets=sheets, supplier_id=sit.supplier_id, demand=demand, gives=gives,
                       asks=[f"EUR {sheets[0]['unit_price']:.2f} per unit"], refs=basis.get("sources", []),
                       lines=lines, evaluation={**sit.cost(sheets[0]).summary(), "basis": basis},
                       why=why or f"the lowest price we can point to: {basis['reference']} at {basis['price']}"), close]

    demand = demands[-1]
    if standing and standing[2].commercial <= demand + EPS and eligible(sit, standing[2], False)[0]:
        return [Action("accept", sheet_id=standing[0], supplier_id=sit.supplier_id, evaluation=standing[2].summary(),
                       why="its standing sheet costs us no more than what we asked"), close]
    c_s = min((e.commercial for _, _, e in sit.offers if e.valid), default=None)
    if c_s is None and sit.ask and sit.state.ours and sit.state.ours[-1]["sheets"]:
        # nothing valid on its side (a quote that breaks a must-have): our own package at its price
        ours = sit.structure(sit.state.ours[-1]["sheets"][0])
        c_s = sit.cost(eco.sheet(sit.case, ours, sit.ask)).commercial
    gap = max((c_s if c_s is not None else demand) - demand, 0.0)
    moved = max(theirs[-2] - theirs[-1], 0.0) if len(theirs) >= 2 else 0.0
    last = next((o["sheets"] for o in reversed(sit.state.ours) if o["sheets"]), [])  # our last offer, not a question
    last_main = sit.structure(last[0]) if last else None

    moves = []
    if moved > EPS and gap > EPS:
        step = min(RECIP * moved, RECIP_SHARE * gap)
        main = main_structure(sit, demand + step, last_main)
        if main is not None:
            sheets, gives, lines = package(sit, demand + step, main)
            moves.append(Action("reciprocate", sheets=sheets, supplier_id=sit.supplier_id, demand=demand + step,
                                gives=gives, asks=[f"EUR {sheets[0]['unit_price']:.2f} per unit"], lines=lines,
                                evaluation=sit.cost(sheets[0]).summary(),
                                why=f"it moved by {moved:,.0f} EUR of our cost; we answer with {step:,.0f}, no more"))
    main = main_structure(sit, demand, last_main)
    if main is not None and gap > EPS and stalled(theirs) < HOLDS_MAX:
        sheets, gives, lines = package(sit, demand + INSIST_STEP * gap, main)
        fresh = any(sit.structure(x) not in sit.proposed() for x in sheets)
        if sit.fresh_claim or fresh:
            moves.append(Action("hold", sheets=sheets, supplier_id=sit.supplier_id, demand=demand + INSIST_STEP * gap,
                                gives=gives, asks=[f"EUR {sheets[0]['unit_price']:.2f} per unit"], lines=lines,
                                evaluation=sit.cost(sheets[0]).summary(),
                                why=("a package it has not seen yet" if fresh else "an argument not made yet")
                                + ": the demand stands, but for a visible step"))
    if not moves and close.kind == "walk" and sit.moves_left > 2:
        # Nothing new to show and nothing on the table worth closing: leaving now scores nothing better
        # than staying. First a visible step, to see whether it moves; then the question, once; then out.
        asked = bool(sit.state.ours) and not sit.state.ours[-1]["sheets"]  # our last message was a question
        if main is not None and gap > EPS and stalled(theirs) < HOLDS_MAX:
            sheets, gives, lines = package(sit, demand + INSIST_STEP * gap, main)
            moves.append(Action("hold", sheets=sheets, supplier_id=sit.supplier_id, demand=demand + INSIST_STEP * gap,
                                gives=gives, asks=[f"EUR {sheets[0]['unit_price']:.2f} per unit"], lines=lines,
                                evaluation=sit.cost(sheets[0]).summary(),
                                why="nothing on the table is worth closing: a visible step, to see whether it moves"))
        elif not asked:
            moves.append(Action("ask", supplier_id=sit.supplier_id, why="its offer is no better than its opening quote",
                                lines=["Your offer does not yet improve on your opening quote for us. "
                                       "Could you review your price on the terms of our last package?"]))
    return moves + [close]


def choose(actions, sit=None):
    """The computed decision: `build` orders the moves, the first one stands. Kept as a function
    so the optional strategist has the same fallback wherever it is called from."""
    return actions[0] if actions else None
