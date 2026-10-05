"""WP07 (mixed-lane-authorship-soundness-01M3M7Y0) — every REFUSE restores the
target (FR-010, operator decision ``01M3MAB8FTDKKVVTXPREK75AEP``: "Rollback on
REFUSE only"), re-pinned to the single rollback door for #5666.

``_phase_reconcile_before_teardown`` runs the S-D reconciliation gate strictly
AFTER ``_phase_commit_and_assert`` — the mission->target advance has already
landed by the time the gate evaluates, so a FAIL and a REFUSE must both roll the
target back. Since #5666 the gate itself moves nothing: it raises
``typer.Exit(1)`` and the driver's single rollback door (#5385,
``executor._report_rollback`` -> ``rollback_to_snapshot``) restores the target,
compare-and-swapping against the post tip THIS run recorded. The retired gate
helper used the LIVE tip as its expected value, so it discarded any commit
another actor landed on top of the landing.

Each case below pins both halves: the real gate leaves the target where it is,
and the door, given the snapshot and the recorded post tip a real run persists,
restores it, keeps a foreign commit (NOT restored, moved by another actor) or
says nothing was rolled back when no snapshot exists.

Real fixtures throughout (on-disk git repo in ``tmp_path``, real git refs) —
no mocking of git itself; only ``MergeOutcomeVerifier.verify`` is patched to
force the verdict under test. The end-to-end door runs live in
``tests/terminus/test_rollback_door.py`` and
``tests/consolidation/test_rollback_anchor_p0_repro.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

from specify_cli.consolidation import executor as ex
from specify_cli.consolidation.rollback import begin_attempt, capture_pre_mutation_snapshot, record_post_mutation_tips
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    Divergence,
    VerifyResult,
)
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.consolidation import phase_gate

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
    (root / ".gitignore").write_text(".kittify/runtime/\n", encoding="utf-8")  # merge state is never tracked
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
        phase_gate.MergeOutcomeVerifier,
        "verify",
        lambda self, target_ref, claim: result,
    )


def _claim_snapshot(repo: Path, run: ex._MergeRunState) -> None:
    """What the claim persists before the first mutation: the snapshot and the attempt's restore targets."""
    capture_pre_mutation_snapshot(repo, run.state, run.lanes_manifest, coord_ref=None)
    begin_attempt(repo, run.state)


def _land(repo: Path, run: ex._MergeRunState) -> str:
    """This run's landing on ``main``, recorded as its post tip exactly as the phase recorder does."""
    advanced = _commit_on(repo, "main", "mutated.py", "landed before the gate ran\n")
    record_post_mutation_tips(repo, run.state)
    return advanced


def _door(run: ex._MergeRunState, capsys: pytest.CaptureFixture[str]) -> str:
    """Run the single rollback door's body and return its flattened report."""
    capsys.readouterr()
    ex._report_rollback(run, anchor_before=None)
    return " ".join(capsys.readouterr().out.split())


def _gate_refuses(run: ex._MergeRunState) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        ex._phase_reconcile_before_teardown(run)
    assert exc_info.value.exit_code == 1


_REFUSED = VerifyResult.refused("claim surface unresolved")
_FAILED = VerifyResult.failed(Divergence(missing_approved=(("WP01", "a" * 40),)))


# ---------------------------------------------------------------------------
# Every verdict axis: the gate moves nothing, the door restores
# ---------------------------------------------------------------------------


class TestRefuseRestoresTarget:
    @pytest.mark.parametrize("verdict", [_REFUSED, _FAILED], ids=["refuse", "fail"])
    def test_gate_moves_nothing_and_the_door_restores_the_pre_mutation_tip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], verdict: VerifyResult
    ) -> None:
        """T033 / #5666: a REFUSE restores the target exactly as a FAIL does, through the door only."""
        repo = _init_repo(tmp_path / "repo", default_branch="main")
        pre_sha = _rev(repo, "main")
        run = _build_run(repo, target="main", pre_sha=pre_sha)
        _claim_snapshot(repo, run)
        advanced = _land(repo, run)
        _force_verdict(monkeypatch, verdict)

        _gate_refuses(run)
        assert _rev(repo, "main") == advanced, "#5666: the gate itself must move no ref; the door restores"

        report = _door(run, capsys)
        assert _rev(repo, "main") == pre_sha, f"the door must restore the target. report={report}"
        assert f"restored main {advanced[:7]} -> {pre_sha[:7]}" in report, report

    def test_pass_never_rolls_back(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = _init_repo(tmp_path / "repo", default_branch="main")
        pre_sha = _rev(repo, "main")
        advanced = _commit_on(repo, "main", "mutated.py", "legitimately landed\n")
        run = _build_run(repo, target="main", pre_sha=pre_sha)
        _force_verdict(monkeypatch, VerifyResult.passed())
        monkeypatch.setattr(phase_gate, "_assert_squash_projected_content_landed", lambda _run: None)

        ex._phase_reconcile_before_teardown(run)

        assert _rev(repo, "main") == advanced

    def test_refuse_when_target_moved_elsewhere_keeps_the_foreign_commit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """#5666 per-PR guard: a commit another actor landed after this run's recorded post tip survives."""
        repo = _init_repo(tmp_path / "repo", default_branch="main")
        pre_sha = _rev(repo, "main")
        run = _build_run(repo, target="main", pre_sha=pre_sha)
        _claim_snapshot(repo, run)
        advanced = _land(repo, run)
        foreign = _commit_on(repo, "main", "teammate.py", "a teammate landed on top\n")
        _force_verdict(monkeypatch, _REFUSED)

        _gate_refuses(run)
        assert _rev(repo, "main") == foreign, "#5666: the gate must not reset the target over the foreign commit"

        report = _door(run, capsys)
        assert _rev(repo, "main") == foreign, f"the door must keep the foreign commit. report={report}"
        assert "NOT restored main" in report and "moved by another actor" in report, report
        assert advanced[:7] in report, f"the report must name this run's recorded post tip as the expected value. report={report}"

    def test_refuse_with_unknown_pre_mutation_tip_rolls_nothing_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No snapshot recorded: the gate moves nothing and the door says nothing was rolled back."""
        repo = _init_repo(tmp_path / "repo", default_branch="main")
        advanced = _commit_on(repo, "main", "mutated.py", "landed before the gate ran\n")
        run = _build_run(repo, target="main", pre_sha=None)
        _force_verdict(monkeypatch, _REFUSED)

        _gate_refuses(run)
        report = _door(run, capsys)

        assert _rev(repo, "main") == advanced
        assert "Nothing was rolled back" in report, report
