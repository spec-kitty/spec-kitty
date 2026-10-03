"""Download and unpack the pinned build toolchain after verifying its checksum (FR-018).

Reads ``contracts/tools/pins.json`` and installs every tool whose ``kind`` is
``archive``: the Gradle distribution (a ``.zip`` holding ``<top>/bin/``) and the prebuilt
Go binaries vacuum and oasdiff (a ``.tar.gz`` holding the binary at its root, named by
the entry's ``binary`` field; it is unpacked into ``<dest>/<name>-<version>/``). A tool
of another kind (a Gradle plugin, resolved by Gradle under ``verification-metadata.xml``)
is not installed here. ``--only NAME`` (repeatable) installs just the named tools, so a
job downloads only what it runs. Nothing is unpacked and nothing is executed before the
downloaded bytes match the pinned sha256; the JDK is a SHA-pinned workflow action, not a
download.

Codes (one stable code per cause), printed as
``CONTRACT-CHECK install_tools: <CODE>: <detail>`` with a last ``counts:`` line:

* ``CHECKSUM_MISMATCH``: the downloaded bytes do not match the pinned sha256.
* ``CHECKSUM_MISSING``: a tool carries no sha256 (never downloaded).
* ``NOT_HTTPS``: a tool url is not an ``https`` URL (never downloaded).
* ``UNSAFE_ARCHIVE``: an archive member would be written outside the destination.
* ``UNSUPPORTED_INTERPRETER``: this Python's ``tarfile`` has no extraction filters (an environment
  problem, not a hostile archive); the ``.tar.gz`` is refused rather than extracted unfiltered.
* ``UNSUPPORTED_FORMAT``: the url is neither ``.zip`` nor ``.tar.gz`` (never downloaded).
* ``BINARY_MISSING``: a ``.tar.gz`` tool's declared ``binary`` is not in the archive.

Exit 0 pass, 1 violation, 2 cannot do its job: ``MANIFEST_EMPTY`` (unreadable,
or no installable tool listed), ``TOOL_UNKNOWN`` (an ``--only`` name is not an installable
tool) and ``DOWNLOAD_FAILED``.

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
import tarfile
import urllib.request
import zipfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

CHECK_NAME = "install_tools"
INSTALLABLE_KIND = "archive"
DOWNLOAD_TIMEOUT_SECONDS = 300
UNIX_MODE_SHIFT = 16
ZIP_SUFFIX = ".zip"
TARBALL_SUFFIX = ".tar.gz"


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


def _unpack_tarball(data: bytes, destination: Path, binary: str) -> str | None:
    """Unpack the tar.gz ``data`` into ``destination``. Returns an error code and text, or ``None``.

    The ``data`` filter refuses absolute names, ``..`` escapes and links that leave the destination.
    The filters were added in Python 3.12 and backported to the security releases of earlier versions, so the
    check is by feature detection, not by version: a ``tarfile`` without ``data_filter`` is refused with
    ``UNSUPPORTED_INTERPRETER`` rather than extracted unfiltered.
    """
    if not hasattr(tarfile, "data_filter"):
        return "UNSUPPORTED_INTERPRETER|tarfile extraction filters are missing in this Python; use a security release that has them"
    root = destination.resolve()
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                target = (root / member.name).resolve()
                if root != target and root not in target.parents:
                    return f"UNSAFE_ARCHIVE|member {member.name!r} would be written outside {destination}"
            destination.mkdir(parents=True, exist_ok=True)
            archive.extractall(destination, members=members, filter="data")
    except (tarfile.TarError, OSError) as error:
        return f"UNSAFE_ARCHIVE|the archive could not be unpacked safely: {error}"
    target_binary = root / binary
    if not target_binary.is_file():
        return f"BINARY_MISSING|{binary!r} is not at the root of the archive"
    target_binary.chmod(target_binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return None


def _format_of(url: str) -> str | None:
    path = url.split("?", 1)[0]
    if path.endswith(TARBALL_SUFFIX):
        return TARBALL_SUFFIX
    return ZIP_SUFFIX if path.endswith(ZIP_SUFFIX) else None


def _static_problems(tools: Sequence[dict[str, Any]], out: Callable[[str], None]) -> int:
    """Report every manifest problem that can be seen without downloading; return how many there are."""
    problems = 0
    for tool in tools:
        name = str(tool.get("name", "?"))
        if not tool.get("sha256"):
            _violation(out, "CHECKSUM_MISSING", f"{name} has no sha256")
            problems += 1
        if not str(tool.get("url", "")).startswith("https://"):
            _violation(out, "NOT_HTTPS", f"{name} url is not https: {tool.get('url')!r}")
            problems += 1
        elif _format_of(str(tool["url"])) is None:
            _violation(out, "UNSUPPORTED_FORMAT", f"{name} url is neither {ZIP_SUFFIX} nor {TARBALL_SUFFIX}: {tool.get('url')!r}")
            problems += 1
    return problems


def _unpack_tool(tool: dict[str, Any], data: bytes, dest: Path, out: Callable[[str], None]) -> list[Path] | None:
    """Unpack one verified download; return the directories for ``PATH``, or ``None`` after reporting a violation."""
    name = str(tool["name"])
    if _format_of(str(tool["url"])) == TARBALL_SUFFIX:
        tool_dir = dest / f"{name}-{tool.get('version', '')}"
        failure = _unpack_tarball(data, tool_dir, str(tool.get("binary", name)))
        if failure is not None:
            code, detail = failure.split("|", 1)
            _violation(out, code, f"{name}: {detail}")
            return None
        return [tool_dir]
    unpacked = _unpack(data, dest)
    if isinstance(unpacked, str):
        _violation(out, "UNSAFE_ARCHIVE", f"{name}: member {unpacked!r} would be written outside {dest}")
        return None
    return [dest / top / "bin" for top in unpacked if (dest / top / "bin").is_dir()]


def run(argv: Sequence[str] | None = None, *, fetch: Callable[[str], bytes] = default_fetch, out: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description="Install the pinned contracts toolchain.")
    parser.add_argument("--pins", default="contracts/tools/pins.json", type=Path)
    parser.add_argument("--dest", required=True, type=Path)
    parser.add_argument("--only", action="append", default=[], help="install just this tool (repeatable)")
    args = parser.parse_args(argv)

    tools = _load_tools(args.pins)
    if not tools:
        return _blocked(out, "MANIFEST_EMPTY", f"{args.pins} is unreadable or lists no installable tool")
    unknown = [name for name in args.only if name not in {str(tool.get("name")) for tool in tools}]
    if unknown:
        return _blocked(out, "TOOL_UNKNOWN", f"--only names no installable tool: {', '.join(unknown)}")
    if args.only:
        tools = [tool for tool in tools if str(tool.get("name")) in args.only]

    # Every static check runs before the first download, so a bad manifest executes nothing.
    if _static_problems(tools, out):
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
        added = _unpack_tool(tool, data, args.dest, out)
        if added is None:
            out(f"counts: tools_installed={installed}")
            return 1
        path_additions.extend(added)
        installed += 1
        out(f"installed {name} {tool.get('version', '')} sha256={digest}")

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
