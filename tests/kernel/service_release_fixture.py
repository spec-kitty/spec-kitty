"""Build a ``file://`` service release for tests (#6590, WP02 T008).

One helper for every test that needs a pinned release on disk: the launcher,
resolution, vendor and sync-script tests all call :func:`build_release` instead
of hand-writing assets, digests and a ``SHA256SUMS`` file.

The layout matches ``kernel.release_assets.asset_url`` for ``file://``
repositories: ``<root>/<tag>/<asset name>``. The returned pin's repository is
``root.as_uri()``, so ``kernel.service_artifacts.fetch_asset`` fetches from the
fixture exactly as it would from a GitHub release.

Not a test module (no ``test_`` prefix), so pytest never collects it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from pathlib import Path

from kernel.service_pin import DEFAULT_ASSET_PREFIXES, PINS_DIR, ServiceAsset, ServicePin, ServiceTarget, pin_file

__all__ = [
    "ASSET_PREFIXES",
    "DEFAULT_ASSETS",
    "FIXTURE_COMMIT",
    "asset_name",
    "build_release",
    "elf64",
    "extra_name",
    "macho64",
    "native_asset",
    "pe64",
    "pin_path",
]

FIXTURE_COMMIT = "0123456789abcdef0123456789abcdef01234567"
SUMS_FILE = "SHA256SUMS"

_JAR = b"PK\x03\x04 fake jar\n"
_ELF_MACHINE: Mapping[ServiceTarget, int] = {ServiceTarget.LINUX_X64: 62, ServiceTarget.LINUX_ARM64: 183}  # EM_X86_64, EM_AARCH64


def _version(tag: str) -> str:
    return tag.removeprefix("service-v")


#: Deployable asset prefix per service: the kernel's own table, never a copy.
ASSET_PREFIXES: Mapping[str, str] = DEFAULT_ASSET_PREFIXES
#: Release names of the shared extras (``contracts/service-pin.schema.md``).
_EXTRA_PREFIXES: Mapping[str, str] = {"contracts": "contract-bundles", "contract_tools": "contract-tools", "fixtures": "conformance-fixtures"}


def asset_name(service: str, tag: str, target: ServiceTarget, *, prefix: str | None = None) -> str:
    """The release asset name of *target*: ``<prefix>-<ver>`` plus the target's ``asset_suffix``."""
    return f"{prefix or ASSET_PREFIXES[service]}-{_version(tag)}{target.asset_suffix}"


def pin_path(root: Path, service: str) -> Path:
    """The lockfile of *service* under the tree *root*: ``<root>/pins/<service>.source.yaml``."""
    return pin_file(Path(root) / PINS_DIR, service)


def extra_name(key: str, tag: str) -> str:
    """The release asset name of the extras entry *key*: ``contract-bundles-<ver>.tar.gz`` and so on."""
    return f"{_EXTRA_PREFIXES[key]}-{_version(tag)}.tar.gz"


# --------------------------------------------------------------------------- #
# Native binaries: real headers, a few hundred bytes (#6948)
#
# A companion platform wheel states an OS floor in its tag, and the build reads that floor out
# of the binary the wheel carries. These builders give the tests a binary whose headers say
# exactly what the test needs, so no released build and no network are involved.
# --------------------------------------------------------------------------- #

_ELF_MAGIC = b"\x7fELF"
_ELF_DATA_LSB = 1
_ELF_VERSION = 1
_ELF_ET_EXEC = 2
_ELF_PT_LOAD = 1
_ELF_PT_DYNAMIC = 2
_ELF_DT_STRTAB = 5
_ELF_DT_STRSZ = 10
_ELF_DT_VERNEED = 0x6FFFFFFE
_ELF_DT_VERNEEDNUM = 0x6FFFFFFF
_ELF_PHDR_SIZE = 64
_ELF_PROGRAM_HEADER_SIZE = 56
#: A non-zero load address, so a reader must translate a virtual address to a file offset.
_ELF_VADDR_BASE = 0x400000
_MACHO_MAGIC_64 = 0xFEEDFACF
_MACHO_CPU_TYPE_ARM64 = 0x0100000C
_MACHO_CPU_SUBTYPE_ALL = 0
_MACHO_MH_EXECUTE = 2
_MACHO_LC_VERSION_MIN_MACOSX = 0x24
_MACHO_LC_BUILD_VERSION = 0x32
_MACHO_PLATFORM_MACOS = 1


