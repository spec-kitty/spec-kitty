"""Unit tests for ``scripts/ci/gradle_tool_cache.py``.

The canonical installer is replaced by a tiny fake installer that writes the
same ``gradle-<version>/bin/gradle`` shape, so every cache-miss/cache-hit/
corruption path is exercised without downloading Gradle.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ci.gradle_tool_cache import (
    MANIFEST_NAME,
    GradlePin,
    ensure_gradle,
    load_gradle_pin,
    main,
    verify_cached_gradle,
)

pytestmark = [pytest.mark.fast]

_VERSION = "8.14.5"
_SHA_A = "a" * 64
_SHA_B = "b" * 64

_FAKE_INSTALLER = """
import os
import pathlib
import sys

count_path = pathlib.Path(os.environ["FAKE_INSTALL_COUNT"])
count_path.write_text(str(int(count_path.read_text() or 0) + 1) if count_path.exists() else "1", encoding="utf-8")
exit_code = int(os.environ.get("FAKE_INSTALL_EXIT", "0"))
if exit_code:
    raise SystemExit(exit_code)
destination = pathlib.Path(sys.argv[sys.argv.index("--dest") + 1])
bin_dir = destination / "gradle-__VERSION__" / "bin"
bin_dir.mkdir(parents=True, exist_ok=True)
gradle = bin_dir / "gradle"
gradle.write_text("#!/bin/sh\\necho __VERSION__\\n", encoding="utf-8")
gradle.chmod(0o755)
"""


def _write_pins(path: Path, *, sha: str = _SHA_A, version: str = _VERSION) -> Path:
    path.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "gradle",
                        "kind": "archive",
                        "version": version,
                        "url": f"https://services.gradle.org/distributions/gradle-{version}-bin.zip",
                        "sha256": sha,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_installer(path: Path) -> Path:
    path.write_text(_FAKE_INSTALLER.replace("__VERSION__", _VERSION), encoding="utf-8")
    return path


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    count = tmp_path / "install-count"
    monkeypatch.setenv("FAKE_INSTALL_COUNT", str(count))
    monkeypatch.setenv("GITHUB_PATH", str(tmp_path / "github_path"))
    (tmp_path / "github_path").touch()
    return {
        "pins": _write_pins(tmp_path / "pins.json"),
        "installer": _write_installer(tmp_path / "install_tools.py"),
        "destination": tmp_path / "tools",
        "count": count,
        "github_path": tmp_path / "github_path",
    }


def _ensure(workspace: dict[str, Path]) -> int:
    return ensure_gradle(
        pins_path=workspace["pins"],
        destination=workspace["destination"],
        installer=workspace["installer"],
    )


def _installs(workspace: dict[str, Path]) -> int:
    count = workspace["count"]
    return int(count.read_text(encoding="utf-8")) if count.exists() else 0


def test_first_ensure_installs_and_writes_a_verified_manifest(workspace: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    assert _ensure(workspace) == 0

    install_root = workspace["destination"] / f"gradle-{_VERSION}"
    assert (install_root / "bin" / "gradle").is_file()
    assert (install_root / MANIFEST_NAME).is_file()
    manifest = json.loads((install_root / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["archive_sha256"] == _SHA_A
    assert manifest["version"] == _VERSION
    assert _installs(workspace) == 1
    assert "INSTALLED" in capsys.readouterr().out
    assert f"gradle-{_VERSION}/bin" in workspace["github_path"].read_text(encoding="utf-8")


def test_second_ensure_is_a_verified_cache_hit_and_does_not_run_the_installer(workspace: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    assert _ensure(workspace) == 0
    assert _ensure(workspace) == 0

    assert _installs(workspace) == 1, "a verified cache hit must not download or unpack the distribution again"
    assert "CACHE_VERIFIED" in capsys.readouterr().out


def test_corrupt_cached_tree_is_rejected_and_reinstalled(workspace: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    assert _ensure(workspace) == 0
    gradle = workspace["destination"] / f"gradle-{_VERSION}" / "bin" / "gradle"
    gradle.write_text("#!/bin/sh\necho corrupted\n", encoding="utf-8")

    assert _ensure(workspace) == 0

    assert _installs(workspace) == 2
    captured = capsys.readouterr().out
    assert "cached gradle" in captured and "rejected" in captured
    assert "tree does not match its install manifest" in captured
    assert gradle.read_text(encoding="utf-8").endswith(f"echo {_VERSION}\n")


def test_cache_from_another_pinned_archive_sha_is_reinstalled(workspace: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    assert _ensure(workspace) == 0
    _write_pins(workspace["pins"], sha=_SHA_B)

    assert _ensure(workspace) == 0

    assert _installs(workspace) == 2
    assert "another pinned archive sha256" in capsys.readouterr().out
    verified, reason = verify_cached_gradle(workspace["destination"], GradlePin(version=_VERSION, archive_sha256=_SHA_B))
    assert verified is True, reason


def test_installer_failure_propagates_its_exit_code(workspace: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("FAKE_INSTALL_EXIT", "7")

    assert _ensure(workspace) == 7

    assert not (workspace["destination"] / f"gradle-{_VERSION}" / MANIFEST_NAME).exists()
    assert "installer exited 7" in capsys.readouterr().err


def test_missing_installer_is_a_clear_helper_error(workspace: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    workspace["installer"].unlink()

    code = main(
        [
            "ensure",
            "--pins",
            str(workspace["pins"]),
            "--dest",
            str(workspace["destination"]),
            "--installer",
            str(workspace["installer"]),
        ]
    )

    assert code == 2
    assert "canonical installer is missing" in capsys.readouterr().err


def test_pins_without_gradle_are_a_helper_error(workspace: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    workspace["pins"].write_text(json.dumps({"tools": []}), encoding="utf-8")

    code = main(
        [
            "ensure",
            "--pins",
            str(workspace["pins"]),
            "--dest",
            str(workspace["destination"]),
            "--installer",
            str(workspace["installer"]),
        ]
    )

    assert code == 2
    assert "no tool named 'gradle'" in capsys.readouterr().err


def test_cache_does_not_hold_build_or_test_result_paths(workspace: dict[str, Path]) -> None:
    """The helper only ever writes the tool tree and its manifest, never test results."""
    assert _ensure(workspace) == 0

    for path in workspace["destination"].rglob("*"):
        relative = path.relative_to(workspace["destination"]).as_posix()
        assert "test-results" not in relative
        assert "/build/" not in f"/{relative}"
        assert "acceptance" not in relative


@pytest.mark.parametrize("version", ["../../outside", "1/../../outside", "1\\outside", "", "\n8.1"])
def test_pin_version_cannot_escape_the_cache(workspace: dict[str, Path], version: str) -> None:
    from scripts.ci.gradle_tool_cache import CacheError

    _write_pins(workspace["pins"], version=version)
    with pytest.raises(CacheError, match="safe release version"):
        _ensure(workspace)
    assert _installs(workspace) == 0


@pytest.mark.parametrize("kind", ["file", "symlink", "broken-symlink"])
def test_corrupt_distribution_root_is_replaced_without_touching_link_target(workspace: dict[str, Path], kind: str) -> None:
    destination = workspace["destination"]
    destination.mkdir()
    install = destination / f"gradle-{_VERSION}"
    outside = destination.parent / "unrelated"
    outside.mkdir()
    marker = outside / "keep"
    marker.write_text("preserved", encoding="utf-8")
    if kind == "file":
        install.write_text("corrupted", encoding="utf-8")
    else:
        install.symlink_to(outside if kind == "symlink" else outside / "absent", target_is_directory=True)
    assert _ensure(workspace) == 0
    assert marker.read_text(encoding="utf-8") == "preserved"
    assert not install.is_symlink()
    assert _installs(workspace) == 1


def test_manifest_is_not_part_of_its_own_tree_digest(workspace: dict[str, Path]) -> None:
    assert _ensure(workspace) == 0
    manifest = workspace["destination"] / f"gradle-{_VERSION}" / MANIFEST_NAME
    manifest.write_text(manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")

    verified, reason = verify_cached_gradle(
        workspace["destination"],
        load_gradle_pin(workspace["pins"]),
    )
    assert verified is True, f"editing the manifest's whitespace alone must not invalidate the tree digest: {reason}"
