"""intel reads the Sunday release (11/10): price list 2027 / no individual reductions, insolvency.

Needs the data package and its release (`uv run arena data`, ignored by Git): skipped without them.
"""

from pathlib import Path

import pytest

from intel import Package
from intel import dossier as intel_dossier

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "data" / "package"
RELEASE = ROOT / "data" / "release-sunday"

pytestmark = pytest.mark.skipif(
    not (PACKAGE / "facts.json").is_file() or not (RELEASE / "facts.json").is_file(),
    reason="data package or Sunday release missing: run `uv run arena data`",
)

# The rules before the release fix, to show what it changes and nothing else.
OLD_PRICE_FROZEN = (
    r"frozen all price reductions|price list applies to all customers without exception"
    r"|discounts not possible this year"
)


@pytest.fixture(scope="module")
def package():
    return Package(PACKAGE, RELEASE)


def signals(package, sid):
    return {s["type"]: {e.get("ref") or e.get("id") for e in s["evidence"]} for s in package.dossier(sid)["signals"]}


def test_price_list_2027_letters_freeze_the_price(package):
    assert "doc:20261001-70510-S5" in signals(package, "sup:70510")["price_frozen"]  # Nordmark, "Price list 2027"
    assert "doc:20261008-70650-S10" in signals(package, "sup:70650")["price_frozen"]  # Mairhofer, now Strelvo


def test_insolvency_news_is_a_supply_risk(package):
    assert signals(package, "sup:70140")["supply_risk"] == {"news:20261006-S1"}  # Kalwisz files for insolvency


def test_only_three_suppliers_change(package, monkeypatch):
    suppliers = sorted(i for i, (table, _) in package.ids.items() if table == "suppliers")
    assert len(suppliers) == 447
    after = {sid: signals(package, sid) for sid in suppliers}
    old = dict(intel_dossier.SIGNAL_RULES)
    old.pop("supply_risk")
    old["price_frozen"] = (OLD_PRICE_FROZEN, *old["price_frozen"][1:])
    monkeypatch.setattr(intel_dossier, "SIGNAL_RULES", old)
    changed = {sid for sid in suppliers if signals(package, sid) != after[sid]}
    assert changed == {"sup:70140", "sup:70510", "sup:70650"}
