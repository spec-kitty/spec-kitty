"""Owned status authority must survive an in-repository worktree location."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mission_runtime import ActionContextError

from specify_cli.coordination.status_service import (
    EventLogReadContract,
    StatusContractError,
    StatusReadSource,
    read_event_log,
    read_event_stream_log,
)
from specify_cli.coordination.status_transition import read_events_transactional
from tests.integration.test_explicit_checkout_commands import SLUG, checkouts, git, invoke, snapshot

__all__ = ["checkouts"]
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_finalize_and_read_owned_mission_below_worktrees(checkouts, monkeypatch):
    primary, owned, sibling = checkouts
    inside = primary / ".worktrees" / "owned"
    inside.parent.mkdir()
    (primary / ".git/info/exclude").write_text(".worktrees/\n", encoding="utf-8")
    monkeypatch.chdir(primary)
    git(primary, "worktree", "move", str(owned), str(inside))
    monkeypatch.chdir(inside)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(inside))
    before = git(primary, "rev-parse", "HEAD"), git(primary, "status", "--porcelain"), snapshot(sibling)

    result = invoke("finalize-tasks", inside)

    assert result.exit_code == 0, result.output
    events = read_events_transactional(
        feature_dir=inside / "kitty-specs" / SLUG,
        mission_slug=SLUG,
        repo_root=primary,
        effective_root=inside,
    )
    assert [(event.wp_id, str(event.to_lane)) for event in events] == [("WP01", "planned")]
    assert (git(primary, "rev-parse", "HEAD"), git(primary, "status", "--porcelain"), snapshot(sibling)) == before
    assert not (primary / "kitty-specs" / SLUG).exists()


@pytest.mark.parametrize("reader", [read_event_log, read_event_stream_log])
def test_owned_contract_validates_root_and_mission(checkouts, reader):
    primary, owned, sibling = checkouts
    mission = owned / "kitty-specs" / SLUG
    contract = EventLogReadContract.owned_checkout(mission, repo_root=primary, owned_root=owned)
    reader(contract)
    with pytest.raises(StatusContractError, match="require primary and owned roots"):
        reader(EventLogReadContract(source=StatusReadSource.OWNED_CHECKOUT, feature_dir=mission))
    with pytest.raises(StatusContractError, match="mission directory does not match"):
        reader(EventLogReadContract.owned_checkout(primary / "kitty-specs" / SLUG, repo_root=primary, owned_root=owned))
    for wrong_root in (sibling, owned / ".worktrees" / "unregistered"):
        with pytest.raises((ActionContextError, StatusContractError)):
            reader(EventLogReadContract.owned_checkout(mission, repo_root=primary, owned_root=wrong_root))

    with pytest.raises((ActionContextError, StatusContractError)):
        reader(EventLogReadContract.owned_checkout(mission, repo_root=sibling, owned_root=owned))

    meta_path = mission / "meta.json"
    meta = json.loads(meta_path.read_text())
    meta.update(topology="coord", coordination_branch="coord/test")
    meta_path.write_text(json.dumps(meta))
    with pytest.raises((ActionContextError, StatusContractError)):
        reader(contract)


@pytest.mark.parametrize("reader", [read_event_log, read_event_stream_log])
def test_primary_contract_still_rejects_coordination_shaped_path(tmp_path: Path, reader):
    with pytest.raises(StatusContractError, match="primary_checkout"):
        reader(EventLogReadContract.primary_checkout(tmp_path / ".worktrees" / "coord" / "kitty-specs" / SLUG))
