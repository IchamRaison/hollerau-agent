"""The run's resolved configuration, written before any session opens.

A score is only worth something if we can say which code, data, settings, memory and prompts
produced it. `record` writes `data/runs/<UTC>-<fingerprint>/config.json` and returns the run
directory; `Journal` appends one JSON line per decision next to it (`decisions.jsonl`).

No secret enters either file: a key is recorded as "set" or missing, never its value. The
fingerprint covers what changes the agent's behaviour (code, settings, data, initial memory,
reader cache, playbook, prompts) - not the clock, the command line or who validated the launch.
"""

import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path

log = logging.getLogger("pegasus")

ROOT = Path(__file__).resolve().parents[2]
SECRET_WORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD")
ENV_PREFIXES = ("PEGASUS_", "LLM_", "ARENA_", "HOLLERAU_")
# recorded for the trace, but they do not change how the agent negotiates
NOT_BEHAVIOUR = {"HOLLERAU_VALIDATED", "ARENA_URL", "ARENA_API_KEY", "PEGASUS_RUNS", "PEGASUS_NONCE"}
SIMPLE = (bool, int, float, str, list, tuple)


def runs_dir():
    return Path(os.environ.get("PEGASUS_RUNS", "data/runs"))


def secret(name):
    return any(w in name.upper() for w in SECRET_WORDS)


def sha(path):
    """sha256 of a file, None when it does not exist."""
    p = Path(path)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_sha(root):
    """One hash for a directory: every file's relative path and content, in a fixed order."""
    root = Path(root)
    if not root.is_dir():
        return None, 0
    h, n = hashlib.sha256(), 0
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        h.update(str(p.relative_to(root)).encode() + b"\0" + (sha(p) or "").encode() + b"\n")
        n += 1
    return h.hexdigest(), n


def code():
    """The commit that runs, and whether tracked files differ from it."""
    def git(*args):
        try:
            r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=10)
            return r.stdout.strip() if r.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            return None

    status = git("status", "--porcelain", "--untracked-files=no")
    return {"commit": git("rev-parse", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": None if status is None else bool(status)}


def environment():
    """Our environment variables as set for this run; secrets as "set"."""
    return {k: ("set" if secret(k) else v) for k, v in sorted(os.environ.items())
            if k.startswith(ENV_PREFIXES) and v != ""}


def settings():
    """Every tunable as the modules resolved it (defaults included), not only what the
    environment overrides: two runs with the same values here take the same decisions."""
    from . import actions, agent, economics, memory, play, prose, reader, strategist

    out = {}
    for mod in (actions, agent, economics, memory, play, prose, reader, strategist):
        name = mod.__name__.rsplit(".", 1)[1]
        for k, v in sorted(vars(mod).items()):
            if (k.isupper() and not k.startswith("_") and isinstance(v, SIMPLE) and not secret(k)
                    and len(repr(v)) <= 200):
                out[f"{name}.{k}"] = list(v) if isinstance(v, tuple) else v
    return out


def agent_policy():
    """How the next move is decided, and who may choose it."""
    from . import agent, strategist

    return {"decides": agent.POLICY, "strategist": strategist.ENABLED, "strategist_prompt": strategist.VERSION}


def resolve(kind, cases=(), parallel=None, playbook=None, data_dir=None):
    """The configuration of a run and its fingerprint."""
    from . import memory, reader, reader_cache

    data_dir = Path(data_dir or os.environ.get("ARENA_DATA", "data/package"))
    data_hash, files = tree_sha(data_dir)
    mem = Path(memory.FILE)
    archive = Path(os.environ.get("PEGASUS_READER_ARCHIVE", "data/reader_archive.json"))
    try:
        suppliers = len(json.loads(mem.read_text(encoding="utf-8"))) if mem.is_file() else 0
    except (OSError, ValueError):
        suppliers = None
    env = environment()
    behaviour = {
        "code": code(),
        "settings": settings(),
        "env": {k: v for k, v in env.items() if k not in NOT_BEHAVIOUR},
        "data": {"path": str(data_dir), "sha256": data_hash, "files": files,
                 "release": (data_dir / "release-sunday").is_dir()},
        "memory": {"path": str(mem), "sha256": sha(mem), "suppliers": suppliers},
        "reader": {"enabled": reader.ENABLED, "prompt": reader.VERSION, "archive": str(archive),
                   "archive_sha256": sha(archive), "cache": getattr(reader_cache, "MODE", None)},
        "playbook": {"path": playbook, "sha256": sha(playbook) if playbook else None},
        "policy": agent_policy(),
        "python": platform.python_version(),
    }
    canon = json.dumps(behaviour, sort_keys=True, default=str)
    return {
        "fingerprint": hashlib.sha256(canon.encode()).hexdigest()[:12],
        "run": {"set": kind, "cases": list(cases), "parallel": parallel, "argv": sys.argv[1:],
                "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "validated": os.environ.get("HOLLERAU_VALIDATED") or None,
                "arena": os.environ.get("ARENA_URL") or None, "platform": platform.platform()},
        **behaviour,
        "env_all": env,
    }


def record(kind, cases=(), parallel=None, playbook=None, data_dir=None):
    """Write the configuration before the run starts. Returns (run directory, configuration);
    (None, configuration) if the directory cannot be written - a log is never a reason not to play."""
    cfg = resolve(kind, cases, parallel, playbook, data_dir)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = runs_dir() / f"{stamp}-{kind}-{cfg['fingerprint']}"
    try:
        out.mkdir(parents=True, exist_ok=True)
        (out / "config.json").write_text(json.dumps(cfg, indent=1, sort_keys=True, default=str), encoding="utf-8")
    except OSError as e:
        log.warning("run configuration not written (%s)", e)
        return None, cfg
    return out, cfg


def describe(cfg):
    """One line for the terminal: what is about to play."""
    c = cfg["code"]
    commit = (c.get("commit") or "no-git")[:7] + ("+dirty" if c.get("dirty") else "")
    return (f"run {cfg['fingerprint']}: code {commit}, policy {cfg['policy']['decides']}"
            f"{'+strategist' if cfg['policy']['strategist'] else ''}, data {str(cfg['data']['sha256'])[:8]} "
            f"({cfg['data']['files']} files), memory {cfg['memory']['suppliers']} supplier(s), "
            f"reader {'LLM' if cfg['reader']['enabled'] else 'keywords'}")


class Journal:
    """One JSON line per decision, safe across the parallel cases. Writing never raises."""

    def __init__(self, run_dir, name="decisions.jsonl"):
        self.path = Path(run_dir) / name if run_dir else None
        self.lock = threading.Lock()

    def write(self, **entry):
        if not self.path:
            return
        line = json.dumps({"t": round(time.time(), 3), **entry}, sort_keys=True, default=str)
        try:
            with self.lock, self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            log.warning("journal not written (%s)", e)


def save(run_dir, name, payload):
    """A JSON file next to the configuration (e.g. results.json); never raises."""
    if not run_dir:
        return
    try:
        (Path(run_dir) / name).write_text(json.dumps(payload, indent=1, sort_keys=True, default=str),
                                          encoding="utf-8")
    except OSError as e:
        log.warning("%s not written (%s)", name, e)
