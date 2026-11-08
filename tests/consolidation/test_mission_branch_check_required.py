"""The one predicate deciding whether consolidation checks the recorded Mission branch (#7267).

``executor`` (the real run) and ``forecast`` (``--dry-run``) both call
``mission_branch_check_required``; these pin its three branches so the two cannot drift.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from specify_cli.consolidation import preflight

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO = Path("/repo")


@pytest.fixture
def patch_inputs(monkeypatch: pytest.MonkeyPatch):
    def _apply(*, planning_only: bool, lands_branch: bool = False, landing_verified: bool = False) -> None:
        monkeypatch.setattr("specify_cli.lanes.compute.is_planning_artifact_only", lambda _manifest: planning_only)
        monkeypatch.setattr("specify_cli.lanes.single_branch_landing.lands_mission_branch", lambda _repo, _manifest: lands_branch)
        monkeypatch.setattr("specify_cli.consolidation.run_state.landing_verified_for_resume", lambda _repo, _state: landing_verified)

    return _apply


def test_planning_only_manifest_skips_the_check(patch_inputs) -> None:
    patch_inputs(planning_only=True)
    assert preflight.mission_branch_check_required(_REPO, MagicMock(), None) is False


def test_planning_only_manifest_that_lands_a_mission_branch_is_checked(patch_inputs) -> None:
    patch_inputs(planning_only=True, lands_branch=True)
    assert preflight.mission_branch_check_required(_REPO, MagicMock(), None) is True


def test_resume_after_a_verified_landing_skips_the_check(patch_inputs) -> None:
    patch_inputs(planning_only=False, landing_verified=True)
    state = SimpleNamespace(cleanup_started=True)
    assert preflight.mission_branch_check_required(_REPO, MagicMock(), state) is False


def test_resume_whose_cleanup_has_not_started_is_checked(patch_inputs) -> None:
    patch_inputs(planning_only=False, landing_verified=True)
    state = SimpleNamespace(cleanup_started=False)
    assert preflight.mission_branch_check_required(_REPO, MagicMock(), state) is True


def test_normal_run_is_checked(patch_inputs) -> None:
    patch_inputs(planning_only=False)
    assert preflight.mission_branch_check_required(_REPO, MagicMock(), None) is True
