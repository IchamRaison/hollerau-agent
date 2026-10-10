"""Smoke plan for the local simulator: one single-supplier run, one RFQ with two threads, one question-only run."""


def runs(cases):
    ladder = [{"sheets": [{"price": ["x_opening", 0.88]}]}] + [
        {"sheets": [{"price": ["ours_plus_pct", 0.8]}]} for _ in range(3)
    ]
    return [
        {
            "run_id": "smoke-S01-accept",
            "block": "single",
            "case_id": "case:S01",
            "rep": 1,
            "factors": {"policy": "ladder"},
            "threads": {"*": ladder},
            "end": {"type": "accept", "supplier": "best"},
        },
        {
            "run_id": "smoke-S02-rfq",
            "block": "rfq",
            "case_id": "case:S02",
            "rep": 1,
            "factors": {"policy": "ladder"},
            "threads": {
                "*": [
                    {"sheets": [{"price": ["x_opening", 0.9], "terms": {"payment_days": 60}}]},
                    {"sheets": [{"price": ["gap", 0.3], "terms": {"payment_days": 60}}]},
                ]
            },
            "end": {"type": "accept", "supplier": "best"},
        },
        {
            "run_id": "smoke-S03-question",
            "block": "question",
            "case_id": "case:S03",
            "rep": 1,
            "factors": {"ask": "breakdown"},
            "threads": {
                "*": [
                    {"body": "Could you send us a cost breakdown?"},
                    {
                        "sheets": [
                            {"price": ["x_opening", 0.9], "terms": {"contract_months": 24}},
                            {"price": ["x_opening", 0.9], "terms": {"incoterm": "DAP"}},
                        ]
                    },
                ]
            },
            "end": {"type": "walk"},
        },
    ]