def _elf_glibc_names(glibc: str | Iterable[str] | None) -> list[str]:
    """``"2_39"`` -> ``["GLIBC_2.39"]``; ``"2.2.5"`` is kept verbatim; ``None`` -> no version needs."""
    if glibc is None:
        return []
    values = [glibc] if isinstance(glibc, str) else list(glibc)
    return [value if value.startswith("GLIBC_") else "GLIBC_" + value.replace("_", ".") for value in values]


def elf64(*, glibc: str | Iterable[str] | None = "2_39", target: ServiceTarget = ServiceTarget.LINUX_X64, static: bool = False) -> bytes:
    """A minimal ELF64 little-endian executable for *target* whose version needs are *glibc*.

    *glibc* is one ``<major>_<minor>`` string or an iterable of them (emitted as ``GLIBC_<major>.<minor>``);
    ``None`` emits an empty version-need table, and *static* emits no ``PT_DYNAMIC`` at all.
    """
    names = _elf_glibc_names(glibc)
    machine = _ELF_MACHINE.get(target, 62)
    phnum = 1 if static else 2
    phdrs_offset = _ELF_PHDR_SIZE
    dynamic_offset = phdrs_offset + phnum * _ELF_PROGRAM_HEADER_SIZE
    dynamic_size = 0 if static else 16 * 5
    strtab = b"\x00libc.so.6\x00" + b"".join(name.encode() + b"\x00" for name in names)
    strtab_offset = dynamic_offset + dynamic_size
    verneed_offset = strtab_offset + len(strtab)
    verneed_size = (16 + 16 * len(names)) if names else 0
    total = verneed_offset + verneed_size

    out = bytearray(b"\x00" * total)
    out[0:4] = _ELF_MAGIC
    out[4] = 2  # ELFCLASS64
    out[5] = _ELF_DATA_LSB
    out[6] = _ELF_VERSION
    out[16:18] = _ELF_ET_EXEC.to_bytes(2, "little")
    out[18:20] = machine.to_bytes(2, "little")
    out[20:24] = _ELF_VERSION.to_bytes(4, "little")
    out[32:40] = phdrs_offset.to_bytes(8, "little")  # e_phoff
    out[52:54] = _ELF_PHDR_SIZE.to_bytes(2, "little")  # e_ehsize
    out[54:56] = _ELF_PROGRAM_HEADER_SIZE.to_bytes(2, "little")  # e_phentsize
    out[56:58] = phnum.to_bytes(2, "little")  # e_phnum

    def _program_header(index: int, p_type: int, p_offset: int, p_filesz: int) -> None:
        base = phdrs_offset + index * _ELF_PROGRAM_HEADER_SIZE
        out[base : base + 4] = p_type.to_bytes(4, "little")  # p_type
        out[base + 4 : base + 8] = (5 if p_type == _ELF_PT_LOAD else 4).to_bytes(4, "little")  # p_flags
        out[base + 8 : base + 16] = p_offset.to_bytes(8, "little")  # p_offset
        out[base + 16 : base + 24] = (_ELF_VADDR_BASE + p_offset).to_bytes(8, "little")  # p_vaddr
        out[base + 24 : base + 32] = (_ELF_VADDR_BASE + p_offset).to_bytes(8, "little")  # p_paddr
        out[base + 32 : base + 40] = p_filesz.to_bytes(8, "little")  # p_filesz
        out[base + 40 : base + 48] = p_filesz.to_bytes(8, "little")  # p_memsz
        out[base + 48 : base + 56] = (8 if p_type == _ELF_PT_DYNAMIC else 0x1000).to_bytes(8, "little")  # p_align

    _program_header(0, _ELF_PT_LOAD, 0, total)
    if not static:
        _program_header(1, _ELF_PT_DYNAMIC, dynamic_offset, dynamic_size)
        entries = [
            (_ELF_DT_STRTAB, _ELF_VADDR_BASE + strtab_offset),
            (_ELF_DT_STRSZ, len(strtab)),
            (_ELF_DT_VERNEED, _ELF_VADDR_BASE + verneed_offset),
            (_ELF_DT_VERNEEDNUM, 1 if names else 0),
            (0, 0),  # DT_NULL: the walk stops here whatever follows
        ]
        for index, (tag, value) in enumerate(entries):
            base = dynamic_offset + index * 16
            out[base : base + 8] = tag.to_bytes(8, "little")
            out[base + 8 : base + 16] = value.to_bytes(8, "little")
    out[strtab_offset : strtab_offset + len(strtab)] = strtab
    if names:
        name_index = len(b"\x00libc.so.6\x00")
        out[verneed_offset : verneed_offset + 2] = _ELF_VERSION.to_bytes(2, "little")  # vn_version
        out[verneed_offset + 2 : verneed_offset + 4] = len(names).to_bytes(2, "little")  # vn_cnt
        out[verneed_offset + 4 : verneed_offset + 8] = (1).to_bytes(4, "little")  # vn_file: "libc.so.6"
        out[verneed_offset + 8 : verneed_offset + 12] = (16).to_bytes(4, "little")  # vn_aux
        for index, name in enumerate(names):
            aux = verneed_offset + 16 + index * 16
            out[aux + 8 : aux + 12] = name_index.to_bytes(4, "little")  # vna_name
            out[aux + 12 : aux + 16] = (0 if index == len(names) - 1 else 16).to_bytes(4, "little")  # vna_next
            name_index += len(name.encode()) + 1
    return bytes(out)


