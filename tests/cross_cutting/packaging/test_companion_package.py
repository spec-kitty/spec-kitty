"""The ``spec-kitty-services`` companion package: providers, wheel writer and in-tree backend (#6904, WP02).

The package lives in ``packages/spec-kitty-services/`` (outside ``src/``) and is not
installed in the test environment, so the tests put its project root on
``sys.path`` and load the backend by file path. Nothing here reaches the network.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import sys
import tarfile
import zipfile
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.fast

_REPO = Path(__file__).resolve().parents[3]
_PROJECT = _REPO / "packages" / "spec-kitty-services"
_BACKEND = _PROJECT / "_backend" / "spec_kitty_services_backend.py"
_SHA = "a" * 64
_ASSET = "command-cli-0.1.0-linux-x64"


@pytest.fixture
def companion(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    monkeypatch.syspath_prepend(str(_PROJECT))
    for name in [name for name in sys.modules if name == "spec_kitty_services" or name.startswith("spec_kitty_services.")]:
        monkeypatch.delitem(sys.modules, name)
    yield importlib.import_module("spec_kitty_services")


@pytest.fixture
def writer(companion: ModuleType) -> ModuleType:
    return importlib.import_module("spec_kitty_services.wheel")


@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    spec = importlib.util.spec_from_file_location("spec_kitty_services_backend", _BACKEND)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def _installed(
    tmp_path: Path,
    companion: ModuleType,
    writer: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    *,
    cli_version: str = "4.0.0rc8",
    installed_version: str | None = "4.0.0rc8",
    target: str | None = "linux-x64",
    host: str | None = "linux-x64",
    services: tuple[str, ...] = ("write-service",),
    write_binary: bool = True,
    pinned: str | None = _SHA,
) -> Path:
    """A stand-in installed package directory: manifest plus ``bin/`` (the provider's ``_package_dir`` seam)."""
    package = tmp_path / "site" / "spec_kitty_services"
    (package / "bin").mkdir(parents=True)
    binaries = [writer.BundledBinary(service=service, tag="service-v0.1.0", asset=f"{service}-{_ASSET}", sha256=_SHA) for service in services]
    (package / "_manifest.json").write_bytes(writer.manifest_bytes(cli_version, target, binaries))
    if write_binary:
        for binary in binaries:
            (package / "bin" / binary.asset).write_bytes(b"#!/bin/sh\n")
    monkeypatch.setattr(companion, "_package_dir", lambda: package)
    monkeypatch.setattr(companion, "_installed_cli_version", lambda: installed_version)
    monkeypatch.setattr(companion, "_host_target", lambda: host)
    monkeypatch.setattr(companion, "_pinned_sha256", lambda service, target: pinned)
    return package


# --------------------------------------------------------------------------- #
# Providers (FR-002, FR-003)
# --------------------------------------------------------------------------- #


def test_provider_offers_the_bundled_binary_built_for_this_cli_and_host(
    tmp_path: Path, companion: ModuleType, writer: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _installed(tmp_path, companion, writer, monkeypatch)
    assert companion.write_service() == str(package / "bin" / f"write-service-{_ASSET}")


def test_provider_offers_nothing_on_a_cli_version_skew(tmp_path: Path, companion: ModuleType, writer: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    _installed(tmp_path, companion, writer, monkeypatch, installed_version="4.0.0rc9")
    assert companion.write_service() is None


def test_provider_offers_nothing_without_an_installed_cli(tmp_path: Path, companion: ModuleType, writer: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    _installed(tmp_path, companion, writer, monkeypatch, installed_version=None)
    assert companion.write_service() is None


@pytest.mark.parametrize(
    ("host", "pinned"),
    [("linux-arm64", _SHA), (None, _SHA), ("linux-x64", "b" * 64), ("linux-x64", None)],
    ids=["other-host", "unknown-host", "digest-differs-from-the-cli-pin", "cli-pins-no-build"],
)
def test_provider_offers_nothing_on_another_host_or_an_unpinned_build(
    tmp_path: Path, companion: ModuleType, writer: ModuleType, monkeypatch: pytest.MonkeyPatch, host: str | None, pinned: str | None
) -> None:
    _installed(tmp_path, companion, writer, monkeypatch, host=host, pinned=pinned)
    assert companion.write_service() is None


def test_provider_offers_nothing_for_a_service_it_does_not_carry(
    tmp_path: Path, companion: ModuleType, writer: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _installed(tmp_path, companion, writer, monkeypatch, services=("write-service",))
    assert companion.charter_service() is None
    assert companion.write_service() == str(package / "bin" / f"write-service-{_ASSET}")  # positive control, same fixture


def test_provider_offers_nothing_for_a_symlinked_binary(tmp_path: Path, companion: ModuleType, writer: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    package = _installed(tmp_path, companion, writer, monkeypatch, write_binary=False)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_bytes(b"#!/bin/sh\n")
    (package / "bin" / f"write-service-{_ASSET}").symlink_to(elsewhere)
    assert companion.write_service() is None


def test_provider_offers_nothing_when_the_binary_is_missing(tmp_path: Path, companion: ModuleType, writer: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    _installed(tmp_path, companion, writer, monkeypatch, write_binary=False)
    assert companion.write_service() is None


def test_fallback_manifest_offers_nothing(tmp_path: Path, companion: ModuleType, writer: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    _installed(tmp_path, companion, writer, monkeypatch, target=None, services=())
    assert companion.write_service() is None
    assert companion.charter_service() is None


def test_source_tree_without_a_manifest_offers_nothing(companion: ModuleType) -> None:
    assert not (_PROJECT / "spec_kitty_services" / "_manifest.json").exists()
    assert companion.write_service() is None


@pytest.mark.parametrize("payload", [b"{not json", b'{"schema": 2}', b"\xff\xfe"])
def test_provider_never_raises_on_a_corrupt_manifest(
    tmp_path: Path, companion: ModuleType, writer: ModuleType, monkeypatch: pytest.MonkeyPatch, payload: bytes
) -> None:
    package = _installed(tmp_path, companion, writer, monkeypatch)
    (package / "_manifest.json").write_bytes(payload)
    assert companion.write_service() is None


def test_provider_never_raises_when_the_host_lookup_fails(tmp_path: Path, companion: ModuleType, writer: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    _installed(tmp_path, companion, writer, monkeypatch)

    def _broken() -> str:
        raise ImportError("no kernel")

    monkeypatch.setattr(companion, "_host_target", _broken)
    assert companion.write_service() is None


def test_real_host_lookup_uses_the_kernel_authority(companion: ModuleType) -> None:
    from kernel.service_hosts import host_target

    expected = host_target()
    assert companion._host_target() == (None if expected is None else expected.value)


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #


def test_manifest_round_trips_and_is_canonical(writer: ModuleType) -> None:
    binaries = [
        writer.BundledBinary(service="write-service", tag="service-v0.1.0", asset="w", sha256=_SHA),
        writer.BundledBinary(service="charter-service", tag="service-v0.2.0", asset="c", sha256="b" * 64),
    ]
    data = writer.manifest_bytes("4.0.0rc8", "linux-x64", binaries)
    assert data == writer.manifest_bytes("4.0.0rc8", "linux-x64", list(reversed(binaries)))
    manifest = writer.parse_manifest(data)
    assert manifest.cli_version == "4.0.0rc8"
    assert manifest.target == "linux-x64"
    assert [binary.service for binary in manifest.binaries] == ["charter-service", "write-service"]


@pytest.mark.parametrize(
    "document",
    [
        {"schema": 1, "cli_version": "1", "target": "linux-x64", "services": [{"service": "read-service", "tag": "service-v1", "asset": "a", "sha256": _SHA}]},
        {"schema": 1, "cli_version": "1", "target": "solaris", "services": []},
        {"schema": 1, "cli_version": "1", "target": None, "services": [{"service": "write-service", "tag": "service-v1", "asset": "a", "sha256": _SHA}]},
        {"schema": 1, "cli_version": "1", "target": "linux-x64", "services": [{"service": "write-service", "tag": "service-v1", "asset": "../a", "sha256": _SHA}]},
        {"schema": 1, "cli_version": "1", "target": "linux-x64", "services": [{"service": "write-service", "tag": "service-v1", "asset": "a", "sha256": "XYZ"}]},
        {"schema": 1, "cli_version": "1", "target": "linux-x64", "services": [], "extra": 1},
        {
            "schema": 1,
            "cli_version": "1",
            "target": "linux-x64",
            "services": [
                {"service": "write-service", "tag": "service-v1", "asset": "a", "sha256": _SHA},
                {"service": "write-service", "tag": "service-v1", "asset": "b", "sha256": _SHA},
            ],
        },
        {
            "schema": 1,
            "cli_version": "1",
            "target": "windows-x64",
            "services": [{"service": "write-service", "tag": "service-v1", "asset": "C:evil", "sha256": _SHA}],
        },
        {
            "schema": 1,
            "cli_version": "1",
            "target": "linux-x64",
            "services": [{"service": "write-service", "tag": "service-v1", "asset": ".hidden", "sha256": _SHA}],
        },
        {"schema": 1, "cli_version": "1", "target": "linux-x64", "services": [{"service": "write-service", "tag": "v1.0.0", "asset": "a", "sha256": _SHA}]},
    ],
)
def test_manifest_refuses_off_schema_documents(writer: ModuleType, document: dict[str, object]) -> None:
    with pytest.raises(writer.ManifestError):
        writer.parse_manifest(json.dumps(document).encode())


# --------------------------------------------------------------------------- #
# Wheel writer (FR-006, NFR-001)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("target", "floor", "tag"),
    [
        ("linux-x64", "2_39", "py3-none-manylinux_2_39_x86_64"),
        ("linux-arm64", "2_39", "py3-none-manylinux_2_39_aarch64"),
        ("linux-x64", "2_28", "py3-none-manylinux_2_28_x86_64"),
        ("macos-arm64", "2_39", "py3-none-macosx_11_0_arm64"),
        ("windows-x64", "2_39", "py3-none-win_amd64"),
    ],
)
def test_platform_tags(writer: ModuleType, target: str, floor: str, tag: str) -> None:
    assert writer.platform_tag(target, floor) == tag


def test_native_targets_match_the_kernel_targets(writer: ModuleType) -> None:
    from kernel.service_pin import ServiceTarget

    assert set(writer.NATIVE_TARGETS) == {target.value for target in ServiceTarget if target is not ServiceTarget.JVM}


@pytest.mark.parametrize(("target", "floor"), [("jvm", "2_39"), ("linux-x64", "2.39"), ("linux-x64", "")])
def test_platform_tag_refuses_unknown_input(writer: ModuleType, target: str, floor: str) -> None:
    with pytest.raises(ValueError, match="glibc floor|not a native service target"):
        writer.platform_tag(target, floor)


def _platform_wheel(writer: ModuleType, out: Path) -> Path:
    binary = writer.BundledBinary(service="write-service", tag="service-v0.1.0", asset=_ASSET, sha256=hashlib.sha256(b"#!/bin/sh\n").hexdigest())  # noqa: TID251 - asset digest fixture
    return writer.build_companion_wheel(out, project_root=_PROJECT, version="4.0.0rc8", target="linux-x64", binaries={binary: b"#!/bin/sh\n"})


def test_wheels_are_reproducible(tmp_path: Path, writer: ModuleType) -> None:
    first = _platform_wheel(writer, tmp_path / "a")
    second = _platform_wheel(writer, tmp_path / "b")
    assert first.name == "spec_kitty_services-4.0.0rc8-py3-none-manylinux_2_39_x86_64.whl"
    assert first.read_bytes() == second.read_bytes()


def test_wheel_record_wheel_and_entry_points(tmp_path: Path, writer: ModuleType) -> None:
    with zipfile.ZipFile(_platform_wheel(writer, tmp_path)) as archive:
        names = archive.namelist()
        dist_info = "spec_kitty_services-4.0.0rc8.dist-info"
        assert names[-1] == f"{dist_info}/RECORD"
        package, dist = [name for name in names if not name.startswith(dist_info)], [name for name in names if name.startswith(dist_info)]
        assert names == [*sorted(package), *sorted(dist[:-1]), dist[-1]]  # package first, dist-info last (PEP 427)
        assert {info.create_system for info in archive.infolist()} == {3}
        record = archive.read(f"{dist_info}/RECORD").decode().splitlines()
        assert record[-1] == f"{dist_info}/RECORD,,"
        for line in record[:-1]:
            name, digest, size = line.split(",")
            data = archive.read(name)
            expected = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()  # noqa: TID251 - wheel RECORD format check
            assert (digest, int(size)) == (f"sha256={expected}", len(data))
        assert {line.split(",")[0] for line in record[:-1]} == set(names) - {f"{dist_info}/RECORD"}
        wheel = archive.read(f"{dist_info}/WHEEL").decode()
        assert "Root-Is-Purelib: false" in wheel
        assert "Tag: py3-none-manylinux_2_39_x86_64" in wheel
        entry_points = archive.read(f"{dist_info}/entry_points.txt").decode()
        assert "[spec_kitty.service_binaries]" in entry_points
        assert "write-service = spec_kitty_services:write_service" in entry_points
        assert "charter-service = spec_kitty_services:charter_service" in entry_points
        binary = archive.getinfo(f"spec_kitty_services/bin/{_ASSET}")
        assert (binary.external_attr >> 16) & 0o777 == 0o755
        assert (archive.getinfo("spec_kitty_services/__init__.py").external_attr >> 16) & 0o777 == 0o644


def test_fallback_wheel_refuses_a_binary(tmp_path: Path, writer: ModuleType) -> None:
    binary = writer.BundledBinary(service="write-service", tag="service-v0.1.0", asset=_ASSET, sha256=_SHA)
    with pytest.raises(ValueError, match="fallback"):
        writer.build_companion_wheel(tmp_path, project_root=_PROJECT, version="1", target=None, binaries={binary: b"x"})


# --------------------------------------------------------------------------- #
# In-tree backend (FR-002, C-004)
# --------------------------------------------------------------------------- #


def test_backend_needs_no_build_dependency(backend: ModuleType) -> None:
    assert backend.get_requires_for_build_wheel() == []
    assert backend.get_requires_for_build_editable() == []
    assert backend.get_requires_for_build_sdist() == []


def test_backend_builds_the_binary_free_fallback_wheel(tmp_path: Path, backend: ModuleType, writer: ModuleType) -> None:
    name = backend.build_wheel(str(tmp_path))
    version = writer.project_version(_PROJECT)
    assert name == f"spec_kitty_services-{version}-py3-none-any.whl"
    with zipfile.ZipFile(tmp_path / name) as archive:
        assert not [member for member in archive.namelist() if "/bin/" in member]
        manifest = writer.parse_manifest(archive.read("spec_kitty_services/_manifest.json"))
        assert (manifest.cli_version, manifest.target, manifest.binaries) == (version, None, ())
        assert "Root-Is-Purelib: true" in archive.read(f"spec_kitty_services-{version}.dist-info/WHEEL").decode()


def test_backend_builds_an_editable_wheel_pointing_at_the_source(tmp_path: Path, backend: ModuleType) -> None:
    with zipfile.ZipFile(tmp_path / backend.build_editable(str(tmp_path))) as archive:
        assert archive.read("spec_kitty_services_editable.pth").decode().strip() == str(_PROJECT.resolve())


def test_backend_builds_a_reproducible_sdist(tmp_path: Path, backend: ModuleType) -> None:
    first = tmp_path / "a" / backend.build_sdist(str(tmp_path / "a"))
    second = tmp_path / "b" / backend.build_sdist(str(tmp_path / "b"))
    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first) as tar:
        names = {Path(name).relative_to(Path(name).parts[0]).as_posix() for name in tar.getnames()}
    assert {
        "PKG-INFO",
        "pyproject.toml",
        "README.md",
        "_backend/spec_kitty_services_backend.py",
        "spec_kitty_services/__init__.py",
        "spec_kitty_services/wheel.py",
    } <= names


def test_backend_fallback_wheel_installs_with_pip(tmp_path: Path, backend: ModuleType) -> None:
    """pip accepts the writer's RECORD and WHEEL: the fallback wheel installs offline."""
    import subprocess

    wheel = tmp_path / backend.build_wheel(str(tmp_path))
    site = tmp_path / "site"
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-deps", "--no-index", "--target", str(site), str(wheel)], check=True)
    assert (site / "spec_kitty_services" / "__init__.py").is_file()
    dist = next(importlib.metadata.distributions(path=[str(site)]))
    assert {entry.name for entry in dist.entry_points if entry.group == "spec_kitty.service_binaries"} == {"charter-service", "write-service"}


# --------------------------------------------------------------------------- #
# Pre-PR squad folds
# --------------------------------------------------------------------------- #


def test_companion_services_are_the_known_services_minus_the_read_service(writer: ModuleType) -> None:
    """One authority: the companion carries every service the CLI pins except the read service (ADR D-6)."""
    from kernel.service_pin import KNOWN_SERVICES

    assert set(writer.COMPANION_SERVICES) == set(KNOWN_SERVICES) - {"read-service"}


def test_the_project_entry_points_match_the_wheel_entry_points(writer: ModuleType) -> None:
    import tomllib

    declared = tomllib.loads((_PROJECT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["entry-points"]["spec_kitty.service_binaries"]
    written = dict(line.split(" = ") for line in writer._entry_points().decode().splitlines()[1:])
    assert declared == written
    assert set(declared) == set(writer.COMPANION_SERVICES)


def test_wheels_carry_the_readme_as_their_description(tmp_path: Path, writer: ModuleType) -> None:
    with zipfile.ZipFile(_platform_wheel(writer, tmp_path)) as archive:
        metadata = archive.read("spec_kitty_services-4.0.0rc8.dist-info/METADATA").decode()
    head, _, body = metadata.partition("\n\n")
    assert "Description-Content-Type: text/markdown" in head
    assert body == (_PROJECT / "README.md").read_text(encoding="utf-8")


def test_the_editable_wheel_refuses_a_path_with_a_line_break(tmp_path: Path, writer: ModuleType) -> None:
    hostile = tmp_path / "evil\nimport os"
    hostile.mkdir()
    with pytest.raises(ValueError, match="line break"):
        writer.build_editable_wheel(tmp_path / "out", project_root=hostile, version="1")
    assert writer.build_editable_wheel(tmp_path / "out", project_root=tmp_path, version="1").is_file()  # positive control
