"""FR-003 positive control: ``spec-kitty init`` writes what the built-in ``default`` preset lists (#3732 WP09).

Driven through the real ``spec-kitty init`` CLI, not the provisioner function:
a tmp copy of ``packs/built-in`` is resolved through ``SPEC_KITTY_PACKS_ROOT``
and its ``presets/default.yaml`` is edited or removed.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import typer
from click.testing import Result
from rich.console import Console
from ruamel.yaml import YAML
from typer.testing import CliRunner

# The ``charter`` package re-exports the ``generate`` command function under the
# submodule's name, so the module itself is reached through ``import_module``.
generate_module = importlib.import_module("specify_cli.cli.commands.charter.generate")

pytestmark = [pytest.mark.integration]

_BUILT_IN = Path(__file__).resolve().parents[4] / "packs" / "built-in"
_SAFE_YAML = YAML(typ="safe")
_SHIPPED_TYPES: list[str] = _SAFE_YAML.load((_BUILT_IN / "presets" / "default.yaml").read_text(encoding="utf-8"))["mission_type_activations"]


@pytest.fixture
def default_preset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The ``default`` preset file of the copied built-in pack ``spec-kitty`` resolves."""
    packs_root = tmp_path / "packs-root"
    shutil.copytree(_BUILT_IN, packs_root / "built-in")
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
    return packs_root / "built-in" / "presets" / "default.yaml"


def _cli(args: list[str], cwd: Path) -> Result:
    from specify_cli import app

    with contextlib.chdir(cwd):
        return CliRunner().invoke(app, args, catch_exceptions=True)


def _init(parent: Path, name: str = "p") -> tuple[Result, Path]:
    parent.mkdir(parents=True, exist_ok=True)
    return _cli(["init", name, "--ai", "claude", "--non-interactive"], parent), parent / name


def _config(project: Path) -> dict[str, Any]:
    path = project / ".kittify" / "config.yaml"
    return (_SAFE_YAML.load(path) or {}) if path.exists() else {}


def _describe(result: Result) -> str:
    return f"exit={result.exit_code}\n{result.output}\n{result.exception!r}"


def test_init_writes_the_copied_default_preset_mission_types(default_preset: Path, tmp_path: Path) -> None:
    fixture_types = ["software-dev", "research"]
    assert sorted(fixture_types) != sorted(_SHIPPED_TYPES), "control: the fixture differs from the shipped list"
    YAML().dump({"name": "default", "description": "fixture", "mission_type_activations": fixture_types}, default_preset)

    result, project = _init(tmp_path / "work")

    assert result.exit_code == 0, _describe(result)
    assert _config(project)["mission_type_activations"] == fixture_types


def test_init_with_the_untouched_copy_writes_the_shipped_list(default_preset: Path, tmp_path: Path) -> None:
    result, project = _init(tmp_path / "work")

    assert result.exit_code == 0, _describe(result)
    assert _config(project)["mission_type_activations"] == _SHIPPED_TYPES


def test_init_fails_closed_when_the_default_preset_is_missing(default_preset: Path, tmp_path: Path) -> None:
    default_preset.unlink()

    result, project = _init(tmp_path / "work")

    assert result.exit_code == 1, _describe(result)
    assert "Error (DEFAULT_PRESET_MISSING):" in result.output
    assert "presets/default.yaml does not exist" in result.output
    assert "mission_type_activations" not in _config(project)


def test_init_equals_activating_the_default_preset(tmp_path: Path) -> None:
    """FR-003: init leaves exactly the state ``charter activate --preset default`` governs, so applying it changes nothing."""
    result, project = _init(tmp_path / "work")
    assert result.exit_code == 0, _describe(result)
    config = _config(project)

    assert config["mission_type_activations"] == _SHIPPED_TYPES
    assert not [key for key in config if key.startswith("activated_")], "the default preset lists no per-kind keys and no kind gate"

    config_file = project / ".kittify" / "config.yaml"
    before = config_file.read_bytes()
    applied = _cli(["charter", "activate", "--preset", "default"], project)

    assert applied.exit_code == 0, _describe(applied)
    assert config_file.read_bytes() == before, "applying --preset default after init changes no byte"


# --------------------------------------------------------------------------------------
# `charter generate` shares the seed-read and renders the same code (logged WP09 edit)
# --------------------------------------------------------------------------------------


def _project_without_mission_types(root: Path) -> Path:
    (root / ".kittify").mkdir(parents=True)
    (root / ".kittify" / "config.yaml").write_text("vcs:\n  type: git\n", encoding="utf-8")
    return root


@pytest.mark.parametrize("json_output", [False, True], ids=["text", "json"])
def test_charter_generate_renders_default_preset_missing(
    default_preset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], json_output: bool
) -> None:
    text_console = Console(file=io.StringIO(), width=400)
    monkeypatch.setattr(generate_module, "console", text_console)
    default_preset.unlink()
    project = _project_without_mission_types(tmp_path / "project")

    with pytest.raises(typer.Exit) as caught:
        generate_module._provision_mission_types_or_exit(project, json_output=json_output)

    assert caught.value.exit_code == 1
    if json_output:
        envelope = json.loads(capsys.readouterr().out)
        assert envelope["code"] == "DEFAULT_PRESET_MISSING" and "does not exist" in envelope["error"]
    else:
        assert "Error (DEFAULT_PRESET_MISSING):" in text_console.file.getvalue()
    assert "mission_type_activations" not in _config(project)


def test_charter_generate_provisioning_seeds_the_copied_preset(default_preset: Path, tmp_path: Path) -> None:
    YAML().dump({"name": "default", "description": "fixture", "mission_type_activations": ["plan"]}, default_preset)
    project = _project_without_mission_types(tmp_path / "project")

    generate_module._provision_mission_types_or_exit(project, json_output=False)

    assert _config(project)["mission_type_activations"] == ["plan"]
