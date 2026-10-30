"""The ``spec-kitty implement --actor`` arm of the seed-refusal matrix (#6754).

``implement`` is a compatibility surface whose hidden ``--actor`` is recorded
verbatim as a bare-string actor, so it could seed. The refusal sits beside the
existing ``--mission`` no-selector guard: it fires before the mission context is
detected, before any lane worktree is allocated and before the claim is emitted.

Red on the base: the command proceeds and the claim's actor is the seed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.status.models import MIGRATION_ACTOR_PREFIX, SEED_SHAPED_IDENTITY_REFUSAL
from tests.specify_cli.cli.commands._implement_fixtures import (
    MISSION_ID,
    SLUG,
    activate_repo,
    build_mission,
    implement_cli,
    init_repo,
)

_REFUSAL = SEED_SHAPED_IDENTITY_REFUSAL.format(option="--actor", prefix=MIGRATION_ACTOR_PREFIX)


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = init_repo(tmp_path / "repo")
    activate_repo(root, monkeypatch, tmp_path)
    mission = build_mission(root, SLUG, MISSION_ID)
    return root, mission.feature_dir


@pytest.mark.integration
@pytest.mark.git_repo
def test_implement_refuses_a_caller_supplied_seed_before_any_allocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, _feature_dir = _repo(tmp_path, monkeypatch)
    events_before = sorted(path.read_bytes() for path in root.rglob("status.events.jsonl") if path.is_file())

    result = implement_cli("WP01", "--mission", SLUG, "--actor", "migration:backfill")

    assert result.exit_code == 1, result.output
    assert _REFUSAL in result.output
    assert sorted(path.read_bytes() for path in root.rglob("status.events.jsonl") if path.is_file()) == events_before
    assert not (root / ".worktrees").exists(), "a refused implement must not allocate a lane worktree"


@pytest.mark.integration
@pytest.mark.git_repo
def test_implement_still_works_without_the_hidden_actor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: the same fixture and command are not simply refusing everything."""
    _root, _feature_dir = _repo(tmp_path, monkeypatch)

    result = implement_cli("WP01", "--mission", SLUG)

    assert _REFUSAL not in result.output
    assert result.exit_code == 0, result.output
