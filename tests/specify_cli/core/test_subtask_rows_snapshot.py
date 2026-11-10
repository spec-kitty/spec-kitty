"""Owned WP13 test (#2816 IC-10 / T054, FR-016 / SC-010 / C-010).

The lane-transition guard's subtask-completion authority is the reduced
event-log ``subtasks`` slot — NOT the ``- [ ] T###`` markdown checkbox, which
the cutover retires as an incoherent proxy (research D-13: a raw checkbox edit
without ``mark-status`` showed frozen progress). This file is the NON-VACUOUS
proof that the rerouted guard reads the snapshot, and that the migration seed
reader is left intact.

Discipline (reviewer guidance):

* Every guard case drives **real** snapshot state via ``emit_inner_state_changed``
  (the exact writer ``mark-status`` calls) — the guard's read source is never
  mocked. A mocked snapshot would make "off the snapshot" vacuous.
* Every guard fixture's ``tasks.md`` carries **zero** ``- [ ] T###`` rows (a
  precondition assert): the roster comes from the WP frontmatter ``subtasks:``
  list, so a passing block/unblock case cannot be secretly reading a checkbox.
* The seed-before-remove (C-010) fixture is the mirror image — it deliberately
  KEEPS checkboxes and proves the migration reader still folds them to the
  snapshot; the two fixture families are never conflated.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.cli.commands.agent.tasks_shared import _check_unchecked_subtasks
from specify_cli.core.subtask_rows import (
    SubtaskRosterResolutionError,
    UNCHECKED_SUBTASK_ROW,
    authored_subtask_roster,
    iter_wp_section_subtask_rows,
    unchecked_subtask_ids_from_event_stream,
    unchecked_subtask_ids_from_snapshot,
)
from specify_cli.migration.backfill_runtime_state import _subtasks_from_tasks_md
from specify_cli.status import emit_inner_state_changed
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.models import TransitionRequest
from specify_cli.status.store import read_events
from specify_cli.status.store import read_event_stream
from specify_cli.status.models import Lane, SubtaskStatus, SubtaskValue, WPInnerStateDelta
from tests.status.conftest import seed_wp_to_planned

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_SLUG = "subtask-rows-snapshot"

#: A checkbox-FREE tasks.md — the roster now comes from frontmatter, so the
#: guard must block/unblock with zero canonical checkbox rows present.
_TASKS_MD_NO_CHECKBOXES = (
    "# Tasks\n\n## Subtask Index\n\n"
    "| Task | WP | Description |\n"
    "| --- | --- | --- |\n"
    "| T001 | WP01 | alpha |\n"
    "| T002 | WP01 | beta |\n"
    "| T003 | WP01 | gamma |\n\n"
    "## WP01 - repro\n\n"
    "**Subtasks**: T001, T002, T003\n"
)


# ---------------------------------------------------------------------------
# Fixture builders — a primary-partition mission dir with a WP frontmatter file
# and (optionally) a checkbox-free tasks.md; snapshot driven by the real emit.
# ---------------------------------------------------------------------------


def _seed_feature_dir(tmp_path: Path, *, tasks_md: str | None) -> Path:
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        '{"mission_slug":"subtask-rows-snapshot","topology":"single_branch"}\n',
        encoding="utf-8",
    )
    if tasks_md is not None:
        (feature_dir / "tasks.md").write_text(tasks_md, encoding="utf-8")
    return feature_dir


def _write_wp_file(feature_dir: Path, wp_id: str, subtask_ids: list[str]) -> Path:
    """Author a WP file whose frontmatter ``subtasks:`` list is the roster."""
    lines = ["---", f"work_package_id: {wp_id}", "title: repro"]
    if subtask_ids:
        lines.append("subtasks:")
        lines.extend(f"- {tid}" for tid in subtask_ids)
    else:
        lines.append("subtasks: []")
    lines += ["---", "", f"# {wp_id}", ""]
    wp_file = feature_dir / "tasks" / f"{wp_id}.md"
    wp_file.write_text("\n".join(lines), encoding="utf-8")
    return wp_file


def _emit_subtasks(feature_dir: Path, wp_id: str, subtasks: dict[str, SubtaskValue]) -> None:
    """Record subtask completion through the REAL writer ``mark-status`` uses."""
    emit_inner_state_changed(
        feature_dir,
        wp_id,
        WPInnerStateDelta(subtasks=subtasks),
        actor="test",
        mission_slug=_MISSION_SLUG,
    )


def _check(tmp_path: Path, wp_id: str, *, force: bool = False) -> list[str]:
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    with (
        patch(
            "specify_cli.cli.commands.agent.tasks.get_main_repo_root",
            return_value=tmp_path,
        ),
        patch(
            "specify_cli.coordination.resolve_status_surface",
            return_value=feature_dir / "status.events.jsonl",
        ),
    ):
        result: list[str] = _check_unchecked_subtasks(tmp_path, _MISSION_SLUG, wp_id, force)
        return result


def _assert_no_checkbox_rows(tasks_md: str) -> None:
    """Precondition: the fixture carries zero canonical checkbox rows, so any
    block/unblock verdict must come from the snapshot, never a checkbox."""
    rows = [
        line for line in tasks_md.splitlines() if UNCHECKED_SUBTASK_ROW.match(line.strip())
    ]
    assert rows == [], f"fixture must be checkbox-free; found {rows!r}"


# ---------------------------------------------------------------------------
# T054.1 / T054.2 — guard blocks (incomplete) and unblocks (complete) off the
# snapshot, with a checkbox-free fixture.
# ---------------------------------------------------------------------------


def test_guard_blocks_off_snapshot_when_incomplete(tmp_path: Path) -> None:
    _assert_no_checkbox_rows(_TASKS_MD_NO_CHECKBOXES)
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=_TASKS_MD_NO_CHECKBOXES)
    _write_wp_file(feature_dir, "WP01", ["T001", "T002", "T003"])
    _emit_subtasks(feature_dir, "WP01", {"T001": Lane.DONE, "T002": Lane.IN_PROGRESS, "T003": Lane.DONE})

    result = _check(tmp_path, "WP01")

    assert result == ["T002"], (
        "the incomplete id must come from the snapshot slot, not any checkbox "
        f"(the fixture has none); got {result!r}"
    )


def test_guard_unblocks_off_snapshot_when_all_done(tmp_path: Path) -> None:
    _assert_no_checkbox_rows(_TASKS_MD_NO_CHECKBOXES)
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=_TASKS_MD_NO_CHECKBOXES)
    _write_wp_file(feature_dir, "WP01", ["T001", "T002", "T003"])
    _emit_subtasks(feature_dir, "WP01", {"T001": Lane.DONE, "T002": Lane.DONE, "T003": Lane.DONE})

    assert _check(tmp_path, "WP01") == []


# ---------------------------------------------------------------------------
# T054.3 — force=True: the reader still reports the incomplete ids (the caller,
# not the reader, decides warn-vs-raise) — no behaviour drift on the force path.
# ---------------------------------------------------------------------------


def test_force_true_still_reports_ids_without_raising(tmp_path: Path) -> None:
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=_TASKS_MD_NO_CHECKBOXES)
    _write_wp_file(feature_dir, "WP01", ["T001", "T002", "T003"])
    _emit_subtasks(feature_dir, "WP01", {"T001": Lane.DONE})

    # Never raises here; returns the same incomplete ids regardless of force.
    forced = _check(tmp_path, "WP01", force=True)
    unforced = _check(tmp_path, "WP01", force=False)
    assert forced == unforced == ["T002", "T003"]


# ---------------------------------------------------------------------------
# T054.4 — an empty authored roster is "nothing to block on".
# ---------------------------------------------------------------------------


def test_empty_roster_is_nothing_to_block_on(tmp_path: Path) -> None:
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=_TASKS_MD_NO_CHECKBOXES)
    _write_wp_file(feature_dir, "WP01", [])  # frontmatter subtasks: []

    assert _check(tmp_path, "WP01") == []


def test_missing_subtasks_key_fails_closed(tmp_path: Path) -> None:
    """A defaulted model field must not disguise a deleted authored roster key."""
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=_TASKS_MD_NO_CHECKBOXES)
    (feature_dir / "tasks" / "WP01.md").write_text(
        "---\nwork_package_id: WP01\n---\n\n# WP01\n",
        encoding="utf-8",
    )

    with pytest.raises(SubtaskRosterResolutionError, match="subtasks.*missing"):
        _check(tmp_path, "WP01")


def test_missing_wp_file_fails_closed(tmp_path: Path) -> None:
    _seed_feature_dir(tmp_path, tasks_md=_TASKS_MD_NO_CHECKBOXES)
    with pytest.raises(SubtaskRosterResolutionError, match="work-package file is missing"):
        _check(tmp_path, "WP01")


def test_ambiguous_wp_files_fail_closed(tmp_path: Path) -> None:
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=_TASKS_MD_NO_CHECKBOXES)
    _write_wp_file(feature_dir, "WP01", ["T001"])
    (feature_dir / "tasks" / "WP01-other.md").write_text(
        "---\nwork_package_id: WP01\nsubtasks: []\n---\n",
        encoding="utf-8",
    )

    with pytest.raises(SubtaskRosterResolutionError, match="ambiguous files"):
        _check(tmp_path, "WP01")


def test_directory_named_like_a_wp_file_fails_closed(tmp_path: Path) -> None:
    """#7443: a directory matching the WP name is refused, not read."""
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=None)
    (feature_dir / "tasks" / "WP03-dir.md").mkdir()

    with pytest.raises(SubtaskRosterResolutionError, match=r"WP03-dir\.md is not a regular file"):
        authored_subtask_roster(feature_dir, "WP03")


