"""Unit tests for the shared claim-integrity predicate (#5338).

``claim_integrity_refusal`` is the single claim-integrity authority used at claim
time; ``MergeOutcomeVerifier.verify`` applies the same three checks at gate time.
The parity tests pin both to the same verdict and text over real git.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    MergeOutcomeVerifier,
    VerifyStatus,
    claim_integrity_refusal,
)
from specify_cli.consolidation import phase_claim
from specify_cli.consolidation.run_state import _MergeRunState
from specify_cli.consolidation.state import ConsolidationState
from tests.consolidation.executor_family import setattr_executor_family

pytestmark = [pytest.mark.git_repo]

_TARGET = "main"
_SURFACE_TEXT = "coordination surface is unresolved or unmaterialized"


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-qb", _TARGET, str(repo)], check=True)
    for key, value in (("user.email", "t@t.co"), ("user.name", "Claim Test"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    return repo


def _healthy() -> ApprovedWpCommitSet:
    return ApprovedWpCommitSet(approved={"WP01": ("a" * 40,)}, manifest_wp_ids=frozenset({"WP01"}), surface_resolved=True)


def test_explicit_refusal_text_is_returned() -> None:
    claim = ApprovedWpCommitSet(refusal="approved lane lane-a: branch missing", manifest_wp_ids=frozenset({"WP01"}))
    assert claim_integrity_refusal(claim) == "approved lane lane-a: branch missing"


def test_unresolved_surface_is_refused() -> None:
    claim = ApprovedWpCommitSet(approved={"WP01": ("a" * 40,)}, manifest_wp_ids=frozenset({"WP01"}), surface_resolved=False)
    assert claim_integrity_refusal(claim) == _SURFACE_TEXT


def test_vacuous_claim_against_manifest_is_refused() -> None:
    claim = ApprovedWpCommitSet(approved={}, manifest_wp_ids=frozenset({"WP01", "WP02"}), surface_resolved=True)
    assert claim_integrity_refusal(claim) == "derived claim is empty while the manifest lists 2 WP(s)"


def test_healthy_claim_has_no_refusal() -> None:
    assert claim_integrity_refusal(_healthy()) is None


def test_empty_claim_with_empty_manifest_is_not_vacuous() -> None:
    assert claim_integrity_refusal(ApprovedWpCommitSet(surface_resolved=True)) is None


def test_explicit_refusal_wins_over_other_reasons() -> None:
    claim = ApprovedWpCommitSet(refusal="explicit", manifest_wp_ids=frozenset({"WP01"}), surface_resolved=False)
    assert claim_integrity_refusal(claim) == "explicit"


@pytest.mark.parametrize(
    "claim",
    [
        ApprovedWpCommitSet(refusal="explicit reason", manifest_wp_ids=frozenset({"WP01"})),
        ApprovedWpCommitSet(approved={"WP01": ("a" * 40,)}, manifest_wp_ids=frozenset({"WP01"}), surface_resolved=False),
        ApprovedWpCommitSet(approved={}, manifest_wp_ids=frozenset({"WP01"}), surface_resolved=True),
    ],
    ids=["explicit-refusal", "unresolved-surface", "vacuous"],
)
def test_predicate_and_gate_agree_on_refusing_claims(tmp_path: Path, claim: ApprovedWpCommitSet) -> None:
    """Parity: the predicate is non-None exactly when verify() REFUSEs on steps 1-3, with the same text."""
    repo = _init_repo(tmp_path)
    reason = claim_integrity_refusal(claim)
    result = MergeOutcomeVerifier(repo).verify(_TARGET, claim)
    assert reason is not None
    assert result.status is VerifyStatus.REFUSE
    assert result.refusal_reason == reason


def test_predicate_and_gate_agree_on_a_healthy_claim(tmp_path: Path) -> None:
    """A claim the predicate passes must not be REFUSEd by the claim-integrity steps of verify()."""
    repo = _init_repo(tmp_path)
    claim = ApprovedWpCommitSet(surface_resolved=True)
    assert claim_integrity_refusal(claim) is None
    assert MergeOutcomeVerifier(repo).verify(_TARGET, claim).status is not VerifyStatus.REFUSE


# ------------------------------------------------ claim-time refusal text (slice-10 F4)


_MISSION = "kitty/mission-x"
_GONE = "kitty/mission-gone"


def _git_out(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _earlier_attempt(
    tmp_path: Path, *, is_resume: bool, moved: tuple[str, ...], recorded: tuple[str, ...], vanished: tuple[str, ...]
) -> tuple[_MergeRunState, str]:
    """A run whose persisted state carries a pre-run snapshot of a real repo, in which ``moved`` branches have advanced since.

    ``recorded`` names the branches that also hold a post-mutation tip (a phase exited after moving them);
    ``vanished`` are snapshotted branches that do not resolve. Returns the run and the target's pre-run SHA.
    """
    repo = _init_repo(tmp_path)
    pre = _git_out(repo, "rev-parse", "HEAD")
    _git_out(repo, "branch", _MISSION)
    state = ConsolidationState(mission_id="m", mission_slug="m", target_branch=_TARGET, wp_order=["WP01"])
    state.pre_mutation_refs = {_TARGET: pre, _MISSION: pre, **dict.fromkeys(vanished, pre)}
    for branch in moved:
        _git_out(repo, "update-ref", f"refs/heads/{branch}", _git_out(repo, "commit-tree", "-p", pre, "-m", branch, f"{pre}^{{tree}}"))
    state.post_mutation_refs = {branch: _git_out(repo, "rev-parse", branch) for branch in recorded}
    run = SimpleNamespace(main_repo=repo, state=state, is_resume=is_resume, recorded_attestations=(), lanes_manifest=SimpleNamespace(target_branch=_TARGET))
    return cast("_MergeRunState", run), pre


def _claim_refusal_output(monkeypatch: pytest.MonkeyPatch, attested: tuple[str, ...], *, run: _MergeRunState | None = None) -> str:
    from unittest.mock import MagicMock

    import typer

    console = MagicMock()
    setattr_executor_family(monkeypatch, "console", console)

    def refuse() -> None:
        if run is None:
            phase_claim._exit_on_claim_integrity_refusal("approved lane branch is gone.", attested=attested)
        phase_claim._refuse_claim_before_mutation(run, "approved lane branch is gone.")

    with pytest.raises(typer.Exit) as exited:
        refuse()
    assert exited.value.exit_code == 1
    return " ".join(str(call.args[0]) for call in console.print.call_args_list)


@pytest.mark.parametrize(
    ("is_resume", "moved", "recorded", "vanished", "present", "absent"),
    [
        pytest.param(
            False,
            (_TARGET, _MISSION),
            (),
            (),
            ["at claim time, before any change:", "No branch, worktree or status record was changed by this run."],
            ["attestation", "currently holds", "NOT restored"],
            id="fresh_run",
        ),
        pytest.param(
            True,
            (_TARGET, _MISSION),
            (_TARGET, _MISSION),
            (),
            [
                "Run `spec-kitty consolidate --abort` to restore the branches it recorded.",
                f"That attempt already moved {_MISSION}, {_TARGET} (the local target '{_TARGET}' currently holds content from it).",
            ],
            ["before any change", "No branch, worktree or status record was changed", "NOT restored", "could not be resolved"],
            id="resume_moved_with_a_recorded_post_tip",
        ),
        pytest.param(
            True,
            (_TARGET, _MISSION),
            (_MISSION,),
            (),
            [
                "Run `spec-kitty consolidate --abort` to restore the branches it recorded.",
                f"That attempt already moved {_MISSION}, {_TARGET} (the local target '{_TARGET}' currently holds content from it).",
                f"`spec-kitty consolidate --abort` will report {_TARGET} (restore target {{pre}}) as NOT restored: the attempt was interrupted before it",
                "recorded where it stopped.",
                f"Restore the local target '{_TARGET}' to {{pre}} yourself before re-running.",
            ],
            ["before any change", "No branch, worktree or status record was changed", f"{_MISSION} (restore target"],
            id="resume_target_moved_but_killed_before_a_post_tip_was_recorded",
        ),
        pytest.param(
            True,
            (),
            (),
            (_GONE,),
            [
                "Run `spec-kitty consolidate --abort` to restore the branches it recorded.",
                f"The current tip of {_GONE} could not be resolved, so whether that attempt moved it is unknown.",
            ],
            ["before any change", "No branch, worktree or status record was changed", "already moved", "NOT restored"],
            id="resume_with_an_unresolvable_tip",
        ),
        pytest.param(
            True,
            (),
            (),
            (),
            ["at claim time, before any change:", "if an earlier attempt left partial state, run `spec-kitty consolidate --abort` first."],
            ["already moved", "NOT restored"],
            id="resume_that_nothing_moved",
        ),
    ],
)
def test_claim_refusal_says_what_the_run_changed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    is_resume: bool,
    moved: tuple[str, ...],
    recorded: tuple[str, ...],
    vanished: tuple[str, ...],
    present: list[str],
    absent: list[str],
) -> None:
    """A fresh run changed nothing; a refused resume leads with ``--abort`` and says what ``--abort`` will not restore, judged from the pre-run snapshot."""
    run, pre = _earlier_attempt(tmp_path, is_resume=is_resume, moved=moved, recorded=recorded, vanished=vanished)
    printed = _claim_refusal_output(monkeypatch, (), run=run)
    for text in present:
        assert text.format(pre=pre) in printed
    for text in absent:
        assert text not in printed


def test_claim_refusal_after_recorded_attestations_names_them(monkeypatch: pytest.MonkeyPatch) -> None:
    """F4: ``--attest-canceled-superseded`` writes status events BEFORE the claim; the text must not deny it."""
    printed = _claim_refusal_output(monkeypatch, ("WP03", "WP04"))
    assert "No branch, worktree or status record was changed" not in printed
    assert "No branch or worktree was changed by this run; only the operator attestation(s) for WP03, WP04 were recorded." in printed


def test_claim_refusal_prints_commands_unwrapped_and_paths_unparsed(monkeypatch: pytest.MonkeyPatch) -> None:
    """#5668: a captured console must not split a recovery command, and a ``[/slug]`` path must not be read as markup."""
    import io

    import typer
    from rich.console import Console

    from specify_cli.consolidation.approved_bound import BoundRefusal, BoundRefusalCode

    out = io.StringIO()
    setattr_executor_family(monkeypatch, "console", Console(file=out, width=80, force_terminal=False))
    slug = "a-rather-long-mission-slug-for-the-recovery-command-01M444QR"
    refusal = BoundRefusal(
        code=BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL,
        lane_id="lane-a",
        branch="kitty/mission-x-lane-a",
        wp_ids=("WP01",),
        commits=("a" * 40,),
        path="src/[/slug]/x.py",
    ).render(slug)

    with pytest.raises(typer.Exit):
        phase_claim._exit_on_claim_integrity_refusal(refusal)

    printed = out.getvalue()
    assert f"spec-kitty agent tasks move-task WP01 --to in_progress --mission {slug}\n" in printed
    assert "src/[/slug]/x.py" in printed
    assert "\nNo branch, worktree or status record was changed by this run." in printed


