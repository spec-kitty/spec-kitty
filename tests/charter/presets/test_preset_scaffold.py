"""``charter org init`` scaffolds an example preset that validates (FR-019, T039/T040)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.offering.packs.presets import load_preset, render_example_preset, write_example_preset
from kernel.charter_pack_paths import pack_presets_dir

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: The scaffolded preset name (contracts: ``presets/starter.yaml``).
EXAMPLE_PRESET_NAME = "starter"


def test_example_preset_lists_no_ids(tmp_path: Path) -> None:
    path = write_example_preset(tmp_path)
    assert path == pack_presets_dir(tmp_path) / f"{EXAMPLE_PRESET_NAME}.yaml"
    assert path.read_text(encoding="utf-8") == render_example_preset()
    preset = load_preset(tmp_path, EXAMPLE_PRESET_NAME)
    assert preset.activations == {}
    assert preset.activated_kinds is None
    assert EXAMPLE_PRESET_NAME not in {"default", "minimal"}


def test_org_init_writes_a_preset_that_validates(tmp_path: Path) -> None:
    from specify_cli.cli.commands.charter._app import charter_app as app

    pack = tmp_path / "pack"
    runner = CliRunner()
    init = runner.invoke(app, ["org", "init", str(pack)])
    assert init.exit_code == 0, init.output
    preset_path = pack_presets_dir(pack) / f"{EXAMPLE_PRESET_NAME}.yaml"
    assert preset_path.is_file()
    assert f"presets/{EXAMPLE_PRESET_NAME}.yaml" in init.output
    assert load_preset(pack, EXAMPLE_PRESET_NAME).name == EXAMPLE_PRESET_NAME
    assert "presets/" in (pack / "README.md").read_text(encoding="utf-8")
    validated = runner.invoke(app, ["org", "validate", str(pack)])
    assert validated.exit_code == 0, validated.output
