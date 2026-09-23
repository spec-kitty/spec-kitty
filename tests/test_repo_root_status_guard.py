"""Tests for the #2815 repo-root status-artifact guard itself.

Two layers, both mandatory:

* **Detector units** — the pure snapshot/violation functions, including the
  non-vacuity limb (a sanctioned in-mission status write never trips the
  guard: the guard is a PLACEMENT guard, not an anti-status-write guard) and
  the ambient-dirt limb (pre-existing operator dirt from an earlier buggy run
  must not fail unrelated tests).
* **End-to-end firing proof** — a real nested ``pytest`` run whose polluter
  test reproduces the exact #2815 incident shape (both ``status.events.jsonl``
  and ``status.json`` written at a checkout root) must ERROR at that test's
  teardown. The nested run loads a byte-identical runtime copy of the guard
  module in a scratch checkout so the proof never writes at THIS repo's root
  (which would trip sibling guards under ``-n auto`` — the very leak class
  this guard detects). A paired control run without the plugin must pass the
  same polluter, proving the failure is the guard, not the polluter.

Incident evidence: mission ``wp-runtime-state-eviction-01KXWN13`` (the #2684
implement-review run) — reviewers twice found both files untracked at the
worktree/repo root after running parts of the agent/move-task unit test suite
(#2815); cross-references #2647 (the same ``Path.cwd()`` resolution class on
the production read path) and #2549/#2570 (the placement partition these
artifacts belong to).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests._support.repo_root_status_guard import (
    GUARD_ROOT,
    ROOT_LEVEL_STATUS_ARTIFACTS,
    RepoRootStatusArtifactLeak,
    root_status_artifact_violations,
    snapshot_root_status_artifacts,
)
from tests.utils import REPO_ROOT

#: The polluter test executed inside the nested pytest runs. It reproduces
#: the #2815 incident shape exactly: BOTH guarded artifacts written at the
#: checkout root during a test body. It writes them at the guard module's own
#: ``GUARD_ROOT`` (the scratch checkout root), never at this repo's root.
_POLLUTER_TEST = '''\
from tests._support.repo_root_status_guard import GUARD_ROOT


def test_polluter_writes_status_artifacts_at_the_root() -> None:
    """The #2815 incident shape, replayed against the scratch checkout root."""
    (GUARD_ROOT / "status.events.jsonl").write_text("{}\\n", encoding="utf-8")
    (GUARD_ROOT / "status.json").write_text("{}\\n", encoding="utf-8")
