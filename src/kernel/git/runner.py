"""The one subprocess seam for git path listings (mission git-paths-are-data).

:func:`run_git` runs ``git <args>`` in a checkout and returns raw bytes. It
knows no specific git command: callers never build path-listing argv
themselves — they ask :mod:`kernel.git.listing` by intent — and destructive
commands (``reset --hard``, ``update-ref``, ``worktree remove``) stay at their
guarded call sites in ``specify_cli`` (C-007).

Paths git prints are decoded exactly one way, :func:`decode_path`: UTF-8 with
``surrogateescape``. That is lossless (undecodable bytes round-trip to the
filesystem through ``os.fsencode`` on POSIX) and matches git for Windows, which
emits UTF-8 path bytes under ``-z``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

__all__ = ["GitCommandError", "GitResult", "decode_path", "run_git"]

# Returncode reported when git could not be executed at all (missing binary,
# unreadable working directory, timeout).
_NOT_RUN: int = -1


@dataclass(frozen=True)
class GitResult:
    """Raw outcome of one git invocation."""

    returncode: int
    stdout: bytes
    stderr: bytes


class GitCommandError(RuntimeError):
    """A git invocation failed: non-zero exit, missing binary, or timeout.

    Queries raise this instead of returning an empty result, so a guard can
    never read a failed probe as "nothing to protect" (fail closed).
    """

    def __init__(self, *, argv: tuple[str, ...], cwd: Path, returncode: int, stderr: str, timed_out: bool = False) -> None:
        self.argv = argv
        self.cwd = cwd
        self.returncode = returncode
        self.stderr = stderr
        self.timed_out = timed_out
        detail = stderr.strip().splitlines()[0] if stderr.strip() else "no error output"
        super().__init__(f"git {' '.join(argv)} failed in {cwd} (exit {returncode}): {detail}")

    @property
    def not_run(self) -> bool:
        """``True`` when git could not be started (missing binary, unusable cwd); a timeout is not this."""
        return self.returncode == _NOT_RUN and not self.timed_out


def decode_path(raw: bytes) -> str:
    """Decode a path git printed, losslessly (UTF-8, ``surrogateescape``)."""
    return raw.decode("utf-8", "surrogateescape")


def run_git(
    cwd: Path,
    *args: str,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    check: bool = True,
) -> GitResult:
    """Run ``git <args>`` in *cwd* and return its raw bytes.

    Args:
        cwd: Directory git runs in (a checkout root; the listing queries also
            ask git for repository-relative paths so a subdirectory works).
        args: Arguments after ``git``.
        env: Subprocess environment, passed through unchanged (``None``
            inherits the caller's environment).
        timeout: Seconds before the process is killed; ``None`` waits.
        check: When ``True`` (the default) a non-zero exit raises
            :class:`GitCommandError`; when ``False`` the result is returned for
            the caller to interpret.

    Raises:
        GitCommandError: git exited non-zero (with ``check``), could not be
            executed, or timed out.
    """
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            env=dict(env) if env is not None else None,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitCommandError(argv=args, cwd=cwd, returncode=_NOT_RUN, stderr=str(exc), timed_out=True) from exc
    except OSError as exc:
        raise GitCommandError(argv=args, cwd=cwd, returncode=_NOT_RUN, stderr=str(exc)) from exc
    if check and completed.returncode != 0:
        raise GitCommandError(argv=args, cwd=cwd, returncode=completed.returncode, stderr=completed.stderr.decode("utf-8", "replace"))
    return GitResult(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
