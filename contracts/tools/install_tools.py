"""Download and unpack the pinned build toolchain after verifying its checksum (FR-018).

Reads ``contracts/tools/pins.json`` and installs every tool whose ``kind`` is
``archive`` (the Gradle distribution). A tool of another kind (a Gradle plugin,
resolved by Gradle under ``verification-metadata.xml``) is not installed here.
Nothing is unpacked and nothing is executed before the downloaded bytes match
the pinned sha256; the JDK is a SHA-pinned workflow action, not a download.

Codes (one stable code per cause), printed as
``CONTRACT-CHECK install_tools: <CODE>: <detail>`` with a last ``counts:`` line:

* ``CHECKSUM_MISMATCH``: the downloaded bytes do not match the pinned sha256.
* ``CHECKSUM_MISSING``: a tool carries no sha256 (never downloaded).
* ``NOT_HTTPS``: a tool url is not an ``https`` URL (never downloaded).
* ``UNSAFE_ARCHIVE``: an archive member would be written outside the destination.

Exit 0 pass, 1 violation, 2 cannot do its job: ``MANIFEST_EMPTY`` (unreadable,
or no installable tool listed) and ``DOWNLOAD_FAILED``.

Run as a bare script (``python contracts/tools/install_tools.py --pins FILE --dest DIR``).
When ``GITHUB_PATH`` is set, the ``bin`` directory of each installed tool is
appended to it so later workflow steps find the tool. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import stat
import sys
import urllib.request
import zipfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

CHECK_NAME = "install_tools"
INSTALLABLE_KIND = "archive"
DOWNLOAD_TIMEOUT_SECONDS = 300
UNIX_MODE_SHIFT = 16


def default_fetch(url: str) -> bytes:
    """Download ``url`` (already checked to be https) and return its bytes."""
    if not url.startswith("https://"):
        raise ValueError(f"refusing a non-https url: {url}")
    with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:  # noqa: S310 -- scheme checked to be https on the line above
        data: bytes = response.read()
    return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()  # noqa: TID251 -- file-integrity checksum of a downloaded archive, not the charter hash


def _violation(out: Callable[[str], None], code: str, detail: str) -> None:
    out(f"CONTRACT-CHECK {CHECK_NAME}: {code}: {detail}")


def _blocked(out: Callable[[str], None], code: str, detail: str, installed: int = 0) -> int:
    _violation(out, code, detail)
    out(f"counts: tools_installed={installed}")
    return 2


def _load_tools(pins: Path) -> list[dict[str, Any]] | None:
    try:
        manifest = json.loads(pins.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    tools = manifest.get("tools") if isinstance(manifest, dict) else None
    if not isinstance(tools, list):
        return None
    return [tool for tool in tools if isinstance(tool, dict) and tool.get("kind") == INSTALLABLE_KIND]


def _unpack(data: bytes, destination: Path) -> list[str] | str:
    """Unpack the zip ``data`` under ``destination``; return the top-level names, or the offending member name."""
    root = destination.resolve()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        for member in members:
            target = (root / member.filename).resolve()
            if root != target and root not in target.parents:
                return member.filename
        destination.mkdir(parents=True, exist_ok=True)
        for member in members:
            target = root / member.filename
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))
            mode = (member.external_attr >> UNIX_MODE_SHIFT) & 0o777
            if mode & stat.S_IXUSR:
                target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return sorted({member.filename.split("/")[0] for member in members})


def run(argv: Sequence[str] | None = None, *, fetch: Callable[[str], bytes] = default_fetch, out: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description="Install the pinned contracts toolchain.")
    parser.add_argument("--pins", default="contracts/tools/pins.json", type=Path)
    parser.add_argument("--dest", required=True, type=Path)
    args = parser.parse_args(argv)

    tools = _load_tools(args.pins)
    if not tools:
        return _blocked(out, "MANIFEST_EMPTY", f"{args.pins} is unreadable or lists no installable tool")

    # Every static check runs before the first download, so a bad manifest executes nothing.
    problems = 0
    for tool in tools:
        name = str(tool.get("name", "?"))
        if not tool.get("sha256"):
            _violation(out, "CHECKSUM_MISSING", f"{name} has no sha256")
            problems += 1
        if not str(tool.get("url", "")).startswith("https://"):
            _violation(out, "NOT_HTTPS", f"{name} url is not https: {tool.get('url')!r}")
            problems += 1
    if problems:
        out("counts: tools_installed=0")
        return 1

    installed = 0
    path_additions: list[Path] = []
    for tool in tools:
        name, url = str(tool["name"]), str(tool["url"])
        try:
            data = fetch(url)
        except (OSError, ValueError) as error:
            return _blocked(out, "DOWNLOAD_FAILED", f"{name}: {error}", installed)
        digest = _sha256(data)
        if digest != str(tool["sha256"]).lower():
            _violation(out, "CHECKSUM_MISMATCH", f"{name}: pinned {tool['sha256']} but downloaded {digest}")
            out(f"counts: tools_installed={installed}")
            return 1
        unpacked = _unpack(data, args.dest)
        if isinstance(unpacked, str):
            _violation(out, "UNSAFE_ARCHIVE", f"{name}: member {unpacked!r} would be written outside {args.dest}")
            out(f"counts: tools_installed={installed}")
            return 1
        installed += 1
        out(f"installed {name} {tool.get('version', '')} sha256={digest}")
        path_additions.extend(args.dest / top / "bin" for top in unpacked if (args.dest / top / "bin").is_dir())

    github_path = os.environ.get("GITHUB_PATH")
    for directory in path_additions:
        out(f"bin directory: {directory.resolve()}")
        if github_path:
            with open(github_path, "a", encoding="utf-8") as handle:
                handle.write(f"{directory.resolve()}\n")
    out(f"counts: tools_installed={installed}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