@pytest.mark.parametrize("readme", ["README.md", "readme.md", "ReadMe.md"])
def test_readme_never_matches_a_wp_id(tmp_path: Path, readme: str) -> None:
    """#7443: ``readme.md`` is excluded in any case, so it never stands in for a WP file."""
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=None)
    (feature_dir / "tasks" / readme).write_text("---\nsubtasks: [T001]\n---\n", encoding="utf-8")

    with pytest.raises(SubtaskRosterResolutionError, match="work-package file is missing"):
        authored_subtask_roster(feature_dir, "README")


def test_malformed_wp_file_fails_closed(tmp_path: Path) -> None:
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=_TASKS_MD_NO_CHECKBOXES)
    (feature_dir / "tasks" / "WP01.md").write_text(
        "---\nwork_package_id: WP01\nsubtasks: [T001\n---\n",
        encoding="utf-8",
    )

    with pytest.raises(SubtaskRosterResolutionError, match="is unreadable"):
        _check(tmp_path, "WP01")


# ---------------------------------------------------------------------------
# T054.5 — fail-closed: an authored roster with a silent/absent snapshot BLOCKS
# (proves the deleted checkbox fallback did not become a silent open).
# ---------------------------------------------------------------------------


def test_fail_closed_on_silent_snapshot_blocks(tmp_path: Path) -> None:
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=_TASKS_MD_NO_CHECKBOXES)
    _write_wp_file(feature_dir, "WP01", ["T001", "T002", "T003"])
    # No _emit_subtasks(...) at all: the snapshot slot is silent for WP01.

    result = _check(tmp_path, "WP01")

    assert result == ["T001", "T002", "T003"], (
        "an authored roster with no snapshot completion must fail-closed (block "
        f"every id), not fall open to complete; got {result!r}"
    )


