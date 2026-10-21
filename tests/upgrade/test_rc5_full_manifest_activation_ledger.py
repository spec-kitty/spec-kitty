"""An rc5-era project upgraded through the whole manifest ends on the ledger (WP08 T043.4, US2.6, SC-002).

The fixture is
built with :mod:`tests.upgrade._legacy_upgrade_fixture` (a hermetic, committed
git project): an ``4.0.0rc5`` project whose tracked migration ledger records
every migration up to rc5, with its activation keys on the legacy surface (the
pointed ``charter.yaml`` plus an equal ``config.yaml`` mirror). A real
``spec-kitty upgrade`` runs the remaining manifest: the shipped migrations act
on the legacy surface inside the upgrade scope, then
``4.0.0rc8_activation_ledger`` moves what they left into the ledger.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

import pytest
import typer
import yaml
from packaging.version import InvalidVersion, Version
from typer.testing import CliRunner

from charter.activation.activation_ledger import LEDGER_KEYS
from kernel.activation_ledger_store import activation_ledger_path
from specify_cli.cli.commands.migrate_cmd import app as migrate_app
from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA
from specify_cli.upgrade.ledger import build_record
from specify_cli.upgrade.metadata import canonical_schema_capabilities
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry
from tests.upgrade._legacy_upgrade_fixture import make_legacy_project, upgrade_env

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_RC5 = Version("4.0.0rc5")
_MIGRATION_ID = "4.0.0rc8_activation_ledger"
_POINTER = ".kittify/charter/charter.yaml"

_CHARTER = """\
# authored charter
schema_version: "2.0.0"
governance:
  testing: {}
directives: []
catalog: {}
activated_tactics:
- custom-tactic-one
activated_directives:
- CUSTOM_DIRECTIVE_ONE
mission_type_activations:
- software-dev
- research
metadata:
  bundle_schema_version: 2
"""

_CONFIG = f"""\
agents:
  available:
  - claude
vcs:
  type: git
charter: {_POINTER}
mission_type_activations:
- research
- software-dev
"""


def _rc5_ledger() -> str:
    auto_discover_migrations()
    lines = []
    for migration in MigrationRegistry.get_all():
        if migration.clone_local_effect:
            continue
        try:
            settled = Version(migration.target_version) <= _RC5
        except InvalidVersion:
            continue
        if settled:
            lines.append(json.dumps(build_record(migration, "success").to_dict(), ensure_ascii=False))
    return "\n".join(lines) + "\n"


def _metadata() -> str:
    spec_kitty = {
        "version": str(_RC5),
        "initialized_at": "2026-09-01T00:00:00",
        "schema_version": MAX_SUPPORTED_SCHEMA,
        "schema_capabilities": canonical_schema_capabilities(None),
    }
    return yaml.safe_dump({"spec_kitty": spec_kitty}, sort_keys=False)


def _project(tmp_path: Path) -> Path:
    env = upgrade_env(tmp_path)
    return make_legacy_project(
        tmp_path / "project",
        env,
        agents=["claude"],
        gitignore=None,
        extra_files={
            ".kittify/metadata.yaml": _metadata(),
            ".kittify/migration-ledger.jsonl": _rc5_ledger(),
            ".kittify/config.yaml": _CONFIG,
            _POINTER: _CHARTER,
        },
    )


def _yaml(path: Path) -> dict[str, Any]:
    return dict(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def test_rc5_project_upgrades_through_the_whole_manifest_onto_the_ledger(tmp_path: Path) -> None:
    project = _project(tmp_path)
    upgrade_app = typer.Typer(add_completion=False)
    upgrade_app.command()(upgrade)

    with contextlib.chdir(project):
        result = CliRunner().invoke(upgrade_app, ["--yes", "--no-worktrees"], catch_exceptions=False)
    assert result.exit_code == 0, result.output

    ledger = _yaml(activation_ledger_path(project))
    assert ledger["activated_tactics"] == ["custom-tactic-one"]
    assert ledger["activated_directives"] == ["CUSTOM_DIRECTIVE_ONE"]
    assert ledger["mission_type_activations"] == ["software-dev", "research"]
    assert not set(_yaml(project / ".kittify" / "config.yaml")) & set(LEDGER_KEYS)
    charter = project / _POINTER
    assert not set(_yaml(charter)) & set(LEDGER_KEYS)
    assert charter.read_text(encoding="utf-8").startswith("# authored charter\n")

    with contextlib.chdir(project):
        report = CliRunner().invoke(migrate_app, ["ledger", "--json"])
    assert report.exit_code == 0, report.output
    steps = {step["id"]: step for step in json.loads(report.output)["steps"]}
    assert steps[_MIGRATION_ID]["applied"] is True
    assert steps[_MIGRATION_ID]["pending"] is False
