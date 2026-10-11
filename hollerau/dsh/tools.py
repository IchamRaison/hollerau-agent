"""The model's tools, served to DeepSeek Harness over MCP (local Streamable HTTP).

`Desk` holds the open decisions; every tool takes the opaque `decision_id` the coordinator gave
the model for this turn, and the desk derives the case from it - the model never names a case.
`commit_decision` is the only tool with an effect, and even it sends nothing: it hands a
validated, immutable batch to the coordinator, which is the only thing that talks to the arena.
The tool methods are plain Python (tested without MCP); `build_server` only wraps them.
"""

import logging
import secrets
import socket
import threading
import time

from . import economics, validation

log = logging.getLogger("pegasus.dsh")

ATTACHMENT_CHARS = 6000
MAX_ROWS = 50


class Decision:
    """One turn of the model on one case: a lease that is active, committed or expired."""

    def __init__(self, state, budget_s, clock=time.monotonic):
        self.id = "dec-" + secrets.token_hex(6)
        self.state, self.clock = state, clock
        self.deadline = clock() + budget_s
        self.drafts, self.batch, self.status = {}, None, "active"
        self.done = threading.Event()
        self.calls = []  # (tool, seconds since the lease opened): the trace of the turn
        self.opened = clock()

    def seconds_left(self):
        return self.deadline - self.clock()

    def expire(self):
        if self.status == "active":
            self.status = "expired"


