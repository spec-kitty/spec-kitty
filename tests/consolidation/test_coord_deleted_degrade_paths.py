"""Landing fold (#3012) — best-effort paths degrade on a DELETED coord branch.

PR #3012 routes mission reads through the kind-aware placement seam. COORD-partition
kinds (``STATUS_STATE``, ``LANE_STATE``) now fail loud with
:class:`~specify_cli.coordination.surface_resolver.CoordinationBranchDeleted` when the
declared ``coordination_branch`` is absent from git — a shape the old kind-blind
resolver could never raise. Two paths propagated that exception where they must not:

1. ``workflow_executor.review_compute_dependents_warning`` — explicitly best-effort
   (it only computes an advisory warning), but the seam call sat OUTSIDE the existing
   ``try/except``, so ``agent workflow review`` aborted while computing a warning.
2. ``merge.executor._run_lane_based_consolidation`` — a traceback mid-merge is the worst UX in
   the set; it must exit cleanly with the remediation the exception already carries.

``lanes.recovery.scan_recovery_state`` was ALSO folded here and has been reverted:
the WP02 ledger classifies that site ``migrate-fail-loud`` with a rationale that
pre-emptively rejects the degrade ("rather than silently reading a stale/absent
surface"), and the mission ships an acceptance test asserting it raises. The
operator-experience concern is real but is a contract change to ``implement --recover``
that needs its own mission; it is tracked as follow-up. Fail-loud coverage for that
site lives with the mission's own acceptance test in
``tests/specify_cli/merge/test_read_seam_migration_merge_lanes.py`` — deliberately NOT
duplicated here, since the tests/merge vs tests/specify_cli/merge split is exactly what
hid the conflict.

``CoordinationBranchDeleted`` subclasses ``StatusReadPathNotFound``, which subclasses
``Exception`` — so the pre-existing bare ``except Exception`` in (1) does catch it once
the raising call is moved inside the guard. (2) catches the specific type.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer

from specify_cli.frontmatter import write_frontmatter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Production-shaped identity: a real 26-char ULID, mid8 = first 8 chars
# (Mission Identity Model 083+), matching the on-disk composed dir name.
_MISSION_ID = "01KW7COORDDELETED3012LAND0"[:26]
_MID8 = _MISSION_ID[:8]
_MISSION_SLUG = "coord-deleted-degrade-mission"
_SLUG_WITH_MID8 = f"{_MISSION_SLUG}-{_MID8}"
_COORD_BRANCH = f"kitty/mission-{_SLUG_WITH_MID8}"

# The remediation string the exception carries; every degrade path must propagate it
# rather than discard it.
_REMEDIATION = "spec-kitty doctor coordination --fix"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _write_wp(tasks_dir: Path, wp_id: str, dependencies: list[str]) -> None:
    write_frontmatter(
        tasks_dir / f"{wp_id}-test.md",
        {
            "work_package_id": wp_id,
            "title": f"Test {wp_id}",
            "dependencies": dependencies,
            "subtasks": [],
            "phase": "Test Phase",
        },
        f"# Test WP: {wp_id}\n\nTest content.\n",
    )


def _build_coord_deleted_mission(repo_root: Path) -> Path:
    """Real git repo whose mission declares a coordination branch that does not exist.

    This is the narrow shape that actually reproduces the crash: the branch must be
    absent locally AND from every remote (``_coord_branch_exists`` consults
    ``refs/remotes/`` too), and no coord worktree may be registered. Normal post-merge
    state yields UNMATERIALIZED (→ PRIMARY) instead, which is why this fixture never
    creates the branch at all.
    """
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "coord-deleted-3012@example.test")
    _git(repo_root, "config", "user.name", "Coord Deleted Degrade")

    feature_dir = repo_root / "kitty-specs" / _SLUG_WITH_MID8
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _MISSION_SLUG,
                "slug": _SLUG_WITH_MID8,
                "friendly_name": _MISSION_SLUG,
                "mission_type": "software-dev",
                "coordination_branch": _COORD_BRANCH,
                "topology": "coord",
            }
        ),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")

    # WP02 depends on WP01 so the dependents warning actually reaches the STATUS read
    # (the helper returns early when a WP has no dependents).
    _write_wp(tasks_dir, "WP01", [])
    _write_wp(tasks_dir, "WP02", ["WP01"])

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "init mission declaring a nonexistent coord branch")
    return feature_dir


def test_coord_branch_deleted_is_actually_raised_by_the_seam(tmp_path: Path) -> None:
    """Anchor: the fixture really produces the DELETED shape, and the type is catchable.

    Without this, the three degrade tests below could pass vacuously on a fixture that
    silently resolves to PRIMARY. It also pins the inheritance chain the best-effort
    handler in ``review_compute_dependents_warning`` relies on: catching ``Exception``
    is sufficient there ONLY because ``CoordinationBranchDeleted`` is an ``Exception``.
    """
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    _build_coord_deleted_mission(tmp_path)

    assert issubclass(CoordinationBranchDeleted, StatusReadPathNotFound)
    assert issubclass(CoordinationBranchDeleted, Exception)

    seam = placement_seam(tmp_path, _SLUG_WITH_MID8)
    with pytest.raises(CoordinationBranchDeleted) as excinfo:
        seam.read_dir(MissionArtifactKind.STATUS_STATE)

    assert _REMEDIATION in excinfo.value.next_step


def test_dependents_warning_degrades_instead_of_aborting_review(tmp_path: Path) -> None:
    """FINDING 1: the best-effort warning helper must not abort on a warning computation.

    Red-first: with the ``read_dir(STATUS_STATE)`` call outside the existing
    ``try/except Exception``, this raises ``CoordinationBranchDeleted`` and
    ``agent workflow review`` dies. With the call moved inside the guard, lanes degrade
    to ``{}`` — every dependent is treated as ``planned`` — and the advisory warning is
    still produced.
    """
    from specify_cli.cli.commands.agent.workflow_executor import (
        review_compute_dependents_warning,
    )

    _build_coord_deleted_mission(tmp_path)

    warning = review_compute_dependents_warning(tmp_path, _SLUG_WITH_MID8, "WP01")

    assert warning, "the helper must still emit its advisory warning after degrading"
    assert any("WP02" in line for line in warning), (
        f"degraded lanes default dependents to planned, so WP02 must be flagged; got {warning}"
    )


def test_lane_based_merge_exits_cleanly_instead_of_tracebacking(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """FINDING 3: ``spec-kitty merge`` must not traceback mid-run.

    Red-first: with no typed handler the ``read_dir(STATUS_STATE)`` call at the top of
    ``_run_lane_based_consolidation`` propagates ``CoordinationBranchDeleted`` straight out of
    the command. After the fix it becomes a rendered error plus ``typer.Exit(1)``,
    matching the handler shape already used in ``agent/status.py`` and
    ``mission_finalize.py``. The failure happens before any state change.
    """
    from specify_cli.consolidation.executor import _run_lane_based_consolidation

    _build_coord_deleted_mission(tmp_path)

    with pytest.raises(typer.Exit) as excinfo:
        _run_lane_based_consolidation(
            repo_root=tmp_path,
            mission_slug=_SLUG_WITH_MID8,
            push=False,
            delete_branch=False,
            remove_worktree=False,
        )

    assert excinfo.value.exit_code == 1
    # Rich hard-wraps console output at the terminal width, so collapse whitespace
    # before matching — the assertion is about content, not line breaks.
    output = " ".join(capsys.readouterr().out.split())
    assert _COORD_BRANCH in output, f"the error must name the missing branch; got: {output!r}"
    assert "doctor coordination --fix" in output, (
        f"the error must carry the remediation guidance; got: {output!r}"
    )
    assert "Merge aborted before any state change" in output, (
        f"the operator must be told the merge is a clean no-op; got: {output!r}"
    )
