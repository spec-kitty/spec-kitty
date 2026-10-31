"""``kernel.service_hosts``: the host's release target and which pinned build runs on it (#6590, F5).

The one authority for the platform-to-target table and the "native build, else
the jar" rule; the sync script, ``service fetch`` and resolution all use it.
"""

from __future__ import annotations

import pytest

from kernel.service_hosts import HOST_TARGETS, SelectedBuild, host_target, select_build
from kernel.service_pin import ServiceAsset, ServicePin, ServiceTarget

pytestmark = pytest.mark.fast

_NATIVE = ServiceAsset(name="command-cli-0.1.0-linux-x64", sha256="a" * 64)
_JAR = ServiceAsset(name="command-cli-0.1.0.jar", sha256="b" * 64)


def _pin(assets: dict[ServiceTarget, ServiceAsset]) -> ServicePin:
    return ServicePin(
        service="write-service",
        repository="https://github.com/spec-kitty/spec-kitty-events",
        tag="service-v0.1.0",
        commit="0123456789abcdef0123456789abcdef01234567",
        protocol_versions=(1,),
        requires_core=">=4.0.0rc8,<5",
        assets=assets,
    )


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Linux", "x86_64", ServiceTarget.LINUX_X64),
        ("Linux", "AMD64", ServiceTarget.LINUX_X64),
        ("Linux", "aarch64", ServiceTarget.LINUX_ARM64),
        ("Linux", "arm64", ServiceTarget.LINUX_ARM64),
        ("Darwin", "arm64", ServiceTarget.MACOS_ARM64),
        ("Windows", "AMD64", ServiceTarget.WINDOWS_X64),
        ("Windows", "x86_64", ServiceTarget.WINDOWS_X64),
        ("Darwin", "x86_64", None),
        ("Linux", "riscv64", None),
        ("FreeBSD", "amd64", None),
        ("Windows", "arm64", None),
    ],
)
def test_host_target_maps_the_platform_pair(system: str, machine: str, expected: ServiceTarget | None) -> None:
    assert host_target(system=system, machine=machine) is expected


def test_host_target_defaults_to_the_running_platform() -> None:
    result = host_target()
    assert result is None or result in set(ServiceTarget) - {ServiceTarget.JVM}


def test_the_table_names_native_targets_only() -> None:
    assert ServiceTarget.JVM not in set(HOST_TARGETS.values())


def test_select_build_prefers_the_native_build() -> None:
    assert select_build(_pin({ServiceTarget.LINUX_X64: _NATIVE, ServiceTarget.JVM: _JAR}), ServiceTarget.LINUX_X64) == SelectedBuild(
        ServiceTarget.LINUX_X64, _NATIVE
    )


@pytest.mark.parametrize("host", [ServiceTarget.MACOS_ARM64, None])
def test_select_build_falls_back_to_the_jar(host: ServiceTarget | None) -> None:
    assert select_build(_pin({ServiceTarget.LINUX_X64: _NATIVE, ServiceTarget.JVM: _JAR}), host) == SelectedBuild(ServiceTarget.JVM, _JAR)


@pytest.mark.parametrize("host", [ServiceTarget.MACOS_ARM64, None])
def test_select_build_is_none_without_a_native_build_or_a_jar(host: ServiceTarget | None) -> None:
    assert select_build(_pin({ServiceTarget.LINUX_X64: _NATIVE}), host) is None