class Desk:
    def __init__(self):
        self.lock = threading.Lock()
        self.decisions = {}

    def open(self, state, budget_s):
        d = Decision(state, budget_s)
        with self.lock:
            self.decisions[d.id] = d
        return d

    def _get(self, decision_id, tool):
        d = self.decisions.get(decision_id)
        if d is None:
            return None, {"error": "UNKNOWN_DECISION", "detail": "use the decision_id given in this turn's message"}
        d.calls.append((tool, round(d.clock() - d.opened, 2)))
        return d, None

    def _open(self, decision_id, tool):
        """For tools that prepare or engage: the lease must still be active and in time."""
        d, err = self._get(decision_id, tool)
        if err:
            return None, err
        if d.status == "committed":
            return None, {"error": "DECISION_COMMITTED", "detail": "this turn's decision is already engaged; stop here"}
        if d.status == "expired" or d.seconds_left() <= 0:
            d.expire()
            return None, {
                "error": "EXPIRED_DECISION",
                "detail": "this turn's time is over; nothing more can be sent now",
            }
        return d, None

    # -- read-only tools ------------------------------------------------------------------------
    def get_case_state(self, decision_id):
        d, err = self._get(decision_id, "get_case_state")
        if err:
            return err
        return {**d.state.snapshot(), "seconds_left_in_this_turn": round(d.seconds_left(), 1)}

    def read_thread(self, decision_id, supplier_id):
        d, err = self._get(decision_id, "read_thread")
        if err:
            return err
        events = d.state.threads.get(supplier_id)
        if events is None:
            return {"error": "UNKNOWN_SUPPLIER", "suppliers": list(d.state.threads)}
        out = []
        for m in events:
            item = {
                "from": "you" if m.get("from") == "buyer" else (m.get("from") or supplier_id),
                "subject": m.get("subject"),
                "body": m.get("body"),
                "term_sheets": m.get("term_sheets") or [],
            }
            if m.get("from") != "buyer":
                item.update(
                    status=m.get("status"),
                    missing_fields=m.get("missing_fields") or [],
                    claim_results=m.get("claim_results") or [],
                    signals=m.get("signals") or {},
                )
                item["attachments"] = [
                    {"name": a.get("name"), "text": (a.get("text") or "")[:ATTACHMENT_CHARS]}
                    for a in m.get("attachments") or []
                ]
            elif m.get("refs"):
                item["refs"] = m["refs"]
            out.append(item)
        return {"supplier_id": supplier_id, "messages": out}

    def evaluate_offers(self, decision_id, supplier_id, term_sheets):
        d, err = self._get(decision_id, "evaluate_offers")
        if err:
            return err
        if supplier_id not in d.state.threads:
            return {"error": "UNKNOWN_SUPPLIER", "suppliers": list(d.state.threads)}
        out = [d.state.evaluate(supplier_id, dict(ts.get("terms", ts))) for ts in term_sheets or []]
        totals = [e["total_eur"] for e in out if e["total_eur"] is not None]
        return {
            "supplier_id": supplier_id,
            "evaluations": out,
            "cheapest_for_us_eur": min(totals) if totals else None,
            "alternative_without_a_deal_eur": economics.alternative(d.state.case),
        }

    def search_structures(self, decision_id, supplier_id, target_cost_eur, restrict=None, limit=12):
        d, err = self._get(decision_id, "search_structures")
        if err:
            return err
        st = d.state
        if supplier_id not in st.threads:
            return {"error": "UNKNOWN_SUPPLIER", "suppliers": list(st.threads)}
        try:
            target = float(target_cost_eur)
        except (TypeError, ValueError):
            return {"error": "INVALID_TERMS", "detail": "target_cost_eur must be a number of EUR"}
        return {
            "supplier_id": supplier_id,
            **economics.structures_for_target(
                st.case,
                target,
                st.std.get(supplier_id),
                st.estimate.get(supplier_id),
                restrict or None,
                max(1, min(int(limit or 12), 40)),
            ),
        }

    def lookup_facts(self, decision_id, ids):
        d, err = self._get(decision_id, "lookup_facts")
        if err:
            return err
        st, out = d.state, {}
        offers = {
            ts["term_sheet_id"]: {"supplier": sid, "terms": ts.get("terms")}
            for sid, events in st.threads.items()
            for m in events
            for ts in m.get("term_sheets") or []
            if ts.get("term_sheet_id")
        }
        for ref in (ids or [])[:40]:
            if ref in st.facts:
                out[ref] = st.facts[ref]
            elif ref in offers:
                out[ref] = offers[ref]
            elif ref in (st.case.get("refs") or []):
                out[ref] = {"known": False, "note": "named by the case, value not in our data"}
            else:
                out[ref] = None
        return {"facts": out, "note": "null: not a known ID - do not cite it"}

    def query_data(self, decision_id, sql, limit=20):
        d, err = self._get(decision_id, "query_data")
        if err:
            return err
        if d.state.pkg is None:
            return {"error": "NO_DATA_PACKAGE"}
        try:
            return {"rows": d.state.pkg.query(sql, limit=max(1, min(int(limit or 20), MAX_ROWS)))}
        except Exception as e:  # a bad query is the model's to fix, never a crash of the turn
            return {"error": "QUERY_FAILED", "detail": f"{type(e).__name__}: {e}"[:400]}

    def update_hypotheses(self, decision_id, notes):
        d, err = self._get(decision_id, "update_hypotheses")
        if err:
            return err
        st = d.state
        with st.lock:
            by_id = {h["id"]: h for h in st.hypotheses}
            for n in notes or []:
                if not isinstance(n, dict) or not str(n.get("text") or "").strip():
                    continue
                hid = n.get("id") or f"h{len(st.hypotheses) + 1}"
                note = {
                    "id": hid,
                    "text": str(n["text"])[:500],
                    "status": n.get("status") or "supposed",
                    "sources": [str(s)[:80] for s in n.get("sources") or []][:8],
                }
                if hid in by_id:
                    by_id[hid].update(note)
                else:
                    st.hypotheses.append(note)
                    by_id[hid] = note
            return {"your_notes": st.hypotheses}

    def set_supplier_estimate(self, decision_id, supplier_id, full_cost_per_unit, cost_of_money=None, source=""):
        d, err = self._get(decision_id, "set_supplier_estimate")
        if err:
            return err
        st = d.state
        if supplier_id not in st.threads:
            return {"error": "UNKNOWN_SUPPLIER", "suppliers": list(st.threads)}
        try:
            full_cost = float(full_cost_per_unit)
            rate = None if cost_of_money is None else float(cost_of_money)
        except (TypeError, ValueError):
            return {
                "error": "INVALID_TERMS",
                "detail": "full_cost_per_unit (EUR) and cost_of_money (e.g. 0.08) are numbers",
            }
        if not full_cost > 0 or (rate is not None and not 0 <= rate <= 1):
            return {
                "error": "INVALID_TERMS",
                "detail": "full_cost_per_unit must be positive; cost_of_money between 0 and 1",
            }
        if not economics.charge_applies(st.case):
            return {"applies": False, "note": "no relationship charge in this case: the estimate changes no cost"}
        st.set_estimate(supplier_id, full_cost, rate, source)
        sheet_id, terms = st.standing(supplier_id)
        return {
            "applies": True,
            "supplier_id": supplier_id,
            "estimate": {
                "full_cost_per_unit": full_cost,
                "its_cost_of_money": st.estimate[supplier_id]["interest_rate"],
            },
            "its_standing_sheet_now_costs": st.evaluate(supplier_id, terms) if sheet_id else None,
            "note": "every cost of this thread now includes the relationship charge this estimate implies",
        }

    # -- prepare and engage -----------------------------------------------------------------------
    def prepare_decision(self, decision_id, decision, commit=False):
        d, err = self._open(decision_id, "prepare_decision")
        if err:
            return err
        result = validation.prepare(d.state, decision)
        out = {
            "ok": result["ok"],
            "errors": result["errors"],
            "diagnostics": result["diagnostics"],
            "costs": result["costs"],
            "seconds_left_in_this_turn": round(d.seconds_left(), 1),
        }
        if not result["ok"]:
            out["next"] = "fix the errors and prepare again; nothing was sent"
            return out
        draft_id = "draft-" + validation.fingerprint(result["batch"])
        d.drafts[draft_id] = result["batch"]
        out["draft_id"] = draft_id
        if commit:
            return {**out, **self._commit(d, draft_id)}
        out["next"] = "call commit_decision with this draft_id to send it, or prepare a changed decision"
        return out

    def commit_decision(self, decision_id, draft_id):
        d, err = self._open(decision_id, "commit_decision")
        if err:
            return err
        if draft_id not in d.drafts:
            return {
                "error": "UNKNOWN_DRAFT",
                "detail": "prepare the decision first; a changed decision needs a new draft",
            }
        return self._commit(d, draft_id)

    def _commit(self, d, draft_id):
        with d.state.lock:
            # the state may have moved since the draft was prepared: validate what is about to leave
            batch = d.drafts[draft_id]
            stale = [m["supplier_id"] for m in batch["emails"] if m["supplier_id"] not in d.state.ready()]
            if stale:
                return {
                    "error": "STALE_STATE",
                    "detail": f"{stale} can no longer be answered; read the state and prepare again",
                }
            d.batch, d.status = batch, "committed"
        d.done.set()
        return {
            "committed": True,
            "draft_id": draft_id,
            "next": "your decision is engaged and is being sent; end your turn now with one short line",
        }


