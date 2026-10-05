"""Unit tests for the shared claim-integrity predicate (#5338).

``claim_integrity_refusal`` is the single claim-integrity authority used at claim
time; ``MergeOutcomeVerifier.verify`` applies the same three checks at gate time.
The parity tests pin both to the same verdict and text over real git.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    MergeOutcomeVerifier,
    VerifyStatus,
    claim_integrity_refusal,
)
from specify_cli.consolidation import phase_claim
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


def _claim_refusal_output(monkeypatch: pytest.MonkeyPatch, attested: tuple[str, ...], *, earlier_moved: tuple[str, ...] = ()) -> str:
    from unittest.mock import MagicMock

    import typer

    console = MagicMock()
    setattr_executor_family(monkeypatch, "console", console)
    with pytest.raises(typer.Exit) as exited:
        phase_claim._exit_on_claim_integrity_refusal("approved lane branch is gone.", attested=attested, earlier_moved=earlier_moved, target_branch=_TARGET)
    assert exited.value.exit_code == 1
    return " ".join(str(call.args[0]) for call in console.print.call_args_list)


@pytest.mark.parametrize(
    ("earlier_moved", "present", "absent"),
    [
        pytest.param(
            (),
            ["at claim time, before any change:", "No branch, worktree or status record was changed by this run."],
            ["attestation", "currently holds"],
            id="fresh_run",
        ),
        pytest.param(
            (_TARGET, "kitty/mission-x"),
            [
                "Run `spec-kitty consolidate --abort` to restore the branches it recorded.",
                f"That attempt already moved {_TARGET}, kitty/mission-x (the local target '{_TARGET}' currently holds content from it).",
            ],
            ["before any change", "No branch, worktree or status record was changed"],
            id="resume_after_the_target_moved",
        ),
    ],
)
def test_claim_refusal_says_what_the_run_changed(monkeypatch: pytest.MonkeyPatch, earlier_moved: tuple[str, ...], present: list[str], absent: list[str]) -> None:
    """A fresh run changed nothing; a refused resume leads with ``--abort`` because an earlier attempt already moved the target."""
    printed = _claim_refusal_output(monkeypatch, (), earlier_moved=earlier_moved)
    for text in present:
        assert text in printed
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
