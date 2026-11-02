"""Cache the pinned Gradle distribution without ever trusting an unverified copy.

``install_tools.py`` of the pinned contract-tools extra downloads
``acceptance-jvm/tools/pins.json``'s Gradle archive and checks its sha256 before
unpacking. That download is paid by every acceptance-JVM nightly leg and every
nightly Sonar run. GitHub's cache can carry the unpacked distribution, but a
cache entry is only as trustworthy as its key: this helper verifies the restored
tree against a manifest written after a checksum-verified install, and
reinstalls from the canonical installer when anything does not match.

Only the *tool* lives under the cached path. Gradle's dependency cache is a
separate workflow path (``~/.gradle/caches/modules-2``); test results and build
outputs (``acceptance-jvm/build``) are never cached by this helper or the
workflows that use it.

Manifest (``.spec-kitty-install.json`` inside the distribution root): the pin's
archive sha256, the tool version, and a sha256 over the unpacked tree (relative
paths, file bytes, executable bits and symlink targets). A cache hit therefore
means the bytes on disk are the bytes the pinned archive produced, not merely
that some directory exists.

Exit codes: 0 a verified install or cache hit; the installer's code when it
fails; 2 when this helper cannot do its job (unreadable pins, missing installer,
no install directory after a successful installer).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence

__all__ = (
    "CacheError",
    "GradlePin",
    "ensure_gradle",
    "load_gradle_pin",
    "main",
    "verify_cached_gradle",
)

CHECK_NAME = "gradle_cache"
MANIFEST_NAME = ".spec-kitty-install.json"
MANIFEST_VERSION = 1
_READ_CHUNK = 1024 * 1024


class CacheError(RuntimeError):
    """The helper cannot complete (not a verdict on the cached tree)."""


@dataclass(frozen=True)
class GradlePin:
    """The Gradle archive identity from ``pins.json``."""

    version: str
    archive_sha256: str


def _validate_sha256(value: str) -> str:
    normalised = value.lower()
    if len(normalised) != 64 or any(character not in "0123456789abcdef" for character in normalised):
        raise CacheError(f"gradle pin sha256 is not 64 lowercase hex characters: {value!r}")
    return normalised


def load_gradle_pin(pins_path: Path) -> GradlePin:
    """Read the ``gradle`` archive entry from ``pins.json``."""
    try:
        manifest = json.loads(pins_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise CacheError(f"cannot read Gradle pins {pins_path}: {error}") from error
    except ValueError as error:
        raise CacheError(f"Gradle pins {pins_path} are not valid JSON: {error}") from error
    tools = manifest.get("tools") if isinstance(manifest, Mapping) else None
    if not isinstance(tools, list):
        raise CacheError(f"Gradle pins {pins_path} carry no tools list")
    for tool in tools:
        if isinstance(tool, Mapping) and tool.get("name") == "gradle":
            version = tool.get("version")
            sha256 = tool.get("sha256")
            if not isinstance(version, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*(?:-[A-Za-z0-9][A-Za-z0-9.-]*)?", version):
                raise CacheError("the gradle pin carries no safe release version")
            if not isinstance(sha256, str):
                raise CacheError("the gradle pin carries no sha256")
            return GradlePin(version=version, archive_sha256=_validate_sha256(sha256))
    raise CacheError(f"Gradle pins {pins_path} carry no tool named 'gradle'")


def _tree_sha256(root: Path) -> str:
    """Digest the unpacked tree: paths, executable bits, file bytes and symlink targets."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST_NAME:
            continue
        if path.is_symlink():
            digest.update(f"L\0{relative}\0{os.readlink(path)}\0".encode())
        elif path.is_dir():
            digest.update(f"D\0{relative}\0".encode())
        elif path.is_file():
            executable = "x" if os.access(path, os.X_OK) else "-"
            digest.update(f"F\0{relative}\0{executable}\0".encode())
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(_READ_CHUNK), b""):
                    digest.update(chunk)
        else:
            digest.update(f"?\0{relative}\0".encode())
    return digest.hexdigest()


def _manifest_path(install_root: Path) -> Path:
    return install_root / MANIFEST_NAME


