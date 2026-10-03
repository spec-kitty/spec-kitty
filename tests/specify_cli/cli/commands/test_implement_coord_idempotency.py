"""Regression: read-surface == write-surface for a coordination mission's
healthy verbatim commit path (PR #2662 adversarial-squad finding).

The implement-claim idempotency guard skips files already identical on the ref
they will be COMMITTED to, so a re-discovered edit does not produce an empty
commit that ``safe_commit`` rejects. On the healthy ``placement_ref is not
None`` path the whole batch commits VERBATIM to ``placement_ref.ref`` (the
coord ref on a coordination mission -- the C-004/#2160 deferral leaves it
un-partitioned). Before the fix the guard compared a PRIMARY artifact against
``HEAD`` while the write went to coord, so a PRIMARY ``spec.md`` already on
coord but differing from ``HEAD`` was re-committed → empty commit → the SECOND
claim hard-failed with ``typer.Exit(1)``.

These tests use the REAL ``BookkeepingTransaction`` (the sibling write-side
suite monkeypatches a fake, which is why the empty-commit was never exercised).
The invariant: the read ref must be the SAME surface as the write target.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer

from mission_runtime.context import CommitTarget
from specify_cli.cli.commands.implement_cores import PlanningArtifactStagingPlan, resolve_planning_artifact_staging

# Real-git-repo + real BookkeepingTransaction integration test (mirrors the
# sibling test_tasks_move_task_cwd.py markers so a CI gate selects it and the
# marker-convention / orphan-surface arch gates stay green).
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_PLANNING_BRANCH = "mission/coord-idempotency-demo"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _seed_coord_mission_real(tmp_path: Path) -> tuple[Path, Path, str, str, CommitTarget]:
    """A real git repo with a coordination mission, an empty coord branch, and a
    genuinely-dirty PRIMARY ``spec.md`` (revised in the working tree, differs
    from the committed HEAD baseline). Returns (repo, feature_dir, mission_slug,
    spec_rel, coord_target)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _PLANNING_BRANCH)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")

    mission_slug = "coord-idempotency-demo"
    mission_id = "01J9COORDIDEMPOTENCYXXXXXX"
    mid8 = mission_id[:8]
    coord_branch = f"kitty/mission-{mission_slug}-{mid8}"
    _git(repo, "branch", coord_branch)

    feature_dir = repo / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": mission_slug,
                "mid8": mid8,
                "mission_type": "software-dev",
                "target_branch": _PLANNING_BRANCH,
                "coordination_branch": coord_branch,
                "topology": "coord",
                "created_at": "2026-07-14T00:00:00+00:00",
                "friendly_name": "coord idempotency demo",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    spec = feature_dir / "spec.md"
    spec.write_text("# Spec\noriginal\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed feature dir (spec=original on HEAD)")
    # Genuinely-dirty PRIMARY artifact: differs from the HEAD baseline.
    spec.write_text("# Spec\nrevised\n", encoding="utf-8")

    return repo, feature_dir, mission_slug, f"kitty-specs/{mission_slug}/spec.md", CommitTarget(ref=coord_branch)


def _claim(
    repo: Path,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    target: CommitTarget,
    *,
    auto_commit: bool = True,
) -> None:
    from specify_cli.cli.commands.implement import _ensure_planning_artifacts_committed_git

    _ensure_planning_artifacts_committed_git(
        repo_root=repo,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        planning_branch=_PLANNING_BRANCH,
        auto_commit=auto_commit,
        placement_ref=target,
    )


