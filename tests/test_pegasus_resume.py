"""After a runner crash, practice and sandbox sessions left open are picked up again, each one once."""

from hollerau.pegasus import play
from hollerau.pegasus.play import ResumedTable, open_sessions, play_cases


class FakeClient:
    def __init__(self, sessions, broken=False):
        self._sessions, self.broken = sessions, broken

    def sessions(self, set_="practice"):
        if self.broken:
            raise RuntimeError("arena down")
        return self._sessions

    def cases(self, set_="practice"):
        return [{"case_id": c} for c in ("case:S01", "case:S02")]


OPEN = [
    {"session_id": "sim3", "case_id": "case:S01", "status": "open", "created_at": 3},
    {"session_id": "sim1", "case_id": "case:S01", "status": "open", "created_at": 1},
    {"session_id": "sim2", "case_id": "case:S02", "status": "ended", "created_at": 2},
    {"session_id": "sim9", "case_id": "case:UNKNOWN", "status": "open", "created_at": 9},
]


def test_open_sessions_by_case_oldest_first():
    running = open_sessions(FakeClient(OPEN), "practice")
    assert [sid for sid, _ in running["case:S01"]] == ["sim1", "sim3"]
    assert "case:S02" not in running and "case:UNKNOWN" not in running  # ended, or not a case of this set


def test_open_sessions_never_blocks_a_run():
    assert open_sessions(FakeClient(OPEN, broken=True), "practice") == {}


def test_each_open_session_is_picked_up_once(monkeypatch):
    """Three runs of S01 with two open sessions: two resumed (one each), the third opens a new one."""
    seen = []

    def fake_play_case(table, cid, agent):
        seen.append((cid, getattr(table, "running", None) if isinstance(table, ResumedTable) else "new"))
        return {"score": 1.0}

    monkeypatch.setattr(play, "play_case", fake_play_case)
    play_cases(FakeClient(OPEN), ["case:S01", "case:S01", "case:S01", "case:S02"], lambda: None, parallel=4)
    assert sorted(r for c, r in seen if c == "case:S01") == ["new", "sim1", "sim3"]
    assert [r for c, r in seen if c == "case:S02"] == ["new"]
