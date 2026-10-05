"""Seam unit tests for ``coordination/planning_commit`` (implement-degod WP04).

The module holds the pure planning-artifact commit decisions moved out of the ``implement``
command: the PRIMARY/coord partition and its guard, the ``meta.json`` demotion verdict, the
bookkeeping identifier cascade and the planning-artifact path helpers. Nothing here prints or
exits, so every case is driven directly, with a tiny real git repo only where the verdict reads
``HEAD``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination import planning_commit
from specify_cli.coordination.commit_router import PrimaryKindReachedCoordStagingError
from specify_cli.git.commit_helpers import SafeCommitPathPolicyError

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "seam-mission"
_META_REL = f"kitty-specs/{_SLUG}/meta.json"
_COORD_BRANCH = "kitty/mission-seam-mission-01KSEAMA"
_DECLARING_META: dict[str, object] = {"mission_slug": _SLUG, "coordination_branch": _COORD_BRANCH, "mission_id": "01KSEAMAAAAAAAAAAAAAAAAAAA"}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "work")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _write_meta(repo: Path, payload: dict[str, object] | str) -> Path:
    meta_path = repo / _META_REL
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    return meta_path


def _commit_all(repo: Path) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")


class TestPartition:
    def test_coord_residue_goes_to_the_coord_group_and_everything_else_to_primary(self) -> None:
        primary, coord = planning_commit.partition_files_for_commit(
            [
                f"kitty-specs/{_SLUG}/status.events.jsonl",
                f"kitty-specs/{_SLUG}/lanes.json",
                f"kitty-specs/{_SLUG}/tasks/WP01.md",
                "unclassified.txt",
            ]
        )

        assert coord == [f"kitty-specs/{_SLUG}/status.events.jsonl"]
        assert primary == [f"kitty-specs/{_SLUG}/lanes.json", f"kitty-specs/{_SLUG}/tasks/WP01.md", "unclassified.txt"]

    def test_meta_json_defaults_to_primary(self) -> None:
        primary, coord = planning_commit.partition_files_for_commit([_META_REL])

        assert (primary, coord) == ([_META_REL], [])

    def test_empty_batch_yields_two_empty_groups(self) -> None:
        assert planning_commit.partition_files_for_commit([]) == ([], [])


class TestGuard:
    def test_primary_kind_under_a_coord_destination_raises_with_the_primary_text(self) -> None:
        with pytest.raises(PrimaryKindReachedCoordStagingError) as caught:
            planning_commit.guard_planning_commit_partition([f"kitty-specs/{_SLUG}/lanes.json"], destination_is_coord=True)

        assert str(caught.value) == (
            f"PRIMARY-partition planning artifact 'kitty-specs/{_SLUG}/lanes.json' reached the "
            "coordination-branch commit seam; PRIMARY kinds must commit to the primary target "
            "branch and never transit the coordination branch (write-path-integrity FR-002)."
        )

    def test_coord_kind_under_a_primary_destination_raises_with_the_coord_text(self) -> None:
        with pytest.raises(PrimaryKindReachedCoordStagingError) as caught:
            planning_commit.guard_planning_commit_partition([f"kitty-specs/{_SLUG}/status.json"], destination_is_coord=False)

        assert str(caught.value) == (
            f"COORD-partition artifact 'kitty-specs/{_SLUG}/status.json' reached a PRIMARY/lane commit "
            "seam; coordination-partition kinds must commit to the coordination branch, never a primary "
            "or lane branch (write-path-integrity FR-002/#2549)."
        )

    @pytest.mark.parametrize("destination_is_coord", [True, False])
    def test_self_bookkeeping_is_exempt_in_both_directions(self, destination_is_coord: bool) -> None:
        planning_commit.guard_planning_commit_partition([_META_REL], destination_is_coord=destination_is_coord)

    def test_matching_partitions_pass(self) -> None:
        planning_commit.guard_planning_commit_partition([f"kitty-specs/{_SLUG}/status.json"], destination_is_coord=True)
        planning_commit.guard_planning_commit_partition([f"kitty-specs/{_SLUG}/lanes.json"], destination_is_coord=False)


class TestDemotionVerdict:
    def test_no_baseline_allows(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        meta_path = _write_meta(tmp_path, {"mission_slug": _SLUG})

        assert planning_commit.meta_json_demotion_refusal(tmp_path, _SLUG, meta_path, _META_REL) is None

    def test_dropping_the_coordination_branch_is_refused_with_the_exact_message(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        meta_path = _write_meta(tmp_path, {"mission_slug": _SLUG, "coordination_branch": _COORD_BRANCH})
        _commit_all(tmp_path)
        _write_meta(tmp_path, {"mission_slug": _SLUG})

        refusal = planning_commit.meta_json_demotion_refusal(tmp_path, _SLUG, meta_path, _META_REL)

        assert refusal == planning_commit.DEMOTION_REFUSAL_MSG.format(rel_path=_META_REL, mission_slug=_SLUG, coordination_branch=_COORD_BRANCH)
        assert refusal is not None and f"silently demotes {_SLUG} off its coordination branch ('{_COORD_BRANCH}' -> absent)" in refusal

    def test_keeping_the_coordination_branch_allows(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        meta_path = _write_meta(tmp_path, {"mission_slug": _SLUG, "coordination_branch": _COORD_BRANCH})
        _commit_all(tmp_path)
        _write_meta(tmp_path, {"mission_slug": _SLUG, "coordination_branch": _COORD_BRANCH, "note": "edited"})

        assert planning_commit.meta_json_demotion_refusal(tmp_path, _SLUG, meta_path, _META_REL) is None

    def test_corrupt_head_baseline_is_refused_as_corrupt(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        meta_path = _write_meta(tmp_path, "{not json")
        _commit_all(tmp_path)
        _write_meta(tmp_path, {"mission_slug": _SLUG})

        refusal = planning_commit.meta_json_demotion_refusal(tmp_path, _SLUG, meta_path, _META_REL)

        assert refusal == planning_commit.DEMOTION_CORRUPT_MSG.format(rel_path=_META_REL, side="HEAD")

    def test_corrupt_working_copy_is_refused_as_corrupt(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        meta_path = _write_meta(tmp_path, {"mission_slug": _SLUG, "coordination_branch": _COORD_BRANCH})
        _commit_all(tmp_path)
        _write_meta(tmp_path, "{not json")

        refusal = planning_commit.meta_json_demotion_refusal(tmp_path, _SLUG, meta_path, _META_REL)

        assert refusal == planning_commit.DEMOTION_CORRUPT_MSG.format(rel_path=_META_REL, side="working copy")

    def test_unreadable_working_copy_is_refused_as_corrupt(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        meta_path = _write_meta(tmp_path, {"mission_slug": _SLUG, "coordination_branch": _COORD_BRANCH})
        _commit_all(tmp_path)
        meta_path.unlink()

        refusal = planning_commit.meta_json_demotion_refusal(tmp_path, _SLUG, meta_path, _META_REL)

        assert refusal == planning_commit.DEMOTION_CORRUPT_MSG.format(rel_path=_META_REL, side="working copy")

    def test_repo_relative_meta_path_resolves_under_the_repo_and_none_outside(self, tmp_path: Path) -> None:
        inside = tmp_path / "kitty-specs" / _SLUG
        outside = tmp_path.parent / "elsewhere"

        assert planning_commit.meta_json_repo_relative_path(tmp_path, inside) == _META_REL
        assert planning_commit.meta_json_repo_relative_path(tmp_path, outside) is None


class TestIdentifierCascade:
    def test_primary_meta_is_read_first_and_a_declared_mid8_wins(self, tmp_path: Path) -> None:
        primary = tmp_path / "kitty-specs" / _SLUG
        primary.mkdir(parents=True)
        (primary / "meta.json").write_text(
            json.dumps({"mission_slug": _SLUG, "coordination_branch": _COORD_BRANCH, "mission_id": "01KSEAMAAAAAAAAAAAAAAAAAAA", "mid8": "CUSTOM99"}),
            encoding="utf-8",
        )
        coord_dir = tmp_path / ".worktrees" / f"{_SLUG}-coord" / "kitty-specs" / _SLUG
        coord_dir.mkdir(parents=True)
        (coord_dir / "meta.json").write_text(json.dumps({"mission_slug": _SLUG, "mission_id": "01KWRONGWRONGWRONGWRONGWRO"}), encoding="utf-8")

        ids = planning_commit.resolve_bookkeeping_transaction_identifiers(coord_dir, _SLUG, tmp_path)

        assert ids == (_COORD_BRANCH, "01KSEAMAAAAAAAAAAAAAAAAAAA", "CUSTOM99", "01KSEAMAAAAAAAAAAAAAAAAAAA", "CUSTOM99")
        assert isinstance(ids, planning_commit.BookkeepingTransactionIdentifiers)

    def test_fallback_meta_is_used_when_the_primary_has_none(self, tmp_path: Path) -> None:
        fallback = tmp_path / ".worktrees" / f"{_SLUG}-coord" / "kitty-specs" / _SLUG
        fallback.mkdir(parents=True)
        (fallback / "meta.json").write_text(
            json.dumps({"mission_slug": _SLUG, "coordination_branch": _COORD_BRANCH, "mission_id": "01KFALLBACKAAAAAAAAAAAAAAA", "mid8": "01KFALLB"}),
            encoding="utf-8",
        )

        ids = planning_commit.resolve_bookkeeping_transaction_identifiers(fallback, _SLUG, tmp_path)

        assert ids.coord_branch == _COORD_BRANCH
        assert ids.mission_id == "01KFALLBACKAAAAAAAAAAAAAAA"

    def test_missing_meta_everywhere_yields_the_legacy_slug_identity(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / _SLUG
        feature_dir.mkdir(parents=True)

        ids = planning_commit.resolve_bookkeeping_transaction_identifiers(feature_dir, _SLUG, tmp_path)

        assert (ids.coord_branch, ids.mission_id, ids.mid8) == (None, None, None)
        assert ids.effective_mission_id == f"legacy-{_SLUG}"

    def test_without_a_repo_root_only_the_feature_dir_is_read(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / _SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": _SLUG, "mission_id": "01KNOROOTAAAAAAAAAAAAAAAAA"}), encoding="utf-8")

        assert planning_commit.load_primary_anchored_mission_meta(None, _SLUG) is None
        assert planning_commit.resolve_bookkeeping_transaction_identifiers(feature_dir, _SLUG).mission_id == "01KNOROOTAAAAAAAAAAAAAAAAA"

    def test_a_non_dict_meta_yields_no_identifiers(self) -> None:
        assert planning_commit.extract_mission_identifiers_from_meta(None, _SLUG) == (None, None, None)


class TestCandidateEnumeration:
    def test_lists_every_file_repo_relative_and_sorted(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / _SLUG
        (feature_dir / "tasks").mkdir(parents=True)
        (feature_dir / "tasks" / "WP01.md").write_text("x", encoding="utf-8")
        (feature_dir / "spec.md").write_text("x", encoding="utf-8")

        assert planning_commit.feature_dir_file_paths(tmp_path, feature_dir) == [
            f"kitty-specs/{_SLUG}/spec.md",
            f"kitty-specs/{_SLUG}/tasks/WP01.md",
        ]

    def test_a_feature_dir_under_worktrees_raises_the_path_policy_error(self, tmp_path: Path) -> None:
        coord_dir = tmp_path / ".worktrees" / f"{_SLUG}-coord" / "kitty-specs" / _SLUG
        coord_dir.mkdir(parents=True)
        (coord_dir / "spec.md").write_text("x", encoding="utf-8")

        with pytest.raises(SafeCommitPathPolicyError):
            planning_commit.feature_dir_file_paths(tmp_path, coord_dir)

    def test_a_directory_outside_the_repo_is_returned_unchanged_by_the_source_dir_helper(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside-dir"

        assert planning_commit.planning_artifact_source_dir(tmp_path, outside, _SLUG) == outside

    def test_a_worktree_feature_dir_resolves_to_the_primary_dir_when_it_exists(self, tmp_path: Path) -> None:
        primary = tmp_path / "kitty-specs" / _SLUG
        primary.mkdir(parents=True)
        (primary / "meta.json").write_text(json.dumps({"mission_slug": _SLUG}), encoding="utf-8")
        coord_dir = tmp_path / ".worktrees" / f"{_SLUG}-coord" / "kitty-specs" / _SLUG
        coord_dir.mkdir(parents=True)

        assert planning_commit.planning_artifact_source_dir(tmp_path, coord_dir, _SLUG) == primary


class TestPlacementResolutionRemedy:
    """FR-018: the one ``PlacementResolutionRequired`` remedy text
    (moved here from ``implement_cores._resolve_claim_commit_target``, deleted in #5232)."""

    def test_remedy_is_structured_and_names_the_real_command(self) -> None:
        from specify_cli.core.errors import PlacementResolutionRequired

        error = PlacementResolutionRequired(planning_commit.placement_resolution_remedy("demo-mission"))

        assert error.error_code == "PLACEMENT_RESOLUTION_REQUIRED"
        # #5113 / FR-014: names the real materializing/flattening command
        # with the real slug, never the retired `doctor workspaces --fix`.
        assert "doctor coordination --mission demo-mission --fix" in str(error)
        assert "doctor workspaces" not in str(error)


class TestPlanningPlacement:
    def test_ref_is_set_exactly_when_resolved(self) -> None:
        from mission_runtime import CommitTarget

        target = CommitTarget(ref="kitty/mission-demo-AAAA1111")
        assert planning_commit.PlanningPlacement(resolved=True, ref=target).ref is target
        assert planning_commit.PlanningPlacement(resolved=False, ref=None).ref is None
        with pytest.raises(ValueError, match="set exactly when the placement is resolved"):
            planning_commit.PlanningPlacement(resolved=True, ref=None)
        with pytest.raises(ValueError, match="set exactly when the placement is resolved"):
            planning_commit.PlanningPlacement(resolved=False, ref=target)


class TestPlacementCoordFilter:
    """Moved with ``placement_coord_filter`` from ``implement_cores._placement_coord_filter`` (#5232)."""

    def test_none_placement_ref_returns_none(self, tmp_path: Path) -> None:
        assert planning_commit.placement_coord_filter(tmp_path, "m", None) is None

    def test_coord_topology_returns_placement_ref(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from mission_runtime import CommitTarget, MissionTopology

        monkeypatch.setattr(planning_commit, "resolve_topology", lambda _root, _slug: MissionTopology.COORD)
        target = CommitTarget(ref="kitty/mission-m-AAAA1111")
        assert planning_commit.placement_coord_filter(tmp_path, "m", target) == "kitty/mission-m-AAAA1111"

    def test_flattened_topology_returns_none(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from mission_runtime import CommitTarget, MissionTopology

        monkeypatch.setattr(planning_commit, "resolve_topology", lambda _root, _slug: MissionTopology.SINGLE_BRANCH)
        target = CommitTarget(ref="main")
        assert planning_commit.placement_coord_filter(tmp_path, "m", target) is None


def _write_primary_meta(repo_root: Path, payload: dict[str, object]) -> Path:
    feature_dir = repo_root / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps(payload), encoding="utf-8")
    return feature_dir


class TestDeclaredCoordinationRef:
    """R-1b (B2**): the unresolved degrade is the declared coordination branch, read through the
    identity cascade, with no topology gate and no existence probe."""

    def test_declared_branch_is_returned_without_a_topology_gate(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from mission_runtime import MissionTopology

        monkeypatch.setattr(planning_commit, "resolve_topology", lambda _root, _slug: MissionTopology.LANES)
        feature_dir = _write_primary_meta(tmp_path, _DECLARING_META)

        assert planning_commit.declared_coordination_ref(feature_dir, _SLUG, tmp_path) == _COORD_BRANCH

    def test_undeclared_branch_gives_none(self, tmp_path: Path) -> None:
        feature_dir = _write_primary_meta(tmp_path, {"mission_slug": _SLUG, "mission_id": "01X"})

        assert planning_commit.declared_coordination_ref(feature_dir, _SLUG, tmp_path) is None

    def test_feature_dir_fallback_is_read_when_the_primary_has_no_meta(self, tmp_path: Path) -> None:
        fallback = tmp_path / ".worktrees" / f"{_SLUG}-coord" / "kitty-specs" / _SLUG
        fallback.mkdir(parents=True)
        (fallback / "meta.json").write_text(json.dumps(_DECLARING_META), encoding="utf-8")

        assert planning_commit.declared_coordination_ref(fallback, _SLUG, tmp_path) == _COORD_BRANCH


class TestCoordinationFilter:
    def test_resolved_placement_filters_through_the_topology(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from mission_runtime import CommitTarget, MissionTopology

        monkeypatch.setattr(planning_commit, "resolve_topology", lambda _root, _slug: MissionTopology.COORD)
        placement = planning_commit.PlanningPlacement(resolved=True, ref=CommitTarget(ref="kitty/mission-m-AAAA1111"))

        assert planning_commit.coordination_filter(tmp_path, "m", placement, feature_dir=tmp_path) == "kitty/mission-m-AAAA1111"

    def test_resolved_placement_on_a_flattened_topology_has_no_filter(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from mission_runtime import CommitTarget, MissionTopology

        monkeypatch.setattr(planning_commit, "resolve_topology", lambda _root, _slug: MissionTopology.SINGLE_BRANCH)
        placement = planning_commit.PlanningPlacement(resolved=True, ref=CommitTarget(ref="main"))

        assert planning_commit.coordination_filter(tmp_path, "m", placement, feature_dir=tmp_path) is None

    def test_unresolved_placement_filters_on_the_declared_branch(self, tmp_path: Path) -> None:
        feature_dir = _write_primary_meta(tmp_path, _DECLARING_META)
        placement = planning_commit.PlanningPlacement(resolved=False, ref=None)

        assert planning_commit.coordination_filter(tmp_path, _SLUG, placement, feature_dir=feature_dir) == _COORD_BRANCH
