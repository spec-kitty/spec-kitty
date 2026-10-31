"""``specify_cli.services.resolution``: the binary resolution order and its refusals (#6590, WP03 T015).

Acceptance coverage for spec User Story 2 (fail closed, never run unverified
bytes) and User Story 5 (the developer opt-in). Releases are ``file://``
fixtures from ``tests.kernel.service_release_fixture``; the host target, the
Java probe and the install slot are monkeypatched, so nothing here depends on
the machine running the tests. ``SPEC_KITTY_SERVICE_UNPINNED`` is set only
inside the tests that exercise it.
"""

from __future__ import annotations

import dataclasses
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from kernel.service_artifacts import ASSET_DIR_ENV, cached_path
from kernel.service_pin import ServicePin, ServiceTarget, write_service_pin
from specify_cli.core.errors import StructuredError
from specify_cli.services import resolution
from specify_cli.services.errors import ServiceRefusal, ServiceRefusalCode, remedy_for
from specify_cli.services.resolution import (
    INSTALLED_PINS_PACKAGE_DIR,
    UNPINNED_ENV,
    ResolvedBinary,
    binary_env_var,
    find_pin,
    resolve_binary,
    verify_before_exec,
)
from tests.kernel.service_release_fixture import asset_name, build_release, pin_path

pytestmark = pytest.mark.fast

SERVICE = "write-service"
EXPLICIT_ENV = "SPEC_KITTY_WRITE_SERVICE_BINARY"
JAVA = Path("/opt/jdk-25/bin/java")
_REAL_PROVIDERS = resolution._binary_providers
_REAL_SOURCE_CHECKOUT_ROOT = resolution.source_checkout_root
#: This test file's own source checkout (``tests/specify_cli/services/`` is three levels below it).
_THIS_CHECKOUT = Path(__file__).resolve().parents[3]


@dataclasses.dataclass
class Release:
    pin: ServicePin
    release_dir: Path
    repo_root: Path
    cache_root: Path

    def native(self) -> Path:
        return self.release_dir / asset_name(SERVICE, self.pin.tag, ServiceTarget.LINUX_X64)

    def jar(self) -> Path:
        return self.release_dir / asset_name(SERVICE, self.pin.tag, ServiceTarget.JVM)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in (ASSET_DIR_ENV, UNPINNED_ENV, EXPLICIT_ENV):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(resolution, "host_target", lambda: ServiceTarget.LINUX_X64)
    monkeypatch.setattr(resolution, "find_java", lambda **_: None)
    monkeypatch.setattr(resolution, "_binary_providers", lambda service: ())
    _no_spawn(monkeypatch)
    empty_package = tmp_path / "installed-package"
    empty_package.mkdir()
    monkeypatch.setattr(resolution, "_package_root", lambda: empty_package)
    # The CLI's own tree: a stand-in source checkout whose pins/ ``_release`` fills.
    monkeypatch.setattr(resolution, "source_checkout_root", lambda: tmp_path / "repo")


def _release(tmp_path: Path, *, corrupt: frozenset[str] = frozenset(), assets: Mapping[ServiceTarget, bytes] | None = None) -> Release:
    pin, release_dir = build_release(tmp_path / "release", corrupt=corrupt, assets=assets)
    repo_root = tmp_path / "repo"
    pin_path(repo_root, SERVICE).parent.mkdir(parents=True)
    write_service_pin(pin, pin_path(repo_root, SERVICE))
    return Release(pin, release_dir, repo_root, tmp_path / "cache")


def _resolve(release: Release, env: dict[str, str] | None = None, *, offline: bool = False) -> ResolvedBinary:
    return resolve_binary(SERVICE, env={} if env is None else env, offline=offline, cache_root=release.cache_root)


def _refusal(call: Callable[[], object]) -> ServiceRefusal:
    with pytest.raises(ServiceRefusal) as info:
        call()
    return info.value


_REAL_POPEN = subprocess.Popen


def _no_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test in this module proves resolution spawns nothing (autouse via ``_isolated``)."""

    def _fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("a process was spawned during resolution")

    monkeypatch.setattr(subprocess, "Popen", _fail)


@pytest.fixture
def allow_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Opt a test out of the autouse no-spawn guard (``@pytest.mark.usefixtures("allow_spawn")``)."""
    monkeypatch.setattr(subprocess, "Popen", _REAL_POPEN)


