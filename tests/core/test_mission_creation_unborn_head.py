"""Regression tests for the unborn-HEAD create guard (#4033).

A freshly ``git init``-ed repository has an unborn HEAD: HEAD names a branch ref
that does not exist yet, because there are no commits. Git cannot create a
branch in that state. Every topology also commits its scaffold to an existing
planning ref, so all creation paths must reject an unborn checkout before
writing a scaffold. The error identifies the initial commit needed to proceed.
"""

from __future__ import annotations

from contextlib import contextmanager
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import MissionCreationError, create_mission_core
from specify_cli.core.owned_mission import resolve_owned_create_root

from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CORE_MODULE = "specify_cli.core.mission_creation"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True)


def _scaffold_project(repo: Path) -> None:
    """Provision a Spec Kitty project WITHOUT making an initial commit."""
    (repo / ".kittify").mkdir(exist_ok=True)
    provision_test_charter(repo)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    _git(repo, "init", "-b", "operator-work")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    # Deliberately NO commit: this is the unborn-HEAD state under test.


def _mission_summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ").strip() or "test mission"
    return {
        "friendly_name": title.title(),
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (f"This mission delivers {title} so product and engineering can move forward with a clear outcome and shared understanding."),
    }


@contextmanager
def _patched_context(tmp_path: Path):
    """Patch the context seams, but leave the real ``has_unborn_head`` in place."""
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value="operator-work"),
    ):
        yield


# ---------------------------------------------------------------------------
# The predicate
# ---------------------------------------------------------------------------


def test_has_unborn_head_true_before_first_commit(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    from specify_cli.core.git_ops import has_unborn_head

    assert has_unborn_head(tmp_path) is True


def test_has_unborn_head_false_once_a_commit_exists(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@test.com")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "commit", "-m", "init", "--allow-empty")
    from specify_cli.core.git_ops import has_unborn_head

    assert has_unborn_head(tmp_path) is False


def test_has_unborn_head_false_for_a_non_repository(tmp_path: Path) -> None:
    """Never the thing that reports 'no commits' for a directory that is not a repo.

    Callers guard on ``is_git_repo`` separately; conflating the two would make
    the create error tell a non-repo user to run ``git commit``.
    """
    from specify_cli.core.git_ops import has_unborn_head

    assert has_unborn_head(tmp_path) is False


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------


def test_coord_create_refuses_on_unborn_head(tmp_path: Path) -> None:
    """Coord create on a commitless repo fails before writing a scaffold."""
    _scaffold_project(tmp_path)

    with _patched_context(tmp_path), pytest.raises(MissionCreationError) as excinfo:
        create_mission_core(
            tmp_path,
            "unborn-coord",
            topology=MissionTopology.COORD,
            **_mission_summary("unborn-coord"),
        )

    message = str(excinfo.value)
    assert "no commits yet" in message
    # The error must be actionable — it names the recovery, not just the fault.
    assert "git commit" in message


def test_refusal_writes_no_scaffold(tmp_path: Path) -> None:
    """Fail before mutating: a refused create leaves nothing to recover.

    The pre-guard behavior left a ``kitty-specs/<slug>/`` scaffold plus a
    dangling ``coordination_branch`` declaration behind.
    """
    _scaffold_project(tmp_path)

    with _patched_context(tmp_path), pytest.raises(MissionCreationError):
        create_mission_core(
            tmp_path,
            "unborn-no-residue",
            topology=MissionTopology.COORD,
            **_mission_summary("unborn-no-residue"),
        )

    assert list((tmp_path / "kitty-specs").iterdir()) == []


@pytest.mark.parametrize(
    "topology",
    [MissionTopology.SINGLE_BRANCH, MissionTopology.LANES],
    ids=["single_branch", "lanes"],
)
def test_branch_flat_topologies_refuse_unborn_head(tmp_path: Path, topology: MissionTopology) -> None:
    """Branch-flat creation still needs an existing ref for its scaffold commit."""
    _scaffold_project(tmp_path)

    with _patched_context(tmp_path), pytest.raises(MissionCreationError, match="no commits yet"):
        create_mission_core(
            tmp_path,
            "unborn-flat",
            topology=topology,
            **_mission_summary("unborn-flat"),
        )

    assert list((tmp_path / "kitty-specs").iterdir()) == []


def test_coord_create_succeeds_after_the_first_commit(tmp_path: Path) -> None:
    """The remedy the error message prescribes actually works.

    Pins the whole loop: refuse, the user commits, create succeeds. A guard that
    blocks without a working recovery is worse than the bug.
    """
    _scaffold_project(tmp_path)
    _git(tmp_path, "commit", "-m", "init", "--allow-empty")

    # The mint is deliberately NOT patched here: the point is that a real
    # coordination branch can now be created, which is exactly what the unborn
    # HEAD made impossible.
    with _patched_context(tmp_path):
        result = create_mission_core(
            tmp_path,
            "born-coord",
            topology=MissionTopology.COORD,
            **_mission_summary("born-coord"),
        )

    assert result.feature_dir.exists()
    assert result.coordination_branch is not None
    # The declaration in meta.json now resolves to a ref that actually exists —
    # the invariant #4033 violated.
    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", result.coordination_branch],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert resolved.returncode == 0, f"declared branch {result.coordination_branch!r} does not exist"


@pytest.mark.parametrize("unborn_owned", [False, True], ids=["committed-owned", "unborn-owned"])
def test_guard_uses_owned_checkout_head(tmp_path: Path, unborn_owned: bool) -> None:
    repo = tmp_path / "primary"
    repo.mkdir()
    _scaffold_project(repo)
    _git(repo, "add", ".kittify")
    _git(repo, "commit", "-m", "Initialize project")
    owned = tmp_path / "owned"
    _git(repo, "worktree", "add", str(owned), "-b", "owned-work")
    _git(owned if unborn_owned else repo, "checkout", "--orphan", "unborn")

    # occurrence_map tests_fixtures: rename to the typed create root (WP10 T055)
    owned_create_root = resolve_owned_create_root(repo, owned)
    if unborn_owned:
        with pytest.raises(MissionCreationError, match="no commits yet"):
            create_mission_core(repo, "owned-unborn", owned_create_root=owned_create_root, **_mission_summary("owned-unborn"))
        assert not (owned / "kitty-specs").exists()
    else:
        result = create_mission_core(repo, "owned-committed", owned_create_root=owned_create_root, **_mission_summary("owned-committed"))
        assert result.feature_dir.is_relative_to(owned)
        assert result.feature_dir.exists()
        assert result.coordination_branch is not None
        assert _git(owned, "rev-parse", "--verify", result.coordination_branch).returncode == 0
