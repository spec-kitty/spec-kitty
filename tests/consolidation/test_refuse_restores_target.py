"""WP07 (mixed-lane-authorship-soundness-01M3M7Y0) — every REFUSE restores the
target (FR-010, operator decision ``01M3MAB8FTDKKVVTXPREK75AEP``: "Rollback on
REFUSE only").

``_phase_reconcile_before_teardown`` runs the S-D reconciliation gate strictly
AFTER ``_phase_commit_and_assert`` — the mission->target advance has already
landed by the time the gate evaluates. A ``FAIL`` (proven tree divergence)
already rolled the target back to its pre-mutation tip via the existing
compare-and-swap helper (:func:`_rollback_target_after_failed_reconciliation`).
A ``REFUSE`` (fail-closed claim integrity — the claim could not even be
evaluated) historically skipped that restore, leaving the already-advanced
target stranded on a state the gate never verified. This suite drives the real
gate (not just the CAS helper in isolation, which
``TestRollbackTargetAfterFailedReconciliation`` in
``test_merge_state_authority.py`` already covers) end to end for every verdict
axis: REFUSE restores, FAIL restores (unchanged), PASS never rolls back, a
REFUSE whose target moved elsewhere warns instead of overwriting (CAS
fail-safe), and a REFUSE with an unknown pre-mutation tip is a no-op.

Real fixtures throughout (on-disk git repo in ``tmp_path``, real git refs) —
no mocking of git itself; only ``MergeOutcomeVerifier.verify`` is patched to
force the verdict under test, mirroring how the WP prompt drives the gate.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

from specify_cli.consolidation import executor as ex
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    Divergence,
    VerifyResult,
)
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.lanes.models import ExecutionLane, LanesManifest

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


# ---------------------------------------------------------------------------
# Real-fixture helpers (mirrors tests/consolidation/test_merge_state_authority.py)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _init_repo(root: Path, *, default_branch: str = "main") -> Path:
    """Initialise a real git repo with a single commit on *default_branch*."""
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-qb", default_branch, str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "README.md").write_text("init\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "init")
    return root


def _rev(repo: Path, ref: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", ref],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _commit_on(repo: Path, branch: str, filename: str, body: str) -> str:
    """Add a commit on *branch* (checks it out) and return the new tip SHA."""
    _git(repo, "checkout", "-q", branch)
    (repo / filename).write_text(body, encoding="utf-8")
    _git(repo, "add", filename)
    _git(repo, "commit", "-qm", f"work: {filename}")
    return _rev(repo, branch)


def _build_run(repo: Path, *, target: str, pre_sha: str | None) -> ex._MergeRunState:
    """A minimal, real ``_MergeRunState`` that reaches
    ``_phase_reconcile_before_teardown`` without touching any mutating phase.

    ``is_resume=False`` keeps ``_resume_reconciliation_already_passed`` a
    guaranteed ``False`` (no persisted CAS anchor to fall through), and a
    non-``None`` ``approved_wp_set`` keeps ``_reconciliation_claim_for_gate``
    from rebuilding a claim via git probes the test never sets up — the
    verdict itself is forced via a patched ``MergeOutcomeVerifier.verify``.
    """
    manifest = LanesManifest(
        version=1,
        mission_slug="m",
        mission_id="01M5007A" + "0" * 18,
        mission_branch="kitty/mission-m",
        target_branch=target,
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/wp01.py",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-01-01T00:00:00+00:00",
        computed_from="test",
    )
    state = ConsolidationState(
        mission_id=manifest.mission_id,
        mission_slug="m",
        target_branch=target,
        wp_order=["WP01"],
    )
    run = ex._MergeRunState(
        main_repo=repo,
        mission_slug="m",
        canonical_id=manifest.mission_id,
        canonical_mission_id=manifest.mission_id,
        feature_dir=repo / "kitty-specs" / "m",
        target_feature_dir=repo / "kitty-specs" / "m",
        lanes_manifest=manifest,
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=False,
        remove_worktree=False,
        strategy=MergeStrategy.MERGE,
        assume_yes=True,
        planning_artifact_only=False,
        state=state,
        is_resume=False,
    )
    run.target_expected_old_sha = pre_sha
    run.approved_wp_set = ApprovedWpCommitSet()
    return run


def _force_verdict(monkeypatch: pytest.MonkeyPatch, result: VerifyResult) -> None:
    """Patch ``MergeOutcomeVerifier.verify`` to always return *result*."""
    monkeypatch.setattr(
        ex.MergeOutcomeVerifier,
        "verify",
        lambda self, target_ref, claim: result,
    )


# ---------------------------------------------------------------------------
# T033 (red-first) / T035 — every verdict axis through the real gate
# ---------------------------------------------------------------------------


class TestRefuseRestoresTarget:
    def test_refuse_restores_the_target_to_its_pre_mutation_tip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T033: a REFUSE must restore the target exactly as a FAIL does.

        RED on the base: the pre-fix gate only rolled back on FAIL, so
        ``_rev(repo, "main") == pre_sha`` fails here (the target stays
        advanced) even though ``typer.Exit(1)`` is still raised.
        """
        repo = _init_repo(tmp_path / "repo", default_branch="main")
        pre_sha = _rev(repo, "main")
        advanced = _commit_on(repo, "main", "mutated.py", "landed before the gate ran\n")
        assert advanced != pre_sha
        run = _build_run(repo, target="main", pre_sha=pre_sha)
        _force_verdict(monkeypatch, VerifyResult.refused("claim surface unresolved"))

        with pytest.raises(typer.Exit) as exc_info:
            ex._phase_reconcile_before_teardown(run)

        assert exc_info.value.exit_code == 1
        assert _rev(repo, "main") == pre_sha

    def test_fail_restores_the_target_unchanged_behaviour(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """FAIL already rolled back pre-fix; this is a same-shape regression
        guard exercised through the real gate (the CAS helper itself is
        directly covered by
        ``TestRollbackTargetAfterFailedReconciliation`` in
        ``test_merge_state_authority.py``)."""
        repo = _init_repo(tmp_path / "repo", default_branch="main")
        pre_sha = _rev(repo, "main")
        _commit_on(repo, "main", "mutated.py", "landed before the gate ran\n")
        run = _build_run(repo, target="main", pre_sha=pre_sha)
        _force_verdict(
            monkeypatch,
            VerifyResult.failed(Divergence(missing_approved=(("WP01", "a" * 40),))),
        )

        with pytest.raises(typer.Exit) as exc_info:
            ex._phase_reconcile_before_teardown(run)

        assert exc_info.value.exit_code == 1
        assert _rev(repo, "main") == pre_sha

    def test_pass_never_rolls_back(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = _init_repo(tmp_path / "repo", default_branch="main")
        pre_sha = _rev(repo, "main")
        advanced = _commit_on(repo, "main", "mutated.py", "legitimately landed\n")
        run = _build_run(repo, target="main", pre_sha=pre_sha)
        _force_verdict(monkeypatch, VerifyResult.passed())
        monkeypatch.setattr(ex, "_assert_squash_projected_content_landed", lambda _run: None)

        ex._phase_reconcile_before_teardown(run)

        assert _rev(repo, "main") == advanced

    def test_refuse_when_target_moved_elsewhere_warns_not_overwrites(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CAS fail-safe: if the target advanced PAST the point the CAS
        restore observed as current (a third party moved it again), the
        restore must not clobber that newer tip — it warns instead."""
        repo = _init_repo(tmp_path / "repo", default_branch="main")
        pre_sha = _rev(repo, "main")
        advanced = _commit_on(repo, "main", "mutated.py", "landed before the gate ran\n")
        run = _build_run(repo, target="main", pre_sha=pre_sha)
        _force_verdict(monkeypatch, VerifyResult.refused("claim surface unresolved"))

        # Simulate the ref moving AGAIN between the rollback helper's own
        # ``current_sha`` read (== ``advanced``) and its CAS write, by racing a
        # further commit onto the target right before the real restore call —
        # the real restore's own CAS then observes a stale expected-current
        # value and fails safe rather than overwriting the newer tip.
        real_restore = ex.restore_branch_ref
        raced_sha: str | None = None

        def _racing_restore(repo_arg, branch, new_sha, *, expected_current_sha):
            nonlocal raced_sha
            raced_sha = _commit_on(repo_arg, branch, "raced.py", "moved again after the read\n")
            return real_restore(repo_arg, branch, new_sha, expected_current_sha=expected_current_sha)

        monkeypatch.setattr(ex, "restore_branch_ref", _racing_restore)

        with pytest.raises(typer.Exit) as exc_info:
            ex._phase_reconcile_before_teardown(run)

        assert exc_info.value.exit_code == 1
        assert raced_sha is not None
        # The CAS-guarded restore must fail safe and leave the raced (newest)
        # tip in place rather than force-overwrite it back to pre_sha.
        assert _rev(repo, "main") == raced_sha
        assert _rev(repo, "main") not in (pre_sha, advanced)

    def test_refuse_with_unknown_pre_mutation_tip_is_a_noop(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = _init_repo(tmp_path / "repo", default_branch="main")
        advanced = _commit_on(repo, "main", "mutated.py", "landed before the gate ran\n")
        run = _build_run(repo, target="main", pre_sha=None)
        _force_verdict(monkeypatch, VerifyResult.refused("claim surface unresolved"))

        with pytest.raises(typer.Exit) as exc_info:
            ex._phase_reconcile_before_teardown(run)

        assert exc_info.value.exit_code == 1
        assert _rev(repo, "main") == advanced
