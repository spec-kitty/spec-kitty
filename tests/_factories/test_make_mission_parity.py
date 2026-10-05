"""Parity guard for ``tests/_factories.make_mission()`` (FR-008 / E-06 / IC-07).

``make_mission()`` MUST be a thin delegate over ``create_mission_core()`` --
never a forked re-implementation of the meta-assembly schema. This module
asserts that invariant plus the behaviour-preservation of the
``allow_worktree_context`` seam added to ``create_mission_core()`` to make a
side-effect-free, no-coordination-branch entrypoint usable from test code
(T038 / NFR-003).

A raw byte-compare across two independent calls is unachievable as-is:
``mission_id`` (a ``ULID``) and ``created_at`` (wall-clock) are minted fresh
every call, and the mission directory / ``slug`` / ``mission_slug`` fields
embed the ``mission_id``-derived ``mid8`` suffix. The factory runs first with
its real mint; the direct core call then takes that identity through the
private identity inputs of ``_create_mission_core_failure_atomic`` (the body of
``create_mission_core``, #5634), so both calls produce the identical
mission_id and timestamp and the written ``meta.json`` files can be compared
byte for byte -- the strongest form of the parity assertion, with nothing
patched.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
import subprocess

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import (
    MissionCreationError,
    _create_mission_core_failure_atomic,
    create_mission_core,
)
from tests._factories import make_mission, provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def _init_git_repo(repo: Path, *, branch: str = "main") -> None:
    (repo / ".kittify").mkdir(parents=True, exist_ok=True)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", branch], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo, check=True)


def _linked_worktree(repo: Path, checkout: Path) -> Path:
    """A real ``git worktree add`` checkout of ``repo`` (its ``.git`` is a gitdir pointer)."""
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(checkout)], cwd=repo, check=True)
    return checkout


def _read_meta_bytes(repo_root: Path, mission_slug_prefix: str) -> bytes:
    matches = [
        p for p in (repo_root / "kitty-specs").iterdir() if p.name.startswith(f"{mission_slug_prefix}-")
    ]
    assert len(matches) == 1, f"expected exactly one mission dir, found {matches}"
    return (matches[0] / "meta.json").read_bytes()


def test_make_mission_meta_is_byte_identical_to_direct_core_call(tmp_path: Path) -> None:
    """E-06 / IC-07: make_mission() delegates -- it does not fork the schema."""
    direct_repo = tmp_path / "direct"
    factory_repo = tmp_path / "factory"
    direct_repo.mkdir()
    factory_repo.mkdir()
    _init_git_repo(direct_repo)
    _init_git_repo(factory_repo)
    # WP04 fail-closed follow-up: create_mission_core() now hard-requires an
    # activated mission type. Provision BOTH sides explicitly (rather than
    # relying on make_mission()'s internal provisioning for factory_repo
    # alone) so this parity test keeps proving direct_repo and factory_repo
    # start from an identical charter surface, not an asymmetric one.
    provision_test_charter(direct_repo)
    provision_test_charter(factory_repo)

    friendly_name = "Parity Mission"
    purpose_tldr = "Deliver parity mission cleanly for the team."
    purpose_context = (
        "This mission delivers parity mission so product and engineering "
        "can move forward with a clear outcome and shared understanding."
    )

    make_mission(
        factory_repo,
        "parity-mission",
        friendly_name=friendly_name,
        purpose_tldr=purpose_tldr,
        purpose_context=purpose_context,
        target_branch="main",
        topology=MissionTopology.SINGLE_BRANCH,
        allow_worktree_context=True,
    )
    factory_meta = json.loads(_read_meta_bytes(factory_repo, "parity-mission"))
    _create_mission_core_failure_atomic(
        direct_repo,
        "parity-mission",
        friendly_name=friendly_name,
        purpose_tldr=purpose_tldr,
        purpose_context=purpose_context,
        target_branch="main",
        topology=MissionTopology.SINGLE_BRANCH,
        allow_worktree_context=True,
        _mission_id=factory_meta["mission_id"],
        _created_at=factory_meta["created_at"],
    )

    direct_bytes = _read_meta_bytes(direct_repo, "parity-mission")
    factory_bytes = _read_meta_bytes(factory_repo, "parity-mission")

    assert direct_bytes == factory_bytes


def test_make_mission_applies_explicit_overrides_on_production_shaped_meta(tmp_path: Path) -> None:
    """Overrides land on top of the production schema, not a forked one."""
    repo = tmp_path / "override-repo"
    repo.mkdir()
    _init_git_repo(repo)

    result = make_mission(repo, "override-mission", friendly_name="Custom Override Name")

    assert result.meta["friendly_name"] == "Custom Override Name"
    meta_bytes = _read_meta_bytes(repo, "override-mission")
    assert b'"friendly_name": "Custom Override Name"' in meta_bytes
    # Still production-shaped: the schema fields make_mission() did not
    # override come straight from create_mission_core().
    # The identity is the core's own mint: a ULID whose mid8 names the mission.
    assert _ULID_RE.match(result.meta["mission_id"])
    assert result.meta["mid8"] == result.meta["mission_id"][:8]
    assert result.mission_slug == f"override-mission-{result.meta['mid8']}"
    assert result.meta["topology"] == "single_branch"
    assert "coordination_branch" not in result.meta


def test_create_mission_core_worktree_guard_default_still_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T038 behaviour-preservation proof: the new ``allow_worktree_context``
    seam defaults to ``False``, so the pre-existing interactive/CLI guard
    against scaffolding a mission from inside a worktree is unchanged for
    every existing caller that does not pass the new keyword.
    """
    repo = tmp_path / "guard-default-repo"
    repo.mkdir()
    _init_git_repo(repo)

    # The *process* cwd sits inside a real linked worktree of the repository,
    # independent of the temp ``repo_root`` under test -- exactly what
    # ``is_worktree_context(Path.cwd())`` observes for a run started from a
    # lane worktree checkout. Nothing is patched.
    monkeypatch.chdir(_linked_worktree(repo, tmp_path / "guard-default-linked"))

    with pytest.raises(MissionCreationError, match="worktree"):
        create_mission_core(
            repo,
            "guard-default-mission",
            topology=MissionTopology.SINGLE_BRANCH,
            friendly_name="Guard Default",
            purpose_tldr="Deliver guard default cleanly for the team.",
            purpose_context="This mission proves the worktree guard still blocks by default.",
        )


def test_create_mission_core_worktree_guard_bypass_is_behaviour_preserving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The opt-in bypass unblocks mission creation from a worktree-shaped cwd
    while every other guard and the resulting schema stay unchanged --
    proving the new entrypoint is behaviour-preserving (NFR-003), not a new
    code path with different output shape.
    """
    repo = tmp_path / "guard-bypass-repo"
    repo.mkdir()
    _init_git_repo(repo)
    provision_test_charter(repo)
    monkeypatch.chdir(_linked_worktree(repo, tmp_path / "guard-bypass-linked"))

    result = create_mission_core(
        repo,
        "guard-bypass-mission",
        topology=MissionTopology.SINGLE_BRANCH,
        allow_worktree_context=True,
        friendly_name="Guard Bypass",
        purpose_tldr="Deliver guard bypass cleanly for the team.",
        purpose_context="This mission proves the worktree guard bypass is behaviour-preserving.",
    )

    assert result.feature_dir.exists()
    assert result.meta["topology"] == "single_branch"