def macho64(*, minos: str = "11_0", minimum: str | None = None, platform: int = _MACHO_PLATFORM_MACOS) -> bytes:
    """A thin 64-bit arm64 Mach-O executable whose ``LC_BUILD_VERSION`` says ``minos``.

    *minimum* adds the deprecated ``LC_VERSION_MIN_MACOSX`` command with that version, for the
    fallback read path; *platform* overrides the ``LC_BUILD_VERSION`` platform id.
    """
    commands: list[bytes] = []
    commands.append(
        _MACHO_LC_BUILD_VERSION.to_bytes(4, "little")
        + (24).to_bytes(4, "little")  # cmdsize
        + platform.to_bytes(4, "little")
        + _macho_version(minos).to_bytes(4, "little")  # minos
        + _macho_version(minos).to_bytes(4, "little")  # sdk
        + (0).to_bytes(4, "little")  # ntools
    )
    if minimum is not None:
        commands.append(
            _MACHO_LC_VERSION_MIN_MACOSX.to_bytes(4, "little")
            + (16).to_bytes(4, "little")  # cmdsize
            + _macho_version(minimum).to_bytes(4, "little")  # version
            + _macho_version(minimum).to_bytes(4, "little")  # sdk
        )
    body = b"".join(commands)
    out = bytearray(b"\x00" * (32 + len(body)))
    out[0:4] = _MACHO_MAGIC_64.to_bytes(4, "little")
    out[4:8] = _MACHO_CPU_TYPE_ARM64.to_bytes(4, "little")
    out[8:12] = _MACHO_CPU_SUBTYPE_ALL.to_bytes(4, "little")
    out[12:16] = _MACHO_MH_EXECUTE.to_bytes(4, "little")
    out[16:20] = len(commands).to_bytes(4, "little")  # ncmds
    out[20:24] = len(body).to_bytes(4, "little")  # sizeofcmds
    out[32:] = body
    return bytes(out)


def _macho_version(value: str) -> int:
    """``"11_0"`` -> the packed ``xxxx.yy.zz`` ``minos`` word."""
    parts = [int(part) for part in value.split("_")]
    major, minor, patch = (parts + [0, 0])[:3]
    return (major << 16) | (minor << 8) | patch


