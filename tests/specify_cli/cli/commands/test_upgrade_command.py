"""Integration tests for ``spec-kitty upgrade`` command surface — T038.

Covers the FR-023 case matrix:
  1. cli_update_available       -- outdated CLI, compatible project
  2. project_migration_needed   -- stale project (schema 1)
  3. project_too_new_for_cli    -- too-new project (schema 7)
  4. project_not_initialized    -- no project at all
  5. install_method_unknown     -- UNKNOWN install method

Plus:
  - Mutual exclusion: --cli + --project → exit 2
  - --yes alias: same effect as --force; --yes --force allowed together
  - JSON output validates against contracts/compat-planner.json key set

JSON contract validation uses ``jsonschema`` if available; otherwise falls
back to a hand-check of required top-level keys and their types.

Exit-code assertions honour CHK037 / A-006: --yes does NOT bypass
BLOCK_CLI_UPGRADE (project_too_new_for_cli stays exit 5).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer
import yaml
from typer.testing import CliRunner

from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.compat.planner import Invocation as _Invocation
from specify_cli.compat.planner import ProjectState
from specify_cli.compat.provider import FakeLatestVersionProvider, LatestVersionResult

# ---------------------------------------------------------------------------
# Contract path (relative to repo root)
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Strip rich's ANSI color codes so substring assertions are robust.

    Rich auto-highlights numerics (e.g. ``schema \x1b[1;36m7\x1b[0m``,
    ``\x1b[1;36m3.1\x1b[0m.\x1b[1;36m0\x1b[0m``), which breaks plain substring
    checks against the rendered output. Strip the codes to pin the message text
    contract without coupling to the highlighter.
    """
    return _ANSI_RE.sub("", text)


_WORKTREE_ROOT = Path(__file__).parent.parent.parent.parent.parent  # repo root
_CONTRACT_PATH = (
    _WORKTREE_ROOT
    / "kitty-specs"
    / "cli-upgrade-nag-lazy-project-migrations-01KQ6YDN"
    / "contracts"
    / "compat-planner.json"
)


def _load_contract(contract_path: Path) -> dict[str, Any]:
    """Load and parse the JSON contract at *contract_path*.

    Fails hard (raises ``FileNotFoundError`` / ``json.JSONDecodeError``) on a
    missing or malformed contract — no silent ``None`` fallback. Extracted
    to a pure, parameterized seam so the fail-hard behaviour is directly
    testable (T006) without reimporting this module or monkeypatching
    globals.
    """
    raw: Any = json.loads(contract_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"Contract at {contract_path} must be a JSON object, got {type(raw).__name__}")
    return raw


# Load the contract unconditionally — a missing/unreadable contract must
# raise, never silently degrade to a skipped check (see #2339 / WP01).
_CONTRACT: dict[str, Any] = _load_contract(_CONTRACT_PATH)

# Required top-level keys from contracts/compat-planner.json
_REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "case",
    "decision",
    "exit_code",
    "cli",
    "project",
    "safety",
    "install_method",
    "upgrade_hint",
    "pending_migrations",
    "rendered_human",
}

# ---------------------------------------------------------------------------
# Test app (minimal — no full-app side-effects)
# ---------------------------------------------------------------------------

_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Contract validation helpers (T037)
# ---------------------------------------------------------------------------


