"""One seed-read for ``mission_type_activations``: the built-in ``default`` preset (FR-003).

``spec-kitty init``
(:func:`specify_cli.provisioning.default_charter.provision_default_mission_type_activations`)
and ``spec-kitty charter generate`` / upgrade
(:func:`charter.activation.compiler.provision_mission_type_activations`) both
seed ``mission_type_activations`` through
:func:`charter.activation.compiler.default_preset_mission_types`. This suite
pins:

* both provisioners seed the IDENTICAL set from the real built-in ``default``
  preset;
* a missing, malformed or empty ``default`` preset fails closed on BOTH write
  paths with the same ``DEFAULT_PRESET_MISSING`` error, writing nothing.

Each broken case points ``SPEC_KITTY_PACKS_ROOT`` at a tmp copy of the
built-in pack. Write-side behaviour (which file, additive-only, idempotence,
authored ``[]`` preserved) is covered by
``tests/specify_cli/cli/commands/test_init_provisioning.py`` and
``tests/charter/test_mission_type_activation_emit.py``.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.compiler import (
    DefaultPresetMissingError,
    default_preset_mission_types,
    provision_mission_type_activations,
)
from specify_cli.provisioning.default_charter import provision_default_mission_type_activations

pytestmark = [pytest.mark.fast]

_SAFE_YAML = YAML(typ="safe")
_BUILT_IN = Path(__file__).resolve().parents[2] / "packs" / "built-in"
_SHIPPED = _SAFE_YAML.load((_BUILT_IN / "presets" / "default.yaml").read_text(encoding="utf-8"))


def _load_config(config_file: Path) -> dict:
    return _SAFE_YAML.load(config_file) or {}


def _missing(preset: Path) -> None:
    preset.unlink()


def _malformed(preset: Path) -> None:
    preset.write_text("name: default\ndescription: [unclosed\n", encoding="utf-8")


def _empty(preset: Path) -> None:
    preset.write_text("name: default\ndescription: fixture\nmission_type_activations: []\n", encoding="utf-8")


_BREAKAGES: dict[str, Callable[[Path], None]] = {"missing": _missing, "malformed": _malformed, "empty": _empty}


@pytest.fixture
def broken_default_preset(request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp copy of the built-in pack whose ``default`` preset is broken as ``request.param`` names."""
    packs_root = tmp_path / "packs-root"
    shutil.copytree(_BUILT_IN, packs_root / "built-in")
    preset = packs_root / "built-in" / "presets" / "default.yaml"
    _BREAKAGES[request.param](preset)
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
    return preset


def _legacy_project(root: Path) -> Path:
    kittify = root / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "config.yaml").write_text("vcs:\n  type: git\n", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Parity: both provisioners seed the identical set from the real default preset
# ---------------------------------------------------------------------------


def test_both_provisioners_seed_identical_set_from_the_default_preset(tmp_path: Path) -> None:
    """init and charter-generate write the SAME activation list, the preset's."""
    init_project = tmp_path / "init-project"
    assert provision_default_mission_type_activations(init_project) is True
    init_config = _load_config(init_project / ".kittify" / "config.yaml")

    gen_project = _legacy_project(tmp_path / "gen-project")
    assert provision_mission_type_activations(gen_project) is True
    gen_config = _load_config(gen_project / ".kittify" / "config.yaml")

    shared = default_preset_mission_types()

    assert shared == _SHIPPED["mission_type_activations"]
    assert init_config["mission_type_activations"] == shared
    assert gen_config["mission_type_activations"] == shared
    assert shared  # non-empty: a fixture-free regression would be silent otherwise


# ---------------------------------------------------------------------------
# Fail-closed: a missing / malformed / empty default preset blocks BOTH provisioners
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("broken_default_preset", sorted(_BREAKAGES), indirect=True)
def test_charter_generate_path_fails_closed_on_broken_default_preset(broken_default_preset: Path, tmp_path: Path) -> None:
    project = _legacy_project(tmp_path / "project")

    with pytest.raises(DefaultPresetMissingError) as caught:
        provision_mission_type_activations(project)

    assert caught.value.code == "DEFAULT_PRESET_MISSING"
    assert str(broken_default_preset) in caught.value.body
    assert "mission_type_activations" not in _load_config(project / ".kittify" / "config.yaml")


@pytest.mark.parametrize("broken_default_preset", sorted(_BREAKAGES), indirect=True)
def test_init_path_fails_closed_on_broken_default_preset(broken_default_preset: Path, tmp_path: Path) -> None:
    project = tmp_path / "project"

    with pytest.raises(DefaultPresetMissingError) as caught:
        provision_default_mission_type_activations(project)

    assert caught.value.code == "DEFAULT_PRESET_MISSING"
    assert not (project / ".kittify" / "config.yaml").exists()
