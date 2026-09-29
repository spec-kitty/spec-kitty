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
    body = {"mission_slug": slug, "target_branch": "main", **meta}
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


def test_mission_write_bypass_helper_matches_policy_fold(tmp_path: Path) -> None:
    from specify_cli.git.protection_policy import mission_write_bypass

    repo = _repo(tmp_path)
    _mission(repo, "flagged-mission", commit_to_target=True)
    _mission(repo, "other-mission")
    _mission(repo, "bad-flag", commit_to_target="yes")

    assert mission_write_bypass(repo, "flagged-mission", "main") is True
    assert mission_write_bypass(repo, "flagged-mission", "master") is False
    assert mission_write_bypass(repo, "other-mission", "main") is False
    assert mission_write_bypass(repo, "bad-flag", "main") is False
    assert mission_write_bypass(repo, None, "main") is False
    assert mission_write_bypass(repo, "no-such-mission", "main") is False
