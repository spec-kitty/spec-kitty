"""Regression tests for MissionTopology minting at creation (T011 / FR-002).

A fresh ``mission create`` has no ``lanes.json`` yet, so create-time
classification only ever yields ``COORD`` (coordination branch present) or
``SINGLE_BRANCH`` (no coordination branch). The lanes-bearing cells arise only
after finalize and are covered in the classifier + backfill tests.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.core.mission_creation import create_mission_core

from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CORE_MODULE = "specify_cli.core.mission_creation"


def _init_git_repo(repo: Path) -> None:
    (repo / ".kittify").mkdir(exist_ok=True)
    # WP04 fail-closed: create_mission_core requires a provisioned charter.
    # Seed the default mission_type_activations via the production provisioner
    # (same shared helper used across the mission-creation test harness).
    provision_test_charter(repo)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    # Pin the branch the checkout is really on to the one ``_patched_context``
    # reports (``get_current_branch`` -> "main"): ``git init``'s default branch
    # is environment-dependent (``init.defaultBranch``; ``master`` when unset),
    # so without this the protected single_branch mint is asked to fork from a
    # ``main`` that exists only in the patch.
    subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init", "--allow-empty"], cwd=repo, capture_output=True, check=True)


def _mission_summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ").strip() or "test mission"
    return {
        "friendly_name": title.title(),
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (f"This mission delivers {title} so product and engineering can move forward with a clear outcome and shared understanding."),
    }


@contextmanager
def _patched_context(tmp_path: Path):
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value="main"),
        patch(f"{_CORE_MODULE}._commit_feature_file"),
    ):
        yield


def _read_meta(tmp_path: Path) -> dict[str, object]:
    mission_dir = next((tmp_path / "kitty-specs").iterdir())
    return json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))


def test_coord_create_mints_coord_topology(tmp_path: Path) -> None:
    """A normal create (coordination branch minted) stores topology == 'coord'."""
    _init_git_repo(tmp_path)
    with _patched_context(tmp_path):
        create_mission_core(tmp_path, "topology-coord", **_mission_summary("topology-coord"))

    meta = _read_meta(tmp_path)
    assert meta["coordination_branch"]  # coordination branch present
    assert meta["topology"] == "coord"
    assert meta["flattened"] is False


def test_no_coord_create_mints_single_branch(tmp_path: Path) -> None:
    """An explicit ``single_branch`` create skips the mint and stores
    topology == 'single_branch' with NO coordination_branch key.

    Re-pinned to the #2218 contract (WP03): topology is now the operator's
    EXPLICIT ``MissionTopology`` choice, not a value re-derived by
    ``classify_topology`` from a (possibly stubbed) mint outcome. A
    ``single_branch`` choice is coordination-flat, so ``ensure_coordination_branch``
    is never called and ``meta.json`` carries no ``coordination_branch`` key.
    The old form stubbed ``ensure_coordination_branch`` to return ``branch_name=None``
    (a non-production value) to coax classify into ``single_branch``; that path is
    retired."""
    from mission_runtime import MissionTopology

    _init_git_repo(tmp_path)
    with (
        _patched_context(tmp_path),
        patch(
            "specify_cli.missions._create.ensure_coordination_branch",
        ) as mint,
    ):
        create_mission_core(
            tmp_path,
            "topology-single",
            topology=MissionTopology.SINGLE_BRANCH,
            **_mission_summary("topology-single"),
        )

    meta = _read_meta(tmp_path)
    assert "coordination_branch" not in meta
    assert meta["topology"] == "single_branch"
    mint.assert_not_called()  # branch-flat shape: the mint is skipped entirely
    assert meta["flattened"] is False


def test_coordinationless_create_persists_topology_so_2453_routing_is_not_cwd(
    tmp_path: Path,
) -> None:
    """PR #2662 squad (debbie LOW): the ONLY thing keeping a modern
    coordination-less mission out of the #2453/#2647 ``Path.cwd()`` write-side
    path is a READABLE stored ``topology`` in meta.json — a mission lacking it
    is (fail-safe) classified genuinely-legacy and routes through the operator's
    cwd lane worktree. So mission-creation MUST persist it, and the classifier
    must read the created mission as modern. This pins the linkage end-to-end.
    """
    from specify_cli.coordination.transaction import _warrants_legacy_warning

    # Exercise the real commit preflight against an initialized repository.
    _init_git_repo(tmp_path)

    with _patched_context(tmp_path), patch("specify_cli.missions._create.ensure_coordination_branch"):
        from mission_runtime import MissionTopology

        create_mission_core(
            tmp_path,
            "topology-2453-linkage",
            topology=MissionTopology.SINGLE_BRANCH,
            **_mission_summary("topology-2453-linkage"),
        )

    meta = _read_meta(tmp_path)
    # Invariant: a readable, non-empty topology is persisted.
    assert meta.get("topology"), "coordination-less create MUST persist a readable topology"
    assert "coordination_branch" not in meta

    # Linkage: the classifier reads this created mission as MODERN
    # coordination-less (NOT genuinely-legacy) -> #2453 routes it to repo_root,
    # not Path.cwd(). If creation ever stopped writing topology, this flips True
    # (genuinely-legacy) and silently reopens #2647.
    mid8 = str(meta["mission_id"])[:8]
    assert _warrants_legacy_warning(tmp_path, "topology-2453-linkage", mid8) is False


# ---------------------------------------------------------------------------
# #5100 WP08 follow-up: the protected single_branch mint when the target branch
# names no commit. ``create_mission_core`` already refuses an unborn checkout
# HEAD up front (#4033, tests/core/test_mission_creation_unborn_head.py), so the
# mint only ever sees a committed HEAD; a target that still resolves to no
# commit (never created, or the operator's unborn default branch while HEAD sits
# elsewhere) must be refused with an actionable message, never git's raw
# "'<target>' is not a commit", and before any ref or meta mutation.
# ---------------------------------------------------------------------------


def _git_out(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False).stdout.strip()


def _committed_repo_on(repo: Path, branch: str) -> None:
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "symbolic-ref", "HEAD", f"refs/heads/{branch}"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init", "--allow-empty"], cwd=repo, capture_output=True, check=True)


def test_protected_mint_refuses_clearly_when_target_branch_has_no_commit(tmp_path: Path) -> None:
    from specify_cli.core.mission_creation import MissionCreationError, _mint_protected_single_branch_mission_branch

    _committed_repo_on(tmp_path, "trunk")
    meta: dict[str, object] = {}

    with (
        patch("specify_cli.core.git_ops.resolve_primary_branch", return_value="main"),
        pytest.raises(MissionCreationError) as excinfo,
    ):
        _mint_protected_single_branch_mission_branch(
            tmp_path,
            "unborn-target-01M3Q4EC",
            mission_id="01M3Q4ECZZZZZZZZZZZZZZZZZZ",
            target_branch="main",
            meta=meta,
        )

    message = str(excinfo.value)
    assert "'main'" in message
    assert "has no commit" in message
    assert "is not a commit" not in message  # never git's raw start-point error
    # Fail-closed before any mutation: no meta write, no ref, checkout untouched.
    assert "mission_branch" not in meta
    assert _git_out(tmp_path, "branch", "--list", "kitty/*") == ""
    assert _git_out(tmp_path, "symbolic-ref", "--short", "HEAD") == "trunk"


def test_protected_mint_still_forks_from_an_existing_target(tmp_path: Path) -> None:
    """Positive control: a target with a commit is minted from and checked out."""
    from specify_cli.core.mission_creation import _mint_protected_single_branch_mission_branch
    from specify_cli.lanes.branch_naming import mission_branch_name

    _committed_repo_on(tmp_path, "main")
    meta: dict[str, object] = {}

    with patch("specify_cli.core.git_ops.resolve_primary_branch", return_value="main"):
        _mint_protected_single_branch_mission_branch(
            tmp_path,
            "born-target-01M3Q4ED",
            mission_id="01M3Q4EDZZZZZZZZZZZZZZZZZZ",
            target_branch="main",
            meta=meta,
        )

    expected = mission_branch_name("born-target-01M3Q4ED", mission_id="01M3Q4EDZZZZZZZZZZZZZZZZZZ")
    assert meta["mission_branch"] == expected
    assert _git_out(tmp_path, "symbolic-ref", "--short", "HEAD") == expected
    assert _git_out(tmp_path, "rev-parse", expected) == _git_out(tmp_path, "rev-parse", "main")
