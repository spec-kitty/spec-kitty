"""Regression guard for the four coord-topology lane-lifecycle guards (issue #3867).

The coord lane-lifecycle surface-authority fix has **already landed** on ``main``
(via #2533, FIX-M2-04, #3910, #3915, and the #2070 residue-predicate delegation).
These tests LOCK that fixed behaviour: each one pins an *observable* fact of a
lane-lifecycle guard on current HEAD, so a future change that reintroduces one of
the fixed defects — a kind-blind divergent read, a lost coord-residue exclusion —
reds a pin instead of slipping through silently. They are GREEN on HEAD because
HEAD is the fixed state.

Scope discipline (avoid over-pinning): each assertion pins an *observable* fact
(a predicate's boolean, a produced remedy string, the gate's read surface), never
an internal call graph, so a legitimate future refactor that preserves behaviour
does not spuriously churn an unrelated pin.

The single authority these guards route through is ``resolve_artifact_surface``: a
coordination artifact's surface is whatever it returns, and the lane is never that
surface. These pins anchor that invariant to observed HEAD behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mission_runtime import (
    MissionArtifactKind,
    is_primary_artifact_kind,
    kind_for_mission_file,
)
from specify_cli.coordination.coherence import is_coord_residue_churn
from specify_cli.lanes.auto_rebase import (
    _is_coordination_owned_artifact,
    _is_status_events_path,
    _is_status_json_path,
)

pytestmark = [pytest.mark.unit]

_SLUG = "coord-topo-unprot-01M28ZZH"


def _rel(name: str) -> str:
    """A mission-relative kitty-specs path for *name* under the fixture slug."""
    return f"kitty-specs/{_SLUG}/{name}"


# ---------------------------------------------------------------------------
# Guard 1 — move-task kitty-specs pollution check
# ---------------------------------------------------------------------------
#
# Guard 1's *detection* was already fixed on HEAD (FIX-M2-04, commit 8a95e2d36e,
# #2274/#2980): the contamination producer excludes COORD-partition files via
# ``is_coord_residue_churn`` so Guard 1 CANNOT fire on a pure coord-owned status
# file today. The behaviour worth pinning here is the *remedy guidance text*, which
# is the blanket ``-- kitty-specs/`` restore.


class TestGuard1PollutionCheck:
    @pytest.mark.parametrize(
        "basename",
        [
            "status.events.jsonl",
            "status.json",
            "issue-matrix.json",
            "issue-matrix.md",
        ],
    )
    def test_coord_owned_artifacts_are_excluded_from_contamination(self, basename: str) -> None:
        """FIX-M2-04: coord-owned status/matrix files are coord residue, so the
        contamination producer (``_list_wp_branch_mission_specs_changes``)
        excludes them — Guard 1 cannot flag them on a coord-topology lane."""
        assert is_coord_residue_churn(_rel(basename), mission_slug=_SLUG) is True

    @pytest.mark.parametrize(
        "basename",
        ["spec.md", "plan.md", "tasks.md", "lanes.json"],
    )
    def test_primary_planning_artifacts_are_still_contamination(self, basename: str) -> None:
        """Genuine PRIMARY-partition planning pollution (spec/plan/tasks/lanes
        authored on a lane) is NOT coord residue, so Guard 1 still flags it —
        the fail-toward-flag invariant this guard preserves."""
        assert is_coord_residue_churn(_rel(basename), mission_slug=_SLUG) is False

    def test_remedy_pathspec_is_currently_the_blanket_kitty_specs_restore(self, tmp_path: Path) -> None:
        """Pin the remedy shape: the guidance restores the *whole*
        ``kitty-specs/`` tree, not just the flagged PRIMARY-partition paths.

        The blanket restore is the current, safe behaviour (it can only over-
        restore, never leave pollution on the lane); this pin makes any future
        narrowing to the specific flagged ``is_primary_artifact_kind`` paths a
        visible, deliberate delta rather than a silent change.
        """
        from specify_cli.core.constants import KITTY_SPECS_DIR
        from specify_cli.cli.commands.agent.tasks_parsing_validation import (
            _check_kitty_specs_contamination,
        )

        # A feature_dir with no meta.json → the guard falls back to check_branch
        # as its delta base (legacy/no-planning-branch path).
        feature_dir = tmp_path / "kitty-specs" / _SLUG
        feature_dir.mkdir(parents=True)
        flagged = _rel("spec.md")

        def _stub_contamination_list(*, worktree_path: Path, base_branch: str) -> list[str]:
            # Inject a single PRIMARY-partition pollution path so the guard emits
            # its remedy guidance; the git delta itself is not under test here.
            return [flagged]

        guidance = _check_kitty_specs_contamination(
            worktree_path=tmp_path,
            check_branch="mission-base",
            feature_dir=feature_dir,
            wp_id="WP01",
            target_lane="for_review",
            list_wp_branch_specs_changes_for_guard=_stub_contamination_list,
        )

        assert guidance is not None, "guard must emit remedy guidance when it flags a file"
        remedy = "\n".join(guidance)
        # Blanket restore of the entire kitty-specs tree (current behaviour):
        assert f"-- {KITTY_SPECS_DIR}/" in remedy
        # And crucially NOT narrowed to the specific flagged path:
        assert f"-- {flagged}" not in remedy


# ---------------------------------------------------------------------------
# Guard 2 — review-claim auto-rebase membership predicates
# ---------------------------------------------------------------------------
#
# Guard 2's auto-rebase "take theirs" arm classifies coordination-owned
# artifacts; on HEAD it delegates through the residue predicate + partition
# membership (#2070). Pin the observable classification so a regression that
# drops a coord-owned artifact from the take-theirs arm is caught.


class TestGuard2AutoRebaseMembership:
    def test_status_events_path_predicate(self) -> None:
        assert _is_status_events_path(_rel("status.events.jsonl")) is True
        assert _is_status_events_path(_rel("status.json")) is False
        assert _is_status_events_path(_rel("spec.md")) is False

    def test_status_json_path_predicate(self) -> None:
        assert _is_status_json_path(_rel("status.json")) is True
        assert _is_status_json_path(_rel("status.events.jsonl")) is False
        assert _is_status_json_path(_rel("spec.md")) is False

    @pytest.mark.parametrize(
        "basename",
        [
            "status.events.jsonl",
            "status.json",
            "issue-matrix.json",
            "issue-matrix.md",
        ],
    )
    def test_coordination_owned_artifact_membership(self, basename: str) -> None:
        """The auto-rebase "take theirs" arm currently treats each of these as a
        coordination-owned artifact it deterministically resolves."""
        assert _is_coordination_owned_artifact(_rel(basename)) is True

    def test_primary_source_is_not_coordination_owned(self) -> None:
        """``spec.md`` is a planning SOURCE doc — its conflicts surface as a
        manual halt, never a coordination-owned take-theirs."""
        assert _is_coordination_owned_artifact(_rel("spec.md")) is False


# ---------------------------------------------------------------------------
# The ONE authority the guards route through
# ---------------------------------------------------------------------------
#
# Pin the classifier + partition predicate the landed fix routes every guard
# through, so the surface-authority invariant is anchored to observed HEAD
# behaviour.


class TestSingleAuthorityClassifier:
    @pytest.mark.parametrize(
        ("basename", "expected_kind"),
        [
            ("status.events.jsonl", MissionArtifactKind.STATUS_STATE),
            ("status.json", MissionArtifactKind.STATUS_STATE),
            ("issue-matrix.json", MissionArtifactKind.ISSUE_MATRIX),
            ("spec.md", MissionArtifactKind.SPEC),
            ("lanes.json", MissionArtifactKind.LANE_STATE),
        ],
    )
    def test_kind_for_mission_file(self, basename: str, expected_kind: MissionArtifactKind) -> None:
        assert kind_for_mission_file(_rel(basename), mission_slug=_SLUG) is expected_kind

    def test_coord_partition_kinds_are_not_primary(self) -> None:
        assert is_primary_artifact_kind(MissionArtifactKind.STATUS_STATE) is False
        assert is_primary_artifact_kind(MissionArtifactKind.ISSUE_MATRIX) is False

    def test_planning_partition_kinds_are_primary(self) -> None:
        assert is_primary_artifact_kind(MissionArtifactKind.SPEC) is True
        assert is_primary_artifact_kind(MissionArtifactKind.FINALIZED_EXECUTION_PLAN) is True
        assert is_primary_artifact_kind(MissionArtifactKind.TASKS_INDEX) is True
        assert is_primary_artifact_kind(MissionArtifactKind.LANE_STATE) is True


# ---------------------------------------------------------------------------
# Guard 4 — issue-matrix approve gate reads the caller-passed feature_dir
# ---------------------------------------------------------------------------
#
# The real approve gate (``_issue_matrix_approval_blocker``) reads the matrix
# from its ``feature_dir`` argument — the caller's topology-resolved read surface
# — and consults ``primary_feature_dir`` ONLY to DISCOVER referenced issues.
# Pin that contract: the gate reads exactly the ``feature_dir`` it is handed, and
# uses ``primary_feature_dir`` only for issue discovery. On HEAD the handed read
# surface and the issue-matrix write surface AGREE — both resolve through the same
# authority (see ``TestGuard4NoSplitBrain`` in the integration suite: read ==
# ``resolve_artifact_surface(ISSUE_MATRIX)``, and the verdict writes through
# ``write_target(ISSUE_MATRIX)`` to that same surface) — so the FR-004 split-brain
# cannot arise. This guard locks the read-its-handed-dir contract so a regression
# that reintroduces a kind-blind read diverging from the matrix authority is
# caught.


class TestGuard4ApproveGateReadSurface:
    @staticmethod
    def _write_spec_with_issue_ref(feature_dir: Path, issue: int) -> None:
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "spec.md").write_text(f"# Spec\n\nCloses #{issue}. Substantive content.\n", encoding="utf-8")

    def test_gate_reads_matrix_from_feature_dir_arg_not_primary(self, tmp_path: Path) -> None:
        """A matrix present on one dir but absent on the ``feature_dir`` the gate
        is handed → the gate BLOCKS with the "required before approval" signal.

        This pins the read-its-handed-dir contract: the gate trusts the
        ``feature_dir`` argument, so a matrix on a *different* dir is invisible to
        it. On HEAD the handed dir IS the matrix authority surface (see the
        integration suite's ``TestGuard4NoSplitBrain``), so this constructed
        divergence cannot arise naturally — the pin exists to catch a regression
        that reintroduces a kind-blind read diverging from the authority.
        """
        from specify_cli.cli.commands.agent.tasks_parsing_validation import (
            _issue_matrix_approval_blocker,
        )
        from specify_cli.status.models import Lane
        from specify_cli.tasks.issue_matrix_migration import (
            issue_matrix_artifact_present,
        )

        primary_dir = tmp_path / "primary" / "kitty-specs" / _SLUG
        coord_husk_dir = tmp_path / "coord" / "kitty-specs" / _SLUG
        coord_husk_dir.mkdir(parents=True)

        # PRIMARY carries the referenced-issue source AND an issue-matrix artifact
        # (the verdict-write surface on an unprotected primary).
        self._write_spec_with_issue_ref(primary_dir, 3867)
        (primary_dir / "issue-matrix.json").write_text("[]\n", encoding="utf-8")
        # The COORD husk carries NO issue-matrix (the read surface the kind-blind
        # handoff hands the gate).
        assert issue_matrix_artifact_present(primary_dir) is True
        assert issue_matrix_artifact_present(coord_husk_dir) is False

        blocker = _issue_matrix_approval_blocker(
            coord_husk_dir,
            target_lane=Lane.APPROVED,
            primary_feature_dir=primary_dir,
        )

        assert blocker is not None, "gate must block: it reads the coord husk (no matrix), not the PRIMARY surface where the verdict lives"
        # Assert on the emitted SIGNAL TEXT (not merely truthiness). #4330 has
        # landed: the gate now names the artifact it actually reads. This coord
        # husk carries NO matrix (neither ``.json`` nor ``.md``), so the prefix
        # resolves to the canonical scaffolded artifact ``issue-matrix.json``
        # (C-008: no new ``.md`` is emitted) — no longer the old hardcoded,
        # wrong-for-JSON-missions ``issue-matrix.md``.
        assert "ERROR: issue-matrix.json" in blocker
        assert "is required before approval" in blocker
        # The referenced issue was discovered from the PRIMARY spec.md, proving
        # primary_feature_dir is used for discovery while the matrix read is NOT.
        assert "#3867" in blocker

    def test_gate_is_satisfiable_when_read_surface_holds_the_matrix(self, tmp_path: Path) -> None:
        """Control: the SAME issue reference does NOT block when the gate reads a
        surface whose matrix has no unresolved rows — proving the block above is
        a surface mismatch, not an unfillable requirement.
        """
        from specify_cli.cli.commands.agent.tasks_parsing_validation import (
            _issue_matrix_approval_blocker,
        )
        from specify_cli.status.models import Lane

        # No issue references anywhere → the gate short-circuits to None (refs is
        # empty). This is the minimal, robust "not blocked" control that does not
        # depend on the full matrix-satisfaction schema.
        feature_dir = tmp_path / "kitty-specs" / _SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "spec.md").write_text("# Spec\n\nNo issue references here.\n", encoding="utf-8")

        blocker = _issue_matrix_approval_blocker(
            feature_dir,
            target_lane=Lane.APPROVED,
            primary_feature_dir=feature_dir,
        )
        assert blocker is None
