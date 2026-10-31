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
from collections.abc import Mapping
from pathlib import Path

from kernel.service_pin import DEFAULT_ASSET_PREFIXES, PINS_DIR, ServiceAsset, ServicePin, ServiceTarget, pin_file

__all__ = ["ASSET_PREFIXES", "DEFAULT_ASSETS", "FIXTURE_COMMIT", "asset_name", "build_release", "extra_name", "pin_path"]

FIXTURE_COMMIT = "0123456789abcdef0123456789abcdef01234567"
SUMS_FILE = "SHA256SUMS"

#: Small stand-in contents: a shell script for the native build, opaque bytes for the jar.
DEFAULT_ASSETS: Mapping[ServiceTarget, bytes] = {
    ServiceTarget.LINUX_X64: b"#!/bin/sh\necho fake write service\n",
    ServiceTarget.JVM: b"PK\x03\x04 fake jar\n",
}


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
