"""``consolidate-mission`` reports a mission branch that moved after landing by CODE (#5613).

``docs/api/orchestrator-api.md`` tells callers to key on codes, not prose. The refusal
keeps its ``PREFLIGHT_FAILED`` envelope and its message; the stable code travels in
``data["teardown_error_code"]``, the way ``_fail_from_destructive_op_refused`` carries
``data["destructive_op_error_code"]``.

Drives the real ``consolidate_mission`` entry point. The merge body is replaced by the
REAL ``_delete_mission_branch_at`` on a real repository whose mission branch moved past
the approved tip, so both the raise site and the envelope are exercised.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer

from specify_cli.lanes.models import LanesManifest
from specify_cli.orchestrator_api import _common, consolidation
from specify_cli.orchestrator_api.consolidation import _MergePreflightResult, consolidate_mission

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

MISSION_BRANCH = "kitty/mission-moved-01M5613O"
_IDENTITY = {"mission_slug": "some-mission", "mission_number": None, "mission_type": "software-dev"}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug="some-mission",
        mission_id="some-mission",
        mission_branch=MISSION_BRANCH,
        target_branch="main",
        lanes=[],
        computed_at="2026-01-01T00:00:00+00:00",
        computed_from="test",
    )


@pytest.fixture
def moved(tmp_path: Path) -> tuple[Path, str, str]:
    """``(repo, approved tip, late tip)``: the mission branch moved past the tip the cleanup approved."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.email", "t@example.com"), ("user.name", "Test"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    approved = _git(repo, "rev-parse", "HEAD")
    late = _git(repo, "commit-tree", f"{approved}^{{tree}}", "-p", approved, "-m", "late status emit")
    _git(repo, "update-ref", f"refs/heads/{MISSION_BRANCH}", late)
    return repo, approved, late


def _run_consolidate_mission(repo: Path, merge_body: Any, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    mission_dir = repo / "kitty-specs" / "some-mission"
    mission_dir.mkdir(parents=True)
    with (
        patch.object(_common, "_get_main_repo_root", return_value=repo),
        patch.object(_common, "_resolve_mission_dir_or_fail", return_value=mission_dir),
        patch.object(consolidation, "_build_merge_preflight", return_value=_MergePreflightResult(target_branch="main", errors=[])),
        patch.object(consolidation, "_execute_lane_merge", side_effect=merge_body),
        patch.object(_common, "_mission_identity_payload", return_value=dict(_IDENTITY)),
        pytest.raises(typer.Exit) as excinfo,
    ):
        consolidate_mission(mission="some-mission", target=None, strategy="merge", push=False, origin_check=None)
    assert excinfo.value.exit_code == 1
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly one JSON envelope line, got: {lines!r}"
    envelope: dict[str, Any] = json.loads(lines[0])
    return envelope


def test_a_moved_mission_branch_carries_its_code_in_the_envelope_data(moved: tuple[Path, str, str], capsys: pytest.CaptureFixture[str]) -> None:
    repo, approved, late = moved

    def _cleanup(*_args: object, **_kwargs: object) -> None:
        consolidation._delete_mission_branch_at(repo, _manifest(), approved)

    envelope = _run_consolidate_mission(repo, _cleanup, capsys)

    assert envelope["success"] is False and envelope["error_code"] == "PREFLIGHT_FAILED"
    assert envelope["data"]["teardown_error_code"] == "COORD_MOVED_AFTER_LANDING"
    (error,) = envelope["data"]["errors"]
    assert MISSION_BRANCH in error and late[:12] in error, "the message names the branch and the moved tip"
    assert error.endswith("Error code: COORD_MOVED_AFTER_LANDING.")
    assert _git(repo, "rev-parse", f"refs/heads/{MISSION_BRANCH}") == late, "the late commit stays reachable"


def test_any_other_merge_failure_carries_no_teardown_code(moved: tuple[Path, str, str], capsys: pytest.CaptureFixture[str]) -> None:
    repo, _approved, _late = moved

    envelope = _run_consolidate_mission(repo, RuntimeError("lane merge failed"), capsys)

    assert envelope["error_code"] == "PREFLIGHT_FAILED"
    assert envelope["data"]["errors"] == ["lane merge failed"]
    assert "teardown_error_code" not in envelope["data"]


_BOTH_CODES = ("LANE_MOVED_AFTER_APPROVAL", "APPROVAL_STAMP_MISSING")


@pytest.mark.parametrize(
    ("error_code", "error_codes", "expected", "expected_list"),
    [
        ("LANE_MOVED_AFTER_APPROVAL", None, "LANE_MOVED_AFTER_APPROVAL", ["LANE_MOVED_AFTER_APPROVAL"]),
        ("LANE_MOVED_AFTER_APPROVAL", _BOTH_CODES, "LANE_MOVED_AFTER_APPROVAL", list(_BOTH_CODES)),
        (None, None, None, None),
    ],
)
def test_an_approved_bound_refusal_carries_its_codes_beside_the_unchanged_envelope(
    moved: tuple[Path, str, str],
    capsys: pytest.CaptureFixture[str],
    error_code: str | None,
    error_codes: tuple[str, ...] | None,
    expected: str | None,
    expected_list: list[str] | None,
) -> None:
    """#5668, #5720: ``preflight_error_code`` (first code) and ``preflight_error_codes`` (every distinct code) are additive; no code leaves both out."""
    repo, _approved, _late = moved
    refusal = consolidation.ApprovedBoundRefused("a lane holds work review did not approve", error_code=error_code, error_codes=error_codes)

    envelope = _run_consolidate_mission(repo, refusal, capsys)

    assert envelope["error_code"] == "PREFLIGHT_FAILED" and envelope["data"]["errors"] == ["a lane holds work review did not approve"]
    assert envelope["data"].get("preflight_error_code") == expected
    assert envelope["data"].get("preflight_error_codes") == expected_list
    assert ("preflight_error_code" in envelope["data"]) is (expected is not None)
