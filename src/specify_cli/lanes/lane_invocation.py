"""Lane test invocation and probe: where a lane's tests load their code from.

The single authority (mission lane-code-verification, #7547) that:

1. builds the **lane test invocation** -- the working directory, the declared
   test command template (passed in by callers, never read here), and the
   environment changes -- for a lane or write checkout;
2. **probes** it: a child process started with exactly that working directory
   and environment reports where each git-tracked regular package under
   ``<root>/src`` would load from, giving ``verified`` (inside ``<root>/src``),
   ``foreign`` (elsewhere: the #1907 case) or ``unverified`` (cannot tell);
3. captures an **evidence tree** (path, HEAD, dirty flag, probe) through
   :mod:`kernel.git`;
4. decides path containment portably (:func:`origin_inside`).

This is a leaf module: it imports only the standard library, :mod:`kernel.git`,
:mod:`kernel.paths` and :mod:`specify_cli.lanes.lane_env`. The probe never
raises; every failure becomes an ``unverified`` result with a bounded reason.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import MappingProxyType, ModuleType
from typing import Any, Final

from kernel.git import GitCommandError, run_git, status_entries, tracked_paths
from kernel.paths import is_windows
from specify_cli.lanes.lane_env import lane_test_env

__all__ = [
    "INTERPRETER_REDIRECT_KEYS",
    "EvidenceTree",
    "LaneTestInvocation",
    "ProbeResult",
    "ProbeStatus",
    "build_lane_test_invocation",
    "capture_evidence_tree",
    "lane_interpreter",
    "origin_inside",
    "probe_lane_imports",
    "run_environment",
]

# Variables that redirect which interpreter or which install a test run uses.
# Inherited from the repository root checkout they make a lane's tests load
# the root's code (#2803, #7554). Removed before the lane's own settings apply.
# Moved here from ``pre_review_gate._UV_ENV_LEAK_KEYS`` (mission #7547, WP03).
INTERPRETER_REDIRECT_KEYS: Final[tuple[str, ...]] = ("PYTHONPATH", "UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV")

_PYTHONPATH: Final[str] = "PYTHONPATH"
_PATH: Final[str] = "PATH"
_SOURCE_DIR: Final[str] = "src"
_PACKAGE_PATHSPEC: Final[str] = "src/*/__init__.py"
_PACKAGE_PATH_SEGMENTS: Final[int] = 3
_REASON_MAX_CHARS: Final[int] = 200
_DEFAULT_TIMEOUT_S: Final[float] = 5.0
_GIT_TIMEOUT_S: Final[float] = 10.0
_NO_PACKAGES_REASON: Final[str] = "no tracked source-layout packages to probe"

# Runs in the child: resolve each named package without executing it. ``-c``
# puts the working directory first on ``sys.path``; drop it so a package in the
# lane root never shadows ``<lane>/src`` (what ``-P`` does, on every Python).
_PROBE_SCRIPT: Final[str] = """\
import importlib.util, json, sys
if sys.path and sys.path[0] == "":
    del sys.path[0]
out = {}
for name in sys.argv[1:]:
    try:
        spec = importlib.util.find_spec(name)
    except Exception:
        spec = None
    origin = None
    if spec is not None:
        origin = spec.origin
        if origin is None and spec.submodule_search_locations:
            origin = list(spec.submodule_search_locations)[0]
    out[name] = origin
print(json.dumps(out))
"""

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class ProbeStatus(StrEnum):
    """What the probe could establish about the lane's source packages."""

    VERIFIED = "verified"
    FOREIGN = "foreign"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class ProbeResult:
    """Observed origin of each probed package and the verdict drawn from it."""

    status: ProbeStatus
    origins: tuple[tuple[str, str | None], ...]
    foreign: tuple[str, ...]
    reason: str | None
    interpreter: str | None

    def to_dict(self) -> dict[str, Any]:
        """The JSON shape of ``contracts/lane-test-invocation.md``."""
        return {
            "status": self.status.value,
            "origins": dict(self.origins),
            "foreign": list(self.foreign),
            "reason": self.reason,
            "interpreter": self.interpreter,
        }


