"""Behaviour of ``contracts/tools/fixture_builder.py``, the run-time leak-fixture builder (plan D-P11, FR-021).

Leak-class plants are never committed: the builder assembles each one from string fragments into
a temporary root, next to a clean control on the same root. These tests prove each kind builds a
root whose planted value is exactly the one leak the kind names (seen through ``leak_patterns``),
that the control is clean, and that neither the builder nor this test holds a leak-shaped literal.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

TOOLS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "tools"
SCRIPT = TOOLS_DIR / "fixture_builder.py"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", TOOLS_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None, f"cannot load {name}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder() -> ModuleType:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        return _load("fixture_builder")
    finally:
        sys.path.remove(str(TOOLS_DIR))


@pytest.fixture(scope="module")
def leaks() -> ModuleType:
    return _load("leak_patterns")


def _documents(root: Path) -> dict[str, Any]:
    return {path.name: yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted(root.rglob("*.yaml"))}


def test_the_four_leak_kinds_are_offered(builder: ModuleType) -> None:
    assert set(builder.KINDS) == {"host-path-strict", "host-path-human", "email", "forbidden-property"}


def test_an_unknown_kind_is_refused(builder: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown fixture kind"):
        builder.build("not-a-kind", tmp_path)


def test_every_kind_builds_a_planted_file_and_a_clean_control_on_one_root(builder: ModuleType, tmp_path: Path) -> None:
    for kind in builder.KINDS:
        built = builder.build(kind, tmp_path / kind)
        names = sorted(path.name for path in built.root.rglob("*.yaml"))
        assert names == sorted([builder.CONTROL_FILE, builder.PLANTED_FILE]), (kind, names)
        assert built.expected_codes, kind


def test_the_strict_host_path_plant_is_seen_by_the_strict_class_only(builder: ModuleType, leaks: ModuleType, tmp_path: Path) -> None:
    built = builder.build("host-path-strict", tmp_path)
    value = _documents(built.root)[builder.PLANTED_FILE][built.field]
    assert built.expected_codes == ("HOST_PATH",)
    assert leaks.leak_codes(value, leaks.STRICT) == ("HOST_PATH",)


def test_the_human_host_path_plant_is_seen_by_the_human_class(builder: ModuleType, leaks: ModuleType, tmp_path: Path) -> None:
    built = builder.build("host-path-human", tmp_path)
    value = _documents(built.root)[builder.PLANTED_FILE][built.field]
    assert built.expected_codes == ("HOST_PATH",)
    assert leaks.leak_codes(value, leaks.HUMAN) == ("HOST_PATH",)


def test_the_email_plant_is_seen_in_both_classes(builder: ModuleType, leaks: ModuleType, tmp_path: Path) -> None:
    built = builder.build("email", tmp_path)
    value = _documents(built.root)[builder.PLANTED_FILE][built.field]
    assert built.expected_codes == ("EMAIL",)
    assert leaks.leak_codes(value, leaks.HUMAN) == ("EMAIL",)
    assert leaks.leak_codes(value, leaks.STRICT) == ("EMAIL",)


def test_the_forbidden_property_plant_is_a_key_the_name_list_rejects(builder: ModuleType, leaks: ModuleType, tmp_path: Path) -> None:
    built = builder.build("forbidden-property", tmp_path)
    document = _documents(built.root)[builder.PLANTED_FILE]
    assert built.expected_codes == ("FORBIDDEN_PROPERTY_NAME",)
    assert [key for key in document if leaks.is_forbidden_property_name(key)] == [built.field]


def test_the_control_is_clean_under_every_pattern_and_has_strict_and_human_values(builder: ModuleType, leaks: ModuleType, tmp_path: Path) -> None:
    built = builder.build("email", tmp_path)
    control = _documents(built.root)[builder.CONTROL_FILE]
    assert not [key for key in control if leaks.is_forbidden_property_name(key)]
    for key, value in control.items():
        field_class = leaks.STRICT if key in builder.STRICT_FIELDS else leaks.HUMAN
        assert leaks.leak_codes(value, field_class) == (), (key, value)
    assert set(control) & set(builder.STRICT_FIELDS), "a control needs a strict-class value"
    assert set(control) - set(builder.STRICT_FIELDS), "a control needs a human-class value"


def test_the_control_carries_the_two_real_pass_controls(builder: ModuleType, tmp_path: Path) -> None:
    control = _documents(builder.build("email", tmp_path).root)[builder.CONTROL_FILE]
    assert control["friendlyName"] == "~/.kittify Runtime Centralization"
    assert control["title"] == "/tmp burn-down: sync"


def test_the_command_line_builds_every_kind_under_out(tmp_path: Path, builder: ModuleType) -> None:
    result = subprocess.run([sys.executable, str(SCRIPT), "--out", str(tmp_path)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    for kind in builder.KINDS:
        assert (tmp_path / kind / "planted" / "examples" / builder.PLANTED_FILE).is_file(), kind
        assert kind in result.stdout


def test_the_command_line_refuses_an_unknown_kind(tmp_path: Path) -> None:
    result = subprocess.run([sys.executable, str(SCRIPT), "--out", str(tmp_path), "--kind", "nope"], capture_output=True, text=True, check=False)
    assert result.returncode == 2


@pytest.mark.parametrize("source", [SCRIPT, Path(__file__)], ids=["builder", "this-test"])
def test_no_leak_shaped_literal_in_the_builder_or_its_test(source: Path, leaks: ModuleType) -> None:
    text = source.read_text(encoding="utf-8")
    for number, line in enumerate(text.splitlines(), start=1):
        assert leaks.leak_codes(line, leaks.HUMAN) == (), f"{source.name}:{number} holds a leak-shaped literal"
    lowered = text.replace("_", "").replace("-", "").lower()
    for name in leaks.FORBIDDEN_PROPERTY_NAMES:
        assert name.replace("_", "").lower() not in lowered, f"{source.name} spells a forbidden property name"
