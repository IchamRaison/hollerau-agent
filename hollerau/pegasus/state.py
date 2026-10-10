"""What a thread has taught us so far, how we know it, and whether it still holds.

`reader.apply` folds every signal into flags that only ever switch on. Here each thing learnt is
a note with its standing:
  contract    fixed by the case file: certain
  statement   the supplier said it - a position, held until it takes it back or its own offers
              contradict it ("cannot fix prices over 24 months", then a fixed-price sheet at 24)
  observed    the supplier did it: a term it put in a sheet, a price it offered
  hypothesis  our reading: a prior from an earlier negotiation, a signal from the dossier
A statement keeps the condition it was made under: an index clause required for a 36-month contract
is not required for every contract. A prior from memory is a hint - it never filters an offer until
the supplier says it again in this negotiation.

`rebuild` replays a thread from its first e-mail, so a restarted run recovers the same state from
the arena's messages. Nothing here is probabilistic: every note can be read and explained.
"""

import re
from dataclasses import asdict, dataclass, field

from . import reader

# reader signal -> (subject, the term it is about)
SUBJECTS = {
    "wants_faster_payment": ("payment.faster", "payment_days"),
    "wants_volume_commitment": ("volume.commitment", "volume_per_year"),
    "wants_longer_contract": ("contract.longer", "contract_months"),
    "requires_index_clause": ("index.required", "index_clause"),
    "price_frozen": ("price.frozen", "unit_price"),
    "needs_internal_approval": ("approval.needed", None),
    "arguments_rejected": ("arguments.rejected", None),
    "chargeback_too_high": ("chargeback.too_high", "chargeback_eur_per_complaint"),
    "lead_time_firm": ("lead_time.firm", "lead_time_days"),
    "capacity_tight": ("capacity.tight", None),
    "free_capacity": ("capacity.free", None),
    "cost_floor": ("price.floor", "unit_price"),
}
# memory's prior flags (memory.PRIOR_FLAGS values) -> subject
PRIORS = {"cash": "payment.faster", "freeze": "price.frozen", "wants_index": "index.required",
          "lead_firm": "lead_time.firm", "cb_too_high": "chargeback.too_high",
          "wants_duration": "contract.longer", "wants_volume": "volume.commitment"}
# legacy flag -> subject, and whether a mere hypothesis may switch it on (a preference yes, a constraint no)
FLAGS = {"cash": ("payment.faster", True), "freeze": ("price.frozen", False),
         "wants_index": ("index.required", False), "wants_volume": ("volume.commitment", True),
         "wants_duration": ("contract.longer", True), "cb_too_high": ("chargeback.too_high", False),
         "lead_firm": ("lead_time.firm", False), "args_rejected": ("arguments.rejected", False)}
MONTHS_RE = re.compile(r"(?:over|for|of|beyond) (?:a |an |this |the )?(?:period of )?(\d{2})[- ]?months?|(\d{2})-month")
TOLERANCE = 0.005  # a price is "lower" beyond half a cent


@dataclass
class Note:
    kind: str  # contract | statement | observed | hypothesis
    subject: str
    value: object = None
    condition: dict = field(default_factory=dict)  # e.g. {"contract_months": 24}: holds from 24 months up
    at: int = 0  # index of the supplier message it comes from (0 = its opening)
    source: str = "mail"  # mail | memory | dossier | case
    active: bool = True
    why: str = ""  # why it stopped holding

    def holds_for(self, structure):
        """The condition under which it was said covers this structure."""
        months = self.condition.get("contract_months")
        if months is not None and structure.get("contract_months") is not None:
            return structure["contract_months"] >= months
        return True


