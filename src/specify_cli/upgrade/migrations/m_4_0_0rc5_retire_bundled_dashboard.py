"""Migration: remove what the retired bundled dashboard left in a project (#5530).

The bundled dashboard (``spec-kitty dashboard``, ``/spec-kitty.dashboard``) was
deleted. The global slash-command and command-skill installers already retire
command files that are no longer canonical, and the managed skill installer
retires the ``spk-admin-dashboard`` skill. This migration covers what those
installers never reach:

* legacy project-local ``spec-kitty.dashboard.md`` / ``.toml`` command files in
  every configured agent directory (written before commands were globalized);
* the daemon metadata file ``.kittify/.dashboard`` and the persisted preflight
  banner ``.kittify/preflight-warning.json``, both machine-written runtime state.

Every removal goes through the ownership guard: a command file is removed only
when it carries the package version marker, so a user file that reuses the name
is preserved with a diagnostic. The two runtime files are package-managed paths.

A dashboard server started by an older CLI runs until it is stopped, and
``.kittify/.dashboard`` is the only record of its PID. Before that file goes,
the migration stops the recorded process when its command line proves it is the
dashboard server. When it cannot (permission denied), it keeps the file and
warns with the PID and port, so the operator can stop it by hand.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import psutil

from specify_cli.asset_preservation import (
    AnyProver,
    CanonicalContentProver,
    ManagedPathProver,
    guard_destructive_removal,
)

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from .m_0_9_1_complete_lane_migration import get_agent_dirs_for_project

_COMMAND_FILENAMES = (
    "spec-kitty.dashboard.md",
    "spec-kitty.dashboard.prompt.md",
    "spec-kitty.dashboard.toml",
)
_DASHBOARD_META_RELPATH = ".kittify/.dashboard"
_RUNTIME_RELPATHS = (_DASHBOARD_META_RELPATH, ".kittify/preflight-warning.json")
_SERVER_MODULE = "specify_cli.dashboard"
_TERMINATE_TIMEOUT_S = 3.0


def _prover() -> AnyProver:
    return AnyProver((CanonicalContentProver(), ManagedPathProver(managed_relpaths=_RUNTIME_RELPATHS)))


@MigrationRegistry.register
class RetireBundledDashboardMigration(BaseMigration):
    """Remove the retired dashboard's command files and runtime state."""

    migration_id = "4.0.0rc5_retire_bundled_dashboard"
    description = "Remove the retired /spec-kitty.dashboard command and dashboard runtime files"
    target_version = "4.0.0rc5"

    def detect(self, project_path: Path) -> bool:
        """Return True if any retired dashboard file the package owns is still present.

        A preserved user file does not count, so it never re-triggers the migration.
        """
        prover = _prover()
        return any(prover.prove(path, project_path) is not None for path in _iter_retired_paths(project_path))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Always safe to apply; missing dirs are silently skipped."""
        del project_path  # every check happens per path inside apply()
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Remove every proven-owned retired dashboard file."""
        changes: list[str] = []
        errors: list[str] = []
        warnings: list[str] = []
        preserved: list[str] = []
        prover = _prover()

        for path in _iter_retired_paths(project_path):
            rel = path.relative_to(project_path).as_posix()
            if rel == _DASHBOARD_META_RELPATH:
                stopped, message = _stop_recorded_server(path, dry_run=dry_run)
                if message:
                    (changes if stopped else warnings).append(message)
                if not stopped:
                    preserved.append(str(path))
                    continue
            try:
                verdict = guard_destructive_removal(path, project_path, prover=prover, dry_run=dry_run)
            except OSError as exc:
                errors.append(f"Failed to remove {rel}: {exc}")
                continue
            if verdict.owned:
                changes.append(f"{'Would remove' if dry_run else 'Removed'} retired {rel}")
            else:
                warnings.append(verdict.diagnostic)
                preserved.append(str(path))

        if not changes and not errors and not preserved:
            changes.append("No retired dashboard files present")

        return MigrationResult(
            success=not errors,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
            preserved_paths=preserved,
        )


def _recorded_pid(meta_path: Path) -> int | None:
    """Return the PID on line 4 of ``.kittify/.dashboard`` (URL, port, token, PID)."""
    try:
        lines = [line.strip() for line in meta_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError):
        return None
    if len(lines) < 4:
        return None
    try:
        return int(lines[3])
    except ValueError:
        return None


def _recorded_port(meta_path: Path) -> str:
    try:
        lines = [line.strip() for line in meta_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError):
        return "unknown"
    return lines[1] if len(lines) >= 2 else "unknown"


def _stop_recorded_server(meta_path: Path, *, dry_run: bool) -> tuple[bool, str]:
    """Stop the dashboard server recorded in *meta_path*.

    Returns ``(may_remove_meta, message)``. The metadata file may go when no
    dashboard server is running under the recorded PID (none recorded, process
    gone, or the PID now belongs to another program) or when the server was
    stopped. It stays when a running server could not be stopped.
    """
    pid = _recorded_pid(meta_path)
    if pid is None:
        return True, ""
    try:
        process = psutil.Process(pid)
        if not any(_SERVER_MODULE in part for part in process.cmdline()):
            return True, ""
        if dry_run:
            return True, f"Would stop the running dashboard server (PID {pid})"
        process.terminate()
        try:
            process.wait(timeout=_TERMINATE_TIMEOUT_S)
        except psutil.TimeoutExpired:
            process.kill()
            process.wait(timeout=_TERMINATE_TIMEOUT_S)
    except psutil.NoSuchProcess:
        return True, ""
    except (psutil.AccessDenied, psutil.TimeoutExpired):
        return False, (
            f"A dashboard server from an older CLI may still be running (PID {pid}, port "
            f"{_recorded_port(meta_path)}) and could not be stopped; stop it by hand. "
            f"Kept {_DASHBOARD_META_RELPATH} as its only record."
        )
    return True, f"Stopped the running dashboard server (PID {pid})"


def _iter_retired_paths(project_path: Path) -> Iterator[Path]:
    for agent_root, subdir in get_agent_dirs_for_project(project_path):
        agent_dir = project_path / agent_root / subdir
        if not agent_dir.is_dir():
            continue
        for name in _COMMAND_FILENAMES:
            candidate = agent_dir / name
            if candidate.is_file():
                yield candidate
    for rel in _RUNTIME_RELPATHS:
        candidate = project_path / rel
        if candidate.is_file():
            yield candidate
