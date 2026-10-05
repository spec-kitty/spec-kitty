"""Behaviour of ``contracts/tools/fixture_builder.py``, the run-time leak-fixture builder (plan D-P11, FR-021).

Leak-class plants are never committed: the builder assembles each one from string fragments into
a temporary root, next to a clean control on the same root. These tests prove each kind builds a
root whose planted value is exactly the one leak the kind names (seen through ``leak_patterns``),
that the control is clean, and that neither the builder nor this test holds a leak-shaped literal.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

TOOLS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "tools"
SCRIPT = TOOLS_DIR / "fixture_builder.py"


def _load(mp: pytest.MonkeyPatch, name: str) -> ModuleType:
    return load_tool(mp, TOOLS_DIR / f"{name}.py", f"{name}_under_test")


@pytest.fixture(scope="module")
def builder() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        mp.syspath_prepend(str(TOOLS_DIR))
        yield _load(mp, "fixture_builder")


@pytest.fixture(scope="module")
def leaks() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        yield _load(mp, "leak_patterns")


def _documents(root: Path) -> dict[str, Any]:
    return {path.name: yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted(root.rglob("*.yaml"))}


OLD_KINDS = ("host-path-strict", "host-path-human", "email", "email-dotless", "github-token", "aws-key", "private-key", "forbidden-property")
NEW_STRICT_NAMES = ("id", "laneId", "laneBranch", "planningBranch", "pattern", "feedbackReference", "reviewer", "kind", "mediaType", "changeState")
ARTIFACT_PATH_REASONS = (
    "empty",
    "too_long",
    "absolute",
    "tilde",
    "drive_letter",
    "backslash",
    "nul",
    "line_break",
    "empty_segment",
    "trailing_slash",
    "dot_segment",
    "dotdot_segment",
)
REGRESSION_CONTROLS = {
    "content-host-path-and-email": ("content", ("HOST_PATH", "EMAIL")),
    "credential-in-content": ("content", ("SECRET",)),
    "credential-in-title": ("title", ("SECRET",)),
}
STRICT_KINDS = tuple(f"strict-{name}" for name in NEW_STRICT_NAMES)
ARTIFACT_PATH_KINDS = tuple(f"artifact-path-{reason.replace('_', '-')}" for reason in ARTIFACT_PATH_REASONS) + ("artifact-path-reference",)
AT = chr(64)


@pytest.fixture(scope="module")
def scanner() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, TOOLS_DIR / "leak_scan.py", "leak_scan_for_builder_test", syspath=TOOLS_DIR)


def test_the_leak_kinds_are_offered(builder: ModuleType) -> None:
    expected = set(OLD_KINDS) | set(STRICT_KINDS) | set(ARTIFACT_PATH_KINDS) | set(REGRESSION_CONTROLS)
    assert set(builder.KINDS) == expected
    assert len(builder.KINDS) == len(expected) == 34
    assert tuple(builder.KINDS[:8]) == OLD_KINDS


def test_the_strict_field_list_gains_the_ten_names_and_keeps_title_out(builder: ModuleType) -> None:
    assert set(NEW_STRICT_NAMES) <= set(builder.STRICT_FIELDS)
    assert "title" not in builder.STRICT_FIELDS


@pytest.mark.parametrize("name", NEW_STRICT_NAMES)
def test_a_strict_name_plant_is_a_strict_only_host_path_next_to_a_clean_control(builder: ModuleType, leaks: ModuleType, tmp_path: Path, name: str) -> None:
    built = builder.build(f"strict-{name}", tmp_path)
    documents = _documents(built.root)
    value = documents[builder.PLANTED_FILE][name]
    assert built.field == name and built.expected_codes == ("HOST_PATH",)
    assert leaks.leak_codes(value, leaks.STRICT) == ("HOST_PATH",)
    assert leaks.leak_codes(value, leaks.HUMAN) == (), "a plant the human class also reports would not need the strict name"
    assert leaks.leak_codes(documents[builder.CONTROL_FILE][name], leaks.STRICT) == ()


@pytest.mark.parametrize("kind", ARTIFACT_PATH_KINDS)
def test_an_artifact_path_plant_is_one_malformed_entry_next_to_a_control_of_odd_legitimate_names(
    builder: ModuleType, scanner: ModuleType, tmp_path: Path, kind: str
) -> None:
    built = builder.build(kind, tmp_path)
    documents = _documents(built.root)
    key = "artifactPath" if kind == "artifact-path-reference" else "path"
    planted = documents[builder.PLANTED_FILE]["entries"]
    control = [entry[key] for entry in documents[builder.CONTROL_FILE]["entries"]]
    assert built.field == f"entries[0].{key}" and built.expected_codes == ("ARTIFACT_PATH_MALFORMED",)
    assert len(planted) == 1, "a list in the fragment replaces the list of the base, it is not concatenated"
    expected_reason = "dotdot_segment" if kind == "artifact-path-reference" else kind.removeprefix("artifact-path-").replace("-", "_")
    assert scanner.malformed_artifact_path(planted[0][key]) == expected_reason
    assert [scanner.malformed_artifact_path(name) for name in control] == [None] * len(control)
    assert any(name.startswith("home/") for name in control), "a home/<x>/ directory segment"
    assert any(" " in name for name in control), "a space"
    assert any(not name.isascii() for name in control), "an accented letter"
    assert any(AT in name for name in control), "an at sign, built at run time"


@pytest.mark.parametrize(("kind", "expected"), sorted(REGRESSION_CONTROLS.items()))
def test_a_content_or_title_regression_control_plants_into_human_text_and_has_a_clean_control(
    builder: ModuleType, leaks: ModuleType, tmp_path: Path, kind: str, expected: tuple[str, tuple[str, ...]]
) -> None:
    key, codes = expected
    built = builder.build(kind, tmp_path)
    documents = _documents(built.root)
    assert built.field == key and built.expected_codes == codes
    assert set(codes) <= set(leaks.leak_codes(documents[builder.PLANTED_FILE][key], leaks.HUMAN))
    assert leaks.leak_codes(documents[builder.CONTROL_FILE].get(key, ""), leaks.HUMAN) == ()


# blake2b digests (16 bytes) of the two files of each pre-existing kind, taken from the builder as it stood at commit aef7cc967,
# before the Plant-shape change. This test passes before and after that change by design: it is a guard, not a red-first test.
OLD_KIND_DIGESTS = {
    "host-path-strict": ("543b9ca28efb864500af6fb8e2ef9589", "e9dae488da1a557d9ca0ceeaf4ac2a52"),
    "host-path-human": ("543b9ca28efb864500af6fb8e2ef9589", "0de3d5346ef43dd0670c10fcd30ee6b1"),
    "email": ("543b9ca28efb864500af6fb8e2ef9589", "0a54a0917cc301e7ad96a65de656c93a"),
    "email-dotless": ("543b9ca28efb864500af6fb8e2ef9589", "4c9a50e0c8e69bc98db76ca25a8b0605"),
    "github-token": ("543b9ca28efb864500af6fb8e2ef9589", "381bd2c98d20af6347485cdd22686937"),
    "aws-key": ("543b9ca28efb864500af6fb8e2ef9589", "8ef2cd3fcf3f0121b5456770aafd7a2e"),
    "private-key": ("543b9ca28efb864500af6fb8e2ef9589", "2df2933203db1eae948d52b8f97666b0"),
    "forbidden-property": ("543b9ca28efb864500af6fb8e2ef9589", "366879fc7778536cf1b954c7af373f21"),
}


def _digest(path: Path) -> str:
    return hashlib.blake2b(path.read_bytes(), digest_size=16).hexdigest()


@pytest.mark.parametrize("kind", OLD_KINDS)
def test_the_eight_old_kinds_still_build_byte_identically(builder: ModuleType, tmp_path: Path, kind: str) -> None:
    built = builder.build(kind, tmp_path)
    examples = built.root.joinpath(*builder.EXAMPLES_PATH)
    assert (_digest(examples / builder.CONTROL_FILE), _digest(examples / builder.PLANTED_FILE)) == OLD_KIND_DIGESTS[kind]


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


def test_the_dotless_email_plant_is_a_dotless_host_address(builder: ModuleType, leaks: ModuleType, tmp_path: Path) -> None:
    built = builder.build("email-dotless", tmp_path)
    value = _documents(built.root)[builder.PLANTED_FILE][built.field]
    assert built.expected_codes == ("EMAIL",)
    assert "." not in value.split("@")[1].split()[0]
    assert leaks.leak_codes(value, leaks.HUMAN) == ("EMAIL",)
    assert leaks.leak_codes(value, leaks.STRICT) == ("EMAIL",)


@pytest.mark.parametrize("kind", ["github-token", "aws-key", "private-key"])
def test_each_secret_plant_is_seen_as_a_secret_in_both_classes(builder: ModuleType, leaks: ModuleType, tmp_path: Path, kind: str) -> None:
    built = builder.build(kind, tmp_path)
    value = _documents(built.root)[builder.PLANTED_FILE][built.field]
    assert built.expected_codes == ("SECRET",)
    assert leaks.leak_codes(value, leaks.HUMAN) == ("SECRET",)
    assert leaks.leak_codes(value, leaks.STRICT) == ("SECRET",)


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