# ---------------------------------------------------------------------------
# T054.7 — no ``- [ ] T###`` checkbox remains in the SOURCE tasks templates
# WP13 edited. (This mission's own tasks.md checkbox strip is a closeout data
# step per the live-mission runner contract, so it is NOT asserted here.)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
# Mission doctrine-consumer-surface-missions-extraction-01KZ6G6H (FR-005)
# relocated missions/ from src/charter/offering/missions to packs/built-in/missions.
_EDITED_TASKS_TEMPLATES = (
    "packs/built-in/missions/software-dev/templates/tasks-template.md",
    "packs/built-in/missions/documentation/templates/tasks-template.md",
    "packs/built-in/missions/research/templates/tasks-template.md",
    # src/specify_cli/missions/{documentation,research}/templates/ are frozen,
    # migration-only forks (#5280; tests/runtime/test_frozen_migration_template_sources.py).
)


@pytest.mark.parametrize("rel_path", _EDITED_TASKS_TEMPLATES)
def test_source_tasks_templates_have_no_checkbox_rows(rel_path: str) -> None:
    template = _REPO_ROOT / rel_path
    text = template.read_text(encoding="utf-8")
    offenders = [
        line for line in text.splitlines() if UNCHECKED_SUBTASK_ROW.match(line.strip())
    ]
    assert offenders == [], (
        f"{rel_path} still emits canonical checkbox tracking rows: {offenders!r} — "
        "SC-010 requires reference rows tracked by mark-status, no checkbox glyph"
    )