class _Entry:
    """A stand-in for an ``importlib.metadata.EntryPoint``: ``load()`` returns the provider."""

    def __init__(self, provider: Callable[[], object]) -> None:
        self._provider = provider

    def load(self) -> Callable[[], object]:
        return self._provider


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


def test_refusal_renders_message_remedy_and_code() -> None:
    refusal = ServiceRefusal(ServiceRefusalCode.UNHEALTHY, "the service did not become ready", remedy_for(ServiceRefusalCode.UNHEALTHY, gcd="/r/.git"))
    assert isinstance(refusal, StructuredError)
    assert refusal.error_code == "SERVICE_UNHEALTHY"
    assert str(refusal) == (
        "the service did not become ready\n"
        "Remedy: see /r/.git/spec-kitty-write-service/service.log; then `spec-kitty service stop` and retry\n"
        "Error code: SERVICE_UNHEALTHY."
    )
    assert refusal.to_dict() == {
        "error_code": "SERVICE_UNHEALTHY",
        "message": "the service did not become ready",
        "remedy": refusal.remedy,
    }


@pytest.mark.parametrize(
    ("code", "value"),
    [
        (ServiceRefusalCode.BINARY_MISSING, "SERVICE_BINARY_MISSING"),
        (ServiceRefusalCode.DIGEST_MISMATCH, "SERVICE_BINARY_DIGEST_MISMATCH"),
        (ServiceRefusalCode.UNSUPPORTED_PLATFORM, "SERVICE_UNSUPPORTED_PLATFORM"),
        (ServiceRefusalCode.UNHEALTHY, "SERVICE_UNHEALTHY"),
        (ServiceRefusalCode.VERSION_MISMATCH, "SERVICE_VERSION_MISMATCH"),
        (ServiceRefusalCode.PIN_INVALID, "SERVICE_PIN_INVALID"),
    ],
)
def test_refusal_codes_are_stable(code: ServiceRefusalCode, value: str) -> None:
    assert code.value == value


def test_every_code_has_a_remedy() -> None:
    fields = {"asset": "a", "path": "p", "targets": "t", "gcd": "g", "service": "s", "env_var": "E"}
    for code in ServiceRefusalCode:
        assert remedy_for(code, **fields)
    assert "re-run `spec-kitty service vendor`" in remedy_for(ServiceRefusalCode.PIN_INVALID, variant="malformed", **fields)


def test_binary_env_var_names() -> None:
    assert binary_env_var("write-service") == EXPLICIT_ENV
    assert binary_env_var("charter-service") == "SPEC_KITTY_CHARTER_SERVICE_BINARY"


# --------------------------------------------------------------------------- #
# Pin lookup
# --------------------------------------------------------------------------- #


def test_installed_pins_dir_constant() -> None:
    assert INSTALLED_PINS_PACKAGE_DIR == "_pins"


def test_find_pin_reads_the_cli_s_own_source_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    installed = tmp_path / "pkg"
    (installed / "_pins").mkdir(parents=True)
    (installed / "_pins" / "write-service.source.yaml").write_text("x", encoding="utf-8")
    monkeypatch.setattr(resolution, "_package_root", lambda: installed)
    assert find_pin(SERVICE) == pin_path(release.repo_root, SERVICE)


def test_find_pin_ignores_a_pin_planted_in_the_user_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``pins/`` under the user's project is never read: the CLI's own tree alone decides (F1)."""
    release = _release(tmp_path)
    consumer = tmp_path / "consumer"
    planted = pin_path(consumer, SERVICE)
    planted.parent.mkdir(parents=True)
    write_service_pin(release.pin, planted)
    # The obvious defeat attempt: the consumer claims to be spec-kitty itself.
    (consumer / "pyproject.toml").write_text('[project]\nname = "spec-kitty-cli"\n', encoding="utf-8")
    (consumer / "src" / "specify_cli").mkdir(parents=True)
    monkeypatch.chdir(consumer)
    monkeypatch.setattr(resolution, "source_checkout_root", lambda: None)  # a wheel install with no pin shipped
    assert find_pin(SERVICE) is None
    refusal = _refusal(lambda: resolve_binary(SERVICE, env={}, cache_root=release.cache_root))
    assert refusal.code is ServiceRefusalCode.PIN_INVALID
    assert not release.cache_root.exists()


def test_find_pin_ignores_the_user_project_with_the_real_lookup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unpatched lookup from inside a consumer project: its planted pin is still not the one found."""
    release = _release(tmp_path)
    consumer = tmp_path / "consumer"
    planted = pin_path(consumer, SERVICE)
    planted.parent.mkdir(parents=True)
    write_service_pin(release.pin, planted)
    monkeypatch.chdir(consumer)
    monkeypatch.setattr(resolution, "source_checkout_root", _REAL_SOURCE_CHECKOUT_ROOT)
    assert find_pin(SERVICE) != planted
    assert resolution.pins_dir() == _THIS_CHECKOUT / "pins"


