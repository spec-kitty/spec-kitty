"""``scripts/build_services_wheel.py``: the companion wheels hold exactly the pinned assets (#6904, WP03).

Every release here is a ``file://`` fixture from ``tests/kernel/service_release_fixture``;
nothing reaches the network (NFR-002). The script is loaded by file path, the way
``tests/ci/test_sync_services.py`` loads its script.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import zipfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

from kernel.service_pin import ServiceTarget, write_service_pin
from specify_cli.services import resolution
from specify_cli.services.errors import ServiceRefusal, ServiceRefusalCode
from tests.kernel.service_release_fixture import asset_name, build_release, pin_path

pytestmark = pytest.mark.fast

_REPO = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO / "scripts" / "build_services_wheel.py"
_COMPANION = _REPO / "packages" / "spec-kitty-services"
_VERSION = "4.0.0rc8"
_TAG = "service-v0.1.0"
_NATIVE = (ServiceTarget.LINUX_X64, ServiceTarget.LINUX_ARM64, ServiceTarget.MACOS_ARM64, ServiceTarget.WINDOWS_X64)
_PLATFORM_TAGS = {
    "linux-x64": "manylinux_2_39_x86_64",
    "linux-arm64": "manylinux_2_39_aarch64",
    "macos-arm64": "macosx_11_0_arm64",
    "windows-x64": "win_amd64",
}


@pytest.fixture(scope="module")
def script() -> Iterator[ModuleType]:
    spec = importlib.util.spec_from_file_location("build_services_wheel", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
        yield module


def _assets(service: str, targets: tuple[ServiceTarget, ...] = _NATIVE) -> dict[ServiceTarget, bytes]:
    payload = {target: f"#!/bin/sh\necho {service} {target.value}\n".encode() for target in targets}
    payload[ServiceTarget.JVM] = f"PK fake {service} jar\n".encode()
    return payload


@dataclass
class Fixture:
    repo: Path
    cache: Path
    release: Path

    def asset(self, service: str, target: ServiceTarget) -> bytes:
        return (self.release / _TAG / asset_name(service, _TAG, target)).read_bytes()


def _repo(
    tmp_path: Path,
    *,
    services: Mapping[str, tuple[ServiceTarget, ...]] | None = None,
    corrupt: frozenset[str] = frozenset(),
) -> Fixture:
    """A fake checkout: the root ``pyproject.toml``, the real companion source, and pins for *services*."""
    repo = tmp_path / "repo"
    (repo / "pins").mkdir(parents=True)
    (repo / "pyproject.toml").write_text(f'[project]\nname = "spec-kitty-cli"\nversion = "{_VERSION}"\n', encoding="utf-8")
    shutil.copytree(_COMPANION, repo / "packages" / "spec-kitty-services", ignore=shutil.ignore_patterns("__pycache__"))
    release = tmp_path / "release"
    wanted = {"write-service": _NATIVE, "charter-service": _NATIVE} if services is None else services
    for service, targets in wanted.items():
        pin, _ = build_release(release, service=service, tag=_TAG, assets=_assets(service, targets), corrupt=corrupt)
        write_service_pin(pin, pin_path(repo, service))
    return Fixture(repo=repo, cache=tmp_path / "cache", release=release)


def _build(script: ModuleType, fixture: Fixture, out: Path, *extra: str) -> int:
    return int(script.main(["--out", str(out), *extra], repo_root=fixture.repo, cache_root=fixture.cache))


def _members(wheel: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(wheel) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _bin(members: Mapping[str, bytes]) -> dict[str, bytes]:
    return {name.removeprefix("spec_kitty_services/bin/"): data for name, data in members.items() if name.startswith("spec_kitty_services/bin/")}


# --------------------------------------------------------------------------- #
# Build (FR-004, FR-005, FR-006)
# --------------------------------------------------------------------------- #


def test_builds_four_platform_wheels_and_the_fallback(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    names = sorted(path.name for path in (tmp_path / "out").glob("*.whl"))
    expected = sorted(
        [f"spec_kitty_services-{_VERSION}-py3-none-any.whl", *(f"spec_kitty_services-{_VERSION}-py3-none-{tag}.whl" for tag in _PLATFORM_TAGS.values())]
    )
    assert names == expected


@pytest.mark.parametrize("target", _NATIVE, ids=lambda target: target.value)
def test_each_platform_wheel_holds_exactly_its_pinned_assets(tmp_path: Path, script: ModuleType, target: ServiceTarget) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    wheel = tmp_path / "out" / f"spec_kitty_services-{_VERSION}-py3-none-{_PLATFORM_TAGS[target.value]}.whl"
    expected = {asset_name(service, _TAG, target): fixture.asset(service, target) for service in ("charter-service", "write-service")}
    assert _bin(_members(wheel)) == expected  # byte-identical, no jar, no other target


def test_fallback_wheel_holds_no_binary(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    assert _bin(_members(tmp_path / "out" / f"spec_kitty_services-{_VERSION}-py3-none-any.whl")) == {}


def test_the_read_service_is_never_packed(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path, services={"read-service": _NATIVE, "write-service": _NATIVE})
    assert _build(script, fixture, tmp_path / "out") == 0
    for wheel in (tmp_path / "out").glob("*.whl"):
        assert not [name for name in _bin(_members(wheel)) if name.startswith("mission-status-api")]
    linux = _bin(_members(tmp_path / "out" / f"spec_kitty_services-{_VERSION}-py3-none-{_PLATFORM_TAGS['linux-x64']}.whl"))
    assert set(linux) == {asset_name("write-service", _TAG, ServiceTarget.LINUX_X64)}  # positive control, same fixture


def test_a_target_pinned_for_one_service_only_carries_that_service(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path, services={"write-service": _NATIVE, "charter-service": (ServiceTarget.LINUX_X64,)})
    assert _build(script, fixture, tmp_path / "out") == 0
    arm = _bin(_members(tmp_path / "out" / f"spec_kitty_services-{_VERSION}-py3-none-{_PLATFORM_TAGS['linux-arm64']}.whl"))
    x64 = _bin(_members(tmp_path / "out" / f"spec_kitty_services-{_VERSION}-py3-none-{_PLATFORM_TAGS['linux-x64']}.whl"))
    assert set(arm) == {asset_name("write-service", _TAG, ServiceTarget.LINUX_ARM64)}
    assert set(x64) == {asset_name(service, _TAG, ServiceTarget.LINUX_X64) for service in ("charter-service", "write-service")}


def test_a_target_no_service_pins_gets_no_platform_wheel(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path, services={"write-service": (ServiceTarget.LINUX_X64,)})
    assert _build(script, fixture, tmp_path / "out") == 0
    assert sorted(path.name for path in (tmp_path / "out").glob("*.whl")) == sorted(
        [f"spec_kitty_services-{_VERSION}-py3-none-any.whl", f"spec_kitty_services-{_VERSION}-py3-none-{_PLATFORM_TAGS['linux-x64']}.whl"]
    )


def test_no_pin_builds_only_the_fallback(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path, services={})
    assert _build(script, fixture, tmp_path / "out") == 0
    assert [path.name for path in (tmp_path / "out").glob("*.whl")] == [f"spec_kitty_services-{_VERSION}-py3-none-any.whl"]


def test_a_tampered_asset_fails_and_writes_no_wheel(tmp_path: Path, script: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = _repo(tmp_path, corrupt=frozenset({"linux-arm64"}))
    assert _build(script, fixture, tmp_path / "out") == 1
    assert "SERVICE_BINARY_DIGEST_MISMATCH" in capsys.readouterr().err
    assert not list((tmp_path / "out").glob("*.whl"))
    assert not [path for path in tmp_path.iterdir() if path.name.startswith(".companion-")]  # scratch cleaned up


def test_the_glibc_floor_is_a_build_input(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path, services={"write-service": (ServiceTarget.LINUX_X64,)})
    assert _build(script, fixture, tmp_path / "out", "--glibc-floor", "2_28") == 0
    assert (tmp_path / "out" / f"spec_kitty_services-{_VERSION}-py3-none-manylinux_2_28_x86_64.whl").is_file()


def test_builds_are_reproducible(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "a") == 0
    assert _build(script, fixture, tmp_path / "b") == 0
    for wheel in (tmp_path / "a").glob("*.whl"):
        assert wheel.read_bytes() == (tmp_path / "b" / wheel.name).read_bytes()


# --------------------------------------------------------------------------- #
# Size gate (FR-007)
# --------------------------------------------------------------------------- #


def test_a_wheel_above_the_cap_fails_the_build(tmp_path: Path, script: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out", "--max-mb", "0.0001", "--warn-mb", "0") == 1
    assert "COMPANION_SIZE_EXCEEDED" in capsys.readouterr().err
    assert not list((tmp_path / "out").glob("*.whl"))


def test_a_wheel_above_the_warning_line_warns_and_passes(tmp_path: Path, script: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out", "--warn-mb", "0.0001") == 0
    assert "warning:" in capsys.readouterr().err
    assert len(list((tmp_path / "out").glob("*.whl"))) == 5


def test_the_default_gate_is_95_and_60_mb(script: ModuleType) -> None:
    args = script._parser().parse_args(["--out", "x"])
    assert (args.max_mb, args.warn_mb) == (95.0, 60.0)


# --------------------------------------------------------------------------- #
# Verify (FR-010 companion half, NFR-003)
# --------------------------------------------------------------------------- #


def _verify(script: ModuleType, fixture: Fixture, wheels: Path) -> int:
    return int(script.main(["--verify", str(wheels)], repo_root=fixture.repo, cache_root=fixture.cache))


def _rewrite(wheel: Path, change: Mapping[str, bytes | None]) -> None:
    members = _members(wheel)
    for name, data in change.items():
        if data is None:
            members.pop(name, None)
        else:
            members[name] = data
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)


def test_verify_passes_on_the_built_wheels(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    assert _verify(script, fixture, tmp_path / "out") == 0


def _linux_wheel(out: Path) -> Path:
    return out / f"spec_kitty_services-{_VERSION}-py3-none-{_PLATFORM_TAGS['linux-x64']}.whl"


def test_verify_fails_on_a_swapped_binary(tmp_path: Path, script: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    name = f"spec_kitty_services/bin/{asset_name('write-service', _TAG, ServiceTarget.LINUX_X64)}"
    _rewrite(_linux_wheel(tmp_path / "out"), {name: b"#!/bin/sh\necho evil\n"})
    assert _verify(script, fixture, tmp_path / "out") == 1
    assert "COMPANION_VERIFY_FAILED" in capsys.readouterr().err


def test_verify_fails_on_an_added_binary(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    _rewrite(_linux_wheel(tmp_path / "out"), {"spec_kitty_services/bin/extra-tool": b"#!/bin/sh\n"})
    assert _verify(script, fixture, tmp_path / "out") == 1


def test_verify_fails_when_the_pins_moved(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    pin, _ = build_release(tmp_path / "release-2", service="write-service", tag="service-v0.2.0", assets=_assets("write-service"))
    write_service_pin(pin, pin_path(fixture.repo, "write-service"))
    assert _verify(script, fixture, tmp_path / "out") == 1


def test_verify_fails_without_the_fallback_wheel(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    (tmp_path / "out" / f"spec_kitty_services-{_VERSION}-py3-none-any.whl").unlink()
    assert _verify(script, fixture, tmp_path / "out") == 1


def test_verify_fails_on_a_missing_platform_wheel(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    _linux_wheel(tmp_path / "out").unlink()
    assert _verify(script, fixture, tmp_path / "out") == 1


def test_verify_fails_on_a_wheel_for_another_cli_version(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    (fixture.repo / "pyproject.toml").write_text('[project]\nname = "spec-kitty-cli"\nversion = "4.0.0rc9"\n', encoding="utf-8")
    assert _verify(script, fixture, tmp_path / "out") == 1


# --------------------------------------------------------------------------- #
# End to end: the CLI resolves a built companion (US1, US2, FR-011)
# --------------------------------------------------------------------------- #


@pytest.fixture
def installed(tmp_path: Path, script: ModuleType, monkeypatch: pytest.MonkeyPatch) -> tuple[Fixture, Path]:
    """The linux-x64 companion wheel extracted into a site directory, its provider registered in the slot."""
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    site = tmp_path / "site"
    with zipfile.ZipFile(_linux_wheel(tmp_path / "out")) as archive:
        archive.extractall(site)
    monkeypatch.syspath_prepend(str(site))
    for name in [name for name in sys.modules if name == "spec_kitty_services" or name.startswith("spec_kitty_services.")]:
        monkeypatch.delitem(sys.modules, name)
    import spec_kitty_services

    monkeypatch.setattr(spec_kitty_services, "_installed_cli_version", lambda: _VERSION)
    monkeypatch.setattr(spec_kitty_services, "_host_target", lambda: "linux-x64")

    class _Entry:
        def load(self) -> object:
            return spec_kitty_services.write_service

    monkeypatch.setattr(resolution, "_binary_providers", lambda service: (_Entry(),))
    monkeypatch.setattr(resolution, "host_target", lambda: ServiceTarget.LINUX_X64)
    monkeypatch.setattr(resolution, "find_java", lambda **_: None)
    monkeypatch.setattr(resolution, "source_checkout_root", lambda: fixture.repo)
    return fixture, site


def test_the_cli_resolves_the_companion_binary_offline(tmp_path: Path, installed: tuple[Fixture, Path]) -> None:
    fixture, _site = installed
    resolved = resolution.resolve_binary("write-service", env={}, offline=True, cache_root=tmp_path / "cli-cache")
    assert resolved.source == "install"
    assert resolved.pinned is True
    assert resolved.path.read_bytes() == fixture.asset("write-service", ServiceTarget.LINUX_X64)


def test_a_tampered_companion_binary_refuses(tmp_path: Path, installed: tuple[Fixture, Path]) -> None:
    _fixture, site = installed
    (site / "spec_kitty_services" / "bin" / asset_name("write-service", _TAG, ServiceTarget.LINUX_X64)).write_bytes(b"#!/bin/sh\necho evil\n")
    with pytest.raises(ServiceRefusal) as info:
        resolution.resolve_binary("write-service", env={}, offline=True, cache_root=tmp_path / "cli-cache")
    assert info.value.code is ServiceRefusalCode.DIGEST_MISMATCH


def test_a_companion_for_another_cli_version_falls_through(tmp_path: Path, installed: tuple[Fixture, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    import spec_kitty_services

    monkeypatch.setattr(spec_kitty_services, "_installed_cli_version", lambda: "4.0.0rc9")
    with pytest.raises(ServiceRefusal) as info:  # offline, empty cache: the fetch tier is what refuses, not the slot
        resolution.resolve_binary("write-service", env={}, offline=True, cache_root=tmp_path / "cli-cache")
    assert info.value.code is ServiceRefusalCode.BINARY_MISSING
    assert resolution.resolve_binary("write-service", env={}, cache_root=tmp_path / "cli-cache").source == "cache"  # the fetch serves it


# --------------------------------------------------------------------------- #
# Review cycle 1: tampering with a consistent RECORD, and the non-blocking findings
# --------------------------------------------------------------------------- #


def _rewrite_consistently(wheel: Path, change: Mapping[str, bytes | None], *, duplicate: str | None = None) -> None:
    """Rewrite *wheel* with *change* and a RECORD that agrees with it (an attacker's wheel, not a corrupt one)."""
    import base64
    import hashlib

    members = _members(wheel)
    for name, data in change.items():
        if data is None:
            members.pop(name, None)
        else:
            members[name] = data
    record_name = next(name for name in members if name.endswith(".dist-info/RECORD"))
    members.pop(record_name)
    lines = [
        f"{name},sha256={base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()},{len(data)}"  # noqa: TID251 - wheel RECORD format
        for name, data in members.items()
    ]
    members[record_name] = ("\n".join([*lines, f"{record_name},,"]) + "\n").encode()
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
        if duplicate is not None:
            archive.writestr(duplicate, b"shadow")


@pytest.mark.parametrize(
    "change",
    [
        {"evil.pth": b"import os\n"},
        {"spec_kitty_services/__init__.py": b"def write_service():\n    return '/srv/evil'\n"},
        {"spec_kitty_services/extra.py": b"print('extra')\n"},
    ],
    ids=["planted-pth", "replaced-provider", "extra-module"],
)
def test_verify_fails_on_any_other_change_even_with_a_consistent_record(tmp_path: Path, script: ModuleType, change: Mapping[str, bytes]) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    assert _verify(script, fixture, tmp_path / "out") == 0  # positive control, same wheels
    _rewrite_consistently(_linux_wheel(tmp_path / "out"), change)
    assert _verify(script, fixture, tmp_path / "out") == 1


def test_verify_fails_on_a_wheel_tag_that_contradicts_the_file_name(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    wheel = _linux_wheel(tmp_path / "out")
    dist_wheel = f"spec_kitty_services-{_VERSION}.dist-info/WHEEL"
    tampered = _members(wheel)[dist_wheel].replace(b"manylinux_2_39_x86_64", b"any")
    _rewrite_consistently(wheel, {dist_wheel: tampered})
    assert _verify(script, fixture, tmp_path / "out") == 1


def test_verify_fails_on_a_duplicate_member(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    _rewrite_consistently(_linux_wheel(tmp_path / "out"), {}, duplicate="spec_kitty_services/__init__.py")
    assert _verify(script, fixture, tmp_path / "out") == 1


def test_verify_reports_a_non_zip_with_a_stable_code(tmp_path: Path, script: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    _linux_wheel(tmp_path / "out").write_bytes(b"not a zip")
    assert _verify(script, fixture, tmp_path / "out") == 1
    err = capsys.readouterr().err
    assert "COMPANION_VERIFY_FAILED" in err
    assert "Traceback" not in err


def test_build_refuses_an_out_directory_that_already_holds_wheels(tmp_path: Path, script: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = _repo(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / f"spec_kitty_services-{_VERSION}-py3-none-win_amd64.whl").write_bytes(b"stale")
    assert _build(script, fixture, tmp_path / "out") == 1
    assert "COMPANION_OUT_NOT_EMPTY" in capsys.readouterr().err


def test_a_bad_glibc_floor_fails_even_without_a_linux_target(tmp_path: Path, script: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = _repo(tmp_path, services={"write-service": (ServiceTarget.WINDOWS_X64,)})
    assert _build(script, fixture, tmp_path / "out", "--glibc-floor", "bad") == 1
    assert "COMPANION_BUILD_FAILED" in capsys.readouterr().err


def test_a_pinned_asset_name_the_manifest_refuses_fails_the_build(tmp_path: Path, script: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _repo(tmp_path, services={}).repo
    pin, _ = build_release(tmp_path / "odd-release", service="write-service", tag=_TAG, assets={ServiceTarget.WINDOWS_X64: b"MZ"}, prefix="C:evil")
    write_service_pin(pin, pin_path(repo, "write-service"))
    assert int(script.main(["--out", str(tmp_path / "out")], repo_root=repo, cache_root=tmp_path / "cache")) == 1
    assert "COMPANION_BUILD_FAILED" in capsys.readouterr().err
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").glob("*.whl"))


# --------------------------------------------------------------------------- #
# Pre-PR squad folds
# --------------------------------------------------------------------------- #


def test_verify_fails_on_a_writer_built_wheel_with_forged_binaries(tmp_path: Path, script: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    """The sha256 check stands on its own: a wheel the real writer built around forged bytes under the pinned manifest."""
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    writer = script.load_writer(fixture.repo)
    wheel = _linux_wheel(tmp_path / "out")
    manifest = writer.parse_manifest(_members(wheel)["spec_kitty_services/_manifest.json"])
    forged = dict.fromkeys(manifest.binaries, b"#!/bin/sh\necho forged\n")
    wheel.unlink()
    writer.build_companion_wheel(
        tmp_path / "out", project_root=fixture.repo / "packages" / "spec-kitty-services", version=_VERSION, target="linux-x64", binaries=forged
    )
    assert _verify(script, fixture, tmp_path / "out") == 1
    assert "does not match its pinned sha256" in capsys.readouterr().err


def test_verify_refuses_a_file_that_is_not_a_wheel(tmp_path: Path, script: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = _repo(tmp_path)
    assert _build(script, fixture, tmp_path / "out") == 0
    (tmp_path / "out" / "spec_kitty_services-4.0.0rc8.tar.gz").write_bytes(b"would be uploaded unverified")
    assert _verify(script, fixture, tmp_path / "out") == 1
    assert "not companion wheels" in capsys.readouterr().err


def test_a_wheel_exactly_at_the_cap_passes(tmp_path: Path, script: ModuleType) -> None:
    fixture = _repo(tmp_path, services={})
    assert _build(script, fixture, tmp_path / "probe") == 0
    size = next((tmp_path / "probe").glob("*.whl")).stat().st_size
    gate = script.SizeGate(max_bytes=size, warn_bytes=size)
    built = script.build(fixture.repo, tmp_path / "out", cache_root=fixture.cache, gate=gate, warn=lambda message: None)
    assert [path.stat().st_size for path in built] == [size]
    with pytest.raises(script.BuildError, match="COMPANION_SIZE_EXCEEDED"):  # one byte less fails
        script.build(fixture.repo, tmp_path / "out-2", cache_root=fixture.cache, gate=script.SizeGate(max_bytes=size - 1, warn_bytes=0), warn=lambda message: None)
