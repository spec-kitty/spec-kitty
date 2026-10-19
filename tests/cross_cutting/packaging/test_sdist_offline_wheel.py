"""FR-008 / C-003: a wheel builds from the unpacked sdist with no git, no network and no fetch.

The sdist carries the pinned ``packs/built-in`` tree. Building a wheel from it must
verify that tree against the pin and nothing else: the ``git`` shim on ``PATH``
records any invocation and fails, the protocol allow-list is empty and the HTTPS
proxy is dead, so any attempt to fetch would either trip the shim or fail loudly.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from charter.offering.packs.pack_clean_digest import clean_tree_digest
from charter.offering.packs.pack_pin import load_pack_pin

pytestmark = [pytest.mark.slow, pytest.mark.distribution, pytest.mark.integration]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PIN_FILE = "packs/built-in.source.yaml"
_PACK_PREFIX = "packs/built-in/"
_BUILD_TIMEOUT_S = 480


@pytest.fixture()
def git_shim(tmp_path: Path) -> tuple[Path, Path]:
    """Return ``(shim_dir, marker)``; the shim ``git`` appends to *marker* and exits 1."""
    shim_dir = tmp_path / "shim-bin"
    shim_dir.mkdir()
    marker = tmp_path / "git-was-called"
    shim = shim_dir / "git"
    shim.write_text(f'#!/bin/sh\necho "$@" >> "{marker}"\nexit 1\n', encoding="utf-8")
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    return shim_dir, marker


@pytest.fixture()
def unpacked_sdist(build_artifacts: dict[str, Path], tmp_path: Path) -> Path:
    """Unpack the built sdist into a fresh directory with no ``.git`` and return its root."""
    target = tmp_path / "sdist"
    target.mkdir()
    with tarfile.open(build_artifacts["sdist"], "r:gz") as tar:
        tar.extractall(target, filter="data")
    (root,) = [child for child in target.iterdir() if child.is_dir()]
    assert not (root / ".git").exists()
    return root


def _offline_env(shim_dir: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        {
            "PATH": f"{shim_dir}{os.pathsep}{env.get('PATH', '')}",
            "GIT_ALLOW_PROTOCOL": "",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "https_proxy": "http://127.0.0.1:9",
            "HTTP_PROXY": "http://127.0.0.1:9",
            "SPEC_KITTY_PACK_OFFLINE": "1",
        }
    )
    return env


def _build_wheel(source: Path, outdir: Path, shim_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--wheel", "--outdir", str(outdir), str(source)],
        cwd=source,
        env=_offline_env(shim_dir),
        capture_output=True,
        text=True,
        timeout=_BUILD_TIMEOUT_S,
    )


def test_wheel_builds_from_sdist_offline_and_matches_the_pin(unpacked_sdist: Path, git_shim: tuple[Path, Path], tmp_path: Path) -> None:
    shim_dir, marker = git_shim
    outdir = tmp_path / "wheel-out"

    result = _build_wheel(unpacked_sdist, outdir, shim_dir)

    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    assert not marker.exists(), f"git was invoked during the sdist->wheel build: {marker.read_text()}"
    (wheel,) = outdir.glob("spec_kitty_cli-*.whl")
    extracted = tmp_path / "wheel-tree"
    with zipfile.ZipFile(wheel) as zf:
        members = [name for name in zf.namelist() if name.startswith(_PACK_PREFIX)]
        zf.extractall(extracted, members=members)
    assert members, "wheel built from the sdist ships no packs/built-in files"
    assert not [name for name in zipfile.ZipFile(wheel).namelist() if name.startswith("packs/internal")]
    pin = load_pack_pin(unpacked_sdist / _PIN_FILE)
    assert clean_tree_digest(extracted / "packs" / "built-in", level="built-in") == pin.tree_digest.value


def test_tampered_sdist_tree_fails_the_wheel_build(unpacked_sdist: Path, git_shim: tuple[Path, Path], tmp_path: Path) -> None:
    shim_dir, marker = git_shim
    victim = next((unpacked_sdist / "packs" / "built-in" / "directives").glob("*.yaml"))
    victim.write_text(victim.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")

    result = _build_wheel(unpacked_sdist, tmp_path / "wheel-out", shim_dir)

    assert result.returncode != 0
    assert "PACK_TREE_STALE" in result.stdout + result.stderr
    assert not marker.exists(), "a tampered sdist tree must be refused, never refetched"


def test_sdist_without_the_tree_fails_instead_of_fetching(unpacked_sdist: Path, git_shim: tuple[Path, Path], tmp_path: Path) -> None:
    shim_dir, marker = git_shim
    shutil.rmtree(unpacked_sdist / "packs" / "built-in")

    result = _build_wheel(unpacked_sdist, tmp_path / "wheel-out", shim_dir)

    assert result.returncode != 0
    assert "PACK_TREE_STALE" in result.stdout + result.stderr
    assert not marker.exists(), "an sdist build must never fetch (C-003)"


def test_repo_pin_file_is_not_the_repo_root_tree() -> None:
    """Guard the fixture assumption: the sdist is unpacked, not the live checkout."""
    assert (_REPO_ROOT / _PIN_FILE).is_file()
