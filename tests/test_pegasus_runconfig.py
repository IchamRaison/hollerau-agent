"""Offline tests of the reproducible run: recorded configuration, journal, one official command."""

import json
import tomllib
from pathlib import Path

import pytest

from hollerau import cli as legacy_cli
from hollerau.pegasus import runconfig

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def package(tmp_path):
    pkg = tmp_path / "package"
    (pkg / "data").mkdir(parents=True)
    (pkg / "facts.json").write_text("{}")
    (pkg / "data" / "orders.csv").write_text("id,price\n1,5.17\n")
    return pkg


def test_no_secret_is_recorded(monkeypatch, tmp_path, package):
    monkeypatch.setenv("LLM_API_KEY", "sk-do-not-write-me")
    monkeypatch.setenv("ARENA_API_KEY", "arena-do-not-write-me")
    monkeypatch.setenv("PEGASUS_RUNS", str(tmp_path / "runs"))
    run_dir, cfg = runconfig.record("practice", ["P01"], 5, None, package)
    text = (run_dir / "config.json").read_text()
    assert "do-not-write-me" not in text
    assert cfg["env_all"]["LLM_API_KEY"] == "set" and cfg["env_all"]["ARENA_API_KEY"] == "set"
    assert cfg["data"]["files"] == 2 and cfg["code"]["commit"]
    assert "agent.ANCHOR_DROP" in cfg["settings"] and "agent.SCHEDULE" in cfg["settings"]


def test_the_fingerprint_follows_behaviour_not_the_clock(monkeypatch, package):
    first = runconfig.resolve("practice", ["P01"], 5, None, package)
    monkeypatch.setenv("HOLLERAU_VALIDATED", "someone, for something")  # who validated: not behaviour
    assert runconfig.resolve("final", [], 10, None, package)["fingerprint"] == first["fingerprint"]
    monkeypatch.setenv("PEGASUS_SOME_SWITCH", "1")  # a setting: behaviour
    switched = runconfig.resolve("practice", ["P01"], 5, None, package)["fingerprint"]
    assert switched != first["fingerprint"]
    monkeypatch.delenv("PEGASUS_SOME_SWITCH")
    (package / "data" / "orders.csv").write_text("id,price\n1,5.45\n")  # the data: behaviour
    changed = runconfig.resolve("practice", ["P01"], 5, None, package)["fingerprint"]
    assert changed not in (first["fingerprint"], switched)


def test_the_journal_appends_and_never_raises(tmp_path):
    journal = runconfig.Journal(tmp_path)
    journal.write(case="case:P01", move="accept")
    journal.write(case="case:P02", move={"type": "walk_away"})
    lines = [json.loads(x) for x in (tmp_path / "decisions.jsonl").read_text().splitlines()]
    assert [x["case"] for x in lines] == ["case:P01", "case:P02"] and all("t" in x for x in lines)
    runconfig.Journal(None).write(case="x")  # no run directory: no trace, no error
    runconfig.Journal(tmp_path / "missing" / "dir").write(case="x")  # unwritable: logged, not raised


def test_the_first_agent_never_plays_the_final_by_accident(capsys):
    with pytest.raises(SystemExit) as stop:
        legacy_cli.legacy_notice(["run", "--set", "final", "--parallel", "10"])
    assert "uv run pegasus final" in str(stop.value)
    legacy_cli.legacy_notice(["run", "--set", "final", "--agent", "ours"])  # on purpose: allowed
    legacy_cli.legacy_notice(["play", "case:S01"])
    assert "pegasus" in capsys.readouterr().err
    legacy_cli.legacy_notice(["me"])  # other kit commands are untouched


def test_pegasus_is_the_declared_command_and_the_readme_says_so():
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]
    assert scripts["pegasus"] == "hollerau.pegasus.cli:main"
    readme = (ROOT / "README.md").read_text()
    assert "uv run pegasus final --parallel 10" in readme
    assert "uv run hollerau run --set final" not in readme