def test_the_source_checkout_layout_finds_its_own_pins_dir() -> None:
    """Editable or source-checkout layout: ``src/specify_cli`` two levels below a spec-kitty pyproject."""
    assert _REAL_SOURCE_CHECKOUT_ROOT() == _THIS_CHECKOUT


def test_checkout_root_of_requires_a_spec_kitty_pyproject(tmp_path: Path) -> None:
    package_file = tmp_path / "tree" / "src" / "specify_cli" / "__init__.py"
    package_file.parent.mkdir(parents=True)
    package_file.write_text("", encoding="utf-8")
    assert resolution.checkout_root_of(package_file) is None  # no pyproject.toml: a wheel's site-packages
    pyproject = tmp_path / "tree" / "pyproject.toml"
    pyproject.write_text('[project]\nname = "someone-else"\n', encoding="utf-8")
    assert resolution.checkout_root_of(package_file) is None
    pyproject.write_text("not toml [", encoding="utf-8")
    assert resolution.checkout_root_of(package_file) is None
    pyproject.write_text('[project]\nname = "spec-kitty-cli"\n', encoding="utf-8")
    assert resolution.checkout_root_of(package_file) == tmp_path / "tree"


def test_checkout_root_of_refuses_a_wheel_installed_inside_a_spec_kitty_named_tree(tmp_path: Path) -> None:
    """A wheel put on ``pip install --target <proj>/deps`` inside a fork-named project is not a checkout."""
    tree = tmp_path / "proj"
    tree.mkdir()
    (tree / "pyproject.toml").write_text('[project]\nname = "spec-kitty-cli"\n', encoding="utf-8")
    package_file = tree / "deps" / "specify_cli" / "__init__.py"
    package_file.parent.mkdir(parents=True)
    package_file.write_text("", encoding="utf-8")
    assert resolution.checkout_root_of(package_file) is None


