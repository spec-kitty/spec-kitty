"""Mission-type provisioning reads the built-in ``default`` preset (FR-003, #3732 WP09).

:func:`charter.activation.compiler.default_preset_mission_types` is the one
seed-read of ``init``, ``charter generate`` and the upgrade provisioning. Each
case points ``SPEC_KITTY_PACKS_ROOT`` at a tmp copy of ``packs/built-in`` and
edits its ``presets/default.yaml``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation import compiler
from charter.activation.compiler import (
    DefaultPresetMissingError,
    default_preset_mission_types,
    prepare_mission_type_activations,
    provision_mission_type_activations,
)
from kernel.errors import KittyInternalConsistencyError

pytestmark = [pytest.mark.unit]

_BUILT_IN = Path(__file__).resolve().parents[3] / "packs" / "built-in"
_SAFE_YAML = YAML(typ="safe")
_SHIPPED_TYPES = _SAFE_YAML.load((_BUILT_IN / "presets" / "default.yaml").read_text(encoding="utf-8"))["mission_type_activations"]
_HEADER = "name: default\ndescription: fixture\n"


@pytest.fixture
def default_preset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The ``default`` preset file of a tmp copy of the built-in pack the code resolves."""
    packs_root = tmp_path / "packs-root"
    shutil.copytree(_BUILT_IN, packs_root / "built-in")
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
    return packs_root / "built-in" / "presets" / "default.yaml"


def _project(root: Path, config: str = "vcs:\n  type: git\n") -> Path:
    (root / ".kittify").mkdir(parents=True)
    (root / ".kittify" / "config.yaml").write_text(config, encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------


def test_reader_returns_the_shipped_preset_list() -> None:
    assert default_preset_mission_types() == _SHIPPED_TYPES
    assert _SHIPPED_TYPES, "control: the shipped preset lists mission types"


def test_reader_returns_the_copied_preset_list_verbatim(default_preset: Path) -> None:
    default_preset.write_text(_HEADER + "mission_type_activations:\n  - research\n  - not-a-builtin-type\n", encoding="utf-8")

    assert default_preset_mission_types() == ["research", "not-a-builtin-type"], "copied verbatim, never intersected with the catalog"


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        (None, "does not exist"),
        ("name: default\ndescription: [unclosed\n", "is malformed"),
        (_HEADER + "unknown_key: 1\n", "is malformed"),
        (_HEADER, "declares no non-empty 'mission_type_activations' list"),
        (_HEADER + "mission_type_activations: []\n", "declares no non-empty 'mission_type_activations' list"),
    ],
    ids=["missing", "unparseable", "invalid", "no-key", "empty"],
)
def test_broken_default_preset_fails_closed(default_preset: Path, body: str | None, detail: str) -> None:
    if body is None:
        default_preset.unlink()
    else:
        default_preset.write_text(body, encoding="utf-8")

    with pytest.raises(DefaultPresetMissingError) as caught:
        default_preset_mission_types()

    error = caught.value
    assert isinstance(error, KittyInternalConsistencyError)
    assert error.code == "DEFAULT_PRESET_MISSING"
    assert error.preset_path == default_preset
    assert f"{default_preset} {detail}" in error.body
    assert "reinstall spec-kitty" in error.body


# ---------------------------------------------------------------------------
# prepare_mission_type_activations seeds from the preset and observes it
# ---------------------------------------------------------------------------


def test_prepare_seeds_the_preset_list_and_observes_the_preset_file(default_preset: Path, tmp_path: Path) -> None:
    default_preset.write_text(_HEADER + "mission_type_activations: [software-dev, research]\n", encoding="utf-8")
    project = _project(tmp_path / "project")

    prepared = prepare_mission_type_activations(project)

    assert prepared.reason == "key_missing"
    assert prepared.mission_type_activations == ("software-dev", "research")
    assert default_preset in {observation.path for observation in prepared.write.observations}
    assert prepared.apply() is True
    assert _SAFE_YAML.load(project / ".kittify" / "config.yaml")["mission_type_activations"] == ["software-dev", "research"]


def test_prepared_write_refuses_after_the_preset_changed(default_preset: Path, tmp_path: Path) -> None:
    project = _project(tmp_path / "project")
    prepared = prepare_mission_type_activations(project)
    before = (project / ".kittify" / "config.yaml").read_bytes()

    default_preset.write_text(default_preset.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")

    with pytest.raises(ValueError, match="precondition_changed"):
        prepared.apply()
    assert (project / ".kittify" / "config.yaml").read_bytes() == before


@pytest.mark.parametrize("authored", ["mission_type_activations: []\n", "mission_type_activations: [custom-type]\n"])
def test_present_key_is_untouched_and_never_reads_the_preset(default_preset: Path, tmp_path: Path, authored: str) -> None:
    default_preset.unlink()  # a present key must not even consult the (here broken) seed
    project = _project(tmp_path / "project", "vcs:\n  type: git\n" + authored)
    before = (project / ".kittify" / "config.yaml").read_bytes()

    prepared = prepare_mission_type_activations(project)

    assert prepared.reason == "key_present"
    assert default_preset not in {observation.path for observation in prepared.write.observations}
    assert provision_mission_type_activations(project) is False
    assert (project / ".kittify" / "config.yaml").read_bytes() == before


def test_missing_preset_fails_closed_before_any_write(default_preset: Path, tmp_path: Path) -> None:
    default_preset.unlink()
    project = _project(tmp_path / "project")
    before = (project / ".kittify" / "config.yaml").read_bytes()

    with pytest.raises(DefaultPresetMissingError):
        provision_mission_type_activations(project)

    assert (project / ".kittify" / "config.yaml").read_bytes() == before


def test_reader_path_comes_from_the_kernel_presets_dir(default_preset: Path) -> None:
    assert compiler._default_preset_path() == default_preset