'''


def test_guard_root_is_this_checkout_root() -> None:
    """The guarded surface is this checkout's root, derived cwd-invariantly.

    ``GUARD_ROOT`` must come from the module's own location (a worktree copy
    of ``tests/`` guards that worktree's root), never from ``Path.cwd()`` —
    the exact resolution class the guard exists to detect (#2647/#2815).
    """
    assert GUARD_ROOT == REPO_ROOT
    assert Path(__file__).resolve().parents[1] == GUARD_ROOT


def test_created_artifacts_are_flagged(tmp_path: Path) -> None:
    """The #2815 incident shape: both files appear at the root during a window."""
    before = snapshot_root_status_artifacts(tmp_path)
    assert before == dict.fromkeys(ROOT_LEVEL_STATUS_ARTIFACTS)

    for name in ROOT_LEVEL_STATUS_ARTIFACTS:
        (tmp_path / name).write_text("{}\n", encoding="utf-8")

    assert root_status_artifact_violations(tmp_path, before) == [
        "status.events.jsonl",
        "status.json",
    ]


def test_untouched_preexisting_artifacts_are_not_flagged(tmp_path: Path) -> None:
    """Ambient operator dirt from an earlier buggy run fails no unrelated test.

    Without this limb a developer with leftover root-level ``status.*`` from
    a pre-guard run would see every test in the suite error.
    """
    for name in ROOT_LEVEL_STATUS_ARTIFACTS:
        (tmp_path / name).write_text("stale operator dirt\n", encoding="utf-8")

    before = snapshot_root_status_artifacts(tmp_path)

    assert root_status_artifact_violations(tmp_path, before) == []


def test_modified_preexisting_artifact_is_flagged(tmp_path: Path) -> None:
    """A test that rewrites pre-existing root-level dirt IS its own violation."""
    artifact = tmp_path / "status.json"
    artifact.write_text('{"a": 1}\n', encoding="utf-8")
    before = snapshot_root_status_artifacts(tmp_path)

    artifact.write_text('{"a": 1, "b": 2}\n', encoding="utf-8")

    assert root_status_artifact_violations(tmp_path, before) == ["status.json"]


def test_mission_dir_status_writes_are_not_flagged(tmp_path: Path) -> None:
    """Non-vacuity: the sanctioned placement never trips the guard.

    ``status.events.jsonl`` / ``status.json`` written INSIDE a mission
    directory is the correct, everyday status-emit outcome. A guard that
    flagged any status write would be an anti-status guard, not a placement
    guard — this limb kills that mutant.
    """
    mission_dir = tmp_path / "kitty-specs" / "demo-mission-01KXWN13"
    mission_dir.mkdir(parents=True)
    before = snapshot_root_status_artifacts(tmp_path)

    (mission_dir / "status.events.jsonl").write_text("{}\n", encoding="utf-8")
    (mission_dir / "status.json").write_text("{}\n", encoding="utf-8")

    assert root_status_artifact_violations(tmp_path, before) == []


def test_guard_is_registered_in_this_session(request: pytest.FixtureRequest) -> None:
    """Wiring: the plugin (and therefore both run-test hooks) is live here.

    This session is itself the existence proof that registration happens via
    ``tests/conftest.py``'s ``pytest_configure`` — if that call were dropped,
    this assertion goes red on the next run of this file.
    """
    from tests._support import repo_root_status_guard as plugin_module

    registered = request.config.pluginmanager.get_plugins()
    assert plugin_module in registered


@pytest.mark.integration
def test_nested_pytest_run_errors_when_a_test_leaks_at_the_root(tmp_path: Path) -> None:
    """End-to-end firing proof: the guard makes a polluter test ERROR, loudly.

    A real nested ``pytest`` run loads a runtime copy of the guard module in
    a scratch checkout (``tmp_path``), runs the #2815 incident polluter, and
    must exit non-zero with the ``RepoRootStatusArtifactLeak`` teardown error
    naming both artifacts. The copy is made from the live module at run time,
    so this always exercises the current guard, never a stale snapshot of it.

    The self-check that THIS test itself never leaked at the REAL checkout
    root (as opposed to the scratch sandbox above) is window-scoped
    (``root_status_artifact_violations`` against a ``before`` snapshot taken
    right before the nested run) rather than an absolute ``not exists()``
    claim (#4036): an absolute claim cannot tell ambient, pre-existing
    root-level dirt apart from a genuine leak caused by THIS test's own
    nested-pytest invocation, and would flag both identically -- flaky under
    ``-n auto`` and any checkout carrying leftover root-level ``status.*``
    debris. The window-scoped check only flags a fingerprint change since
    ``before``, exactly the "this test didn't leak" claim the self-check is
    meant to make.
    """
    before = snapshot_root_status_artifacts(REPO_ROOT)
    sandbox = _scratch_checkout(tmp_path)
    result = _run_nested_pytest(sandbox, with_guard=True)

    assert result.returncode != 0, f"guard did not fire: polluter passed a run that loads the guard.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    combined = result.stdout + result.stderr
    assert RepoRootStatusArtifactLeak.__name__ in combined
    assert "#2815" in combined
    for name in ROOT_LEVEL_STATUS_ARTIFACTS:
        assert name in combined
    # The leaked artifacts landed in the scratch checkout, never here.
    assert (sandbox / "status.events.jsonl").exists()
    assert (sandbox / "status.json").exists()
    assert root_status_artifact_violations(REPO_ROOT, before) == [], "this test's own nested-pytest invocation leaked at the REAL checkout root (#4036)"


@pytest.mark.integration
def test_control_nested_pytest_without_the_guard_passes_the_polluter(
    tmp_path: Path,
) -> None:
    """Paired control: the same polluter PASSES when the guard is not loaded.

    Proves the firing test's red comes from the guard, not from the polluter
    erroring on its own (import failure, bad path, etc.) — the two-run pair
    is the non-vacuity contract for the hook wiring, mirroring the repo's
    two-sided RED/GREEN proof idiom.
    """
    sandbox = _scratch_checkout(tmp_path)
    result = _run_nested_pytest(sandbox, with_guard=False)

    assert result.returncode == 0, f"polluter failed without the guard — the firing test proves nothing:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    # It wrote at the scratch root unguarded — exactly the pre-#2815 world.
    assert (sandbox / "status.events.jsonl").exists()
    assert (sandbox / "status.json").exists()


#: A two-test straddle scenario for the #4036 attribution proof: a polluter
#: (test A) writes both guarded artifacts at the scratch root, then a second,
#: innocent test (test B) runs immediately after in the SAME nested session
#: and touches nothing. A's leak persists on disk across the gap into B's
#: nominal window -- proving attribution stays scoped to A alone (no cascade
#: onto B) is the point of this fixture.
_STRADDLE_POLLUTER_THEN_INNOCENT_TESTS = '''\
from tests._support.repo_root_status_guard import GUARD_ROOT


def test_a_polluter_writes_status_artifacts_at_the_root() -> None:
    """The #2815 incident shape, replayed against the scratch checkout root."""
    (GUARD_ROOT / "status.events.jsonl").write_text("{}\\n", encoding="utf-8")
    (GUARD_ROOT / "status.json").write_text("{}\\n", encoding="utf-8")