def test_find_pin_falls_back_to_the_installed_resource(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    installed = tmp_path / "pkg"
    (installed / "_pins").mkdir(parents=True)
    shipped = installed / "_pins" / "write-service.source.yaml"
    shipped.write_text("x", encoding="utf-8")
    monkeypatch.setattr(resolution, "_package_root", lambda: installed)
    monkeypatch.setattr(resolution, "source_checkout_root", lambda: None)
    assert find_pin(SERVICE) == shipped
    assert resolution.pins_dir() == installed / "_pins"


def test_find_pin_none_when_absent() -> None:
    assert find_pin(SERVICE) is None


def test_missing_pin_refuses_with_no_pin_yet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    refusal = _refusal(lambda: resolve_binary(SERVICE, env={}, cache_root=tmp_path / "cache"))
    assert refusal.code is ServiceRefusalCode.PIN_INVALID
    assert "has no pin for write-service yet" in refusal.remedy


def test_malformed_pin_refuses_with_vendor_remedy(tmp_path: Path) -> None:
    path = pin_path(tmp_path / "repo", SERVICE)
    path.parent.mkdir(parents=True)
    path.write_text("service: write-service\n", encoding="utf-8")
    refusal = _refusal(lambda: resolve_binary(SERVICE, env={}, cache_root=tmp_path / "cache"))
    assert refusal.code is ServiceRefusalCode.PIN_INVALID
    assert "spec-kitty service vendor" in refusal.remedy


def test_protocol_mismatch_refuses_before_any_fetch(tmp_path: Path) -> None:
    release = _release(tmp_path)
    write_service_pin(dataclasses.replace(release.pin, protocol_versions=(2,)), pin_path(release.repo_root, SERVICE))
    refusal = _refusal(lambda: _resolve(release))
    assert refusal.code is ServiceRefusalCode.VERSION_MISMATCH
    assert "spec-kitty service stop" in refusal.remedy
    assert not release.cache_root.exists()


# --------------------------------------------------------------------------- #
# Tiers
# --------------------------------------------------------------------------- #


def test_explicit_tier_with_native_digest(tmp_path: Path) -> None:
    release = _release(tmp_path)
    resolved = _resolve(release, {EXPLICIT_ENV: str(release.native())})
    assert resolved.source == "explicit"
    assert resolved.pinned is True
    assert resolved.warning is None
    # Runs the verified cache copy, never the supplied path (no swap window after verify).
    cached = cached_path(release.pin, release.pin.assets[ServiceTarget.LINUX_X64], release.cache_root)
    assert resolved.path == cached
    assert resolved.path.is_relative_to(release.cache_root)
    assert resolved.argv_prefix == (str(cached),)
    assert resolved.sha256 == release.pin.assets[ServiceTarget.LINUX_X64].sha256
    release.native().write_bytes(b"swapped after verify")
    verify_before_exec(resolved)  # the cached copy is untouched


def test_explicit_tier_follows_a_symlink_to_the_real_file(tmp_path: Path) -> None:
    release = _release(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(release.native())
    resolved = _resolve(release, {EXPLICIT_ENV: str(link)})
    assert resolved.source == "explicit"
    assert resolved.path.read_bytes() == release.native().read_bytes()


def test_explicit_tier_with_jar_digest_runs_under_java(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    monkeypatch.setattr(resolution, "find_java", lambda **_: JAVA)
    resolved = _resolve(release, {EXPLICIT_ENV: str(release.jar())})
    assert resolved.source == "explicit"
    cached = cached_path(release.pin, release.pin.assets[ServiceTarget.JVM], release.cache_root)
    assert resolved.argv_prefix == (str(JAVA), "-jar", str(cached))


def test_explicit_jar_without_java_refuses(tmp_path: Path) -> None:
    release = _release(tmp_path)
    refusal = _refusal(lambda: _resolve(release, {EXPLICIT_ENV: str(release.jar())}))
    assert refusal.code is ServiceRefusalCode.UNSUPPORTED_PLATFORM
    assert "Java 25" in refusal.remedy


def test_explicit_missing_file_refuses(tmp_path: Path) -> None:
    release = _release(tmp_path)
    refusal = _refusal(lambda: _resolve(release, {EXPLICIT_ENV: str(tmp_path / "nope")}))
    assert refusal.code is ServiceRefusalCode.BINARY_MISSING
    assert EXPLICIT_ENV in refusal.remedy


def test_install_tier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    monkeypatch.setattr(resolution, "_binary_providers", lambda service: (_Entry(lambda: str(release.native())),))
    resolved = _resolve(release)
    assert resolved.source == "install"
    assert resolved.pinned is True
    assert resolved.path.is_relative_to(release.cache_root)


def test_install_tier_reads_entry_points(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    monkeypatch.setattr(resolution, "_binary_providers", _REAL_PROVIDERS)
    seen: list[dict[str, str]] = []

    class _EntryPoint:
        def load(self) -> Callable[[], Path]:
            return release.native

    def _entry_points(**selection: str) -> list[_EntryPoint]:
        seen.append(selection)
        return [_EntryPoint()]

    monkeypatch.setattr(resolution, "entry_points", _entry_points)
    resolved = _resolve(release)
    assert resolved.source == "install"
    assert seen == [{"group": "spec_kitty.service_binaries", "name": SERVICE}]


def test_install_tier_provider_returning_none_falls_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    monkeypatch.setattr(resolution, "_binary_providers", lambda service: (_Entry(lambda: None),))
    assert _resolve(release).source == "cache"


def test_install_tier_digest_mismatch_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    wrong = tmp_path / "wrong"
    wrong.write_bytes(b"not the pinned build")
    monkeypatch.setattr(resolution, "_binary_providers", lambda service: (_Entry(lambda: wrong),))
    refusal = _refusal(lambda: _resolve(release))
    assert refusal.code is ServiceRefusalCode.DIGEST_MISMATCH


def test_install_tier_broken_provider_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)

    def _broken() -> Path:
        raise RuntimeError("secret-token-value")

    monkeypatch.setattr(resolution, "_binary_providers", lambda service: (_Entry(_broken),))
    refusal = _refusal(lambda: _resolve(release))
    assert refusal.code is ServiceRefusalCode.BINARY_MISSING
    assert "secret-token-value" not in str(refusal)


def test_cache_tier(tmp_path: Path) -> None:
    release = _release(tmp_path)
    resolved = _resolve(release)
    asset = release.pin.assets[ServiceTarget.LINUX_X64]
    assert resolved.source == "cache"
    assert resolved.path == cached_path(release.pin, asset, release.cache_root)
    assert resolved.argv_prefix == (str(resolved.path),)
    assert resolved.pinned is True


def test_jar_tier_on_an_unknown_host_with_java_25(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    monkeypatch.setattr(resolution, "host_target", lambda: None)
    monkeypatch.setattr(resolution, "find_java", lambda **_: JAVA)
    resolved = _resolve(release)
    jar = cached_path(release.pin, release.pin.assets[ServiceTarget.JVM], release.cache_root)
    assert resolved.source == "jar"
    assert resolved.argv_prefix == (str(JAVA), "-jar", str(jar))
    assert resolved.path == jar


def test_jar_tier_when_the_native_asset_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    asset_dir = tmp_path / "offline"
    asset_dir.mkdir()
    (asset_dir / release.jar().name).write_bytes(release.jar().read_bytes())
    monkeypatch.setattr(resolution, "find_java", lambda **_: JAVA)
    resolved = _resolve(release, {ASSET_DIR_ENV: str(asset_dir)}, offline=True)
    assert resolved.source == "jar"


def test_host_without_native_asset_uses_the_jar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    monkeypatch.setattr(resolution, "host_target", lambda: ServiceTarget.MACOS_ARM64)
    monkeypatch.setattr(resolution, "find_java", lambda **_: JAVA)
    assert _resolve(release).source == "jar"


# --------------------------------------------------------------------------- #
# US2 refusals
# --------------------------------------------------------------------------- #


def test_us2_offline_empty_cache_refuses_binary_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    refusal = _refusal(lambda: _resolve(release, offline=True))
    assert refusal.code is ServiceRefusalCode.BINARY_MISSING
    assert "spec-kitty service fetch" in refusal.remedy
    assert "SPEC_KITTY_SERVICE_ASSET_DIR" in refusal.remedy
    assert release.native().name in refusal.remedy


def test_us2_native_missing_and_no_java_refuses_binary_missing(tmp_path: Path) -> None:
    release = _release(tmp_path)
    refusal = _refusal(lambda: _resolve(release, offline=True))
    assert refusal.code is ServiceRefusalCode.BINARY_MISSING


def test_us2_jar_unavailable_refuses_binary_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    monkeypatch.setattr(resolution, "host_target", lambda: None)
    monkeypatch.setattr(resolution, "find_java", lambda **_: JAVA)
    refusal = _refusal(lambda: _resolve(release, offline=True))
    assert refusal.code is ServiceRefusalCode.BINARY_MISSING
    assert release.jar().name in refusal.remedy


def test_us2_corrupt_asset_refuses_and_runs_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path, corrupt=frozenset({ServiceTarget.LINUX_X64.value}))
    monkeypatch.setattr(resolution, "find_java", lambda **_: JAVA)
    refusal = _refusal(lambda: _resolve(release))
    assert refusal.code is ServiceRefusalCode.DIGEST_MISMATCH
    assert "spec-kitty service fetch" in refusal.remedy
    asset = release.pin.assets[ServiceTarget.LINUX_X64]
    assert not cached_path(release.pin, asset, release.cache_root).exists()


def test_us2_corrupt_jar_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path, corrupt=frozenset({ServiceTarget.JVM.value}))
    monkeypatch.setattr(resolution, "host_target", lambda: None)
    monkeypatch.setattr(resolution, "find_java", lambda **_: JAVA)
    assert _refusal(lambda: _resolve(release)).code is ServiceRefusalCode.DIGEST_MISMATCH


def test_us2_unknown_host_no_java_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    monkeypatch.setattr(resolution, "host_target", lambda: None)
    refusal = _refusal(lambda: _resolve(release))
    assert refusal.code is ServiceRefusalCode.UNSUPPORTED_PLATFORM
    assert "Java 25" in refusal.remedy
    assert "linux-x64" in refusal.remedy


def test_unknown_host_and_no_jar_pinned_refuses_unsupported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path, assets={ServiceTarget.LINUX_X64: b"#!/bin/sh\n"})
    monkeypatch.setattr(resolution, "host_target", lambda: None)
    monkeypatch.setattr(resolution, "find_java", lambda **_: JAVA)
    assert _refusal(lambda: _resolve(release)).code is ServiceRefusalCode.UNSUPPORTED_PLATFORM


# --------------------------------------------------------------------------- #
# US5: the developer opt-in
# --------------------------------------------------------------------------- #


def _foreign_build(tmp_path: Path) -> Path:
    build = tmp_path / "dev-build"
    build.write_bytes(b"#!/bin/sh\necho local build\n")
    return build


def test_us5_unmatched_explicit_path_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    refusal = _refusal(lambda: _resolve(release, {EXPLICIT_ENV: str(_foreign_build(tmp_path))}))
    assert refusal.code is ServiceRefusalCode.DIGEST_MISMATCH
    assert EXPLICIT_ENV in refusal.remedy


def test_us5_opt_in_with_explicit_path_runs_unpinned_with_a_warning(tmp_path: Path) -> None:
    release = _release(tmp_path)
    build = _foreign_build(tmp_path)
    resolved = _resolve(release, {EXPLICIT_ENV: str(build), UNPINNED_ENV: "1"})
    assert resolved.source == "unpinned"
    assert resolved.pinned is False
    assert resolved.argv_prefix == (str(build.resolve()),)
    assert resolved.warning == (
        f"Running an UNPINNED write-service binary at {build.resolve()} (SPEC_KITTY_SERVICE_UNPINNED=1). This build is not verified against the pin."
    )


def test_us5_opt_in_with_an_unreadable_path_refuses_as_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)

    def _unreadable(path: Path) -> str:
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(resolution, "sha256_file", _unreadable)
    refusal = _refusal(lambda: _resolve(release, {EXPLICIT_ENV: str(_foreign_build(tmp_path)), UNPINNED_ENV: "1"}))
    assert refusal.code is ServiceRefusalCode.BINARY_MISSING
    assert EXPLICIT_ENV in refusal.remedy


