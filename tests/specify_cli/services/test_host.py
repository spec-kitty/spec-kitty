"""``specify_cli.services.host``: host target detection and the Java runtime probe (#6590, WP03 T012).

(``host_target`` moved to ``kernel.service_hosts``; ``tests/kernel/test_service_hosts.py``.)
``find_java`` prefers ``JAVA_HOME`` over ``PATH``, accepts only a runtime whose
major version is at least the minimum (research R-6), and caches its answer per
process. The exec part uses a fake ``java`` shell script and is POSIX-only.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.services import host
from specify_cli.services.host import find_java, parse_java_major

pytestmark = pytest.mark.fast

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="the fake java is a POSIX shell script")


@pytest.fixture(autouse=True)
def _fresh_java_cache() -> None:
    host._JAVA_CACHE.clear()


@pytest.mark.parametrize(
    ("text", "major"),
    [
        ('openjdk version "25.0.2" 2026-01-20', 25),
        ('java version "25"', 25),
        ('openjdk version "21.0.5" 2024-10-15 LTS', 21),
        ('java version "1.8.0_402"', 8),
        ('openjdk version "26-ea" 2026-03-17', 26),
        ("no version here", None),
        ("", None),
    ],
)
def test_parse_java_major(text: str, major: int | None) -> None:
    assert parse_java_major(text) == major


def _fake_java(directory: Path, version: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    java = directory / "java"
    java.write_text(f"#!/bin/sh\necho 'openjdk version \"{version}\" 2026-01-20' >&2\n", encoding="utf-8")
    java.chmod(0o755)
    return java


@posix_only
def test_find_java_prefers_java_home(tmp_path: Path) -> None:
    home_java = _fake_java(tmp_path / "jdk" / "bin", "25.0.2")
    path_java = _fake_java(tmp_path / "path", "26")
    env = {"JAVA_HOME": str(tmp_path / "jdk"), "PATH": str(path_java.parent)}
    assert find_java(env=env) == home_java


@posix_only
def test_find_java_falls_back_to_path(tmp_path: Path) -> None:
    path_java = _fake_java(tmp_path / "path", "25")
    env = {"JAVA_HOME": str(tmp_path / "missing-jdk"), "PATH": str(path_java.parent)}
    assert find_java(env=env) == path_java


@posix_only
def test_find_java_skips_a_too_old_java_home_for_a_new_enough_path_java(tmp_path: Path) -> None:
    _fake_java(tmp_path / "jdk" / "bin", "21.0.5")
    path_java = _fake_java(tmp_path / "path", "25.0.1")
    env = {"JAVA_HOME": str(tmp_path / "jdk"), "PATH": str(path_java.parent)}
    assert find_java(env=env) == path_java


@posix_only
def test_find_java_refuses_an_old_runtime(tmp_path: Path) -> None:
    old = _fake_java(tmp_path / "path", "1.8.0_402")
    assert find_java(env={"PATH": str(old.parent)}) is None


@posix_only
def test_find_java_honours_min_major(tmp_path: Path) -> None:
    java = _fake_java(tmp_path / "path", "21.0.5")
    env = {"PATH": str(java.parent)}
    assert find_java(env=env) is None
    assert find_java(21, env=env) == java


def _plain_java(directory: Path) -> Path:
    """A file named like this platform's java, with the exec bit (its content is never run: ``subprocess.run`` is faked)."""
    java = directory / ("java.exe" if sys.platform == "win32" else "java")
    java.write_text("", encoding="utf-8")
    java.chmod(0o755)
    return java


@pytest.mark.parametrize("windows", [False, True])
def test_find_java_never_runs_a_java_from_the_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, windows: bool) -> None:
    """F7: only absolute PATH entries are searched; ``.``, empty and relative entries (and the cwd itself) never are."""
    cwd = tmp_path / "project"
    (cwd / "relative" / "bin").mkdir(parents=True)
    for directory in (cwd, cwd / "relative" / "bin"):
        for name in ("java", "java.exe"):
            planted = directory / name
            planted.write_text("#!/bin/sh\necho planted\n", encoding="utf-8")
            planted.chmod(0o755)
    empty_absolute = tmp_path / "empty-bin"
    empty_absolute.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(host, "is_windows", lambda: windows)
    ran: list[list[str]] = []

    def _run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        ran.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr='openjdk version "25.0.2"')

    monkeypatch.setattr(subprocess, "run", _run)
    env = {"PATH": os.pathsep.join([".", "", "relative/bin", str(empty_absolute)]), "JAVA_HOME": "relative"}

    assert find_java(env=env) is None
    assert ran == [], f"a java outside an absolute PATH entry was run: {ran}"


def test_find_java_finds_java_exe_on_an_absolute_windows_path_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    java = tmp_path / "jdk" / "bin" / "java.exe"
    java.parent.mkdir(parents=True)
    java.write_text("", encoding="utf-8")
    monkeypatch.setattr(host, "is_windows", lambda: True)
    monkeypatch.setattr(subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, stdout="", stderr='openjdk version "25"'))
    assert find_java(env={"PATH": os.pathsep.join([".", str(java.parent)])}) == java


def test_find_java_with_no_java_anywhere(tmp_path: Path) -> None:
    assert find_java(env={"PATH": str(tmp_path)}) is None


def test_find_java_treats_a_timeout_as_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plain_java(tmp_path)

    def _timeout(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="java", timeout=10)

    monkeypatch.setattr(subprocess, "run", _timeout)
    assert find_java(env={"PATH": str(tmp_path)}) is None


def test_find_java_treats_an_unrunnable_binary_as_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plain_java(tmp_path)

    def _broken(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise PermissionError("not executable")

    monkeypatch.setattr(subprocess, "run", _broken)
    assert find_java(env={"PATH": str(tmp_path)}) is None


def test_find_java_caches_per_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def _run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr='openjdk version "25.0.2"')

    _plain_java(tmp_path)
    monkeypatch.setattr(subprocess, "run", _run)
    env = {"PATH": str(tmp_path)}
    first = find_java(env=env)
    second = find_java(env=env)
    assert first == second == tmp_path / "java"
    assert len(calls) == 1
    assert calls[0][1:] == ["-version"]


def test_find_java_reads_the_process_environment_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JAVA_HOME", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert os.environ["PATH"] == str(tmp_path)
    assert find_java() is None


def test_java_home_on_windows_is_java_exe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The JAVA_HOME candidate's file name follows the sanctioned OS seam (``kernel.paths.is_windows``)."""
    bin_dir = tmp_path / "jdk" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "java.exe").write_bytes(b"")
    env = {"JAVA_HOME": str(tmp_path / "jdk"), "PATH": str(tmp_path / "empty")}

    monkeypatch.setattr(host, "is_windows", lambda: True)
    assert host._java_candidates(env) == [bin_dir / "java.exe"]
    monkeypatch.setattr(host, "is_windows", lambda: False)
    assert host._java_candidates(env) == []