def test_source_tasks_prompt_directs_mark_status() -> None:
    prompt = _REPO_ROOT / "packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md"
    text = prompt.read_text(encoding="utf-8")
    assert "mark-status" in text, "the tasks prompt must direct agents to mark-status"


# ---------------------------------------------------------------------------
# T054.8 — seed-before-remove (C-010): the migration reader still folds
# legacy checkboxes to the snapshot. This fixture DELIBERATELY has checkboxes.
# ---------------------------------------------------------------------------

_TASKS_MD_LEGACY_CHECKBOXES = (
    "# Tasks\n\n## WP01 - legacy\n"
    "- [x] T001 alpha done the legacy way\n"
    "- [ ] T002 beta still pending\n"
    "- [x] T003 gamma done the legacy way\n"
)


def test_backfill_seed_reader_still_folds_legacy_checkboxes() -> None:
    # The migration reader (``iter_wp_section_subtask_rows``) is intact and the
    # backfill seeds subtask completion from the checkboxes (C-010): removing
    # checkboxes from canonical missions did not break the migration seed path.
    rows = list(iter_wp_section_subtask_rows(_TASKS_MD_LEGACY_CHECKBOXES, "WP01"))
    assert rows == [("T001", True), ("T002", False), ("T003", True)]

    seeded = _subtasks_from_tasks_md(_TASKS_MD_LEGACY_CHECKBOXES, "WP01")
    assert seeded == {"T001": Lane.DONE, "T002": Lane.PLANNED, "T003": Lane.DONE}


# ---------------------------------------------------------------------------
# Direct unit coverage of the two new core resolvers (owned surface).
# ---------------------------------------------------------------------------


def test_authored_subtask_roster_reads_frontmatter(tmp_path: Path) -> None:
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=None)
    _write_wp_file(feature_dir, "WP01", ["T001", "T002", "T001", "T003"])  # dup T001

    # De-duplicated, authored order, ignores tasks.md entirely.
    assert authored_subtask_roster(feature_dir, "WP01") == ["T001", "T002", "T003"]
    with pytest.raises(SubtaskRosterResolutionError, match="work-package file is missing"):
        authored_subtask_roster(feature_dir, "WP99")


@pytest.mark.parametrize("terminal", [Lane.DONE, SubtaskStatus.SKIPPED], ids=["done", "skipped"])
def test_unchecked_from_snapshot_fail_closed_and_terminal_detection(tmp_path: Path, terminal: SubtaskValue) -> None:
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=None)
    _write_wp_file(feature_dir, "WP01", ["T001", "T002"])

    roster = ["T001", "T002"]
    # Silent snapshot -> fail-closed (every roster id incomplete).
    assert unchecked_subtask_ids_from_snapshot(feature_dir, "WP01", roster) == ["T001", "T002"]

    # A deliberately skipped subtask is as terminal as a done one; planned is not.
    _emit_subtasks(feature_dir, "WP01", {"T001": terminal, "T002": Lane.PLANNED})
    assert unchecked_subtask_ids_from_snapshot(feature_dir, "WP01", roster) == ["T002"]

    _emit_subtasks(feature_dir, "WP01", {"T002": terminal})
    assert unchecked_subtask_ids_from_snapshot(feature_dir, "WP01", roster) == []
    # The transactional (event-stream) resolver shares the same terminal rule.
    stream = read_event_stream(feature_dir)
    assert unchecked_subtask_ids_from_event_stream(stream, "WP01", roster) == []

    # An empty roster is nothing to block on regardless of snapshot state.
    assert unchecked_subtask_ids_from_snapshot(feature_dir, "WP01", []) == []


# ---------------------------------------------------------------------------
# #7442 — the authored roster accepts only task ids (``str``, non-bool ``int``);
# any other entry refuses with the WP file, the entry position, its type and
# the expected list form, instead of being coerced to an unmatchable junk id.
# ---------------------------------------------------------------------------

#: An integer whose decimal text exceeds Python's 4300-digit int->str limit.
#: Written as hex so the YAML parser builds it (its own decimal parse would refuse).
_HUGE_HEX_INT = "0x" + "f" * 4000

