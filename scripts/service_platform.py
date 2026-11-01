"""The OS floor a native service binary needs, read from the binary itself (#6948).

A companion platform wheel's tag states an OS minimum — ``manylinux_2_39_x86_64``,
``macosx_11_0_arm64`` — so the number in it is a promise to whoever installs the wheel. This
module reads that minimum out of the binary the wheel carries, so the release build can refuse
a wheel whose tag claims an older OS than the binary needs
(``SERVICE_PLATFORM_FLOOR_EXCEEDED``) instead of publishing one that dies at exec.

What is read, per platform:

- **Linux** (``linux-x64``, ``linux-arm64``): the highest ``GLIBC_<major>.<minor>`` version need
  in the ELF's ``.gnu.version_r`` table, reached through ``PT_DYNAMIC`` → ``DT_VERNEED`` so a
  stripped GraalVM image with no section headers still works. Version *indexes* are not used:
  they are not a stable encoding of the glibc release.
- **macOS** (``macos-arm64``): ``LC_BUILD_VERSION`` ``minos``, falling back to the deprecated
  ``LC_VERSION_MIN_MACOSX`` command. Thin 64-bit images only.
- **Windows** (``windows-x64``): nothing. ``win_amd64`` states no OS minimum, so the target has
  no floor kind at all.

Standard library only, and build-time only: the reader lives here rather than in ``src/kernel``
(its only caller is the release tooling) or in the companion package (whose ``wheel.py`` is
copied into every wheel, and this is not something a wheel needs).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

__all__ = [
    "GLIBC",
    "MACOS",
    "FloorNeed",
    "UnreadableBinary",
    "exceeds",
    "floor_kind",
    "parse_floor",
    "read_floor",
    "required_floor",
]

GLIBC = "glibc"
MACOS = "macos"

#: Target -> the kind of floor its tag states, or ``None`` when the tag states no minimum.
#: The targets are ``kernel.service_pin.ServiceTarget`` values.
_FLOOR_KINDS: Mapping[str, str | None] = {
    "linux-x64": GLIBC,
    "linux-arm64": GLIBC,
    "macos-arm64": MACOS,
    "windows-x64": None,
}

_FLOOR = re.compile(r"^(\d+)_(\d+)$")
_GLIBC_NAME = re.compile(r"^GLIBC_(\d+)\.(\d+)(?:\.(\d+))?$")

_ELF_MAGIC = b"\x7fELF"
_ELFCLASS32, _ELFCLASS64 = 1, 2
_ELFDATA2LSB = 1
_ELF_HEADER_SIZE = 64
_ELF_PHDR_SIZE = 56
_PT_LOAD = 1
_PT_DYNAMIC = 2
_DT_NULL = 0
_DT_STRTAB = 5
_DT_STRSZ = 10
_DT_VERNEED = 0x6FFFFFFE
_DT_VERNEEDNUM = 0x6FFFFFFF
_DYN_SIZE = 16
_VERNEED_SIZE = 16
_VERNAUX_SIZE = 16

_MACHO_MAGIC_64 = 0xFEEDFACF
_MACHO_MAGIC_32 = 0xFEEDFACE
_MACHO_FAT_MAGICS = (b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca")
_MACHO_HEADER_SIZE = 32
_LC_VERSION_MIN_MACOSX = 0x24
_LC_BUILD_VERSION = 0x32
_PLATFORM_MACOS = 1


class UnreadableBinary(ValueError):
    """A binary whose platform floor cannot be read; the message says why and names the shape found."""


@dataclass(frozen=True)
class FloorNeed:
    """The floor a set of binaries needs: the highest one, and the asset that sets it."""

    floor: str
    asset: str


def floor_kind(target: str) -> str | None:
    """The kind of floor *target*'s wheel tag states (``GLIBC``, ``MACOS``), or ``None`` for none."""
    try:
        return _FLOOR_KINDS[target]
    except KeyError:
        raise ValueError(f"{target!r} is not a native service target ({', '.join(_FLOOR_KINDS)}; jvm is not native)") from None


def read_floor(data: bytes, target: str) -> str | None:
    """The floor *data* needs as a ``<major>_<minor>`` string for *target*, or ``None`` when it states none.

    Raises :class:`UnreadableBinary` when *target* states a floor and the bytes cannot be read
    as the native format that target carries.
    """
    kind = floor_kind(target)
    if kind is None:
        return None
    return _elf_floor(data) if kind == GLIBC else _macho_floor(data)


