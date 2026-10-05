"""Red-first regression: create-time meta commit destination (WP02 T006 / C-006).

``_commit_feature_file`` (``core/mission_creation.py``) commits the freshly
written ``meta.json`` via ``CommitTarget(ref=current_branch)`` -- deriving the
commit destination from the operator's CURRENT CHECKOUT rather than the
mission's placement-seam-resolved home (research.md D5, the create-time
split-brain root; this is the highest-leverage unowned target the whole
mission's Context section blames).

Under a coord-routing mission whose explicit ``target_branch`` differs from
the checkout (a legitimate ``mission create --target-branch design/coord-target``
invocation while the operator stays parked on ``main``), the metadata commit
lands on ``main`` instead of the mission's actual primary home
``design/coord-target`` -- a real data-integrity bug: ``meta.json`` itself
declares ``target_branch: design/coord-target`` but its own git history lives
on ``main``.

This test drives the real ``create_mission_core`` entry point end-to-end
(not ``_commit_feature_file`` directly, per the WP) with the REAL
``safe_commit`` (#5634: formerly a capturing fake). The destination the
create hands ``safe_commit`` is observable in what the real commit does with
it: ``safe_commit`` refuses a HEAD/destination mismatch (and a protected
branch) by naming the ``destination_ref``, the create discloses that refusal
as the bootstrap-skip log line, and nothing lands on the operator's checkout.

RED pre-fix: the destination is ``"main"`` (the checkout) -- the protected
refusal names ``'main'``. GREEN post-fix (T007): the destination is
``"design/coord-target"`` (the seam-resolved PRIMARY_METADATA/SPEC home), so
the refusal is the HEAD mismatch naming it, matching parity for both coord
and non-coord topologies (T008).
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import create_mission_core

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CORE_MODULE = "specify_cli.core.mission_creation"
_CHECKOUT_BRANCH = "main"
_TARGET_BRANCH = "design/coord-target"


@pytest.fixture(autouse=True)
def _cwd_outside_any_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The worktree-context guard reads the real process cwd, and pytest may run
    from inside a lane worktree. Run each test from its ``tmp_path`` so the real
    guard sees a non-worktree directory (no patch)."""
    monkeypatch.chdir(tmp_path)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_git_repo(repo: Path) -> None:
    kittify_dir = repo / ".kittify"
    kittify_dir.mkdir(exist_ok=True)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    # WP04 fail-closed (C-A1): create_mission_core requires a non-empty
    # activated mission-type set for the default software-dev resolution
    # exercised throughout this file.
    (kittify_dir / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )
    _git(repo, "init", "-q", "-b", _CHECKOUT_BRANCH)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "commit", "-m", "init", "--allow-empty")
    # The mission's real target branch exists as a ref but is NEVER checked
    # out -- the operator stays parked on _CHECKOUT_BRANCH throughout create.
    _git(repo, "branch", _TARGET_BRANCH, _CHECKOUT_BRANCH)


def _mission_summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ").strip() or "test mission"
    return {
        "friendly_name": title.title(),
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (
            f"This mission delivers {title} so product and engineering can move "
            "forward with a clear outcome and shared understanding."
        ),
    }


_SKIP_LOG_PREFIX = "Skipping bootstrap scaffold commit"


def _scaffold_commit_refusal(caplog: pytest.LogCaptureFixture) -> str:
    """The real ``safe_commit`` refusal the create disclosed for its scaffold commit."""
    [record] = [r for r in caplog.records if r.getMessage().startswith(_SKIP_LOG_PREFIX)]
    return record.getMessage()


def _tip(repo: Path, branch: str) -> str:
    return subprocess.run(["git", "rev-parse", branch], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def test_meta_commit_destination_comes_from_seam_not_checkout(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Coord-routing mission, checkout ("main") != target_branch (design/coord-target).

    The meta.json commit destination must be the seam-resolved PRIMARY home
    (``target_branch``), never the operator's current checkout.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    checkout_tip = _tip(repo, _CHECKOUT_BRANCH)
    caplog.set_level(logging.INFO, logger=_CORE_MODULE)

    result = create_mission_core(
        repo,
        "coord-checkout-mismatch",
        target_branch=_TARGET_BRANCH,
        topology=MissionTopology.COORD,
        **_mission_summary("coord-checkout-mismatch"),
    )

    refusal = _scaffold_commit_refusal(caplog)
    assert f"expected {_TARGET_BRANCH!r}" in refusal, (
        "meta.json commit destination must be the seam-resolved primary target "
        f"({_TARGET_BRANCH!r}), not the operator's checkout ({_CHECKOUT_BRANCH!r}); "
        f"got {refusal!r} -- the create-time split-brain root "
        "(research.md D5) is still deriving from the checkout, not the seam."
    )
    assert _tip(repo, _CHECKOUT_BRANCH) == checkout_tip, "meta.json must never land on the operator's checkout"
    assert result.feature_dir / "meta.json" in result.uncommitted_files


def test_non_coord_single_branch_meta_commit_still_targets_target_branch(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Parity (T008): a SINGLE_BRANCH mission with checkout != target_branch
    also lands meta.json on the seam-resolved target, not the checkout.

    SINGLE_BRANCH skips the coordination-branch mint entirely, so this pins
    that the fix is not accidentally coord-topology-specific.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    checkout_tip = _tip(repo, _CHECKOUT_BRANCH)
    caplog.set_level(logging.INFO, logger=_CORE_MODULE)

    create_mission_core(
        repo,
        "flat-checkout-mismatch",
        target_branch=_TARGET_BRANCH,
        topology=MissionTopology.SINGLE_BRANCH,
        **_mission_summary("flat-checkout-mismatch"),
    )

    refusal = _scaffold_commit_refusal(caplog)
    assert f"expected {_TARGET_BRANCH!r}" in refusal, f"got {refusal!r}, expected the destination {_TARGET_BRANCH!r} (SINGLE_BRANCH parity with COORD)"
    assert _tip(repo, _CHECKOUT_BRANCH) == checkout_tip


def test_meta_commit_matches_seam_write_target_when_checkout_equals_target(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Parity (T007): normal create (checkout == target_branch) is unaffected.

    No behavior change to WHICH surface meta.json lands on when the operator
    is already parked on the mission's target -- only the DERIVATION changes
    (seam, not checkout). This regression-locks that the common-case create
    flow keeps committing meta.json to the branch it always has: here the
    protected ``main``, whose real refusal names it as the destination.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    caplog.set_level(logging.INFO, logger=_CORE_MODULE)

    create_mission_core(
        repo,
        "no-mismatch",
        topology=MissionTopology.COORD,
        **_mission_summary("no-mismatch"),
    )

    assert f"refusing to commit to protected branch {_CHECKOUT_BRANCH!r}" in _scaffold_commit_refusal(caplog)