def _read_manifest(install_root: Path) -> dict[str, Any] | None:
    try:
        loaded = json.loads(_manifest_path(install_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _write_manifest(install_root: Path, pin: GradlePin, tree_sha256: str) -> None:
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "tool": "gradle",
        "version": pin.version,
        "archive_sha256": pin.archive_sha256,
        "tree_sha256": tree_sha256,
    }
    target = _manifest_path(install_root)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def _install_root(destination: Path, pin: GradlePin) -> Path:
    return destination / f"gradle-{pin.version}"


def verify_cached_gradle(destination: Path, pin: GradlePin) -> tuple[bool, str]:
    """Return ``(verified, reason)`` for the distribution under ``destination``."""
    install_root = _install_root(destination, pin)
    gradle_binary = install_root / "bin" / "gradle"
    if install_root.is_symlink():
        return False, "the cached distribution root is a symlink"
    if not gradle_binary.is_file():
        return False, f"no installed gradle binary at {gradle_binary}"
    manifest = _read_manifest(install_root)
    if manifest is None:
        return False, "the cached distribution has no readable install manifest"
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        return False, f"cached manifest version is {manifest.get('manifest_version')!r}, expected {MANIFEST_VERSION}"
    if manifest.get("tool") != "gradle" or manifest.get("version") != pin.version:
        return False, "the cached distribution is for another tool or version"
    if manifest.get("archive_sha256") != pin.archive_sha256:
        return False, "the cache manifest names another pinned archive sha256"
    actual = _tree_sha256(install_root)
    if actual != manifest.get("tree_sha256"):
        return False, "the cached distribution tree does not match its install manifest"
    return True, "cached Gradle distribution matches the pin and its install manifest"


def _publish_on_path(install_root: Path) -> str | None:
    """Append the distribution's ``bin`` to ``GITHUB_PATH``; return the path used."""
    bin_dir = install_root / "bin"
    github_path = os.environ.get("GITHUB_PATH")
    if github_path:
        with open(github_path, "a", encoding="utf-8") as handle:
            handle.write(f"{bin_dir}\n")
    return str(bin_dir)


def _run_installer(installer: Path, pins_path: Path, destination: Path) -> int:
    if not installer.is_file():
        raise CacheError(f"the canonical installer is missing: {installer}")
    completed = subprocess.run(  # noqa: S603 - fixed argv from checked paths, never a shell
        [sys.executable, str(installer), "--pins", str(pins_path), "--dest", str(destination), "--only", "gradle"],
        check=False,
    )
    return completed.returncode


def ensure_gradle(*, pins_path: Path, destination: Path, installer: Path) -> int:
    """Use a verified cached Gradle distribution, or install it from the pinned archive."""
    pin = load_gradle_pin(pins_path)
    destination.mkdir(parents=True, exist_ok=True)
    install_root = _install_root(destination, pin)

    verified, reason = verify_cached_gradle(destination, pin)
    if verified:
        bin_dir = _publish_on_path(install_root)
        print(f"CONTRACT-CHECK {CHECK_NAME}: CACHE_VERIFIED: gradle {pin.version} at {install_root} ({reason}); PATH+={bin_dir}")
        return 0

    if install_root.exists() or install_root.is_symlink():
        print(f"::warning::{CHECK_NAME}: cached gradle {pin.version} rejected ({reason}); reinstalling from the pinned, checksum-verified archive")
        if install_root.is_symlink() or install_root.is_file():
            install_root.unlink()
        else:
            shutil.rmtree(install_root)

    print(f"CONTRACT-CHECK {CHECK_NAME}: INSTALLING: gradle {pin.version} via {installer}")
    code = _run_installer(installer, pins_path, destination)
    if code != 0:
        print(f"::error::{CHECK_NAME}: the pinned Gradle installer exited {code}", file=sys.stderr)
        return code

    if not (install_root / "bin" / "gradle").is_file():
        raise CacheError(f"the installer succeeded but {install_root / 'bin' / 'gradle'} is missing")

    tree_sha256 = _tree_sha256(install_root)
    _write_manifest(install_root, pin, tree_sha256)
    bin_dir = _publish_on_path(install_root)
    print(f"CONTRACT-CHECK {CHECK_NAME}: INSTALLED: gradle {pin.version} at {install_root} (archive {pin.archive_sha256}, tree {tree_sha256}); PATH+={bin_dir}")
    return 0


def _ensure_command(args: argparse.Namespace) -> int:
    return ensure_gradle(
        pins_path=Path(args.pins),
        destination=Path(args.dest),
        installer=Path(args.installer),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cache and verify the pinned Gradle distribution.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ensure_parser = subparsers.add_parser("ensure", help="verify the cached tool or install it from the pin")
    ensure_parser.add_argument("--pins", required=True, help="acceptance-jvm/tools/pins.json")
    ensure_parser.add_argument("--dest", required=True, help="install destination (the cached tools directory)")
    ensure_parser.add_argument("--installer", required=True, help="the canonical install_tools.py to run on a miss")
    ensure_parser.set_defaults(handler=_ensure_command)
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except CacheError as error:
        print(f"::error::{CHECK_NAME}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    raise SystemExit(main())
