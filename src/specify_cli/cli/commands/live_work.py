"""live-work — Live Work harness capture commands (spec-kitty#4268).

``spec-kitty live-work hook <harness>`` is the command registered in each
harness's native hook configuration: the harness pipes one event's JSON on
stdin, the adapter maps it to observations, and the publisher offers each
as a live relay frame through the existing path. It **always exits 0**
(the harness invocation must never fail because capture did) and is
hard-bounded by the client budget machinery (``budget.bound_stdout``: the
process exits within the 4 s hook budget whatever it is doing). Because
the harness runs this synchronously around every tool call, the invocation
takes the ``next`` command's startup fast path (#4353 fix round): only the
live-work group is registered, and neither the global runtime bootstrap
nor the startup project gates (whose schema gate may ``SystemExit``)
run — so the budget is armed against the capture work itself, not a
~12 s command-registry import that preceded it.

``spec-kitty live-work matrix`` prints the executable capability matrix;
``install``/``uninstall`` manage the harness hook registrations;
``watch`` is the one-shot labeled changed-file fallback.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import typer

from specify_cli.core.env import moment_handlers_disabled_reason

logger = logging.getLogger(__name__)

app = typer.Typer(help="Live Work harness capture: tools, files, tests and delegation as live relay frames (spec-kitty#4268).")


def _read_stdin_payload() -> dict[str, object] | None:
    """Read one JSON payload from stdin; ``None`` when absent/invalid.

    Mirrors the harness-payload posture of ``cli/commands/lint.py``: a tty
    or empty stdin is a benign no-op, never an error.
    """
    if sys.stdin.isatty():
        return None
    raw = sys.stdin.read().strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _find_repo_root(start: Path | None = None) -> Path:
    """The nearest ancestor with a ``.git`` entry, else the cwd."""
    cursor = Path(start or Path.cwd()).resolve()
    if (cursor / ".git").exists():
        return cursor
    for ancestor in cursor.parents:
        if (ancestor / ".git").exists():
            return ancestor
    return cursor


@app.command(name="hook")
def hook_command(
    harness: str = typer.Argument(..., help="The harness whose hook fired (claude / codex)."),
    verbose: bool = typer.Option(False, "--verbose", help="Print the publish report to stderr."),
) -> None:
    """Handle one harness hook event (JSON on stdin) and publish live frames.

    Exit 0 always — capture must never fail the harness invocation.
    """
    from specify_cli.zeitgeist_client.budget import HOOK_BUDGET_S, bound_stdout, disarm

    bound_stdout(HOOK_BUDGET_S)
    try:
        _run_hook(harness, verbose)
    except Exception as exc:  # the exit-0 guarantee is this command's contract
        logger.debug("live-work hook %s swallowed: %s", harness, exc)
    finally:
        disarm()


def _run_hook(harness: str, verbose: bool) -> None:
    from specify_cli.live_work.adapters import get_adapter
    from specify_cli.live_work.coalesce import BurstCoalescer
    from specify_cli.live_work.publisher import publish_observations

    if moment_handlers_disabled_reason() is not None:
        # The same kill switch that silences the moment handlers silences
        # live-work capture: one switch, one meaning.
        return
    adapter = get_adapter(harness)
    if adapter is None:
        return
    payload = _read_stdin_payload()
    if payload is None:
        return
    repo_root = _find_repo_root(Path(str(payload.get("cwd") or Path.cwd())))
    observations = adapter.parse(payload, repo_root=repo_root)
    if not observations:
        return
    coalescer = BurstCoalescer()
    frames = [frame for observation in observations for frame in coalescer.offer(observation).frames]
    frames.extend(coalescer.flush_all())
    if not frames:
        return
    report = publish_observations(frames, cwd=repo_root)
    if verbose:
        print(json.dumps(report.as_dict()), file=sys.stderr)


@app.command(name="matrix")
def matrix_command(
    allow_degraded: bool = typer.Option(False, "--allow-degraded", help="Exit 0 even when a configured harness has no capture hooks."),
) -> None:
    """Print the executable capability matrix (rows + health + codec state).

    Exits non-zero when a harness configured in this project has no Live
    Work hooks installed — the no-silent-green enforcement.
    """
    from specify_cli.core.agent_config import load_agent_config
    from specify_cli.live_work.capability import CapabilityMatrix

    repo_root = _find_repo_root()
    matrix = CapabilityMatrix(repo_root)
    configured: frozenset[str] = frozenset()
    try:
        config = load_agent_config(repo_root)
        configured = frozenset(config.available)
    except Exception as exc:
        logger.debug("agent config unreadable: %s", exc)
    payload = matrix.as_dict()
    payload["configured_harnesses"] = sorted(configured)
    degraded = matrix.degraded_harnesses(configured)
    payload["degraded_harnesses"] = degraded
    print(json.dumps(payload, indent=2))
    if degraded and not allow_degraded:
        raise typer.Exit(code=1)


@app.command(name="install")
def install_command(
    harness: str = typer.Argument(..., help="The harness to install capture hooks for (claude / codex)."),
) -> None:
    """Register the Live Work capture hooks in the harness's native config."""
    from specify_cli.live_work.install import install_hooks

    outcome = install_hooks(harness, _find_repo_root())
    print(outcome.detail)
    if not outcome.installed:
        raise typer.Exit(code=1)


@app.command(name="uninstall")
def uninstall_command(
    harness: str = typer.Argument(..., help="The harness to remove capture hooks for (claude / codex)."),
) -> None:
    """Remove the Live Work capture hooks (sibling hooks are untouched)."""
    from specify_cli.live_work.install import uninstall_hooks

    outcome = uninstall_hooks(harness, _find_repo_root())
    print(outcome.detail)


@app.command(name="watch")
def watch_command(
    verbose: bool = typer.Option(False, "--verbose", help="Print the publish report to stderr."),
) -> None:
    """One-shot labeled changed-file observation (sampled fallback).

    Emits sampled file-change frames for the working tree's uncommitted
    changes — changed files only, explicitly labeled: no attribution to an
    agent, and file reads are never claimed.
    """
    from specify_cli.live_work.publisher import publish_observations
    from specify_cli.live_work.watcher import watch_changed_files

    repo_root = _find_repo_root()
    observations = watch_changed_files(repo_root)
    if not observations:
        return
    report = publish_observations(observations, cwd=repo_root)
    if verbose:
        print(json.dumps(report.as_dict()), file=sys.stderr)