def _validate_json_contract(payload: dict[str, Any]) -> None:
    """Validate *payload* against the compat-planner.json contract.

    Uses ``jsonschema`` when available; otherwise hand-checks required keys
    and types.
    """
    try:
        import jsonschema  # type: ignore[import]

        jsonschema.validate(instance=payload, schema=_CONTRACT)
        return
    except ImportError:
        pass  # Fall through to hand-check

    # Hand-check required keys
    missing = _REQUIRED_TOP_LEVEL_KEYS - set(payload.keys())
    assert not missing, f"JSON output missing required keys: {missing}"

    # schema_version must be 1
    assert payload["schema_version"] == 1, f"Expected schema_version=1, got {payload['schema_version']!r}"

    # case must be one of the enumerated tokens
    valid_cases = {
        "none",
        "cli_update_available",
        "project_migration_needed",
        "project_too_new_for_cli",
        "project_not_initialized",
        "project_metadata_corrupt",
        "install_method_unknown",
    }
    assert payload["case"] in valid_cases, f"case {payload['case']!r} not in {valid_cases}"

    # exit_code must be int in [0, 255]
    ec = payload["exit_code"]
    assert isinstance(ec, int) and 0 <= ec <= 255, f"exit_code={ec!r} out of range"

    # cli sub-object
    cli_obj = payload["cli"]
    for k in ("installed_version", "is_outdated", "latest_source"):
        assert k in cli_obj, f"cli.{k} missing"

    # project sub-object
    proj_obj = payload["project"]
    for k in ("state", "min_supported", "max_supported"):
        assert k in proj_obj, f"project.{k} missing"

    # upgrade_hint — exactly one of command/note non-null
    hint = payload["upgrade_hint"]
    cmd = hint.get("command")
    note = hint.get("note")
    assert (cmd is None) != (note is None), f"upgrade_hint must have exactly one of command/note non-null; got command={cmd!r}, note={note!r}"

    # pending_migrations is an array
    assert isinstance(payload["pending_migrations"], list), "pending_migrations must be a list"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_compatible_project(tmp_path: Path, schema_version: int = 3) -> Path:
    """Create a minimal Spec Kitty project with the given schema version."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "metadata.yaml").write_text(
        f"spec_kitty:\n  schema_version: {schema_version}\n",
        encoding="utf-8",
    )
    return tmp_path


def _invoke_upgrade(args: list[str], cwd: Path) -> Any:
    """Invoke the upgrade command with the given args from *cwd*."""
    old_cwd = os.getcwd()
    try:
        os.chdir(cwd)
        return runner.invoke(_test_app, args, catch_exceptions=False)
    finally:
        os.chdir(old_cwd)


# ---------------------------------------------------------------------------
# T034 — Mutual exclusion: --cli + --project → exit 2
# ---------------------------------------------------------------------------


def test_cli_and_project_mutex_exits_2(tmp_path: Path) -> None:
    """--cli and --project together must exit 2 (BLOCK_INCOMPATIBLE_FLAGS)."""
    result = _invoke_upgrade(["--cli", "--project"], cwd=tmp_path)
    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}. Output: {result.output}"
    assert "mutually exclusive" in result.output.lower() or "exclusive" in result.output.lower()


def test_cli_and_project_mutex_error_message(tmp_path: Path) -> None:
    """--cli --project error message mentions both flags."""
    result = _invoke_upgrade(["--cli", "--project"], cwd=tmp_path)
    assert "--cli" in result.output or "cli" in result.output.lower()
    assert "--project" in result.output or "project" in result.output.lower()


def test_agent_check_json_prompts_when_update_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.compat._detect.install_method import InstallMethod
    from specify_cli.compat.cache import NagCache
    from specify_cli.compat.provider import PyPIProvider

    monkeypatch.setattr("specify_cli.compat.cache.NagCache.default", lambda: NagCache(tmp_path / "agent-cache.json"))
    monkeypatch.setattr(
        PyPIProvider,
        "get_latest",
        lambda self, package: LatestVersionResult("999.0.0", "pypi", None),
    )
    monkeypatch.setattr("specify_cli.compat._detect.install_method.detect_install_method", lambda: InstallMethod.PIPX)
    # The agent-check producer builds its Invocation with ``env_ci=is_ci_env()``;
    # under CI the planner selects NoNetworkProvider and the PyPIProvider mock
    # never fires (latest_version stays None → action=none). Pin network-allowed
    # so the real "update available → prompt" decision path is the one exercised,
    # independent of whether the suite itself runs in a CI environment.
    monkeypatch.setattr("specify_cli.compat.is_ci_env", lambda: False)

    result = _invoke_upgrade(["--agent-check", "--json"], cwd=tmp_path)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["action"] == "prompt"
    assert payload["latest_version"] == "999.0.0"
    assert "upgrade_command" in payload


def test_agent_check_guidance_when_upgrade_command_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specify_cli.compat._detect.install_method import InstallMethod
    from specify_cli.compat.cache import NagCache
    from specify_cli.compat.provider import PyPIProvider

    monkeypatch.setattr("specify_cli.compat.cache.NagCache.default", lambda: NagCache(tmp_path / "agent-cache.json"))
    monkeypatch.setattr(
        PyPIProvider,
        "get_latest",
        lambda self, package: LatestVersionResult("999.0.0", "pypi", None),
    )
    monkeypatch.setattr("specify_cli.compat._detect.install_method.detect_install_method", lambda: InstallMethod.UNKNOWN)
    # See test_agent_check_json_prompts_when_update_available: pin network-allowed
    # so the PyPIProvider mock fires under CI and the real "manual upgrade required
    # → guidance" path is exercised rather than the CI network-suppressed action=none.
    monkeypatch.setattr("specify_cli.compat.is_ci_env", lambda: False)

    result = _invoke_upgrade(["--agent-check", "--json"], cwd=tmp_path)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["action"] == "guidance"
    assert payload["reason"] == "manual_upgrade_required"
    assert payload["upgrade_command"] is None
    assert payload["upgrade_note"]


def test_agent_check_uv_tool_command_targets_latest_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.compat._detect.install_method import InstallMethod
    from specify_cli.compat.cache import NagCache
    from specify_cli.compat.provider import PyPIProvider

    monkeypatch.setattr("specify_cli.compat.cache.NagCache.default", lambda: NagCache(tmp_path / "agent-cache.json"))
    # Use a high sentinel for the mocked "latest" (matching the 999.0.0 convention
    # in test_agent_choice_not_now_records_snooze) so this stays > the installed
    # package version across release bumps and the upgrade-available ('prompt')
    # path is always exercised — never coupled to the current pyproject version.
    monkeypatch.setattr(
        PyPIProvider,
        "get_latest",
        lambda self, package: LatestVersionResult("999.0.0", "pypi", None),
    )
    monkeypatch.setattr("specify_cli.compat._detect.install_method.detect_install_method", lambda: InstallMethod.UV_TOOL)
    monkeypatch.setattr("specify_cli.compat.is_ci_env", lambda: False)

    result = _invoke_upgrade(["--agent-check", "--json"], cwd=tmp_path)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["action"] == "prompt"
    assert payload["upgrade_command"] == "uv tool install --force spec-kitty-cli==999.0.0"


def test_agent_choice_not_now_records_snooze(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.compat.cache import NagCache

    cache = NagCache(tmp_path / "agent-cache.json")
    monkeypatch.setattr("specify_cli.compat.cache.NagCache.default", lambda: cache)

    result = _invoke_upgrade(
        ["--agent-choice", "not_now", "--agent-latest", "999.0.0", "--json"],
        cwd=tmp_path,
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "recorded"
    record = cache.read()
    assert record is not None
    assert record.remote_version_seen == "999.0.0"
    assert record.snooze_step == "24h"
    assert record.snoozed_until is not None


# ---------------------------------------------------------------------------
# T034 — --yes alias tests
# ---------------------------------------------------------------------------


def test_yes_and_force_produce_same_effect(tmp_path: Path) -> None:
    """--yes and --force are syntactically accepted (no error)."""
    _make_compatible_project(tmp_path)
    # Both flags accepted (may or may not have migrations; we just check no crash on flag parsing)
    result_yes = _invoke_upgrade(["--dry-run", "--yes"], cwd=tmp_path)
    result_force = _invoke_upgrade(["--dry-run", "--force"], cwd=tmp_path)
    # Both should succeed (same exit code)
    assert result_yes.exit_code == result_force.exit_code


def test_yes_and_force_together_allowed(tmp_path: Path) -> None:
    """--yes --force together is not an error (both are the same confirmation flag)."""
    _make_compatible_project(tmp_path)
    result = _invoke_upgrade(["--dry-run", "--yes", "--force"], cwd=tmp_path)
    # Should not exit 2 (no mutual exclusion error)
    assert result.exit_code != 2


# ---------------------------------------------------------------------------
# FR-023 case 1: cli_update_available
# ---------------------------------------------------------------------------


def test_cli_update_available_dry_run_shows_nag(tmp_path: Path) -> None:
    """Outdated CLI + compatible project: planner returns is_outdated=True.

    Uses FakeLatestVersionProvider("999.0.0") to force is_outdated=True.
    """
    _make_compatible_project(tmp_path, schema_version=3)

    fake_provider = FakeLatestVersionProvider("999.0.0")

    # Direct test: call planner with a fake provider to verify nag is triggered
    from specify_cli.compat.cache import NagCache
    from specify_cli.compat.planner import plan as compat_plan

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        inv = _Invocation(
            command_path=("upgrade",),
            raw_args=("--cli",),
            is_help=False,
            is_version=False,
            flag_no_nag=False,
            env_ci=False,
            stdout_is_tty=True,
        )
        result_plan = compat_plan(
            inv,
            latest_version_provider=fake_provider,
            nag_cache=NagCache(tmp_path / "upgrade-nag-test.json"),
        )
        assert result_plan.cli_status.is_outdated
        assert result_plan.fr023_case.value in ("cli_update_available", "install_method_unknown")
    finally:
        os.chdir(old_cwd)


def test_cli_update_available_json_contract(tmp_path: Path) -> None:
    """Outdated CLI: --cli --json emits valid compat-planner contract."""
    _make_compatible_project(tmp_path, schema_version=3)

    from kernel.clock import now_utc
    from specify_cli.compat.cache import NagCache, NagCacheRecord
    from specify_cli.compat.planner import _cache_version_key, _get_installed_version
    from specify_cli.core.channel import prerelease_enabled

    # CLI guidance is read-only: it consumes known version data from the cache.
    cache_path = tmp_path / "upgrade-nag-test.json"
    cache = NagCache(cache_path)
    cache.write(NagCacheRecord(
        cli_version_key=_cache_version_key(_get_installed_version(), prerelease=prerelease_enabled()),
        latest_version="999.0.0", latest_source="pypi",
        fetched_at=now_utc(), last_shown_at=None,
    ))
    before = cache_path.read_bytes()
    with patch("specify_cli.compat.cache.NagCache.default", return_value=cache):
        result = _invoke_upgrade(["--cli", "--json"], cwd=tmp_path)
    assert cache_path.read_bytes() == before

    assert result.exit_code == 0, f"Exit {result.exit_code}; output: {result.output}"
    payload = json.loads(result.output)
    _validate_json_contract(payload)
    assert payload["schema_version"] == 1
    assert payload["cli"]["is_outdated"] is True


# ---------------------------------------------------------------------------
# FR-023 case 2: project_migration_needed
# ---------------------------------------------------------------------------


def test_project_migration_needed_cli_mode_lists_hint(tmp_path: Path) -> None:
    """Stale project: --cli still succeeds (project-agnostic path)."""
    # Schema 1 is stale (MIN_SUPPORTED = 3)
    _make_compatible_project(tmp_path, schema_version=1)

    result = _invoke_upgrade(["--cli", "--dry-run"], cwd=tmp_path)
    assert result.exit_code == 0, f"Exit {result.exit_code}; output: {result.output}"


def test_project_migration_needed_planner_json(tmp_path: Path) -> None:
    """Stale project (schema 1): planner reports project_migration_needed or stale state."""
    _make_compatible_project(tmp_path, schema_version=1)

    from specify_cli.compat.planner import plan as compat_plan

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        inv = _Invocation(
            command_path=("upgrade",),
            raw_args=("--project",),
            is_help=False,
            is_version=False,
            flag_no_nag=False,
            env_ci=False,
            stdout_is_tty=True,
        )
        result_plan = compat_plan(inv)
        # Project with schema_version=1 < MIN_SUPPORTED=3 should be STALE
        assert result_plan.project_status.state == ProjectState.STALE
        payload = result_plan.rendered_json
        _validate_json_contract(payload)
        assert payload["project"]["state"] == "stale"
    finally:
        os.chdir(old_cwd)


def test_project_migration_needed_project_dry_run_json_contract(tmp_path: Path) -> None:
    """Stale project: upgrade --project --dry-run --json reports the blocking project plan."""
    from specify_cli.compat._detect.install_method import InstallMethod

    _make_compatible_project(tmp_path, schema_version=1)

    with patch(
        "specify_cli.compat._detect.install_method.detect_install_method",
        return_value=InstallMethod.PIPX,
    ):
        result = _invoke_upgrade(["--project", "--dry-run", "--json"], cwd=tmp_path)

    assert result.exit_code == 0, f"dry-run JSON should exit 0; output: {result.output}"
    payload = json.loads(result.output)
    _validate_json_contract(payload)
    assert payload["case"] == "project_migration_needed"
    assert payload["decision"] == "BLOCK_PROJECT_MIGRATION"
    assert payload["exit_code"] == 4
    assert payload["project"]["state"] == "stale"
    assert payload["safety"] == "unsafe"
    assert payload["pending_migrations"], "stale-project dry-run JSON must list pending migrations"


# ---------------------------------------------------------------------------
# FR-023 case 3: project_too_new_for_cli (CHK037 / A-006)
# ---------------------------------------------------------------------------


def _assert_too_new_project_human_output(output: str) -> None:
    plain = _strip_ansi(output)
    normalized = " ".join(plain.split())
    assert "This project uses Spec Kitty project schema 7" in normalized
    assert "supports up to schema" in normalized
    assert "Upgrade your CLI:" in plain
    assert "pip install --upgrade spec-kitty-cli" in plain


def test_project_too_new_for_cli_command_exit_5(tmp_path: Path) -> None:
    """Project schema 7 (too new): upgrade command exits 5 (CHK037)."""
    from specify_cli.compat._detect.install_method import InstallMethod

    _make_compatible_project(tmp_path, schema_version=7)
    with patch(
        "specify_cli.compat._detect.install_method.detect_install_method",
        return_value=InstallMethod.PIP_SYSTEM,
    ):
        result = _invoke_upgrade(["--project", "--dry-run"], cwd=tmp_path)
    assert result.exit_code == 5, f"Expected exit 5 for too-new project, got {result.exit_code}. Output: {result.output}"
    _assert_too_new_project_human_output(result.output)


def test_project_too_new_for_cli_default_mode_exit_5(tmp_path: Path) -> None:
    """Project schema 7 (too new): default upgrade mode also exits 5."""
    from specify_cli.compat._detect.install_method import InstallMethod

    _make_compatible_project(tmp_path, schema_version=7)
    with patch(
        "specify_cli.compat._detect.install_method.detect_install_method",
        return_value=InstallMethod.PIP_SYSTEM,
    ):
        result = _invoke_upgrade(["--dry-run"], cwd=tmp_path)
    assert result.exit_code == 5, f"Expected exit 5 for too-new project, got {result.exit_code}. Output: {result.output}"
    _assert_too_new_project_human_output(result.output)


def test_project_too_new_for_cli_yes_does_not_bypass(tmp_path: Path) -> None:
    """--yes does NOT bypass too-new schema block (A-006 / CHK037).

    ``--yes`` is a confirmation alias; it cannot bypass a schema-incompatibility
    that is unfixable from the project side.  Exit must remain 5.
    """
    _make_compatible_project(tmp_path, schema_version=7)
    result = _invoke_upgrade(["--yes"], cwd=tmp_path)
    # Still exit 5, NOT 0
    assert result.exit_code == 5, f"Expected exit 5 (BLOCK_CLI_UPGRADE) even with --yes, got {result.exit_code}"


def test_project_too_new_for_cli_force_does_not_bypass(tmp_path: Path) -> None:
    """--force does NOT bypass too-new schema block (A-006 / CHK037)."""
    _make_compatible_project(tmp_path, schema_version=7)
    result = _invoke_upgrade(["--force"], cwd=tmp_path)
    assert result.exit_code == 5, f"Expected exit 5 (BLOCK_CLI_UPGRADE) even with --force, got {result.exit_code}"


def test_project_too_new_for_cli_json_contract(tmp_path: Path) -> None:
    """project_too_new_for_cli: --json output is valid contract with exit_code=5."""
    _make_compatible_project(tmp_path, schema_version=7)

    result = _invoke_upgrade(["--project", "--dry-run", "--json"], cwd=tmp_path)
    assert result.exit_code == 5, f"Expected exit 5 for too-new project with --json, got {result.exit_code}. Output: {result.output}"
    try:
        payload = json.loads(result.output)
    except json.JSONDecodeError as e:
        pytest.fail(f"Output is not valid JSON: {e}\nOutput: {result.output!r}")
    _validate_json_contract(payload)
    assert payload["case"] == "project_too_new_for_cli"
    assert payload["decision"] == "BLOCK_CLI_UPGRADE"
    assert payload["exit_code"] == 5
    assert payload["project"]["state"] == "too_new"


def test_project_too_new_for_cli_project_state(tmp_path: Path) -> None:
    """Project schema 7: planner reports TOO_NEW state in rendered_json."""
    _make_compatible_project(tmp_path, schema_version=7)

    from specify_cli.compat.planner import plan as compat_plan

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        inv = _Invocation(
            command_path=("upgrade",),
            raw_args=("--project",),
            is_help=False,
            is_version=False,
            flag_no_nag=False,
            env_ci=False,
            stdout_is_tty=True,
        )
        result_plan = compat_plan(inv)
        assert result_plan.project_status.state == ProjectState.TOO_NEW
    finally:
        os.chdir(old_cwd)


# ---------------------------------------------------------------------------
# FR-023 case 4: project_not_initialized
# ---------------------------------------------------------------------------


def test_project_not_initialized_cli_flag_succeeds(tmp_path: Path) -> None:
    """No project + --cli → exit 0 (FR-014: --cli works outside any project)."""
    # tmp_path has no .kittify
    result = _invoke_upgrade(["--cli", "--dry-run"], cwd=tmp_path)
    assert result.exit_code == 0, f"Exit {result.exit_code}; output: {result.output}"


def test_project_not_initialized_project_flag_errors(tmp_path: Path) -> None:
    """No project + --project → errors with a clear 'no project' message."""
    result = _invoke_upgrade(["--project", "--dry-run"], cwd=tmp_path)
    # Should exit non-zero with an error message
    assert result.exit_code != 0, "Expected non-zero exit for --project outside a project"
    combined = (result.output or "") + (result.stderr or "")
    assert "not a spec kitty project" in combined.lower() or "no project" in combined.lower() or "init" in combined.lower()


def test_project_not_initialized_planner_state(tmp_path: Path) -> None:
    """No project: planner reports NO_PROJECT state.

    Patches ``locate_project_root`` to return ``None`` so the test is
    independent of the developer's ``~/.kittify`` directory (which would
    otherwise cause the resolver's upward walk to find an unrelated
    ``.kittify`` and return UNINITIALIZED instead of NO_PROJECT).
    """
    from specify_cli.compat.planner import plan as compat_plan

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        inv = _Invocation(
            command_path=("upgrade",),
            raw_args=("--cli",),
            is_help=False,
            is_version=False,
            flag_no_nag=False,
            env_ci=False,
            stdout_is_tty=True,
        )
        with patch(
            "specify_cli.core.project_resolver.locate_project_root",
            return_value=None,
        ):
            result_plan = compat_plan(inv)
        assert result_plan.project_status.state == ProjectState.NO_PROJECT
        # --cli is always exit 0 regardless of project state
        # (planner exit_code is 0 for ALLOW/ALLOW_WITH_NAG)
        payload = result_plan.rendered_json
        _validate_json_contract(payload)
    finally:
        os.chdir(old_cwd)


# ---------------------------------------------------------------------------
# FR-023 case 5: install_method_unknown (CHK031)
# ---------------------------------------------------------------------------


def test_install_method_unknown_cli_prints_note_not_command(tmp_path: Path) -> None:
    """UNKNOWN install method: upgrade_hint has note (not command) per CHK031."""
    from specify_cli.compat._detect.install_method import InstallMethod
    from specify_cli.compat.planner import plan as compat_plan

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        inv = _Invocation(
            command_path=("upgrade",),
            raw_args=("--cli",),
            is_help=False,
            is_version=False,
            flag_no_nag=False,
            env_ci=False,
            stdout_is_tty=True,
        )
        with (
            patch(
                "specify_cli.compat._detect.install_method.detect_install_method",
                return_value=InstallMethod.UNKNOWN,
            ),
        ):
            result_plan = compat_plan(inv)

        hint = result_plan.upgrade_hint
        # For UNKNOWN install method, command should be None, note should be set
        assert hint.command is None, f"UNKNOWN install method should have command=None, got {hint.command!r}"
        assert hint.note is not None, "UNKNOWN install method should have a note"

        # Validate JSON contract
        payload = result_plan.rendered_json
        _validate_json_contract(payload)
        hint_json = payload["upgrade_hint"]
        assert hint_json["command"] is None
        assert hint_json["note"] is not None
    finally:
        os.chdir(old_cwd)


def test_install_method_unknown_upgrade_hint_structure() -> None:
    """UNKNOWN install method: build_upgrade_hint returns note=non-null, command=null."""
    from specify_cli.compat._detect.install_method import InstallMethod
    from specify_cli.compat.upgrade_hint import build_upgrade_hint

    hint = build_upgrade_hint(InstallMethod.UNKNOWN)
    assert hint.command is None, f"UNKNOWN: command should be None, got {hint.command!r}"
    assert hint.note is not None, "UNKNOWN: note should be set"


def test_install_method_unknown_cli_flag_exit_0(tmp_path: Path) -> None:
    """UNKNOWN install method + --cli flag: exits 0 (not an error condition)."""
    from specify_cli.compat._detect.install_method import InstallMethod

    with patch(
        "specify_cli.compat._detect.install_method.detect_install_method",
        return_value=InstallMethod.UNKNOWN,
    ):
        result = _invoke_upgrade(["--cli"], cwd=tmp_path)

    assert result.exit_code == 0, f"Exit {result.exit_code}; output: {result.output}"


# ---------------------------------------------------------------------------
# T037 — --dry-run --json contract validation
# ---------------------------------------------------------------------------


def test_dry_run_json_compatible_project_exits_0(tmp_path: Path) -> None:
    """--cli --dry-run --json: compatible project, always exits 0 (R-08 / FR-012)."""
    _make_compatible_project(tmp_path, schema_version=3)
    result = _invoke_upgrade(["--cli", "--dry-run", "--json"], cwd=tmp_path)
    assert result.exit_code == 0, f"Exit {result.exit_code}; output: {result.output}"
    payload = json.loads(result.output)
    _validate_json_contract(payload)


def test_dry_run_json_no_project_exits_0(tmp_path: Path) -> None:
    """--cli --dry-run --json without a project: exits 0."""
    result = _invoke_upgrade(["--cli", "--dry-run", "--json"], cwd=tmp_path)
    assert result.exit_code == 0, f"Exit {result.exit_code}; output: {result.output}"
    payload = json.loads(result.output)
    _validate_json_contract(payload)


# ---------------------------------------------------------------------------
# FIX 5 — RISK-3: --cli mode respects real CI environment (no network call)
# ---------------------------------------------------------------------------


def test_explicit_upgrade_queries_fetch_in_ci_without_cache_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit text and JSON queries report the latest version when piped in CI."""
    from specify_cli.compat.cache import NagCache

    monkeypatch.setenv("CI", "1")
    cache_path = tmp_path / "nag.json"
    monkeypatch.setattr(NagCache, "default", lambda: NagCache(cache_path))
    provider_calls: list[bool] = []

    def provider(*, network_suppressed: bool, profile: object) -> FakeLatestVersionProvider:
        provider_calls.append(network_suppressed)
        return FakeLatestVersionProvider("999.0.0")

    monkeypatch.setattr("specify_cli.compat.planner._default_latest_provider", provider)
    text_result = _invoke_upgrade(["--cli"], cwd=tmp_path)
    assert text_result.exit_code == 0
    assert "999.0.0" in text_result.output

    json_result = _invoke_upgrade(["--cli", "--json"], cwd=tmp_path)
    assert json_result.exit_code == 0
    payload = json.loads(json_result.output)
    assert payload["cli"]["latest_version"] == "999.0.0"
    assert payload["cli"]["is_outdated"] is True

    _make_compatible_project(tmp_path)
    preview = _invoke_upgrade(["--dry-run", "--json"], cwd=tmp_path)
    assert preview.exit_code == 0
    preview_payload = json.loads(preview.output)
    assert preview_payload["cli"]["latest_version"] == "999.0.0"
    assert preview_payload["cli"]["is_outdated"] is True
    assert provider_calls == [False, False, False]
    assert not cache_path.exists()


