"""The one owner of git commands that contact a remote (FR-013, FR-017, NFR-001, NFR-002).

This is the "how" layer for remote contact, the sibling of :mod:`kernel.git.listing`:
it knows refs and remotes, never Missions, lanes or status (C-001). Every
function runs through :func:`kernel.git.runner.run_git` with
:func:`no_prompt_env` and a bounded timeout, so an unreachable or
credential-prompting remote can neither hang the CLI nor ask a question.

A failed contact is NEVER read as "the branch is not there": :func:`remote_heads`
and :func:`fetch_branches` raise :class:`RemoteUnreachable` instead of returning
an empty result, so a caller cannot mistake "could not ask" for "asked, absent".
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath

from kernel.git.runner import GitCommandError, GitResult, run_git

__all__ = [
    "CLONE_TIMEOUT",
    "FETCH_TIMEOUT",
    "LS_REMOTE_TIMEOUT",
    "Divergence",
    "RemoteUnreachable",
    "clone_repository",
    "describe_remote_head",
    "divergence",
    "fetch_branches",
    "fetch_tags",
    "no_prompt_env",
    "remote_heads",
    "resolve_remote",
    "tracking_ref",
]

# Seconds before a remote listing is abandoned (NFR-001).
LS_REMOTE_TIMEOUT: float = 5.0
# Seconds before a branch fetch is abandoned (NFR-001).
FETCH_TIMEOUT: float = 15.0
# A clone transfers a whole pack repository, so it gets a generous bound; it is
# still finite so a stalled transport cannot hang ``spec-kitty`` indefinitely.
CLONE_TIMEOUT: float = 120.0

_DEFAULT_SSH_PROGRAM = "ssh"
_SSH_LIKE_PROGRAMS = frozenset({"ssh", "ssh.exe"})
_BATCH_MODE = "BatchMode"
_LOCAL_REMOTE = "."
_DEFAULT_REMOTE = "origin"


def _configured_ssh_command(cwd: Path | None) -> str | None:
    """Read ``core.sshCommand`` from git config (no network).

    With a *cwd*, every scope git itself would read there (repository-local,
    global, system). With ``None`` (a clone, which reads no repository's local
    config), only the global and system scopes, so the caller's own project
    repository never lends its transport choice to an unrelated clone.
    """
    if cwd is not None:
        return _read_ssh_command(cwd, ())
    return _read_ssh_command(Path.cwd(), ("--global",)) or _read_ssh_command(Path.cwd(), ("--system",))


def _read_ssh_command(cwd: Path, scope: tuple[str, ...]) -> str | None:
    result = run_git(cwd, "config", *scope, "--get", "core.sshCommand", timeout=LS_REMOTE_TIMEOUT, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", "replace").strip() or None


def _is_ssh_like(command: str) -> bool:
    """``True`` when *command*'s program is plain ssh(1), the only program that takes ``-o BatchMode``."""
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    return bool(words) and PurePath(words[0]).name.lower() in _SSH_LIKE_PROGRAMS


def no_prompt_env(base: Mapping[str, str] | None = None, *, cwd: Path | None = None, clone: bool = False) -> dict[str, str]:
    """Build the subprocess environment for a non-interactive git contact.

    ``GIT_TERMINAL_PROMPT=0`` refuses any interactive credential prompt
    outright; the SSH ``BatchMode`` mirrors that refusal for the ssh(1)
    transport, which does not honor ``GIT_TERMINAL_PROMPT`` on its own
    (NFR-002).

    The user's own transport choice is never overridden (git gives the
    ``GIT_SSH_COMMAND`` environment variable precedence over ``core.sshCommand``
    and ``GIT_SSH``). The effective command is the pre-set ``GIT_SSH_COMMAND``,
    else ``core.sshCommand`` read in *cwd*, else (when ``GIT_SSH`` is set) none:
    ``GIT_SSH_COMMAND`` is then left unset and the prompt refusal plus the
    caller's timeout bound the contact. Otherwise the default is plain ``ssh``.
    ``-o BatchMode=yes`` is appended only to an ssh-like effective command that
    does not already carry ``BatchMode``.

    Args:
        base: Environment to extend; ``None`` uses ``os.environ``.
        cwd: Directory whose git config is read for ``core.sshCommand``;
            ``None`` uses the process working directory.
        clone: The contact is a clone, which reads no repository's local
            config: only the global and system ``core.sshCommand`` apply.
    """
    source = os.environ if base is None else base
    env = dict(source)
    env["GIT_TERMINAL_PROMPT"] = "0"
    command = source.get("GIT_SSH_COMMAND", "").strip() or _configured_ssh_command(None if clone else (cwd or Path.cwd()))
    if command is None and source.get("GIT_SSH", "").strip():
        return env
    command = command or _DEFAULT_SSH_PROGRAM
    if _is_ssh_like(command) and _BATCH_MODE not in command:
        command = f"{command} -o {_BATCH_MODE}=yes"
    env["GIT_SSH_COMMAND"] = command
    return env


