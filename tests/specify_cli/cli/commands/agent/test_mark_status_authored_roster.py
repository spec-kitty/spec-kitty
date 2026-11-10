"""``mark-status`` must resolve a subtask id the shipped template tells you to author.

Campsite fix for #2962, landed in-branch ahead of mission
``doctrine-silence-guards-01KYFV7Q``'s work packages because it blocks every one
of them.

The defect
----------
Since **#2816 IC-10 (FR-016 / SC-010)** subtask completion is *solely*
event-sourced, and the lane-transition guard sources its roster from the WP
frontmatter rather than from ``tasks.md``. :func:`authored_subtask_roster`'s own
docstring records why: *"Sourcing the roster from the frontmatter — not by
re-parsing tasks.md — is what makes checkbox removal safe."*

The shipped ``software-dev`` tasks template was updated to match, and now tells
authors:

    Subtasks are **reference rows**, not checkboxes … there is no ``- [ ]`` box
    to tick.

``mark-status`` was not updated. It resolves an id through four legacy shapes —
``- [ ] T001``, a pipe-table row, an inline ``Subtasks: T001, T002`` list, or a
bare ``WPxx`` — and a ``tasks.md`` authored exactly as the template instructs
(``T001 <description>`` beneath an ``### Included Subtasks`` heading) matches
none of them. Every id reports ``NOT_FOUND``, so no subtask can be marked, so
``move-task --to for_review`` blocks on subtasks that can never be checked, and
``--force`` becomes the only way through **on every WP of every mission using
this template**.

That is the failure this repository keeps having: two canonical surfaces that
disagree, with the disagreement invisible until someone follows the documented
one literally.

The fix
-------
A fifth resolver that consults the **authored ``subtasks:`` frontmatter roster** —
the same source the guard already treats as canonical static intent. It is added
*after* the four legacy resolvers, so every existing format keeps resolving
exactly as before; this is additive, not a replacement.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.cli.commands.agent.tasks_mark_status import (
    TaskIdResolutionOutcome,
    _resolve_authored_roster,
    owning_wp_from_authored_roster,
)

# Pure-logic resolution over a tmp_path fixture: no subprocess, no git, no network.
# Without a tier marker no CI job's ``-m`` expression selects this file, so it would
# run in no job at all — the exact silence WP10's collection-completeness gate exists
# to catch, and which it did catch here.
pytestmark = [pytest.mark.unit, pytest.mark.fast]

_TEMPLATE_SHAPED_TASKS_MD = """\
# Work Packages: Example

## Work Package WP01: Something (Priority: P0)

**Prompt**: `/tasks/WP01-something.md`

### Included Subtasks

T001 Define the thing
T002 Failing-first test for the thing
"""

_WP_PROMPT = """\
---
work_package_id: WP01
title: Something
subtasks:
- T001
- T002
---

