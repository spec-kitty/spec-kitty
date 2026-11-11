"""#7552: a failed flatten bookkeeping commit tells the operator a remedy that works.

``doctor coordination --fix`` now refuses without a scope, so the fail-open log
lines of ``_flatten_coordination_metadata_after_branch_delete`` must name the
Mission (``--fix --mission <slug>``) or the operator follows them into
``COORDINATION_FIX_SCOPE_REQUIRED``. Both failure arms are driven here: a
recovery failure whose commit did not land, and any other commit error. The
behaviour around them (fail-open, never raise) is unchanged.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.consolidation import phase_teardown
from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed

pytestmark = [pytest.mark.unit]

_SLUG = "alpha-mission-01J6XW9K"


def _run(tmp_path: Path) -> SimpleNamespace:
    feature_dir = tmp_path / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{}")
    return SimpleNamespace(
        target_feature_dir=feature_dir,
        main_repo=tmp_path,
        mission_slug=_SLUG,
        lanes_manifest=SimpleNamespace(target_branch="main"),
    )


@pytest.mark.parametrize(
    "failure",
    [
        SafeCommitRecoveryFailed("commit did not land", commit_sha=None),
        RuntimeError("git exploded"),
    ],
    ids=["recovery-failed-not-landed", "other-commit-error"],
)
def test_failed_flatten_commit_logs_a_scoped_doctor_remedy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    failure: Exception,
) -> None:
    monkeypatch.setattr("specify_cli.mission_metadata.flatten_coordination_metadata", lambda _dir: True)
    monkeypatch.setattr(phase_teardown, "_paths_have_status_changes", lambda _repo, _paths: True)

    def _raise(**_kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(phase_teardown, "commit_merge_bookkeeping", _raise)

    with caplog.at_level(logging.WARNING, logger=phase_teardown.logger.name):
        phase_teardown._flatten_coordination_metadata_after_branch_delete(_run(tmp_path))  # fail-open: no raise

    assert f"spec-kitty doctor coordination --fix --mission {_SLUG}" in caplog.text


def test_a_recovered_flatten_commit_logs_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """Positive control: a recovery failure whose commit DID land is a success, not a warning."""
    monkeypatch.setattr("specify_cli.mission_metadata.flatten_coordination_metadata", lambda _dir: True)
    monkeypatch.setattr(phase_teardown, "_paths_have_status_changes", lambda _repo, _paths: True)

    def _raise(**_kwargs: object) -> None:
        raise SafeCommitRecoveryFailed("recovered", commit_sha="abc123")

    monkeypatch.setattr(phase_teardown, "commit_merge_bookkeeping", _raise)

    with caplog.at_level(logging.WARNING, logger=phase_teardown.logger.name):
        phase_teardown._flatten_coordination_metadata_after_branch_delete(_run(tmp_path))

    assert "doctor coordination" not in caplog.text
