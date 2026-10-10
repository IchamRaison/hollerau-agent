"""Absolute rule: no arena session is opened without the user's validation.

Every entry point that can open a session on a hosted arena calls `require_validation` first.
The local simulator (localhost) is free. Validation is given per launch, on the command line:
  HOLLERAU_VALIDATED="who said yes, for what" uv run ...
"""

import os
import sys
from urllib.parse import urlparse

LOCAL = {"127.0.0.1", "localhost", "::1"}


def is_local(url=None):
    return (urlparse(url or os.environ.get("ARENA_URL", "")).hostname or "") in LOCAL


def require_validation(what, sessions, quota=False):
    """Stop unless the user validated this launch. `sessions`: how many it opens; `quota`: counts on the 200."""
    if is_local():
        return
    ok = os.environ.get("HOLLERAU_VALIDATED", "").strip()
    kind = "PRACTICE (counts against the 200 per 24 h)" if quota else "sandbox (off quota)"
    if not ok:
        sys.exit(
            f"REFUSED: {what} would open {sessions} session(s), {kind}.\n"
            "Rule: no session without the user's validation. Ask, then relaunch with\n"
            '  HOLLERAU_VALIDATED="<who validated, for what>" ...'
        )
    print(f"[sessions] {what}: {sessions} session(s), {kind} - validated: {ok}", file=sys.stderr)
