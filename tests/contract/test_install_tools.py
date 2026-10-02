"""Planted-violation tests for ``contracts/tools/install_tools.py`` (FR-018, NFR-002).

The fixture directory ``contracts/tools/fixtures/install_tools/`` holds a clean
manifest and the tiny archive it pins. Each violation is made at run time from a
copy of that manifest (never by hand in a committed file) and must fail with its
stable code before anything is unpacked or executed. The downloader is injected,
so no test touches the network.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

TOOLS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "tools"
FIXTURE_DIR = TOOLS_DIR / "fixtures" / "install_tools"
SCRIPT = TOOLS_DIR / "install_tools.py"


@pytest.fixture(scope="module")
def installer() -> ModuleType:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("install_tools_under_test", SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(TOOLS_DIR))
    return module


def _manifest() -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))


def _write(tmp_path: Path, manifest: dict[str, Any]) -> Path:
    target = tmp_path / "pins.json"
    target.write_text(json.dumps(manifest), encoding="utf-8")
    return target


def _fetch_fixture(calls: list[str]) -> Callable[[str], bytes]:
    def fetch(url: str) -> bytes:
        calls.append(url)
        return (FIXTURE_DIR / "payload.zip").read_bytes()

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