def test_us5_opt_in_with_a_matching_path_stays_pinned(tmp_path: Path) -> None:
    release = _release(tmp_path)
    resolved = _resolve(release, {EXPLICIT_ENV: str(release.native()), UNPINNED_ENV: "1"})
    assert resolved.source == "explicit"
    assert resolved.pinned is True


def test_us5_opt_in_without_explicit_path_changes_nothing(tmp_path: Path) -> None:
    release = _release(tmp_path)
    resolved = _resolve(release, {UNPINNED_ENV: "1"})
    assert resolved.source == "cache"
    assert resolved.pinned is True
    assert resolved.warning is None


@pytest.mark.parametrize("value", ["true", "yes", "0", "", " 1", "1 "])
def test_us5_any_value_other_than_1_is_ignored(tmp_path: Path, value: str) -> None:
    release = _release(tmp_path)
    refusal = _refusal(lambda: _resolve(release, {EXPLICIT_ENV: str(_foreign_build(tmp_path)), UNPINNED_ENV: value}))
    assert refusal.code is ServiceRefusalCode.DIGEST_MISMATCH


def test_resolve_reads_the_process_environment_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    monkeypatch.setenv(EXPLICIT_ENV, str(release.native()))
    resolved = resolve_binary(SERVICE, cache_root=release.cache_root)
    assert resolved.source == "explicit"


