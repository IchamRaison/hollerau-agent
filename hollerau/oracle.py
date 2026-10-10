"""Menu oracle (C4): reveal a NEW case's real term grid via 422s, consuming no round.

The published `term_options` of a hidden case may be incomplete or absent; the arena's
validator names the allowed values in its 422 ("X is not one of [...]"), and Pydantic
bounds for range-checked fields. One session, ~2 probes per field, zero rounds used
(rejections never increment the round counter - verified in the kit's sim and against
the arena in phase B).

Usage inside the final runner, right after opening a session:
    from hollerau.oracle import probe_menus
    real_menus = probe_menus(client, sid, case)   # {field: [values]} or {"min":..,"max":..}

The compiled Economics can then be rebuilt with the revealed grid via
`compile_case({**case, "term_options": {**case.get("term_options", {}), **real_menus}})`.
"""

import logging
import re
import time

log = logging.getLogger(__name__)

PROBE_OUT_OF_RANGE = {
    "payment_days": 10_000,
    "contract_months": 10_000,
    "volume_per_year": 10_000_000,
    "lead_time_days": 10_000,
    "tooling_eur": 100_000_000,
    "ppm_commitment": 100_000_000,
    "chargeback_eur_per_complaint": 100_000_000,
}
ENUM_FIELDS = ("effective_date", "incoterm", "index_clause")
PAUSE = 0.12  # 10 calls/s
NOT_ONE_OF = re.compile(r"is not one of \[([^\]]*)\]")
LE = re.compile(r"less than or equal to (\d+)")
GE = re.compile(r"greater than or equal to (\d+)")


def _probe(client, sid, supplier, case, field, value):
    """Send one sheet with field=value; return the 422 detail string (or None if accepted)."""
    from arena_kit.cost import complete_offer

    terms = complete_offer(case, {"unit_price": 100.0})
    terms[field] = value
    message = {"subject": "T", "body": "Checking a term.", "refs": [],
               "term_sheets": [{"term_sheet_id": None, "terms": terms}]}
    try:
        client.send_message(sid, supplier, message)
        return None  # accepted: consumed a round - only for fields with no options
    except Exception as e:  # noqa: BLE001
        return str(getattr(e, "detail", e))


def _parse_values(detail):
    m = NOT_ONE_OF.search(detail)
    if not m:
        return None
    raw = m.group(1)
    out = []
    for tok in raw.split(","):
        tok = tok.strip().strip("'\"")
        if not tok:
            continue
        try:
            out.append(int(tok))
        except ValueError:
            try:
                out.append(float(tok))
            except ValueError:
                out.append(tok)
    return out or None


def probe_menus(client, sid, case, supplier=None, pause=PAUSE):
    """Reveal each negotiable field's real allowed values (or numeric bounds).

    Returns {field: {"values": [...]} | {"max": x, "min": y}}; fields whose probe was
    ACCEPTED (round consumed) are marked {"accepted_probe": value} and should not be
    re-probed. Never raises.
    """
    supplier = supplier or case["suppliers"][0]
    out = {}
    for field in case["negotiable"]:
        if field == "unit_price":
            continue
        if field in PROBE_OUT_OF_RANGE:
            detail = _probe(client, sid, supplier, case, field, PROBE_OUT_OF_RANGE[field])
            time.sleep(pause)
            values = _parse_values(detail or "")
            if values:
                out[field] = {"values": values}
                continue
            le, ge = LE.search(detail or ""), GE.search(detail or "")
            if le or ge:
                out[field] = {"max": int(le.group(1)) if le else None,
                              "min": int(ge.group(1)) if ge else None}
            elif detail is None:
                out[field] = {"accepted_probe": PROBE_OUT_OF_RANGE[field]}
        elif field in ENUM_FIELDS:
            junk = {"effective_date": "1999-01-01", "incoterm": "ZZZ", "index_clause": "not-a-clause"}[field]
            detail = _probe(client, sid, supplier, case, field, junk)
            time.sleep(pause)
            values = _parse_values(detail or "")
            out[field] = {"values": values} if values else ({"accepted_probe": junk} if detail is None else {})
        else:
            detail = _probe(client, sid, supplier, case, field, 10_000_000)
            time.sleep(pause)
            values = _parse_values(detail or "")
            out[field] = {"values": values} if values else {}
    log.info("menu oracle %s: %s", case.get("case_id"), out)
    return out


def merge_into_case(case, revealed):
    """Overlay the revealed grid onto the case's term_options (revealed wins)."""
    options = dict(case.get("term_options") or {})
    for field, info in (revealed or {}).items():
        vals = info.get("values")
        if vals:
            options[field] = vals
    return {**case, "term_options": options}
