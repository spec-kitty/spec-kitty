"""Edit-burst coalescing — the §3.2/§3.5 rule, machine-tested.

First edit publishes promptly; repeats within the window are absorbed; the
burst closes with one honest update frame (count, interval, cumulative
deltas); structural operations and non-file observations pass through
distinctly and are never coalesced away.
"""

from __future__ import annotations

import pytest

from specify_cli.live_work.coalesce import BurstCoalescer, is_structural
from specify_cli.live_work.kinds import WorkEmissionKind
from specify_cli.live_work.models import (
    ActivityBinding,
    ActorBinding,
    FileDetail,
    FileOperation,
    Observation,
    Provenance,
    RepositoryBinding,
    SessionBinding,
    ToolDetail,
    ToolState,
)

pytestmark = pytest.mark.fast


class _FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _file_observation(path: str = "src/a.py", added: int = 5, removed: int = 1, session: str = "s1") -> Observation:
    return Observation(
        kind=WorkEmissionKind.FILE_EDITED,
        session=SessionBinding(session_id=session),
        actor=ActorBinding(harness="claude"),
        repository=RepositoryBinding(slug="acme/repo"),
        activity=ActivityBinding(activity_id="act-1"),
        action=FileDetail(operation=FileOperation.EDIT, path=path, bytes_added=added, bytes_removed=removed),
        provenance=Provenance(source="harness_hook", capability="live-work.test"),
        occurred_at="2026-09-14T12:00:00+00:00",
    )


def _tool_observation() -> Observation:
    return Observation(
        kind=WorkEmissionKind.TOOL_INVOKED,
        session=SessionBinding(session_id="s1"),
        actor=ActorBinding(harness="claude"),
        repository=RepositoryBinding(slug="acme/repo"),
        activity=ActivityBinding(activity_id="act-2"),
        action=ToolDetail(tool="Bash", state=ToolState.STARTED),
        provenance=Provenance(source="harness_hook", capability="live-work.test"),
        occurred_at="2026-09-14T12:00:00+00:00",
    )


def test_first_edit_publishes_immediately() -> None:
    clock = _FakeClock()
    coalescer = BurstCoalescer(clock=clock)
    result = coalescer.offer(_file_observation())
    assert not result.absorbed
    assert len(result.frames) == 1


def test_repeated_edits_within_the_window_are_absorbed() -> None:
    clock = _FakeClock()
    coalescer = BurstCoalescer(clock=clock)
    first = coalescer.offer(_file_observation(added=5))
    assert len(first.frames) == 1
    for _ in range(3):
        clock.now += 1.0
        repeat = coalescer.offer(_file_observation(added=3, removed=2))
        assert repeat.absorbed
        assert repeat.frames == ()


def test_burst_closes_with_one_honest_update_frame() -> None:
    clock = _FakeClock()
    coalescer = BurstCoalescer(clock=clock)
    coalescer.offer(_file_observation(added=5, removed=1))
    clock.now += 1.0
    coalescer.offer(_file_observation(added=3, removed=2))
    clock.now += 1.0
    coalescer.offer(_file_observation(added=7, removed=0))
    clock.now += 10.0  # outside the 5s window: new burst opens, old closes
    result = coalescer.offer(_file_observation(added=1))
    # The update frame for the closed 3-edit burst rides with the new first edit.
    update = result.frames[0]
    detail = update.action
    assert isinstance(detail, FileDetail)
    assert detail.coalesced_edits == 3
    assert detail.bytes_added == 15
    assert detail.bytes_removed == 3
    assert detail.coalesced_window_s is not None and detail.coalesced_window_s > 0


def test_flush_all_closes_an_open_burst_at_session_end() -> None:
    clock = _FakeClock()
    coalescer = BurstCoalescer(clock=clock)
    coalescer.offer(_file_observation(added=2))
    clock.now += 1.0
    assert coalescer.offer(_file_observation(added=2)).absorbed
    frames = coalescer.flush_all()
    assert len(frames) == 1
    detail = frames[0].action
    assert isinstance(detail, FileDetail)
    assert detail.coalesced_edits == 2


def test_structural_operations_are_never_coalesced() -> None:
    assert is_structural(FileDetail(operation=FileOperation.DELETE, path="a.py", bytes_added=0, bytes_removed=0))
    assert is_structural(
        FileDetail(
            operation=FileOperation.RENAME,
            path="a.py",
            destination_path="b.py",
            bytes_added=0,
            bytes_removed=0,
        )
    )
    clock = _FakeClock()
    coalescer = BurstCoalescer(clock=clock)
    structural = Observation(
        kind=WorkEmissionKind.FILE_EDITED,
        session=SessionBinding(session_id="s1"),
        actor=ActorBinding(harness="claude"),
        repository=RepositoryBinding(slug="acme/repo"),
        activity=ActivityBinding(activity_id="a"),
        action=FileDetail(operation=FileOperation.DELETE, path="a.py", bytes_added=0, bytes_removed=0),
        provenance=Provenance(source="harness_hook", capability="live-work.test"),
        occurred_at="2026-09-14T12:00:00+00:00",
    )
    for _ in range(3):
        result = coalescer.offer(structural)
        assert not result.absorbed
        assert result.frames == (structural,)


def test_non_file_observations_pass_through() -> None:
    coalescer = BurstCoalescer()
    tool = _tool_observation()
    for _ in range(3):
        result = coalescer.offer(tool)
        assert not result.absorbed
        assert result.frames == (tool,)


def test_bursts_are_per_session_and_path() -> None:
    clock = _FakeClock()
    coalescer = BurstCoalescer(clock=clock)
    coalescer.offer(_file_observation(path="src/a.py", session="s1"))
    clock.now += 1.0
    # Same path, different session: a distinct burst, publishes immediately.
    other = coalescer.offer(_file_observation(path="src/a.py", session="s2"))
    assert not other.absorbed
    assert len(other.frames) == 1


def test_negative_window_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        BurstCoalescer(window_s=-1)
