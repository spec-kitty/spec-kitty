"""``spec-kitty next`` missing-``--mission`` discovery (contract C5, FR-006..FR-012).

When ``next`` is invoked without ``--mission`` the command no longer dead-ends
on a required-flag *usage* error. Instead it discovers the mission population:

* exactly one mission  -> auto-select it and proceed (query mode, exit 0);
* more than one        -> list ``slug (mid8) - friendly_name`` and exit
                          non-zero (never a ``typer.BadParameter`` usage error);
* zero                 -> nudge the operator to ``specify`` and exit non-zero.

A sole *legacy* mission (``meta.json`` without ``mission_id``) is still
auto-selected, with an advisory ``backfill-identity`` nudge. A present-but-bad
handle (``--mission zznope``) keeps its pre-existing clean not-found envelope.

These tests exercise the real CLI in-process (``CliRunner``) over real git
repositories; usage *semantics* are asserted (exit code / absence of the
required-flag message), never the version-fragile literal ``"Invalid value"``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

# A syntactically valid 26-char ULID and its 8-char mid8 disambiguator.
_ULID_A = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
_MID8_A = _ULID_A[:8]
_ULID_B = "01BX5ZZKBKACTAV9WEVGEMMVRZ"
_MID8_B = _ULID_B[:8]


def _init_git_repo(path: Path) -> None:
    """Initialise a real git repo so main-repo/context detection works."""
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def _new_repo(tmp_path: Path, *, charter: bool = False) -> Path:
    """Return a fresh initialised repo root, optionally charter-provisioned."""
    repo_root = tmp_path / "project"
    repo_root.mkdir()
    _init_git_repo(repo_root)
    (repo_root / ".kittify").mkdir(exist_ok=True)
    if charter:
        provision_test_charter(repo_root)
        from specify_cli.identity.project import ensure_identity

        ensure_identity(repo_root)
    return repo_root


def _add_mission(
    repo_root: Path,
    slug: str,
    *,
    mission_id: str | None = None,
    friendly_name: str | None = None,
    mission_type: str = "software-dev",
) -> None:
    """Create ``kitty-specs/<slug>/meta.json`` (legacy when *mission_id* is None)."""
    feature_dir = repo_root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    meta: dict[str, object] = {"mission_type": mission_type}
    if mission_id is not None:
        meta["mission_id"] = mission_id
    if friendly_name is not None:
        meta["friendly_name"] = friendly_name
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


@pytest.fixture
def _bypass_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the charter preflight hook so tests reach the discovery logic.

    Deliberately NOT autouse: the FR-009 test omits it to prove the
    zero-mission nudge is reachable through the real (non-bypassed) preflight.
    """
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    ok = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_a, **_kw: ok,
    )
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_for_dashboard",
        lambda *_a, **_kw: ok,
    )


# ---------------------------------------------------------------------------
# (a) exactly one mission -> auto-select and proceed
# ---------------------------------------------------------------------------


def test_single_mission_auto_selected_bare_next(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _bypass_preflight: None) -> None:
    repo_root = _new_repo(tmp_path, charter=True)
    _add_mission(repo_root, "042-only-mission", mission_id=_ULID_A, friendly_name="Only Mission")
    monkeypatch.chdir(repo_root)

    result = runner.invoke(cli_app, ["next", "--json"])

    assert result.exit_code == 0, f"expected auto-select success; output:\n{result.output}"
    payload = json.loads(result.stdout)
    assert payload["mission_slug"] == "042-only-mission"


def test_single_mission_bare_next_has_no_usage_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _bypass_preflight: None) -> None:
    repo_root = _new_repo(tmp_path, charter=True)
    _add_mission(repo_root, "042-only-mission", mission_id=_ULID_A)
    monkeypatch.chdir(repo_root)

    result = runner.invoke(cli_app, ["next"])

    assert result.exit_code == 0, result.output
    assert "is required" not in result.output
    assert "Missing option" not in result.output


# ---------------------------------------------------------------------------
# (b) more than one mission -> list and exit non-zero (never a usage error)
# ---------------------------------------------------------------------------


def test_multiple_missions_listed_human(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _bypass_preflight: None) -> None:
    repo_root = _new_repo(tmp_path)
    _add_mission(repo_root, "042-alpha", mission_id=_ULID_A, friendly_name="Alpha Mission")
    _add_mission(repo_root, "043-beta", mission_id=_ULID_B, friendly_name="Beta Mission")
    monkeypatch.chdir(repo_root)

    result = runner.invoke(cli_app, ["next"])

    # Non-zero, but NOT a Typer usage error (that would be exit code 2).
    assert result.exit_code == 1, result.output
    assert "Missing option" not in result.output
    assert "is required" not in result.output
    # Each mission is rendered as ``slug (mid8) - friendly_name``.
    assert "042-alpha" in result.output
    assert _MID8_A in result.output
    assert "Alpha Mission" in result.output
    assert "043-beta" in result.output
    assert _MID8_B in result.output
    assert "--mission" in result.output


