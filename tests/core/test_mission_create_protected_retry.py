"""Protected single_branch create: refusals leave no residue, re-runs refuse stably.

* #5704 -- a protected-mint refusal (dirty write checkout, mission branch
  already exists, target with no commit) leaves no mission directory behind,
  so the retry after the operator fixes the cause succeeds instead of being
  refused MISSION_ALREADY_EXISTS on a meta-less orphan scaffold.
* #5726 -- re-running a create for the same slug while the prior mission's
  minted mission branch exists refuses MISSION_ALREADY_EXISTS whatever mid8
  the second create mints (never the mint's dirty-checkout
  MISSION_CREATE_FAILED on the prior's own untracked ``spec.md``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import MissionCreationError, _create_mission_core_failure_atomic
from specify_cli.lanes.branch_naming import mission_branch_name

from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Two identities in different mid8 buckets (first 8 characters differ).
_FIRST_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
_SECOND_ID = "01BX5ZZKBKACTAV9WEVGEMMVRZ"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _protected_repo(tmp_path: Path) -> Path:
    """A repository on ``main`` (the primary branch, so a protected target) with a charter committed."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "retry@example.invalid")
    _git(repo, "config", "user.name", "Retry Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    provision_test_charter(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    return repo


def _create(repo: Path, slug: str, mission_id: str, **overrides: Any) -> Any:
    kwargs: dict[str, Any] = {
        "_mission_id": mission_id,
        "topology": MissionTopology.SINGLE_BRANCH,
        "target_branch": "main",
        "allow_worktree_context": True,
        "friendly_name": "Protected Retry",
        "purpose_tldr": "Protected create retry.",
        "purpose_context": "A protected single_branch create that is refused and then retried.",
    }
    kwargs.update(overrides)
    return _create_mission_core_failure_atomic(repo, slug, **kwargs)


def _scaffolds(repo: Path, slug: str) -> list[str]:
    specs = repo / "kitty-specs"
    if not specs.is_dir():
        return []
    return sorted(entry.name for entry in specs.iterdir() if entry.name.startswith(slug))


# ---------------------------------------------------------------------------
# #5704: a mint refusal leaves no scaffold; the retry succeeds
# ---------------------------------------------------------------------------


def test_dirty_mint_refusal_leaves_no_scaffold_and_retry_succeeds(tmp_path: Path) -> None:
    repo = _protected_repo(tmp_path)
    stray = repo / "stray.txt"
    stray.write_text("operator work\n", encoding="utf-8")

    with pytest.raises(MissionCreationError, match="uncommitted changes outside") as refused:
        _create(repo, "orphan-retry", _FIRST_ID)
    assert refused.value.error_code is None  # MISSION_CREATE_FAILED, unchanged
    assert _scaffolds(repo, "orphan-retry") == []
    assert _git(repo, "branch", "--show-current") == "main"
    assert stray.read_text(encoding="utf-8") == "operator work\n"  # the operator's work is untouched

    stray.unlink()
    result = _create(repo, "orphan-retry", _SECOND_ID)

    assert result.feature_dir.is_dir()
    assert (result.feature_dir / "meta.json").is_file()
    assert _git(repo, "branch", "--show-current") == mission_branch_name("orphan-retry", mission_id=_SECOND_ID)


def test_branch_exists_mint_refusal_leaves_no_scaffold(tmp_path: Path) -> None:
    repo = _protected_repo(tmp_path)
    planted = mission_branch_name("branch-exists", mission_id=_FIRST_ID)
    _git(repo, "branch", planted)

    with pytest.raises(MissionCreationError) as refused:
        _create(repo, "branch-exists", _FIRST_ID)

    assert refused.value.error_code == "MISSION_BRANCH_EXISTS"
    assert _scaffolds(repo, "branch-exists") == []
    assert _git(repo, "rev-parse", "--verify", f"refs/heads/{planted}")  # the operator's branch is kept


def test_target_without_commit_mint_refusal_leaves_no_scaffold(tmp_path: Path) -> None:
    repo = _protected_repo(tmp_path)
    config = repo / ".kittify" / "config.yaml"
    config.write_text(config.read_text(encoding="utf-8") + "\nprotection:\n  protected_branches: [release]\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "protect release")

    with pytest.raises(MissionCreationError, match="has no commit"):
        _create(repo, "no-commit-target", _FIRST_ID, target_branch="release")

    assert _scaffolds(repo, "no-commit-target") == []


# ---------------------------------------------------------------------------
# #5726: a re-run for the same slug refuses MISSION_ALREADY_EXISTS whatever the mid8
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("second_id", [_FIRST_ID, _SECOND_ID], ids=["same-mid8", "fresh-mid8"])
def test_rerun_for_same_slug_refuses_mission_already_exists(tmp_path: Path, second_id: str) -> None:
    repo = _protected_repo(tmp_path)
    first = _create(repo, "rerun-slug", _FIRST_ID)
    meta_path = first.feature_dir / "meta.json"
    meta_before = meta_path.read_text(encoding="utf-8")
    assert not _git(repo, "ls-files", str(first.feature_dir / "spec.md"))  # #846: spec.md left untracked

    with pytest.raises(MissionCreationError) as refused:
        _create(repo, "rerun-slug", second_id)

    assert refused.value.error_code == "MISSION_ALREADY_EXISTS"
    assert meta_path.read_text(encoding="utf-8") == meta_before
    assert _scaffolds(repo, "rerun-slug") == [first.feature_dir.name]
    assert _git(repo, "branch", "--show-current") == mission_branch_name("rerun-slug", mission_id=_FIRST_ID)

