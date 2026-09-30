"""#5385 -- ``BookkeepingTransaction.preflight_refusal`` is the transaction's own gate, probed lock-free.

The preflight must return exactly the ``Refused`` that :meth:`BookkeepingTransaction.acquire`
would raise as ``BookkeepingPolicyRefused`` (C-001: one protection authority), and
``None`` wherever ``acquire`` would proceed. It takes no lock, creates no coordination
worktree and writes nothing. ``status_write_refusal`` is the same probe entered through
the transactional status door's own identity + topology decision.

Real temp git repos, nothing mocked.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.status_transition import status_write_refusal
from specify_cli.coordination.transaction import BookkeepingPolicyRefused, BookkeepingTransaction
from specify_cli.coordination.types import PROTECTED_BRANCH_REFUSED, Refused
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.status.models import TransitionRequest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_HATCH = "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"
_MISSION_ID = "01M5385X0000000000000000AB"
_MID8 = _MISSION_ID[:8]
_SLUG = f"preflight-probe-{_MID8}"
_OPERATION = "status transition WP01"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture(autouse=True)
def _no_hatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_HATCH, raising=False)


def _mission(tmp_path: Path, *, target_branch: str = "main", coordination: bool = False, topology: str = "lanes") -> Path:
    """A real repo with a committed mission ``meta.json`` (coordination-less unless ``coordination``)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")
    if target_branch != "main":
        _git(repo, "branch", target_branch)
    feature_dir = repo / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mission_slug": _SLUG,
        "mid8": _MID8,
        "mission_type": "research",
        "target_branch": target_branch,
        "topology": "coord" if coordination else topology,
        "created_at": "2026-01-01T00:00:00+00:00",
        "friendly_name": "preflight probe",
    }
    if coordination:
        meta["coordination_branch"] = CoordinationWorkspace.branch_name(_SLUG, _MID8)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission")
    if coordination:
        _git(repo, "branch", CoordinationWorkspace.branch_name(_SLUG, _MID8), "main")
    return repo


def _probe(repo: Path, destination_ref: str) -> Refused | None:
    return BookkeepingTransaction.preflight_refusal(
        repo_root=repo,
        mission_slug=_SLUG,
        mid8=_MID8,
        destination_ref=destination_ref,
        operation=_OPERATION,
    )


def _acquire_refusal(repo: Path, destination_ref: str) -> Refused | None:
    """What the REAL acquire does: the refused verdict it raises, or ``None`` when it proceeds."""
    try:
        txn = BookkeepingTransaction.acquire(
            repo_root=repo,
            mission_id=_MISSION_ID,
            mission_slug=_SLUG,
            mid8=_MID8,
            destination_ref=destination_ref,
            operation=_OPERATION,
        )
    except BookkeepingPolicyRefused as exc:
        return exc.verdict
    txn._release_lock()
    return None


def _request(repo: Path) -> TransitionRequest:
    return TransitionRequest(
        feature_dir=repo / "kitty-specs" / _SLUG,
        mission_slug=_SLUG,
        wp_id="WP01",
        to_lane="done",
        actor="merge",
        repo_root=repo,
    )


def test_coordination_less_mission_on_protected_main_is_refused(tmp_path: Path) -> None:
    repo = _mission(tmp_path)
    head_before = _git(repo, "rev-parse", "main")

    verdict = _probe(repo, "main")

    assert isinstance(verdict, Refused), verdict
    assert verdict.error_code == PROTECTED_BRANCH_REFUSED
    assert _HATCH in verdict.next_step, "the coordination-less remedy names the operator hatch"
    assert _git(repo, "rev-parse", "main") == head_before
    assert not (repo / ".worktrees").exists(), "the probe creates no worktree"
    assert _git(repo, "status", "--porcelain") == "", "the probe writes nothing (no lock file, no status files)"


def test_unprotected_target_is_not_refused(tmp_path: Path) -> None:
    repo = _mission(tmp_path, target_branch="develop")
    assert _probe(repo, "develop") is None