# Work Package Prompt: WP01
"""


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    """A mission directory authored exactly as the shipped template instructs."""
    (tmp_path / "tasks.md").write_text(_TEMPLATE_SHAPED_TASKS_MD, encoding="utf-8")
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "WP01-something.md").write_text(_WP_PROMPT, encoding="utf-8")
    return tmp_path


def test_resolves_a_subtask_authored_only_in_the_frontmatter_roster(
    feature_dir: Path,
) -> None:
    """The regression: this shape is what the template produces, and it must resolve."""
    result = _resolve_authored_roster("T001", feature_dir)

    assert result is not None, (
        "T001 is in WP01's authored subtasks: roster, which is the canonical "
        "static-intent source the transition guard already uses — mark-status "
        "must find it there rather than requiring a legacy tasks.md row shape"
    )
    assert result.outcome is TaskIdResolutionOutcome.UPDATED
    assert result.id == "T001"


def test_resolution_is_case_insensitive(feature_dir: Path) -> None:
    """Matches the case-insensitivity the other resolvers already apply."""
    result = _resolve_authored_roster("t002", feature_dir)

    assert result is not None
    assert result.id == "t002"


def test_an_id_in_no_roster_is_not_resolved(feature_dir: Path) -> None:
    """Non-vacuity: the resolver must not simply accept every id it is handed.

    Without this, "resolve from the roster" degrades into "resolve anything",
    and a typo'd subtask id would be silently recorded as complete.
    """
    assert _resolve_authored_roster("T999", feature_dir) is None


def test_a_mission_with_no_tasks_directory_is_not_an_error(tmp_path: Path) -> None:
    """Absent rosters yield no match rather than raising.

    ``authored_subtask_roster`` raises ``SubtaskRosterResolutionError`` on a
    missing tasks directory — correct for the guard, where corruption must not
    fail open. Here it would turn an ordinary "not found" into a crash, so the
    resolver treats an unresolvable roster as simply no match and lets the
    caller's existing NOT_FOUND path report it.
    """
    (tmp_path / "tasks.md").write_text("# no work packages\n", encoding="utf-8")

    assert _resolve_authored_roster("T001", tmp_path) is None


def test_a_malformed_wp_prompt_does_not_crash_resolution(tmp_path: Path) -> None:
    """One unreadable WP file must not prevent resolving ids from the others."""
    (tmp_path / "tasks.md").write_text("# x\n", encoding="utf-8")
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "WP01-broken.md").write_text("---\nnot: [valid\n", encoding="utf-8")
    (tasks / "WP02-fine.md").write_text(
        "---\nwork_package_id: WP02\nsubtasks:\n- T007\n---\n", encoding="utf-8"
    )

    result = _resolve_authored_roster("T007", tmp_path)

    assert result is not None
    assert result.id == "T007"


def test_owning_wp_is_resolvable_for_the_event_emit(feature_dir: Path) -> None:
    """The defect had three sites, not one — this pins the second and third.

    Fixing only the id resolver left ``mark-status`` failing with *"Could not
    resolve owning work package for subtask event"*, and then warning *"Could not
    resolve owning WP for HistoryAdded event"*. Both re-derived ownership from
    ``tasks.md`` row shapes independently, so both inherited the same blind spot.
    They now share :func:`owning_wp_from_authored_roster` with the resolver.
    """
    assert owning_wp_from_authored_roster(feature_dir, "T001") == "WP01"
    assert owning_wp_from_authored_roster(feature_dir, "t002") == "WP01"


def test_owning_wp_is_none_for_an_unknown_id(feature_dir: Path) -> None:
    """Non-vacuity for the shared helper: it must not attribute an id it never saw."""
    assert owning_wp_from_authored_roster(feature_dir, "T999") is None


def test_owning_wp_from_authored_roster_kind_co_membership_is_pinned() -> None:
    """#3027: pin the undeclared TASKS_INDEX/WORK_PACKAGE_TASK co-membership.

    ``owning_wp_from_authored_roster`` (and ``_resolve_authored_roster``) are
    called with a ``feature_dir`` the caller (``_ms_resolve_read_dir``)
    resolves via ``planning_read_dir(handle, kind=MissionArtifactKind.
    TASKS_INDEX)`` — but the ``tasks/*.md`` files this function globs are
    ``WORK_PACKAGE_TASK``-kinded artifacts. That is a no-op TODAY only because
    ``mission_runtime.artifacts`` places both kinds in the same partition
    (``_PRIMARY_ARTIFACT_KINDS``). ``ANALYSIS_REPORT`` has already been
    re-homed COORD->PRIMARY once (see the FR-003 comment in ``artifacts.py``),
    so this assertion is the gate that fails LOUD if ``WORK_PACKAGE_TASK`` is
    ever re-homed away from ``TASKS_INDEX`` — instead of the roster read
    silently starting to point at the wrong partition.
    """
    from mission_runtime import MissionArtifactKind, is_primary_artifact_kind

    tasks_index_is_primary = is_primary_artifact_kind(MissionArtifactKind.TASKS_INDEX)
    work_package_task_is_primary = is_primary_artifact_kind(
        MissionArtifactKind.WORK_PACKAGE_TASK
    )

    assert tasks_index_is_primary == work_package_task_is_primary, (
        "TASKS_INDEX and WORK_PACKAGE_TASK have diverged into different "
        "partitions. owning_wp_from_authored_roster's feature_dir is resolved "
        "via TASKS_INDEX but reads WORK_PACKAGE_TASK-kinded tasks/*.md files "
        "(#3027) — that read must be updated to resolve its own directory "
        "via WORK_PACKAGE_TASK before this divergence ships."
    )
    # The call site assumes PRIMARY specifically (not merely "the same
    # surface"), so pin that too rather than only pinning equality.
    assert tasks_index_is_primary is True
    assert work_package_task_is_primary is True


# ---------------------------------------------------------------------------
# #7442 / FR-011: one non-id roster entry refuses ``mark-status`` for the whole
# Mission, through the real command, naming the file and the list-form remedy.
# ---------------------------------------------------------------------------

_SLUG = "7442-map-roster"
_runner = CliRunner()


@contextmanager
def _null_lock(repo_root: Path, mission_slug: str) -> Iterator[None]:
    del repo_root, mission_slug
    yield


def _invoke_mark_status(repo: Path, *args: str) -> tuple[int, str]:
    with (
        patch("specify_cli.cli.commands.agent.tasks.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent.tasks._find_mission_slug", return_value=_SLUG),
        patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out", return_value=(repo, "main")),
        patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning"),
        patch("specify_cli.cli.commands.agent.tasks.feature_status_lock", _null_lock),
    ):
        result = _runner.invoke(
            app,
            ["mark-status", *args, "--status", "done", "--mission", _SLUG, "--json", "--no-auto-commit"],
        )
    return result.exit_code, result.output


def test_map_shaped_roster_refuses_mark_status_for_the_whole_mission(tmp_path: Path) -> None:
    mission_dir = tmp_path / "kitty-specs" / _SLUG
    tasks = mission_dir / "tasks"
    tasks.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_id": "01TESTMISSION", "status_phase": "1"}), encoding="utf-8")
    (mission_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    (tasks / "WP01-good.md").write_text("---\nwork_package_id: WP01\ntitle: WP01\nsubtasks:\n  - T001\n---\n\n# WP01\n", encoding="utf-8")
    (tasks / "WP02-maps.md").write_text(
        "---\nwork_package_id: WP02\ntitle: WP02\nsubtasks:\n  - id: T002\n    title: map form\n---\n\n# WP02\n",
        encoding="utf-8",
    )

    # T001 belongs to WP01, whose roster is fine: the refusal is still Mission-wide,
    # because an unreadable roster could hide a second owner of T001.
    exit_code, output = _invoke_mark_status(tmp_path, "T001")

    assert exit_code == 1, output
    assert "Cannot determine which work package owns the subtasks" in output
    assert "WP02-maps.md" in output
    assert "as a list of task ids, e.g. - T001" in output
    assert not (mission_dir / "status.events.jsonl").exists()
