"""``spec-kitty init`` writes the activation ledger for a fresh project (WP03, WP14; FR-019, IC-03 B1/M1).

A fresh ``init`` provisions ``mission_type_activations`` into
``.kittify/charter/activation.yaml``, puts no activation key into
``config.yaml``, and the command-rendering identity
(:func:`specify_cli.skills.command_renderer.rendering_inputs`) ends with the
ledger. On an unmigrated project (legacy activation keys, no ledger) the
provisioning keeps the legacy target and never creates a ledger (hole 3).
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console
from ruamel.yaml import YAML
from typer import Typer
from typer.testing import CliRunner

from charter.activation.activation_ledger import LEDGER_KEYS
from kernel.activation_ledger_store import activation_ledger_path
from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.provisioning.default_charter import provision_default_mission_type_activations
from specify_cli.skills.command_renderer import rendering_inputs, validate_mission_provisioning
from specify_cli.template.manager import TemplateCopyResult
from tests._factories.activation_ledger import read_activation_ledger

pytestmark = pytest.mark.integration

_SAFE_YAML = YAML(typ="safe")
_BUILT_IN = Path(__file__).resolve().parents[4] / "packs" / "built-in"
_DEFAULT_TYPES = _SAFE_YAML.load(_BUILT_IN / "presets" / "default.yaml")["mission_type_activations"]


def _fake_copy_package(project_path: Path) -> TemplateCopyResult:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=True)


@pytest.fixture()
def cli_app(monkeypatch: pytest.MonkeyPatch) -> Typer:
    """A minimal Typer app with ``init`` registered and heavy I/O mocked (as ``test_init_provisioning``)."""
    app = Typer()
    register_init_command(
        app,
        console=Console(file=io.StringIO(), force_terminal=False),
        show_banner=lambda: None,
        activate_mission=lambda proj, mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda path, tracker=None: None,
    )
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)
    return app


def _config(project: Path) -> dict[str, Any]:
    return dict(_SAFE_YAML.load(project / ".kittify" / "config.yaml") or {})


def test_init_writes_mission_type_activations_to_the_ledger(cli_app: Typer, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli_app, ["init", "fresh-ledger", "--ai", "claude", "--non-interactive"], catch_exceptions=True)
    assert result.exit_code == 0, result.output

    project = tmp_path / "fresh-ledger"
    assert read_activation_ledger(project) == {"mission_type_activations": _DEFAULT_TYPES}
    assert not set(_config(project)) & set(LEDGER_KEYS)
    assert rendering_inputs(project)[-1] == activation_ledger_path(project)


def test_provisioning_writes_the_ledger_only_when_the_key_is_absent(tmp_path: Path) -> None:
    assert provision_default_mission_type_activations(tmp_path) is True
    ledger = activation_ledger_path(tmp_path)
    before = ledger.read_bytes()

    assert provision_default_mission_type_activations(tmp_path) is False
    assert ledger.read_bytes() == before
    assert read_activation_ledger(tmp_path) == {"mission_type_activations": _DEFAULT_TYPES}
    assert not (tmp_path / ".kittify" / "config.yaml").exists() or not set(_config(tmp_path)) & set(LEDGER_KEYS)


def test_provisioning_an_unmigrated_project_keeps_the_legacy_target(tmp_path: Path) -> None:
    config = tmp_path / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("activated_directives:\n- 024-locality-of-change\n", encoding="utf-8")

    assert provision_default_mission_type_activations(tmp_path) is True

    assert not activation_ledger_path(tmp_path).exists()
    assert _config(tmp_path) == {"activated_directives": ["024-locality-of-change"], "mission_type_activations": _DEFAULT_TYPES}


def test_provisioning_an_unmigrated_project_with_the_key_is_a_no_op(tmp_path: Path) -> None:
    config = tmp_path / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("mission_type_activations: [research]\n", encoding="utf-8")
    before = config.read_bytes()

    assert provision_default_mission_type_activations(tmp_path) is False

    assert config.read_bytes() == before
    assert not activation_ledger_path(tmp_path).exists()


def test_rendering_identity_ends_with_the_ledger_of_a_fresh_project(tmp_path: Path) -> None:
    config = tmp_path / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("vcs:\n  type: git\n", encoding="utf-8")

    assert rendering_inputs(tmp_path) == (config, activation_ledger_path(tmp_path))


def test_mission_provisioning_validates_against_the_ledger(tmp_path: Path) -> None:
    config = tmp_path / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("vcs:\n  type: git\n", encoding="utf-8")
    ledger = activation_ledger_path(tmp_path)

    validate_mission_provisioning(tmp_path, None, b"mission_type_activations: [software-dev]\n", ledger.resolve())
    with pytest.raises(ValueError, match="existing rendering authority"):
        validate_mission_provisioning(tmp_path, None, b"mission_type_activations: [software-dev]\n", config.resolve())