# --------------------------------------------------------------------------- #
# verify_before_exec
# --------------------------------------------------------------------------- #


def test_verify_before_exec_passes_an_untouched_binary(tmp_path: Path) -> None:
    release = _release(tmp_path)
    verify_before_exec(_resolve(release))


def test_verify_before_exec_catches_a_swap_after_resolve(tmp_path: Path) -> None:
    release = _release(tmp_path)
    resolved = _resolve(release)
    resolved.path.chmod(0o644)
    resolved.path.write_bytes(b"#!/bin/sh\necho swapped\n")
    refusal = _refusal(lambda: verify_before_exec(resolved))
    assert refusal.code is ServiceRefusalCode.DIGEST_MISMATCH
    assert str(resolved.path) in refusal.remedy


def test_verify_before_exec_catches_a_deleted_binary(tmp_path: Path) -> None:
    release = _release(tmp_path)
    resolved = _resolve(release)
    resolved.path.unlink()
    assert _refusal(lambda: verify_before_exec(resolved)).code is ServiceRefusalCode.DIGEST_MISMATCH


def test_verify_before_exec_skips_an_unpinned_binary(tmp_path: Path) -> None:
    release = _release(tmp_path)
    build = _foreign_build(tmp_path)
    resolved = _resolve(release, {EXPLICIT_ENV: str(build), UNPINNED_ENV: "1"})
    build.write_bytes(b"rebuilt")
    verify_before_exec(resolved)