class ThreadState:
    def __init__(self):
        self.notes = []
        self.theirs = []  # supplier messages: {"status", "sheets": [(id, terms)]}
        self.ours = []  # our messages with sheets: {"sheets": [terms], "refs": [...]}
        self.arguments = []  # what became of the arguments we sent: {"refs", "results"}
        self.granted = {}  # field -> values the supplier put in a sheet of its own

    # -- reading -------------------------------------------------------------------------------
    def notes_on(self, subject, kinds=("statement",)):
        return [n for n in self.notes if n.subject == subject and n.active and n.kind in kinds]

    def holds(self, subject, structure=None, kinds=("statement",)):
        """An active note on `subject` (that covers `structure`, when one is given)."""
        return any(structure is None or n.holds_for(structure) for n in self.notes_on(subject, kinds))

    def value(self, subject, kinds=("statement",)):
        notes = self.notes_on(subject, kinds)
        return notes[-1].value if notes else None

    def flags(self):
        """The flags `agent` and `adapt` read, from the notes that still hold. A hypothesis switches a
        preference on (it may earn a trade), never a constraint."""
        out = {}
        for flag, (subject, soft) in FLAGS.items():
            out[flag] = self.holds(subject, kinds=("statement", "hypothesis") if soft else ("statement",))
        stated = {}
        for subject, f in (("lead_time.firm", "lead_time_days"),
                           ("chargeback.too_high", "chargeback_eur_per_complaint")):
            v = self.value(subject)
            if v is not None:
                stated[f] = v
        out["stated"] = stated
        return out

    def floor_hits(self):
        """How many times it said its price is its limit, since it last lowered that price."""
        return len(self.notes_on("price.floor"))

    def allowed(self, structure):
        """Whether a structure respects what the supplier currently states as constraints.
        Returns (ok, why not): unlike a flag, a statement only binds the structures it was made about."""
        for n in self.notes_on("index.required"):
            if "index_clause" in structure and n.holds_for(structure):
                clause = structure.get("index_clause")
                if not isinstance(clause, dict) or (n.value and clause.get("series") != n.value):
                    return False, "it requires an index clause for this contract length"
        lead = self.value("lead_time.firm")
        if lead is not None and structure.get("lead_time_days") is not None and structure["lead_time_days"] < lead:
            return False, f"it holds its lead time at {lead:g} days"
        cb = self.value("chargeback.too_high")
        mine = structure.get("chargeback_eur_per_complaint")
        if cb is not None and mine is not None and (mine > 0 if cb <= 0 else mine >= cb):
            return False, f"it refused a chargeback of {cb:g}"
        return True, ""

    def wants(self):
        """Terms the supplier asks for, that a trade could give: subject -> field."""
        subjects = ("payment.faster", "contract.longer", "volume.commitment", "index.required")
        return {s: dict(SUBJECTS.values())[s] for s in subjects if self.holds(s)}

    def cash_rate(self):
        """Its cost of money per year, read from two of its own quotes that differ only in payment
        terms (None until it shows such a pair): observed, not assumed."""
        notes = self.notes_on("cash.rate", kinds=("observed",))
        return notes[-1].value if notes else None

    def summary(self):
        return {"holds": [f"{n.kind}: {n.subject}" + (f"={n.value}" if n.value is not None else "")
                          + (f" if {n.condition}" if n.condition else "") for n in self.notes if n.active],
                "withdrawn": [f"{n.subject}: {n.why}" for n in self.notes if not n.active],
                "their_offers": len(self.theirs), "our_offers": len(self.ours)}

    def to_dict(self):
        return {"notes": [asdict(n) for n in self.notes], "theirs": len(self.theirs), "ours": len(self.ours)}

    # -- writing -------------------------------------------------------------------------------
    def _withdraw(self, subject, why, when=lambda n: True):
        for n in self.notes_on(subject, kinds=("statement", "hypothesis")):
            if when(n):
                n.active, n.why = False, why

    def prior(self, flags, stated=None):
        """What memory says of this supplier from earlier negotiations: hypotheses."""
        for flag, on in (flags or {}).items():
            if on and flag in PRIORS and not self.holds(PRIORS[flag], kinds=("hypothesis",)):
                value = (stated or {}).get(dict(SUBJECTS.values()).get(PRIORS[flag]))
                self.notes.append(Note("hypothesis", PRIORS[flag], value, source="memory"))

    def situation(self, dossier):
        """The dossier's readings of the supplier that bear on a trade: hypotheses."""
        for key, subject in (("supplier.cash_need", "payment.faster"), ("supplier.capacity_tight", "capacity.tight"),
                             ("supplier.free_capacity", "capacity.free")):
            if dossier is not None and dossier.has(key) and not self.holds(subject, kinds=("hypothesis", "statement")):
                self.notes.append(Note("hypothesis", subject, source="dossier"))

    def said(self, message):
        """One of our own messages."""
        sheets = [dict(ts.get("terms", ts)) for ts in message.get("term_sheets") or []]
        if sheets or message.get("refs"):
            self.ours.append({"sheets": sheets, "refs": list(message.get("refs") or [])})

    def heard(self, message, signals=None, denials=None):
        """A supplier message: what it did (its sheets), then what it said, then what it took back."""
        at = len(self.theirs)
        sheets = [(ts.get("term_sheet_id"), dict(ts.get("terms") or {})) for ts in message.get("term_sheets") or []]
        sheets = [(i, t) for i, t in sheets if t.get("unit_price") is not None]
        previous = self.theirs[-1]["sheets"] if self.theirs else []
        self.theirs.append({"status": message.get("status"), "sheets": sheets})
        if message.get("claim_results") and self.ours:
            self.arguments.append({"refs": self.ours[-1]["refs"],
                                   "results": [r.get("result") for r in message["claim_results"]]})
        for _, terms in sheets:
            for f, v in terms.items():
                if f != "unit_price" and not isinstance(v, dict):
                    self.granted.setdefault(f, set()).add(v)
        self._contradictions(sheets, previous)
        self._rate(sheets, at)
        text = message.get("body") or ""
        standing = sheets[0][1] if sheets else {}
        for kind in sorted(signals or ()):
            if kind not in SUBJECTS:
                continue
            subject, fld = SUBJECTS[kind]
            value, condition = None, {}
            stated = (getattr(signals, "values", None) or {}).get(fld) if fld else None
            if subject == "index.required":
                clause = standing.get("index_clause")
                value = clause.get("series") if isinstance(clause, dict) else None
                m = MONTHS_RE.search(text.lower())
                months = int(m.group(1) or m.group(2)) if m else standing.get("contract_months")
                if months:
                    condition = {"contract_months": months}
            elif subject == "lead_time.firm":
                value = stated if stated is not None else standing.get("lead_time_days")
            elif subject == "chargeback.too_high":
                asked = (self.ours[-1]["sheets"][0] if self.ours and self.ours[-1]["sheets"] else {})
                value = stated if stated is not None else asked.get("chargeback_eur_per_complaint")
            elif subject == "price.floor":
                value = stated if stated is not None else standing.get("unit_price")
            if subject != "price.floor":  # said again: one note, the latest wording of it
                self.notes = [n for n in self.notes
                              if not (n.subject == subject and n.kind == "statement" and n.active)]
            self.notes.append(Note("statement", subject, value, condition, at))
        for kind in sorted(denials or ()):
            if kind in SUBJECTS:
                self._withdraw(SUBJECTS[kind][0], f"taken back in its message {at}")
        return self

    def _contradictions(self, sheets, previous):
        """Its own offers outweigh what it said: a statement they contradict stops holding."""
        price = sheets[0][1].get("unit_price") if sheets else None
        before = previous[0][1].get("unit_price") if previous else None
        for _, t in sheets:
            if "index_clause" in t and t["index_clause"] is None:
                self._withdraw("index.required", "it offered a fixed price for that contract length",
                               when=lambda n, t=t: n.holds_for(t))
            if t.get("lead_time_days") is not None:
                self._withdraw("lead_time.firm", f"it offered {t['lead_time_days']} days",
                               when=lambda n, t=t: n.value is not None and t["lead_time_days"] < n.value)
            if t.get("chargeback_eur_per_complaint") is not None:
                cb = t["chargeback_eur_per_complaint"]
                self._withdraw("chargeback.too_high", f"it offered a chargeback of {cb:g} itself",
                               when=lambda n, cb=cb: n.value is not None
                               and (cb > 0 if n.value <= 0 else cb >= n.value))
        if price is not None:
            self._withdraw("price.floor", f"it then offered {price}",
                           when=lambda n: n.value is not None and price < n.value - TOLERANCE)
            if before is not None and price < before - TOLERANCE:
                self._withdraw("price.frozen", f"it then lowered its price to {price}")

    def _rate(self, sheets, at):
        """Two of its sheets that differ only in payment terms price its money."""
        for i, (_, a) in enumerate(sheets):
            for _, b in sheets[i + 1:]:
                rest = {k for k in set(a) | set(b)
                        if k not in ("unit_price", "payment_days") and a.get(k) != b.get(k)}
                days = (b.get("payment_days") or 0) - (a.get("payment_days") or 0)
                if rest or not days or not a.get("unit_price") or not b.get("unit_price"):
                    continue
                rate = (b["unit_price"] / a["unit_price"] - 1) * 360 / days
                if 0 < rate < 1:
                    self.notes.append(Note("observed", "cash.rate", round(rate, 4), at=at))

    # -- replay --------------------------------------------------------------------------------
    @classmethod
    def rebuild(cls, events, read=reader.read, denied=reader.denied, start=None, seen=0):
        """The state of a thread from its messages, in order. `start`, `seen`: continue an existing
        state from the `seen`-th event (the live path); without them, a full replay after a restart."""
        state = start or cls()
        for message in events[seen:]:
            if message.get("from") == "buyer":
                state.said(message)
            else:
                text = message.get("body") or ""
                state.heard(message, read(text) if text else set(), denied(text) if text else set())
        return state