@dataclass(frozen=True)
class LaneTestInvocation:
    """How a lane's tests are run: working directory, command, environment changes.

    ``environ(base)`` is *base* minus :attr:`env_unset`, then plus :attr:`env_set`,
    with :attr:`path_prepend` put in front of ``PATH`` (see :func:`run_environment`).
    Never persisted: each surface re-derives it.
    """

    cwd: Path
    command: str | None
    env_set: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    env_unset: tuple[str, ...] = INTERPRETER_REDIRECT_KEYS
    path_prepend: tuple[str, ...] = ()
    probe: ProbeResult | None = None

    def with_probe(self, probe: ProbeResult) -> LaneTestInvocation:
        """A copy carrying *probe*."""
        return dataclasses.replace(self, probe=probe)

    def to_dict(self) -> dict[str, Any]:
        """The JSON shape of ``contracts/lane-test-invocation.md``."""
        return {
            "cwd": str(self.cwd),
            "command": self.command,
            "env_set": dict(self.env_set),
            "env_unset": list(self.env_unset),
            "path_prepend": list(self.path_prepend),
            "probe": self.probe.to_dict() if self.probe is not None else None,
        }


@dataclass(frozen=True)
class EvidenceTree:
    """The tree a verdict was produced in: path, HEAD, dirty flag and probe."""

    path: str
    head: str | None
    dirty: bool | None
    probe: ProbeResult

    def to_dict(self) -> dict[str, Any]:
        """The JSON shape of ``contracts/pre-review-evidence-tree.md``."""
        return {"path": self.path, "head": self.head, "dirty": self.dirty, "probe": self.probe.to_dict()}


def _source_packages(root: Path) -> tuple[str, ...]:
    """Names of the git-tracked regular packages directly under ``<root>/src``."""
    try:
        paths = tracked_paths(root, pathspecs=[_PACKAGE_PATHSPEC], glob=True, timeout=_GIT_TIMEOUT_S)
    except GitCommandError:
        return ()
    names = {path.parts[1] for path in paths if len(path.parts) == _PACKAGE_PATH_SEGMENTS}
    return tuple(sorted(names))


def lane_interpreter(root: Path) -> Path | None:
    """The interpreter of the lane's own ``.venv``, when it has one."""
    venv = root / ".venv"
    python = venv / "Scripts" / "python.exe" if is_windows() else venv / "bin" / "python"
    return python if python.exists() else None


def _lane_identity_env(mission_slug: str | None, lane_id: str | None) -> dict[str, str]:
    if not mission_slug or not lane_id:
        return {}
    try:
        env: dict[str, str] = lane_test_env(mission_slug, lane_id)
    except ValueError:
        return {}
    return env


def build_lane_test_invocation(
    root: Path,
    *,
    command: str | None,
    mission_slug: str | None = None,
    lane_id: str | None = None,
) -> LaneTestInvocation:
    """Build the invocation a lane's (or write checkout's) tests run under.

    Args:
        root: The lane or write checkout root; the invocation's working directory.
        command: The declared test command template, verbatim (``{output_file}``
            is left for the caller to substitute), or ``None`` when unset.
        mission_slug: With *lane_id*, adds the lane test database name.
        lane_id: See *mission_slug*.

    A root with a ``.venv`` of its own gets that venv's script directory in
    front of ``PATH``, so a declared bare ``python`` or ``pytest`` runs the
    interpreter the probe checks, not one the caller's ``PATH`` points at.
    Otherwise ``PYTHONPATH=<root>/src`` is added when the root has tracked
    source packages.
    """
    env_set = _lane_identity_env(mission_slug, lane_id)
    interpreter = lane_interpreter(root)
    path_prepend: tuple[str, ...] = ()
    if interpreter is not None:
        path_prepend = (str(interpreter.parent),)
    elif _source_packages(root):
        env_set[_PYTHONPATH] = str(root / _SOURCE_DIR)
    return LaneTestInvocation(
        cwd=root,
        command=command,
        env_set=MappingProxyType(dict(sorted(env_set.items()))),
        env_unset=INTERPRETER_REDIRECT_KEYS,
        path_prepend=path_prepend,
    )