def _intent_proven(run: _MergeRunState, branch: str, pre: str) -> str:
    """Persist an advance-intent chain proving this run wrote ``branch``'s live tip (a kill before the phase recorder)."""
    live = _git_out(run.main_repo, "rev-parse", branch)
    run.state.advance_intents[branch] = [pre, live]
    return live


def test_claim_refusal_does_not_list_an_intent_proven_landing_as_unrestorable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """P2: ``--abort`` adopts a provable kill-left advance (the rollback's own predicate), so the text must not call it NOT restored."""
    run, pre = _earlier_attempt(tmp_path, is_resume=True, moved=(_TARGET, _MISSION), recorded=(_MISSION,), vanished=())
    _intent_proven(run, _TARGET, pre)

    printed = _claim_refusal_output(monkeypatch, (), run=run)

    assert f"That attempt already moved {_MISSION}, {_TARGET}" in printed
    assert "NOT restored" not in printed and "yourself" not in printed, printed


def test_claim_refusal_names_the_records_restore_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """P2: an unrecorded move is still listed, against the record's restore target (not the snapshot)."""
    run, pre = _earlier_attempt(tmp_path, is_resume=True, moved=(_MISSION,), recorded=(_MISSION,), vanished=())
    anchor = _git_out(run.main_repo, "commit-tree", "-p", pre, "-m", "operator", f"{pre}^{{tree}}")
    landed = _git_out(run.main_repo, "commit-tree", "-p", anchor, "-m", "landing", f"{pre}^{{tree}}")
    _git_out(run.main_repo, "update-ref", f"refs/heads/{_TARGET}", landed)
    run.state.restore_targets = {_TARGET: anchor}

    printed = _claim_refusal_output(monkeypatch, (), run=run)

    assert f"will report {_TARGET} (restore target {anchor}) as NOT restored" in printed, printed
    assert f"Restore the local target '{_TARGET}' to {anchor} yourself" in printed, printed
    assert pre not in printed, "the snapshot is not the restore target here"


def test_claim_refusal_does_not_list_a_branch_back_at_its_restore_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """P2: a branch at its restore target (an A2 re-anchor away from the snapshot) is not moved by an earlier attempt."""
    run, pre = _earlier_attempt(tmp_path, is_resume=True, moved=(_TARGET,), recorded=(), vanished=())
    run.state.restore_targets = {_TARGET: _git_out(run.main_repo, "rev-parse", _TARGET)}

    printed = _claim_refusal_output(monkeypatch, (), run=run)

    assert "already moved" not in printed and "NOT restored" not in printed, printed
