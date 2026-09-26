"""#4979 FR-005 — implement's planning-artifact auto-commit demotion guard.

Before this fix, `_ensure_planning_artifacts_committed_git` treated an
uncommitted `meta.json` that drops `coordination_branch` (a topology
demotion — HEAD had a coordination branch, the working copy silently
flattens it) exactly like any other ordinary dirty planning artifact: it
staged it via `resolve_planning_artifact_staging` and committed it via
`_commit_planning_artifacts_transaction`, carrying the demotion onto the
planning/target branch with no operator confirmation — the step-3
propagation hop in #4979's chain. The regression below drives that same
pre-existing entry point and pins the fixed contract: REFUSE, never
silently commit.

``planning_branch``/the repo's init branch is deliberately never
``main``/``master`` (mirrors ``test_auto_commit_uses_coordination_worktree_paths``
in ``test_implement.py``): those are protected by default, and a real
successful-commit assertion would otherwise fail on
``BookkeepingPolicyRefused: PROTECTED_BRANCH_REFUSED`` for reasons unrelated
to this guard.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_MISSION_ID = "01J8Y8Z900000000000000000R"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _init_repo(repo: Path, branch: str) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", branch)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _mission_branches(mission_slug: str) -> tuple[str, str]:
    """Return ``(planning_branch, coordination_branch)`` for *mission_slug*."""
    return f"mission/{mission_slug}", f"kitty/mission-{mission_slug}-{_MISSION_ID[:8]}"


def _meta_payload(*, with_coord: bool, mission_slug: str, mission_id: str = _MISSION_ID) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mission_id": mission_id,
        "mission_slug": mission_slug,
        "mid8": mission_id[:8],
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-05-28T00:00:00+00:00",
        "friendly_name": "4979 demotion-guard test mission",
    }
    if with_coord:
        payload["coordination_branch"] = _mission_branches(mission_slug)[1]
    return payload


def _write_meta(feature_dir: Path, payload: dict[str, Any]) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _seeded_coord_mission(tmp_path: Path, mission_slug: str = "demotion-guard-mission") -> tuple[Path, Path, str]:
    """A committed coord mission: HEAD's meta.json carries `coordination_branch`,
    and that branch genuinely exists in git (mirrors the real coord-topology
    shape the commit machinery expects)."""
    planning_branch, coord_branch = _mission_branches(mission_slug)
    repo = tmp_path / "repo"
    _init_repo(repo, planning_branch)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "initial")
    _git(repo, "branch", coord_branch)

    feature_dir = repo / "kitty-specs" / mission_slug
    payload = _meta_payload(with_coord=True, mission_slug=mission_slug)
    _write_meta(feature_dir, payload)
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed coord mission")
    return repo, feature_dir, planning_branch


class TestPlanningArtifactCommitDemotionGuard:
    """#4979 FR-005: the auto-commit must REFUSE a silent topology demotion."""

    @pytest.mark.regression
    def test_issue_4979_uncommitted_demotion_refuses_and_does_not_commit(self, tmp_path: Path) -> None:
        """Red-first regression pinned #4979: today this demotion rides into
        the `chore: planning artifacts` commit silently. Fixed behavior:
        REFUSE (typer.Exit) and leave HEAD untouched.
        """
        from specify_cli.cli.commands.implement import _ensure_planning_artifacts_committed_git

        mission_slug = "demotion-guard-mission"
        repo, feature_dir, planning_branch = _seeded_coord_mission(tmp_path, mission_slug)
        head_before = _git(repo, "rev-parse", "HEAD")

        # Flatten: drop coordination_branch from the working copy, uncommitted.
        flattened = _meta_payload(with_coord=False, mission_slug=mission_slug)
        _write_meta(feature_dir, flattened)
        assert _git(repo, "status", "--porcelain", str(feature_dir))  # dirty

        with pytest.raises(typer.Exit):
            _ensure_planning_artifacts_committed_git(
                repo_root=repo,
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id="WP01",
                planning_branch=planning_branch,
                auto_commit=True,
            )

        # The claim refused: nothing was committed (no silent demotion).
        assert _git(repo, "rev-parse", "HEAD") == head_before
        # The refusal does not mutate the working copy either -- the operator
        # still has to resolve it deliberately.
        working_meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
        assert "coordination_branch" not in working_meta

    def test_untracked_meta_json_allows_first_commit(self, tmp_path: Path) -> None:
        """No HEAD baseline (`git show HEAD:...` exit 128) is a legitimate
        first commit -- ALLOW, even though `coordination_branch` is set."""
        from specify_cli.cli.commands.implement import _ensure_planning_artifacts_committed_git

        mission_slug = "fresh-coord-mission"
        planning_branch, coord_branch = _mission_branches(mission_slug)
        repo = tmp_path / "repo"
        _init_repo(repo, planning_branch)
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        _git(repo, "add", "seed.txt")
        _git(repo, "commit", "-q", "-m", "initial")
        _git(repo, "branch", coord_branch)

        feature_dir = repo / "kitty-specs" / mission_slug
        _write_meta(feature_dir, _meta_payload(with_coord=True, mission_slug=mission_slug))
        assert _git(repo, "status", "--porcelain", str(feature_dir))  # untracked, dirty

        _ensure_planning_artifacts_committed_git(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            planning_branch=planning_branch,
            auto_commit=True,
        )

        committed = json.loads(_git(repo, "show", f"{planning_branch}:kitty-specs/{mission_slug}/meta.json"))
        assert committed["coordination_branch"].startswith("kitty/mission-")

    def test_corrupt_head_meta_json_refuses(self, tmp_path: Path) -> None:
        """A HEAD baseline that fails to parse as JSON fails closed to REFUSE."""
        from specify_cli.cli.commands.implement import _ensure_planning_artifacts_committed_git

        mission_slug = "corrupt-head-mission"
        planning_branch, _coord_branch = _mission_branches(mission_slug)
        repo = tmp_path / "repo"
        _init_repo(repo, planning_branch)
        feature_dir = repo / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text("{not valid json", encoding="utf-8")
        (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "seed corrupt meta.json")
        head_before = _git(repo, "rev-parse", "HEAD")

        # Dirty meta.json (still corrupt, but different bytes) so it lands in
        # the staged set.
        (feature_dir / "meta.json").write_text("{also not valid json", encoding="utf-8")
        assert _git(repo, "status", "--porcelain", str(feature_dir))

        with pytest.raises(typer.Exit):
            _ensure_planning_artifacts_committed_git(
                repo_root=repo,
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id="WP01",
                planning_branch=planning_branch,
                auto_commit=True,
            )
        assert _git(repo, "rev-parse", "HEAD") == head_before

    def test_corrupt_working_meta_json_refuses(self, tmp_path: Path) -> None:
        """A working copy that fails to parse as JSON fails closed to REFUSE,
        even though the HEAD baseline is valid."""
        from specify_cli.cli.commands.implement import _ensure_planning_artifacts_committed_git

        mission_slug = "corrupt-working-mission"
        repo, feature_dir, planning_branch = _seeded_coord_mission(tmp_path, mission_slug)
        head_before = _git(repo, "rev-parse", "HEAD")

        (feature_dir / "meta.json").write_text("{not valid json", encoding="utf-8")
        assert _git(repo, "status", "--porcelain", str(feature_dir))

        with pytest.raises(typer.Exit):
            _ensure_planning_artifacts_committed_git(
                repo_root=repo,
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id="WP01",
                planning_branch=planning_branch,
                auto_commit=True,
            )
        assert _git(repo, "rev-parse", "HEAD") == head_before

    def test_non_demoting_edit_commits_as_today(self, tmp_path: Path) -> None:
        """An ordinary, non-demoting meta.json edit still commits normally."""
        from specify_cli.cli.commands.implement import _ensure_planning_artifacts_committed_git

        mission_slug = "non-demoting-edit-mission"
        repo, feature_dir, planning_branch = _seeded_coord_mission(tmp_path, mission_slug)
        head_before = _git(repo, "rev-parse", "HEAD")

        edited = _meta_payload(with_coord=True, mission_slug=mission_slug)
        edited["source_description"] = "added by a later planning pass"
        _write_meta(feature_dir, edited)
        assert _git(repo, "status", "--porcelain", str(feature_dir))

        _ensure_planning_artifacts_committed_git(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            planning_branch=planning_branch,
            auto_commit=True,
        )

        head_after = _git(repo, "rev-parse", "HEAD")
        assert head_after != head_before
        committed = json.loads(_git(repo, "show", f"{planning_branch}:kitty-specs/{mission_slug}/meta.json"))
        assert committed["source_description"] == "added by a later planning pass"
        assert committed["coordination_branch"].startswith("kitty/mission-")


