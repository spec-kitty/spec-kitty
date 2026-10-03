"""Planted-violation tests for ``contracts/tools/install_tools.py`` (FR-018, NFR-002).

The fixture directory ``contracts/tools/fixtures/install_tools/`` holds a clean
manifest and the tiny archive it pins. Each violation is made at run time from a
copy of that manifest (never by hand in a committed file) and must fail with its
stable code before anything is unpacked or executed. The downloader is injected,
so no test touches the network.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

TOOLS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "tools"
FIXTURE_DIR = TOOLS_DIR / "fixtures" / "install_tools"
SCRIPT = TOOLS_DIR / "install_tools.py"


@pytest.fixture(scope="module")
def installer() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, SCRIPT, "install_tools_under_test", syspath=TOOLS_DIR)


def _manifest() -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))


def _write(tmp_path: Path, manifest: dict[str, Any]) -> Path:
    target = tmp_path / "pins.json"
    target.write_text(json.dumps(manifest), encoding="utf-8")
    return target


def _fetch_fixture(calls: list[str]) -> Callable[[str], bytes]:
    def fetch(url: str) -> bytes:
        calls.append(url)
        return (FIXTURE_DIR / "payload.bin").read_bytes()

    return fetch


def _run(installer: ModuleType, pins: Path, dest: Path, fetch: Callable[[str], bytes]) -> tuple[int, str]:
    lines: list[str] = []
    code = installer.run(["--pins", str(pins), "--dest", str(dest)], fetch=fetch, out=lines.append)
    return code, "\n".join(lines)


def test_clean_manifest_installs_and_unpacks_with_the_executable_bit(installer: ModuleType, tmp_path: Path) -> None:
    calls: list[str] = []

    code, output = _run(installer, _write(tmp_path, _manifest()), tmp_path / "tools", _fetch_fixture(calls))

    assert code == 0, output
    binary = tmp_path / "tools" / "fixture-tool-1.0" / "bin" / "fixture-tool"
    assert binary.is_file() and os.access(binary, os.X_OK)
    assert calls == ["https://downloads.example.invalid/fixture-tool-1.0.zip"]
    assert output.splitlines()[-1] == "counts: tools_installed=1"


def test_altered_checksum_fails_before_anything_is_unpacked(installer: ModuleType, tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["tools"][0]["sha256"] = "0" * 64

    code, output = _run(installer, _write(tmp_path, manifest), tmp_path / "tools", _fetch_fixture([]))

    assert code == 1
    assert "CONTRACT-CHECK install_tools: CHECKSUM_MISMATCH:" in output
    assert not (tmp_path / "tools").exists(), "nothing is unpacked after a mismatch"
    assert output.splitlines()[-1] == "counts: tools_installed=0"


def test_missing_checksum_fails_before_download(installer: ModuleType, tmp_path: Path) -> None:
    manifest = _manifest()
    del manifest["tools"][0]["sha256"]
    calls: list[str] = []

    code, output = _run(installer, _write(tmp_path, manifest), tmp_path / "tools", _fetch_fixture(calls))

    assert code == 1
    assert "CHECKSUM_MISSING" in output
    assert calls == [], "a tool without a checksum is never downloaded"


def test_non_https_url_fails_before_download(installer: ModuleType, tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["tools"][0]["url"] = "http://downloads.example.invalid/fixture-tool-1.0.zip"
    calls: list[str] = []

    code, output = _run(installer, _write(tmp_path, manifest), tmp_path / "tools", _fetch_fixture(calls))

    assert code == 1
    assert "NOT_HTTPS" in output
    assert calls == []


@pytest.mark.parametrize("manifest", [{"tools": []}, {}, {"tools": [{"name": "plugin", "kind": "gradle-plugin"}]}])
def test_empty_manifest_cannot_do_its_job(installer: ModuleType, tmp_path: Path, manifest: dict[str, Any]) -> None:
    code, output = _run(installer, _write(tmp_path, manifest), tmp_path / "tools", _fetch_fixture([]))

    assert code == 2
    assert "MANIFEST_EMPTY" in output


def test_unreadable_manifest_cannot_do_its_job(installer: ModuleType, tmp_path: Path) -> None:
    broken = tmp_path / "pins.json"
    broken.write_text("{not json", encoding="utf-8")

    code, output = _run(installer, broken, tmp_path / "tools", _fetch_fixture([]))

    assert code == 2
    assert "MANIFEST_EMPTY" in output


def test_failed_download_cannot_do_its_job(installer: ModuleType, tmp_path: Path) -> None:
    def broken(url: str) -> bytes:
        raise OSError(f"cannot reach {url}")

    code, output = _run(installer, _write(tmp_path, _manifest()), tmp_path / "tools", broken)

    assert code == 2
    assert "DOWNLOAD_FAILED" in output


def test_archive_member_escaping_the_destination_is_refused(installer: ModuleType, tmp_path: Path) -> None:
    import hashlib
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escape.txt", "x")
    payload = buffer.getvalue()
    manifest = _manifest()
    manifest["tools"][0]["sha256"] = hashlib.sha256(payload).hexdigest()  # noqa: TID251 -- file-integrity checksum of a test payload

    code, output = _run(installer, _write(tmp_path, manifest), tmp_path / "tools", lambda _url: payload)

    assert code == 1
    assert "UNSAFE_ARCHIVE" in output
    assert not (tmp_path / "escape.txt").exists()


def test_script_prints_the_final_counts_line_and_exits_2_on_a_missing_manifest(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--pins", str(tmp_path / "absent.json"), "--dest", str(tmp_path / "tools")],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 2
    assert result.stdout.splitlines()[-1] == "counts: tools_installed=0"


def test_the_committed_manifest_pins_https_checksummed_tools_with_every_field() -> None:
    manifest = json.loads((TOOLS_DIR / "pins.json").read_text(encoding="utf-8"))

    assert {tool["name"] for tool in manifest["tools"]} >= {"gradle", "openapi-generator-gradle-plugin"}
    for tool in manifest["tools"]:
        assert set(tool) >= {"name", "kind", "version", "url", "sha256", "published", "advisory_feed_checked"}
        assert tool["url"].startswith("https://")
        assert len(tool["sha256"]) == 64


# -- prebuilt Go binaries (vacuum, oasdiff): tar.gz archives with the binary at the archive root -------------

GO_URL = "https://downloads.example.invalid/gotool_2.0_linux_x86_64.tar.gz"


def _tarball(members: dict[str, bytes], modes: dict[str, int] | None = None) -> bytes:
    import io
    import tarfile

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = (modes or {}).get(name, 0o755 if name == "gotool" else 0o644)
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def _go_manifest(payload: bytes, **overrides: Any) -> dict[str, Any]:
    import hashlib

    tool = {
        "name": "gotool",
        "kind": "archive",
        "version": "2.0",
        "url": GO_URL,
        "sha256": hashlib.sha256(payload).hexdigest(),  # noqa: TID251 -- file-integrity checksum of a test payload
        "binary": "gotool",
        "published": "2026-01-01",
        "advisory_feed_checked": "fixture only",
    }
    tool.update(overrides)
    return {"tools": [tool]}


def test_tar_gz_binary_installs_into_its_own_directory_with_the_executable_bit(installer: ModuleType, tmp_path: Path) -> None:
    payload = _tarball({"LICENSE": b"licence", "gotool": b"#!/bin/sh\necho gotool\n"})

    code, output = _run(installer, _write(tmp_path, _go_manifest(payload)), tmp_path / "tools", lambda _url: payload)

    assert code == 0, output
    binary = tmp_path / "tools" / "gotool-2.0" / "gotool"
    assert binary.is_file() and os.access(binary, os.X_OK)
    assert f"bin directory: {(tmp_path / 'tools' / 'gotool-2.0').resolve()}" in output
    assert output.splitlines()[-1] == "counts: tools_installed=1"


def test_tar_gz_install_appends_its_directory_to_github_path(installer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _tarball({"gotool": b"x"})
    github_path = tmp_path / "github_path"
    monkeypatch.setenv("GITHUB_PATH", str(github_path))

    _run(installer, _write(tmp_path, _go_manifest(payload)), tmp_path / "tools", lambda _url: payload)

    assert github_path.read_text(encoding="utf-8").strip() == str((tmp_path / "tools" / "gotool-2.0").resolve())


def test_tar_gz_with_an_altered_checksum_is_never_unpacked(installer: ModuleType, tmp_path: Path) -> None:
    payload = _tarball({"gotool": b"x"})

    code, output = _run(installer, _write(tmp_path, _go_manifest(payload, sha256="0" * 64)), tmp_path / "tools", lambda _url: payload)

    assert code == 1 and "CHECKSUM_MISMATCH" in output
    assert not (tmp_path / "tools").exists()


def test_tar_gz_without_the_declared_binary_fails(installer: ModuleType, tmp_path: Path) -> None:
    payload = _tarball({"README.md": b"no binary here"})

    code, output = _run(installer, _write(tmp_path, _go_manifest(payload)), tmp_path / "tools", lambda _url: payload)

    assert code == 1
    assert "CONTRACT-CHECK install_tools: BINARY_MISSING: gotool:" in output
    assert output.splitlines()[-1] == "counts: tools_installed=0"


def test_tar_gz_member_escaping_the_destination_is_refused(installer: ModuleType, tmp_path: Path) -> None:
    payload = _tarball({"gotool": b"x", "../escape.txt": b"x"})

    code, output = _run(installer, _write(tmp_path, _go_manifest(payload)), tmp_path / "tools", lambda _url: payload)

    assert code == 1 and "UNSAFE_ARCHIVE" in output
    assert not (tmp_path / "escape.txt").exists()


def test_an_archive_url_of_an_unknown_format_cannot_be_installed(installer: ModuleType, tmp_path: Path) -> None:
    payload = _tarball({"gotool": b"x"})
    manifest = _go_manifest(payload, url="https://downloads.example.invalid/gotool_2.0.rpm")

    code, output = _run(installer, _write(tmp_path, manifest), tmp_path / "tools", lambda _url: payload)

    assert code == 1 and "UNSUPPORTED_FORMAT" in output


def test_only_installs_the_named_tool_and_downloads_nothing_else(installer: ModuleType, tmp_path: Path) -> None:
    payload = _tarball({"gotool": b"x"})
    manifest = _go_manifest(payload)
    manifest["tools"].append(_manifest()["tools"][0])
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return payload

    lines: list[str] = []
    code = installer.run(["--pins", str(_write(tmp_path, manifest)), "--dest", str(tmp_path / "tools"), "--only", "gotool"], fetch=fetch, out=lines.append)

    assert code == 0, lines
    assert calls == [GO_URL]
    assert lines[-1] == "counts: tools_installed=1"


def test_only_with_an_unknown_name_cannot_do_its_job(installer: ModuleType, tmp_path: Path) -> None:
    payload = _tarball({"gotool": b"x"})
    lines: list[str] = []

    code = installer.run(
        ["--pins", str(_write(tmp_path, _go_manifest(payload))), "--dest", str(tmp_path / "tools"), "--only", "absent"], fetch=lambda _u: payload, out=lines.append
    )

    assert code == 2 and any("TOOL_UNKNOWN" in line for line in lines)
    assert lines[-1] == "counts: tools_installed=0"


# -- the committed pins for the two CI-only Go binaries ----------------------------------------------------

# A version published less than 14 days before the pin date is adverse (R-9). ISO dates compare as text.
PIN_DATE = "2026-10-02"
LATEST_ACCEPTABLE_PUBLICATION = "2026-09-18"
VENDOR_PREFIXES = {
    "vacuum": "https://github.com/daveshanley/vacuum/releases/download/v{version}/vacuum_{version}_linux_x86_64.tar.gz",
    "oasdiff": "https://github.com/oasdiff/oasdiff/releases/download/v{version}/oasdiff_{version}_linux_amd64.tar.gz",
}


@pytest.mark.parametrize("name", sorted(VENDOR_PREFIXES))
def test_go_binary_pins_come_from_the_vendor_release_over_https_and_are_old_enough(name: str) -> None:
    manifest = json.loads((TOOLS_DIR / "pins.json").read_text(encoding="utf-8"))
    (tool,) = [entry for entry in manifest["tools"] if entry["name"] == name]

    assert tool["kind"] == "archive" and tool["binary"] == name
    assert tool["url"] == VENDOR_PREFIXES[name].format(version=tool["version"]), "the official release location, version in the url"
    assert len(tool["sha256"]) == 64 and set(tool["sha256"]) <= set("0123456789abcdef")
    assert tool["published"] <= LATEST_ACCEPTABLE_PUBLICATION, f"{name} {tool['version']} is younger than 14 days at {PIN_DATE}"
    assert tool["advisory_feed_checked"].strip()


def _tarball_with(entries: list[tarfile.TarInfo], payloads: dict[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for info in entries:
            content = (payloads or {}).get(info.name, b"")
            if info.isreg():
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
            else:
                archive.addfile(info)
    return buffer.getvalue()


def _binary_entry() -> tarfile.TarInfo:
    info = tarfile.TarInfo("gotool")
    info.mode = 0o755
    return info


def _link_entry(name: str, target: str, kind: bytes) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = target
    return info


@pytest.mark.parametrize(
    "hostile",
    [
        pytest.param(("/escape.txt", b"x"), id="absolute-member"),
        pytest.param(("sub/../../escape.txt", b"x"), id="dotdot-member"),
    ],
)
def test_tar_gz_absolute_and_dotdot_members_are_refused(installer: ModuleType, tmp_path: Path, hostile: tuple[str, bytes]) -> None:
    name, content = hostile
    info = tarfile.TarInfo(name)
    payload = _tarball_with([_binary_entry(), info], {"gotool": b"x", name: content})

    code, output = _run(installer, _write(tmp_path, _go_manifest(payload)), tmp_path / "tools", lambda _url: payload)

    assert code == 1 and "UNSAFE_ARCHIVE" in output
    assert not (tmp_path / "escape.txt").exists()


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE], ids=["symlink", "hardlink"])
def test_tar_gz_links_leaving_the_destination_are_refused(installer: ModuleType, tmp_path: Path, kind: bytes) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("untouched", encoding="utf-8")
    payload = _tarball_with([_binary_entry(), _link_entry("pivot", str(outside), kind)], {"gotool": b"x"})

    code, output = _run(installer, _write(tmp_path, _go_manifest(payload)), tmp_path / "tools", lambda _url: payload)

    assert code == 1 and "UNSAFE_ARCHIVE" in output
    assert outside.read_text(encoding="utf-8") == "untouched"


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE], ids=["symlink", "hardlink"])
def test_tar_gz_links_to_a_relative_escape_are_refused(installer: ModuleType, tmp_path: Path, kind: bytes) -> None:
    payload = _tarball_with([_binary_entry(), _link_entry("pivot", "../../outside.txt", kind)], {"gotool": b"x"})

    code, output = _run(installer, _write(tmp_path, _go_manifest(payload)), tmp_path / "tools", lambda _url: payload)

    assert code == 1 and "UNSAFE_ARCHIVE" in output


def test_tar_gz_unpacking_is_refused_where_the_data_filter_is_unavailable(installer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A tarfile without extraction filters must refuse with its own code, never extract unfiltered and never claim a hostile archive."""
    monkeypatch.delattr(tarfile, "data_filter")
    payload = _tarball({"gotool": b"x"})

    code, output = _run(installer, _write(tmp_path, _go_manifest(payload)), tmp_path / "tools", lambda _url: payload)

    assert code == 1
    assert "UNSUPPORTED_INTERPRETER" in output and "extraction filters" in output
    assert "UNSAFE_ARCHIVE" not in output and "3.11.4" not in output
    assert not (tmp_path / "tools").exists()
