"""r15: accept an `agreed` at once; one-tick nudge before accepting an open offer; answer the supplier's
scripted data questions with the forecast (fact + CSV attachment); the supplier's cost of money from
its own same-message payment pairs; the wanted index clause offered once at its own U bottom; P11
wording. All behind env switches (defaults = on)."""
import pathlib
import re

KIT = pathlib.Path("/home/heezo/tacto/negotiation-arena-kit/starter-kit")
A = KIT / "pegasus/agent.py"
E = KIT / "pegasus/economics.py"
a = A.read_text()
e = E.read_text()


def sub(text, old, new, label):
    assert text.count(old) == 1, f"{label}: {text.count(old)} occurrences"
    return text.replace(old, new, 1)


# ---- economics: implied rate ---------------------------------------------------------------
e = sub(e, "from itertools import product\n", "from itertools import combinations, product\nfrom statistics import median\n", "imports")
e = sub(e, '''def bottoms(case, ranked, std, hi):''', '''def implied_rate(sheets):
    """The supplier's own cost of money, from two sheets of the SAME message that differ only in
    payment days and price (its standing offer beside "Alternatively, with Zahlungsziel 14 days
    net: ..."): value parity p1 (1 - r d1 / 360) = p2 (1 - r d2 / 360). P02: 373.88 at 90 days
    beside 368.68 at 14 -> 6.6 %, the rate fitted on the arena's own charges. None without a pair."""
    rates = []
    for x, y in combinations(sheets, 2):
        diff = {k for k in set(x) | set(y) if x.get(k) != y.get(k)}
        if diff != {"unit_price", "payment_days"}:
            continue
        p1, d1, p2, d2 = x["unit_price"], x["payment_days"], y["unit_price"], y["payment_days"]
        den = p1 * d1 - p2 * d2
        if not den:
            continue
        r = 360 * (p1 - p2) / den
        if 0.02 <= r <= 0.20:
            rates.append(r)
    return median(rates) if rates else None


def bottoms(case, ranked, std, hi):''', "implied_rate")

# ---- agent: switches -----------------------------------------------------------------------
a = sub(a, '''MESO_TOL = float(os.environ.get("PEGASUS_MESO_TOL", "0.04"))''',
        '''MESO_TOL = float(os.environ.get("PEGASUS_MESO_TOL", "0.04"))
PUSH_AGREED = os.environ.get("PEGASUS_PUSH_AGREED", "0") == "1"  # push once more after an early "agreed" (off: it stands anyway)
NUDGE = os.environ.get("PEGASUS_NUDGE", "1") == "1"  # one tick under its open offer before taking it (P04: 4.93 = 1.000, 4.94 = 0.860)
SUBSTANTIATE = os.environ.get("PEGASUS_SUBSTANTIATE", "1") == "1"  # answer "which figures?" with the forecast fact + CSV
QUESTION_RE = re.compile(r"which figures|underlying (?:data|forecast)|forecast data|consumption data|substantiat"
                         r"|(?:what|which) volume (?:can|could|will) you commit|binding (?:volume|release)"
                         r"|share (?:the|this|your|corresponding|such) [a-z ]{0,20}(?:data|figures|forecast)"
                         r"|data (?:behind|supporting|confirming)|provide (?:the |your )?(?:actual |underlying )?(?:data|figures|forecasts?)"
                         r"|based on\\?|which data")''', "switches")

# ---- agent: agreed -> accept at once -------------------------------------------------------
a = sub(a, '''            if (st["offers"] <= 2 or behind_target) and not st.get("pushed_agreed") and moves_left(case, events) > 3:''',
        '''            if (PUSH_AGREED and (st["offers"] <= 2 or behind_target) and not st.get("pushed_agreed")
                    and moves_left(case, events) > 3):''', "agreed push gate")

# ---- agent: implied rate on every reply ----------------------------------------------------
a = sub(a, '''        rel = [eco.standing_cost(case, t, eco.with_relationship(st["std"])) for _, t in offered(events) if eco.ok(case, t, st["std"])]
        st["c_s_rel"] = min(rel) if rel else None''',
        '''        sup = st["std"].get("_floor")
        if sup and last.get("from") != "buyer":
            r = eco.implied_rate([t for _, t in offered(events)])
            if r is not None:
                # its own payment pairs outweigh our prior from the correspondence (2:1)
                prior = sup.setdefault("prior_rate", sup["interest_rate"])
                sup["interest_rate"] = round(min(max(0.67 * r + 0.33 * prior, 0.03), 0.15), 4)
                log.info("%s %s: implied cost of money %.1f %% -> model %.1f %%", case["case_id"], sid, 100 * r, 100 * sup["interest_rate"])
        rel = [eco.standing_cost(case, t, eco.with_relationship(st["std"])) for _, t in offered(events) if eco.ok(case, t, st["std"])]
        st["c_s_rel"] = min(rel) if rel else None''', "implied rate")

