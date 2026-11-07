"""Explicit isolated subprocesses for upgrade acceptance, without ambient secrets."""

from __future__ import annotations

import json
import errno
import os
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests._support.git_ceiling import GIT_CEILING_ENV
from tests._support.temp_root import harness_env


def child_environment(sandbox: Path, options: Mapping[str, str] | None = None) -> dict[str, str]:
    """Construct an allowlisted environment; never inherit credentials or selectors.

    The measured home is deliberately NOT created. Temporary roots are setup
    infrastructure outside it. Only presentation options may customize a child.
    """
    sandbox = sandbox.resolve()
    home = sandbox / "home"
    temp = sandbox / "tmp"
    temp.mkdir(parents=True, exist_ok=True)
    env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
    env.update(
        {
            "PATH": os.defpath,
            "HOME": str(home),
            "USERPROFILE": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_DATA_HOME": str(home / ".local/share"),
            "XDG_STATE_HOME": str(home / ".local/state"),
            "APPDATA": str(home / "AppData/Roaming"),
            "LOCALAPPDATA": str(home / "AppData/Local"),
            "SPEC_KITTY_HOME": str(home / ".kittify"),
            "TMPDIR": str(temp),
            "TMP": str(temp),
            "TEMP": str(temp),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
            "GIT_TERMINAL_PROMPT": "0",
            "CI": "true",
            "COLUMNS": "240",
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
        }
    )
    env.update({key: value for key, value in (options or {}).items() if key in {"CI", "TERM", "COLUMNS"}})
    if not env["CI"]:
        del env["CI"]
    env["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "0"
    # Only the ceiling: this child owns its temp root on purpose (provenance probes read
    # ``env["TMPDIR"]``), but its git must still stop at the harness boundary instead of
    # resolving into whatever encloses the sandbox (#7076).
    ceiling = harness_env().get(GIT_CEILING_ENV)
    if ceiling is not None:
        env[GIT_CEILING_ENV] = ceiling
    return env


@dataclass(frozen=True)
class ProcessResult:
    """Complete command evidence, including failures and elapsed wall time."""

    argv: tuple[str, ...]
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    elapsed: float

    def require_success(self) -> None:
        """Refuse startup/error output as a successful observation."""
        assert self.returncode == 0, f"Command failed: {self.argv}\n{self.stdout}\n{self.stderr}"
        assert self.stdout.strip(), f"Empty command output: {self.argv}"

    def json(self) -> dict[str, Any]:
        """Parse the entire stdout as exactly one nonempty JSON object."""
        value = json.loads(self.stdout)
        assert isinstance(value, dict) and value, "Expected nonempty JSON object"
        return value


def _tty_process(argv: Sequence[str], cwd: Path, env: Mapping[str, str], timeout: float) -> tuple[int, str, str]:
    """Capture a genuine POSIX stdout TTY while keeping stdin closed."""
    import pty

    master, slave = pty.openpty()
    chunks: list[bytes] = []
    errors: list[OSError] = []

    def drain() -> None:
        try:
            while data := os.read(master, 65536):
                chunks.append(data)
        except OSError as exc:
            if exc.errno != errno.EIO:  # POSIX PTYs report EIO at slave EOF.
                errors.append(exc)

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        result = subprocess.run(
            list(argv), cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=slave, stderr=subprocess.PIPE, text=True, timeout=timeout, check=False
        )
    finally:
        os.close(slave)
        reader.join(timeout=5)
        os.close(master)
    assert not reader.is_alive() and not errors, f"TTY observer failed: {errors}"
    return result.returncode, b"".join(chunks).decode("utf-8"), result.stderr


def run_process(argv: Sequence[str], cwd: Path, env: Mapping[str, str], *, timeout: float = 90, tty_output: bool = False) -> ProcessResult:
    """Run with closed stdin and a bounded deadline; bind sync off last."""
    bound = dict(env)
    bound["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "0"
    start = time.monotonic()
    if tty_output:
        code, stdout, stderr = _tty_process(argv, cwd, bound, timeout)
        return ProcessResult(tuple(argv), str(cwd), code, stdout, stderr, time.monotonic() - start)
    result = subprocess.run(list(argv), cwd=cwd, env=bound, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout, check=False)
    return ProcessResult(tuple(argv), str(cwd), result.returncode, result.stdout, result.stderr, time.monotonic() - start)
