"""Host facts the resolver needs beyond the release target: a usable Java runtime (#6590, research R-6).

The host's release target and the "native build, else the jar" rule live in
``kernel.service_hosts`` (one authority for the sync script, ``service fetch``
and resolution). :func:`find_java` finds a Java runtime of at least the
required major version, ``JAVA_HOME`` first and then ``PATH``, both only as
absolute paths, never the working directory; it runs ``java -version`` (10 s
budget) only when the resolver needs the jar, and caches the answer per process.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

from kernel.paths import is_windows

__all__ = ["find_java"]

DEFAULT_JAVA_MAJOR = 25
_VERSION_TIMEOUT_S = 10.0
_VERSION_RE = re.compile(r'version "(\d+)(?:\.(\d+))?[^"]*"')

#: ``find_java`` answers, keyed by the minimum major and the environment it read.
_JAVA_CACHE: dict[tuple[int, str | None, str | None], Path | None] = {}


def parse_java_major(text: str) -> int | None:
    """The major version in ``java -version`` output: ``"25.0.2"`` and ``"25"`` are 25, ``"1.8.0_x"`` is 8."""
    match = _VERSION_RE.search(text)
    if match is None:
        return None
    major = int(match.group(1))
    if major == 1 and match.group(2) is not None:
        return int(match.group(2))
    return major


def _absolute_dir(raw: str) -> Path | None:
    """*raw* as a directory to search, or ``None`` when it is empty, ``.`` or relative (it would resolve against the cwd)."""
    if not raw or raw == ".":
        return None
    path = Path(raw)
    return path if path.is_absolute() else None


def _on_path(executable: str, path_value: str | None) -> Path | None:
    """The first *executable* in an absolute ``PATH`` entry.

    Not ``shutil.which``: on Windows it looks in the working directory first, so a
    ``java.exe`` planted in a project would run. Empty, ``.`` and relative entries are
    skipped on every platform for the same reason.
    """
    for entry in (path_value or "").split(os.pathsep):
        directory = _absolute_dir(entry)
        if directory is None:
            continue
        candidate = directory / executable
        if candidate.is_file() and (is_windows() or os.access(candidate, os.X_OK)):
            return candidate
    return None


def _java_candidates(env: Mapping[str, str]) -> list[Path]:
    executable = "java.exe" if is_windows() else "java"
    candidates: list[Path] = []
    java_home = _absolute_dir(env.get("JAVA_HOME", ""))
    if java_home is not None:
        home_java = java_home / "bin" / executable
        if home_java.is_file():
            candidates.append(home_java)
    on_path = _on_path(executable, env.get("PATH"))
    if on_path is not None:
        candidates.append(on_path)
    return candidates


def _java_major(java: Path) -> int | None:
    try:
        completed = subprocess.run([str(java), "-version"], capture_output=True, text=True, timeout=_VERSION_TIMEOUT_S, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_java_major(f"{completed.stderr}\n{completed.stdout}")


def find_java(min_major: int = DEFAULT_JAVA_MAJOR, *, env: Mapping[str, str] | None = None) -> Path | None:
    """A Java runtime whose major version is at least *min_major*, or ``None``."""
    environ = os.environ if env is None else env
    key = (min_major, environ.get("JAVA_HOME"), environ.get("PATH"))
    if key not in _JAVA_CACHE:
        _JAVA_CACHE[key] = next((java for java in _java_candidates(environ) if (_java_major(java) or 0) >= min_major), None)
    return _JAVA_CACHE[key]