class TestCoordHealthyPathIdempotency:
    def test_repeated_claim_of_a_coord_identical_primary_artifact_does_not_hard_fail(
        self, tmp_path: Path
    ) -> None:
        """The read surface follows the verbatim write target: a PRIMARY artifact
        already committed to the coord ref is dropped on the next claim instead of
        producing an empty commit that ``Exit(1)``s. Pre-fix this raised on claim 2.
        """
        repo, feature_dir, mission_slug, spec_rel, target = _seed_coord_mission_real(tmp_path)

        # write-path-integrity WP02 / T008+T009 re-baseline: a PRIMARY artifact
        # (spec.md) now commits to the mission TARGET branch (``_PLANNING_BRANCH``),
        # never the coordination ref (the #3371 partition fix), and a re-claim of
        # an identical artifact is a ``commit_idempotent`` no-op (T009 crash-
        # recovery re-drive) rather than an empty commit that ``Exit(1)``s.
        #
        # Claim 1: spec.md is dirty vs HEAD -> committed to the TARGET branch.
        _claim(repo, feature_dir, mission_slug, "WP01", target)
        assert _git(repo, "show", f"{_PLANNING_BRANCH}:{spec_rel}") == "# Spec\nrevised"
        # It must NOT have landed on the coordination ref.
        on_coord = subprocess.run(
            ["git", "show", f"{target.ref}:{spec_rel}"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert on_coord.returncode != 0, "PRIMARY spec.md must never land on coord (#3371)"

        # Claim 2: spec.md is now identical on the TARGET write surface -> the
        # idempotent re-drive no-ops, no empty commit, no raise.
        try:
            _claim(repo, feature_dir, mission_slug, "WP02", target)
        except typer.Exit as exc:  # pragma: no cover - the bug this test guards
            pytest.fail(
                f"claim 2 hard-failed with typer.Exit({exc.exit_code}) — an "
                "already-committed PRIMARY artifact must be an idempotent no-op, "
                "not an empty commit that fails the claim"
            )
        assert _git(repo, "show", f"{_PLANNING_BRANCH}:{spec_rel}") == "# Spec\nrevised"


# ---------------------------------------------------------------------------
# #5576 -- planning-artifact staging compares Git's CLEAN view, not raw bytes.
# ---------------------------------------------------------------------------

_PLAN_LF = b"# Plan\nbaseline\n"


def _seed_crlf_clean_checkout(tmp_path: Path) -> tuple[Path, Path, str, CommitTarget]:
    """A Windows-style clone: ``* text=auto eol=crlf`` makes every checked-out
    text file CRLF on disk while the committed blobs stay LF, and
    ``git status --porcelain`` is empty. Returns (repo, feature_dir,
    mission_slug, coord_target)."""
    repo, feature_dir, mission_slug, _spec_rel, target = _seed_coord_mission_real(tmp_path)
    (feature_dir / "plan.md").write_bytes(_PLAN_LF)
    # Land every planning file (the dirty spec.md included) as a LF blob first.
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning artifacts (LF blobs)")
    (repo / ".gitattributes").write_text("* text=auto eol=crlf\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-q", "-m", "crlf checkout policy")
    # Re-materialize the working tree the way a fresh Windows clone would.
    for tracked in _git(repo, "ls-files", "kitty-specs", "seed.txt").splitlines():
        (repo / tracked).unlink()
    _git(repo, "checkout", "--", ".")
    assert _git(repo, "status", "--porcelain") == "", "precondition: checkout is Git-clean"
    assert b"\r\n" in (feature_dir / "plan.md").read_bytes(), "precondition: working files are CRLF"
    return repo, feature_dir, mission_slug, target


def _staging_plan(repo: Path, feature_dir: Path, target: CommitTarget, *, auto_commit: bool) -> PlanningArtifactStagingPlan:
    from specify_cli.cli.commands.implement import _feature_dir_file_paths

    return resolve_planning_artifact_staging(
        repo,
        feature_dir,
        target.ref,
        _feature_dir_file_paths(repo, feature_dir),
        auto_commit=auto_commit,
    )


class TestGitCleanCrlfCheckout:
    def test_crlf_clean_checkout_yields_an_empty_planning_artifact_staging_plan(self, tmp_path: Path) -> None:
        repo, feature_dir, _slug, target = _seed_crlf_clean_checkout(tmp_path)

        plan = _staging_plan(repo, feature_dir, target, auto_commit=False)

        assert plan.files_to_commit == []
        assert plan.status_paths_to_commit == []

    def test_crlf_worktree_with_a_real_token_change_is_still_staged(self, tmp_path: Path) -> None:
        """Ratchet (C-004), green before and after the fix: a genuine edit saved
        with CRLF endings is never reported as clean."""
        repo, feature_dir, slug, target = _seed_crlf_clean_checkout(tmp_path)
        (feature_dir / "plan.md").write_bytes(b"# Plan\r\nREVISED\r\n")

        plan = _staging_plan(repo, feature_dir, target, auto_commit=False)

        assert f"kitty-specs/{slug}/plan.md" in plan.files_to_commit

    def test_crlf_worktree_with_a_real_token_change_stages_only_that_path(self, tmp_path: Path) -> None:
        """FR-005: the really-changed file is staged ALONE; its Git-clean CRLF
        siblings stay out of the plan."""
        repo, feature_dir, slug, target = _seed_crlf_clean_checkout(tmp_path)
        (feature_dir / "plan.md").write_bytes(b"# Plan\r\nREVISED\r\n")

        plan = _staging_plan(repo, feature_dir, target, auto_commit=False)

        assert plan.files_to_commit == [f"kitty-specs/{slug}/plan.md"]

    @pytest.mark.parametrize("auto_commit", [False, True])
    def test_implement_entry_point_opens_no_commit_on_a_crlf_clean_checkout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, auto_commit: bool
    ) -> None:
        """NFR-001: through ``_ensure_planning_artifacts_committed_git`` (what
        ``implement WP##`` calls, with and without ``--no-auto-commit``) a
        Git-clean CRLF checkout is not refused and opens no planning-artifact
        commit transaction, so no empty commit can be attempted."""
        from specify_cli.cli.commands import implement as implement_module

        repo, feature_dir, slug, target = _seed_crlf_clean_checkout(tmp_path)
        tips_before = (_git(repo, "rev-parse", _PLANNING_BRANCH), _git(repo, "rev-parse", target.ref))
        opened: list[list[str]] = []
        monkeypatch.setattr(
            implement_module,
            "_commit_planning_artifacts_transaction",
            lambda **kwargs: opened.append(list(kwargs["files_to_commit"])),
        )

        try:
            _claim(repo, feature_dir, slug, "WP01", target, auto_commit=auto_commit)
        except typer.Exit as exc:
            pytest.fail(f"a Git-clean checkout was refused with typer.Exit({exc.exit_code})")

        assert opened == [], f"commit transaction opened for Git-clean files: {opened}"
        assert (_git(repo, "rev-parse", _PLANNING_BRANCH), _git(repo, "rev-parse", target.ref)) == tips_before
