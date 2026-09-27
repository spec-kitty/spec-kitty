"""Per-site regression tests for FR-008 match sites: guards against these
sites regressing off the naming authority's parsers and back onto a
hand-rolled recognition regex.

Covers the sites routed through the naming authority's parsers:

* ``git/sparse_checkout.py`` (``_ManagedLanePolicy.matches_path`` /
  ``expected_branch_for``);
* ``status/doctor.py::check_orphan_workspaces``;
* ``live_work/bindings.py::_resolve_mission_from_worktree`` (via
  ``resolve_bindings``);
* ``policy/commit_guard.py::is_implementation_branch``;
* ``merge/resolve.py::_extract_mission_slug``.

No mocks for the recognition logic itself; real tmp directories and git where
a site needs git (Test Strategy).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from kernel.clock import now_utc_iso
from specify_cli.git.sparse_checkout import _ManagedLanePolicy
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.live_work.bindings import _resolve_mission_from_worktree
from specify_cli.merge.resolve import _extract_mission_slug
from specify_cli.policy.commit_guard import is_implementation_branch
from specify_cli.status.doctor import check_orphan_workspaces


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def _make_manifest(mission_slug: str, mission_id: str, mission_branch: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mission_branch=mission_branch,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=(),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=now_utc_iso(),
        computed_from="test",
    )


# ---------------------------------------------------------------------------
# git/sparse_checkout.py::_ManagedLanePolicy
# ---------------------------------------------------------------------------


class TestManagedLanePolicy:
    def test_expected_branch_for_nnn_coordination_mission_matches_created_lane(self, tmp_path: Path) -> None:
        """Guards against a hand-rolled ``f"{coordination_branch}-{lane_id}"``
        compose diverging from the branch ``allocate_lane_worktree`` actually
        creates for an ``NNN-`` coordination mission whose stored
        ``coordination_branch`` embeds a mid8 the lane branch never gets
        (the naming authority is the single hand-rolled compose).
        """
        repo = _init_repo(tmp_path)
        mission_slug = "060-test"  # NNN- prefix retained, no embedded mid8
        mission_id = "01J6XW9KABCDEFGHJKMNPQRSTV"
        # Historical divergent coordination_branch shape: retains NNN- AND
        # appends the mid8 -- exactly the shape that does not match what the
        # allocator actually names the lane branch.
        coordination_branch = f"kitty/mission-{mission_slug}-01J6XW9K"

        spec_dir = repo / "kitty-specs" / mission_slug
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec.md").write_text("# spec\n")
        (spec_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": mission_id,
                    "mission_slug": mission_slug,
                    "coordination_branch": coordination_branch,
                }
            )
        )
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "seed mission")
        _git(repo, "branch", coordination_branch)

        manifest = _make_manifest(mission_slug, mission_id, coordination_branch)
        worktree_path, real_branch = allocate_lane_worktree(repo_root=repo, mission_slug=mission_slug, wp_id="WP01", lanes_manifest=manifest)

        policy = _ManagedLanePolicy(mission_slug=mission_slug, expected_patterns=frozenset())
        assert policy.expected_branch_for(worktree_path) == real_branch

        # Evidence that the OLD hand-rolled compose diverged (the bug this
        # subtask fixes): f"{coordination_branch}-{lane_id}" != the real branch.
        old_hand_rolled = f"{coordination_branch}-lane-a"
        assert old_hand_rolled != real_branch

    def test_matches_path_rejects_slug_embedded_in_larger_slug(self) -> None:
        """Guards against a ``startswith(f"{slug}-lane-")`` check false-
        positives when a DIFFERENT, longer mission's own slug embeds
        ``-lane-`` (e.g. ``057-foo-lane-mgmt``), because its lane worktree dir
        (``057-foo-lane-mgmt-lane-a``) happens to start with
        ``057-foo-lane-``. Recognition by recomposition rejects it.
        """
        policy = _ManagedLanePolicy(mission_slug="057-foo", expected_patterns=frozenset())
        assert policy.matches_path(Path("057-foo-lane-mgmt-lane-a")) is False

    def test_matches_path_rejects_same_prefix_impostor(self) -> None:
        """Regression guard: a `057-foobar` dir must never match slug `057-foo`."""
        policy = _ManagedLanePolicy(mission_slug="057-foo", expected_patterns=frozenset())
        assert policy.matches_path(Path("057-foobar-lane-a")) is False

    def test_matches_path_and_expected_branch_for_own_lane(self) -> None:
        """Regression guard: a mission's own lane dir is recognized and its
        branch composed correctly (mid8-in-slug, byte-identical to today)."""
        policy = _ManagedLanePolicy(mission_slug="foo-01KV6510", expected_patterns=frozenset())
        path = Path("foo-01KV6510-lane-a")
        assert policy.matches_path(path) is True
        assert policy.expected_branch_for(path) == "kitty/mission-foo-01KV6510-lane-a"

    def test_expected_branch_for_returns_none_for_non_matching_path(self) -> None:
        policy = _ManagedLanePolicy(mission_slug="057-foo", expected_patterns=frozenset())
        assert policy.expected_branch_for(Path("unrelated-dir")) is None


# ---------------------------------------------------------------------------
# status/doctor.py::check_orphan_workspaces
# ---------------------------------------------------------------------------


class TestCheckOrphanWorkspacesRecomposition:
    def test_legacy_orphan_dir_is_found(self, tmp_path: Path) -> None:
        worktrees_dir = tmp_path / ".worktrees"
        worktrees_dir.mkdir()
        (worktrees_dir / "057-foo-lane-a").mkdir()

        snapshot = {"work_packages": {"WP01": {"lane": "done"}}}
        findings = check_orphan_workspaces(tmp_path, "057-foo", snapshot)
        assert len(findings) == 1

    def test_same_prefix_impostor_not_reported(self, tmp_path: Path) -> None:
        """Regression guard: the glob `{slug}-lane-*` never matches
        `057-foobar-lane-a` for slug `057-foo` -- the glob's own `-lane-`
        literal already excludes a plain same-prefix impostor."""
        worktrees_dir = tmp_path / ".worktrees"
        worktrees_dir.mkdir()
        (worktrees_dir / "057-foobar-lane-a").mkdir()

        snapshot = {"work_packages": {"WP01": {"lane": "done"}}}
        findings = check_orphan_workspaces(tmp_path, "057-foo", snapshot)
        assert len(findings) == 0

    def test_slug_embedding_lane_not_reported(self, tmp_path: Path) -> None:
        """Guards against a glob `{slug}-lane-*` false-positive-matching a
        DIFFERENT mission's own lane dir when that mission's slug itself
        embeds `-lane-` (e.g. `057-foo-lane-mgmt`), since its lane worktree
        dir `057-foo-lane-mgmt-lane-a` starts with the glob's literal
        `057-foo-lane-`. Recognition by recomposition rejects it.
        """
        worktrees_dir = tmp_path / ".worktrees"
        worktrees_dir.mkdir()
        (worktrees_dir / "057-foo-lane-mgmt-lane-a").mkdir()

        snapshot = {"work_packages": {"WP01": {"lane": "done"}}}
        findings = check_orphan_workspaces(tmp_path, "057-foo", snapshot)
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# live_work/bindings.py::_resolve_mission_from_worktree (via resolve_bindings)
# ---------------------------------------------------------------------------


def _seed_mission(repo: Path, mission_slug: str, mission_id: str) -> None:
    spec_dir = repo / "kitty-specs" / mission_slug
    spec_dir.mkdir(parents=True)
    (spec_dir / "meta.json").write_text(json.dumps({"mission_id": mission_id, "mission_slug": mission_slug}))


def _make_lane_worktree(repo: Path, dir_name: str) -> Path:
    worktrees_dir = repo / ".worktrees"
    worktrees_dir.mkdir(exist_ok=True)
    lane_branch = f"lane-worktree-branch-{dir_name}"
    _git(repo, "branch", lane_branch)
    lane_path = worktrees_dir / dir_name
    _git(repo, "worktree", "add", "-q", str(lane_path), lane_branch)
    return lane_path


class TestResolveMissionFromWorktree:
    """Tests call the private site directly: ``resolve_bindings`` additionally
    gates on a git-truth ``origin`` remote (unrelated to this WP's change),
    which a bare tmp repo has none of.
    """

    def test_legacy_dir_binds_to_mission_by_slug_recomposition(self, tmp_path: Path) -> None:
        """Guards against a mid8-only ``_WORKTREE_DIR_RE`` never matching a
        legacy (no-mid8) worktree dir name, so ``057-foo-lane-a`` never binds.
        Named behaviour change: live-work binding by slug recomposition
        instead of mid8 prefix (plan Risk 2).
        """
        repo = _init_repo(tmp_path)
        mission_id = "01J6XW9KABCDEFGHJKMNPQRSTV"
        _seed_mission(repo, "057-foo", mission_id)
        lane_path = _make_lane_worktree(repo, "057-foo-lane-a")

        binding = _resolve_mission_from_worktree(lane_path, repo)
        assert binding is not None
        assert binding.mission_id == mission_id
        assert binding.display_label == "057-foo"

    def test_mid8_dir_binds_as_before(self, tmp_path: Path) -> None:
        """Regression: a modern mid8-embedded worktree dir still binds."""
        repo = _init_repo(tmp_path)
        mission_id = "01J6XW9KABCDEFGHJKMNPQRSTV"
        _seed_mission(repo, "foo-01J6XW9K", mission_id)
        lane_path = _make_lane_worktree(repo, "foo-01J6XW9K-lane-a")

        binding = _resolve_mission_from_worktree(lane_path, repo)
        assert binding is not None
        assert binding.mission_id == mission_id
        assert binding.display_label == "foo-01J6XW9K"

    def test_ambiguous_dir_matching_two_missions_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Zero or more than one recomposition match never guesses (FR-008).

        Honest on-disk state cannot produce two DIFFERENT ``ResolvedMission``
        entries whose ``mission_slug`` (the ``kitty-specs/`` directory name,
        necessarily unique on one filesystem) both recompose the SAME
        worktree-dir name -- recomposition is injective in ``mission_slug``
        for a fixed ``lane_id``. So ambiguity is constructed directly at the
        resolver seam, per the subtask's own "(constructed ambiguity)" note.
        """
        from specify_cli.context import mission_resolver as mission_resolver_module

        repo = _init_repo(tmp_path)
        mission_a = mission_resolver_module.ResolvedMission(
            mission_id="01J6XW9KABCDEFGHJKMNPQRSTV",
            mission_slug="foo",
            feature_dir=repo / "kitty-specs" / "foo",
            mid8="01J6XW9K",
        )
        mission_b = mission_resolver_module.ResolvedMission(
            mission_id="01J6XW9LABCDEFGHJKMNPQRSTV",
            mission_slug="foo",
            feature_dir=repo / "kitty-specs" / "foo",
            mid8="01J6XW9L",
        )
        monkeypatch.setattr(
            mission_resolver_module.FsMissionResolver,
            "all_missions",
            lambda self: [mission_a, mission_b],
        )

        lane_path = _make_lane_worktree(repo, "foo-lane-a")

        binding = _resolve_mission_from_worktree(lane_path, repo)
        assert binding is None

    def test_non_lane_dir_returns_none(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        lane_path = _make_lane_worktree(repo, "not-a-lane-dir")
        binding = _resolve_mission_from_worktree(lane_path, repo)
        assert binding is None


# ---------------------------------------------------------------------------
# policy/commit_guard.py::is_implementation_branch
# ---------------------------------------------------------------------------


class TestIsImplementationBranch:
    @pytest.mark.parametrize(
        "branch_name",
        [
            "kitty/mission-057-foo-lane-aa",
            "kitty/mission-foo-01KV6510-lane-ab",
        ],
    )
    def test_multi_letter_lane_ids_are_recognized(self, branch_name: str) -> None:
        """Guards against a ``_LANE_BRANCH_RE`` ending in ``lane-[a-z]$``
        (single letter only), so these multi-letter lane ids are rejected."""
        assert is_implementation_branch(branch_name) is True

    @pytest.mark.parametrize(
        ("branch_name", "expected"),
        [
            ("kitty/mission-foo-lane-a", True),
            ("kitty/mission-foo", False),
            ("main", False),
        ],
    )
    def test_regression_guards(self, branch_name: str, expected: bool) -> None:
        assert is_implementation_branch(branch_name) is expected


# ---------------------------------------------------------------------------
# merge/resolve.py::_extract_mission_slug
# ---------------------------------------------------------------------------


class TestExtractMissionSlugKnownShapes:
    @pytest.mark.parametrize(
        ("branch_name", "expected"),
        [
            ("017-smarter-feature-merge", "017-smarter-feature-merge"),
            ("017-smarter-feature-merge-lane-a", "017-smarter-feature-merge"),
            ("totally-unparseable!!", None),
            ("kitty/mission-057-foo-lane-a", "057-foo"),
            ("kitty/mission-foo-01KV6510-lane-a", "foo"),
        ],
    )
    def test_known_branch_shapes_unchanged(self, branch_name: str, expected: str | None) -> None:
        assert _extract_mission_slug(branch_name) == expected

    @pytest.mark.parametrize(
        "branch_name",
        [
            "057-Foo_Bar",
            "123-WIP branch",
        ],
    )
    def test_non_slug_grammar_bare_names_rejected(self, branch_name: str) -> None:
        """Guards against a bare (no ``kitty/mission-`` prefix) branch name
        accepted purely because it starts with an ``NNN-`` prefix. The
        bare-slug body is validated against the naming authority's
        ``is_valid_bare_slug_body`` (the same character class a hand-rolled
        regex would otherwise reimplement), so a non-slug-grammar name is
        rejected."""
        assert _extract_mission_slug(branch_name) is None
