"""WP03/T013 — pin the primary-checkout pre-mutation safety regression (#4752).

Prior to WP03 the lane-based merge advanced the target ref and only THEN ran
``_refresh_primary_checkout_after_merge`` (a bare ``git reset --hard HEAD``)
against the operator's repository-root checkout with no branch/dirty guard.
Two loss shapes were possible:

1. **Off-target** (FR-001/US1 AC1): the primary checkout sits on some other
   branch (``feature-x``) with an uncommitted tracked edit. The reset ran
   against that checkout anyway, destroying the edit, and the merge then
   crashed mid-bookkeeping with a raw ``SafeCommitHeadMismatch``.
2. **On-target but dirty** (FR-002/US1 AC2): the primary checkout IS on the
   target branch but has an uncommitted tracked edit. The reset silently
   destroyed it while the merge otherwise proceeded to a false "success".

WP03/T010 hoists a pre-mutation preflight into the OUTER
``_run_lane_based_merge`` — before the global merge lock is even acquired and
long before ``_phase_merge_lanes``/the target-ref advance — so both shapes
now refuse fail-closed with :class:`DestructiveOpRefused` and the repository
is byte-identical to pre-invocation (NFR-001). Uses the real-git Layer 2
harness pattern from ``tests/integration/test_merge_lane_planning_data_loss.py``
(``_real_merge_external_mocks``): real git, only out-of-git side effects
mocked. ``_refresh_primary_checkout_after_merge`` is deliberately NOT mocked.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from kernel.clock import now_utc_iso
from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.git.destructive_guard import (
    MERGE_UNSAFE_PRIMARY_DIRTY,
    MERGE_UNSAFE_PRIMARY_OFF_TARGET,
)
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.merge.config import MergeStrategy
from specify_cli.merge.state import MergeState, save_state

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

_README = "README.md"


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / _README).write_text("init\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _write_meta(feature_dir: Path, slug: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_slug": slug,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "purpose_tldr": "primary-checkout safety regression pin",
        "purpose_context": "real-merge #4752 preflight test",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_lanes_manifest(feature_dir: Path, slug: str) -> LanesManifest:
    """A single code lane (``lane-a``/WP01), target branch ``main``."""
    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=None,
        mission_branch=f"kitty/mission-{slug}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/foo.py",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


def _commit_file(repo: Path, *, branch: str, relpath: str, content: str, message: str) -> None:
    _git(repo, "checkout", branch)
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", relpath)
    _git(repo, "commit", "-m", message)


def _bootstrap_mission(tmp_path: Path, slug: str) -> Path:
    """Bootstrap a mission ready to merge: mission branch + lane-a with a real commit."""
    _init_git_repo(tmp_path)
    feature_dir = tmp_path / "kitty-specs" / slug
    _write_meta(feature_dir, slug)
    _write_lanes_manifest(feature_dir, slug)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap mission fixture")

    mission_branch = f"kitty/mission-{slug}"
    _git(tmp_path, "branch", mission_branch, "main")

    lane_branch = lane_branch_name(slug, "lane-a")
    _git(tmp_path, "branch", lane_branch, "main")
    _commit_file(
        tmp_path,
        branch=lane_branch,
        relpath="src/foo.py",
        content="def foo():\n    return 1\n",
        message=f"feat({slug}): add foo function (WP01)",
    )
    return feature_dir


@contextlib.contextmanager
def _real_merge_external_mocks(repo_root: Path):
    """Mock only the side effects that touch state OUTSIDE git.

    Mirrors ``tests/integration/test_merge_lane_planning_data_loss.py``'s
    harness of the same name. ``_refresh_primary_checkout_after_merge`` is
    deliberately NOT in this list — the whole point of #4752 is what happens
    when that real ``reset --hard`` runs against an unsafe primary checkout.
    """
    patches = [
        patch("specify_cli.merge.done_bookkeeping._mark_wp_merged_done"),
        patch("specify_cli.merge.done_bookkeeping._assert_merged_wps_reached_done"),
        patch("specify_cli.merge.executor.commit_merge_bookkeeping"),
        patch("specify_cli.post_merge.stale_assertions.run_check"),
        patch("specify_cli.merge.executor.run_check"),
        patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        patch("specify_cli.policy.config.load_policy_config"),
        patch(
            "specify_cli.merge.executor._bake_mission_number_into_mission_branch",
            return_value=None,
        ),
        patch("specify_cli.merge.executor._classify_porcelain_lines", return_value=([], 0)),
    ]
    with contextlib.ExitStack() as stack:
        ms = [stack.enter_context(p) for p in patches]
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        ms[7].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = []
        ms[8].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        ms[3].return_value = stale_report
        ms[4].return_value = stale_report
        yield


def _invoke_merge(tmp_path: Path, slug: str) -> None:
    with _real_merge_external_mocks(tmp_path):
        _run_lane_based_merge(
            repo_root=tmp_path,
            mission_slug=slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )


class TestPrimaryCheckoutOffTargetSafety:
    """FR-001/US1 AC1: off-target primary checkout with an uncommitted edit."""

    def test_off_target_dirty_checkout_refuses_before_any_mutation(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        slug = "test-primary-off-target"
        _bootstrap_mission(tmp_path, slug)

        # Off-target: a branch other than "main" (the target), with an
        # uncommitted TRACKED edit.
        _git(tmp_path, "checkout", "-b", "feature-x")
        pre_head = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
        (tmp_path / _README).write_text("operator's unrelated work in progress\n")
        dirty_before = _git(tmp_path, "status", "--porcelain").stdout

        with pytest.raises(typer.Exit) as excinfo:
            _invoke_merge(tmp_path, slug)

        assert excinfo.value.exit_code == 1
        captured = capsys.readouterr()
        assert MERGE_UNSAFE_PRIMARY_OFF_TARGET in captured.out
        assert "currently on 'feature-x', expected 'main'" in captured.out

        # NFR-001: byte-identical to pre-invocation. Nothing mutated: HEAD is
        # unchanged, the branch is unchanged, the edit survives verbatim.
        assert _git(tmp_path, "rev-parse", "HEAD").stdout.strip() == pre_head
        assert _git(tmp_path, "branch", "--show-current").stdout.strip() == "feature-x"
        assert (tmp_path / _README).read_text() == "operator's unrelated work in progress\n"
        assert _git(tmp_path, "status", "--porcelain").stdout == dirty_before
        # The target-ref advance (_phase_mission_to_target) was never reached:
        # "main" still has no trace of the lane-a code commit.
        assert _git(tmp_path, "ls-tree", "--name-only", "-r", "main", "--", "src/foo.py").stdout.strip() == ""


class TestPrimaryCheckoutOnTargetDirtySafety:
    """FR-002/US1 AC2: primary checkout on-target but with tracked dirt."""

    def test_on_target_dirty_checkout_refuses_before_reset(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        slug = "test-primary-on-target-dirty"
        _bootstrap_mission(tmp_path, slug)

        _git(tmp_path, "checkout", "main")
        pre_head = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
        (tmp_path / _README).write_text("uncommitted tracked edit on target\n")
        dirty_before = _git(tmp_path, "status", "--porcelain").stdout

        with pytest.raises(typer.Exit) as excinfo:
            _invoke_merge(tmp_path, slug)

        assert excinfo.value.exit_code == 1
        captured = capsys.readouterr()
        assert MERGE_UNSAFE_PRIMARY_DIRTY in captured.out

        # NFR-001: the reset --hard call site was never reached; edit survives
        # and the target branch never advanced.
        assert _git(tmp_path, "rev-parse", "HEAD").stdout.strip() == pre_head
        assert (tmp_path / _README).read_text() == "uncommitted tracked edit on target\n"
        assert _git(tmp_path, "status", "--porcelain").stdout == dirty_before

    def test_on_target_dirty_checkout_refuses_identically_on_resume(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """US1 AC4: ``--resume`` honors the guard identically to a fresh merge.

        Both the fresh and the resumed CLI paths route through the same
        outer ``_run_lane_based_merge``, so seeding an interrupted
        ``MergeState`` (as a prior attempt would have left behind) must
        refuse exactly like the fresh-merge case above.
        """
        slug = "test-primary-on-target-dirty-resume"
        _bootstrap_mission(tmp_path, slug)

        save_state(
            MergeState(
                mission_id=slug,
                mission_slug=slug,
                target_branch="main",
                wp_order=["WP01"],
                completed_wps=[],
            ),
            tmp_path,
        )

        _git(tmp_path, "checkout", "main")
        pre_head = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
        (tmp_path / _README).write_text("uncommitted tracked edit, resumed merge\n")

        with pytest.raises(typer.Exit) as excinfo:
            _invoke_merge(tmp_path, slug)

        assert excinfo.value.exit_code == 1
        captured = capsys.readouterr()
        assert MERGE_UNSAFE_PRIMARY_DIRTY in captured.out
        assert _git(tmp_path, "rev-parse", "HEAD").stdout.strip() == pre_head
        assert (tmp_path / _README).read_text() == "uncommitted tracked edit, resumed merge\n"


class TestPrimaryCheckoutCleanParity:
    """US1 AC3/NFR-002: the clean/on-target merge is unaffected by the guard."""

    def test_clean_on_target_checkout_merge_completes_unchanged(self, tmp_path: Path) -> None:
        slug = "test-primary-clean-parity"
        _bootstrap_mission(tmp_path, slug)
        _git(tmp_path, "checkout", "main")

        _invoke_merge(tmp_path, slug)

        assert (tmp_path / "src" / "foo.py").exists(), "Parity regression: the clean/on-target merge must complete exactly as before the guard was introduced."