def pe64() -> bytes:
    """A minimal PE/COFF header: ``MZ``, the stub, and the ``PE\0\0`` signature (no floor is read from it)."""
    out = bytearray(b"\x00" * 0x80)
    out[0:2] = b"MZ"
    out[0x3C:0x40] = (0x40).to_bytes(4, "little")
    out[0x40:0x44] = b"PE\x00\x00"
    out[0x44:0x46] = (0x8664).to_bytes(2, "little")  # machine: x86-64
    return bytes(out)


def native_asset(target: ServiceTarget, **kwargs: object) -> bytes:
    """A native fixture binary for *target*: ELF for Linux, Mach-O for macOS, PE for Windows, a jar for jvm.

    *kwargs* are passed to the builder (``glibc=``, ``static=``, ``minos=``, ``minimum=``).
    """
    if target in _ELF_MACHINE:
        return elf64(target=target, **kwargs)  # type: ignore[arg-type]
    if target is ServiceTarget.MACOS_ARM64:
        return macho64(**kwargs)  # type: ignore[arg-type]
    if target is ServiceTarget.WINDOWS_X64:
        return pe64()
    return _JAR


#: Small stand-in contents: a native binary per target, opaque bytes for the jar.
DEFAULT_ASSETS: Mapping[ServiceTarget, bytes] = {
    ServiceTarget.LINUX_X64: native_asset(ServiceTarget.LINUX_X64),
    ServiceTarget.JVM: _JAR,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()  # noqa: TID251 - release-asset integrity digest (SHA256SUMS format), not the charter freshness hash


def _digest(data: bytes, corrupted: bool) -> str:
    digest = _sha256(data)
    if not corrupted:
        return digest
    # Flip the last hex digit: still digest-shaped, never the digest of *data*.
    return digest[:-1] + ("0" if digest[-1] != "0" else "1")


def build_release(
    root: Path,
    *,
    service: str = "write-service",
    tag: str = "service-v0.1.0",
    assets: Mapping[ServiceTarget, bytes] | None = None,
    extras: Mapping[str, bytes] | None = None,
    corrupt: frozenset[str] | set[str] = frozenset(),
    prefix: str | None = None,
) -> tuple[ServicePin, Path]:
    """Write a release under ``root/<tag>/`` and return ``(pin, release_dir)``.

    *assets* maps each target to its bytes (default :data:`DEFAULT_ASSETS`);
    *extras* maps an extras key to its bytes. A ``SHA256SUMS`` file in
    ``sha256sum`` format lists the true digest of every file. An entry of
    *corrupt* (an asset name, a target value or an extras key) gets a pinned
    digest that does not match its bytes. *prefix* overrides the service's asset prefix.
    A second service can be added to the same release by calling again with the same *root* and *tag*
    (its lines are appended to ``SHA256SUMS``).
    """
    release_dir = Path(root) / tag
    release_dir.mkdir(parents=True, exist_ok=True)
    sums: list[str] = []

    def _write(key: str, name: str, data: bytes) -> ServiceAsset:
        (release_dir / name).write_bytes(data)
        sums.append(f"{_sha256(data)}  {name}")
        return ServiceAsset(name=name, sha256=_digest(data, key in corrupt or name in corrupt))

    pinned_assets = {
        target: _write(target.value, asset_name(service, tag, target, prefix=prefix), data)
        for target, data in (DEFAULT_ASSETS if assets is None else assets).items()
    }
    pinned_extras = {key: _write(key, extra_name(key, tag), data) for key, data in (extras or {}).items()}
    with (release_dir / SUMS_FILE).open("a", encoding="utf-8") as sums_file:
        sums_file.write("\n".join(sums) + "\n")
    pin = ServicePin(
        service=service,
        repository=Path(root).resolve().as_uri(),
        tag=tag,
        commit=FIXTURE_COMMIT,
        protocol_versions=(1,),
        requires_core=">=4.0.0rc8,<5",
        assets=pinned_assets,
        extras=pinned_extras,
    )
    return pin, release_dir
