"""#6062 red-first: implement-time baseline capture must never acquire the
``for_review`` gate's machine-wide scoped-run lock (``pre-review-gate-run.lock``).

A claim (``spec-kitty agent action implement``) that captures a baseline reuses
the head runner's launch/reap machinery (``baseline._run_command_for_baseline``
-> ``pre_review_gate._run_raw_command``). Before the #6062 fix that path ALSO
entered ``_scoped_run_lock`` -- so a *claim* acquired/held the machine-wide lock
that belongs to the ``move-task --to for_review`` regression gate (#2493). That
cross-transition lock coupling is the #6062 hang (and the cross-lane
for_review-gate block its P0 rationale names).

Invariant pinned here:
- the baseline launcher (``_run_command_for_baseline``) runs LOCK-FREE;
- the ``for_review`` head run (``_run_raw_command`` with its default
  serialization) STILL serializes on the gate lock (#2493 preserved).
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

import pytest

from specify_cli.review import pre_review_gate

pytestmark = [pytest.mark.fast]


class _DummyProcess:
    """Stand-in for the launched subprocess: never runs anything real."""

    returncode = 0


@pytest.fixture
def lock_spy(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Count ``_scoped_run_lock`` entries without touching a real subprocess."""
    calls = {"n": 0}
    real = pre_review_gate._scoped_run_lock

    @contextlib.contextmanager
    def _spy(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        with real(*args, **kwargs):  # type: ignore[arg-type]
            yield

    monkeypatch.setattr(pre_review_gate, "_scoped_run_lock", _spy)
    monkeypatch.setattr(pre_review_gate, "_launch_scoped_process", lambda command, **_kw: _DummyProcess())
    monkeypatch.setattr(
        pre_review_gate,
        "_observe_process",
        lambda _process, **_kw: (pre_review_gate.HeadRunState.COMPLETED, "", ""),
    )
    return calls


def test_baseline_launcher_does_not_acquire_pre_review_gate_lock(lock_spy: dict[str, int], tmp_path: Path) -> None:
    """#6062: the implement-time baseline launcher must run lock-free."""
    from specify_cli.review.baseline import _run_command_for_baseline

    _run_command_for_baseline(["true"], cwd=tmp_path)

    assert lock_spy["n"] == 0, "baseline capture must NOT acquire the for_review gate lock (#6062)"


def test_for_review_head_run_still_acquires_pre_review_gate_lock(lock_spy: dict[str, int], tmp_path: Path) -> None:
    """#2493 regression guard: the for_review head run still serializes."""
    pre_review_gate._run_raw_command(
        ["true"],
        repo_root=tmp_path,
        timeout=5,
        progress_callback=None,
        monotonic=time.monotonic,
        wait=pre_review_gate._default_process_wait,
    )

    assert lock_spy["n"] == 1, "the for_review head run must keep serializing on the gate lock (#2493)"