def test_operator_hatch_is_honoured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _mission(tmp_path)
    monkeypatch.setenv(_HATCH, "1")
    assert _probe(repo, "main") is None


def test_coordination_mission_is_redirected_not_refused(tmp_path: Path) -> None:
    repo = _mission(tmp_path, coordination=True)
    assert _probe(repo, "main") is None
    assert not CoordinationWorkspace.worktree_path(repo, _SLUG, _MID8).exists(), "the probe never materializes the coord worktree"


def test_coordination_mission_whose_branch_is_not_materialized_is_not_refused(tmp_path: Path) -> None:
    """A missing coordination branch is no POLICY refusal: the probe returns ``None``.

    ``acquire`` does not create the branch; it fails closed with
    ``BookkeepingWorktreeMissing`` while resolving the coordination worktree,
    before its policy gate runs, so the refusal the probe mirrors never happens.
    """
    repo = _mission(tmp_path, coordination=True)
    coord_branch = CoordinationWorkspace.branch_name(_SLUG, _MID8)
    _git(repo, "branch", "-D", coord_branch)
    assert _probe(repo, coord_branch) is None
    assert status_write_refusal(_request(repo)) is None


def test_coordination_mission_with_a_missing_caller_ref_is_refused_like_acquire(tmp_path: Path) -> None:
    repo = _mission(tmp_path, coordination=True)
    verdict = _probe(repo, "no-such-branch")
    assert isinstance(verdict, Refused)
    assert verdict == _acquire_refusal(repo, "no-such-branch")


def test_genuinely_legacy_mission_is_not_probed(tmp_path: Path) -> None:
    """A pre-SSOT mission writes to the operator's lane HEAD, which is not knowable pre-run."""
    repo = _mission(tmp_path)
    meta_path = repo / "kitty-specs" / _SLUG / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["topology"]
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _git(repo, "commit", "-qam", "legacy meta")
    assert _probe(repo, "main") is None


@pytest.mark.parametrize(
    ("target_branch", "hatch"),
    [("main", False), ("main", True), ("develop", False)],
    ids=["protected", "hatch", "unprotected"],
)
def test_preflight_equals_the_real_acquire_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target_branch: str, hatch: bool) -> None:
    """Equivalence (C-001): the probe returns exactly what ``acquire`` raises, on the same fixture."""
    repo = _mission(tmp_path, target_branch=target_branch)
    if hatch:
        monkeypatch.setenv(_HATCH, "1")

    probed = _probe(repo, target_branch)
    acquired = _acquire_refusal(repo, target_branch)

    assert probed == acquired
    if target_branch == "main" and not hatch:
        assert isinstance(probed, Refused) and probed.error_code == PROTECTED_BRANCH_REFUSED


def test_status_write_refusal_follows_the_status_door(tmp_path: Path) -> None:
    repo = _mission(tmp_path)
    verdict = status_write_refusal(_request(repo))
    assert isinstance(verdict, Refused)
    assert verdict.error_code == PROTECTED_BRANCH_REFUSED
    assert verdict.destination_ref == "main", "the status write target is the recorded meta target"


def test_status_write_refusal_is_none_for_an_unprotected_target(tmp_path: Path) -> None:
    repo = _mission(tmp_path, target_branch="develop")
    assert status_write_refusal(_request(repo)) is None


def test_status_write_refusal_is_none_for_a_coordination_mission(tmp_path: Path) -> None:
    repo = _mission(tmp_path, coordination=True)
    assert status_write_refusal(_request(repo)) is None


def test_status_write_refusal_is_none_on_the_non_transactional_fallback(tmp_path: Path) -> None:
    """Outside a git work tree the door takes the fallback, which never consults the policy."""
    feature_dir = tmp_path / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": _MISSION_ID, "mission_slug": _SLUG, "target_branch": "main"}), encoding="utf-8")
    request = TransitionRequest(feature_dir=feature_dir, mission_slug=_SLUG, wp_id="WP01", to_lane="done", actor="merge", repo_root=tmp_path)
    assert status_write_refusal(request) is None
