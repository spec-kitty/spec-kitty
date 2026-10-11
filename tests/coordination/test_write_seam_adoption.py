"""Tests for ``coordination.write_seam`` (WP03 / T010 / T013).

Covers the two cross-cutting contracts every Lane-C writer (WP04/05/07/10)
inherits from this foundation:

- **FR-011 zero-write refusal**: an unroutable target (missing coord surface,
  deleted ``target_branch``, or any other mission-resolution failure) returns
  a structured, recoverable ``"refused"`` result disclosing #3033 -- NEVER a
  fallback write, NEVER a raised exception, and (proven directly)
  ``commit_for_mission`` is never even invoked, so literally nothing is
  written.
- **FR-012 idempotent, structured result**: a re-run with an unchanged
  artifact is a no-op (``"unchanged"``), inherited from
  ``commit_for_mission``'s own idempotence contract.
- **Ledger-M16 recursion guard**: the write boundary resolves via
  ``PlacementSeam.write_target`` and never calls ``PlacementSeam.read_dir`` --
  the read and write authorities are never conflated at this seam.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mission_runtime import ActionContextError, CommitTarget, MissionArtifactKind
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.coordination.write_seam import WriteSeamResult, write_artifact
from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_SLUG = "001-write-seam-demo"


def _policy(*, protected: bool = False) -> object:
    class _Policy:
        def is_protected(self, ref: str) -> bool:  # noqa: ARG002 - fixed-answer stub
            return protected

    return _Policy()


def _status_read_path_not_found(mission_slug: str, tmp_path: Path) -> StatusReadPathNotFound:
    return StatusReadPathNotFound(
        repo_root=tmp_path,
        mission_slug=mission_slug,
        mid8="AAAA1111",
        coord_candidate=tmp_path / ".worktrees" / f"{mission_slug}-AAAA1111-coord",
        primary_candidate=tmp_path / "kitty-specs" / mission_slug,
    )


# ---------------------------------------------------------------------------
# FR-011: zero-write refusal
# ---------------------------------------------------------------------------


class TestZeroWriteRefusal:
    def test_unroutable_target_refuses_and_discloses_3033(self, tmp_path: Path) -> None:
        """An unresolvable mission (ActionContextError) refuses -- structured
        result, no exception escapes, #3033 named in the diagnostic."""
        artifact = tmp_path / "phantom.md"  # deliberately never created

        with (
            patch("specify_cli.coordination.write_seam.placement_seam") as seam_ctor,
            patch(
                "specify_cli.coordination.write_seam.commit_for_mission",
                side_effect=AssertionError("commit_for_mission must not be called on refusal"),
            ) as commit_mock,
        ):
            seam_ctor.return_value = MagicMock(
                write_target=MagicMock(
                    side_effect=ActionContextError(
                        "MISSION_CONTEXT_UNRESOLVED", "mission slug does not resolve"
                    )
                )
            )

            result = write_artifact(
                repo_root=tmp_path,
                mission_slug=_MISSION_SLUG,
                kind=MissionArtifactKind.ISSUE_MATRIX,
                files=(artifact,),
                message="chore: write issue matrix row",
                policy=_policy(),
                entry_id="issue-42",
            )

            commit_mock.assert_not_called()

        assert result == WriteSeamResult(
            status="refused",
            entry_id="issue-42",
            destination_surface=None,
            commit_hash=None,
            diagnostic=result.diagnostic,
        )
        assert result.diagnostic is not None
        assert "#3033" in result.diagnostic
        assert _MISSION_SLUG in result.diagnostic
        # Nothing was written -- the phantom artifact still does not exist.
        assert not artifact.exists()

    def test_deleted_coordination_branch_refuses_never_falls_back_to_main(
        self, tmp_path: Path
    ) -> None:
        """A deleted ``target_branch`` / coordination branch
        (``StatusReadPathNotFound`` and its ``CoordinationBranchDeleted``
        subclass) refuses -- this is the literal FR-011 scenario: the
        pre-existing ``resolve_write_target_or_degrade`` degrade path would
        fall back to writing ``main`` here; this helper must not."""
        artifact = tmp_path / "status.events.jsonl"
        artifact.write_text('{"event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV"}\n', encoding="utf-8")

        with (
            patch("specify_cli.coordination.write_seam.placement_seam") as seam_ctor,
            patch(
                "specify_cli.coordination.write_seam.commit_for_mission",
                side_effect=AssertionError("commit_for_mission must not be called on refusal"),
            ) as commit_mock,
        ):
            seam_ctor.return_value = MagicMock(
                write_target=MagicMock(
                    side_effect=_status_read_path_not_found(_MISSION_SLUG, tmp_path)
                )
            )

            result = write_artifact(
                repo_root=tmp_path,
                mission_slug=_MISSION_SLUG,
                kind=MissionArtifactKind.STATUS_STATE,
                files=(artifact,),
                message="chore(spec-kitty): status transition",
                policy=_policy(),
                entry_id="WP01",
            )

            commit_mock.assert_not_called()

        assert result.status == "refused"
        assert result.destination_surface is None
        assert result.diagnostic is not None
        assert "main" not in result.diagnostic.split("Original resolution failure:")[0]
        # The artifact content is untouched (still exactly what the test wrote --
        # no commit, no mutation, no write to any surface including 'main').
        assert artifact.read_text(encoding="utf-8") == '{"event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV"}\n'