class TestMetaJsonDemotionRefusalHelper:
    """Direct unit coverage of the pure predicate (`_meta_json_demotion_refusal`)
    and its staging-seam wrapper (`_refuse_if_meta_json_demotion`) for branches
    that do not need a full real commit through `BookkeepingTransaction` to
    exercise (that plumbing is orthogonal to this guard's own logic)."""

    def _seed(self, tmp_path: Path, mission_slug: str, payload: dict[str, Any]) -> tuple[Path, Path]:
        repo = tmp_path / "repo"
        _init_repo(repo, "mission/seed")
        feature_dir = repo / "kitty-specs" / mission_slug
        _write_meta(feature_dir, payload)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "seed")
        return repo, feature_dir

    def test_already_flat_at_head_is_not_a_demotion(self, tmp_path: Path) -> None:
        """Both HEAD and the working copy lack `coordination_branch` -- not a
        demotion (there is nothing to demote from) -- ALLOW."""
        from specify_cli.cli.commands.implement import _meta_json_demotion_refusal

        mission_slug = "already-flat-mission"
        repo, feature_dir = self._seed(tmp_path, mission_slug, _meta_payload(with_coord=False, mission_slug=mission_slug))
        meta_path = feature_dir / "meta.json"
        rel_path = f"kitty-specs/{mission_slug}/meta.json"

        # Still-flat working edit (unrelated key added).
        edited = _meta_payload(with_coord=False, mission_slug=mission_slug)
        edited["source_description"] = "unrelated edit"
        _write_meta(feature_dir, edited)

        assert _meta_json_demotion_refusal(repo, mission_slug, meta_path, rel_path) is None

    def test_untracked_meta_json_has_no_baseline_allows(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.implement import _meta_json_demotion_refusal

        mission_slug = "untracked-mission"
        repo = tmp_path / "repo"
        _init_repo(repo, "mission/seed")
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        _git(repo, "add", "seed.txt")
        _git(repo, "commit", "-q", "-m", "initial")

        feature_dir = repo / "kitty-specs" / mission_slug
        _write_meta(feature_dir, _meta_payload(with_coord=True, mission_slug=mission_slug))
        meta_path = feature_dir / "meta.json"
        rel_path = f"kitty-specs/{mission_slug}/meta.json"

        assert _meta_json_demotion_refusal(repo, mission_slug, meta_path, rel_path) is None

    def test_demotion_returns_actionable_refusal_message(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.implement import _meta_json_demotion_refusal

        mission_slug = "demoted-mission"
        repo, feature_dir = self._seed(tmp_path, mission_slug, _meta_payload(with_coord=True, mission_slug=mission_slug))
        meta_path = feature_dir / "meta.json"
        rel_path = f"kitty-specs/{mission_slug}/meta.json"

        _write_meta(feature_dir, _meta_payload(with_coord=False, mission_slug=mission_slug))

        message = _meta_json_demotion_refusal(repo, mission_slug, meta_path, rel_path)
        assert message is not None
        assert mission_slug in message
        assert "coordination_branch" in message

    def test_refuse_if_meta_json_demotion_noop_when_not_in_dirty_set(self, tmp_path: Path) -> None:
        """The guard is a no-op when `meta.json` is not itself part of the
        dirty files being staged -- it must never inspect git for paths that
        are not part of this commit."""
        from specify_cli.cli.commands.implement import _refuse_if_meta_json_demotion

        mission_slug = "unrelated-dirty-file-mission"
        repo, feature_dir = self._seed(tmp_path, mission_slug, _meta_payload(with_coord=True, mission_slug=mission_slug))
        # Demote the working copy, but meta.json is NOT in files_to_commit --
        # some other file is what is being staged this round.
        _write_meta(feature_dir, _meta_payload(with_coord=False, mission_slug=mission_slug))

        # Must not raise: meta.json's demotion is irrelevant to this commit.
        _refuse_if_meta_json_demotion(
            repo,
            feature_dir,
            mission_slug,
            [f"kitty-specs/{mission_slug}/spec.md"],
        )
