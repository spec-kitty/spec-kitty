"""``scripts/service_platform.py``: reading an OS floor out of a native binary (#6948).

Every fixture is a few hundred bytes of real header structure built by
``tests/kernel/service_release_fixture``; nothing here reads a released binary or touches the
network. The reader is loaded by path, the way ``tests/cross_cutting/packaging/
test_companion_services_wheel.py`` loads the build script.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from kernel.service_pin import ServiceTarget
from tests.kernel.service_release_fixture import elf64, macho64, pe64

pytestmark = pytest.mark.fast

_REPO = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO / "scripts" / "service_platform.py"


@pytest.fixture(scope="module")
def platform_floor() -> ModuleType:
    spec = importlib.util.spec_from_file_location("service_platform_under_test", _SCRIPT)
    assert spec is not None and spec.loader is not None
    import sys

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# Target -> floor kind
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("target", "kind"),
    [("linux-x64", "glibc"), ("linux-arm64", "glibc"), ("macos-arm64", "macos"), ("windows-x64", None)],
)
def test_each_native_target_maps_to_the_floor_its_tag_states(platform_floor: ModuleType, target: str, kind: str | None) -> None:
    assert platform_floor.floor_kind(target) is kind


def test_an_unknown_or_non_native_target_is_refused(platform_floor: ModuleType) -> None:
    with pytest.raises(ValueError, match="not a native service target"):
        platform_floor.floor_kind("jvm")
    with pytest.raises(ValueError, match="not a native service target"):
        platform_floor.floor_kind("freebsd-riscv64")


# --------------------------------------------------------------------------- #
# Linux: the ELF version needs
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("target", ["linux-x64", "linux-arm64"])
def test_the_glibc_floor_is_the_highest_version_need(platform_floor: ModuleType, target: str) -> None:
    assert platform_floor.read_floor(elf64(glibc="2_39", target=ServiceTarget(target)), target) == "2_39"


def test_several_version_needs_resolve_to_the_highest(platform_floor: ModuleType) -> None:
    data = elf64(glibc=["2_17", "2_42", "2_34"])
    assert platform_floor.read_floor(data, "linux-x64") == "2_42"


def test_a_three_part_version_name_normalizes_to_major_minor(platform_floor: ModuleType) -> None:
    assert platform_floor.read_floor(elf64(glibc="2.2.5"), "linux-x64") == "2_2"


def test_an_elf_with_no_version_needs_states_no_floor(platform_floor: ModuleType) -> None:
    assert platform_floor.read_floor(elf64(glibc=None), "linux-x64") is None


def test_a_statically_linked_elf_states_no_floor(platform_floor: ModuleType) -> None:
    assert platform_floor.read_floor(elf64(static=True), "linux-x64") is None


def test_a_glibc_floor_is_found_through_a_stripped_image(platform_floor: ModuleType) -> None:
    """No section headers at all: the reader goes through PT_DYNAMIC, as a stripped native image needs."""
    data = elf64(glibc="2_39")
    assert data[40:48] == b"\x00" * 8  # e_shoff == 0
    assert data[60:62] == b"\x00" * 2  # e_shnum == 0
    assert platform_floor.read_floor(data, "linux-x64") == "2_39"


# --------------------------------------------------------------------------- #
# macOS: the Mach-O build-version command
# --------------------------------------------------------------------------- #


def test_the_macos_floor_is_the_build_version_minos(platform_floor: ModuleType) -> None:
    assert platform_floor.read_floor(macho64(minos="11_0"), "macos-arm64") == "11_0"


def test_a_newer_minos_is_reported_as_is(platform_floor: ModuleType) -> None:
    assert platform_floor.read_floor(macho64(minos="14_2"), "macos-arm64") == "14_2"


def test_the_deprecated_minimum_command_is_read_when_it_is_all_there_is(platform_floor: ModuleType) -> None:
    """Only ``LC_VERSION_MIN_MACOSX`` (no ``LC_BUILD_VERSION``): an older toolchain's image."""
    data = macho64_without_build_version("12_3")
    assert platform_floor.read_floor(data, "macos-arm64") == "12_3"


def test_a_build_version_for_another_platform_is_not_a_macos_floor(platform_floor: ModuleType) -> None:
    with pytest.raises(platform_floor.UnreadableBinary, match="no macOS build-version command"):
        platform_floor.read_floor(macho64(platform=2), "macos-arm64")


def macho64_without_build_version(version: str) -> bytes:
    """A Mach-O whose only load command is the deprecated ``LC_VERSION_MIN_MACOSX``."""
    data = macho64(minos=version, minimum=version)
    header, command = data[:32], data[32:56]
    assert int.from_bytes(command[0:4], "little") == 0x32
    kept = data[56:]  # drop the LC_BUILD_VERSION command, keep LC_VERSION_MIN_MACOSX
    out = bytearray(header + kept)
    out[16:20] = (1).to_bytes(4, "little")  # ncmds
    out[20:24] = len(kept).to_bytes(4, "little")  # sizeofcmds
    return bytes(out)


# --------------------------------------------------------------------------- #
# Windows and the other targets
# --------------------------------------------------------------------------- #


def test_windows_states_no_floor_and_is_never_measured(platform_floor: ModuleType) -> None:
    assert platform_floor.read_floor(pe64(), "windows-x64") is None
    assert platform_floor.read_floor(b"not a binary at all", "windows-x64") is None
    assert platform_floor.required_floor("windows-x64", {"write-service.exe": b"MZ"}) is None


