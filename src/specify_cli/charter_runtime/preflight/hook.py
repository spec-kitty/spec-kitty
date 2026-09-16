"""Session-start hook helpers (T023 / T024 / FR-006 caller contract).

These helpers implement the rules in
``contracts/charter-preflight-json.md`` § "Hook caller contract":

| Consumer                | passed=True   | passed=False                                     |
|-------------------------|---------------|--------------------------------------------------|
| spec-kitty next         | emit warnings + continue | print blocked_reason, exit 1, NO mutation |
| spec-kitty implement WP | emit warnings + continue | abort BEFORE worktree/.kittify writes     |
| dashboard serve / start | persist advisory + start | start server, persist blocked_reason       |

The helpers are intentionally CLI-side (typer-aware): they are the shared
glue between the three consumer entry points and ``run_charter_preflight``.
The runner itself stays framework-free.

Boundary heal caveat (WP04, charter-synthesize-reconciliation-01KZJQN6): when
``cfg.auto_refresh`` is set, ``run_charter_preflight`` attempts a
non-destructive heal (``SynthesizeMode.preserve`` — never drops backed
content) before falling through to the ``passed=False`` branch below. That
non-destructive guarantee is not a "never refuses" guarantee: orphaned
(backing-artifact-deleted) content and an unparseable on-disk doctrine
overlay still make the heal fail. When that happens it surfaces here exactly
like any other preflight failure — printed ``blocked_reason`` + exit 1 (or,
for the dashboard, a warning banner), never a silently-coerced ``passed=True``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, TextIO

import typer

from specify_cli.charter_runtime.preflight.ambient_warning import (
    dedupe_warnings,
    record_surfaced,
    render_ambient_warning,
    warning_already_surfaced,
)
from specify_cli.charter_runtime.preflight.config import load_preflight_config
from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

__all__ = [
    "emit_advisory_warnings",
    "run_preflight_or_abort",
    "run_preflight_for_dashboard",
]


_logger = logging.getLogger(__name__)


def run_charter_preflight(**kwargs: Any) -> CharterPreflightResult:
    """Patchable lazy wrapper for the framework-free preflight runner."""
    from specify_cli.charter_runtime.preflight.runner import run_charter_preflight as _run

    return _run(**kwargs)


def emit_advisory_warnings(
    result: CharterPreflightResult,
    *,
    stderr: TextIO | None = None,
    consumer: str = "charter preflight",
    repo_root: Path | None = None,
) -> None:
    """Render passed advisory warnings on stderr without polluting JSON stdout.

    #3971: each distinct ambient warning is surfaced at most once per
    command run (process lifetime) — a repeated hook invocation in the same
    process prints the duplicate no more — and the single surfaced instance
    carries its scope (the consumer that ran preflight and the repo root
    the condition was computed against). The warning text itself carries
    the concrete remedy (an exact recovery command).

    Args:
        result: The preflight result whose ``warnings`` are advisory notes.
        stderr: Optional stream override (mostly for tests). Defaults to
            ``sys.stderr``.
        consumer: Human-readable consumer name for the scope suffix, e.g.
            ``"next"`` or ``"implement"``.
        repo_root: The repository root preflight ran against, for the scope
            suffix. ``None`` renders as ``<unresolved>``.
    """
    err = stderr if stderr is not None else sys.stderr
    for warning in dedupe_warnings(list(result.warnings)):
        if warning_already_surfaced(warning):
            continue
        record_surfaced(warning)
        print(render_ambient_warning(warning, consumer=consumer, repo_root=repo_root), file=err)


def run_preflight_or_abort(
    repo_root: Path,
    *,
    consumer: str,
    stderr: TextIO | None = None,
) -> CharterPreflightResult:
    """Run charter preflight; abort the process if it fails.

    Shared implementation for ``spec-kitty next`` (T023) and
    ``spec-kitty implement`` (T024). Both consumers behave identically on
    failure: print ``blocked_reason`` and exit with code 1, with **no
    state mutation** (no worktree allocation, no ``.kittify/`` writes,
    no event-log appends).

    Args:
        repo_root: Repository root used to load the config flag and to
            resolve ``.kittify/charter/`` / ``.kittify/doctrine/`` paths.
        consumer: Human-readable consumer name for log lines, e.g.
            ``"next"`` or ``"implement"``. Used only for observability.
        stderr: Optional stream override (mostly for tests). Defaults to
            ``sys.stderr``.

    Returns:
        The :class:`CharterPreflightResult` when ``passed`` is ``True``.

    Raises:
        typer.Exit: Exit code 1 when ``passed`` is ``False``.
    """
    cfg = load_preflight_config(repo_root)
    if not cfg.enabled:
        _logger.info("charter preflight disabled by project config (consumer=%s)", consumer)
        return CharterPreflightResult(passed=True, checks=[])

    result = run_charter_preflight(
        repo_root=repo_root,
        auto_refresh=cfg.auto_refresh,
        allow_missing_charter=True,
        strict=False,
    )

    if result.passed:
        emit_advisory_warnings(result, stderr=stderr, consumer=consumer, repo_root=repo_root)
        _logger.info("charter preflight passed (consumer=%s)", consumer)
        return result

    err = stderr if stderr is not None else sys.stderr
    reason = result.blocked_reason or "charter preflight failed"
    print(f"Error: {reason}", file=err)
    raise typer.Exit(1)


def run_preflight_for_dashboard(repo_root: Path) -> CharterPreflightResult:
    """Run charter preflight without aborting; dashboard always starts.

    Implements the dashboard side of the caller contract (T025): the
    server is allowed to come up even when preflight fails, but the
    ``blocked_reason`` MUST be surfaced to the SPA so the operator sees a
    critical banner instead of silently consuming stale doctrine.

    Args:
        repo_root: Repository root used to load the config flag.

    Returns:
        The :class:`CharterPreflightResult`. Callers inspect
        ``result.passed`` / ``result.blocked_reason`` directly.
    """
    cfg = load_preflight_config(repo_root)
    if not cfg.enabled:
        _logger.info("charter preflight disabled by project config (consumer=dashboard)")
        return CharterPreflightResult(passed=True, checks=[])

    result = run_charter_preflight(
        repo_root=repo_root,
        auto_refresh=cfg.auto_refresh,
        allow_missing_charter=True,
        strict=False,
    )
    if result.passed:
        _logger.info("charter preflight passed (consumer=dashboard)")
    else:
        _logger.warning(
            "charter preflight failed (consumer=dashboard): %s",
            result.blocked_reason,
        )
    return result
