"""#4933: a user's own ``meta.json`` must never be exempted from dirty-tree gates.

``coordination.coherence.is_self_bookkeeping_churn`` (pre-fix) exempted ANY
path whose basename is ``meta.json`` from every dirty-tree safety gate that
consults it (directly, or via ``is_toolchain_generated_churn``). A dirty
``src/app/meta.json`` — an operator's OWN file that merely happens to share a
basename with Spec Kitty's own mission-identity metadata — was therefore
invisible to ``_pre_mutation_safety_preflight`` (``consolidation/executor.py``),
and ``spec-kitty consolidate`` proceeded to ``reset --hard`` the repository
root checkout / ``worktree remove --force`` the lane worktree, destroying the
edit, then exited 0.

The fix anchors the exemption depth-exact —
``(?:^|/)kitty-specs/[^/]+/meta\\.json$`` plus the legacy
``(?:^|/)\\.kittify/meta\\.json$`` — so a user ``meta.json`` anywhere else is
real dirt again, while Spec Kitty's own mission ``meta.json`` (including under
a monorepo subdirectory) stays exempt.

Harness: the real-git ``_run_lane_based_consolidation`` Layer-2 pattern from
``tests/integration/test_merge_primary_checkout_safety.py`` /
``test_merge_lane_worktree_safety.py`` (real git, only out-of-git side effects
mocked; the dirty-tree preflight and the worktree-removal chokepoint are
deliberately NOT mocked).
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
from specify_cli.cli.commands.consolidate import _run_lane_based_consolidation
from specify_cli.consolidation.executor import _report_pre_mutation_refusal
from specify_cli.git.destructive_guard import (
    MERGE_UNSAFE_PRIMARY_DIRTY,
    MERGE_UNSAFE_WORKTREE_DIRTY,
    DestructiveOpRefused,
)
from specify_cli.lanes.branch_naming import lane_branch_name, worktree_path
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.consolidation.config import MergeStrategy

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_USER_META = "src/app/meta.json"
_README = "README.md"
_REMEDIATION_TEXT = "Remediation: Commit, stash, or revert the local changes"


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
        "purpose_tldr": "user meta.json dirty-tree safety regression (#4933)",
        "purpose_context": "user meta.json regression fixture",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_lanes_manifest(feature_dir: Path, slug: str) -> LanesManifest:
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


def _write_wp_file(feature_dir: Path, wp_id: str, *, agent: str = "researcher-ryan") -> None:
    """Minimal WP prompt file (mirrors ``test_merge_lane_planning_data_loss.py``)."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{wp_id}.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id} planning\nagent: {agent}\ndependencies: []\n---\n\nBody.\n",
        encoding="utf-8",
    )


def _seed_wp_approved(feature_dir: Path, mission_slug: str, wp_id: str) -> None:
    """Drive a WP to ``approved`` via the real status-emit pipeline so the
    mission is merge-ready (:func:`_assert_mission_terminal_ready`) and the
    dirty-tree preflight is the sole blocker the fixtures below exercise --
    mirrors ``test_merge_lane_planning_data_loss.py``'s helper of the same
    name."""
    from specify_cli.status.emit import emit_status_transition
    from specify_cli.status.models import ReviewResult, TransitionRequest

    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane="planned",
            actor="seed",
            force=True,
            reason="seed",
        )
    )
    for to_lane in ("claimed", "in_progress", "for_review", "in_review"):
        gating = to_lane == "for_review"
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id=wp_id,
                to_lane=to_lane,
                actor="seed",
                force=gating,
                reason="seed: manufacture reviewable state" if gating else None,
            )
        )
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane="approved",
            actor="seed",
            evidence={
                "review": {
                    "reviewer": "reviewer-renata",
                    "verdict": "approved",
                    "reference": f"review-{wp_id}",
                }
            },
            review_result=ReviewResult(
                reviewer="reviewer-renata",
                verdict="approved",
                reference=f"review-{wp_id}",
            ),
        )
    )


def _bootstrap_mission(tmp_path: Path, slug: str) -> Path:
    """Bootstrap a mission ready to consolidate: mission branch + approved lane-a."""
    _init_git_repo(tmp_path)
    feature_dir = tmp_path / "kitty-specs" / slug
    _write_meta(feature_dir, slug)
    _write_lanes_manifest(feature_dir, slug)
    _write_wp_file(feature_dir, "WP01")
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
    # Mission-terminal-ready precondition (#4764): the dirty-tree preflight
    # must be the sole blocker under test, not an incidental WP-readiness
    # refusal, so WP01 is driven to `approved` on the real event log.
    _seed_wp_approved(feature_dir, slug, "WP01")
    return feature_dir


