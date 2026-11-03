"""An approved work package whose ownership cannot be read is refused as unresolved, never as missing (#7149).

``owned_files`` live in the work package's task file. When that file (or the ``tasks/``
directory) cannot be read the evidence axis has no declaration to judge against, so it must say
so (``OWNERSHIP_UNRESOLVED``) instead of reporting ``IMPLEMENTATION_MISSING``, whose recovery
(commit more work, or attest) cannot help. An authored list, an empty one included, is a
resolved declaration and keeps its old verdict (pinned at the CLI level by test_owned_acceptance_authority_6023).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from specify_cli.consolidation import wp_evidence as ev
from specify_cli.lanes.models import LanesManifest
from tests.consolidation.test_wp_evidence import (
    _LANE_BRANCH,
    _commit,
    _evaluate,
    _git,
    _independent_review,
    _lane,
    _lane_fixture,
    _manifest,
    _write_events,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TASK_FILE = "WP01-x.md"


def _lanes_case(tmp_path: Path) -> tuple[Path, Path, LanesManifest, str]:
    """A lanes Mission whose window holds an owned-looking change and an independent review."""
    repo, fd, planning = _lane_fixture(tmp_path)
    _git(repo, "checkout", "-q", _LANE_BRANCH)
    _commit(repo, "src/m1/real.py")
    _git(repo, "checkout", "-q", "main")
    _write_events(fd, _independent_review(fd, "WP01"))
    return repo, fd, _manifest([_lane("lane-a", ["WP01"])], planning), ev.OWNERSHIP_UNRESOLVED


def _single_branch_case(tmp_path: Path) -> tuple[Path, Path, LanesManifest, str]:
    repo, fd, planning = _lane_fixture(tmp_path)
    _commit(repo, "src/m1/real.py")
    _write_events(fd, _independent_review(fd, "WP01"))
    manifest = _manifest([_lane("lane-planning", ["WP01"])], planning)
    manifest.mission_branch = "main"
    return repo, fd, manifest, ev._SINGLE_BRANCH_OWNERSHIP_UNRESOLVED


def _break_task_file(fd: Path, how: str) -> None:
    tasks = fd / "tasks"
    if how == "absent_file":
        (tasks / _TASK_FILE).unlink()
    elif how == "unreadable_file":
        (tasks / _TASK_FILE).write_text("---\nowned_files: [unclosed\n---\n", encoding="utf-8")
    elif how == "unknown_key":
        (tasks / _TASK_FILE).write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\ndependencies: []\nowned_files:\n  - src/m1/**\nestimated_lines: 3\n---\n# WP01\n",
            encoding="utf-8",
        )
    else:
        shutil.rmtree(tasks)


@pytest.mark.parametrize(
    ("case", "how", "reasons"),
    [
        pytest.param(_lanes_case, "absent_file", ("no task file", "declares work_package_id WP01"), id="lanes-absent_file"),
        pytest.param(_lanes_case, "unreadable_file", (_TASK_FILE, "FrontmatterError", "Invalid YAML"), id="lanes-unreadable_file"),
        pytest.param(_lanes_case, "missing_directory", ("tasks directory does not exist",), id="lanes-missing_directory"),
        # A valid file with one unknown key fails strict validation: the line must say so, not "missing".
        pytest.param(
            _lanes_case,
            "unknown_key",
            (_TASK_FILE, "ValidationError: Extra inputs are not permitted: 'estimated_lines'"),
            id="lanes-unknown_key",
        ),
        # The breakage kind is topology-independent, so one single_branch row proves the alias.
        pytest.param(_single_branch_case, "absent_file", ("no task file", "declares work_package_id WP01"), id="single_branch-absent_file"),
    ],
)
def test_an_unreadable_ownership_declaration_is_unresolved_not_missing(
    tmp_path: Path, case: Callable[[Path], tuple[Path, Path, LanesManifest, str]], how: str, reasons: tuple[str, ...]
) -> None:
    repo, fd, manifest, code = case(tmp_path)
    single_branch = code.startswith("SINGLE_BRANCH")
    control = _evaluate(repo, fd, manifest, {"WP01": "approved"}, single_branch=single_branch)
    assert control.refusal is None, "control: with the task file readable the same fixture passes"

    _break_task_file(fd, how)
    report = _evaluate(repo, fd, manifest, {"WP01": "approved"}, single_branch=single_branch)

    assert report.codes == [code], report.refusal
    assert report.verdicts == {"WP01": ev.OWNERSHIP_UNRESOLVED}
    assert f"{code}: WP01" in str(report.refusal)
    assert str(fd / "tasks") in str(report.refusal), "the line names the location that was read"
    for reason in reasons:
        assert reason in str(report.refusal), f"the line names why ownership is unresolved: {reason!r}"
    assert "IMPLEMENTATION_MISSING" not in str(report.refusal)
    assert ev.ATTEST_NO_IMPLEMENTATION_FLAG not in str(report.refusal), "no attestation is offered for an unresolved declaration"
    assert "unknown or retired key" in str(report.refusal), "the recovery covers a task file rejected for a key"
    if single_branch:
        assert "Recovery: implement" not in str(report.refusal), "only the unresolved-specific recovery is offered"
        assert str(report.refusal).count(f"Recovery for {code}:") == 1


def test_unresolved_and_missing_work_packages_are_each_named_once_with_their_own_recovery(tmp_path: Path) -> None:
    repo, fd, manifest, _ = _lanes_case(tmp_path)
    manifest.lanes.append(_lane("lane-b", ["WP02"]))
    _git(repo, "branch", "kitty/mission-fx-lane-b", manifest.planning_commit_sha or "main")
    _write_events(fd, [*_independent_review(fd, "WP01"), *_independent_review(fd, "WP02", seq=10)])
    (fd / "tasks" / "WP02-x.md").write_text(
        "---\nwork_package_id: WP02\ntitle: WP02\ndependencies: []\nowned_files:\n  - src/m2/**\nsubtasks:\n  - T1\n---\n# WP02\n", encoding="utf-8"
    )
    (fd / "tasks" / _TASK_FILE).unlink()

    report = _evaluate(repo, fd, manifest, {"WP01": "approved", "WP02": "approved"})

    assert report.verdicts == {"WP01": ev.OWNERSHIP_UNRESOLVED, "WP02": ev.IMPLEMENTATION_MISSING}
    assert str(report.refusal).count(f"Recovery for {ev.OWNERSHIP_UNRESOLVED}:") == 1
    assert str(report.refusal).count(f"Recovery for {ev.IMPLEMENTATION_MISSING}:") == 1