# ---- agent: the wanted index clause offered once at its own bottom ----------------------------
a = sub(a, '''            room = MESO_TOL * max(c_open - c_best, 0.0)
            kept = [ts for c, ts in kept if c <= c_best + room]
        msg["term_sheets"] = kept
        return msg''',
        '''            room = MESO_TOL * max(c_open - c_best, 0.0)
            kept = [ts for c, ts in kept if c <= c_best + room]
            series = (st.get("index_preference") or (None, False))[0]
            if (series and len(kept) < 3 and st.get("ranked")
                    and not any((ts["terms"].get("index_clause") or {}).get("series") == series for ts in kept)):
                # It wants this clause (its cost drivers, its reply) and gives its best prices with it
                # (P02: 355.93 with the CU clause, 367-372 without). Offer it once, on the structure
                # whose U bottom is lowest WITH the clause, at that bottom - never the 14-day variant
                # it would pick otherwise (0.59 against 0.73 at 90 days).
                with_clause = [x for x in st["ranked"] if (x[1].get("index_clause") or {}).get("series") == series]
                hi = max(10 * (st.get("ask") or st["open"].get("unit_price") or 1.0), 1.0)
                cands = eco.bottoms(case, with_clause, st["std"], hi) if with_clause else []
                if cands:
                    _, s, p = cands[0]
                    kept.append({"terms": eco.sheet(case, s, p)})
        msg["term_sheets"] = kept
        return msg''', "index clause exception")

# ---- agent: nudge before _done ----------------------------------------------------------------
a = sub(a, '''    def _done(self, case, threads, sid, st, busy):
        """This thread has gone as far as it will. In an RFQ, keep it alive with a question while
        another bidder is still moving (its offer is our best lever on them); close when no
        thread can still improve."""
        st["done"] = True''',
        '''    def _nudge(self, case, threads, sid, st, busy):
        """Before taking an offer it still calls `open`: once, its own terms one tick under its
        price. It agrees or holds - a walk was never seen before a final offer - and the tick is
        worth a lot where its last price sits near the best achievable (P04: 4.93 scores 1.000,
        its 4.94 scored 0.860). Never under the relationship floor, never after a final offer."""
        events = threads[sid]
        last = latest(events)
        if not NUDGE or st.get("nudged") or last.get("status") != "open" or sid in busy:
            return None
        if moves_left(case, events) <= 2:
            return None
        sheet_id, terms = standing(events)
        if not sheet_id or not terms or not terms.get("unit_price") or not eco.ok(case, terms, st["std"]):
            return None
        rel = eco.with_relationship(st["std"])
        c_std = eco.standing_cost(case, terms, rel)
        if any(eco.ok(case, t, st["std"]) and eco.standing_cost(case, t, rel) < c_std - 1e-6 for _, t in offered(events)[1:]):
            return None  # a better alternative of its own is on the table: mirror that instead
        structure = {f: v for f, v in eco.closing_terms(case, terms, st["std"]).items() if f in eco.fields(case)}
        p = terms["unit_price"]
        price = round(p - max(0.01, 0.002 * p), 2)
        if st["std"].get("_floor") and price < eco.price_floor(case, structure, st["std"], max(10 * p, 1.0)):
            return None  # its price is already at our floor: take it
        ours = [ts.get("unit_price") for ts in (st.get("last_sheets") or []) if {f: ts.get(f) for f in structure} == structure]
        if ours and max(ours) >= price - 1e-9:
            return None  # we already offered that
        st["nudged"] = True
        st["offers"] += 1
        target = eco.cost(case, eco.sheet(case, structure, price), st["std"])
        st["last_target"] = max(st.get("last_target") or 0.0, target)
        out = self._send(case, threads, sid, st, target, min(st["offers"], len(SCHEDULE) - 1),
                         sheets=[(price, structure)], busy=busy)
        if out and out.get("message", {}).get("term_sheets"):
            body = out["message"].get("body", "")
            out["message"]["body"] = body.replace("We value our cooperation.",
                f"We are ready to close: if you can confirm {price:.2f} EUR per unit on the attached terms, "
                "we place the order today.\\nWe value our cooperation.", 1)
            log.info("%s %s: nudge %.2f under its %.2f", case["case_id"], sid, price, p)
            return out
        return None

    def _done(self, case, threads, sid, st, busy):
        """This thread has gone as far as it will. In an RFQ, keep it alive with a question while
        another bidder is still moving (its offer is our best lever on them); close when no
        thread can still improve."""
        nudge = self._nudge(case, threads, sid, st, busy)
        if nudge:
            return nudge
        st["done"] = True''', "nudge")