# --------------------------------------------------------------------------- #
# Refusals: a floor nobody could read is never assumed
# --------------------------------------------------------------------------- #


def _patched(data: bytes, offset: int, value: int, size: int) -> bytes:
    """*data* with the little-endian *size*-byte *value* written at *offset*."""
    out = bytearray(data)
    out[offset : offset + size] = value.to_bytes(size, "little")
    return bytes(out)


@pytest.mark.parametrize(
    ("data", "target", "reason"),
    [
        (b"#!/bin/sh\necho not a native binary\n", "linux-x64", r"not an ELF file"),
        (b"\x7fELF", "linux-x64", r"truncated ELF header"),
        (elf64()[:4] + b"\x01" + elf64()[5:], "linux-x64", r"32-bit ELF"),
        (elf64()[:5] + b"\x02" + elf64()[6:], "linux-x64", r"big-endian ELF"),
        (elf64()[:64], "linux-x64", r"truncated"),
        (b"\xcf\xfa\xed\xfe" + b"\x00" * 28, "macos-arm64", r"no macOS build-version command"),
        (b"\xca\xfe\xba\xbe" + b"\x00" * 60, "macos-arm64", r"universal \(fat\) Mach-O"),
        (b"\xce\xfa\xed\xfe" + b"\x00" * 28, "macos-arm64", r"32-bit Mach-O"),
        (b"\x00\x00\x00\x00" + b"\x00" * 60, "macos-arm64", r"not a Mach-O file"),
        (b"#!/bin/sh\n", "macos-arm64", r"truncated Mach-O header"),
        (_patched(macho64(), 36, 0, 4), "macos-arm64", r"shorter than its own header"),  # cmdsize 0 must not spin
        (_patched(macho64(), 36, 4096, 4), "macos-arm64", r"runs past the end"),  # cmdsize beyond the file
        (macho64(), "linux-x64", r"not an ELF file"),  # a Mach-O in a Linux slot is not read with the other reader
        (_patched(elf64(), 64 + 2 * 56, 0x6FFFFFF0, 8), "linux-x64", r"no DT_STRTAB"),  # version needs, no string table
        (_patched(elf64(), 64 + 56 + 32, 0, 8), "linux-x64", r"PT_DYNAMIC segment is empty"),  # p_filesz 0
    ],
    ids=[
        "shell-script",
        "elf-stub",
        "elf-32-bit",
        "elf-big-endian",
        "elf-header-only",
        "macho-no-command",
        "macho-fat",
        "macho-32-bit",
        "macho-not",
        "macho-stub",
        "macho-cmdsize-zero",
        "macho-cmdsize-past-end",
        "macho-in-linux-slot",
        "elf-no-string-table",
        "elf-empty-dynamic",
    ],
)
def test_an_unreadable_binary_is_refused_with_a_reason(platform_floor: ModuleType, data: bytes, target: str, reason: str) -> None:
    with pytest.raises(platform_floor.UnreadableBinary, match=reason):
        platform_floor.read_floor(data, target)


# --------------------------------------------------------------------------- #
# The per-wheel maximum and the comparison
# --------------------------------------------------------------------------- #


def test_the_wheel_floor_is_the_maximum_and_names_the_asset_that_sets_it(platform_floor: ModuleType) -> None:
    need = platform_floor.required_floor("linux-x64", {"write-service": elf64(glibc="2_39"), "charter-service": elf64(glibc="2_42")})
    assert (need.floor, need.asset) == ("2_42", "charter-service")


def test_a_tie_reports_the_first_asset_in_sorted_order(platform_floor: ModuleType) -> None:
    need = platform_floor.required_floor("linux-x64", {"b": elf64(glibc="2_39"), "a": elf64(glibc="2_39")})
    assert (need.floor, need.asset) == ("2_39", "a")


def test_a_wheel_of_static_binaries_needs_no_floor(platform_floor: ModuleType) -> None:
    assert platform_floor.required_floor("linux-x64", {"write-service": elf64(static=True)}) is None


def test_a_macos_wheel_takes_the_maximum_minos(platform_floor: ModuleType) -> None:
    need = platform_floor.required_floor("macos-arm64", {"write-service": macho64(minos="11_0"), "charter-service": macho64(minos="12_1")})
    assert (need.floor, need.asset) == ("12_1", "charter-service")


@pytest.mark.parametrize(
    ("measured", "declared", "result"),
    [
        ("2_39", "2_39", False),
        ("2_40", "2_39", True),
        ("2_39", "2_9", True),  # numeric, not lexicographic
        ("2_9", "2_39", False),
        ("11_0", "11_0", False),
        ("12_0", "11_0", True),
        ("9_0", "11_0", False),
    ],
)
def test_the_comparison_is_numeric_per_component(platform_floor: ModuleType, measured: str, declared: str, result: bool) -> None:
    assert platform_floor.exceeds(measured, declared) is result


@pytest.mark.parametrize("value", ["", "2", "2.", "two_39", "2_39_1", "2.39"])
def test_a_floor_that_is_not_major_minor_is_refused(platform_floor: ModuleType, value: str) -> None:
    with pytest.raises(ValueError, match=r"is not <major>_<minor>"):
        platform_floor.parse_floor(value)


def test_parse_floor_reads_both_components(platform_floor: ModuleType) -> None:
    assert platform_floor.parse_floor("2_39") == (2, 39)