class RemoteUnreachable(GitCommandError):
    """A remote could not be asked: timeout, transport failure or non-zero exit.

    Carries the remote name plus the argv and stderr of the failed command.
    """

    def __init__(self, remote: str, cause: GitCommandError) -> None:
        super().__init__(argv=cause.argv, cwd=cause.cwd, returncode=cause.returncode, stderr=cause.stderr, timed_out=cause.timed_out)
        self.remote = remote
        stderr = cause.stderr.strip()
        detail = stderr.splitlines()[0] if stderr else ("timed out" if cause.timed_out else "no error output")
        self.args = (f"remote {remote} unreachable: {detail}",)

    def __str__(self) -> str:
        return str(self.args[0])


def _config_value(cwd: Path, key: str) -> str | None:
    """Read one git config key; ``None`` when unset (exit 1)."""
    result = run_git(cwd, "config", "--get", key, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", "replace").strip() or None


def resolve_remote(cwd: Path, branch: str) -> str | None:
    """Name the remote that owns *branch* (FR-017); local config reads only, no network.

    Order: ``branch.<branch>.remote`` (``.`` means "this repository" and is
    treated as unset), then the only configured remote, then ``origin``;
    ``None`` when none applies (no remotes, or several none of which is ``origin``).
    """
    configured = _config_value(cwd, f"branch.{branch}.remote")
    if configured and configured != _LOCAL_REMOTE:
        return configured
    listed = run_git(cwd, "remote", check=False)
    if listed.returncode != 0:
        return None
    remotes = [line.strip() for line in listed.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
    if len(remotes) == 1:
        return remotes[0]
    if _DEFAULT_REMOTE in remotes:
        return _DEFAULT_REMOTE
    return None


def tracking_ref(remote: str, branch: str) -> str:
    """Return the remote-tracking ref ``refs/remotes/<remote>/<branch>``."""
    return f"refs/remotes/{remote}/{branch}"


def _contact(cwd: Path, remote: str, timeout: float, *args: str) -> GitResult:
    """Run one remote-contacting command; any failure becomes :class:`RemoteUnreachable`."""
    try:
        return run_git(cwd, *args, env=no_prompt_env(cwd=cwd), timeout=timeout)
    except GitCommandError as exc:
        raise RemoteUnreachable(remote, exc) from exc


def remote_heads(cwd: Path, remote: str, branches: Sequence[str], *, timeout: float = LS_REMOTE_TIMEOUT) -> dict[str, str]:
    """Return ``{branch: sha}`` for the listed branches that exist on *remote*.

    One ``ls-remote --heads`` call; exact ``refs/heads/<b>`` match only; absent
    branches are omitted. Empty *branches* returns ``{}`` without contacting.

    Raises:
        RemoteUnreachable: the remote could not be asked (never returns ``{}`` for that).
    """
    if not branches:
        return {}
    wanted = {f"refs/heads/{name}": name for name in branches}
    result = _contact(cwd, remote, timeout, "ls-remote", "--heads", remote, *wanted)
    heads: dict[str, str] = {}
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        sha, _, ref = line.partition("\t")
        if ref in wanted:
            heads[wanted[ref]] = sha.strip()
    return heads


def fetch_branches(cwd: Path, remote: str, branches: Sequence[str], *, timeout: float = FETCH_TIMEOUT) -> None:
    """Fetch *branches* into ``refs/remotes/<remote>/<b>``; never writes ``refs/heads``.

    Uses explicit forced refspecs, ``--no-tags`` and ``--no-recurse-submodules`` (a submodule fetch would contact
    further remotes). Empty *branches* does not contact.

    Raises:
        RemoteUnreachable: the fetch failed or timed out.
    """
    if not branches:
        return
    refspecs = [f"+refs/heads/{name}:{tracking_ref(remote, name)}" for name in branches]
    _contact(cwd, remote, timeout, "fetch", "--no-tags", "--no-recurse-submodules", remote, *refspecs)


@dataclass(frozen=True)
class Divergence:
    """Commits unique to each side of a ``local...remote`` comparison."""

    ahead: int
    behind: int

    @property
    def diverged(self) -> bool:
        """``True`` when both sides carry commits the other lacks."""
        return self.ahead > 0 and self.behind > 0


def divergence(cwd: Path, local: str, remote_ref: str, *, paths: Sequence[str] = ()) -> Divergence:
    """Count commits ahead/behind between *local* and *remote_ref* (``rev-list --left-right --count``).

    Left of ``local...remote_ref`` is *ahead* (only on *local*), right is *behind*.
    With *paths*, only commits touching them count; then ``ahead`` is not a
    statement about the whole branch and is meaningful only unscoped.
    """
    argv = ["rev-list", "--left-right", "--count", f"{local}...{remote_ref}"]
    if paths:
        argv.extend(["--", *paths])
    out = run_git(cwd, *argv).stdout.decode("utf-8", "replace").split()
    return Divergence(ahead=int(out[0]), behind=int(out[1]))


def describe_remote_head(cwd: Path, remote: str, *, timeout: float = LS_REMOTE_TIMEOUT) -> str | None:
    """Return *remote*'s default branch (``remote show`` ``HEAD branch:``), or ``None`` when unknown.

    A failed contact yields ``None`` (unknown), which the policy caller treats as such.
    """
    try:
        result = run_git(cwd, "remote", "show", remote, env=no_prompt_env(cwd=cwd), timeout=timeout)
    except GitCommandError:
        return None
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        if "HEAD branch:" in line:
            return line.rsplit(":", 1)[1].strip() or None
    return None


def clone_repository(
    url: str,
    dest: Path,
    *,
    branch: str | None = None,
    depth: int | None = None,
    timeout: float = CLONE_TIMEOUT,
    env: Mapping[str, str] | None = None,
) -> GitResult:
    """Run a bounded ``git clone <url> <dest>``; the caller reads ``returncode``/``stderr``.

    With no *branch* or *depth* the argv is exactly ``clone <url> <dest>``, as the
    doctrine git source builds it today, and it runs from the process cwd so
    relative paths resolve the same way. Unlike that source it adds SSH
    ``BatchMode`` (see :func:`no_prompt_env`) and a finite *timeout*; a timeout
    raises :class:`GitCommandError` even though ``check`` is off, so a caller
    must keep its own error path for it.
    """
    argv = ["clone"]
    if branch is not None:
        argv.extend(["--branch", branch])
    if depth is not None:
        argv.extend(["--depth", str(depth)])
    argv.extend([url, str(dest)])
    # Run from the process cwd: a relative *url* or *dest* resolves exactly as it
    # does for the doctrine git source's inherited cwd (no ``-C``).
    return run_git(Path.cwd(), *argv, env=no_prompt_env(env, clone=True), timeout=timeout, check=False)


def fetch_tags(cwd: Path, remote: str, *, timeout: float = FETCH_TIMEOUT, env: Mapping[str, str] | None = None) -> GitResult:
    """Run a bounded ``git fetch --tags <remote>``; the caller reads ``returncode``/``stderr``.

    Adds SSH ``BatchMode`` and a finite *timeout* to the argv the doctrine git
    source runs today; a timeout raises :class:`GitCommandError` despite ``check`` being off.
    """
    return run_git(cwd, "fetch", "--tags", remote, env=no_prompt_env(env, cwd=cwd), timeout=timeout, check=False)
