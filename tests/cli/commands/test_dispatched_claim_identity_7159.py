"""#7159: the dispatched claim identity seam of ``implement_claim``.

``agent action implement`` hands the structured implementer actor and binding
annotation to the top-level ``implement`` command's claim through
:func:`~specify_cli.cli.commands.implement_claim.dispatched_claim_identity`. Outside
that block the claim records the command's own actor verbatim.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from specify_cli.cli.commands import implement_claim
from specify_cli.cli.commands.implement_claim import DispatchedClaimIdentity, _start_wp_implementation_status, dispatched_claim_identity

pytestmark = pytest.mark.unit

_ACTOR: dict[str, str | None] = {"role": "implementer", "tool": "claude", "model": None, "profile": "python-pedro"}


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(implement_claim, "start_implementation_status", lambda **kwargs: calls.append(kwargs))
    return calls


def _claim(tmp_path: Path) -> None:
    _start_wp_implementation_status(
        feature_dir=tmp_path,
        mission_slug="m",
        wp_id="WP01",
        effective_actor="claude",
        workspace_path=tmp_path,
        status_execution_mode="worktree",
        repo_root=tmp_path,
    )


def test_outside_the_block_the_claim_records_the_command_actor(tmp_path: Path, captured: list[dict[str, Any]]) -> None:
    _claim(tmp_path)
    assert captured[0]["actor"] == "claude"
    assert captured[0]["annotation_delta"] is None


def test_inside_the_block_the_claim_records_the_dispatched_identity(tmp_path: Path, captured: list[dict[str, Any]]) -> None:
    delta = cast(Any, object())  # a sentinel: the seam only passes it through
    with dispatched_claim_identity(DispatchedClaimIdentity(actor=_ACTOR, annotation_delta=delta)):
        _claim(tmp_path)
    assert captured[0]["actor"] == _ACTOR
    assert captured[0]["annotation_delta"] is delta
    # The claim triple keeps the bare agent the command was given.
    assert captured[0]["policy_metadata"]["agent"] == "claude"


def test_a_none_identity_keeps_the_command_actor(tmp_path: Path, captured: list[dict[str, Any]]) -> None:
    with dispatched_claim_identity(None):
        _claim(tmp_path)
    assert captured[0]["actor"] == "claude"


def test_the_identity_does_not_outlive_the_block(tmp_path: Path, captured: list[dict[str, Any]]) -> None:
    with pytest.raises(RuntimeError), dispatched_claim_identity(DispatchedClaimIdentity(actor=_ACTOR, annotation_delta=None)):
        raise RuntimeError("claim failed")
    _claim(tmp_path)
    assert captured[0]["actor"] == "claude"