def test_cli_mode_no_ci_env_does_not_suppress_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without CI, --cli mode builds an Invocation with env_ci=False (RISK-3 fix).

    We verify the env_ci field by inspecting is_ci_env() directly — not by making
    a real network call (which would be fragile in test environments).
    """
    from specify_cli.compat.planner import is_ci_env

    monkeypatch.delenv("CI", raising=False)
    assert is_ci_env() is False


# ---------------------------------------------------------------------------
# FIX 6 — RISK-6 / FR-014: bare upgrade outside project falls through to --cli
# ---------------------------------------------------------------------------


def test_bare_upgrade_outside_project_exits_0(tmp_path: Path) -> None:
    """Bare 'spec-kitty upgrade' outside a project exits 0 (FR-014 fall-through to --cli)."""
    # tmp_path has no .kittify
    result = _invoke_upgrade([], cwd=tmp_path)
    assert result.exit_code == 0, (
        f"Expected exit 0 for bare upgrade outside project (FR-014), got {result.exit_code}. "
        f"Output: {result.output}"
    )


def test_bare_upgrade_outside_project_no_error_message(tmp_path: Path) -> None:
    """Bare 'spec-kitty upgrade' outside a project must NOT print 'Not a Spec Kitty project'."""
    result = _invoke_upgrade([], cwd=tmp_path)
    assert "not a spec kitty project" not in result.output.lower(), (
        f"Bare upgrade should not show project-error message. Output: {result.output}"
    )


def test_project_flag_outside_project_still_errors(tmp_path: Path) -> None:
    """--project outside a project still errors (existing behavior must be preserved)."""
    result = _invoke_upgrade(["--project"], cwd=tmp_path)
    assert result.exit_code != 0, "Expected non-zero exit for --project outside a project"
    combined = (result.output or "") + (result.stderr or "")
    assert (
        "not a spec kitty project" in combined.lower()
        or "no project" in combined.lower()
        or "init" in combined.lower()
    )


def test_planner_json_too_new_project_has_exit_code_5_in_payload(tmp_path: Path) -> None:
    """Direct planner call: too-new project produces exit_code=5 in the JSON payload."""
    _make_compatible_project(tmp_path, schema_version=7)

    from specify_cli.compat.planner import plan as compat_plan

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Use an unsafe command path to trigger BLOCK_CLI_UPGRADE
        inv = _Invocation(
            command_path=("specify",),  # unsafe command, not in SAFETY_REGISTRY
            raw_args=(),
            is_help=False,
            is_version=False,
            flag_no_nag=False,
            env_ci=False,
            stdout_is_tty=True,
        )
        result_plan = compat_plan(inv)
        # The planner should return BLOCK_CLI_UPGRADE for an unsafe command + too_new project
        assert result_plan.project_status.state == ProjectState.TOO_NEW
        payload = result_plan.rendered_json
        _validate_json_contract(payload)
        assert payload["exit_code"] == 5
        assert payload["case"] == "project_too_new_for_cli"
    finally:
        os.chdir(old_cwd)


def test_cli_json_output_valid_contract(tmp_path: Path) -> None:
    """--cli --json emits JSON that passes contract validation."""
    _make_compatible_project(tmp_path, schema_version=3)

    result = _invoke_upgrade(["--cli", "--json"], cwd=tmp_path)
    assert result.exit_code == 0, f"Exit {result.exit_code}; output: {result.output}"

    try:
        payload = json.loads(result.output)
    except json.JSONDecodeError as e:
        pytest.fail(f"--cli --json output is not valid JSON: {e}\nOutput: {result.output!r}")

    _validate_json_contract(payload)


def test_cli_json_no_banner_in_stdout(tmp_path: Path) -> None:
    """--cli --json output is clean JSON only (no banner or nag prefix)."""
    _make_compatible_project(tmp_path, schema_version=3)

    result = _invoke_upgrade(["--cli", "--json"], cwd=tmp_path)
    # First non-whitespace char should be '{'
    stripped = result.output.lstrip()
    assert stripped.startswith("{"), f"JSON output should start with '{{'; got: {result.output[:100]!r}"


# ---------------------------------------------------------------------------
# T035 — --cli outside project (FR-014)
# ---------------------------------------------------------------------------


def test_cli_outside_project_no_error_message(tmp_path: Path) -> None:
    """--cli outside a project: no 'not a Spec Kitty project' error."""
    result = _invoke_upgrade(["--cli"], cwd=tmp_path)
    combined = (result.output or "") + (result.stderr or "")
    assert "not a spec kitty project" not in combined.lower()
    assert result.exit_code == 0


def test_cli_no_project_json_valid(tmp_path: Path) -> None:
    """--cli --json outside a project: valid JSON contract, exit 0.

    Patches ``locate_project_root`` to return ``None`` so the test is
    independent of the developer's ``~/.kittify`` directory (see
    ``test_project_not_initialized_planner_state`` for the same workaround).
    """
    with patch(
        "specify_cli.core.project_resolver.locate_project_root",
        return_value=None,
    ):
        result = _invoke_upgrade(["--cli", "--json"], cwd=tmp_path)
    assert result.exit_code == 0, f"Exit {result.exit_code}; output: {result.output}"
    payload = json.loads(result.output)
    _validate_json_contract(payload)
    assert payload["project"]["state"] == "no_project"


# ---------------------------------------------------------------------------
# T036 — --project suppresses CLI nag
# ---------------------------------------------------------------------------


def test_project_mode_no_cli_nag_in_output(tmp_path: Path) -> None:
    """--project with outdated CLI: no CLI nag in planner output path.

    The project-upgrade flow doesn't invoke the planner rendering at all;
    nag text appears only when --cli is used.
    """
    _make_compatible_project(tmp_path, schema_version=3)

    # Verify that the planner itself with --project flag doesn't produce
    # a CLI nag in rendered_human (it uses the upgrade hint, not the nag message)
    from specify_cli.compat.planner import plan as compat_plan

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        inv = _Invocation(
            command_path=("upgrade",),
            raw_args=("--project",),
            is_help=False,
            is_version=False,
            flag_no_nag=False,
            env_ci=False,
            stdout_is_tty=True,
        )
        result_plan = compat_plan(
            inv,
            latest_version_provider=FakeLatestVersionProvider("999.0.0"),
        )
        # With compatible project + outdated CLI → ALLOW_WITH_NAG
        # rendered_human has nag text; but in --project CLI mode, that is suppressed
        # (the project-upgrade flow doesn't call the planner at all unless --json)
        # Just validate the payload is contract-valid
        payload = result_plan.rendered_json
        _validate_json_contract(payload)
    finally:
        os.chdir(old_cwd)


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------


def test_no_nag_flag_accepted(tmp_path: Path) -> None:
    """--no-nag flag is accepted without error."""
    _make_compatible_project(tmp_path, schema_version=3)
    result = _invoke_upgrade(["--cli", "--no-nag"], cwd=tmp_path)
    assert result.exit_code == 0, f"Exit {result.exit_code}; output: {result.output}"


def test_cli_flag_with_dry_run(tmp_path: Path) -> None:
    """--cli --dry-run exits 0 (dry-run always 0)."""
    result = _invoke_upgrade(["--cli", "--dry-run"], cwd=tmp_path)
    assert result.exit_code == 0


def test_existing_dry_run_flag_preserved(tmp_path: Path) -> None:
    """Existing --dry-run flag is accepted (flag parse succeeds, no crash)."""
    _make_compatible_project(tmp_path, schema_version=3)
    # We only assert that the --dry-run flag doesn't cause a usage error (exit 2).
    # The actual exit code depends on the migration runner state.
    result = _invoke_upgrade(["--dry-run"], cwd=tmp_path)
    assert result.exit_code != 2, f"--dry-run caused a usage error: {result.output}"


def test_existing_dry_run_flag_cli_mode(tmp_path: Path) -> None:
    """--dry-run with --cli exits 0 (safe, project-agnostic path)."""
    result = _invoke_upgrade(["--dry-run", "--cli"], cwd=tmp_path)
    assert result.exit_code == 0, f"Exit {result.exit_code}; output: {result.output}"


def test_existing_verbose_flag_preserved(tmp_path: Path) -> None:
    """Existing --verbose flag is accepted (flag parse succeeds, no crash)."""
    _make_compatible_project(tmp_path, schema_version=3)
    result = _invoke_upgrade(["--dry-run", "--verbose"], cwd=tmp_path)
    assert result.exit_code != 2, f"--verbose caused a usage error: {result.output}"


def test_existing_verbose_flag_cli_mode(tmp_path: Path) -> None:
    """--verbose with --cli is accepted."""
    result = _invoke_upgrade(["--cli", "--verbose"], cwd=tmp_path)
    assert result.exit_code == 0, f"Exit {result.exit_code}; output: {result.output}"


def test_existing_force_flag_preserved(tmp_path: Path) -> None:
    """Existing --force flag is accepted (flag parse succeeds, no crash)."""
    _make_compatible_project(tmp_path, schema_version=3)
    result = _invoke_upgrade(["--dry-run", "--force"], cwd=tmp_path)
    assert result.exit_code != 2, f"--force caused a usage error: {result.output}"


def test_existing_no_worktrees_flag_preserved(tmp_path: Path) -> None:
    """Existing --no-worktrees flag is accepted (flag parse succeeds, no crash)."""
    _make_compatible_project(tmp_path, schema_version=3)
    result = _invoke_upgrade(["--dry-run", "--no-worktrees"], cwd=tmp_path)
    assert result.exit_code != 2, f"--no-worktrees caused a usage error: {result.output}"


# ---------------------------------------------------------------------------
# WP02 / FR-013 (#1784 P3 crumb) — honest --dry-run outcome line
# ---------------------------------------------------------------------------


def _make_upgrade_result(*, dry_run: bool, success: bool = True) -> Any:
    from specify_cli.upgrade.runner import UpgradeResult

    return UpgradeResult(
        success=success,
        from_version="3.1.0",
        to_version="3.2.0",
        dry_run=dry_run,
    )


def _render_upgrade_outcome(result: Any) -> str:
    from specify_cli.cli.commands.upgrade import _display_upgrade_results
    from specify_cli.cli.helpers import console

    with console.capture() as capture:
        # WP04/T022: _display_upgrade_results is pure rendering — it no
        # longer raises typer.Exit itself; the exit code is derived exactly
        # once, at the command boundary, from UpgradeOutcome.exit_code (D-5).
        # These fixtures have no finalizer-level signal beyond `result.success`
        # itself, so `effective_success`/`errors` mirror it directly here.
        _display_upgrade_results(
            result,
            manual_review_paths=[],
            auto_committed=False,
            auto_commit_paths=[],
            effective_success=result.success,
            errors=result.errors,
        )
    return capture.get()


def test_dry_run_success_does_not_print_upgrade_complete() -> None:
    """A --dry-run never prints a line implying changes were applied (FR-013)."""
    output = _render_upgrade_outcome(_make_upgrade_result(dry_run=True))
    assert "Upgrade complete!" not in output, (
        f"--dry-run printed a success line implying changes were applied:\n{output}"
    )
    assert "Dry run complete" in output
    assert "no changes applied" in output


def test_real_run_success_line_unchanged() -> None:
    """A real (non-dry-run) successful upgrade keeps the success line."""
    output = _strip_ansi(_render_upgrade_outcome(_make_upgrade_result(dry_run=False)))
    assert "Upgrade complete!" in output
    assert "3.1.0 -> 3.2.0" in output
    assert "Dry run complete" not in output


def test_failed_run_prints_failure_without_raising() -> None:
    """WP04/T022: a failed render never raises — it is pure rendering.

    The exit code is derived exactly once, at the command boundary, from
    ``UpgradeOutcome.exit_code`` (D-5); see ``tests/upgrade/test_finalizer.py``
    and ``tests/upgrade/test_upgrade_integration.py`` for that boundary proof.
    """
    for dry_run in (False, True):
        output = _render_upgrade_outcome(_make_upgrade_result(dry_run=dry_run, success=False))
        assert "Upgrade failed." in output
        assert "Upgrade complete!" not in output
        assert "Dry run complete" not in output


# ---------------------------------------------------------------------------
# WP01 (#2419) — revived contract-check must be non-vacuous and fail-hard
# ---------------------------------------------------------------------------


def _minimal_valid_payload() -> dict[str, Any]:
    """A minimal payload that satisfies compat-planner.json on its own."""
    return {
        "schema_version": 1,
        "case": "none",
        "decision": "ALLOW",
        "exit_code": 0,
        "cli": {
            "installed_version": "2.0.14",
            "latest_version": None,
            "latest_source": "none",
            "is_outdated": False,
            "fetched_at": None,
        },
        "project": {
            "state": "compatible",
            "project_root": None,
            "schema_version": 3,
            "min_supported": 3,
            "max_supported": 3,
            "metadata_error": None,
        },
        "safety": "unsafe",
        "install_method": "pipx",
        "upgrade_hint": {
            "install_method": "pipx",
            "command": "pipx upgrade spec-kitty-cli",
            "note": None,
        },
        "pending_migrations": [],
        "rendered_human": "",
    }


def test_validate_json_contract_rejects_overlong_migration_description() -> None:
    """T005 Check A: a schema-violating payload must raise through the helper.

    ``pending_migrations[].description`` is capped at 256 chars by the
    contract. A payload that violates this must raise
    ``jsonschema.ValidationError`` *through* ``_validate_json_contract`` —
    proof the helper is genuinely live, not vacuously green. This test goes
    RED if the ``jsonschema.validate(...)`` call inside the helper is deleted
    or re-guarded behind a ``_CONTRACT is not None`` check.
    """
    import jsonschema

    payload = _minimal_valid_payload()
    payload["case"] = "project_migration_needed"
    payload["decision"] = "BLOCK_PROJECT_MIGRATION"
    payload["exit_code"] = 4
    payload["project"]["state"] = "stale"
    payload["pending_migrations"] = [
        {
            "migration_id": "m_bad",
            "target_schema_version": 3,
            "description": "x" * 300,
        }
    ]

    with pytest.raises(jsonschema.ValidationError, match="too long|maxLength"):
        _validate_json_contract(payload)


def test_validate_json_contract_rejects_wrong_typed_field() -> None:
    """T005 Check A (second mutation angle): wrong-typed field is rejected.

    A second, independent violation shape (wrong type rather than length) so
    the witness isn't over-fit to a single ``maxLength`` branch of the
    schema.
    """
    import jsonschema

    payload = _minimal_valid_payload()
    payload["exit_code"] = "not-an-int"

    with pytest.raises(jsonschema.ValidationError):
        _validate_json_contract(payload)


def test_contract_loads_from_a_simulated_non_worktrees_layout(tmp_path: Path) -> None:
    """T005: the contract path is ``__file__``-anchored, not worktree-shaped.

    Build a fake checkout that mirrors this file's on-disk depth
    (``tests/specify_cli/cli/commands/<file>.py``, repo root at
    ``parents[4]``) but lives under a plain directory name with no
    ``.worktrees`` segment anywhere in the path, and confirm the same
    parent-hop formula still resolves to a loadable contract.
    """
    fake_repo_root = tmp_path / "plain-checkout"
    fake_test_file = fake_repo_root / "tests" / "specify_cli" / "cli" / "commands" / "test_stub.py"
    fake_test_file.parent.mkdir(parents=True, exist_ok=True)
    fake_test_file.write_text("# stub\n", encoding="utf-8")

    fake_contract_dir = (
        fake_repo_root
        / "kitty-specs"
        / "cli-upgrade-nag-lazy-project-migrations-01KQ6YDN"
        / "contracts"
    )
    fake_contract_dir.mkdir(parents=True, exist_ok=True)
    fake_contract_path = fake_contract_dir / "compat-planner.json"
    fake_contract_path.write_text(_CONTRACT_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    assert ".worktrees" not in str(fake_repo_root)

    resolved_root = fake_test_file.parent.parent.parent.parent.parent
    resolved_contract_path = (
        resolved_root
        / "kitty-specs"
        / "cli-upgrade-nag-lazy-project-migrations-01KQ6YDN"
        / "contracts"
        / "compat-planner.json"
    )
    assert resolved_root == fake_repo_root
    assert resolved_contract_path == fake_contract_path

    loaded = _load_contract(resolved_contract_path)
    assert loaded["title"] == "spec-kitty upgrade --json output"


def test_contract_path_missing_fails_hard(tmp_path: Path) -> None:
    """T006: a nonexistent contract file must raise, never resolve to None.

    Calls ``_load_contract`` — the same function that builds module-level
    ``_CONTRACT`` — against a nonexistent path and asserts it raises
    ``FileNotFoundError`` rather than being swallowed into a silent ``None``
    fallback. Goes RED if a ``.exists()`` guard + ``suppress`` fallback is
    reintroduced inside ``_load_contract``.
    """
    missing_path = tmp_path / "does" / "not" / "exist" / "compat-planner.json"

    with pytest.raises(FileNotFoundError):
        _load_contract(missing_path)


def test_contract_path_malformed_fails_hard(tmp_path: Path) -> None:
    """T006: a malformed/non-JSON contract file must raise, never return None.

    Calls ``_load_contract`` directly. Goes RED if a silent
    ``except Exception: return None``-shaped fallback is reintroduced inside
    ``_load_contract``.
    """
    malformed_path = tmp_path / "compat-planner.json"
    malformed_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        _load_contract(malformed_path)


# ---------------------------------------------------------------------------
# kernel-clock-single-door FR-011: last_upgraded_at is aware-UTC, not naive
# ---------------------------------------------------------------------------


def test_no_op_upgrade_stamps_last_upgraded_at_as_aware_utc(tmp_path: Path) -> None:
    """The version-stamp-only path (no migrations needed) writes an
    aware-UTC ``last_upgraded_at``, not naive local time.

    Regression guard for the naive ``datetime.now()`` site formerly in
    ``cli.commands.upgrade`` (research/migration-notes.md): a naive value
    persists to ``metadata.yaml`` WITHOUT a UTC offset suffix; the door's
    ``now_utc()`` always carries ``+00:00``. Non-vacuity: reverting the
    door call back to a bare ``datetime.now()`` drops the offset and this
    assertion fails.

    ``MigrationRegistry.get_applicable`` is patched to ``[]`` so the test
    exercises exactly the "no migrations needed, still stamp the version"
    branch, independent of the real migration set's version windows.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "metadata.yaml").write_text(
        "spec_kitty:\n"
        "  schema_version: 3\n"
        "  version: 0.1.0\n"
        "  initialized_at: '2020-01-01T00:00:00+00:00'\n",
        encoding="utf-8",
    )

    with patch("specify_cli.upgrade.registry.MigrationRegistry.get_applicable", return_value=[]):
        result = _invoke_upgrade([], cwd=tmp_path)

    assert result.exit_code == 0, result.output
    data = yaml.safe_load((kittify / "metadata.yaml").read_text(encoding="utf-8"))
    last_upgraded_at = data["spec_kitty"]["last_upgraded_at"]
    assert isinstance(last_upgraded_at, str), "expected an unquoted ISO string in the raw YAML"
    assert last_upgraded_at.endswith("+00:00"), (
        f"last_upgraded_at={last_upgraded_at!r} is missing the aware-UTC offset suffix "
        "-- the naive datetime.now() regression has returned"
    )


