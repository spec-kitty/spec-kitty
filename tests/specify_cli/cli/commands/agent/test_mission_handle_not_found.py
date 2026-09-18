"""WP03 (FR-002/FR-003): truthful not-found for an explicit unmatched handle.

When ``plan``/``tasks`` receive an explicit ``--mission <handle>`` that matches
no mission, they must emit the canonical ``Mission not found: <handle>`` — NOT
the misleading "N missions found, pass --mission <slug> to disambiguate" string,
which was written for the *different* no-handle auto-detect-failed case.

The fix lives in ``_build_setup_plan_detection_error``: it branches on the
presence of a non-empty explicit handle plus the not-found signal. This module
pins both halves of that branch:

* Explicit unmatched handle -> canonical not-found (the WP03 behavior change).
* No handle + multiple missions -> disambiguate payload (regression guard; the
  pinned behavior in ``test_mission_feature_resolution.py`` /
  ``tests/agent/test_agent_feature.py`` must stay green).

The unit-level tests drive the builder directly (deterministic, no CLI boot);
the CLI-level tests prove both call-sites (``setup-plan`` and
``check-prerequisites``) surface the corrected message end to end.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from mission_runtime import ActionContextError
from specify_cli.cli.commands.agent import mission_feature_resolution as seam
from specify_cli.cli.commands.agent.mission import app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

# The authentic not-found message ``_find_feature_directory`` raises for an
# explicit handle that resolves to no mission directory.
_NOT_FOUND_ERROR = "Mission not found for handle 'zznope'; checked the coordination worktree and the primary checkout."
_DISAMBIGUATE_FRAGMENTS = ("missions found", "to disambiguate")


def _make_mission(specs: Path, slug: str) -> None:
    d = specs / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "spec.md").write_text("# Spec\n", encoding="utf-8")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A repo root with a ``kitty-specs`` directory holding two missions."""
    specs = tmp_path / "kitty-specs"
    specs.mkdir(parents=True, exist_ok=True)
    _make_mission(specs, "001-alpha")
    _make_mission(specs, "002-beta")
    return tmp_path


# ---------------------------------------------------------------------------
# Builder-level: the WP03 branch (deterministic, no CLI boot)
# ---------------------------------------------------------------------------


def test_explicit_unmatched_handle_yields_canonical_not_found(repo: Path) -> None:
    """Explicit handle + not-found error -> canonical ``Mission not found``."""
    payload = seam._build_setup_plan_detection_error(repo, _NOT_FOUND_ERROR, "zznope")

    assert payload["error"] == "Mission not found: zznope"
    error_text = str(payload["error"])
    for fragment in _DISAMBIGUATE_FRAGMENTS:
        assert fragment not in error_text
    # The not-found branch is a clean message — no disambiguate scaffolding.
    assert "available_missions" not in payload
    assert "example_command" not in payload
    assert payload["mission_flag"] == "zznope"
    assert payload["error_code"] == "PLAN_CONTEXT_UNRESOLVED"
    assert "spec_kitty_version" in payload


def test_explicit_unmatched_handle_check_prerequisites_error_code(repo: Path) -> None:
    """The check-prerequisites caller's error_code override is preserved."""
    payload = seam._build_setup_plan_detection_error(
        repo,
        _NOT_FOUND_ERROR,
        "zznope",
        error_code="FEATURE_CONTEXT_UNRESOLVED",
        command_name="check-prerequisites",
    )

    assert payload["error"] == "Mission not found: zznope"
    assert payload["error_code"] == "FEATURE_CONTEXT_UNRESOLVED"


def test_no_handle_multi_mission_preserves_disambiguate(repo: Path) -> None:
    """Regression: no explicit handle + >1 mission -> disambiguate payload."""
    payload = seam._build_setup_plan_detection_error(repo, "base", None)

    assert payload["available_missions"] == ["001-alpha", "002-beta"]
    assert "2 missions found" in str(payload["error"])
    assert "to disambiguate" in str(payload["error"])
    assert payload["remediation"] == "Re-run with --mission <slug>"


