"""Integration test: ``init`` produces a project where downstream gates accept the schema.

WP01 (issue #840): a fresh project after ``spec-kitty init`` MUST have both
``schema_version`` and ``schema_capabilities`` populated under ``spec_kitty``
in ``.kittify/metadata.yaml``. Downstream commands (``charter setup``,
``next``, etc.) consult that schema before doing real work and previously
failed with a "missing schema" error on a fresh project, forcing operators
to hand-edit the YAML.

This test exercises the actual ``init`` command via Typer's ``CliRunner`` (the
same surface used in ``tests/specify_cli/cli/commands/test_init_integration.py``)
to prove the schema stamp lands inside the real init pipeline. It then runs
the schema compatibility gate against the resulting project to prove the
fresh project chain is unblocked end-to-end without any operator edit.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from rich.console import Console
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.template.manager import TemplateCopyResult
from specify_cli.migration.schema_version import (
    CURRENT_SCHEMA_CAPABILITIES,
    CURRENT_SCHEMA_VERSION,
    check_compatibility,
    get_project_schema_version,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Local fakes (mirror tests/specify_cli/cli/commands/test_init_integration.py)
# ---------------------------------------------------------------------------


def _fake_copy_package(project_path: Path) -> TemplateCopyResult:
    """Pretend the package install path was successful and return scratch dir."""
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=True)


@pytest.fixture()
def cli_app() -> tuple[Typer, Console]:
    """Return a Typer app with ``init`` registered and heavy I/O mocked."""
    console = Console(file=io.StringIO(), force_terminal=False)
    app = Typer()

    register_init_command(
        app,
        console=console,
        show_banner=lambda: None,
        activate_mission=lambda proj, mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda path, tracker=None: None,
    )
    return app, console


def _run(app: Typer, args: list[str]) -> object:
    runner = CliRunner()
    return runner.invoke(app, args, catch_exceptions=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_init_then_next_no_missing_schema_error(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A fresh project produced by ``init`` passes the schema gate.

    Concretely: after init, ``get_project_schema_version`` returns the
    canonical version and ``check_compatibility`` reports COMPATIBLE — the
    exact gate that previously fired the "missing schema" / "Project requires
    migration" error on fresh projects (issue #840).
    """
    app, _console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        init_module, "get_local_repo_root", lambda override_path=None: None
    )
    monkeypatch.setattr(
        init_module, "copy_specify_base_from_package", _fake_copy_package
    )

    result = _run(app, ["init", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 0, getattr(result, "output", "")
    metadata_path = tmp_path / ".kittify" / "metadata.yaml"
    assert metadata_path.exists(), "init should have produced .kittify/metadata.yaml"

    # Read via plain yaml — exactly what downstream consumers do.
    data = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    spec_kitty = data["spec_kitty"]
    assert isinstance(spec_kitty, dict)

    # Both stamp fields are present and equal to the canonical values.
    assert spec_kitty["schema_version"] == CURRENT_SCHEMA_VERSION
    assert (
        dict(spec_kitty["schema_capabilities"]) == CURRENT_SCHEMA_CAPABILITIES
    )

    # The downstream gate is satisfied without hand-editing.
    project_version = get_project_schema_version(tmp_path)
    assert project_version == CURRENT_SCHEMA_VERSION
    compat = check_compatibility(project_version, CURRENT_SCHEMA_VERSION)
    assert compat.is_compatible, (
        f"fresh project must pass the schema gate; got {compat.status}: {compat.message}"
    )
    assert compat.exit_code == 0
    # The pre-fix message that used to fire here was about a missing schema.
    assert "missing schema" not in compat.message.lower()
    assert "requires migration" not in compat.message.lower()


def test_init_is_idempotent_for_schema_stamp(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Re-running the schema stamp on an already-stamped project is a no-op.

    The init command itself short-circuits when ``.kittify/config.yaml``
    exists, so this test re-invokes the helper directly to confirm the
    additive merge does not rewrite the file when both fields are present.
    """
    app, _console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        init_module, "get_local_repo_root", lambda override_path=None: None
    )
    monkeypatch.setattr(
        init_module, "copy_specify_base_from_package", _fake_copy_package
    )

    result = _run(app, ["init", "--ai", "claude", "--non-interactive"])
    assert result.exit_code == 0, getattr(result, "output", "")

    metadata_path = tmp_path / ".kittify" / "metadata.yaml"
    first_bytes = metadata_path.read_bytes()

    # Re-run the helper — must not modify the file.
    changed = init_module._stamp_schema_metadata(tmp_path / ".kittify")
    assert changed is False
    assert metadata_path.read_bytes() == first_bytes
