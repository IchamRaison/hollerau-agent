"""Reader regressions: local text and a fake model only, never network."""

import pytest

from hollerau.pegasus import adapt, reader


@pytest.mark.parametrize("amount", ["5.70", "5,70", "5.7", "5,7"])
@pytest.mark.parametrize("currency_first", [False, True])
def test_decimal_currency_keeps_stated_price(amount, currency_first):
    money = f"EUR {amount}" if currency_first else f"{amount} EUR"
    text = f"Our absolute price limit is {money} per unit."
    assert reader.validate({"type": "cost_floor", "value": 5.7}, text, text) == (True, 5.7)


@pytest.mark.parametrize(
    "kind,value,text",
    [
        ("lead_time_firm", 54, "Our shortest lead time is 54.5 days."),
        ("lead_time_firm", 54, "Our shortest lead time is 54,5 days."),
        ("lead_time_firm", 54, "Our price is EUR 54 and our shortest lead time is 42 days."),
        ("cost_floor", 5.7, "Our absolute price limit is EUR 15.70 per unit."),
        ("cost_floor", 5.7, "Our absolute price limit is EUR 5,700 per unit."),
        ("cost_floor", 5.7, "Our absolute price limit is EUR 5.700 per unit."),
        ("cost_floor", float("nan"), "Our price limit is EUR nan per unit."),
        ("cost_floor", True, "Our price limit is EUR 1 per unit."),
    ],
)
def test_unverified_or_wrong_field_number_is_rejected(kind, value, text):
    assert reader.validate({"type": kind, "value": value}, text, text) == (False, None)


def test_correct_amount_can_follow_same_amount_for_other_field():
    text = "The chargeback is EUR 500; our lowest price is EUR 500 per unit."
    assert reader.validate({"type": "cost_floor", "value": 500}, text, text) == (True, 500)


def test_verified_decimal_chargeback_changes_next_allowed_package(monkeypatch):
    text = "The chargeback of 500,00 EUR per complaint is too high."
    monkeypatch.setattr(reader, "ENABLED", True)
    signal = {"type": "chargeback_too_high", "line": "L1", "quote": text, "value": 500}
    monkeypatch.setattr(reader.reader_cache, "complete", lambda *args: ({"signals": [signal]}, True))
    signals = reader.read(text)
    state = {}
    reader.apply(state, signals)
    assert state["stated"]["chargeback_eur_per_complaint"] == 500
    # The standing quote can be zero; the explicitly refused amount governs the counteroffer.
    assert adapt.allowed({}, state, {"chargeback_eur_per_complaint": 250}, {"chargeback_eur_per_complaint": 0})
    assert not adapt.allowed({}, state, {"chargeback_eur_per_complaint": 500}, {})


@pytest.mark.parametrize(
    "text",
    [
        "With 14-day payment terms, we can offer a reduced price of EUR 5.30.",
        "By applying the 30-day payment terms, we are able to reduce our price to EUR 51.50.",
        "The shorter payment term allows us to offer a more competitive price.",
    ],
)
def test_explicit_payment_price_trade_is_detected(text):
    assert "wants_faster_payment" in reader.keyword_signals(text)


@pytest.mark.parametrize(
    "text",
    [
        "Our price is EUR 5.30 with payment in 14 days.",
        "The 14-day payment does not help us lower our price.",
        "We don't need faster payment.",
        "Shorter payment would not help us offer a competitive price.",
    ],
)
def test_quote_or_denied_payment_trade_is_not_a_preference(text):
    assert "wants_faster_payment" not in reader.keyword_signals(text)


def test_model_cannot_invent_quote_to_steer_terms(monkeypatch):
    text = "Please retain our current terms."
    monkeypatch.setattr(reader, "ENABLED", True)
    invented = {"type": "chargeback_too_high", "line": "L1", "quote": "Chargeback EUR 500 is too high", "value": 500}
    monkeypatch.setattr(reader.reader_cache, "complete", lambda *args: ({"signals": [invented]}, True))
    signals = reader.read(text)
    assert "chargeback_too_high" not in signals
    assert not signals.values
