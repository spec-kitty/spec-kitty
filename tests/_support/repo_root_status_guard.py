"""Per-test guard: placement-partition status artifacts never land at the checkout root (#2815).

What this guards
----------------

``status.events.jsonl`` and ``status.json`` are STATUS_STATE placement-partition
artifacts (#2549/#2570): their only sanctioned placement is inside a mission
directory — ``kitty-specs/<mission>/`` in the primary checkout, or the
mission's coordination worktree — and they must never land at a checkout root,
on ``main``, or on a lane branch.

Twice during mission ``wp-runtime-state-eviction-01KXWN13`` (the #2684
implement-review run for WP06, then again during WP10 in lane
``.worktrees/wp-runtime-state-eviction-01KXWN13-lane-j``) a reviewer found both
files sitting untracked at the worktree/repo root after running parts of the
agent/move-task unit test suite, and had to ``rm`` them by hand mid-review
(#2815). The class of bug is the same one #2647 fixed on the production
``move-task`` read path: something resolved its target from ``Path.cwd()``
instead of an explicit feature-dir/mission root. On the test side the vector is
a hand-built command state — the ``agent tasks`` state dataclasses
(``_MoveTaskState`` and siblings in ``src/specify_cli/cli/commands/agent/``)
default their ``feature_dir``-family fields to ``field(default_factory=Path)``,
and ``Path() / "status.events.jsonl"`` is a RELATIVE path that resolves against
the process cwd, i.e. the checkout root a pytest run was invoked from. A test
fixture that forgets to set the field therefore writes the artifacts straight
into the checkout (``tests/specify_cli/cli/commands/agent/test_move_task_
durability.py`` documents one such fix-by-hand repoint).

How it works
------------

Registered from ``tests/conftest.py``'s existing ``pytest_configure`` (an
imported call, not a new definition in that module — the frozen
definition-order gate ``tests/architectural/test_home_owner_behaviour.py::
test_conftest_definition_order_is_unchanged_with_the_owner_removed`` forbids
new top-level definitions there; ``tests/_support/fixture_pollution.py``
documents the same workaround). Once registered, two new-style hook wrappers
(``wrapper=True``) bracket every test with the maximal per-test window:

* ``pytest_runtest_setup`` — snapshot taken BEFORE any fixture of the test
  is instantiated;
* ``pytest_runtest_teardown`` — comparison run AFTER every fixture teardown.

Each test is compared against ITS OWN start snapshot, so a polluting test
errors exactly once (attributed, at its own teardown) and no cascade follows:
a later test that leaves the leaked file untouched sees before == after and
passes. Creation, in-place modification, and replace-by-rename are all caught
via the ``(st_ino, st_mtime_ns, st_st_size)`` fingerprint. Pre-existing
operator dirt from an earlier buggy run is NOT flagged unless a test touches
it — the suite's job is to catch its own writes, not to fail on ambient state.

Boundary (documented, deliberate): writes that happen outside any test's
window — at collection/import time, or from an orphaned subprocess after the
session ends — are not caught by this guard. The observed #2815 incidents were
plain in-test writes; a collection-time writer would be a different bug with
different evidence.

Two further boundary cases, both deliberate (#4036):

* **Between-tests gap.** A write that lands strictly after test A's
  ``pytest_runtest_teardown`` comparison has already run and strictly before
  test B's ``pytest_runtest_setup`` snapshot is taken — the brief gap between
  two consecutive items' hook pairs — falls inside neither test's window and
  is attributed to neither. In practice this gap is pytest's own
  inter-item bookkeeping (microseconds), not a window a test's own code can
  reach into, so it has never been the observed vector for a real leak; it is
  documented here as a known, accepted blind spot rather than a claim of
  completeness. (Contrast: a write made DURING test A's window and left
  on-disk — the ordinary case, proven by
  ``tests/test_repo_root_status_guard.py::
  test_leak_attribution_does_not_straddle_into_the_next_test`` — is
  correctly attributed to A alone and never cascades onto a subsequent test
  B that leaves it untouched, because B's own setup snapshot captures A's
  leak as pre-existing state and B's teardown compare only flags a change
  relative to THAT snapshot.)
* **Concurrent xdist worker.** ``GUARD_ROOT`` names the same on-disk checkout
  root for every worker process in a ``-n auto`` run, but each worker's hooks
  only compare fingerprints against snapshots taken IN THAT WORKER'S OWN
  process (the ``_BEFORE_SNAPSHOT`` stash is per-item, per-process). A write
  made by a test running in worker A is attributed to whichever test is
  current in worker A at its next teardown check; it is invisible to worker
  B's own before/after comparisons (a different process, a different
  in-memory stash) — so it is never misattributed to a worker-B test, but it
  is also never cross-checked against what worker B observes. Cross-worker
  attribution is out of scope by construction, not merely untested.

The guarded root is derived from THIS file's location (``tests/_support/`` →
two levels up), never from ``Path.cwd()`` — so it is the root of whichever
checkout this ``tests/`` tree lives in (repo root, or a lane worktree's root
when the suite runs from a worktree copy), which is exactly the surface the
reviewers had to clean by hand.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

#: The guarded placement-partition filenames. STATUS_STATE artifacts whose
#: only sanctioned placement is a mission directory — never a checkout root.
#: Kept as an extensible tuple: a future root-level placement-partition
#: artifact joins here (and only here).
ROOT_LEVEL_STATUS_ARTIFACTS: tuple[str, ...] = ("status.events.jsonl", "status.json")

#: This checkout's root, derived from this module's own location so the guard
#: is cwd-invariant (a worktree copy of ``tests/`` guards that worktree's
#: root). Deliberately NOT ``Path.cwd()`` — the very resolution this module
#: exists to detect.
GUARD_ROOT = Path(__file__).resolve().parents[2]

#: Per-item stash slot for the setup-time snapshot.
_BEFORE_SNAPSHOT = pytest.StashKey[Any]()

#: Marker string quoted in every failure so the guard is greppable from a
#: raw traceback without importing this module.
_INCIDENT_REF = "#2815"


class RepoRootStatusArtifactLeak(RuntimeError):
    """A test wrote a placement-partition status artifact at the checkout root."""


def snapshot_root_status_artifacts(
    root: Path,
) -> dict[str, tuple[int, int, int] | None]:
    """Map each guarded artifact name to its fingerprint, or ``None`` when absent.

    The fingerprint is ``(st_ino, st_mtime_ns, st_size)``: inode catches
    create/replace-by-rename even when size is identical, mtime_ns catches
    in-place rewrites, size catches truncation. ``None`` means "not present
    at snapshot time" — any transition to or from ``None``, or to a different
    fingerprint, is a violation.
    """
    snapshot: dict[str, tuple[int, int, int] | None] = {}
    for name in ROOT_LEVEL_STATUS_ARTIFACTS:
        try:
            stat = os.stat(root / name)
        except OSError:
            # FileNotFoundError (absent) plus any racing unlink/rename —
            # both read as "not present at snapshot time".
            snapshot[name] = None
        else:
            snapshot[name] = (stat.st_ino, stat.st_mtime_ns, stat.st_size)
    return snapshot


def root_status_artifact_violations(
    root: Path,
    before: dict[str, tuple[int, int, int] | None],
) -> list[str]:
    """Which guarded artifacts were created or modified at ``root`` since ``before``.

    Returns a sorted list of names — empty means the window was clean. A name
    that was already present and untouched is NOT a violation: pre-existing
    operator dirt must not fail unrelated tests.
    """
    after = snapshot_root_status_artifacts(root)
    return sorted(name for name in ROOT_LEVEL_STATUS_ARTIFACTS if after[name] != before.get(name))


def _leak_message(violations: list[str]) -> str:
    names = ", ".join(repr(name) for name in violations)
    return (
        f"{_INCIDENT_REF}: this test wrote placement-partition status "
        f"artifact(s) {names} at the checkout root ({GUARD_ROOT}). "
        "status.events.jsonl / status.json are per-mission STATUS_STATE "
        "artifacts (#2549/#2570): their only sanctioned placement is a "
        "mission directory (kitty-specs/<mission>/ or the coordination "
        "worktree), never a checkout root. A root-level write here means the "
        "code under test — or a hand-built fixture state — resolved its "
        "write target from Path.cwd()/a Path() dataclass default instead of "
        "an explicit feature_dir/mission root (the same Path.cwd() class as "
        "#2647). Isolate the write to tmp_path with an explicit feature_dir; "
        "delete the leaked file(s) from the checkout root before re-running."
    )


def register_repo_root_status_guard(config: pytest.Config) -> None:
    """Register this module's run-test hooks on ``config``'s plugin manager.

    Called from ``tests/conftest.py``'s existing ``pytest_configure`` body —
    an imported call rather than a definition in that module, for the frozen
    definition-order gate reason documented in the module docstring.
    Idempotent: a second call against the same manager is a no-op.
    """
    plugin = sys.modules[__name__]
    if not config.pluginmanager.is_registered(plugin):
        config.pluginmanager.register(plugin)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> object:
    """Snapshot the guarded artifacts before any of the test's fixtures run."""
    item.stash[_BEFORE_SNAPSHOT] = snapshot_root_status_artifacts(GUARD_ROOT)
    return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> object:
    """After all fixture teardowns, fail the test if it leaked at the root.

    Raising in the teardown phase reports as an ERROR attributed to this
    test's nodeid — the polluter is named, not the whole session. Tests whose
    setup never ran (collection-time error) carry no snapshot and are skipped.
    """
    result = yield
    before = item.stash.get(_BEFORE_SNAPSHOT, None)
    if before is None:
        return result
    violations = root_status_artifact_violations(GUARD_ROOT, before)
    if violations:
        raise RepoRootStatusArtifactLeak(_leak_message(violations))
    return result
