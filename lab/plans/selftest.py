"""Self-test of the engine features on the local simulator (never run this plan on the hosted arena)."""

CASE_SET = "practice"


def runs(cases):
    ladder = {"sheets": [{"price": ["ours_plus_pct", 1.0]}], "repeat": {"until": ["final_offer", "agreed"], "max": 6},
              "stop_on": ["agreed"], "fresh": True}
    first = {"sheets": [{"price": ["x_opening", 0.85]}], "stop_on": ["agreed"], "fresh": True}
    return [
        {"run_id": "t-nonce-subject", "block": "nonce", "case_id": "case:S01", "nonce": "subject",
         "threads": {"*": [first]}, "end": {"type": "accept"}},
        {"run_id": "t-nonce-body", "block": "nonce", "case_id": "case:S01", "nonce": "body",
         "threads": {"*": [first]}, "end": {"type": "accept"}},
        {"run_id": "t-repeat-then-push", "block": "endgame", "case_id": "case:S01", "nonce": "body", "cap_s": 480,
         "stop_offers_s": 330,
         "threads": {"*": [first, ladder,
                           {"when": ["final_offer"], "sheets": [{"price": ["x_standing", 0.99]}], "stop_on": [],
                            "body": "Your EUR {their_price} is noted. Could you meet EUR {our_price}?"}]},
         "end": {"type": "accept"}},
        {"run_id": "t-rfq-rival", "block": "rfq", "case_id": "case:S02", "nonce": "none",
         "threads": {"*": [{"sheets": [{"price": ["x_opening", 0.9]}]},
                           {"sheets": [{"price": ["gap", 0.3]}], "body": "Thank you.",
                            "rival_line": "Another bidder stands at EUR {rival_price} ({rival_id})."}]},
         "end": {"type": "accept", "supplier": "best"}},
        {"run_id": "t-treatment", "block": "strict", "case_id": "case:S01",
         "threads": {"*": [{"sheets": [{"price": ["x_opening", 0.9], "terms": {"payment_days": 61}}]}]},
         "end": {"type": "walk"}},
    ]
