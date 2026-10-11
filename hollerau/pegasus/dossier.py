"""The case as we understand it before the first e-mail: one preparation for offers and arguments.

`prepare` gathers what the existing compilers already know - the evidence lane's economics and
signals (`compile_case`, `signals`: what `planner_hints` wraps), Codex's supplier dossier
(`Intelligence.brief`), the package facts - and says for every element what it is:
  fact       a number or constraint we can point to (case file, contract, order line, quote, index)
  statement  what the supplier says (its ask, its reasons); a negotiating position, not a truth
  estimate   our reading or computation (should-cost, a signal read in a note, a cost hypothesis)
Each carries its sources. `unknowns` lists what could change the decision and is not known - the
supplier's reservation price is always one of them. No new analysis is built here: this module only
puts the existing ones side by side, in one vocabulary, so that the choice of the offer and the
choice of the arguments read the same thing. Never raises: a brick that fails leaves its part
empty and a line in `diagnostics`.
"""

import logging
import re
from dataclasses import asdict, dataclass, field

from . import economics as eco
from .evaluation import charge_applies

try:  # the evidence lane (hollerau/evidence): economics, signals, order lines, indices
    from hollerau.evidence.economics import compile_case
    from hollerau.evidence.facts import comparable, facts_of, has
    from hollerau.evidence.index import driver_moves, weighted_move_pct
    from hollerau.evidence.orders import order_history
    from hollerau.evidence.quote import case_quotes
    from hollerau.evidence.signals import signals as read_signals

    evidence = True
except Exception:  # pragma: no cover - the package is optional, as in agent.py
    evidence = False

log = logging.getLogger("pegasus")

# One vocabulary for the supplier's situation: {key: (evidence signal names, intel signal types)}.
SITUATION = {
    "cash_need": (("cash_need",), ("cash_sensitive",)),
    "free_capacity": (("free_capacity",), ("free_capacity",)),
    "capacity_tight": (("full_order_book",), ("capacity_tight",)),
    "material_hedged": (("material_hedged",), ("hedged_inputs",)),
    "approval_ladder": (("committee",), ("approval_ladder",)),
    "price_frozen": (("list_price_only",), ("price_frozen",)),
    "account_exit": (("small_account_review", "not_strategic"), ("account_exit",)),
    "open_costing": (("open_book",), ("open_costing",)),
}
OPPOSITES = [("free_capacity", "capacity_tight")]
DRIVER_RE = re.compile(r"\b([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+) rose ([\d.]+) ?% in twelve months "
                       r"and is (\d+) ?% of our cost")
RATIO_NOTE = "0.98 x the package's should-cost: the ratio seen on three practice cases (P01-P03)"


@dataclass
class Item:
    key: str  # what it is about: "price.current", "supplier.cash_need", "cost.should", ...
    value: object
    status: str  # fact | statement | estimate
    sources: list = field(default_factory=list)  # data IDs, or "case", "quote", "opening"
    note: str = ""


@dataclass
class Dossier:
    case_id: str
    supplier_id: str
    constraints: dict = field(default_factory=dict)  # must-haves, fixed terms, need - certain
    alternative: dict = field(default_factory=dict)  # what walking away costs
    levers: list = field(default_factory=list)  # what each term is worth to us, in EUR
    best_package: dict = field(default_factory=dict)
    references: list = field(default_factory=list)  # comparable prices, each an Item
    situation: list = field(default_factory=list)  # the supplier's situation, each an Item
    stated: list = field(default_factory=list)  # what the supplier put forward in its opening
    hypotheses: list = field(default_factory=list)  # supplier cost models for the relationship charge
    unknowns: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)

    def get(self, key):
        """The first reference or situation item with this key, else None."""
        return next((i for i in self.references + self.situation + self.stated if i.key == key), None)

    def has(self, key):
        item = self.get(key)
        return item is not None and bool(item.value)

    def to_dict(self):
        out = asdict(self)
        for h in out["hypotheses"]:  # the supplier model repeats the standard terms: keep the numbers
            h["supplier"] = {k: v for k, v in h["supplier"].items() if k != "standard"}
        return out


def _constraints(case, d):
    b = case["buyer"]
    d.constraints = {
        "negotiable": list(case.get("negotiable", [])),
        "must_haves": list(b.get("must_haves") or []),
        "fixed_terms": dict(case.get("fixed_terms") or {}),
        "need_per_year": b.get("need_per_year"),
        "horizon_years": b.get("horizon_years"),
        "need_lead_time_days": b.get("need_lead_time_days"),
        "category_goal": b.get("category_goal"),
        "round_limit": case.get("round_limit", 10),
    }
    alt = b.get("alternative") or {}
    c_alt = eco.alt_cost(case)
    d.alternative = {"kind": alt.get("kind") or "none", "ref": alt.get("ref"),
                     "terms": dict(alt.get("terms") or {}), "c_alt": c_alt}
    if c_alt == float("inf"):
        d.unknowns.append("alternative: none in the case file - no deal scores nothing")