def build_server(desk):
    """The MCP server over `desk`. Tool names and descriptions are what the model reads."""
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations

    mcp = MCPServer("tacto", instructions="A buyer's desk: read the case, compute costs, prepare and engage decisions.")
    ro = ToolAnnotations(readOnlyHint=True)

    @mcp.tool(annotations=ro)
    def get_case_state(decision_id: str) -> dict:
        """The current state of the case: mandate, cost of the alternative, and per supplier its
        standing sheet with what it costs us, its last e-mail, how far each side has moved, the
        seconds and messages left. Already included in each turn's message; call it again only
        to refresh."""
        return desk.get_case_state(decision_id)

    @mcp.tool(annotations=ro)
    def read_thread(decision_id: str, supplier_id: str) -> dict:
        """Every e-mail of one supplier thread in full, both directions, with the text of its
        attachments (quote PDF with its standard terms, cost breakdown, ...)."""
        return desk.read_thread(decision_id, supplier_id)

    @mcp.tool(annotations=ro)
    def evaluate_offers(decision_id: str, supplier_id: str, term_sheets: list[dict]) -> dict:
        """What each term sheet would cost us in EUR, by part, with this supplier's standard terms
        filling what a sheet leaves out. A term sheet is an object with the case's negotiable
        fields, e.g. {"unit_price": 50.25, "payment_days": 60}. Use it for sheets you consider
        sending and to compare the supplier's own sheets. Costs are computed, never guess them."""
        return desk.evaluate_offers(decision_id, supplier_id, term_sheets)

    @mcp.tool(annotations=ro)
    def search_structures(
        decision_id: str, supplier_id: str, target_cost_eur: float, restrict: dict | None = None, limit: int = 12
    ) -> dict:
        """You choose the total cost you aim at for us (EUR, same unit as cost_eur); this returns,
        for every allowed combination of the non-price terms, the exact unit price that makes it
        cost us that. Sorted by price, highest first: a higher price at the same cost means terms
        that cost us less - which are not always the terms the supplier likes; read what it said
        it values. `restrict` narrows the combinations, e.g. {"payment_days": [14, 30]}."""
        return desk.search_structures(decision_id, supplier_id, target_cost_eur, restrict, limit)

    @mcp.tool(annotations=ro)
    def lookup_facts(decision_id: str, ids: list[str]) -> dict:
        """The recorded values of data IDs (idx:, po:, quote:, sc:, cost:, fc:, news:, doc:, ctr:,
        offer:). The arena checks any ID you cite against these values."""
        return desk.lookup_facts(decision_id, ids)

    @mcp.tool(annotations=ro)
    def query_data(decision_id: str, sql: str, limit: int = 20) -> dict:
        """A read-only SQL query on the company's procurement data (orders, quotes, indices,
        scorecards, contracts, news). Start with: SELECT name FROM sqlite_master WHERE type='table'."""
        return desk.query_data(decision_id, sql, limit)

    @mcp.tool()
    def update_hypotheses(decision_id: str, notes: list[dict]) -> dict:
        """Your private notes on this case, kept across turns: what you believe about a supplier,
        what you asked, what remains unknown. Each note: {"id" (to revise one), "text", "status":
        supposed | supported | contradicted | withdrawn, "sources": [...]}. Revise a note when the
        supplier contradicts it."""
        return desk.update_hypotheses(decision_id, notes)

    @mcp.tool()
    def set_supplier_estimate(
        decision_id: str,
        supplier_id: str,
        full_cost_per_unit: float,
        cost_of_money: float | None = None,
        source: str = "",
    ) -> dict:
        """Cases with a relationship charge only (strategic, bottleneck): record your estimate of
        this supplier's full cost per unit (from its cost breakdown, should-cost data, what it
        says) and, if you know it, what money costs it per year (0.08 = 8 %). From then on every
        cost includes the charge for leaving it below its sustainable margin: our cost is U-shaped
        in the price, and `search_structures` never goes below the bottom of the U."""
        return desk.set_supplier_estimate(decision_id, supplier_id, full_cost_per_unit, cost_of_money, source)

    @mcp.tool()
    def prepare_decision(decision_id: str, decision: dict, commit: bool = False) -> dict:
        """Check a decision before it is sent. `decision` is either
        {"emails": [{"supplier_id", "subject", "body", "term_sheets": [{...}, up to 3], "refs": [data IDs]}],
         "note": "why"}
        - at most one e-mail per supplier, several suppliers in one decision are sent in parallel -
        or {"close": {"type": "accept", "supplier_id", "term_sheet_id"}},
        or {"close": {"type": "walk_away"}}.
        Returns errors (must be fixed), diagnostics (facts to weigh; you may keep your choice) and
        the exact cost of every sheet. With commit=true a decision without errors is engaged at
        once; otherwise call commit_decision with the returned draft_id."""
        return desk.prepare_decision(decision_id, decision, commit)

    @mcp.tool()
    def commit_decision(decision_id: str, draft_id: str) -> dict:
        """Engage a prepared decision: it is sent exactly as prepared. One decision per turn."""
        return desk.commit_decision(decision_id, draft_id)

    return mcp


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ToolServer:
    """The MCP server on a local port, in a background thread of this process."""

    def __init__(self, desk, port=None):
        import uvicorn

        self.port = port or free_port()
        self.url = f"http://127.0.0.1:{self.port}/mcp"
        app = build_server(desk).streamable_http_app(json_response=True, stateless_http=True)
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning"))
        self.thread = threading.Thread(target=self.server.run, name="tacto-mcp", daemon=True)

    def start(self, timeout=15.0):
        self.thread.start()
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.server.started:
                return self
            time.sleep(0.05)
        raise TimeoutError("the tool server did not start")

    def stop(self):
        self.server.should_exit = True
        self.thread.join(timeout=5)