def test_no_missions_payload_unchanged(repo: Path) -> None:
    """Regression: zero-mission branch is byte-unchanged (no candidates)."""
    empty = repo / "empty"
    (empty / "kitty-specs").mkdir(parents=True)
    payload = seam._build_setup_plan_detection_error(empty, "base", None)

    assert payload["error"] == "No missions found in kitty-specs/"
    assert "available_missions" not in payload


def test_ambiguous_handle_is_not_treated_as_not_found(repo: Path) -> None:
    """An ambiguous (not not-found) error with a handle keeps the count payload.

    The WP03 branch keys on the *not-found* signal specifically; an ambiguous
    handle is a distinct condition and must not be relabeled ``Mission not
    found``.
    """
    payload = seam._build_setup_plan_detection_error(repo, "Ambiguous handle 'a' matches: 001-alpha, 002-beta", "a")

    assert payload["error"] != "Mission not found: a"
    assert "missions found" in str(payload["error"])


# ---------------------------------------------------------------------------
# CLI-level: both call-sites surface the corrected message
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.agent.mission.locate_project_root")
@patch("specify_cli.cli.commands.agent.mission._find_feature_directory")
def test_setup_plan_explicit_unmatched_handle_json(mock_find: Mock, mock_locate: Mock, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """setup-plan --mission zznope -> canonical not-found JSON, not disambiguate."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    mock_locate.return_value = repo
    mock_find.side_effect = ActionContextError("FEATURE_CONTEXT_UNRESOLVED", _NOT_FOUND_ERROR)

    result = runner.invoke(app, ["setup-plan", "--mission", "zznope", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout.strip().split("\n")[0])
    assert payload["error"] == "Mission not found: zznope"
    for fragment in _DISAMBIGUATE_FRAGMENTS:
        assert fragment not in result.stdout


@patch("specify_cli.cli.commands.agent.mission.locate_project_root")
@patch("specify_cli.cli.commands.agent.mission._find_feature_directory")
def test_setup_plan_explicit_unmatched_handle_human(mock_find: Mock, mock_locate: Mock, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """setup-plan human output surfaces the canonical not-found message."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    mock_locate.return_value = repo
    mock_find.side_effect = ActionContextError("FEATURE_CONTEXT_UNRESOLVED", _NOT_FOUND_ERROR)

    result = runner.invoke(app, ["setup-plan", "--mission", "zznope"])

    assert result.exit_code == 1
    assert "Mission not found: zznope" in result.stdout
    for fragment in _DISAMBIGUATE_FRAGMENTS:
        assert fragment not in result.stdout


@patch("specify_cli.cli.commands.agent.mission.locate_project_root")
@patch("specify_cli.cli.commands.agent.mission._primary_anchored_feature_dir")
@patch("specify_cli.cli.commands.agent.mission._find_feature_directory")
def test_check_prerequisites_explicit_unmatched_handle_json(
    mock_find: Mock,
    mock_anchor: Mock,
    mock_locate: Mock,
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """check-prerequisites --mission zznope -> canonical not-found JSON."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    mock_locate.return_value = repo
    mock_anchor.return_value = None
    mock_find.side_effect = ActionContextError("FEATURE_CONTEXT_UNRESOLVED", _NOT_FOUND_ERROR)

    result = runner.invoke(app, ["check-prerequisites", "--mission", "zznope", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout.strip().split("\n")[0])
    assert payload["error"] == "Mission not found: zznope"
    assert payload["error_code"] == "FEATURE_CONTEXT_UNRESOLVED"
    for fragment in _DISAMBIGUATE_FRAGMENTS:
        assert fragment not in result.stdout


@patch("specify_cli.cli.commands.agent.mission.locate_project_root")
@patch("specify_cli.cli.commands.agent.mission._find_feature_directory")
def test_setup_plan_no_handle_multi_mission_keeps_disambiguate(mock_find: Mock, mock_locate: Mock, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: no --mission + >1 mission still emits the disambiguate payload."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    mock_locate.return_value = repo
    mock_find.side_effect = ValueError("Multiple missions found")

    result = runner.invoke(app, ["setup-plan", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout.strip().split("\n")[0])
    assert payload["available_missions"] == ["001-alpha", "002-beta"]
    assert "to disambiguate" in str(payload["error"])