def test_multiple_missions_json_available_missions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _bypass_preflight: None) -> None:
    repo_root = _new_repo(tmp_path)
    _add_mission(repo_root, "042-alpha", mission_id=_ULID_A, friendly_name="Alpha Mission")
    _add_mission(repo_root, "043-beta", mission_id=_ULID_B, friendly_name="Beta Mission")
    monkeypatch.chdir(repo_root)

    result = runner.invoke(cli_app, ["next", "--json"])

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["result"] == "error"
    available = payload["available_missions"]
    slugs = {row["mission_slug"] for row in available}
    assert slugs == {"042-alpha", "043-beta"}
    by_slug = {row["mission_slug"]: row for row in available}
    assert by_slug["042-alpha"]["mid8"] == _MID8_A
    assert by_slug["042-alpha"]["friendly_name"] == "Alpha Mission"


def test_multiple_missions_backfill_nudge_when_legacy_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _bypass_preflight: None) -> None:
    repo_root = _new_repo(tmp_path)
    _add_mission(repo_root, "042-alpha", mission_id=_ULID_A)
    _add_mission(repo_root, "043-legacy")  # no mission_id
    monkeypatch.chdir(repo_root)

    result = runner.invoke(cli_app, ["next"])

    assert result.exit_code == 1, result.output
    assert "backfill-identity" in result.output


# ---------------------------------------------------------------------------
# (c) zero missions -> nudge to specify, exit non-zero
# ---------------------------------------------------------------------------


def test_zero_missions_nudge_human(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _bypass_preflight: None) -> None:
    repo_root = _new_repo(tmp_path)
    monkeypatch.chdir(repo_root)

    result = runner.invoke(cli_app, ["next"])

    assert result.exit_code != 0
    assert "Missing option" not in result.output
    assert "No missions" in result.output
    assert "specify" in result.output.lower()


def test_zero_missions_nudge_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _bypass_preflight: None) -> None:
    repo_root = _new_repo(tmp_path)
    monkeypatch.chdir(repo_root)

    result = runner.invoke(cli_app, ["next", "--json"])

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["result"] == "error"
    assert payload["error_code"] == "NO_MISSIONS_FOUND"


# ---------------------------------------------------------------------------
# (d) sole LEGACY mission (no mission_id) -> auto-selected + backfill nudge
# ---------------------------------------------------------------------------


def test_sole_legacy_mission_auto_selected_with_backfill_nudge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _bypass_preflight: None) -> None:
    repo_root = _new_repo(tmp_path, charter=True)
    _add_mission(repo_root, "042-legacy-only")  # no mission_id -> legacy
    monkeypatch.chdir(repo_root)

    result = runner.invoke(cli_app, ["next"])

    # Still auto-selected (proceeds to query mode), NOT a "no missions" nudge.
    assert result.exit_code == 0, result.output
    assert "No missions" not in result.output
    assert "backfill-identity" in result.output


# ---------------------------------------------------------------------------
# (e) regression: present-but-bad handle keeps the clean not-found envelope
# ---------------------------------------------------------------------------


def test_present_but_bad_handle_still_clean_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _bypass_preflight: None) -> None:
    repo_root = _new_repo(tmp_path)
    _add_mission(repo_root, "042-real-mission", mission_id=_ULID_A)
    monkeypatch.chdir(repo_root)

    result = runner.invoke(cli_app, ["next", "--mission", "zznope", "--json"])

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["error_code"] == "MISSION_NOT_FOUND"
    assert payload["handle"] == "zznope"


# ---------------------------------------------------------------------------
# (f) FR-009: zero-mission nudge reachable WITHOUT bypassing charter preflight
# ---------------------------------------------------------------------------


def test_zero_missions_nudge_reachable_without_preflight_bypass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # No ``_bypass_preflight`` fixture: query mode runs the real dashboard
    # preflight (warn-and-continue) so the nudge must still be reachable.
    repo_root = _new_repo(tmp_path)
    monkeypatch.chdir(repo_root)

    result = runner.invoke(cli_app, ["next"])

    assert result.exit_code != 0
    assert "No missions" in result.output
