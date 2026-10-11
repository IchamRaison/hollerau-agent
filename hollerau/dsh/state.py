"""The factual state of one case, built from what the arena answered - never from what the model
remembers. The model gets `snapshot()`; tools and the coordinator read and write under `lock`.
"""

import threading
import time

from arena_kit.play import ENDED, MOVE_LIMIT_S, latest

from ..pegasus import economics as eco
from ..pegasus.agent import direct_cost, supplier_reference
from . import economics, evidence, patterns

BODY_CHARS = 3000  # of a supplier e-mail shown in the snapshot; `read_thread` gives all of it


class CaseState:
    def __init__(self, case, threads, package=None, clock=time.monotonic):
        self.case, self.threads, self.pkg, self.clock = case, threads, package, clock
        self.lock = threading.RLock()
        self.version = 0
        self.inflight = set()  # suppliers we are waiting on: our message is out, no reply yet
        self.arrived = {sid: clock() for sid in threads}  # when the supplier's latest e-mail came in
        self.errors = {}  # supplier -> what the arena last refused, shown to the model once
        self.hypotheses = []  # the model's revisable notes: {"id", "text", "status", "sources", ...}
        self.by_model = set()  # suppliers the model has written to (the coded fallback did not play every move)
        self.result = None
        self.std, self.estimate = {}, {}
        facts = getattr(package, "facts", None) or {}
        self.facts = {**facts, **(case.get("facts") or {})}
        self.records = evidence.Records(case, package)
        for sid, events in threads.items():
            self._model_supplier(sid, events)

    def _model_supplier(self, sid, events):
        self.std[sid] = supplier_reference(self.case, events)
        first = next((m for m in events if m.get("from") != "buyer"), {})
        sheets = first.get("term_sheets") or []
        price = (sheets[0].get("terms") or {}).get("unit_price") if sheets else None
        self.estimate[sid] = eco.supplier_model(self.case, self.std[sid], price, self.facts, sid)

    def set_estimate(self, sid, full_cost, cost_of_money=None, source=""):
        """The model's own estimate of a supplier's full cost per unit (e.g. from its cost
        breakdown): from now on every cost of this thread includes the relationship charge it implies."""
        with self.lock:
            old = self.estimate.get(sid) or {}
            self.estimate[sid] = {
                "standard": economics.clean(self.std.get(sid)),
                "full_cost": float(full_cost),
                "interest_rate": float(
                    cost_of_money if cost_of_money is not None else old.get("interest_rate", eco.CALM_RATE)
                ),
                "_source": str(source)[:200] or "the model's estimate",
            }
            self.version += 1

    # -- events --------------------------------------------------------------------------------
    def sent(self, sid, message):
        with self.lock:
            self.threads[sid].append({**message, "from": "buyer"})
            self.inflight.add(sid)
            self.version += 1

    def replied(self, sid, reply):
        with self.lock:
            self.threads[sid].append(reply)
            self.inflight.discard(sid)
            self.arrived[sid] = self.clock()
            self.version += 1

    def refused(self, sid, message, detail):
        """The arena refused our message (422): nothing happened, no round was used."""
        with self.lock:
            if self.threads[sid] and self.threads[sid][-1].get("from") == "buyer":
                self.threads[sid].pop()
            self.inflight.discard(sid)
            self.errors[sid] = str(detail)[:600]
            self.version += 1

    # -- reads ---------------------------------------------------------------------------------
    def status(self, sid):
        return latest(self.threads[sid]).get("status") or "open"

    def live(self):
        return [s for s in self.threads if self.status(s) not in ENDED]

    def moves_left(self, sid):
        return self.case.get("round_limit", 10) - sum(m.get("from") == "buyer" for m in self.threads[sid])

    def seconds_left(self, sid):
        return MOVE_LIMIT_S - (self.clock() - self.arrived[sid])

    def ready(self):
        """Suppliers whose e-mail waits for our answer."""
        return [s for s in self.live() if s not in self.inflight and self.threads[s][-1].get("from") != "buyer"]

    def standing(self, sid):
        """(term_sheet_id, terms) of the sheet we could accept now, else (None, {})."""
        sheets = latest(self.threads[sid]).get("term_sheets") or []
        return (sheets[0].get("term_sheet_id"), sheets[0].get("terms") or {}) if sheets else (None, {})

    def evaluate(self, sid, terms):
        return economics.evaluate(self.case, terms, self.std.get(sid), self.estimate.get(sid))

    def cost(self, sid, terms):
        return economics.cost(self.case, terms, self.std.get(sid), self.estimate.get(sid))

    def best_standing(self):
        """(cost, supplier, term_sheet_id) of the cheapest signable sheet that keeps the must-haves."""
        best = None
        for sid in self.live():
            sheet_id, terms = self.standing(sid)
            e = self.evaluate(sid, terms) if sheet_id else None
            if e and e["total_eur"] is not None and e["must_haves_ok"]:
                best = min(best or (e["total_eur"], sid, sheet_id), (e["total_eur"], sid, sheet_id))
        return best

    def c_open(self):
        """C of the cheapest opening quote that keeps the must-haves: the zero point of the score."""
        out = None
        for sid, events in self.threads.items():
            first = next((m for m in events if m.get("from") != "buyer"), {})
            for ts in (first.get("term_sheets") or [])[:1]:
                e = self.evaluate(sid, ts.get("terms") or {})
                if e["total_eur"] is not None and e["must_haves_ok"]:
                    out = e["total_eur"] if out is None else min(out, e["total_eur"])
        return out

    def _same_cost_on_other_terms(self, sid, sheets, limit=3):
        """The supplier's standing sheet costs us C. On which other combinations of terms could we
        pay a HIGHER unit price than its own and still not pay more than C? Each entry is a sheet
        that costs us the same as its offer: any price below it on those terms is better for us
        than its offer, and a price above its own is something to offer it."""
        if not sheets or sheets[0]["cost_eur"] is None:
            return []
        its_price = (sheets[0]["terms"] or {}).get("unit_price")
        found = economics.structures_for_target(
            self.case, sheets[0]["cost_eur"], self.std.get(sid), self.estimate.get(sid), limit=200
        )
        better = [
            x for x in found["sheets"] if x["reached"] and its_price and x["terms"]["unit_price"] > its_price * 1.002
        ]
        return [{"terms": x["terms"], "costs_us_eur": x["total_eur"]} for x in better[:limit]]

    def _thread_view(self, sid):
        events = self.threads[sid]
        last = latest(events)
        sheets = []
        for i, ts in enumerate(last.get("term_sheets") or []):
            e = self.evaluate(sid, ts.get("terms") or {})
            sheets.append(
                {
                    "term_sheet_id": ts.get("term_sheet_id"),
                    "can_be_accepted_now": i == 0,
                    "terms": ts.get("terms"),
                    "cost_eur": e["total_eur"],
                    "commercial_eur": e["commercial_eur"],
                    "relationship_eur": e["relationship_eur"],
                    "must_haves_ok": e["must_haves_ok"],
                }
            )
        view = {
            "supplier_id": sid,
            "status": self.status(sid),
            "awaits_your_answer": sid in self.ready(),
            "our_message_in_flight": sid in self.inflight,
            "seconds_left_to_answer": round(self.seconds_left(sid), 1) if sid in self.ready() else None,
            "messages_you_may_still_send": self.moves_left(sid),
            "supplier_sheets": sheets,
            "fields_it_left_to_its_standard_terms": last.get("missing_fields") or [],
            "its_standard_terms": economics.clean(self.std.get(sid)),
            "checks_of_your_last_arguments": last.get("claim_results") or [],
            "its_last_email": (last.get("body") or "")[:BODY_CHARS],
            "attachments_of_its_last_email": [a.get("name") for a in last.get("attachments") or []],
            "movement": economics.movement(self.case, events, self.std.get(sid), self.estimate.get(sid)),
        }
        trades = self._same_cost_on_other_terms(sid, sheets)
        if trades:
            view["what_its_standing_sheet_costs_us_would_buy_on_other_terms"] = trades
        if sheets:
            base = economics.clean({**(self.std.get(sid) or {}), **(sheets[0]["terms"] or {})})
            view["what_each_term_option_costs_us_eur"] = economics.levers(
                self.case, base, self.std.get(sid), self.estimate.get(sid)
            )
        price = (sheets[0]["terms"] or {}).get("unit_price") if sheets else None
        drivers = " ".join(m.get("body") or "" for m in events if m.get("from") != "buyer")
        view["data_you_can_cite"] = evidence.citable(
            self, sid, self.records.arguments(sid, price, drivers) if price else []
        )
        signals = self.records.signals(sid)
        if signals:
            view["what_our_records_say_about_this_supplier"] = signals
        said = patterns.signals(events, skip_case=self.case["case_id"])
        if said:
            view["signals_it_gave"] = said
        arithmetic = evidence.stated_drivers(events, self.case["buyer"].get("current_unit_price"))
        if arithmetic:
            view["its_own_cost_arithmetic"] = arithmetic
        if sid in self.errors:
            view["arena_refused_your_last_message"] = self.errors[sid]
        direct = direct_cost(events)
        if direct:
            view["direct_cost_per_unit_in_its_cost_breakdown"] = round(direct, 2)
        if self.estimate.get(sid):
            est = self.estimate[sid]
            view["our_estimate_of_this_supplier"] = {
                "full_cost_per_unit": round(est["full_cost"], 2),
                "its_cost_of_money": est["interest_rate"],
                "standing": "an estimate, not a fact: "
                + est.get("_source", "from the part's should-cost and the correspondence"),
            }
            check = economics.estimate_check(self.case, events, self.std.get(sid), est)
            if check:
                view["does_its_counter_fit_our_estimate"] = check
        elif economics.charge_applies(self.case):
            view["our_estimate_of_this_supplier"] = None
        return view

    def snapshot(self):
        """Everything the model needs to decide, as plain data."""
        with self.lock:
            case, b = self.case, self.case["buyer"]
            alt = b.get("alternative") or {}
            best = self.best_standing()
            return {
                "state_version": self.version,
                "case": {
                    "case_id": case["case_id"],
                    "type": case.get("type"),
                    "title": case.get("title"),
                    "briefing": case.get("briefing"),
                    "parts": case.get("parts"),
                    "category_goal": b.get("category_goal"),
                    "negotiable_fields": case["negotiable"],
                    "term_options": case.get("term_options", {}),
                    "fixed_terms": case.get("fixed_terms", {}),
                    "must_haves": b.get("must_haves", []),
                    "messages_per_thread": case.get("round_limit", 10),
                    "data_ids_the_case_points_to": case.get("refs", []),
                    "buyer": {k: v for k, v in b.items() if k not in ("alternative", "must_haves")},
                },
                "without_a_deal": {
                    "kind": alt.get("kind", "none"),
                    "terms": alt.get("terms"),
                    "cost_eur": economics.alternative(case),
                    "note": "no deal scores this alternative; with no alternative it scores 0",
                },
                "relationship_charge": (
                    "applies: a deal that leaves the supplier below its sustainable margin costs us"
                    if economics.charge_applies(case)
                    else "does not apply in this case"
                ),
                "cost_of_cheapest_opening_quote_eur": self.c_open(),
                "cheapest_sheet_you_could_accept_now": (
                    {"cost_eur": best[0], "supplier_id": best[1], "term_sheet_id": best[2]} if best else None
                ),
                "what_other_cases_of_this_kind_showed": evidence.similar_cases(case),
                "threads": [self._thread_view(s) for s in self.threads],
                "your_notes": self.hypotheses,
            }