def test_digest_remedy_names_the_default_cache_when_no_cache_root_is_given(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _release(tmp_path, corrupt=frozenset({ServiceTarget.LINUX_X64.value}))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    refusal = _refusal(lambda: resolve_binary(SERVICE, env={}))
    assert refusal.code is ServiceRefusalCode.DIGEST_MISMATCH
    assert str(tmp_path / "xdg") in refusal.remedy


# --------------------------------------------------------------------------- #
# Cycle 2: the guard itself, asset-dir and cache causes, env isolation, provider loading
# --------------------------------------------------------------------------- #


def test_the_no_spawn_guard_is_active() -> None:
    with pytest.raises(AssertionError, match="spawned"):
        subprocess.Popen(["true"])


@pytest.mark.usefixtures("allow_spawn")
def test_allow_spawn_restores_popen() -> None:
    assert subprocess.Popen is _REAL_POPEN


def _tampered_asset_dir(tmp_path: Path, release: Release) -> Path:
    asset_dir = tmp_path / "offline"
    asset_dir.mkdir()
    (asset_dir / release.native().name).write_bytes(b"#!/bin/sh\necho tampered\n")
    return asset_dir / release.native().name


def test_tampered_asset_dir_file_is_named_with_its_own_remedy(tmp_path: Path) -> None:
    release = _release(tmp_path)
    bad = _tampered_asset_dir(tmp_path, release)
    refusal = _refusal(lambda: _resolve(release, {ASSET_DIR_ENV: str(bad.parent)}, offline=True))
    cache_file = cached_path(release.pin, release.pin.assets[ServiceTarget.LINUX_X64], release.cache_root)
    assert refusal.code is ServiceRefusalCode.DIGEST_MISMATCH
    assert str(bad) in refusal.message
    assert str(bad) in refusal.remedy
    assert ASSET_DIR_ENV in refusal.remedy
    assert "SHA256SUMS" in refusal.remedy
    assert "spec-kitty service fetch" in refusal.remedy  # only as the alternative
    assert refusal.remedy.index(str(bad)) < refusal.remedy.index("spec-kitty service fetch")
    assert str(cache_file) not in refusal.remedy
    assert not cache_file.exists()


def test_corrupt_download_keeps_the_cache_remedy(tmp_path: Path) -> None:
    release = _release(tmp_path, corrupt=frozenset({ServiceTarget.LINUX_X64.value}))
    refusal = _refusal(lambda: _resolve(release))
    cache_file = cached_path(release.pin, release.pin.assets[ServiceTarget.LINUX_X64], release.cache_root)
    assert str(cache_file) in refusal.remedy
    assert "downloaded" in refusal.message


def test_unwritable_cache_keeps_the_cause_and_points_at_the_cache(tmp_path: Path) -> None:
    _release(tmp_path)
    blocked = tmp_path / "cache-is-a-file"
    blocked.write_text("not a directory", encoding="utf-8")
    refusal = _refusal(lambda: resolve_binary(SERVICE, env={}, cache_root=blocked))
    assert refusal.code is ServiceRefusalCode.BINARY_MISSING
    assert "is not writable" in refusal.message
    assert str(blocked) in refusal.message
    assert "XDG_CACHE_HOME" in refusal.remedy
    assert "permissions" in refusal.remedy
    assert ASSET_DIR_ENV not in refusal.remedy
    assert "spec-kitty service fetch" not in refusal.remedy


def test_offline_refusal_keeps_the_kernel_cause(tmp_path: Path) -> None:
    release = _release(tmp_path)
    refusal = _refusal(lambda: _resolve(release, offline=True))
    assert "offline mode forbids a download" in refusal.message


def test_injected_env_hides_the_process_asset_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    asset_dir = tmp_path / "offline"
    asset_dir.mkdir()
    (asset_dir / release.native().name).write_bytes(release.native().read_bytes())
    monkeypatch.setenv(ASSET_DIR_ENV, str(asset_dir))
    refusal = _refusal(lambda: _resolve(release, {}, offline=True))
    assert refusal.code is ServiceRefusalCode.BINARY_MISSING
    assert _resolve(release, {ASSET_DIR_ENV: str(asset_dir)}, offline=True).source == "cache"


def test_injected_env_reaches_find_java(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    monkeypatch.setenv("JAVA_HOME", str(tmp_path / "process-jdk"))
    seen: list[Mapping[str, str] | None] = []

    def _find_java(*, env: Mapping[str, str] | None = None) -> Path:
        seen.append(env)
        return JAVA

    monkeypatch.setattr(resolution, "host_target", lambda: None)
    monkeypatch.setattr(resolution, "find_java", _find_java)
    injected: dict[str, str] = {}
    assert _resolve(release, injected).source == "jar"
    assert seen
    assert all(env is injected for env in seen)


def test_install_provider_that_fails_to_load_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)

    class _Broken:
        def load(self) -> Callable[[], object]:
            raise ImportError("companion wheel is broken")

    monkeypatch.setattr(resolution, "_binary_providers", lambda service: (_Broken(),))
    refusal = _refusal(lambda: _resolve(release))
    assert refusal.code is ServiceRefusalCode.BINARY_MISSING
    assert "ImportError" in refusal.message


# --------------------------------------------------------------------------- #
# F9: remedies say only what is true, and the first cause wins
# --------------------------------------------------------------------------- #


def test_the_unsupported_refusal_never_mentions_a_jar_the_pin_lacks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path, assets={ServiceTarget.LINUX_X64: b"#!/bin/sh\n"})
    monkeypatch.setattr(resolution, "host_target", lambda: None)
    monkeypatch.setattr(resolution, "find_java", lambda **_: JAVA)
    refusal = _refusal(lambda: _resolve(release))
    assert refusal.code is ServiceRefusalCode.UNSUPPORTED_PLATFORM
    for text in (refusal.message, refusal.remedy):
        assert "jar" not in text.lower() and "java" not in text.lower(), text
    assert "linux-x64" in refusal.remedy