def test_b_innocent_leaves_the_leaked_files_untouched() -> None:
    """Runs immediately after the polluter, in the same nested session.

    A's leak still sits on disk (its own teardown already fired and errored
    on it) -- this test does not touch it, so it must pass cleanly: its OWN
    window (setup snapshot -> teardown compare) sees before == after.
    """
    assert (GUARD_ROOT / "status.events.jsonl").exists()  # sanity: A's leak persists
'''


@dataclass(frozen=True)
class _StraddleOutcome:
    """Per-test attribution outcome parsed from a two-test nested pytest run."""

    polluter_errored: bool
    innocent_passed: bool


#: Matches pytest's ``-rA`` per-test summary lines, e.g.
#: ``PASSED test_polluter.py::test_b_innocent_leaves_the_leaked_files_untouched``
#: or ``ERROR test_polluter.py::test_a_polluter_writes_status_artifacts_at_the_root``.
_RESULT_LINE_RE = re.compile(r"^(?P<outcome>PASSED|FAILED|ERROR)\s+(?P<nodeid>\S+)\s*$", re.MULTILINE)


def _classify_straddle_result(result: subprocess.CompletedProcess[str]) -> _StraddleOutcome:
    """Attribute the two-test straddle run's outcome to each test independently.

    Parses the ``-rA`` per-test summary lines (never aggregate pass/fail
    counts, which cannot distinguish "A errored, B passed" from "A passed, B
    errored") so the straddle proof checks the SPECIFIC test each assertion
    names, not just that something in the run went one way or the other.
    """
    combined = result.stdout + result.stderr
    outcomes = {match.group("nodeid").rsplit("::", 1)[-1]: match.group("outcome") for match in _RESULT_LINE_RE.finditer(combined)}
    return _StraddleOutcome(
        polluter_errored=outcomes.get("test_a_polluter_writes_status_artifacts_at_the_root") == "ERROR",
        innocent_passed=outcomes.get("test_b_innocent_leaves_the_leaked_files_untouched") == "PASSED",
    )


@pytest.mark.integration
def test_leak_attribution_does_not_straddle_into_the_next_test(tmp_path: Path) -> None:
    """RED-first #4036 demo: a leak's write straddles test A's window into
    what would nominally be test B's -- proving it is attributed to A alone,
    and B (which touches nothing) passes cleanly. This is a REAL, mechanistic
    proof via a nested ``pytest`` run -- not merely a restatement of the
    module docstring's "errors exactly once... no cascade follows" prose
    claim.
    """
    sandbox = _scratch_checkout(tmp_path)
    (sandbox / "test_polluter.py").write_text(_STRADDLE_POLLUTER_THEN_INNOCENT_TESTS, encoding="utf-8")
    result = _run_nested_pytest(sandbox, with_guard=True)

    outcome = _classify_straddle_result(result)
    assert outcome.polluter_errored, f"test A must ERROR on its own leak.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert outcome.innocent_passed, f"test B must pass cleanly -- attribution must not cascade.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def _scratch_checkout(tmp_path: Path) -> Path:
    """A minimal scratch checkout whose ``tests/_support`` holds the live guard.

    The nested run's ``-p tests._support.repo_root_status_guard`` resolves
    against ``PYTHONPATH=<scratch>`` (``tests`` and ``tests._support`` exist
    there as packages), so the guard module's own ``GUARD_ROOT`` — derived
    from its file location — is the SCRATCH root, and the polluter's writes
    land there. Nothing in this proof ever writes at this repo's root, which
    under ``-n auto`` would trip sibling tests' guards mid-window.
    """
    source = REPO_ROOT / "tests" / "_support" / "repo_root_status_guard.py"
    support = tmp_path / "tests" / "_support"
    support.mkdir(parents=True)
    (support / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "__init__.py").write_text("", encoding="utf-8")
    # Runtime copy of the live module — never a committed duplicate.
    (support / "repo_root_status_guard.py").write_bytes(source.read_bytes())
    (tmp_path / "test_polluter.py").write_text(_POLLUTER_TEST, encoding="utf-8")
    return tmp_path


def _run_nested_pytest(
    sandbox: Path,
    *,
    with_guard: bool,
) -> subprocess.CompletedProcess[str]:
    """Run the polluter test in a nested pytest, optionally loading the guard.

    ``-rA`` prints an explicit per-test outcome summary line (``PASSED
    <nodeid>`` / ``ERROR <nodeid>`` / ...) in addition to the ``-q`` dot
    output, so callers can attribute a specific test's outcome from the
    combined stdout/stderr without depending on aggregate count phrasing.
    """
    argv = [sys.executable, "-m", "pytest", "test_polluter.py", "-q", "--no-header", "-rA", "-p", "no:cacheprovider"]
    if with_guard:
        argv.append("-p")
        argv.append("tests._support.repo_root_status_guard")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(sandbox)
    return subprocess.run(
        argv,
        cwd=str(sandbox),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