# ---- agent: substantiation + attachments -------------------------------------------------------
a = sub(a, '''        lines += rules.lines(case, st, sheets)
        if not sheets:''',
        '''        lines += rules.lines(case, st, sheets)
        attachments, extra_refs = [], []
        asked_now = (latest(threads[sid]).get("body") or "").lower()
        if SUBSTANTIATE and not st.get("substantiated") and QUESTION_RE.search(asked_now):
            # Its scripted question ("which figures is that based on?", "share the consumption data")
            # gates its next step; unanswered it closes worse or walks (P18). The forecast fact and
            # its monthly lines as a CSV attachment - read by the bot, no claim slot used.
            sentence, ref, att = self._forecast_evidence(case, part)
            if sentence:
                lines.append(sentence)
                st["substantiated"] = True
                if ref:
                    extra_refs.append(ref)
                if att:
                    attachments.append(att)
        if not sheets:''', "substantiation")
a = sub(a, '''        refs = [r for c in chosen for r in c["refs"]]
        msg = {"subject": f"Re: {case['title']}" + (f" [{NONCE}]" if NONCE else ""), "body": "\\n".join(lines),
               "term_sheets": [{"terms": t} for t in sheets]}
        if refs:
            msg["refs"] = refs[:20]
        return msg''',
        '''        refs = [r for c in chosen for r in c["refs"]] + [r for r in extra_refs if r not in {x for c in chosen for x in c["refs"]}]
        msg = {"subject": f"Re: {case['title']}" + (f" [{NONCE}]" if NONCE else ""), "body": "\\n".join(lines),
               "term_sheets": [{"terms": t} for t in sheets]}
        if refs:
            msg["refs"] = refs[:20]
        if attachments:
            msg["attachments"] = attachments[:5]
        return msg

    def _forecast_evidence(self, case, part):
        """The latest forecast fact for the part and its monthly lines as a CSV attachment:
        (sentence, fact id, attachment) - (None, None, None) without a forecast."""
        if not self.pkg:
            return None, None, None
        try:
            ids = self.pkg.ids(f"fc:{part.split(':')[1]}@")
            fid = ids[-1] if ids else None
            f = self.pkg.lookup(fid) if fid else None
            if not f:
                return None, None, None
            rows = self.pkg.query("select target_month, qty from forecast_lines where fc_id = ? order by target_month", (fid,))
        except Exception as ex:
            log.warning("%s: forecast evidence failed: %s", case["case_id"], ex)
            return None, None, None
        qty = f.get("qty_next_12m") or f.get("volume_per_year")
        pct = f.get("change_pct")
        bits = []
        if qty:
            bits.append(f"{int(qty):,} pcs per year")
        if pct is not None:
            bits.append(f"{pct:+.1f}% against the previous plan")
        sentence = (f"To substantiate our volume commitment: our official forecast {fid} shows "
                    + (", ".join(bits) if bits else "the demand we commit to") + ".")
        att = None
        if rows:
            csv = "month,qty,source\\n" + "\\n".join(f"{r[0]},{r[1]},{fid}" for r in rows)
            att = {"name": f"forecast-{part.split(':')[1]}.csv", "type": "csv",
                   "content_b64": base64.b64encode(csv.encode()).decode()}
            sentence += f" The attached {att['name']} lists the monthly demand plan we release to our suppliers."
        return sentence, fid, att''', "message tail + forecast evidence")
a = sub(a, '''            lines.append(f"The enquiry fixes payment at {case['fixed_terms']['payment_days']} days net; "
                         "the attached packages therefore trade only the negotiable terms.")''',
        '''            # not "the enquiry fixes payment at 60 days": the bot quotes it back as its excuse to hold
            # (P11: "since you can't change the 60 days payment, we don't have much more room")
            lines.append("We will pay every invoice on its due date, without exception.")''', "P11 wording")
if "import base64" not in a:
    m = re.search(r"^(import |from )", a, re.M)
    a = a[:m.start()] + "import base64\n" + a[m.start():]
A.write_text(a)
E.write_text(e)
import ast  # noqa: E402

ast.parse(a)
ast.parse(e)
print("patch r15 ok")
