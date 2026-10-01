"""Unit tests for :mod:`specify_cli.git.sparse_checkout_remediation`.

Covers T015 validation items from WP03:

- Clean primary, no worktrees — all 5 steps run, success.
- Clean primary + 2 clean worktrees — 3 results, all success.
- Primary dirty — all-or-nothing refusal (every result marked dirty).
- One worktree dirty — same all-or-nothing refusal.
- Interactive confirm returns False for one worktree — other paths remediate.
- ``git sparse-checkout disable`` failure on one worktree — other paths OK.
- Pattern file absent — ``remove_pattern_file`` still counts as completed.
- Verify-clean fails after refresh — ``error_step="verify_clean"``.

Every test builds a real sparse-configured repo on ``tmp_path`` so the five
git invocations actually run. We shell out to ``git init`` / ``git worktree
add`` / ``git config`` the same way WP02's detection tests do.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.git.sparse_checkout import (
    SparseCheckoutScanReport,
    SparseCheckoutState,
    scan_repo,
)
from specify_cli.git.sparse_checkout_remediation import (
    STEP_REFRESH_WORKING_TREE,
    STEP_REMOVE_PATTERN_FILE,
    STEP_SPARSE_DISABLE,
    STEP_UNSET_CONFIG,
    STEP_USER_DECLINED,
    STEP_VERIFY_CLEAN,
    SparseCheckoutRemediationReport,
    SparseCheckoutRemediationResult,
    remediate,
)


# ---------------------------------------------------------------------------
# Helpers — mirror the style used in the WP02 detection tests.
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

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


def _enable_sparse_with_pattern(repo: Path, patterns: list[str]) -> None:
    _run(["git", "-C", str(repo), "config", "core.sparseCheckout", "true"])
    pf = repo / ".git" / "info" / "sparse-checkout"
    pf.parent.mkdir(parents=True, exist_ok=True)
    pf.write_text("\n".join(patterns) + "\n", encoding="utf-8")


def _add_worktree(repo: Path, name: str, branch: str) -> Path:
    # Make sure the primary does not report `.worktrees/` as untracked; that
    # would cause the remediation dirty-tree pre-check to refuse on a fixture
    # that is effectively clean from the operator's perspective.
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if ".worktrees/" not in existing:
        exclude.write_text(existing + ".worktrees/\n", encoding="utf-8")

    wt = repo / ".worktrees" / name
    _run(
        [
            "git",
            "-C",
            str(repo),
            "worktree",
            "add",
            "-b",
            branch,
            str(wt),
        ],
    )
    return wt


# ---------------------------------------------------------------------------
# Happy-path cases
# ---------------------------------------------------------------------------


class TestCleanRemediation:
    def test_primary_only_all_five_steps(self, tmp_path: Path) -> None:
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        _enable_sparse_with_pattern(repo, ["README.md"])

        report = scan_repo(repo)
        assert report.primary.is_active is True

        result = remediate(report, interactive=False)

        assert isinstance(result, SparseCheckoutRemediationReport)
        assert result.worktree_results == ()
        assert result.overall_success is True

        pr = result.primary_result
        assert pr.success is True
        assert pr.error_step is None
        assert pr.error_detail is None
        assert pr.dirty_before_remediation is False
        assert pr.steps_completed == (
            STEP_SPARSE_DISABLE,
            STEP_UNSET_CONFIG,
            STEP_REMOVE_PATTERN_FILE,
            STEP_REFRESH_WORKING_TREE,
            STEP_VERIFY_CLEAN,
        )

        # Post-conditions: sparse disabled, pattern file gone, tree clean.
        proc = subprocess.run(
            ["git", "-C", str(repo), "config", "--get", "core.sparseCheckout"],
            capture_output=True,
            text=True,
            check=False,
        )
        # Exit code 1 == key not set (desired end-state).
        assert proc.returncode != 0 or proc.stdout.strip() == "false"
        pf = repo / ".git" / "info" / "sparse-checkout"
        assert not pf.exists()
        porcelain = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert porcelain.stdout.strip() == ""

    def test_primary_plus_two_worktrees_all_success(self, tmp_path: Path) -> None:
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)

        # Create worktrees BEFORE enabling any sparse state, so the checkout
        # step runs on a normal (non-sparse) config and leaves a clean tree.
        wt_a = _add_worktree(repo, "lane-a", "feature/a")
        wt_b = _add_worktree(repo, "lane-b", "feature/b")

        # Now enable sparse on the primary (affects only the primary repo
        # layout, which has a single tracked file so stays clean) and on each
        # worktree via worktree-scoped config.
        _enable_sparse_with_pattern(repo, ["README.md"])
        _run(["git", "-C", str(repo), "config", "extensions.worktreeConfig", "true"])
        for wt in (wt_a, wt_b):
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

        # Make absolutely sure every target is clean before remediation starts.
        for target in (repo, wt_a, wt_b):
            porcelain = subprocess.run(
                ["git", "-C", str(target), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            )
            assert porcelain.stdout.strip() == "", (
                f"fixture left {target} dirty: {porcelain.stdout!r}"
            )

        report = scan_repo(repo)
        # At minimum, primary + 2 worktrees present.
        assert len(report.worktrees) == 2

        result = remediate(report, interactive=False)
        assert result.overall_success is True, result
        assert result.primary_result.success is True
        assert len(result.worktree_results) == 2
        for wr in result.worktree_results:
            assert wr.success is True
            assert wr.error_step is None
            assert wr.steps_completed[-1] == STEP_VERIFY_CLEAN

    def test_pattern_file_absent_still_completes(self, tmp_path: Path) -> None:
        """Pattern-file absence is the desired state; step counts as complete."""
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        # Sparse config on but no pattern file written.
        _run(["git", "-C", str(repo), "config", "core.sparseCheckout", "true"])

        report = scan_repo(repo)
        result = remediate(report, interactive=False)

        assert result.primary_result.success is True
        assert STEP_REMOVE_PATTERN_FILE in result.primary_result.steps_completed


# ---------------------------------------------------------------------------
# Dirty-tree refusal (all-or-nothing)
# ---------------------------------------------------------------------------


class TestDirtyRefusal:
    def test_primary_dirty_refuses_everything(self, tmp_path: Path) -> None:
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        _enable_sparse_with_pattern(repo, ["README.md"])
        wt = _add_worktree(repo, "lane-a", "feature/a")

        # Dirty the primary.
        (repo / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")

        report = scan_repo(repo)
        result = remediate(report, interactive=False)

        # Nothing remediated anywhere.
        assert result.overall_success is False
        assert result.primary_result.dirty_before_remediation is True
        assert result.primary_result.success is False
        assert result.primary_result.steps_completed == ()
        assert result.primary_result.error_step is None
        assert result.primary_result.error_detail is not None
        assert "dirty" in result.primary_result.error_detail.lower()

        assert len(result.worktree_results) == 1
        wr = result.worktree_results[0]
        assert wr.path == wt
        assert wr.dirty_before_remediation is True
        assert wr.success is False
        assert wr.steps_completed == ()

        # Sparse config must still be set (remediation did not run).
        cfg = subprocess.run(
            ["git", "-C", str(repo), "config", "--get", "core.sparseCheckout"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert cfg.stdout.strip().lower() == "true"
        assert (repo / ".git" / "info" / "sparse-checkout").exists()

    def test_worktree_dirty_refuses_everything(self, tmp_path: Path) -> None:
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        _enable_sparse_with_pattern(repo, ["README.md"])
        wt = _add_worktree(repo, "lane-a", "feature/a")
        # Enable worktree config so the worktree is also "active".
        _run(["git", "-C", str(repo), "config", "extensions.worktreeConfig", "true"])
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

        # Dirty the worktree, not the primary.
        (wt / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")

        report = scan_repo(repo)
        result = remediate(report, interactive=False)

        assert result.overall_success is False
        # Primary was clean but gets the refusal result anyway.
        assert result.primary_result.dirty_before_remediation is True
        assert result.primary_result.success is False
        assert result.worktree_results[0].dirty_before_remediation is True
        assert result.worktree_results[0].success is False


# ---------------------------------------------------------------------------
# Interactive confirm
# ---------------------------------------------------------------------------


class TestInteractiveConfirm:
    def test_confirm_declines_one_worktree_other_paths_proceed(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)

        # Build worktrees first to avoid a sparse checkout transiently dirtying
        # them during `git worktree add`.
        wt_a = _add_worktree(repo, "lane-a", "feature/a")
        _add_worktree(repo, "lane-b", "feature/b")
        _enable_sparse_with_pattern(repo, ["README.md"])

        report = scan_repo(repo)
        calls: list[str] = []

        def _confirm(target: str) -> bool:
            calls.append(target)
            # Decline only the lane-a worktree.
            return not target.endswith(str(wt_a))

        result = remediate(report, interactive=True, confirm=_confirm)

        # Primary + both worktrees = 3 confirm calls (lane-a is one of them).
        assert len(calls) == 3
        # Primary remediated cleanly.
        assert result.primary_result.success is True

        # Look up lane-a's result and assert it was user-declined.
        decline_result = next(
            wr for wr in result.worktree_results if wr.path == wt_a
        )
        assert decline_result.success is False
        assert decline_result.error_step == STEP_USER_DECLINED
        assert decline_result.steps_completed == ()
        assert decline_result.dirty_before_remediation is False

        # The other worktree must have completed successfully.
        other_results = [wr for wr in result.worktree_results if wr.path != wt_a]
        assert len(other_results) == 1
        assert other_results[0].success is True

    def test_confirm_raising_is_treated_as_decline(self, tmp_path: Path) -> None:
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        _enable_sparse_with_pattern(repo, ["README.md"])

        report = scan_repo(repo)

        def _confirm(_target: str) -> bool:
            raise RuntimeError("kaboom")

        result = remediate(report, interactive=True, confirm=_confirm)

        assert result.primary_result.success is False
        assert result.primary_result.error_step == STEP_USER_DECLINED
        assert result.primary_result.error_detail is not None
        assert "kaboom" in result.primary_result.error_detail


# ---------------------------------------------------------------------------
# Step-level failure
# ---------------------------------------------------------------------------


class TestStepFailures:
    def test_sparse_disable_fails_on_one_worktree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulate ``git sparse-checkout disable`` failing in a specific worktree.

        We intercept the subprocess layer at the remediation module level. Only
        ``git sparse-checkout disable`` runs in the target worktree path fail;
        every other invocation goes through the real git binary so the rest of
        the five-step sequence (and the primary path) behave normally.
        """
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        wt_a = _add_worktree(repo, "lane-a", "feature/a")
        wt_b = _add_worktree(repo, "lane-b", "feature/b")
        _enable_sparse_with_pattern(repo, ["README.md"])

        # Make wt_a look sparse via worktree-scoped config so it is a target.
        _run(["git", "-C", str(repo), "config", "extensions.worktreeConfig", "true"])
        for wt in (wt_a, wt_b):
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
        assert any(w.path == wt_a for w in report.worktrees)

        import specify_cli.git.sparse_checkout_remediation as rmod

        real_run = subprocess.run

        def _fake_run(
            cmd: list[str], *args: object, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            cwd = kwargs.get("cwd")
            # Only fail on 'git sparse-checkout disable' issued against wt_a.
            if (
                isinstance(cmd, list)
                and cmd[:3] == ["git", "sparse-checkout", "disable"]
                and cwd == str(wt_a)
            ):
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=1,
                    stdout="",
                    stderr="simulated sparse-checkout failure on lane-a\n",
                )
            return real_run(cmd, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(rmod.subprocess, "run", _fake_run)

        result = remediate(report, interactive=False)

        # Primary succeeded.
        assert result.primary_result.success is True
        # wt_a failed on step 1.
        a_result = next(wr for wr in result.worktree_results if wr.path == wt_a)
        assert a_result.success is False
        assert a_result.error_step == STEP_SPARSE_DISABLE
        assert a_result.steps_completed == ()
        assert a_result.error_detail is not None
        assert "simulated" in a_result.error_detail
        # wt_b still succeeded (other paths are not short-circuited).
        b_result = next(wr for wr in result.worktree_results if wr.path == wt_b)
        assert b_result.success is True

    def test_verify_clean_fails_after_refresh(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Force ``git status --porcelain`` to report changes after step 4.

        This simulates the edge case where git's post-checkout working tree is
        not actually clean — the contract requires ``error_step=verify_clean``
        and the porcelain output captured in ``error_detail``.
        """
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        _enable_sparse_with_pattern(repo, ["README.md"])

        report = scan_repo(repo)

        import specify_cli.git.sparse_checkout_remediation as rmod

        real_run = subprocess.run
        # We need to let the initial dirty-tree pre-check pass (clean) but
        # poison the final verify. Track calls per (cmd, cwd) pair.
        status_call_count = {"n": 0}

        def _fake_run(
            cmd: list[str], *args: object, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            # The kernel.git status query runs ``git status --porcelain=v1 -z``.
            if isinstance(cmd, list) and cmd[:2] == ["git", "status"] and "--porcelain=v1" in cmd:
                status_call_count["n"] += 1
                # First call is the pre-check — return clean.
                # Subsequent calls are the step-5 verify — return dirty.
                if status_call_count["n"] == 1:
                    return real_run(cmd, *args, **kwargs)  # type: ignore[arg-type]
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout=b" M README.md\0",
                    stderr=b"",
                )
            return real_run(cmd, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(rmod.subprocess, "run", _fake_run)

        result = remediate(report, interactive=False)

        assert result.primary_result.success is False
        assert result.primary_result.error_step == STEP_VERIFY_CLEAN
        assert result.primary_result.error_detail is not None
        assert "README.md" in result.primary_result.error_detail
        # Previous four steps should have been recorded as completed.
        assert STEP_SPARSE_DISABLE in result.primary_result.steps_completed
        assert STEP_REFRESH_WORKING_TREE in result.primary_result.steps_completed
        assert STEP_VERIFY_CLEAN not in result.primary_result.steps_completed

    def test_verify_probe_failure_fails_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing post-refresh ``git status`` cannot prove the tree clean."""
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        _enable_sparse_with_pattern(repo, ["README.md"])

        report = scan_repo(repo)

        import specify_cli.git.sparse_checkout_remediation as rmod

        real_run = subprocess.run
        status_call_count = {"n": 0}

        def _fake_run(
            cmd: list[str], *args: object, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            if isinstance(cmd, list) and cmd[:2] == ["git", "status"] and "--porcelain=v1" in cmd:
                status_call_count["n"] += 1
                if status_call_count["n"] == 1:
                    return real_run(cmd, *args, **kwargs)  # type: ignore[arg-type]
                return subprocess.CompletedProcess(
                    args=cmd, returncode=128, stdout=b"", stderr=b"fatal: probe exploded\n"
                )
            return real_run(cmd, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(rmod.subprocess, "run", _fake_run)

        result = remediate(report, interactive=False)

        assert result.primary_result.success is False
        assert result.primary_result.error_step == STEP_VERIFY_CLEAN
        assert result.primary_result.error_detail is not None
        assert "probe exploded" in result.primary_result.error_detail
        assert STEP_VERIFY_CLEAN not in result.primary_result.steps_completed


# ---------------------------------------------------------------------------
# Dataclass-level sanity
# ---------------------------------------------------------------------------


class TestReportProperties:
    def test_overall_success_requires_every_path(self) -> None:
        primary = SparseCheckoutRemediationResult(
            path=Path("/p"),
            success=True,
            steps_completed=(STEP_SPARSE_DISABLE, STEP_UNSET_CONFIG),
            error_step=None,
            error_detail=None,
            dirty_before_remediation=False,
        )
        wt_ok = SparseCheckoutRemediationResult(
            path=Path("/p/.worktrees/a"),
            success=True,
            steps_completed=(STEP_VERIFY_CLEAN,),
            error_step=None,
            error_detail=None,
            dirty_before_remediation=False,
        )
        wt_bad = SparseCheckoutRemediationResult(
            path=Path("/p/.worktrees/b"),
            success=False,
            steps_completed=(),
            error_step=STEP_SPARSE_DISABLE,
            error_detail="nope",
            dirty_before_remediation=False,
        )
        both_good = SparseCheckoutRemediationReport(
            primary_result=primary, worktree_results=(wt_ok,)
        )
        mixed = SparseCheckoutRemediationReport(
            primary_result=primary, worktree_results=(wt_ok, wt_bad)
        )
        assert both_good.overall_success is True
        assert mixed.overall_success is False

    def test_scan_report_with_inactive_primary_still_remediated_noop(
        self, tmp_path: Path
    ) -> None:
        """Primary that is already clean still runs the five steps as no-ops."""
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        # No sparse config enabled — scan reports inactive.
        report = scan_repo(repo)
        assert report.primary.is_active is False

        result = remediate(report, interactive=False)
        # All five steps must succeed: disable is idempotent, unset tolerates
        # missing key, pattern file missing is OK, checkout HEAD -- . is a
        # no-op on a clean tree, verify confirms clean.
        assert result.primary_result.success is True
        assert result.primary_result.steps_completed[-1] == STEP_VERIFY_CLEAN


# ---------------------------------------------------------------------------
# Construction-contract sanity — the module must not reach outside targets.
# ---------------------------------------------------------------------------


class TestContainment:
    def test_remediation_never_touches_paths_outside_scan_report(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = tmp_path / "r"
        _init_repo_with_commit(repo)
        _enable_sparse_with_pattern(repo, ["README.md"])

        report = scan_repo(repo)

        # Hand-construct a report whose "primary" is an irrelevant directory;
        # after remediation, only that path should have been touched.
        other = tmp_path / "elsewhere"
        other.mkdir()
        _run(["git", "init", "-q", str(other)])
        _run(["git", "-C", str(other), "config", "user.email", "e@e"])
        _run(["git", "-C", str(other), "config", "user.name", "E"])
        (other / "f.txt").write_text("x\n", encoding="utf-8")
        _run(["git", "-C", str(other), "add", "f.txt"])
        _run(["git", "-C", str(other), "commit", "-m", "init"])

        synthetic = SparseCheckoutScanReport(
            primary=SparseCheckoutState(
                path=other,
                config_enabled=False,
                pattern_file_path=other / ".git" / "info" / "sparse-checkout",
                pattern_file_present=False,
                pattern_line_count=0,
                is_worktree=False,
            ),
            worktrees=(),
        )

        remediate(synthetic, interactive=False)

        # Unrelated repo still has sparse config intact.
        cfg = subprocess.run(
            ["git", "-C", str(repo), "config", "--get", "core.sparseCheckout"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert cfg.stdout.strip().lower() == "true"
        assert (repo / ".git" / "info" / "sparse-checkout").exists()
        # Keep the real scan report from being garbage-collected pre-assert —
        # also a reminder that synthetic reports are how WP03 can be called
        # without entangling it with WP02 detection outputs.
        assert report.primary.is_active is True