# ---------------------------------------------------------------------------
# FR-012: idempotent, structured result
# ---------------------------------------------------------------------------


class TestIdempotentReRun:
    def test_rerun_with_identical_inputs_is_a_no_op(self, tmp_path: Path) -> None:
        """First call commits; an identical re-run against the same already-
        committed artifact is a no-op (``"unchanged"``) -- inherited from
        ``commit_for_mission``'s own idempotence contract, projected through."""
        artifact = tmp_path / "acceptance-matrix.json"
        artifact.write_text("{}\n", encoding="utf-8")

        committed = CommitRouterResult(
            status="committed", placement_ref="main", commit_hash="abc1234"
        )
        unchanged = CommitRouterResult(status="unchanged", placement_ref="main")

        with (
            patch("specify_cli.coordination.write_seam.placement_seam") as seam_ctor,
            patch(
                "specify_cli.coordination.write_seam.commit_for_mission",
                side_effect=[committed, unchanged],
            ) as commit_mock,
        ):
            seam_ctor.return_value = MagicMock(
                write_target=MagicMock(return_value=CommitTarget(ref="main"))
            )

            first = write_artifact(
                repo_root=tmp_path,
                mission_slug=_MISSION_SLUG,
                kind=MissionArtifactKind.ACCEPTANCE_MATRIX,
                files=(artifact,),
                message="chore: record acceptance verdict",
                policy=_policy(),
                entry_id="FR-001",
            )
            second = write_artifact(
                repo_root=tmp_path,
                mission_slug=_MISSION_SLUG,
                kind=MissionArtifactKind.ACCEPTANCE_MATRIX,
                files=(artifact,),
                message="chore: record acceptance verdict",
                policy=_policy(),
                entry_id="FR-001",
            )

        assert commit_mock.call_count == 2
        assert first.status == "committed"
        assert first.commit_hash == "abc1234"
        assert second.status == "unchanged"
        assert second.commit_hash is None
        # The structured result names the SAME logical entry both times.
        assert first.entry_id == second.entry_id == "FR-001"
        assert first.destination_surface == second.destination_surface == "main"

    def test_unchanged_artifact_maps_status_verbatim_from_commit_router(
        self, tmp_path: Path
    ) -> None:
        """``commit_for_mission`` itself detects idempotence via the
        'nothing to commit' git signal (see test_commit_router.py); this
        helper must not re-derive or second-guess that -- it projects the
        status through unchanged."""
        artifact = tmp_path / "spec.md"
        artifact.write_text("# Spec\n", encoding="utf-8")

        exc = subprocess.CalledProcessError(1, ["git", "commit"])
        exc.stderr = "nothing to commit, working tree clean"

        with (
            patch("specify_cli.coordination.write_seam.placement_seam") as seam_ctor,
            patch(
                "specify_cli.coordination.write_seam.commit_for_mission",
                return_value=CommitRouterResult(status="unchanged", placement_ref="main"),
            ),
        ):
            seam_ctor.return_value = MagicMock(
                write_target=MagicMock(return_value=CommitTarget(ref="main"))
            )
            result = write_artifact(
                repo_root=tmp_path,
                mission_slug=_MISSION_SLUG,
                kind=MissionArtifactKind.SPEC,
                files=(artifact,),
                message="chore: planning artifacts",
                policy=_policy(),
                entry_id="spec",
            )

        assert result.status == "unchanged"


# ---------------------------------------------------------------------------
# Ledger-M16: recursion guard -- write boundary never calls read_dir
# ---------------------------------------------------------------------------


class TestRecursionGuardNeverReadsForAWrite:
    def test_write_boundary_resolves_via_write_target_never_read_dir(
        self, tmp_path: Path
    ) -> None:
        """The write boundary calls ``write_target`` (the write authority) and
        must never call ``read_dir`` (the read authority, which for
        ``RETROSPECTIVE`` routes to a wholly different resolver,
        ``resolve_retrospective_home``). Conflating the two at a write call
        site is exactly the Ledger-M16 defect shape."""
        artifact = tmp_path / "traces" / "trace.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("# Trace\n", encoding="utf-8")

        read_dir_mock = MagicMock(
            side_effect=AssertionError("read_dir must never be called from the write boundary")
        )

        with (
            patch("specify_cli.coordination.write_seam.placement_seam") as seam_ctor,
            patch(
                "specify_cli.coordination.write_seam.commit_for_mission",
                return_value=CommitRouterResult(status="committed", placement_ref="main", commit_hash="deadbee"),
            ),
        ):
            seam_ctor.return_value = MagicMock(
                write_target=MagicMock(return_value=CommitTarget(ref="main")),
                read_dir=read_dir_mock,
            )

            result = write_artifact(
                repo_root=tmp_path,
                mission_slug=_MISSION_SLUG,
                kind=MissionArtifactKind.TRACER_FILE,
                files=(artifact,),
                message="chore: append tracer entry",
                policy=_policy(),
                entry_id="trace-1",
            )

        read_dir_mock.assert_not_called()
        assert result.status == "committed"
        assert result.destination_surface == "main"
