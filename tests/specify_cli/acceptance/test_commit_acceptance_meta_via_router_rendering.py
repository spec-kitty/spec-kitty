"""T088 (D8): per-surface rendering at ``_commit_acceptance_meta_via_router``'s two commits.

WP16 (coord-artifact-single-home-01M3V4BE) adds a render of the FIRST commit's
outcome through the shared ``render_commit_outcome`` trio (non-blocking trace
alongside the existing ``AcceptanceError`` semantics), and a WARNING -- never a
raise -- when the SECOND commit (recording ``accept_commit`` back into
``meta.json``) does not land cleanly on every surface. Before this WP the
second commit's result was discarded entirely.

This is a narrow unit test of the function in isolation: ``commit_for_mission``
is monkeypatched at its import source (``specify_cli.coordination.commit_router``)
to return two different, hand-built ``CommitRouterResult`` values in sequence --
the first a clean ``committed``, the second carrying a ``refused`` surface --
so the test proves the warning fires without needing a real git-backed
protected-branch fixture.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from specify_cli.acceptance import _commit_acceptance_meta_via_router
from specify_cli.coordination.commit_outcome import PathFate, SurfaceOutcome
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.git.protection_policy import ProtectionPolicy


def test_second_commit_surface_not_landing_warns_but_does_not_raise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    repo_root = tmp_path / "repo"
    meta_path = repo_root / "kitty-specs" / "m" / "meta.json"
    meta_path.parent.mkdir(parents=True)
    meta_path.write_text(
        json.dumps(
            {
                "mission_slug": "m",
                "slug": "m",
                "friendly_name": "m",
                "mission_type": "software-dev",
                "target_branch": "topic",
                "created_at": "2026-01-01T00:00:00Z",
                "acceptance_history": [{}],
            }
        ),
        encoding="utf-8",
    )

    first_result = CommitRouterResult(
        status="committed",
        placement_ref="topic",
        commit_hash="abc1234",
        surfaces=(SurfaceOutcome(surface="primary", branch="topic", status="committed", commit_hash="abc1234", committed=("kitty-specs/m/meta.json",)),),
    )
    second_result = CommitRouterResult(
        status="error",
        placement_ref="topic",
        surfaces=(
            SurfaceOutcome(
                surface="coordination",
                branch="kitty/mission-m-01ABCDEF",
                status="refused",
                commit_hash=None,
                refused=(PathFate(path="kitty-specs/m/meta.json", reason="STATUS_LOCK_HELD"),),
                diagnostic="status lock held",
            ),
        ),
    )
    calls: list[CommitRouterResult] = [first_result, second_result]

    def _fake_commit_for_mission(*_args: object, **_kwargs: object) -> CommitRouterResult:
        return calls.pop(0)

    monkeypatch.setattr("specify_cli.coordination.commit_router.commit_for_mission", _fake_commit_for_mission)

    with caplog.at_level(logging.WARNING, logger="specify_cli.acceptance"):
        parent_commit, accept_commit, commit_created = _commit_acceptance_meta_via_router(
            repo_root=repo_root,
            mission_slug="m",
            meta_path=meta_path,
            policy=ProtectionPolicy.resolve(repo_root),
            parent_commit=None,
        )

    assert accept_commit == "abc1234"
    assert commit_created is True
    warning_messages = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert any("coordination" in message and "did not land" in message for message in warning_messages), warning_messages