def run_environment(invocation: LaneTestInvocation, base: Mapping[str, str]) -> dict[str, str]:
    """The environment to run *invocation* with.

    *base* minus ``env_unset``, plus ``env_set``, with ``path_prepend`` in front
    of *base*'s ``PATH``. *base* is not mutated.
    """
    env = {key: value for key, value in base.items() if key not in invocation.env_unset}
    env.update(invocation.env_set)
    if invocation.path_prepend:
        inherited = env.get(_PATH)
        env[_PATH] = os.pathsep.join([*invocation.path_prepend, *([inherited] if inherited else [])])
    return env


def _bounded(reason: str) -> str:
    text = " ".join(reason.split())
    return text if len(text) <= _REASON_MAX_CHARS else text[: _REASON_MAX_CHARS - 3] + "..."


def _unverified(reason: str, interpreter: str | None, origins: tuple[tuple[str, str | None], ...] = ()) -> ProbeResult:
    return ProbeResult(
        status=ProbeStatus.UNVERIFIED,
        origins=origins,
        foreign=(),
        reason=_bounded(reason),
        interpreter=interpreter,
    )


def _run_probe_child(
    argv: list[str],
    invocation: LaneTestInvocation,
    env: dict[str, str],
    timeout: float,
    runner: Runner,
) -> tuple[dict[str, Any] | None, str | None]:
    """Run the probe child; return its parsed JSON object, or ``None`` and why not."""
    try:
        completed = runner(argv, cwd=str(invocation.cwd), env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"probe timed out after {timeout:g} s"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return None, f"probe could not run: {exc}"
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip().splitlines()
        return None, f"probe exited {completed.returncode}: {detail[-1] if detail else 'no error output'}"
    try:
        payload = json.loads(completed.stdout or "")
    except ValueError:
        return None, "probe printed no JSON"
    if not isinstance(payload, dict):
        return None, "probe printed JSON that is not an object"
    return payload, None


def _verdict(
    packages: tuple[str, ...],
    payload: Mapping[str, Any],
    source_root: Path,
    interpreter: str,
) -> ProbeResult:
    origins: tuple[tuple[str, str | None], ...] = tuple(
        (name, value if isinstance(value, str) else None) for name, value in ((name, payload.get(name)) for name in packages)
    )
    # Only a file path proves where code loads from; "frozen", "built-in" or a
    # namespace marker says nothing about a tree, so it is unverified, never foreign.
    located_files = {name: origin for name, origin in origins if origin is not None and os.path.isabs(origin)}
    foreign = tuple(name for name, origin in located_files.items() if not origin_inside(origin, source_root))
    if foreign:
        located = dict(origins)
        detail = ", ".join(f"{name} loads from {located[name]}" for name in foreign)
        return ProbeResult(
            status=ProbeStatus.FOREIGN,
            origins=origins,
            foreign=foreign,
            reason=_bounded(f"{detail}, outside {source_root}"),
            interpreter=interpreter,
        )
    missing = [name for name, origin in origins if origin is None]
    if missing:
        return _unverified(f"{', '.join(missing)} not importable from the lane environment", interpreter, origins)
    no_file = [name for name, _origin in origins if name not in located_files]
    if no_file:
        return _unverified(f"{', '.join(no_file)} has no file origin to check", interpreter, origins)
    return ProbeResult(status=ProbeStatus.VERIFIED, origins=origins, foreign=(), reason=None, interpreter=interpreter)


def probe_lane_imports(
    invocation: LaneTestInvocation,
    *,
    base_env: Mapping[str, str] | None = None,
    timeout: float = _DEFAULT_TIMEOUT_S,
    runner: Runner = subprocess.run,
) -> ProbeResult:
    """Report where the lane's tracked source packages load from under *invocation*.

    The child runs the lane's own venv interpreter when it has one, else this
    process's interpreter, with the working directory removed from ``sys.path``
    (like a console-script pytest) and ``importlib.util.find_spec`` (no package
    code executes). Never raises.
    """
    packages = _source_packages(invocation.cwd)
    if not packages:
        return _unverified(_NO_PACKAGES_REASON, None)
    interpreter = str(lane_interpreter(invocation.cwd) or Path(sys.executable))
    env = run_environment(invocation, base_env if base_env is not None else os.environ)
    argv = [interpreter, "-c", _PROBE_SCRIPT, *packages]
    payload, failure = _run_probe_child(argv, invocation, env, timeout, runner)
    if payload is None:
        return _unverified(failure or "probe failed", interpreter)
    return _verdict(packages, payload, invocation.cwd / _SOURCE_DIR, interpreter)


def _normalized(path: str, pathmod: ModuleType) -> str:
    text = pathmod.realpath(path) if pathmod is os.path else pathmod.normpath(path)
    return str(pathmod.normcase(text))


def origin_inside(
    origin: str | os.PathLike[str],
    root: str | os.PathLike[str],
    *,
    pathmod: ModuleType = os.path,
) -> bool:
    """Whether *origin* is *root* or lies below it, on a path-segment boundary.

    On the host flavour (``os.path``) both paths are resolved through symlinks;
    an injected foreign flavour (``ntpath`` / ``posixpath``) is normalized
    lexically, since resolving a foreign-OS path is meaningless.
    """
    candidate = _normalized(os.fspath(origin), pathmod)
    base = _normalized(os.fspath(root), pathmod).rstrip(pathmod.sep)
    return candidate == base or candidate.startswith(base + pathmod.sep)


def _head(root: Path) -> str | None:
    try:
        result = run_git(root, "rev-parse", "HEAD", check=False, timeout=_GIT_TIMEOUT_S)
    except GitCommandError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", "replace").strip() or None


def _dirty(root: Path) -> bool | None:
    try:
        return bool(status_entries(root, untracked="normal", optional_locks=False, timeout=_GIT_TIMEOUT_S))
    except GitCommandError:
        return None


def _relative_posix(path: Path, base: Path) -> str | None:
    try:
        return PurePosixPath(*path.relative_to(base).parts).as_posix()
    except ValueError:
        return None


def _display_path(root: Path, repo_root: Path | None) -> str:
    """*root* relative to *repo_root* (posix), lexically first, then through symlinks; else unchanged.

    Lexical first, so a venv interpreter that symlinks out of the tree keeps its
    in-tree name.
    """
    if repo_root is not None:
        lexical = _relative_posix(Path(os.path.abspath(root)), Path(os.path.abspath(repo_root)))
        if lexical is not None:
            return lexical
        try:
            resolved = _relative_posix(root.resolve(), repo_root.resolve())
        except OSError:
            resolved = None
        if resolved is not None:
            return resolved
    return str(root)


def _relative_reason(reason: str | None, repo_root: Path) -> str | None:
    """*reason* with the absolute *repo_root* prefix removed from every path in it."""
    if reason is None:
        return None
    prefixes = {os.path.abspath(repo_root)}
    with contextlib.suppress(OSError):
        prefixes.add(str(repo_root.resolve()))
    for prefix in sorted(prefixes, key=len, reverse=True):
        reason = reason.replace(prefix.rstrip(os.sep) + os.sep, "")
    return reason


def _display_optional(path: str | None, repo_root: Path | None) -> str | None:
    return None if path is None else _display_path(Path(path), repo_root)


def _recorded_probe(probe: ProbeResult, repo_root: Path | None) -> ProbeResult:
    """*probe* with paths under *repo_root* made relative, for the tracked status log."""
    if repo_root is None:
        return probe
    origins = tuple((name, _display_optional(origin, repo_root)) for name, origin in probe.origins)
    return dataclasses.replace(
        probe,
        origins=origins,
        interpreter=_display_optional(probe.interpreter, repo_root),
        reason=_relative_reason(probe.reason, repo_root),
    )


def capture_evidence_tree(root: Path, probe: ProbeResult, *, repo_root: Path | None = None) -> EvidenceTree:
    """Record the tree a verdict was produced in. Never raises.

    ``path``, and the probe's origins, interpreter and reason, are relative to *repo_root*
    (posix form) when they lie under it, else unchanged, so the tracked status log
    carries no machine paths it does not need; ``head`` and ``dirty`` are ``None``
    when git cannot say.
    """
    recorded = _recorded_probe(probe, repo_root)
    return EvidenceTree(path=_display_path(root, repo_root), head=_head(root), dirty=_dirty(root), probe=recorded)
