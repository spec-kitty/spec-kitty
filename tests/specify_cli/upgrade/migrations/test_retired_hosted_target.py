"""Tests for ``m_4_0_0_retired_hosted_target`` (#4259).

Mirrors the established migration-test pattern (see
``tests/specify_cli/upgrade/migrations/test_provision_kitty_env.py``): unit
tests call ``detect()``/``can_apply()``/``apply()`` directly on a migration
instance against a synthetic ``SPEC_KITTY_HOME``, never through the upgrade
pipeline. The #4259 acceptance additionally requires exercising the actual
upgrade entry point, so the CLI-driven tests at the bottom invoke the real
``spec-kitty upgrade`` Typer command (the ``test_upgrade_idempotency.py``
harness) against a synthetic project on a machine whose saved target is
stale — once with no env override, once with an explicit canonical
``SPEC_KITTY_SAAS_URL``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import toml
import typer
from typer.testing import CliRunner

from specify_cli.auth.config import DEFAULT_HOSTED_SAAS_URL, RETIRED_HOSTED_SAAS_URL
from specify_cli.auth.server_target import resolve_server_target
from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.upgrade.migrations.m_4_0_0_retired_hosted_target import (
    MIGRATION_ID,
    TARGET_VERSION,
    RetiredHostedTargetMigration,
    home_config_path,
    retired_server_url_value,
)
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.unit]

RETIRED_URL = RETIRED_HOSTED_SAAS_URL
CANONICAL_URL = DEFAULT_HOSTED_SAAS_URL
CUSTOM_URL = "https://saas.internal.example.com:8443/prefix"

# Unrelated configuration the rewrite must carry through untouched.
_UNRELATED_CONFIG = f'[sync]\nserver_url = "{RETIRED_URL}"\npoll_interval = 30\n\n[telemetry]\nenabled = false\n\n[ui]\ntheme = "dark"\n'


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated ``SPEC_KITTY_HOME`` with no env target leakage."""
    root = tmp_path / "spec-kitty-home"
    root.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(root))
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    return root


def _write_home_config(root: Path, text: str) -> Path:
    path = root / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Registration + version pin
# ---------------------------------------------------------------------------


def test_migration_is_registered() -> None:
    found = MigrationRegistry.get_by_id(MIGRATION_ID)
    assert found is not None
    assert found.migration_id == MIGRATION_ID
    assert found.runs_on_worktrees is False


def test_target_version_does_not_exceed_package_version() -> None:
    """Guards the module docstring's own stated invariant directly (the
    ``m_3_2_8`` pin precedent; belt-and-suspenders alongside the repo-wide
    ``test_discovered_migration_targets_do_not_exceed_package_version`` gate)."""
    from packaging.version import Version

    migration = RetiredHostedTargetMigration()
    assert Version(migration.target_version) == Version(TARGET_VERSION)
    assert Version(TARGET_VERSION) <= Version("4.0.0rc1")


def test_chain_selects_migration_from_pre_4_upgrade() -> None:
    """A 3.2.6 → 4.0.0rc1 upgrade selects exactly this migration (the only
    registered target version above 3.2.6)."""
    applicable = MigrationRegistry.get_applicable("3.2.6", "4.0.0rc1", project_path=Path("/nonexistent"))
    assert MIGRATION_ID in [m.migration_id for m in applicable]


# ---------------------------------------------------------------------------
# detect() / can_apply()
# ---------------------------------------------------------------------------


