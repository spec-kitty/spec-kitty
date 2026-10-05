"""Mission-scoped protection bypass for ``meta.commit_to_target`` (WP08 cycle 4 / FR-008).

``commit_to_target: true`` in a mission's ``meta.json`` is a MISSION-SCOPED fold
of the existing operator-hatch concept (C-002): it un-protects the mission's OWN
``target_branch`` for writes resolved through that mission -- and nothing else.

Negative controls (the hatch env var is explicitly unset throughout):

* a different mission WITHOUT the flag on the same protected ``main`` is refused;
* a non-mission resolution (plain ``resolve``) on ``main`` is refused;
* a non-bool ``commit_to_target`` fails closed (refuses, never bypasses);
* the flag never un-protects a branch other than the mission's own target.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from specify_cli.git.protection_policy import ProtectionPolicy

pytestmark = [pytest.mark.git_repo]


@pytest.fixture(autouse=True)
def _hatch_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    (repo / ".kittify").mkdir()
    return repo


def _mission(repo: Path, slug: str, **meta: object) -> None:
    mission_dir = repo / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    body = {"mission_slug": slug, "target_branch": "main", "topology": "single_branch", **meta}
    (mission_dir / "meta.json").write_text(json.dumps(body), encoding="utf-8")


def test_flagged_mission_bypasses_its_own_target(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _mission(repo, "flagged-mission", commit_to_target=True)

    policy = ProtectionPolicy.resolve_for_mission(repo, "flagged-mission")

    assert policy.is_protected("main") is False


def test_other_mission_without_flag_still_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _mission(repo, "flagged-mission", commit_to_target=True)
    _mission(repo, "other-mission")

    assert ProtectionPolicy.resolve_for_mission(repo, "other-mission").is_protected("main") is True


def test_non_mission_commit_still_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _mission(repo, "flagged-mission", commit_to_target=True)

    assert ProtectionPolicy.resolve(repo).is_protected("main") is True
    assert ProtectionPolicy.resolve_for_mission(repo, None).is_protected("main") is True


@pytest.mark.parametrize("bad", ["yes", "true", 1, 0, [], {}])
def test_non_bool_flag_fails_closed(tmp_path: Path, bad: object) -> None:
    repo = _repo(tmp_path)
    _mission(repo, "bad-flag", commit_to_target=bad)

    assert ProtectionPolicy.resolve_for_mission(repo, "bad-flag").is_protected("main") is True


def test_false_flag_and_absent_meta_stay_protected(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _mission(repo, "false-flag", commit_to_target=False)

    assert ProtectionPolicy.resolve_for_mission(repo, "false-flag").is_protected("main") is True
    assert ProtectionPolicy.resolve_for_mission(repo, "no-such-mission").is_protected("main") is True


def test_flag_never_unprotects_a_different_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _mission(repo, "flagged-mission", commit_to_target=True)

    policy = ProtectionPolicy.resolve_for_mission(repo, "flagged-mission")

    assert policy.is_protected("master") is True
    assert policy.is_protected_target("main", primary_branch="main") is False
    assert policy.is_protected_target("master", primary_branch="master") is True


def test_resolve_for_mission_decision_matrix(tmp_path: Path) -> None:
    """The mission-scoped fold, end to end, through the one surviving entry point."""
    repo = _repo(tmp_path)
    _mission(repo, "flagged-mission", commit_to_target=True)
    _mission(repo, "other-mission")
    _mission(repo, "bad-flag", commit_to_target="yes")

    assert ProtectionPolicy.resolve_for_mission(repo, "flagged-mission").is_protected("main") is False
    assert ProtectionPolicy.resolve_for_mission(repo, "flagged-mission").is_protected("master") is True
    assert ProtectionPolicy.resolve_for_mission(repo, "other-mission").is_protected("main") is True
    assert ProtectionPolicy.resolve_for_mission(repo, "bad-flag").is_protected("main") is True
    assert ProtectionPolicy.resolve_for_mission(repo, None).is_protected("main") is True
    assert ProtectionPolicy.resolve_for_mission(repo, "no-such-mission").is_protected("main") is True


def test_for_mission_scopes_an_already_resolved_policy(tmp_path: Path) -> None:
    """``for_mission`` is the instance step ``resolve_for_mission`` composes.

    It exists for callers that hold a policy resolved against a DIFFERENT root
    (e.g. a worktree) than the one the mission's ``meta.json`` lives under.
    """
    repo = _repo(tmp_path)
    _mission(repo, "flagged-mission", commit_to_target=True)
    resolved = ProtectionPolicy.resolve(repo)

    assert resolved.is_protected("main") is True
    assert resolved.for_mission(repo, "flagged-mission").is_protected("main") is False
    assert resolved.for_mission(repo, "flagged-mission") == ProtectionPolicy.resolve_for_mission(repo, "flagged-mission")


@pytest.mark.parametrize("topology", ["lanes", "coord", "lanes_with_coord", "not-a-topology", None])
def test_flag_on_non_single_branch_topology_never_bypasses(tmp_path: Path, topology: object) -> None:
    """A4: ``commit_to_target`` is single_branch-only; a hand-edited meta on any
    other (or unstored) topology must not un-protect the target."""
    repo = _repo(tmp_path)
    _mission(repo, "hand-edited", commit_to_target=True, topology=topology)

    assert ProtectionPolicy.resolve_for_mission(repo, "hand-edited").is_protected("main") is True


# ---------------------------------------------------------------------------
# #5100 -- ONE mission-scoped decision. The former call-site idiom
# ``resolve(root).is_protected(b) and not mission_write_bypass(root, slug, b)``
# is now ``resolve_for_mission(root, slug).is_protected(b)``; these pin that the
# real call sites still answer identically for the three canonical cases.
# ---------------------------------------------------------------------------

_SLUG_OPT_OUT = "opted-out"
_SLUG_PROTECTED = "protected-no-opt-out"


def _call_site_repo(tmp_path: Path) -> Path:
    repo = _repo(tmp_path)
    _mission(repo, _SLUG_OPT_OUT, commit_to_target=True)
    _mission(repo, _SLUG_PROTECTED)
    return repo


def _implement_refuses(repo: Path, slug: str, branch: str) -> bool:
    from specify_cli.cli.commands.implement_claim import _protected_branch_status_commit_error

    return _protected_branch_status_commit_error(branch, repo, slug) is not None


def _tasks_shared_refuses(repo: Path, slug: str, branch: str) -> bool:
    from specify_cli.cli.commands.agent.tasks_shared import _protected_branch_status_commit_error

    return _protected_branch_status_commit_error(branch, repo, "mark-status", slug) is not None


def _tasks_shared_skips(repo: Path, slug: str, branch: str) -> bool:
    from unittest.mock import patch

    from specify_cli.cli.commands.agent.tasks_shared import _skip_target_branch_commit

    with patch("specify_cli.cli.commands.agent.tasks._coord_topology_active", return_value=True):
        return _skip_target_branch_commit(repo, slug or "", branch)


@pytest.mark.parametrize("decide", [_implement_refuses, _tasks_shared_refuses, _tasks_shared_skips])
@pytest.mark.parametrize(
    ("slug", "branch", "expected_protected"),
    [
        (_SLUG_OPT_OUT, "main", False),  # protected + single_branch + commit_to_target -> opted out
        (_SLUG_PROTECTED, "main", True),  # protected, no opt-out -> still protected
        (_SLUG_OPT_OUT, "master", True),  # the opt-out is for the mission's own target only
        (_SLUG_PROTECTED, "feature-x", False),  # unprotected branch -> not protected
        (_SLUG_OPT_OUT, "feature-x", False),
        (None, "main", True),  # no mission scope -> plain policy
    ],
)
def test_call_sites_match_the_mission_scoped_policy_decision(
    tmp_path: Path, decide: Callable[[Path, str | None, str], bool], slug: str | None, branch: str, expected_protected: bool
) -> None:
    repo = _call_site_repo(tmp_path)

    assert ProtectionPolicy.resolve_for_mission(repo, slug).is_protected(branch) is expected_protected
    assert decide(repo, slug, branch) is expected_protected