def eco_std(std):
    return {k: v for k, v in (std or {}).items() if not k.startswith("_")} or None


def _economics(case, package, std, d):
    """Levers and best package: the evidence lane's compiler, not a second one."""
    if not evidence:
        d.diagnostics.append("evidence lane unavailable: no levers")
        return
    econ = compile_case(case, eco_std(std), package)
    d.levers = [{"field": lv.field, "best": lv.best, "worst": lv.worst, "eur": round(lv.cost_of_forgetting_eur, 2)}
                for lv in econ.levers if lv.cost_of_forgetting_eur]
    d.best_package = dict(econ.best_package or {})


def _references(case, package, sid, events, sig, d):
    """Prices we can set against the supplier's ask, each with what it is and where it comes from."""
    b = case["buyer"]
    refs = d.references
    opening = next((m for m in events or [] if m.get("from") != "buyer"), {})
    sheet = (opening.get("term_sheets") or [{}])[0]
    ask = (sheet.get("terms") or {}).get("unit_price")
    if ask:
        refs.append(Item("price.asked", ask, "statement", [sheet.get("term_sheet_id") or "opening"],
                         "its opening quote"))
    if b.get("current_unit_price"):
        ctr = [r for r in case.get("refs", []) if r.startswith("ctr:")]
        refs.append(Item("price.current", b["current_unit_price"], "fact", ctr or ["case"], "what we pay today"))
    if sig.get("asked_pct") is not None:
        refs.append(Item("price.asked_increase_pct", sig["asked_pct"], "statement",
                         [case.get("trigger_doc") or "case"], "the increase its letter asks for"))
    if not evidence or package is None:
        d.unknowns.append("comparables: no data package - order lines, quotes and indices not read")
        return
    facts = facts_of(case, package)
    single = len(case.get("parts") or []) == 1
    lines = order_history(case, package, facts, sid)
    if lines:
        low, last = min(lines, key=lambda r: (r["price"], r["day"])), lines[-1]
        note = " - not to be cited in an RFQ (it tells the rivals what we pay)" if case.get("type") == "rfq" else ""
        refs.append(Item("price.orders_low", low["price"], "fact", [low["id"]],
                         f"lowest order of the last 24 months ({low['order_date'][:7]}){note}"))
        refs.append(Item("price.orders_last", last["price"], "fact", [last["id"]],
                         f"latest order ({last['order_date'][:7]}){note}"))
    for q in case_quotes(case):
        f = facts.get(q)
        if has(f, "unit_price") and comparable(case, package, f) and f.get("supplier") not in case["suppliers"]:
            refs.append(Item("price.quote", f["unit_price"], "fact", [q], "another supplier's quote, same part"))
    cost_id = f"cost:{case['parts'][0].split(':')[1]}" if single else None
    cost = facts.get(cost_id) if cost_id else None
    if has(cost, "unit_cost") and comparable(case, package, cost):
        refs.append(Item("cost.should", cost["unit_cost"], "estimate", [cost_id],
                         "our should-cost: an estimate of its cost, not a price it accepts"))
    if single and getattr(package, "db", None) is not None:
        moves = driver_moves(case["parts"][0], package, facts)
        if moves:
            pct = round(weighted_move_pct(moves), 2)
            ids = [i for m in moves for i in (m.earlier, m.later)]
            refs.append(Item("cost.drivers_12m_pct", pct, "fact", ids,
                             "12-month move of the part's cost drivers, weighted by their share"))
            if b.get("current_unit_price"):
                refs.append(Item("price.cost_justified", round(b["current_unit_price"] * (1 + pct / 100), 4),
                                 "estimate", ids, "today's price moved by its cost drivers over 12 months"))


def _situation(case, package, sid, sig, intel, d):
    """What the notes, letters and news say about the supplier - one vocabulary for both readers."""
    ours = ((sig.get("suppliers") or {}).get(sid)) or {}
    theirs, absent = {}, False
    if intel is not None:
        try:
            brief = intel.brief(case, sid)
            absent = brief.get("status") == "supplier_absent_from_package"
            for s in brief.get("signals") or []:
                theirs.setdefault(s.get("type"), []).extend(
                    e.get("ref") for e in s.get("evidence") or [] if e.get("ref"))
        except Exception as e:
            d.diagnostics.append(f"intel brief unavailable: {type(e).__name__}")
    for key, (ev_names, intel_types) in SITUATION.items():
        sources = [r for n in ev_names for r in (ours.get(n) or []) if isinstance(r, str)]
        sources += [r for t in intel_types for r in theirs.get(t, [])]
        if not sources:
            continue
        value = True
        if key == "material_hedged" and ours.get("material_hedged_until"):
            value = ours["material_hedged_until"]
        if key == "approval_ladder" and ours.get("committee_above_pct") is not None:
            value = ours["committee_above_pct"]
        d.situation.append(Item(f"supplier.{key}", value, "estimate", sorted(set(sources)),
                                "read in notes, letters or news: a sourced reading, not a fact about its books"))
    if ours.get("single_source") is not None:
        d.situation.append(Item("supplier.single_source", bool(ours["single_source"]), "fact", ["sourcing"],
                                "whether a part of the case has no other active or qualified source"))
    for one, other in OPPOSITES:
        if d.has(f"supplier.{one}") and d.has(f"supplier.{other}"):
            d.diagnostics.append(f"conflicting signals: {one} and {other} - neither steers a trade")
    if not absent and package is not None:
        try:
            absent = not package.ids(sid)  # no row of the package carries this supplier ID
        except Exception:
            absent = False
    if absent:
        d.unknowns.append("supplier: absent from the data package - no note, no history to read")