def required_floor(target: str, binaries: Mapping[str, bytes]) -> FloorNeed | None:
    """The highest floor the *binaries* of *target* need, with the asset that sets it, or ``None``.

    A wheel must satisfy every binary it carries, so the maximum wins; ties go to the first asset
    in sorted order, so the reported asset is deterministic. An asset whose floor cannot be read is a
    :class:`UnreadableBinary` that names it, because a refusal has to say which binary to look at.
    """
    if floor_kind(target) is None:
        return None
    highest: FloorNeed | None = None
    for asset in sorted(binaries):
        try:
            floor = read_floor(binaries[asset], target)
        except UnreadableBinary as exc:
            raise UnreadableBinary(f"{asset}: {exc}") from exc
        if floor is not None and (highest is None or parse_floor(floor) > parse_floor(highest.floor)):
            highest = FloorNeed(floor=floor, asset=asset)
    return highest


def parse_floor(value: str) -> tuple[int, int]:
    """``"2_39"`` -> ``(2, 39)``; anything not ``<major>_<minor>`` is a ``ValueError``."""
    match = _FLOOR.match(value)
    if match is None:
        raise ValueError(f"platform floor {value!r} is not <major>_<minor>")
    return int(match.group(1)), int(match.group(2))


def exceeds(measured: str, declared: str) -> bool:
    """Whether *measured* is a newer floor than *declared* (numeric per component: ``2_39`` > ``2_9``)."""
    return parse_floor(measured) > parse_floor(declared)


def _uint(data: bytes, offset: int, size: int, what: str) -> int:
    """The little-endian unsigned integer of *size* bytes at *offset*, or :class:`UnreadableBinary`."""
    if offset < 0 or size <= 0 or offset + size > len(data):
        raise UnreadableBinary(f"truncated {what}: {size} bytes at offset {offset} run past the {len(data)}-byte file")
    return int.from_bytes(data[offset : offset + size], "little")


# --------------------------------------------------------------------------- #
# ELF
# --------------------------------------------------------------------------- #


def _elf_floor(data: bytes) -> str | None:
    """The highest ``GLIBC_<major>.<minor>`` version need of an ELF64 little-endian image, or ``None``."""
    loads, dynamic = _elf_layout(data)
    if dynamic is None:
        return None  # statically linked: no dynamic symbol versions, so no glibc floor
    entries = _dynamic_entries(data, dynamic)
    if _DT_VERNEED not in entries:
        return None  # no version-need table at all: no versioned symbols, so no glibc floor
    if _DT_STRTAB not in entries or _DT_VERNEEDNUM not in entries:
        raise UnreadableBinary("ELF has a version-need table but no string table or version-need count")
    if not entries[_DT_VERNEEDNUM]:
        return None  # an empty version-need table: no glibc floor
    highest = _highest_glibc(
        data,
        strtab=_file_offset(loads, entries[_DT_STRTAB], "DT_STRTAB"),
        strtab_size=entries.get(_DT_STRSZ, 0),
        verneed=_file_offset(loads, entries[_DT_VERNEED], "DT_VERNEED"),
        count=entries[_DT_VERNEEDNUM],
    )
    return None if highest is None else f"{highest[0]}_{highest[1]}"


def _elf_layout(data: bytes) -> tuple[list[tuple[int, int, int]], tuple[int, int] | None]:
    """Validate the ELF header and return ``(PT_LOAD segments, PT_DYNAMIC (offset, size) or None)``."""
    if data[:4] != _ELF_MAGIC:
        raise UnreadableBinary("not an ELF file")
    if len(data) < _ELF_HEADER_SIZE:
        raise UnreadableBinary(f"truncated ELF header: {len(data)} of {_ELF_HEADER_SIZE} bytes")
    elf_class = data[4]
    if elf_class != _ELFCLASS64:
        raise UnreadableBinary("32-bit ELF" if elf_class == _ELFCLASS32 else f"ELF class {elf_class} (only 64-bit is read)")
    if data[5] != _ELFDATA2LSB:
        raise UnreadableBinary("big-endian ELF (only little-endian is read)")

    phoff = _uint(data, 32, 8, "ELF e_phoff")
    phentsize = _uint(data, 54, 2, "ELF e_phentsize")
    phnum = _uint(data, 56, 2, "ELF e_phnum")
    loads: list[tuple[int, int, int]] = []
    dynamic: tuple[int, int] | None = None
    for index in range(phnum):
        base = phoff + index * phentsize
        what = f"ELF program header {index}"
        p_type = _uint(data, base, 4, what)
        p_offset = _uint(data, base + 8, 8, what)
        p_vaddr = _uint(data, base + 16, 8, what)
        p_filesz = _uint(data, base + 32, 8, what)
        if p_type == _PT_LOAD:
            loads.append((p_vaddr, p_offset, p_filesz))
        elif p_type == _PT_DYNAMIC:
            dynamic = (p_offset, p_filesz)
    return loads, dynamic


