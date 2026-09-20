"""Parity guards for WP01 (mission ``terminus-safety-invariant-01M2XFT7``, T003/T004).

WP01 is a **behavior-preserving tidy-first enabler** (DIRECTIVE_025): it adds
``status_lanes.mission_terminal_acceptability`` and dedups ``doctor.py``'s
terminal-lane set onto the canonical ``status_lanes.TERMINAL_LANES``, but must
change NO observable ``accept`` or ``status doctor`` output.

* **T003** — ``accept``'s two lane-bucket views
  (``gates_core._all_work_packages_terminal`` and
  ``summary_core._has_non_terminal_lane``) are deliberately provenance-blind
  and are NOT rerouted onto the new aggregate; this file pins that they still
  evaluate the shared per-lane authority at ``has_provenance=False`` and are
  untouched by this WP (those two source files are not in WP01's owned_files).
* **T004** — ``doctor.py``'s two retired terminal-lane sites
  (``check_blanked_runtime_slots`` / ``check_orphan_workspaces``) now resolve
  against ``status_lanes.TERMINAL_LANES`` instead of a local duplicate; this
  file pins that the retired set is identical to the canonical one and that
  ``done``/``canceled`` classification is unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.acceptance.gates_core import _all_work_packages_terminal
from specify_cli.acceptance.summary_core import _has_non_terminal_lane
from specify_cli.status.doctor import check_blanked_runtime_slots, check_orphan_workspaces
from specify_cli.status_lanes import TERMINAL_LANES

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class TestDoctorTerminalLaneParity:
    """T004: the retired local terminal-lane sets equal the canonical authority."""

    def test_terminal_lanes_is_exactly_done_and_canceled(self) -> None:
        # Pins the value the retired ``_TERMINAL_LANES`` / inline
        # ``{Lane.DONE, Lane.CANCELED}`` duplicates carried before dedup.
        assert frozenset({"done", "canceled"}) == TERMINAL_LANES

    def test_blanked_runtime_slot_check_still_skips_done_wp(self) -> None:
        snapshot = {"work_packages": {"WP01": {"lane": "done", "agent": ""}}}

        findings = check_blanked_runtime_slots(snapshot)

        assert findings == []

    def test_blanked_runtime_slot_check_still_skips_canceled_wp(self) -> None:
        snapshot = {"work_packages": {"WP01": {"lane": "canceled", "agent": ""}}}

        findings = check_blanked_runtime_slots(snapshot)

        assert findings == []

    def test_blanked_runtime_slot_check_still_flags_active_wp(self) -> None:
        snapshot = {"work_packages": {"WP01": {"lane": "in_progress", "agent": ""}}}

        findings = check_blanked_runtime_slots(snapshot)

        assert len(findings) == 1

    def test_orphan_workspaces_still_treats_done_and_canceled_as_terminal(self, tmp_path: Path) -> None:
        worktrees_dir = tmp_path / ".worktrees"
        worktrees_dir.mkdir()
        (worktrees_dir / "wp01-parity-lane-a").mkdir()

        snapshot = {
            "work_packages": {
                "WP01": {"lane": "done"},
                "WP02": {"lane": "canceled"},
            }
        }

        findings = check_orphan_workspaces(tmp_path, "wp01-parity", snapshot)

        assert len(findings) == 1

    def test_orphan_workspaces_still_treats_active_wp_as_not_terminal(self, tmp_path: Path) -> None:
        worktrees_dir = tmp_path / ".worktrees"
        worktrees_dir.mkdir()
        (worktrees_dir / "wp01-parity-lane-a").mkdir()

        snapshot = {
            "work_packages": {
                "WP01": {"lane": "done"},
                "WP02": {"lane": "in_progress"},
            }
        }

        findings = check_orphan_workspaces(tmp_path, "wp01-parity", snapshot)

        assert findings == []


class TestAcceptLaneViewsUntouched:
    """T003: accept's provenance-blind lane views are NOT rerouted onto the new aggregate."""

    def test_all_work_packages_terminal_still_provenance_blind_on_canceled(self) -> None:
        # A canceled-only lane bucket carries no provenance in this lane-only
        # view -- it must stay NOT terminal-ready, exactly as before WP01
        # (has_provenance=False is hardcoded at this call site by design; see
        # gates_core._all_work_packages_terminal's docstring).
        lanes = {"canceled": ["WP01"]}

        assert _all_work_packages_terminal(lanes) is False

    def test_all_work_packages_terminal_still_true_for_approved_done_only(self) -> None:
        lanes = {"approved": ["WP01"], "done": ["WP02"]}

        assert _all_work_packages_terminal(lanes) is True

    def test_has_non_terminal_lane_still_flags_canceled_bucket(self) -> None:
        # Mirrors the pre-WP01 behavior: canceled is "not unconditionally
        # acceptable" under the provenance-blind recommended-fix view.
        lanes = {"canceled": ["WP01"]}

        assert _has_non_terminal_lane(lanes) is True

    def test_has_non_terminal_lane_still_clear_for_approved_done_only(self) -> None:
        lanes = {"approved": ["WP01"], "done": ["WP02"]}

        assert _has_non_terminal_lane(lanes) is False
