"""WP03 (coord-write-placement-closure-01KYCF83) — residual writer routing.

FR-003 / FR-006 / SC-006: ``bookkeeping_projection``, ``bookkeeping_commit``,
and ``decision_log`` must derive their commit/target destinations through the
placement port (``kind_for_mission_file`` -> ``resolve_placement_only`` /
``placement_seam``) instead of an ambient ``feature_dir``/``branch``/HEAD
value. The squad's CAUTION: two of these writers were ALREADY seam-adopted in
*shape* (``target=CommitTarget(...)`` / an injected ``target``) before this
WP — the real delta is that the ambient value feeding that shape is now
REPLACED by a classifier-derived one. Each test below is red-for-the-right-
reason against the PRE-WP03 code: it asserts on the CLASSIFIED destination
while feeding a deliberately WRONG ambient value, so a writer that still
trusts the ambient value (the pre-fix behaviour) fails the assertion.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mission_runtime import CommitTarget, MissionArtifactKind
from runtime.next._internal_runtime.events import NullEmitter
from specify_cli.events.decision_log import DecisionGitLog
from specify_cli.git.bookkeeping_commit import commit_merge_bookkeeping
from specify_cli.consolidation import bookkeeping_projection as bp

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# Production-shaped identifiers (DIRECTIVE_041): a real ULID mission_id and a
# realistic mission slug, never a placeholder like "m"/"foo".
_MISSION_ID = "01KTDVHZKGCHCW6HQ4V577PNES"
_MID8 = _MISSION_ID[:8]
_SLUG = "coord-residual-writer-routing-01KTDVHZ"
_COORD_BRANCH = f"kitty/mission-{_SLUG}-{_MID8}"
_TARGET_BRANCH = "release/3.2.6"


def _write_meta(repo_root: Path, *, coordination_branch: str | None, target_branch: str) -> Path:
    """Write a coord-topology ``meta.json`` for ``_SLUG`` under ``repo_root``."""
    mission_dir = repo_root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mission_slug": _SLUG,
        "target_branch": target_branch,
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return mission_dir


# ---------------------------------------------------------------------------
# T012 — decision_log.py: DECISION_LOG must land COORD via the classifier,
# ignoring a wrong ambient ``destination_ref``.
# ---------------------------------------------------------------------------


class TestDecisionLogRoutesThroughPlacementPort:
    """A DecisionGitLog built WITHOUT an injected ``target`` must derive its
    default destination from the classifier (DECISION_LOG -> COORD), not from
    whatever ``destination_ref`` string the (legacy/ambient) caller supplied.
    """

    def test_default_target_is_classifier_derived_not_ambient_destination_ref(
        self, tmp_path: Path
    ) -> None:
        _write_meta(tmp_path, coordination_branch=_COORD_BRANCH, target_branch=_TARGET_BRANCH)

        # Deliberately WRONG ambient value: a legacy caller that computed some
        # other ref (e.g. a stale/target branch) instead of consulting the
        # classifier. Pre-fix, ``self._target`` trusted this verbatim.
        wrong_ambient_ref = "stale-ambient-branch-not-coord"

        log = DecisionGitLog(
            repo_root=tmp_path,
            worktree_root=tmp_path,
            destination_ref=wrong_ambient_ref,
            mission_slug=_SLUG,
            inner=NullEmitter(),
        )

        assert log._target.ref == _COORD_BRANCH, (
            "DecisionGitLog's default target must be the classifier-derived "
            f"COORD branch ({_COORD_BRANCH!r}), not the ambient destination_ref "
            f"({wrong_ambient_ref!r}) — got {log._target.ref!r}"
        )

    def test_injected_target_still_wins_over_classifier(self, tmp_path: Path) -> None:
        """An explicitly injected ``target`` (the modern runtime_bridge path)
        is never overridden by the classifier — only the DEFAULT changes."""
        _write_meta(tmp_path, coordination_branch=_COORD_BRANCH, target_branch=_TARGET_BRANCH)
        injected = CommitTarget(ref="some-other-explicit-ref")

        log = DecisionGitLog(
            repo_root=tmp_path,
            worktree_root=tmp_path,
            destination_ref=_COORD_BRANCH,
            mission_slug=_SLUG,
            inner=NullEmitter(),
            target=injected,
        )

        assert log._target is injected

    def test_unresolvable_mission_degrades_to_ambient_destination_ref(
        self, tmp_path: Path
    ) -> None:
        """No meta.json at all (bootstrap window / ad-hoc fixture) -> the
        classifier cannot resolve, so the ambient destination_ref is used —
        the degrade-path, not a hard failure."""
        ambient_ref = "kitty/mission-bootstrap-window"

        log = DecisionGitLog(
            repo_root=tmp_path,
            worktree_root=tmp_path,
            destination_ref=ambient_ref,
            mission_slug=_SLUG,
            inner=NullEmitter(),
        )

        assert log._target.ref == ambient_ref


# ---------------------------------------------------------------------------
# T011 — bookkeeping_commit.py: the commit target is classifier-derived,
# ignoring a wrong ambient ``branch``.
# ---------------------------------------------------------------------------


class TestBookkeepingCommitRoutesThroughPlacementPort:
    def test_target_is_classifier_derived_not_ambient_branch(self, tmp_path: Path) -> None:
        _write_meta(tmp_path, coordination_branch=None, target_branch=_TARGET_BRANCH)

        # Deliberately WRONG ambient value the pre-fix code trusted verbatim
        # (``target=CommitTarget(ref=branch)`` — the CAUTION's "real delta").
        wrong_ambient_branch = "wrong-ambient-branch-not-target"

        captured: dict[str, object] = {}

        def _fake_safe_commit(**kwargs: object) -> None:
            captured.update(kwargs)

        with patch("specify_cli.git.bookkeeping_commit.safe_commit", side_effect=_fake_safe_commit):
            commit_merge_bookkeeping(
                repo_root=tmp_path,
                worktree_root=tmp_path,
                mission_slug=_SLUG,
                branch=wrong_ambient_branch,
                message="chore: bookkeeping",
                paths=(tmp_path / "kitty-specs" / _SLUG / "status.events.jsonl",),
            )

        target = captured["target"]
        assert isinstance(target, CommitTarget)
        assert target.ref == _TARGET_BRANCH, (
            "commit_merge_bookkeeping must derive its target through the "
            f"placement port ({_TARGET_BRANCH!r}), not the ambient branch "
            f"argument ({wrong_ambient_branch!r}) — got {target.ref!r}"
        )

    def test_unresolvable_mission_degrades_to_ambient_branch(self, tmp_path: Path) -> None:
        """No meta.json (bootstrap window) -> degrades to the caller-supplied
        ``branch`` fallback rather than raising."""
        ambient_branch = "kitty/mission-bootstrap-window"
        captured: dict[str, object] = {}

        def _fake_safe_commit(**kwargs: object) -> None:
            captured.update(kwargs)

        with patch("specify_cli.git.bookkeeping_commit.safe_commit", side_effect=_fake_safe_commit):
            commit_merge_bookkeeping(
                repo_root=tmp_path,
                worktree_root=tmp_path,
                mission_slug=_SLUG,
                branch=ambient_branch,
                message="chore: bookkeeping",
                paths=(tmp_path / "kitty-specs" / _SLUG / "status.events.jsonl",),
            )

        target = captured["target"]
        assert isinstance(target, CommitTarget)
        assert target.ref == ambient_branch

    def test_unresolvable_mission_with_no_branch_fallback_raises(self, tmp_path: Path) -> None:
        """No meta.json AND no ``branch`` degrade path -> the resolution error
        propagates instead of silently landing nowhere."""
        from mission_runtime import ActionContextError

        with pytest.raises(ActionContextError):
            commit_merge_bookkeeping(
                repo_root=tmp_path,
                worktree_root=tmp_path,
                mission_slug=_SLUG,
                message="chore: bookkeeping",
                paths=(tmp_path / "kitty-specs" / _SLUG / "status.events.jsonl",),
            )


# ---------------------------------------------------------------------------
# T010 — bookkeeping_projection.py: the target-checkout directory is derived
# through the placement port, not a direct ``primary_feature_dir_for_mission``
# composition.
# ---------------------------------------------------------------------------


class TestBookkeepingProjectionRoutesThroughPlacementPort:
    def test_target_dir_is_placement_seam_derived(self, tmp_path: Path) -> None:
        """The target-checkout directory the projection stages onto must come
        from ``placement_seam(...).read_dir(...)`` — patching the seam to
        return a SENTINEL directory must be observable in the result. Under
        the pre-fix code (a direct ``primary_feature_dir_for_mission`` call,
        no ``placement_seam`` reference at all) this patch target does not
        exist on the module and/or the sentinel never surfaces."""
        primary_dir = _write_meta(tmp_path, coordination_branch=None, target_branch=_TARGET_BRANCH)
        coord_specs = tmp_path / ".worktrees" / f"{_SLUG}-{_MID8}-coord" / "kitty-specs" / _SLUG
        coord_specs.mkdir(parents=True)

        sentinel_dir = tmp_path / "sentinel-primary-dir"
        sentinel_dir.mkdir()

        class _FakeSeam:
            def read_dir(self, kind: MissionArtifactKind) -> Path:
                assert kind is MissionArtifactKind.PRIMARY_METADATA
                return sentinel_dir

        with patch.object(bp, "placement_seam", return_value=_FakeSeam()) as mock_seam:
            events_path, status_path = bp._target_bookkeeping_status_paths(
                main_repo=tmp_path,
                mission_slug=_SLUG,
                status_feature_dir=coord_specs,
            )

        mock_seam.assert_called_once()
        assert events_path.parent == sentinel_dir, (
            "the target directory must be derived via placement_seam(...).read_dir(...) "
            f"— expected it under {sentinel_dir}, got {events_path.parent}"
        )
        assert status_path.parent == sentinel_dir
        # Sanity: the un-patched seam resolves back to the real primary dir.
        real_events_path, _ = bp._target_bookkeeping_status_paths(
            main_repo=tmp_path, mission_slug=_SLUG, status_feature_dir=coord_specs
        )
        assert real_events_path.parent == primary_dir.resolve()

    def test_filename_trust_check_is_classifier_derived(self) -> None:
        """The bookkeeping-filename trust check must call the SSOT classifier
        (``kind_for_mission_file``) rather than a hand-maintained literal set —
        patching the classifier to reject a normally-trusted filename must
        flip the trust decision."""
        assert bp._classify_status_bookkeeping_filename("status.events.jsonl") is (
            MissionArtifactKind.STATUS_STATE
        )
        assert bp._classify_status_bookkeeping_filename("status.json") is (
            MissionArtifactKind.STATUS_STATE
        )
        assert bp._classify_status_bookkeeping_filename("evil.txt") is None

        with (
            patch.object(bp, "kind_for_mission_file", return_value=None) as mock_classify,
            pytest.raises(ValueError, match="Refusing untrusted status filename"),
        ):
            bp._assert_status_surface_file_path_is_trusted(
                # Non-shared-temp absolute sentinels (tmp-literal burndown category B):
                # the call raises on the (patched-untrusted) filename before either
                # path is ever read, so the dirs are incidental placeholders.
                repo_root=Path("/sentinel/does-not-matter"),
                status_feature_dir=Path("/sentinel/does-not-matter/kitty-specs/x"),
                filename="status.events.jsonl",
            )
        mock_classify.assert_called_once()
