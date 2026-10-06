"""Tests for the live `next`-loop tasks_finalize occurrence-map guard (WP02).

Covers the shared `_occurrence_gate_failures` helper and its wiring into both
live pre-implement guard enumerators — `_check_cli_guards` (legacy DAG path)
and `_check_composed_action_guard` (composition path) — at the tasks_finalize
boundary. Reuses `ensure_occurrence_classification_ready` (no new validation
logic, C-001); the gate self-conditions on stored `change_mode` (C-003).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Fixtures shared by every test below.
#
# Each fixture builds a feature_dir that is otherwise "finalize-ready"
# (spec.md with a mapped functional requirement, tasks.md, and a WP file
# carrying an explicit `dependencies` frontmatter field) so that the
# pre-existing tasks_finalize guard checks produce zero failures on their
# own — isolating the occurrence-map gate's contribution to `failures`.
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    """Initialize a bare git repo at *path*."""
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


VALID_OCCURRENCE_MAP = """\
target:
  term: oldName
  replacement: newName
  operation: rename
categories:
  code_symbols:
    action: rename
  import_paths:
    action: rename
  filesystem_paths:
    action: manual_review
  serialized_keys:
    action: do_not_change
  cli_commands:
    action: do_not_change
  user_facing_strings:
    action: rename_if_user_visible
  tests_fixtures:
    action: rename
  logs_telemetry:
    action: do_not_change
"""

SCHEMA_INVALID_OCCURRENCE_MAP = """\
categories:
  code_symbols:
    action: rename
"""

INADMISSIBLE_OCCURRENCE_MAP = """\
target:
  term: oldName
  replacement: newName
  operation: rename
categories:
  code_symbols:
    action: rename
  import_paths:
    action: rename