class TestDetect:
    def test_detect_true_when_saved_target_is_retired(self, home: Path) -> None:
        _write_home_config(home, _UNRELATED_CONFIG)
        assert RetiredHostedTargetMigration().detect(Path("/any/project")) is True

    def test_detect_false_when_target_already_canonical(self, home: Path) -> None:
        _write_home_config(home, f'[sync]\nserver_url = "{CANONICAL_URL}"\n')
        assert RetiredHostedTargetMigration().detect(Path("/any/project")) is False

    def test_detect_false_when_target_is_custom_self_hosted(self, home: Path) -> None:
        _write_home_config(home, f'[sync]\nserver_url = "{CUSTOM_URL}"\n')
        assert RetiredHostedTargetMigration().detect(Path("/any/project")) is False

    def test_detect_false_when_no_home_config(self, home: Path) -> None:
        assert RetiredHostedTargetMigration().detect(Path("/any/project")) is False

    def test_detect_false_on_unparseable_config(self, home: Path) -> None:
        _write_home_config(home, "this is = = not valid toml")
        assert RetiredHostedTargetMigration().detect(Path("/any/project")) is False

    def test_detect_false_when_sync_is_not_a_table(self, home: Path) -> None:
        _write_home_config(home, 'sync = "oops"\n')
        assert RetiredHostedTargetMigration().detect(Path("/any/project")) is False

    def test_detect_matches_retired_host_regardless_of_case_slash_and_port(self, home: Path) -> None:
        """The retired *address* is the host: scheme/case/port/path variants
        of it are the same dead endpoint, so all of them detect."""
        for value in (
            f"{RETIRED_URL}/",
            "HTTPS://APP.SPEC-KITTY.AI",
            f"{RETIRED_URL}:8443/dead/path",
            f"  {RETIRED_URL}  ",
        ):
            _write_home_config(home, f'[sync]\nserver_url = "{value}"\n')
            assert retired_server_url_value(home_config_path()) is not None, value

    def test_detect_ignores_look_alike_domains(self, home: Path) -> None:
        """Hostname-exact, never substring: a domain that merely contains the
        literal is somebody else's endpoint and is never migrated."""
        for value in (
            "https://app.spec-kitty.ai.evil.example.com",
            "https://myapp.spec-kitty.ai",
            "https://app.spec-kitty-ai.example.com",
            "https://notapp.spec-kitty.ai",
        ):
            _write_home_config(home, f'[sync]\nserver_url = "{value}"\n')
            assert retired_server_url_value(home_config_path()) is None, value

    def test_can_apply(self, home: Path) -> None:
        _write_home_config(home, _UNRELATED_CONFIG)
        migration = RetiredHostedTargetMigration()
        assert migration.can_apply(Path("/any/project")) == (True, "")
        assert migration.can_apply(Path("/any/project"))[0] is True

    def test_can_apply_false_when_nothing_to_migrate(self, home: Path) -> None:
        can_apply, reason = RetiredHostedTargetMigration().can_apply(Path("/any/project"))
        assert can_apply is False
        assert "no retired first-party server_url" in reason


# ---------------------------------------------------------------------------
# apply()
# ---------------------------------------------------------------------------