_NON_ID_ENTRIES = [
    pytest.param("- id: T001\n  title: x", 1, "mapping", id="mapping"),
    pytest.param("- [T001]", 1, "list", id="list"),
    pytest.param("- T001\n- 1.5", 2, "float", id="float"),
    pytest.param("- 2026-01-01", 1, "date", id="date"),
    pytest.param("- 2026-01-01T10:00:00Z", 1, "datetime", id="datetime"),
    pytest.param("- true", 1, "bool", id="bool"),
    pytest.param("- null", 1, "null", id="null"),
    pytest.param("- T001\n- ~", 2, "null", id="tilde"),
]


def _write_wp_raw_subtasks(feature_dir: Path, wp_id: str, subtasks_body: str) -> Path:
    """Author a WP file whose ``subtasks:`` value is *subtasks_body*, verbatim."""
    wp_file = feature_dir / "tasks" / f"{wp_id}-roster.md"
    wp_file.write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: repro\nsubtasks:\n{subtasks_body}\n---\n\n# {wp_id}\n",
        encoding="utf-8",
    )
    return wp_file


@pytest.mark.parametrize(("body", "position", "type_label"), _NON_ID_ENTRIES)
def test_non_id_roster_entry_refuses_with_file_position_and_remedy(
    tmp_path: Path, body: str, position: int, type_label: str
) -> None:
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=None)
    _write_wp_raw_subtasks(feature_dir, "WP01", body)

    with pytest.raises(SubtaskRosterResolutionError) as excinfo:
        authored_subtask_roster(feature_dir, "WP01")

    message = str(excinfo.value)
    assert "WP01-roster.md" in message
    assert f"entry {position} is a {type_label}" in message
    assert "as a list of task ids, e.g. - T001" in message


def test_int_too_long_to_convert_refuses_as_a_roster_error(tmp_path: Path) -> None:
    """Python refuses to render an int past 4300 digits; that must not escape as ``ValueError``."""
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=None)
    _write_wp_raw_subtasks(feature_dir, "WP01", f"- T001\n- {_HUGE_HEX_INT}")

    with pytest.raises(SubtaskRosterResolutionError, match=r"WP01-roster\.md.*entry 2 is an int too long"):
        authored_subtask_roster(feature_dir, "WP01")


def test_str_and_int_entries_are_still_accepted(tmp_path: Path) -> None:
    """Same-fixture positive control (FR-015): ``- T001`` and ``- 7`` are task ids."""
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=None)
    _write_wp_raw_subtasks(feature_dir, "WP01", "- T001\n- 7\n- ' T001 '")

    assert authored_subtask_roster(feature_dir, "WP01") == ["T001", "7"]


def test_for_review_cli_door_refuses_a_map_shaped_roster(tmp_path: Path) -> None:
    """The ``move-task --to for_review`` subtask gate (``_check_unchecked_subtasks``) refuses.

    Before #7442 the map was coerced to ``"{'id': 'T001', ...}"`` and the gate
    reported that junk id as an unchecked subtask nobody could ever mark.
    """
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=_TASKS_MD_NO_CHECKBOXES)
    _write_wp_raw_subtasks(feature_dir, "WP01", "- id: T001\n  title: alpha")

    with pytest.raises(SubtaskRosterResolutionError, match=r"WP01-roster\.md.*e\.g\. - T001"):
        _check(tmp_path, "WP01")


def test_for_review_transition_refuses_a_map_shaped_roster_and_persists_nothing(tmp_path: Path) -> None:
    """The emit pipeline's ``in_progress -> for_review`` subtask gate refuses too (FR-008)."""
    feature_dir = _seed_feature_dir(tmp_path, tasks_md=_TASKS_MD_NO_CHECKBOXES)
    _write_wp_raw_subtasks(feature_dir, "WP01", "- id: T001\n  title: alpha")
    seed_wp_to_planned(feature_dir, "WP01", slug=_MISSION_SLUG)
    for lane in ("claimed", "in_progress"):
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                to_lane=lane,
                actor="agent-1",
                workspace_context="worktree:/x",
                repo_root=tmp_path,
            )
        )
    before = len(read_events(feature_dir))

    with pytest.raises(SubtaskRosterResolutionError, match=r"WP01-roster\.md.*e\.g\. - T001"):
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                to_lane="for_review",
                actor="agent-1",
                repo_root=tmp_path,
            )
        )
    assert len(read_events(feature_dir)) == before