def _stated(events, d):
    """What the supplier put forward in its opening: its cost drivers, as it states them."""
    text = " ".join(m.get("body", "") for m in events or [] if m.get("from") != "buyer")
    for series, change, share in DRIVER_RE.findall(text):
        d.stated.append(Item(f"driver.{series}", {"change_pct": float(change), "share_pct": float(share)},
                             "statement", ["opening"], "a reason it gives for its price"))


def cost_hypotheses(case, package, std, opening_price):
    """Supplier cost models for the relationship charge: two when the package has a comparable
    should-cost - the calibrated ratio and the raw estimate - so a choice that hangs on the
    difference shows; [] when the charge does not apply or cannot be estimated."""
    if not charge_applies(case):
        return []
    base = eco.supplier_model(case, eco_std(std) or {}, opening_price, getattr(package, "facts", None) or {})
    if not base:
        return []
    raw = {**base, "full_cost": base["full_cost"] / eco.SHOULD_COST_RATIO}
    return [
        {"name": "should_cost_calibrated", "supplier": base, "provenance": RATIO_NOTE},
        {"name": "should_cost_raw", "supplier": raw,
         "provenance": "the package's should-cost as published (confidence stated in the data), uncalibrated"},
    ]


def _hypotheses(case, package, std, events, d):
    """Without a hypothesis the charge is an unknown, not zero."""
    if not charge_applies(case):
        return
    opening = next((m for m in events or [] if m.get("from") != "buyer"), {})
    price = ((opening.get("term_sheets") or [{}])[0].get("terms") or {}).get("unit_price")
    d.hypotheses = cost_hypotheses(case, package, std, price)
    if not d.hypotheses:
        d.unknowns.append("relationship charge: no comparable should-cost - it applies and cannot be "
                          "estimated; C without it is an optimistic bound")
        return
    d.unknowns.append("supplier cash rate: the buyer's rate is assumed until two of its quotes that differ "
                      "only in payment terms let us read it")


def prepare(case, package, sid, events=None, std=None, intel=None):
    """The dossier of one supplier thread. `events`: the thread so far (its opening quote at least);
    `std`: the supplier's standard terms from its quote; `intel`: an `Intelligence` (optional)."""
    d = Dossier(case.get("case_id", "?"), sid)
    d.unknowns.append("supplier reservation price: never known - its ask, its cost and what it would "
                      "accept are three different things")
    sig = {}
    if evidence and package is not None:
        try:
            sig = read_signals(case, package)  # never raises; one reading for prices and situation
        except Exception as e:  # pragma: no cover - belt and braces
            d.diagnostics.append(f"signals unavailable: {type(e).__name__}")
    for name, step in (
        ("constraints", lambda: _constraints(case, d)),
        ("stated", lambda: _stated(events, d)),
        ("hypotheses", lambda: _hypotheses(case, package, std, events, d)),
        ("economics", lambda: _economics(case, package, std, d)),
        ("references", lambda: _references(case, package, sid, events, sig, d)),
        ("situation", lambda: _situation(case, package, sid, sig, intel, d)),
    ):
        try:
            step()
        except Exception as e:
            log.exception("%s %s: dossier %s failed", d.case_id, sid, name)
            d.diagnostics.append(f"{name} failed: {type(e).__name__}")
    if not eco_std(std):
        d.unknowns.append("standard terms: no quote read - the buyer's plan fills the gaps")
    return d


def price_references(dossier, kinds=("fact",)):
    """Comparable prices by standing, lowest first: [(price, Item)]. Percentages and costs are not prices."""
    keys = ("price.current", "price.orders_low", "price.orders_last", "price.quote", "price.cost_justified")
    rows = [(i.value, i) for i in dossier.references if i.key in keys and i.status in kinds
            and isinstance(i.value, (int, float)) and i.value > 0]
    return sorted(rows, key=lambda r: r[0])
