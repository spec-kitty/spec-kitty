"""Red-first: ``WriteSeamResult`` carries ``surfaces``/``commit_hashes``/``reason`` (WP10, T053/T054).

Mission coord-artifact-single-home-01M3V4BE, WP10
(``contracts/commit-outcome.md``, FR-007 / SC-003). At base,
``write_seam.write_artifact`` drops ``CommitRouterResult.surfaces`` /
``commit_hashes`` / ``reason`` when projecting its own
:class:`~specify_cli.coordination.write_seam.WriteSeamResult` -- a caller
with a mixed-outcome batch (one surface committed, one refused) cannot see
the refusal through ``WriteSeamResult`` alone (it only sees the legacy
top-level ``status``, which the router's own caller-partition projection
picks from ONE of the groups). This pins the passthrough.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mission_runtime import CommitTarget, MissionArtifactKind
from specify_cli.coordination.commit_outcome import PathFate, SurfaceOutcome
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.coordination.write_seam import write_artifact

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_SLUG = "001-write-seam-surfaces-demo"


def _policy(*, protected: bool = False) -> object:
    class _Policy:
        def is_protected(self, ref: str) -> bool:  # noqa: ARG002 - fixed-answer stub
            return protected

    return _Policy()


def test_mixed_outcome_surfaces_pass_through_write_seam_result(tmp_path: Path) -> None:
    """One committed surface + one refused surface: both are visible on
    ``WriteSeamResult.surfaces`` -- not dropped, not collapsed into the
    legacy top-level ``status`` alone."""
    artifact = tmp_path / "issue-matrix.json"
    artifact.write_text("{}\n", encoding="utf-8")

    committed_surface = SurfaceOutcome(
        surface="primary",
        branch="topic",
        status="committed",
        commit_hash="abc1234",
        committed=("kitty-specs/demo/issue-matrix.json",),
    )
    refused_surface = SurfaceOutcome(
        surface="coordination",
        branch="kitty/mission-demo-01ABCDEF",
        status="refused",
        commit_hash=None,
        refused=(PathFate(path="kitty-specs/demo/status.events.jsonl", reason="STATUS_LOCK_HELD"),),
    )
    router_result = CommitRouterResult(
        status="committed",
        placement_ref="topic",
        commit_hash="abc1234",
        commit_hashes=(("topic", "abc1234"),),
        reason=None,
        surfaces=(committed_surface, refused_surface),
    )

    with (
        patch("specify_cli.coordination.write_seam.placement_seam") as seam_ctor,
        patch("specify_cli.coordination.write_seam.commit_for_mission", return_value=router_result) as commit_mock,
        patch("specify_cli.coordination.write_seam.assert_coord_write_materialized", return_value=None),
    ):
        seam_ctor.return_value = MagicMock(write_target=MagicMock(return_value=CommitTarget(ref="topic")))

        result = write_artifact(
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            kind=MissionArtifactKind.ISSUE_MATRIX,
            files=(artifact,),
            message="chore: update issue matrix",
            policy=_policy(),
            entry_id="finalize-scaffold",
        )

        commit_mock.assert_called_once()

    assert result.status == "committed"
    assert result.surfaces == (committed_surface, refused_surface)
    assert result.commit_hashes == (("topic", "abc1234"),)
    assert result.reason is None
    # The refusal is visible to a caller that inspects ``surfaces`` even
    # though the legacy top-level ``status`` alone reads "committed".
    refused = [surface for surface in result.surfaces if surface.status == "refused"]
    assert len(refused) == 1
    assert refused[0].refused[0].reason == "STATUS_LOCK_HELD"


def test_zero_write_refusal_carries_no_surfaces(tmp_path: Path) -> None:
    """The FR-011 zero-write refusal (no router call at all) leaves
    ``surfaces`` empty -- there is nothing to report per-surface because
    resolution never got far enough to call the router."""
    from mission_runtime import ActionContextError

    artifact = tmp_path / "phantom.md"

    with (
        patch("specify_cli.coordination.write_seam.placement_seam") as seam_ctor,
        patch(
            "specify_cli.coordination.write_seam.commit_for_mission",
            side_effect=AssertionError("commit_for_mission must not be called on refusal"),
        ),
    ):
        seam_ctor.return_value = MagicMock(write_target=MagicMock(side_effect=ActionContextError("FEATURE_CONTEXT_UNRESOLVED", "mission slug does not resolve")))

        result = write_artifact(
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            kind=MissionArtifactKind.ISSUE_MATRIX,
            files=(artifact,),
            message="chore: update issue matrix",
            policy=_policy(),
            entry_id="issue-42",
        )

    assert result.status == "refused"
    assert result.surfaces == ()
    assert result.commit_hashes == ()


# ---------------------------------------------------------------------------
# T054: ``_commit_post_consolidation_write`` synthesises ONE SurfaceOutcome
# for every one of its own outcome branches, so a post-consolidation
# (E2 CONSOLIDATED) write renders uniformly through the shared trio too.
# ---------------------------------------------------------------------------


def _target(ref: str = "main") -> CommitTarget:
    return CommitTarget(ref=ref)


class TestCommitPostConsolidationWriteSurfaces:
    def test_empty_files_is_unchanged_with_one_surface(self, tmp_path: Path) -> None:
        from specify_cli.coordination.write_seam import _commit_post_consolidation_write

        result = _commit_post_consolidation_write(
            repo_root=tmp_path,
            resolved=_target(),
            files=(),
            message="chore: noop",
            entry_id="e1",
        )

        assert result.status == "unchanged"
        assert result.surfaces == (SurfaceOutcome(surface="primary", branch="main", status="unchanged", commit_hash=None),)

    def test_missing_artifact_is_error_surface_not_wrong_surface_literal(self, tmp_path: Path) -> None:
        """``SurfaceOutcome.status`` has no ``no_op_wrong_surface`` member
        (contract vocabulary) -- this maps to ``"error"`` so the shared
        exit-code rule still flags it."""
        from specify_cli.coordination.write_seam import _commit_post_consolidation_write

        phantom = tmp_path / "never-created.md"

        result = _commit_post_consolidation_write(
            repo_root=tmp_path,
            resolved=_target(),
            files=(phantom,),
            message="chore: noop",
            entry_id="e1",
        )

        assert result.status == "no_op_wrong_surface"
        assert len(result.surfaces) == 1
        surface = result.surfaces[0]
        assert surface.status == "error"
        assert surface.diagnostic is not None
        assert "not present at resolved CONSOLIDATED placement" in surface.diagnostic

    def test_empty_changeset_runtime_error_is_unchanged_with_one_surface(self, tmp_path: Path) -> None:
        from specify_cli.coordination.write_seam import _EMPTY_CHANGESET_PREFIX, _commit_post_consolidation_write

        artifact = tmp_path / "tasks.md"
        artifact.write_text("content\n", encoding="utf-8")

        with patch(
            "specify_cli.git.safe_commit",
            side_effect=RuntimeError(f"{_EMPTY_CHANGESET_PREFIX}: nothing to commit"),
        ):
            result = _commit_post_consolidation_write(
                repo_root=tmp_path,
                resolved=_target(),
                files=(artifact,),
                message="chore: noop",
                entry_id="e1",
            )

        assert result.status == "unchanged"
        assert result.surfaces == (SurfaceOutcome(surface="primary", branch="main", status="unchanged", commit_hash=None),)

    def test_unexpected_runtime_error_is_an_error_surface(self, tmp_path: Path) -> None:
        from specify_cli.coordination.write_seam import _commit_post_consolidation_write

        artifact = tmp_path / "tasks.md"
        artifact.write_text("content\n", encoding="utf-8")

        with patch(
            "specify_cli.git.safe_commit",
            side_effect=RuntimeError("git blew up"),
        ):
            result = _commit_post_consolidation_write(
                repo_root=tmp_path,
                resolved=_target(),
                files=(artifact,),
                message="chore: noop",
                entry_id="e1",
            )

        assert result.status == "error"
        assert result.diagnostic == "git blew up"
        assert result.surfaces == (SurfaceOutcome(surface="primary", branch="main", status="error", commit_hash=None, diagnostic="git blew up"),)

    def test_successful_commit_carries_committed_paths_and_commit_hashes(self, tmp_path: Path) -> None:
        from specify_cli.git.commit_helpers import CommitResult
        from specify_cli.coordination.write_seam import _commit_post_consolidation_write

        artifact = tmp_path / "tasks.md"
        artifact.write_text("content\n", encoding="utf-8")
        commit_result = CommitResult(sha="deadbeef", destination_ref="main", worktree_root=tmp_path)

        with patch("specify_cli.git.safe_commit", return_value=commit_result):
            result = _commit_post_consolidation_write(
                repo_root=tmp_path,
                resolved=_target(),
                files=(artifact,),
                message="chore: noop",
                entry_id="e1",
            )

        assert result.status == "committed"
        assert result.commit_hash == "deadbeef"
        assert result.commit_hashes == (("main", "deadbeef"),)
        assert len(result.surfaces) == 1
        surface = result.surfaces[0]
        assert surface.status == "committed"
        assert surface.commit_hash == "deadbeef"
        assert surface.committed == ("tasks.md",)