def test_the_unsupported_refusal_with_a_jar_names_java(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    monkeypatch.setattr(resolution, "host_target", lambda: None)
    refusal = _refusal(lambda: _resolve(release))
    assert "Java 25" in refusal.remedy


def _record_downloads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from kernel import service_artifacts

    urls: list[str] = []
    real = service_artifacts.download

    def recording(url: str, dest: Path, *, timeout: float = 60.0) -> None:
        urls.append(url)
        real(url, dest, timeout=timeout)

    monkeypatch.setattr(service_artifacts, "download", recording)
    return urls


def test_a_native_download_failure_is_raised_without_also_downloading_the_jar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release(tmp_path)
    release.native().unlink()  # the release (or the network) cannot serve the native build
    monkeypatch.setattr(resolution, "find_java", lambda **_: JAVA)
    urls = _record_downloads(monkeypatch)

    refusal = _refusal(lambda: _resolve(release))

    assert refusal.code is ServiceRefusalCode.BINARY_MISSING
    assert release.native().name in refusal.message
    assert [url.rsplit("/", 1)[1] for url in urls] == [release.native().name], "the jar was downloaded after the native build failed"


def test_a_cached_jar_still_stands_in_when_the_native_download_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from kernel.service_artifacts import fetch_asset

    release = _release(tmp_path)
    fetch_asset(release.pin, release.pin.assets[ServiceTarget.JVM], cache_root=release.cache_root)
    release.native().unlink()
    monkeypatch.setattr(resolution, "find_java", lambda **_: JAVA)
    urls = _record_downloads(monkeypatch)

    resolved = _resolve(release)

    assert resolved.source == "jar"
    assert [url.rsplit("/", 1)[1] for url in urls] == [release.native().name]


def test_a_full_disk_during_download_gets_the_cache_remedy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import errno
    import shutil as shutil_module

    from kernel import release_assets

    def no_space(source: object, sink: object, length: int = 0) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(release_assets.shutil, "copyfileobj", no_space)
    assert shutil_module.copyfileobj is no_space  # the module object is shared; monkeypatch restores it
    release = _release(tmp_path)

    refusal = _refusal(lambda: _resolve(release))

    assert refusal.code is ServiceRefusalCode.BINARY_MISSING
    assert "No space left on device" in refusal.message
    assert str(release.cache_root) in refusal.remedy
