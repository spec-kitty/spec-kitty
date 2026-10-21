"""A keyless pre-ledger project gets the ledger from ``spec-kitty upgrade`` (WP08 T049.3, pass-8 M3).

A project with
no activation key anywhere and no ledger gives ``4.0.0rc8_activation_ledger``
nothing to move (``detect()`` is False). The finalizer's provisioning step then
resolves its target after the migrations, outside the legacy upgrade scope, so
the project is *fresh* and ``mission_type_activations`` lands in
``.kittify/charter/activation.yaml``, never on the legacy surface. The positive
control is a legacy-keyed project, whose keys rc8 moves first.
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer
import yaml
from typer.testing import CliRunner

from charter.activation.activation_ledger import LEDGER_KEYS
from kernel.activation_ledger_store import activation_ledger_path
from kernel.clock import now_utc
from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA
from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_GIT_SETUP = (
    ["init", "-q", "-b", "main"],
    ["config", "user.email", "t@example.com"],
    ["config", "user.name", "T"],
    ["add", "-A"],
    ["commit", "-q", "-m", "init"],
)

_MIGRATION_ID = "4.0.0rc8_activation_ledger"
_BUILT_IN = Path(__file__).resolve().parents[3] / "packs" / "built-in"
_DEFAULT_TYPES = yaml.safe_load((_BUILT_IN / "presets" / "default.yaml").read_text(encoding="utf-8"))["mission_type_activations"]


def _project(root: Path, *, config: str) -> Path:
    kittify = root / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "config.yaml").write_text(config, encoding="utf-8")
    ProjectMetadata(version="4.0.0rc8", initialized_at=now_utc(), python_version="3.11", platform="test", platform_version="test").save(kittify)
    MigrationRunner._stamp_schema_version(kittify, MAX_SUPPORTED_SCHEMA)
    auto_discover_migrations()
    ledger = MigrationLedger(root)
    for migration in MigrationRegistry.get_all():
        if migration.migration_id != _MIGRATION_ID:
            ledger.append(build_record(migration, "success"))
    (root / "kitty-specs").mkdir()
    for args in _GIT_SETUP:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    return root


def _upgrade(root: Path) -> Any:
    app = typer.Typer(add_completion=False)
    app.command()(upgrade)
    with contextlib.chdir(root):
        return CliRunner().invoke(app, ["--yes", "--no-worktrees"], catch_exceptions=False)


def _yaml(path: Path) -> dict[str, Any]:
    return dict(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def test_keyless_project_upgrade_provisions_into_the_ledger(tmp_path: Path) -> None:
    root = _project(tmp_path, config="vcs:\n  type: git\n")

    result = _upgrade(root)

    assert result.exit_code == 0, result.output
    assert _yaml(activation_ledger_path(root)) == {"mission_type_activations": _DEFAULT_TYPES}
    assert not set(_yaml(root / ".kittify" / "config.yaml")) & set(LEDGER_KEYS)
    assert not (root / ".kittify" / "charter" / "charter.yaml").exists()
    records = [record.result for record in MigrationLedger(root).read_all() if record.id == _MIGRATION_ID]
    assert records == ["skipped"]


def test_legacy_keyed_project_gets_its_keys_moved_then_provisioned(tmp_path: Path) -> None:
    root = _project(tmp_path, config="vcs:\n  type: git\nactivated_tactics:\n- custom-tactic\n")

    result = _upgrade(root)

    assert result.exit_code == 0, result.output
    assert _yaml(activation_ledger_path(root)) == {"mission_type_activations": _DEFAULT_TYPES, "activated_tactics": ["custom-tactic"]}
    assert not set(_yaml(root / ".kittify" / "config.yaml")) & set(LEDGER_KEYS)
    records = [record.result for record in MigrationLedger(root).read_all() if record.id == _MIGRATION_ID]
    assert records == ["success"]
