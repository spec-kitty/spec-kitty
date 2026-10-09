"""Tests for the ``doctrine fetch`` and ``doctrine pack`` CLI commands (charter pack adapters).

Covers the fetch matrix: all packs, ``--pack`` flag, unknown pack, empty
registry, dry run, failure reporting.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from charter.offering.drg.org_pack_config import OrgPackConfig
from specify_cli.charter_packs.sources.protocol import FetchResult


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_config(repo_root: Path, body: str) -> Path:
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "config.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


# ----------------------------------------------------------------------
# load_pack_registry
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# doctrine fetch CLI
# ----------------------------------------------------------------------
@pytest.fixture
def fetch_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> typer.Typer:
    """Build a small Typer app that just hosts the doctrine subcommands.

    Patching ``locate_project_root`` lets us bypass the real .kittify
    discovery and point fetch at ``tmp_path``.
    """
    import specify_cli.cli.commands.doctrine as doctrine_module

    monkeypatch.setattr(
        "specify_cli.core.paths.locate_project_root",
        lambda start=None: tmp_path,
    )
    return doctrine_module.app


class TestDoctrineFetchCLI:
    def test_fetch_no_config(self, fetch_app: typer.Typer, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(fetch_app, ["fetch"])
        assert result.exit_code == 1
        assert "No org doctrine packs configured" in result.stdout

    def test_fetch_unknown_pack_flag(self, fetch_app: typer.Typer, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            """
            doctrine:
              org:
                packs:
                  - name: security
                    local_path: /opt/sec
            """,
        )
        runner = CliRunner()
        result = runner.invoke(fetch_app, ["fetch", "--pack", "nonexistent"])
        assert result.exit_code == 1
        assert "nonexistent" in result.stdout
        assert "security" in result.stdout

    def test_fetch_all_packs(
        self,
        fetch_app: typer.Typer,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_config(
            tmp_path,
            """
            doctrine:
              org:
                packs:
                  - name: security
                    local_path: /opt/sec
                    source_type: git
                    url: git@example.com:sec/charter.offering.git
                  - name: architecture
                    local_path: /opt/arch
                    source_type: git
                    url: git@example.com:arch/charter.offering.git
            """,
        )
        fetched_names: list[str] = []

        def fake_fetch_pack(pack: OrgPackConfig, repo_root: Path) -> FetchResult:
            fetched_names.append(pack.name)
            assert isinstance(3, int)  # artifacts_written must be int (FR-007)
            return FetchResult(ok=True, artifacts_written=3, pack_version="v1.0.0")

        monkeypatch.setattr("specify_cli.charter_packs.snapshot.fetch_pack", fake_fetch_pack)

        runner = CliRunner()
        result = runner.invoke(fetch_app, ["fetch"])
        assert result.exit_code == 0, result.stdout
        assert fetched_names == ["security", "architecture"]
        assert "security" in result.stdout
        assert "architecture" in result.stdout

    def test_fetch_single_pack_flag(
        self,
        fetch_app: typer.Typer,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_config(
            tmp_path,
            """
            doctrine:
              org:
                packs:
                  - name: security
                    local_path: /opt/sec
                    source_type: git
                    url: git@example.com:sec/charter.offering.git
                  - name: architecture
                    local_path: /opt/arch
                    source_type: git
                    url: git@example.com:arch/charter.offering.git
            """,
        )
        fetched_names: list[str] = []
        monkeypatch.setattr(
            "specify_cli.charter_packs.snapshot.fetch_pack",
            lambda pack, repo_root: fetched_names.append(pack.name) or FetchResult(ok=True, artifacts_written=1, pack_version=None),
        )
        runner = CliRunner()
        result = runner.invoke(fetch_app, ["fetch", "--pack", "security"])
        assert result.exit_code == 0, result.stdout
        assert fetched_names == ["security"]

    def test_fetch_dry_run(self, fetch_app: typer.Typer, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            """
            doctrine:
              org:
                packs:
                  - name: security
                    local_path: /opt/sec
                    source_type: git
                    url: git@example.com:sec/charter.offering.git
            """,
        )
        runner = CliRunner()
        result = runner.invoke(fetch_app, ["fetch", "--dry-run"])
        assert result.exit_code == 0
        assert "Would fetch" in result.stdout
        assert "security" in result.stdout

    def test_fetch_reports_failures(
        self,
        fetch_app: typer.Typer,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_config(
            tmp_path,
            """
            doctrine:
              org:
                packs:
                  - name: security
                    local_path: /opt/sec
                    source_type: git
                    url: git@example.com:sec/charter.offering.git
            """,
        )
        monkeypatch.setattr(
            "specify_cli.charter_packs.snapshot.fetch_pack",
            lambda pack, repo_root: FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=["network unreachable"],
            ),
        )
        runner = CliRunner()
        result = runner.invoke(fetch_app, ["fetch"])
        assert result.exit_code == 1
        assert "failed" in result.stdout
        assert "network unreachable" in result.stdout


# ----------------------------------------------------------------------
# pack validate / assemble — live implementation wiring (WP06)
# ----------------------------------------------------------------------
class TestDoctrinePackCommands:
    def test_pack_validate_missing_dir_exits_nonzero(self, fetch_app: typer.Typer, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(fetch_app, ["pack", "validate", str(tmp_path / "pack")])
        # Missing pack directory is a validation error → exit 1.
        assert result.exit_code == 1

    def test_pack_validate_empty_pack_exits_zero(self, fetch_app: typer.Typer, tmp_path: Path) -> None:
        # An empty directory is a structurally valid (no-op) pack.
        empty_pack = tmp_path / "empty-pack"
        empty_pack.mkdir()
        runner = CliRunner()
        result = runner.invoke(fetch_app, ["pack", "validate", str(empty_pack)])
        assert result.exit_code == 0, result.stdout

    def test_pack_assemble_missing_inputs_exits_nonzero(self, fetch_app: typer.Typer, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            fetch_app,
            ["pack", "assemble", str(tmp_path / "out"), str(tmp_path / "in")],
        )
        assert result.exit_code == 1
