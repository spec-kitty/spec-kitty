"""Unit coverage for the #5783 retarget verdict and the write-checkout probe it reads.

The end-to-end arms (lanes and coord, ``--dry-run``, ``orchestrator-api``) live in
``tests/terminus/test_target_override_recorded_target_unwritable.py`` and
``tests/orchestrator_api/test_consolidate_mission_protected_target.py``; these pin each
branch of the two functions directly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation import preflight
from specify_cli.coordination import transaction
from specify_cli.coordination.types import STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH, Refused

pytestmark = [pytest.mark.fast]

_HOLD = Refused(
    error_code=STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH,
    message="the status write checkout /repo is on branch 'develop', not on the write branch 'main'.",
    destination_ref="main",
    next_step="checkout main",
)


def _fail_if_called(*_args: object, **_kwargs: object) -> Refused | None:
    raise AssertionError("restating the recorded target must not probe the write checkout")


def test_restating_the_recorded_target_is_not_a_retarget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transaction, "write_checkout_refusal", _fail_if_called)

    assert preflight.refuse_unwritable_recorded_target(Path("/repo"), "m", recorded_target="main", effective_target="main") is None


def test_a_retarget_whose_recorded_target_is_writable_is_not_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def _writable(_repo: Path, _slug: str, ref: str, *, operation: str) -> Refused | None:
        seen.append(ref)
        return None

    monkeypatch.setattr(transaction, "write_checkout_refusal", _writable)

    assert preflight.refuse_unwritable_recorded_target(Path("/repo"), "m", recorded_target="main", effective_target="develop") is None
    assert seen == ["main"], "the probe judges the RECORDED target, never --target"


def test_a_retarget_whose_recorded_target_is_unwritable_is_refused_with_its_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transaction, "write_checkout_refusal", lambda *_a, **_k: _HOLD)

    verdict = preflight.refuse_unwritable_recorded_target(Path("/repo"), "m", recorded_target="main", effective_target="develop")

    assert verdict is not None
    assert verdict.error_code == preflight.TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE == "TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE"
    assert verdict.destination_ref == "main"
    assert _HOLD.message in verdict.message, "the hold check's own reason is carried"
    assert "'--target develop'" in verdict.message
    for remedy in ("Drop '--target develop'", "git checkout main", "meta.json"):
        assert remedy in verdict.next_step, verdict.next_step


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo_on_develop(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "init")
    _git(repo, "checkout", "-qb", "develop")
    return repo


def test_write_checkout_refusal_reads_the_seam_checkout_branch(repo_on_develop: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    probed: list[tuple[str, str]] = []

    def _holder(repo_root: Path, mission_slug: str, destination_ref: str, **_kw: object) -> Path:
        probed.append((mission_slug, destination_ref))
        return repo_root

    monkeypatch.setattr(transaction, "_primary_partition_holder", _holder)

    refused = transaction.write_checkout_refusal(repo_on_develop, "m", "main", operation="consolidation bookkeeping for m")
    held = transaction.write_checkout_refusal(repo_on_develop, "m", "develop", operation="consolidation bookkeeping for m")

    assert probed == [("m", "main"), ("m", "develop")]
    assert refused is not None and refused.error_code == STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH
    assert "'develop'" in refused.message and "'main'" in refused.message
    assert held is None