# ---------------------------------------------------------------------------
# #4124 — stale-bytecode self-heal on the upgrade-system import seam
# ---------------------------------------------------------------------------


def test_load_upgrade_system_with_heal_retries_after_pycache_heal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale-``.pyc`` discovery failure is healed once, then retried (#4124).

    The stand-in raises the *real laundered* shape: a fresh
    ``MigrationDiscoveryError`` chained to the original corrupt-``.pyc``
    import failure, exactly what ``auto_discover_migrations`` produces — the
    corrupt-cache signature rides the ``__cause__`` chain. Non-vacuity: with
    the cause-chain walk removed from ``failure_during_package_import``, the
    wrapper matches no direct shape and this test errors instead of returning
    the four upgrade-system callables.
    """
    import specify_cli.bytecode_heal as bytecode_heal
    import specify_cli.cli.commands.upgrade as upgrade_mod
    import specify_cli.upgrade.migrations as migrations

    calls: list[int] = []

    def flaky() -> None:
        calls.append(1)
        if len(calls) == 1:
            root = bytecode_heal.package_root()
            assert root is not None
            fake_pyc = root / "upgrade" / "migrations" / "__pycache__" / "base.cpython-311.pyc"
            cause = ImportError(f"Non-code object in '{fake_pyc}'")
            raise migrations.MigrationDiscoveryError(
                f"Failed to import migration module(s): base: {cause}"
            ) from cause

    printed: list[str] = []
    monkeypatch.setattr(migrations, "auto_discover_migrations", flaky)
    monkeypatch.setattr(bytecode_heal, "purge_package_bytecode", lambda: 7)
    monkeypatch.setattr(
        upgrade_mod.console, "print", lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args))
    )

    detector, registry, runner, validate = upgrade_mod._load_upgrade_system_with_heal()

    assert len(calls) == 2  # healed, then retried exactly once
    assert detector.__name__ == "VersionDetector"
    assert registry.__name__ == "MigrationRegistry"
    assert runner.__name__ == "MigrationRunner"
    assert callable(validate)
    assert any("Repaired 7 stale bytecode cache file" in line for line in printed)


def test_load_upgrade_system_with_heal_propagates_genuine_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-cache discovery failure still surfaces — the heal is not a swallow."""
    import specify_cli.cli.commands.upgrade as upgrade_mod
    import specify_cli.upgrade.migrations as migrations

    def boom() -> None:
        raise RuntimeError("discovery exploded")

    monkeypatch.setattr(migrations, "auto_discover_migrations", boom)

    with pytest.raises(RuntimeError, match="discovery exploded"):
        upgrade_mod._load_upgrade_system_with_heal()


def test_load_upgrade_system_with_heal_propagates_laundered_genuine_import_bug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A genuinely broken migration module (``SyntaxError``) stays unhealed (#4124).

    Through the identical launder wrapper, the discriminator must not purge
    and retry: the failure is a broken module, not a stale ``.pyc`` cache.
    """
    import specify_cli.bytecode_heal as bytecode_heal
    import specify_cli.cli.commands.upgrade as upgrade_mod
    import specify_cli.upgrade.migrations as migrations

    def broken_module() -> None:
        cause = SyntaxError("invalid syntax (m_0_10_12_charter_cleanup.py, line 1)")
        raise migrations.MigrationDiscoveryError(
            f"Failed to import migration module(s): m_0_10_12_charter_cleanup: {cause}"
        ) from cause

    purged: list[int] = []
    monkeypatch.setattr(migrations, "auto_discover_migrations", broken_module)
    monkeypatch.setattr(bytecode_heal, "purge_package_bytecode", lambda: purged.append(1) or 0)

    with pytest.raises(migrations.MigrationDiscoveryError, match="invalid syntax"):
        upgrade_mod._load_upgrade_system_with_heal()
    assert purged == []