def _add_lane_worktree(tmp_path: Path, slug: str, lane_branch: str) -> Path:
    wt_path = worktree_path(tmp_path, slug, lane_id="lane-a")
    wt_path.parent.mkdir(parents=True, exist_ok=True)
    _git(tmp_path, "worktree", "add", str(wt_path), lane_branch)
    return wt_path


@contextlib.contextmanager
def _real_merge_external_mocks(repo_root: Path):
    """Mock only the side effects that touch state OUTSIDE git.

    Mirrors the Layer-2 harness in ``test_merge_primary_checkout_safety.py`` /
    ``test_merge_lane_worktree_safety.py``. The dirty-tree preflight
    (``_pre_mutation_safety_preflight``) and the worktree-removal chokepoint
    are deliberately NOT mocked -- they are exactly what #4933 is pinning.
    """
    patches = [
        patch("specify_cli.consolidation.done_bookkeeping._mark_wp_merged_done"),
        patch("specify_cli.consolidation.done_bookkeeping._assert_merged_wps_reached_done"),
        patch("specify_cli.consolidation.executor.commit_merge_bookkeeping"),
        patch("specify_cli.post_merge.stale_assertions.run_check"),
        patch("specify_cli.consolidation.executor.run_check"),
        patch("specify_cli.consolidation.executor.require_no_sparse_checkout"),
        patch("specify_cli.cli.commands.consolidate._enforce_git_preflight"),
        patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        patch("specify_cli.policy.config.load_policy_config"),
        patch(
            "specify_cli.consolidation.executor._bake_mission_number_into_mission_branch",
            return_value=None,
        ),
        patch(
            "specify_cli.consolidation.executor._classify_porcelain_lines",
            return_value=([], 0),
        ),
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


def _invoke_merge(tmp_path: Path, slug: str, *, remove_worktree: bool = False, delete_branch: bool = False) -> None:
    with _real_merge_external_mocks(tmp_path):
        _run_lane_based_consolidation(
            repo_root=tmp_path,
            mission_slug=slug,
            push=False,
            delete_branch=delete_branch,
            remove_worktree=remove_worktree,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )


class TestPrimaryCheckoutUserMetaJsonSafety:
    """A dirty user ``src/app/meta.json`` in the root checkout."""

    def test_dirty_user_meta_json_refuses_before_reset(self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin the console width so Rich never wraps the long tmp path across
        # lines -- `cli.console`'s width/wrapping is left to per-invocation
        # `COLUMNS` env detection by design.
        monkeypatch.setenv("COLUMNS", "400")
        slug = "test-user-meta-json-primary-dirty"
        _bootstrap_mission(tmp_path, slug)

        _git(tmp_path, "checkout", "main")
        (tmp_path / "src" / "app").mkdir(parents=True)
        (tmp_path / _USER_META).write_text('{"v": 1}\n', encoding="utf-8")
        _git(tmp_path, "add", _USER_META)
        _git(tmp_path, "commit", "-m", "add user meta.json")
        pre_head = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

        # Modify without committing -- the exact loss shape from #4933.
        (tmp_path / _USER_META).write_text('{"v": 2, "dirty": true}\n', encoding="utf-8")
        dirty_before = _git(tmp_path, "status", "--porcelain").stdout

        with pytest.raises(typer.Exit) as excinfo:
            _invoke_merge(tmp_path, slug)

        assert excinfo.value.exit_code == 1
        captured = capsys.readouterr()
        out = captured.out.replace("\n", " ")
        assert MERGE_UNSAFE_PRIMARY_DIRTY in out
        # The file is named and the real remediation line is printed.
        assert _USER_META in out
        assert _REMEDIATION_TEXT in out
        # On a FRESH consolidation the mission branch is trivially "already
        # an ancestor of HEAD" (it was branched off the target and never
        # advances until the lanes merge), so the lane-ancestry-only
        # classifier misfires BEHIND_OWN_HEAD on every dirty refusal. That
        # must never upgrade to the reset-to-HEAD guidance here -- it would
        # tell the operator to destroy the very edit this refusal protects.
        assert "reset --hard HEAD" not in out

        # Byte-identical to pre-invocation. The edit survives.
        assert _git(tmp_path, "rev-parse", "HEAD").stdout.strip() == pre_head
        assert (tmp_path / _USER_META).read_text() == '{"v": 2, "dirty": true}\n'
        assert _git(tmp_path, "status", "--porcelain").stdout == dirty_before

    def test_two_dirty_user_files_are_aggregated_into_one_refusal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Several dirty user files are listed in one refusal."""
        monkeypatch.setenv("COLUMNS", "400")
        slug = "test-user-meta-json-aggregation"
        _bootstrap_mission(tmp_path, slug)

        _git(tmp_path, "checkout", "main")
        (tmp_path / "src" / "app").mkdir(parents=True)
        (tmp_path / _USER_META).write_text('{"v": 1}\n', encoding="utf-8")
        _git(tmp_path, "add", _USER_META)
        _git(tmp_path, "commit", "-m", "add user meta.json")

        (tmp_path / _USER_META).write_text('{"v": 2}\n', encoding="utf-8")
        (tmp_path / _README).write_text("operator's unrelated in-progress notes\n")

        with pytest.raises(typer.Exit) as excinfo:
            _invoke_merge(tmp_path, slug)

        assert excinfo.value.exit_code == 1
        captured = capsys.readouterr()
        out = captured.out.replace("\n", " ")
        assert MERGE_UNSAFE_PRIMARY_DIRTY in out
        assert _USER_META in out
        assert _README in out
        assert _REMEDIATION_TEXT in out

    def test_dirty_owned_mission_meta_json_still_proceeds(self, tmp_path: Path) -> None:
        """Control: a dirty Spec Kitty-owned mission ``meta.json`` stays
        exempt; consolidation proceeds."""
        slug = "test-owned-meta-json-control"
        feature_dir = _bootstrap_mission(tmp_path, slug)

        _git(tmp_path, "checkout", "main")
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_slug": slug,
                    "mission_number": None,
                    "mission_type": "software-dev",
                    "target_branch": "main",
                    "purpose_tldr": "dirtied for control",
                    "purpose_context": "owned meta.json control",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        # Must NOT raise: the owned meta.json stays exempt.
        _invoke_merge(tmp_path, slug)

        assert (tmp_path / "src" / "foo.py").exists()


class TestLaneWorktreeUserMetaJsonSafety:
    """The same edit inside a lane worktree consolidation would remove."""

    def test_dirty_user_meta_json_in_lane_worktree_refuses_before_removal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("COLUMNS", "400")
        slug = "test-user-meta-json-worktree-dirty"
        _bootstrap_mission(tmp_path, slug)
        lane_branch = lane_branch_name(slug, "lane-a")

        # Track src/app/meta.json ON THE LANE BRANCH so it is a tracked file
        # inside the worktree.
        _commit_file(
            tmp_path,
            branch=lane_branch,
            relpath=_USER_META,
            content='{"v": 1}\n',
            message="track user meta.json on lane branch",
        )
        _git(tmp_path, "checkout", "main")

        wt_path = _add_lane_worktree(tmp_path, slug, lane_branch)
        (wt_path / _USER_META).write_text('{"v": 2, "dirty": true}\n', encoding="utf-8")

        with pytest.raises(typer.Exit) as excinfo:
            _invoke_merge(tmp_path, slug, remove_worktree=True, delete_branch=False)

        assert excinfo.value.exit_code == 1
        captured = capsys.readouterr()
        out = captured.out.replace("\n", " ")
        assert MERGE_UNSAFE_WORKTREE_DIRTY in out
        assert _USER_META in out
        # The worktree is named and the real remediation line is printed.
        assert str(wt_path) in out
        assert _REMEDIATION_TEXT in out

        # The worktree and the edit survive, untouched.
        assert wt_path.exists()
        assert (wt_path / _USER_META).read_text() == '{"v": 2, "dirty": true}\n'

    def test_dirty_owned_mission_meta_json_in_worktree_still_proceeds(self, tmp_path: Path) -> None:
        """Control: a dirty owned ``meta.json`` inside a lane worktree stays
        exempt; the worktree is still removed."""
        slug = "test-owned-meta-json-worktree-control"
        feature_dir = _bootstrap_mission(tmp_path, slug)
        lane_branch = lane_branch_name(slug, "lane-a")
        _git(tmp_path, "checkout", "main")

        wt_path = _add_lane_worktree(tmp_path, slug, lane_branch)
        (wt_path / "kitty-specs" / slug / "meta.json").write_text('{"purpose_tldr": "dirtied inside worktree"}\n', encoding="utf-8")

        _invoke_merge(tmp_path, slug, remove_worktree=True, delete_branch=False)

        assert not wt_path.exists(), "Parity regression: a dirty owned meta.json inside the lane worktree must not block the (still-exempt) removal."
        assert (feature_dir).exists()


class TestReportPreMutationRefusalBehindHeadGuidance:
    """#4933: both branches of the reset-to-HEAD guidance gate.

    ``_report_pre_mutation_refusal``'s reset-to-HEAD guidance (``proven_behind_head
    = remedy.kind is BEHIND_OWN_HEAD and is_pure_behind_head_lag(main_repo,
    base_sha=base_sha)``) must stay ABSENT on a fresh consolidation (the CLI
    tests above) yet still fire when the lag genuinely IS proven -- otherwise
    an over-gated regression (e.g. a call site silently dropping ``base_sha``)
    would go undetected. These probe the
    function DIRECTLY against a real git repo (no mocking of
    ``classify_resume_dirty_remedy`` / ``is_pure_behind_head_lag``), mirroring
    the "real ancestry/diff probes must run for real" house discipline in
    ``test_behind_head_recovery_coverage.py`` / ``test_behind_head_remedy.py``.

    Fixture shape: commit A on ``main``, a lane
    branch with commit B (adds ``f.txt``) off A, then ``git update-ref
    refs/heads/main <B>`` WITHOUT touching the checkout -- so ``main``'s ref
    now points at B while the working tree (and index) still read A's tree.
    That is a pure behind-own-HEAD lag of ``base_sha=A``.
    """

    @staticmethod
    def _build_pure_lag_repo(tmp_path: Path) -> tuple[Path, str, str, str]:
        """Return ``(repo, lane_branch, a_sha, b_sha)`` with ``main`` advanced
        to B via ``update-ref`` while the checkout still reads A's tree."""
        repo = tmp_path / "repo"
        _init_git_repo(repo)
        a_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

        lane_branch = "kitty/lane-a"
        _git(repo, "branch", lane_branch, "main")
        _commit_file(repo, branch=lane_branch, relpath="f.txt", content="hi\n", message="add f.txt")
        b_sha = _git(repo, "rev-parse", lane_branch).stdout.strip()

        _git(repo, "checkout", "main")
        # Advance main's ref to B WITHOUT resetting the checkout -- the pure
        # behind-own-HEAD lag: HEAD/main now names B's tree, but the working
        # tree and index still hold A's (f.txt reads as a staged deletion).
        _git(repo, "update-ref", "refs/heads/main", b_sha)

        return repo, lane_branch, a_sha, b_sha

    @staticmethod
    def _refusal(repo: Path) -> DestructiveOpRefused:
        return DestructiveOpRefused(
            error_code=MERGE_UNSAFE_PRIMARY_DIRTY,
            remediation=f"Commit, stash, or revert the local changes in {repo}, then re-run.",
            worktree_path=repo,
        )

    def test_proven_pure_lag_with_base_sha_prints_reset_guidance(self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
        """(a) A pure lag with ``base_sha`` set to the strict ancestor A: the
        #4982 reset-to-HEAD guidance IS printed."""
        monkeypatch.setenv("COLUMNS", "400")
        repo, lane_branch, a_sha, _b_sha = self._build_pure_lag_repo(tmp_path)

        _report_pre_mutation_refusal(self._refusal(repo), repo, mission_branch=lane_branch, base_sha=a_sha)

        out = capsys.readouterr().out.replace("\n", " ")
        assert "reset --hard HEAD" in out
        assert "Resume recovery guidance" in out

    def test_same_lag_with_no_base_sha_does_not_print_reset_guidance(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(b) The SAME pure lag, but ``base_sha=None`` (a fresh consolidation
        has no persisted state): the guidance is fail-closed ABSENT, and the
        safe commit/stash remedy is present instead."""
        monkeypatch.setenv("COLUMNS", "400")
        repo, lane_branch, _a_sha, _b_sha = self._build_pure_lag_repo(tmp_path)

        _report_pre_mutation_refusal(self._refusal(repo), repo, mission_branch=lane_branch, base_sha=None)

        out = capsys.readouterr().out.replace("\n", " ")
        assert "reset --hard HEAD" not in out
        assert _REMEDIATION_TEXT in out

    def test_lag_plus_genuine_edit_with_base_sha_does_not_print_reset_guidance(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(c) The lag PLUS a genuine user edit (README.md, tracked at A),
        with ``base_sha`` set: the content proof fails (the tree no longer
        matches ``base_sha``), so the guidance is ABSENT even though the
        lane-ancestry classification alone would say BEHIND_OWN_HEAD."""
        monkeypatch.setenv("COLUMNS", "400")
        repo, lane_branch, a_sha, _b_sha = self._build_pure_lag_repo(tmp_path)

        # A genuine edit to a file tracked in A's tree (README.md, from
        # _init_git_repo) -- the working tree now diverges from base_sha=A.
        (repo / _README).write_text("operator's genuine in-progress edit\n", encoding="utf-8")

        _report_pre_mutation_refusal(self._refusal(repo), repo, mission_branch=lane_branch, base_sha=a_sha)

        out = capsys.readouterr().out.replace("\n", " ")
        assert "reset --hard HEAD" not in out
        assert _REMEDIATION_TEXT in out
        # The genuine edit is untouched -- this function only prints, never mutates.
        assert (repo / _README).read_text() == "operator's genuine in-progress edit\n"