def _dynamic_entries(data: bytes, dynamic: tuple[int, int]) -> dict[int, int]:
    """The ``Elf64_Dyn`` tag -> value pairs of the dynamic segment, up to ``DT_NULL``."""
    entries: dict[int, int] = {}
    offset, size = dynamic
    for index in range(size // _DYN_SIZE):
        base = offset + index * _DYN_SIZE
        tag = _uint(data, base, 8, "ELF dynamic entry")
        if tag == _DT_NULL:
            break
        entries[tag] = _uint(data, base + 8, 8, "ELF dynamic entry")
    return entries


def _highest_glibc(data: bytes, *, strtab: int, strtab_size: int, verneed: int, count: int) -> tuple[int, int] | None:
    """The highest ``(major, minor)`` among the ``GLIBC_*`` names of the version-need table."""
    highest: tuple[int, int] | None = None
    offset = verneed
    for _ in range(count):
        vn_cnt = _uint(data, offset + 2, 2, "ELF verneed entry")
        aux = offset + _uint(data, offset + 8, 4, "ELF verneed entry")
        next_need = _uint(data, offset + 12, 4, "ELF verneed entry")
        for _ in range(vn_cnt):
            match = _GLIBC_NAME.match(_cstring(data, strtab, strtab_size, _uint(data, aux + 8, 4, "ELF vernaux entry")))
            if match is not None:
                highest = max(highest or (0, 0), (int(match.group(1)), int(match.group(2))))
            step = _uint(data, aux + 12, 4, "ELF vernaux entry")
            if not step:
                break
            aux += step
        if not next_need:
            break
        offset += next_need
    return highest


def _file_offset(loads: list[tuple[int, int, int]], vaddr: int, what: str) -> int:
    """The file offset of *vaddr*, translated through the ``PT_LOAD`` segments."""
    for start, offset, size in loads:
        if start <= vaddr < start + size:
            return offset + (vaddr - start)
    raise UnreadableBinary(f"ELF {what} address {vaddr:#x} is not inside any loadable segment")


def _cstring(data: bytes, strtab: int, strtab_size: int, index: int) -> str:
    """The NUL-terminated string at *index* in the string table (bounded by *strtab_size*)."""
    if index >= strtab_size:
        raise UnreadableBinary(f"ELF version name {index} is outside the {strtab_size}-byte string table")
    end = data.find(b"\x00", strtab + index, strtab + strtab_size)
    if end < 0:
        raise UnreadableBinary(f"ELF version name at {index} is not NUL-terminated inside the string table")
    return data[strtab + index : end].decode("utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# Mach-O
# --------------------------------------------------------------------------- #


def _macho_floor(data: bytes) -> str | None:
    """The ``minos`` of a thin 64-bit Mach-O image, or the deprecated minimum-macOS version."""
    if data[:4] in _MACHO_FAT_MAGICS:
        raise UnreadableBinary("universal (fat) Mach-O; only a thin arm64 image can be measured")
    if len(data) < _MACHO_HEADER_SIZE:
        raise UnreadableBinary(f"truncated Mach-O header: {len(data)} of {_MACHO_HEADER_SIZE} bytes")
    magic = int.from_bytes(data[:4], "little")
    if magic != _MACHO_MAGIC_64:
        if magic == _MACHO_MAGIC_32:
            raise UnreadableBinary("32-bit Mach-O (only 64-bit is read)")
        raise UnreadableBinary("not a Mach-O file")

    ncmds = _uint(data, 16, 4, "Mach-O header")
    offset = _MACHO_HEADER_SIZE
    built: int | None = None
    minimum: int | None = None
    for index in range(ncmds):
        what = f"Mach-O load command {index}"
        command = _uint(data, offset, 4, what)
        size = _uint(data, offset + 4, 4, what)
        if size < 8:
            raise UnreadableBinary(f"Mach-O load command {index} is {size} bytes, shorter than its own header")
        if offset + size > len(data):
            raise UnreadableBinary(f"Mach-O load command {index} runs past the end of the {len(data)}-byte file")
        if command == _LC_BUILD_VERSION:
            platform = _uint(data, offset + 8, 4, what)
            minos = _uint(data, offset + 12, 4, what)
            if platform == _PLATFORM_MACOS:
                built = minos if built is None else max(built, minos)
        elif command == _LC_VERSION_MIN_MACOSX:
            version = _uint(data, offset + 8, 4, what)
            minimum = version if minimum is None else max(minimum, version)
        offset += size
    packed = built if built is not None else minimum
    if packed is None:
        raise UnreadableBinary("no macOS build-version command (LC_BUILD_VERSION or LC_VERSION_MIN_MACOSX)")
    return f"{packed >> 16}_{(packed >> 8) & 0xFF}"
