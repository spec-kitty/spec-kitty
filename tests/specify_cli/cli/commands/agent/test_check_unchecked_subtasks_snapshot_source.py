"""Owned unit test (WP04/T017, #2684; rerouted for #2816 IC-10 / WP13):
``_check_unchecked_subtasks`` resolves subtask completion from the reduced
event-log snapshot ``subtasks`` slot — never from ``tasks.md`` checkbox bytes,
and never from a ``HistoryAdded`` narrative record.

FR-016 / SC-010: since the #2816 corpus cutover the guard's **roster** is the
authored WP-frontmatter ``subtasks:`` list (static design intent) and its
**completion** is *solely* the snapshot slot (populated by ``mark-status``'s
``emit_inner_state_changed`` call). The markdown checkbox is retired as a
subtask-completion proxy.

**The crux (discriminating, not concordant)**: every fixture below makes
``tasks.md`` and the reduced snapshot *disagree*. A concordant fixture would
pass even if the reader silently reverted to the checkbox byte — only a
contradiction proves the snapshot is the actual resolution source. The checkbox
bytes are pure noise to the rerouted guard; the roster comes from frontmatter.

A separate test proves the gate never consults the ``HistoryAdded`` narrative
path — a plausible wrong implementation could key off "was a HistoryAdded note
recorded" instead of the true ``subtasks`` slot; this pins that it does not.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.cli.commands.agent.tasks_shared import _check_unchecked_subtasks
from specify_cli.status.models import InnerStateChanged, Lane, StatusEvent, WPInnerStateDelta
from specify_cli.status.store import append_annotations_atomic_verified
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_SLUG = "check-unchecked-snapshot-source"

#: WP01's three canonical subtask rows in tasks.md — deliberately CONTRADICTING
#: the snapshot in every fixture, to prove they are ignored (the roster is the
#: frontmatter ``subtasks:`` list, not these rows).
_TASKS_MD_ALL_UNCHECKED = (
    "# Tasks\n\n## WP01 - repro\n"
    "- [ ] T001 alpha\n"
    "- [ ] T002 beta\n"
    "- [ ] T003 gamma\n"
)

_TASKS_MD_ALL_CHECKED = (
    "# Tasks\n\n## WP01 - repro\n"
    "- [x] T001 alpha\n"
    "- [x] T002 beta\n"
    "- [x] T003 gamma\n"
)


def _ulid(suffix: str) -> str:
    """Build a syntactically valid 26-char ULID from a short suffix."""
    return ("01KX" + suffix).ljust(26, "0")[:26]


def _seed_feature_dir(tmp_path: Path, tasks_md: str, *, roster: list[str] | None) -> Path:
    """Primary-partition mission dir: ``kitty-specs/<slug>/`` with a WP file whose
    frontmatter ``subtasks:`` list is the roster, plus a contradicting tasks.md."""
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (feature_dir / "tasks.md").write_text(tasks_md, encoding="utf-8")
    if roster is not None:
        lines = ["---", "work_package_id: WP01"]
        if roster:
            lines.append("subtasks:")
            lines += [f"- {tid}" for tid in roster]
        else:
            lines.append("subtasks: []")
        lines += ["---", "", "# WP01", ""]
        (feature_dir / "tasks" / "WP01.md").write_text("\n".join(lines), encoding="utf-8")
    return feature_dir


def _seed_claim_transition(feature_dir: Path, wp_id: str) -> None:
    """Seed a ``planned -> in_progress`` transition so the WP has a snapshot entry."""
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=_ulid("TRN" + wp_id),
            mission_slug=_MISSION_SLUG,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


def _seed_subtasks_annotation(feature_dir: Path, wp_id: str, subtasks: dict[str, Lane]) -> None:
    """Seed an ``InnerStateChanged`` ``subtasks`` delta — the mark-status emit shape."""
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id=_ulid("ANN" + wp_id),
                wp_id=wp_id,
                at="2026-01-01T00:01:00+00:00",
                actor="test",
                delta=WPInnerStateDelta(subtasks=subtasks),
            )
        ],
    )


def _check(tmp_path: Path, feature_dir: Path, wp_id: str) -> list[str]:
    with patch(
        "specify_cli.cli.commands.agent.tasks.get_main_repo_root", return_value=tmp_path
    ):
        result: list[str] = _check_unchecked_subtasks(tmp_path, _MISSION_SLUG, wp_id, False)
        return result


# ---------------------------------------------------------------------------
# The crux: discriminating (contradicting) fixtures, both directions.
# ---------------------------------------------------------------------------


def test_gate_follows_snapshot_complete_over_unchecked_markdown(tmp_path: Path) -> None:
    """Snapshot says DONE; tasks.md checkboxes are UNCHECKED — the gate must
    return ``[]`` (complete), honoring the log over the noise markdown byte."""
    feature_dir = _seed_feature_dir(
        tmp_path, _TASKS_MD_ALL_UNCHECKED, roster=["T001", "T002", "T003"]
    )
    _seed_claim_transition(feature_dir, "WP01")
    _seed_subtasks_annotation(
        feature_dir, "WP01", {"T001": Lane.DONE, "T002": Lane.DONE, "T003": Lane.DONE}
    )

    result = _check(tmp_path, feature_dir, "WP01")

    assert result == [], (
        "the gate must resolve completion from the reduced snapshot, not the "
        f"unchecked tasks.md bytes; got {result!r}"
    )


def test_gate_follows_snapshot_incomplete_over_checked_markdown(tmp_path: Path) -> None:
    """Mirror case: snapshot says one subtask is still incomplete while tasks.md
    shows every checkbox CHECKED — the gate must still refuse on the log's
    incomplete id, not wave it through because the markdown looks done."""
    feature_dir = _seed_feature_dir(
        tmp_path, _TASKS_MD_ALL_CHECKED, roster=["T001", "T002", "T003"]
    )
    _seed_claim_transition(feature_dir, "WP01")
    _seed_subtasks_annotation(
        feature_dir, "WP01", {"T001": Lane.DONE, "T002": Lane.IN_PROGRESS, "T003": Lane.DONE}
    )

    result = _check(tmp_path, feature_dir, "WP01")

    assert result == ["T002"], (
        "the gate must resolve completion from the reduced snapshot (T002 is "
        f"NOT done there), not the fully-checked tasks.md bytes; got {result!r}"
    )


# ---------------------------------------------------------------------------
# Fail-closed (#2816 IC-10): an authored roster with a silent snapshot BLOCKS —
# the retired legacy checkbox fallback did not become a silent open. An empty
# authored roster is "nothing to block on".
# ---------------------------------------------------------------------------


def test_fail_closed_when_snapshot_silent(tmp_path: Path) -> None:
    """A WP with an authored roster whose snapshot slot is silent must block
    (every roster id incomplete), even though tasks.md shows every box checked —
    the checkbox fallback is gone; unprovable completeness fails closed."""
    feature_dir = _seed_feature_dir(
        tmp_path, _TASKS_MD_ALL_CHECKED, roster=["T001", "T002", "T003"]
    )
    _seed_claim_transition(feature_dir, "WP01")
    # No subtasks annotation seeded: the snapshot slot is silent for WP01.

    result = _check(tmp_path, feature_dir, "WP01")

    assert result == ["T001", "T002", "T003"], (
        "a silent snapshot must fail-closed (block), not fall back to the "
        f"checked tasks.md bytes; got {result!r}"
    )


def test_empty_authored_roster_is_nothing_to_block_on(tmp_path: Path) -> None:
    """A WP with no authored ``subtasks:`` roster returns ``[]`` regardless of
    what the tasks.md checkboxes say."""
    feature_dir = _seed_feature_dir(tmp_path, _TASKS_MD_ALL_UNCHECKED, roster=[])
    _seed_claim_transition(feature_dir, "WP01")

    assert _check(tmp_path, feature_dir, "WP01") == []