"""


def _scaffold_finalize_ready_feature(
    tmp_path: Path,
    *,
    change_mode: str | None,
    occurrence_map_content: str | None,
    mission_slug: str = "042-occurrence-gate-feature",
) -> Path:
    """Build a feature_dir that is finalize-ready aside from the occurrence gate.

    Reuses the ``ensure_occurrence_classification_ready`` fixture shapes
    already established in ``tests/specify_cli/bulk_edit/test_gate.py``.
    """
    repo_root = tmp_path / "project"
    repo_root.mkdir()
    _init_git_repo(repo_root)
    (repo_root / ".kittify").mkdir()

    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)

    meta: dict[str, object] = {
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "friendly_name": "Test",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01",
    }
    if change_mode is not None:
        meta["change_mode"] = change_mode
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    (feature_dir / "spec.md").write_text(
        "# Spec\n\n"
        "## Functional Requirements\n\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | First | Covered by WP01. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: WP01\ndependencies: []\n"
        "requirement_refs: [FR-001]\n---\n# WP01\nDo something.\n",
        encoding="utf-8",
    )

    if occurrence_map_content is not None:
        (feature_dir / "occurrence_map.yaml").write_text(occurrence_map_content, encoding="utf-8")

    return feature_dir


# ---------------------------------------------------------------------------
# T006: shared `_occurrence_gate_failures` helper
# ---------------------------------------------------------------------------


class TestOccurrenceGateFailuresHelper:
    def test_non_bulk_edit_is_noop(self, tmp_path: Path) -> None:
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode=None, occurrence_map_content=None
        )

        from runtime.next.runtime_bridge import _occurrence_gate_failures

        assert _occurrence_gate_failures(feature_dir) == []

    def test_bulk_edit_missing_map_returns_canonical_error(self, tmp_path: Path) -> None:
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode="bulk_edit", occurrence_map_content=None
        )

        from runtime.next.runtime_bridge import _occurrence_gate_failures

        failures = _occurrence_gate_failures(feature_dir)
        assert len(failures) == 1
        assert "Occurrence map required" in failures[0]

    def test_bulk_edit_valid_admissible_map_is_noop(self, tmp_path: Path) -> None:
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode="bulk_edit", occurrence_map_content=VALID_OCCURRENCE_MAP
        )

        from runtime.next.runtime_bridge import _occurrence_gate_failures

        assert _occurrence_gate_failures(feature_dir) == []


# ---------------------------------------------------------------------------
# T007: `_check_cli_guards` tasks_finalize branch
# ---------------------------------------------------------------------------


class TestCheckCliGuardsOccurrenceGate:
    def test_blocks_bulk_edit_missing_map(self, tmp_path: Path) -> None:
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode="bulk_edit", occurrence_map_content=None
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_finalize", feature_dir)
        assert len(failures) == 1
        assert "Occurrence map required" in failures[0]

    def test_blocks_bulk_edit_schema_invalid_map(self, tmp_path: Path) -> None:
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode="bulk_edit", occurrence_map_content=SCHEMA_INVALID_OCCURRENCE_MAP
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_finalize", feature_dir)
        # Provenance-pinned: the failure must be the schema error from the
        # occurrence gate (missing 'target' section), not an unrelated
        # tasks_finalize failure that would let a dropped gate slip through.
        assert any("target" in f.lower() for f in failures), failures

    def test_blocks_bulk_edit_inadmissible_map(self, tmp_path: Path) -> None:
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode="bulk_edit", occurrence_map_content=INADMISSIBLE_OCCURRENCE_MAP
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_finalize", feature_dir)
        # Provenance-pinned: the failure must be the admissibility error from
        # the occurrence gate (too few / missing standard categories).
        assert any(
            "at least" in f.lower() or "categor" in f.lower() for f in failures
        ), failures

    def test_passes_bulk_edit_valid_admissible_map(self, tmp_path: Path) -> None:
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode="bulk_edit", occurrence_map_content=VALID_OCCURRENCE_MAP
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_finalize", feature_dir)
        assert failures == []

    def test_noop_non_bulk_edit_mission(self, tmp_path: Path) -> None:
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode=None, occurrence_map_content=None
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_finalize", feature_dir)
        assert failures == []

    def test_tasks_outline_and_tasks_packages_are_not_gated(self, tmp_path: Path) -> None:
        """Regression guard: the occurrence gate fires only at tasks_finalize."""
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode="bulk_edit", occurrence_map_content=None
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        assert _check_cli_guards("tasks_outline", feature_dir) == []
        assert _check_cli_guards("tasks_packages", feature_dir) == []


# ---------------------------------------------------------------------------
# T008: `_check_composed_action_guard` tasks_finalize / composition-terminal block
# ---------------------------------------------------------------------------


class TestCheckComposedActionGuardOccurrenceGate:
    def test_blocks_bulk_edit_missing_map_composition_only(self, tmp_path: Path) -> None:
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode="bulk_edit", occurrence_map_content=None
        )

        from runtime.next.runtime_bridge_composition import _check_composed_action_guard

        failures = _check_composed_action_guard("tasks", feature_dir, legacy_step_id=None)
        assert len(failures) == 1
        assert "Occurrence map required" in failures[0]

    def test_blocks_bulk_edit_missing_map_legacy_tasks_finalize(self, tmp_path: Path) -> None:
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode="bulk_edit", occurrence_map_content=None
        )

        from runtime.next.runtime_bridge_composition import _check_composed_action_guard

        failures = _check_composed_action_guard(
            "tasks", feature_dir, legacy_step_id="tasks_finalize"
        )
        assert len(failures) == 1
        assert "Occurrence map required" in failures[0]

    def test_passes_bulk_edit_valid_admissible_map(self, tmp_path: Path) -> None:
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode="bulk_edit", occurrence_map_content=VALID_OCCURRENCE_MAP
        )

        from runtime.next.runtime_bridge_composition import _check_composed_action_guard

        failures = _check_composed_action_guard("tasks", feature_dir, legacy_step_id=None)
        assert failures == []

    def test_noop_non_bulk_edit_mission(self, tmp_path: Path) -> None:
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode=None, occurrence_map_content=None
        )

        from runtime.next.runtime_bridge_composition import _check_composed_action_guard

        failures = _check_composed_action_guard("tasks", feature_dir, legacy_step_id=None)
        assert failures == []

    def test_tasks_outline_and_tasks_packages_substeps_are_not_gated(self, tmp_path: Path) -> None:
        """Regression guard: composition substeps prior to tasks_finalize must
        not run the occurrence gate, matching `_check_cli_guards` semantics."""
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode="bulk_edit", occurrence_map_content=None
        )

        from runtime.next.runtime_bridge_composition import _check_composed_action_guard

        outline_failures = _check_composed_action_guard(
            "tasks", feature_dir, legacy_step_id="tasks_outline"
        )
        assert not any("Occurrence map required" in failure for failure in outline_failures)

        packages_failures = _check_composed_action_guard(
            "tasks", feature_dir, legacy_step_id="tasks_packages"
        )
        assert not any("Occurrence map required" in failure for failure in packages_failures)


# ---------------------------------------------------------------------------
# T005 (parity): both dispatch paths agree, and neither double-reports.
# ---------------------------------------------------------------------------


class TestOccurrenceGateParityAcrossDispatchPaths:
    @pytest.mark.parametrize(
        "change_mode,occurrence_map_content",
        [
            ("bulk_edit", None),
            ("bulk_edit", SCHEMA_INVALID_OCCURRENCE_MAP),
            ("bulk_edit", INADMISSIBLE_OCCURRENCE_MAP),
            ("bulk_edit", VALID_OCCURRENCE_MAP),
            (None, None),
        ],
    )
    def test_both_guards_agree_and_no_duplicate_error(
        self, tmp_path: Path, change_mode: str | None, occurrence_map_content: str | None
    ) -> None:
        feature_dir = _scaffold_finalize_ready_feature(
            tmp_path, change_mode=change_mode, occurrence_map_content=occurrence_map_content
        )

        from runtime.next.runtime_bridge import _check_cli_guards
        from runtime.next.runtime_bridge_composition import _check_composed_action_guard

        legacy_failures = _check_cli_guards("tasks_finalize", feature_dir)
        composed_failures = _check_composed_action_guard(
            "tasks", feature_dir, legacy_step_id=None
        )

        legacy_blocked = len(legacy_failures) > 0
        composed_blocked = len(composed_failures) > 0
        assert legacy_blocked == composed_blocked, (
            "Both dispatch paths must agree on block/pass for the same fixture "
            f"(legacy={legacy_failures!r}, composed={composed_failures!r})"
        )

        # No duplicate occurrence-gate error within a single guard's own
        # failures list (the shared helper contributes exactly one error
        # message per call, never two).
        occurrence_hits_legacy = [f for f in legacy_failures if "Occurrence map" in f]
        occurrence_hits_composed = [f for f in composed_failures if "Occurrence map" in f]
        assert len(occurrence_hits_legacy) <= 1
        assert len(occurrence_hits_composed) <= 1
