"""Integration tests for :mod:`specify_cli.git.sparse_checkout` detection.

These tests exercise ``scan_repo`` / ``scan_path`` against real ``git init`` and
``git worktree add`` invocations, not mocked subprocess calls. They are the
end-to-end backstop for WP02's detection primitive: if the shape of git's
per-worktree sparse-checkout configuration ever changes under us, these tests
break first.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination import register_lane_sparse_checkout
from specify_cli.git.sparse_checkout import (
    SparseCheckoutPreflightError,
    SparseCheckoutKind,
    require_no_sparse_checkout,
    scan_path,
    scan_repo,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo_with_commit(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "Test User"])
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", "README.md"])
    _run(["git", "-C", str(repo), "commit", "-m", "init"])


MISSION_SLUG = "demo-feature-01J6XW9K"
MISSION_ID = "01J6XW9KABCDEFGHJKMNPQRSTV"
MID8 = "01J6XW9K"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"


def _init_coordination_lane_repo(repo: Path) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", "-b", "main", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "Test User"])
    _run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"])
    (repo / ".kittify").mkdir()
    spec_dir = repo / "kitty-specs" / MISSION_SLUG
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    (spec_dir / "status.events.jsonl").write_text("{}\n", encoding="utf-8")
    (spec_dir / "status.json").write_text("{}\n", encoding="utf-8")
    (spec_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": MISSION_SLUG,
                "mission_id": MISSION_ID,
                "coordination_branch": COORD_BRANCH,
            }
        ),
        encoding="utf-8",
    )
    _run(["git", "-C", str(repo), "add", "-A"])
    _run(["git", "-C", str(repo), "commit", "-m", "seed"])
    _run(["git", "-C", str(repo), "branch", COORD_BRANCH])
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text(exclude.read_text(encoding="utf-8") + ".worktrees/\n")
    lane_path = repo / ".worktrees" / f"{MISSION_SLUG}-lane-a"
    _run(
        [
            "git",
            "-C",
            str(repo),
            "worktree",
            "add",
            "-b",
            f"{COORD_BRANCH}-lane-a",
            str(lane_path),
            COORD_BRANCH,
        ],
    )
    register_lane_sparse_checkout(lane_path, MISSION_SLUG, MID8)
    return lane_path


MISSION_FREE_BRANCH = "before-the-mission"


def _commit_mission_specs(repo: Path) -> None:
    """Commit ``kitty-specs/<MISSION_SLUG>/`` (meta.json carriers included)."""
    spec_dir = repo / "kitty-specs" / MISSION_SLUG
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    (spec_dir / "status.events.jsonl").write_text("{}\n", encoding="utf-8")
    (spec_dir / "status.json").write_text("{}\n", encoding="utf-8")
    (spec_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": MISSION_SLUG,
                "mission_id": MISSION_ID,
                "coordination_branch": COORD_BRANCH,
            }
        ),
        encoding="utf-8",
    )
    _run(["git", "-C", str(repo), "add", "-A"])
    _run(["git", "-C", str(repo), "commit", "-m", "mission"])


def _add_lane_worktree(repo: Path, name: str, *, start_point: str) -> Path:
    """Add a registered lane worktree on its expected lane branch."""
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text(exclude.read_text(encoding="utf-8") + ".worktrees/\n", encoding="utf-8")
    lane_path = repo / ".worktrees" / name
    _run(
        [
            "git",
            "-C",
            str(repo),
            "worktree",
            "add",
            "-b",
            f"{COORD_BRANCH}-lane-a",
            str(lane_path),
            start_point,
        ],
    )
    return lane_path


def _init_lane_repo_with_mission_free_branch(repo: Path) -> tuple[Path, str]:
    """Coordination lane repo whose root checkout can stand on a Mission-free branch.

    Reproduces #6844 exactly: a base commit, a branch cut **before** the Mission
    exists, then the Mission and its lane worktree. The returned branch name has
    no ``kitty-specs/<MISSION_SLUG>/`` in its tree, so a root checkout switched to
    it knows nothing about the (fully merged) Mission that owns the lane.
    """
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", "-b", "main", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "Test User"])
    _run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"])
    (repo / ".kittify").mkdir()
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", "-A"])
    _run(["git", "-C", str(repo), "commit", "-m", "base"])
    _run(["git", "-C", str(repo), "branch", MISSION_FREE_BRANCH])

    _commit_mission_specs(repo)
    _run(["git", "-C", str(repo), "branch", COORD_BRANCH])
    lane_path = _add_lane_worktree(repo, f"{MISSION_SLUG}-lane-a", start_point=COORD_BRANCH)
    register_lane_sparse_checkout(lane_path, MISSION_SLUG, MID8)
    return lane_path, MISSION_FREE_BRANCH


def _switch_root(repo: Path, branch: str) -> None:
    _run(["git", "-C", str(repo), "checkout", "-q", branch])


# ---------------------------------------------------------------------------
# End-to-end detection
# ---------------------------------------------------------------------------


class TestEndToEndDetection:
    def test_fresh_repo_reports_inactive(self, tmp_path: Path) -> None:
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)

        report = scan_repo(repo)

        assert report.any_active is False
        assert report.primary.is_active is False
        assert report.worktrees == ()
        assert report.affected_paths == ()

    def test_enabling_sparse_checkout_flips_detection(self, tmp_path: Path) -> None:
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)

        _run(
            ["git", "-C", str(repo), "config", "core.sparseCheckout", "true"],
        )

        report = scan_repo(repo)
        assert report.primary.config_enabled is True
        assert report.primary.is_active is True
        assert report.any_active is True
        assert report.affected_paths == (repo,)

    def test_primary_clean_worktree_sparse_detected(self, tmp_path: Path) -> None:
        """Worktree-scoped config alone must flip ``any_active`` to True.

        Uses ``extensions.worktreeConfig=true`` + ``git config --worktree`` so
        the flag lives in the per-worktree config only. This is the realistic
        way to have a sparse worktree without affecting the primary repo.
        """
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)

        wt = repo / ".worktrees" / "lane-a"
        _run(
            [
                "git",
                "-C",
                str(repo),
                "worktree",
                "add",
                "-b",
                "feature/lane-a",
                str(wt),
            ],
        )

        # Enable worktree-scoped config storage.
        _run(["git", "-C", str(repo), "config", "extensions.worktreeConfig", "true"])
        # Enable sparse in the worktree only (per-worktree config file).
        _run(
            [
                "git",
                "-C",
                str(wt),
                "config",
                "--worktree",
                "core.sparseCheckout",
                "true",
            ],
        )

        report = scan_repo(repo)
        assert report.primary.is_active is False
        assert len(report.worktrees) == 1
        wt_state = report.worktrees[0]
        assert wt_state.is_active is True
        assert wt_state.is_worktree is True
        assert wt_state.path == wt
        # Pattern file should resolve under <git-common-dir>/worktrees/<name>/info/
        # even though it may not exist yet.
        assert wt_state.pattern_file_path is not None
        assert "worktrees" in str(wt_state.pattern_file_path)
        assert report.any_active is True
        assert wt in report.affected_paths

    def test_primary_sparse_worktree_clean(self, tmp_path: Path) -> None:
        """Primary has sparse; worktree does not — both must be probed correctly."""
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        _run(["git", "-C", str(repo), "config", "core.sparseCheckout", "true"])

        wt = repo / ".worktrees" / "lane-b"
        _run(
            [
                "git",
                "-C",
                str(repo),
                "worktree",
                "add",
                "-b",
                "feature/lane-b",
                str(wt),
            ],
        )

        report = scan_repo(repo)
        assert report.primary.is_active is True
        assert len(report.worktrees) == 1
        # The worktree inherits the repo-local config because git's config
        # resolution layers worktree > repo for a worktree checkout.
        # We only assert on any_active (FR-001) here — the exact inheritance
        # behaviour is documented in the WP risks section.
        assert report.any_active is True
        assert repo in report.affected_paths

    def test_pattern_file_line_count_counted_without_comments(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        _run(["git", "-C", str(repo), "config", "core.sparseCheckout", "true"])
        pf = repo / ".git" / "info" / "sparse-checkout"
        pf.parent.mkdir(parents=True, exist_ok=True)
        pf.write_text(
            "\n".join(
                [
                    "# header comment",
                    "src/",
                    "",
                    "tests/",
                    "   ",
                    "docs/",
                    "# trailing",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        state = scan_path(repo, is_worktree=False)
        assert state.pattern_file_present is True
        assert state.pattern_line_count == 3

    def test_managed_lane_sparse_checkout_is_not_blocking(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "r"
        lane_path = _init_coordination_lane_repo(repo)

        report = scan_repo(repo)

        assert report.any_active is True
        assert report.any_blocking is False
        assert report.affected_paths == ()
        assert len(report.worktrees) == 1
        assert report.worktrees[0].path == lane_path
        assert (
            report.worktrees[0].sparse_checkout_kind
            is SparseCheckoutKind.MANAGED_LANE
        )

    def test_managed_lane_sparse_checkout_with_drift_is_blocking_unknown(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "r"
        lane_path = _init_coordination_lane_repo(repo)
        raw = _run(
            ["git", "-C", str(lane_path), "rev-parse", "--git-path", "info/sparse-checkout"],
        ).stdout.strip()
        sparse_file = Path(raw)
        if not sparse_file.is_absolute():
            sparse_file = lane_path / sparse_file
        sparse_file.write_text("/*\n", encoding="utf-8")

        report = scan_repo(repo)

        assert report.any_active is True
        assert report.any_blocking is True
        assert report.affected_paths == (lane_path,)
        assert report.worktrees[0].sparse_checkout_kind is SparseCheckoutKind.UNKNOWN

    def test_manual_matching_worktree_is_blocking_unknown(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "r"
        _init_coordination_lane_repo(repo)
        manual_path = repo / ".worktrees" / f"{MISSION_SLUG}-lane-b"
        _run(
            [
                "git",
                "-C",
                str(repo),
                "worktree",
                "add",
                "-b",
                "feature/unrelated-sparse-worktree",
                str(manual_path),
                COORD_BRANCH,
            ],
        )
        register_lane_sparse_checkout(manual_path, MISSION_SLUG, MID8)

        report = scan_repo(repo)
        manual_state = next(w for w in report.worktrees if w.path == manual_path)

        assert manual_state.sparse_checkout_kind is SparseCheckoutKind.UNKNOWN
        assert manual_state.is_blocking is True
        assert manual_path in report.affected_paths


# ---------------------------------------------------------------------------
# Branch independence (#6844)
# ---------------------------------------------------------------------------


class TestManagedLaneIsBranchIndependent:
    """A managed lane's verdict must not depend on the root checkout's branch.

    #6844: ``_load_managed_lane_policies`` derived the managed-lane policy set
    only from the repository-root checkout's ``kitty-specs/``, so a root
    checkout standing on a branch that does not carry the other Mission's
    ``kitty-specs/<slug>/`` misclassified that Mission's own lane worktrees as
    legacy state -- a false refusal that also advertised a remedy
    (``doctor sparse-checkout --fix``) which would disable them.
    """

    def test_managed_lane_verdict_on_both_root_branches(self, tmp_path: Path) -> None:
        repo = tmp_path / "r"
        lane_path, mission_free = _init_lane_repo_with_mission_free_branch(repo)

        # Positive control: the root checkout's branch knows the Mission.
        on_branch = scan_repo(repo)
        assert on_branch.worktrees[0].path == lane_path
        assert on_branch.worktrees[0].sparse_checkout_kind is SparseCheckoutKind.MANAGED_LANE
        assert on_branch.any_blocking is False

        _switch_root(repo, mission_free)
        assert not (repo / "kitty-specs" / MISSION_SLUG).exists()

        off_branch = scan_repo(repo)

        assert off_branch.worktrees[0].path == lane_path
        assert off_branch.worktrees[0].sparse_checkout_kind is SparseCheckoutKind.MANAGED_LANE
        assert off_branch.any_blocking is False
        assert off_branch.affected_paths == ()
        # The invariant, stated directly: the branch is not an input.
        assert (
            off_branch.worktrees[0].sparse_checkout_kind
            is on_branch.worktrees[0].sparse_checkout_kind
        )

    def test_implement_preflight_does_not_refuse_on_mission_free_branch(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "r"
        _init_lane_repo_with_mission_free_branch(repo)
        _switch_root(repo, MISSION_FREE_BRANCH)

        # The exact entry point ``agent action implement`` calls; it must not
        # raise ``SparseCheckoutPreflightError`` for another Mission's lane.
        require_no_sparse_checkout(
            repo,
            command="spec-kitty agent action implement",
            override_flag=False,
            actor="tester",
            mission_slug="successor-mission-01M68JC9",
            mission_id="01M68JC9ABCDEFGHJKMNPQRSTV",
        )

    def test_genuine_legacy_state_still_refuses_on_mission_free_branch(
        self, tmp_path: Path
    ) -> None:
        """Same fixture family, opposite verdict: the escape did not widen.

        The lane's pattern file keeps ``/*`` only, so it is not the managed
        shape. This must refuse on **both** root branches, and with the
        unchanged message.
        """
        repo = tmp_path / "r"
        lane_path, mission_free = _init_lane_repo_with_mission_free_branch(repo)
        _truncate_lane_patterns(lane_path)

        for branch in ("main", mission_free):
            _switch_root(repo, branch)
            with pytest.raises(SparseCheckoutPreflightError) as ei:
                require_no_sparse_checkout(
                    repo,
                    command="spec-kitty agent action implement",
                    override_flag=False,
                    actor="tester",
                    mission_slug="successor-mission-01M68JC9",
                    mission_id="01M68JC9ABCDEFGHJKMNPQRSTV",
                )
            assert "legacy sparse-checkout state detected" in str(ei.value)
            assert "spec-kitty doctor sparse-checkout --fix" in str(ei.value)
            assert str(lane_path) in str(ei.value)
            assert ei.value.report.worktrees[0].sparse_checkout_kind is SparseCheckoutKind.UNKNOWN

    def test_lane_without_own_meta_json_stays_blocking(self, tmp_path: Path) -> None:
        """Fail closed: no branch-independent evidence, no managed verdict.

        A lane-shaped worktree on the expected lane branch with the managed
        patterns, cut from a commit that carries no ``kitty-specs/<slug>/``, has
        no Mission record anywhere to read. It must stay blocking rather than
        becoming managed by shape alone; the kind stays the no-policy default
        (``LEGACY_USER``), which is what "no policy candidate" has always meant.
        """
        repo = tmp_path / "r"
        lane_path, mission_free = _init_lane_repo_with_mission_free_branch(repo)
        _switch_root(repo, mission_free)
        _run(["git", "-C", str(repo), "worktree", "remove", "--force", str(lane_path)])
        _run(["git", "-C", str(repo), "branch", "-D", f"{COORD_BRANCH}-lane-a"])

        orphan = _add_lane_worktree(repo, f"{MISSION_SLUG}-lane-a", start_point=mission_free)
        register_lane_sparse_checkout(orphan, MISSION_SLUG, MID8)
        assert not (orphan / "kitty-specs" / MISSION_SLUG / "meta.json").exists()

        report = scan_repo(repo)
        orphan_state = next(w for w in report.worktrees if w.path == orphan)

        assert orphan_state.is_active is True
        assert orphan_state.sparse_checkout_kind is not SparseCheckoutKind.MANAGED_LANE
        assert orphan_state.is_blocking is True

    def test_root_policy_alone_is_enough_and_not_duplicated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two policy sources that agree must stay one candidate (NFR-001).

        ``_classify_worktree_state`` treats more than one candidate policy as
        ``UNKNOWN``, so the lane-local lookup must not run when the
        repository-root source already knows the Mission -- and it must not turn
        a correct verdict into ``UNKNOWN``. The ``meta.json`` read count is the
        observable: exactly one, the root-derived one.
        """
        repo = tmp_path / "r"
        _init_lane_repo_with_mission_free_branch(repo)
        reads: list[Path] = []

        from specify_cli.git import sparse_checkout as sc_mod

        original = sc_mod.load_meta

        def _record(feature_dir: Path, **kwargs: object):
            reads.append(feature_dir)
            return original(feature_dir, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(sc_mod, "load_meta", _record)

        report = scan_repo(repo)

        assert report.worktrees[0].sparse_checkout_kind is SparseCheckoutKind.MANAGED_LANE
        assert report.any_blocking is False
        assert len(reads) == 1, f"expected only the root-derived meta.json read, got {reads}"


def _truncate_lane_patterns(lane_path: Path) -> None:
    """Leave only the non-negated ``/*`` line in the lane's pattern file."""
    raw = _run(
        ["git", "-C", str(lane_path), "rev-parse", "--git-path", "info/sparse-checkout"],
    ).stdout.strip()
    pattern_file = Path(raw)
    if not pattern_file.is_absolute():
        pattern_file = lane_path / pattern_file
    pattern_file.write_text("/*\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Preflight wiring
# ---------------------------------------------------------------------------


class TestPreflight:
    def test_clean_repo_passes_preflight(self, tmp_path: Path) -> None:
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)

        require_no_sparse_checkout(
            repo,
            command="merge",
            override_flag=False,
            actor="tester",
            mission_slug="some-mission",
            mission_id="01HXYZ",
        )

    def test_sparse_repo_raises_preflight(self, tmp_path: Path) -> None:
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        _run(["git", "-C", str(repo), "config", "core.sparseCheckout", "true"])

        with pytest.raises(SparseCheckoutPreflightError) as ei:
            require_no_sparse_checkout(
                repo,
                command="merge",
                override_flag=False,
                actor="tester",
                mission_slug="some-mission",
                mission_id="01HXYZ",
            )

        err = ei.value
        assert err.command == "merge"
        assert err.report.any_active is True
        msg = str(err)
        assert "merge aborted" in msg
        assert "legacy sparse-checkout state detected" in msg
        assert "spec-kitty doctor sparse-checkout --fix" in msg
        assert "--allow-sparse-checkout" in msg
        assert str(repo) in msg

    def test_override_flag_emits_structured_log_and_does_not_raise(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        from specify_cli.git import sparse_checkout as sc_mod

        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        _run(["git", "-C", str(repo), "config", "core.sparseCheckout", "true"])

        caplog.set_level(logging.WARNING, logger=sc_mod.logger.name)

        require_no_sparse_checkout(
            repo,
            command="merge",
            override_flag=True,
            actor="tester",
            mission_slug="feat-slug",
            mission_id="01HXYZ",
        )

        override_hits = [
            r
            for r in caplog.records
            if "spec_kitty.override.sparse_checkout" in r.getMessage()
        ]
        assert len(override_hits) == 1
        msg = override_hits[0].getMessage()
        assert "command=merge" in msg
        assert "mission_slug=feat-slug" in msg
        assert "mission_id=01HXYZ" in msg
        assert "actor=tester" in msg
        assert str(repo) in msg

    def test_managed_lane_sparse_checkout_passes_preflight(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "r"
        _init_coordination_lane_repo(repo)

        require_no_sparse_checkout(
            repo,
            command="merge",
            override_flag=False,
            actor="tester",
            mission_slug=MISSION_SLUG,
            mission_id=MISSION_ID,
        )
