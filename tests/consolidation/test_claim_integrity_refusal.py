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