class TestApply:
    def test_apply_rewrites_retired_target_to_canonical(self, home: Path) -> None:
        path = _write_home_config(home, _UNRELATED_CONFIG)

        result = RetiredHostedTargetMigration().apply(Path("/any/project"))

        assert result.success is True
        assert result.errors == []
        data = toml.load(path)
        assert data["sync"]["server_url"] == CANONICAL_URL

    def test_apply_preserves_unrelated_configuration(self, home: Path) -> None:
        """#4259 agreed scope: unrelated settings, custom endpoints, ports and
        paths survive the rewrite semantically untouched."""
        path = _write_home_config(home, _UNRELATED_CONFIG)

        RetiredHostedTargetMigration().apply(Path("/any/project"))

        data = toml.load(path)
        assert data["sync"]["poll_interval"] == 30
        assert data["telemetry"] == {"enabled": False}
        assert data["ui"] == {"theme": "dark"}

    def test_apply_is_idempotent(self, home: Path) -> None:
        _write_home_config(home, _UNRELATED_CONFIG)
        migration = RetiredHostedTargetMigration()

        first = migration.apply(Path("/any/project"))
        second = migration.apply(Path("/any/project"))

        assert first.success is True
        assert second.success is True
        data = toml.load(home / "config.toml")
        assert data["sync"]["server_url"] == CANONICAL_URL
        # The second run records a no-op, not a second rewrite.
        assert "no retired first-party server_url" in " ".join(second.changes_made)

    def test_apply_dry_run_leaves_file_untouched(self, home: Path) -> None:
        path = _write_home_config(home, _UNRELATED_CONFIG)
        before = path.read_text(encoding="utf-8")

        result = RetiredHostedTargetMigration().apply(Path("/any/project"), dry_run=True)

        assert result.success is True
        assert path.read_text(encoding="utf-8") == before
        assert any("would rewrite" in change for change in result.changes_made)

    def test_apply_never_touches_custom_self_hosted_target(self, home: Path) -> None:
        """#4259 agreed scope: only the retired first-party address is
        replaced — never every noncanonical URL."""
        path = _write_home_config(home, f'[sync]\nserver_url = "{CUSTOM_URL}"\n')
        before = path.read_text(encoding="utf-8")

        result = RetiredHostedTargetMigration().apply(Path("/any/project"))

        assert result.success is True
        assert path.read_text(encoding="utf-8") == before

    def test_apply_no_op_on_missing_and_broken_config(self, home: Path) -> None:
        """A broken or absent config.toml is never made more broken."""
        migration = RetiredHostedTargetMigration()

        missing = migration.apply(Path("/any/project"))
        assert missing.success is True
        assert not (home / "config.toml").exists()

        _write_home_config(home, "this is = = not valid toml")
        broken = migration.apply(Path("/any/project"))
        assert broken.success is True
        assert (home / "config.toml").read_text(encoding="utf-8") == "this is = = not valid toml"

    def test_apply_does_not_read_env_override(self, home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The saved address is dead first-party infrastructure regardless of
        any live env opinion — an explicit canonical override is no reason to
        keep it, and a custom override is no reason to touch anything else."""
        path = _write_home_config(home, _UNRELATED_CONFIG)

        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", CANONICAL_URL)
        result = RetiredHostedTargetMigration().apply(Path("/any/project"))

        assert result.success is True
        assert toml.load(path)["sync"]["server_url"] == CANONICAL_URL


# ---------------------------------------------------------------------------
# The actual upgrade entry point (#4259 acceptance)
# ---------------------------------------------------------------------------

_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade)
_cli_runner = CliRunner()

_METADATA_YAML = (
    "spec_kitty:\n"
    "  version: '{version}'\n"
    "  initialized_at: '2026-01-01T00:00:00'\n"
    "environment:\n"
    "  python_version: '3.12'\n"
    "  platform: linux\n"
    "  platform_version: ''\n"
    "migrations:\n"
    "  applied: []\n"
)


def _init_project(root: Path, *, version: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    kittify = root / ".kittify"
    kittify.mkdir()
    (kittify / "metadata.yaml").write_text(_METADATA_YAML.format(version=version), encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)


def _run_upgrade(args: list[str], cwd: Path):
    old_cwd = os.getcwd()
    try:
        os.chdir(cwd)
        return _cli_runner.invoke(_test_app, args, catch_exceptions=False)
    finally:
        os.chdir(old_cwd)


def _last_json_line(output: str) -> dict[str, object]:
    lines = [line for line in output.strip().splitlines() if line.strip()]
    return json.loads(lines[-1])


class TestUpgradeEntryPoint:
    """#4259 acceptance: the real ``spec-kitty upgrade`` command migrates a
    stale saved target on a machine whose resolver would otherwise keep
    resolving the retired first-party endpoint."""

    @pytest.mark.integration
    @pytest.mark.git_repo
    @pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the canonical owner pins SPEC_KITTY_HOME=tmp_path/home
    def test_upgrade_rewrites_stale_saved_target_without_env_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "home"
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        _write_home_config(home, _UNRELATED_CONFIG)

        # Pre-migration: with no env opinion, the stale saved target wins.
        assert resolve_server_target().resolved_server_url == RETIRED_URL

        project = tmp_path / "proj"
        _init_project(project, version="3.2.6")
        result = _run_upgrade(
            ["--target", "4.0.0rc1", "--yes", "--no-worktrees", "--json"],
            cwd=project,
        )
        assert result.exit_code == 0, result.output
        payload = _last_json_line(result.output)
        assert payload["success"] is True, payload

        data = toml.load(home / "config.toml")
        assert data["sync"]["server_url"] == CANONICAL_URL
        assert data["sync"]["poll_interval"] == 30
        assert data["telemetry"] == {"enabled": False}
        assert data["ui"] == {"theme": "dark"}
        # Post-migration: the resolver now answers the canonical target.
        assert resolve_server_target().resolved_server_url == CANONICAL_URL

    @pytest.mark.integration
    @pytest.mark.git_repo
    @pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the canonical owner pins SPEC_KITTY_HOME=tmp_path/home
    def test_upgrade_is_idempotent_through_the_entry_point(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "home"
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        _write_home_config(home, _UNRELATED_CONFIG)

        project = tmp_path / "proj"
        _init_project(project, version="3.2.6")
        args = ["--target", "4.0.0rc1", "--yes", "--no-worktrees", "--json"]

        first = _run_upgrade(args, cwd=project)
        assert first.exit_code == 0, first.output
        second = _run_upgrade(args, cwd=project)
        assert second.exit_code == 0, second.output

        data = toml.load(home / "config.toml")
        assert data["sync"]["server_url"] == CANONICAL_URL
        assert data["sync"]["poll_interval"] == 30

    @pytest.mark.integration
    @pytest.mark.git_repo
    @pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the canonical owner pins SPEC_KITTY_HOME=tmp_path/home
    def test_upgrade_with_explicit_canonical_env_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """With ``SPEC_KITTY_SAAS_URL`` explicitly equal to the canonical
        target, the resolver already answers canonical (#4259 precedence
        fix) — and the upgrade still removes the stale saved address, so the
        machine no longer depends on the override to reach the right host."""
        home = tmp_path / "home"
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", CANONICAL_URL)
        _write_home_config(home, _UNRELATED_CONFIG)

        # Pre-migration, with the #4259 precedence fix: the explicit env
        # value wins even though it equals the packaged default.
        assert resolve_server_target().resolved_server_url == CANONICAL_URL

        project = tmp_path / "proj"
        _init_project(project, version="3.2.6")
        result = _run_upgrade(
            ["--target", "4.0.0rc1", "--yes", "--no-worktrees", "--json"],
            cwd=project,
        )
        assert result.exit_code == 0, result.output

        data = toml.load(home / "config.toml")
        assert data["sync"]["server_url"] == CANONICAL_URL
        # The override is no longer load-bearing: with it removed, the
        # machine still resolves the canonical target.
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL")
        assert resolve_server_target().resolved_server_url == CANONICAL_URL
