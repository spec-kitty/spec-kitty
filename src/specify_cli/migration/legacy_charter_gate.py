"""The CLI-root ``LEGACY_CHARTER_STATE`` gate (FR-011, #3732).

Every ``spec-kitty`` command except the exemptions below refuses to run on a
project (or the current checkout) that still carries the retired doctrine
layout. The one detection seam is
:func:`specify_cli.migration.legacy_charter_layout.detect_legacy_charter_layout`,
shared with the cutover upgrade migration, so the gate and the migration cannot
disagree about what "unmigrated" means.

Exempt (``contracts/cli.md`` "Unmigrated project"): ``upgrade`` (the remedy),
``init``, ``--version``, ``--help``, the git merge drivers (``merge-driver-*``:
git runs them inside the checkout being merged, which is the documented remedy
for a pre-upgrade lane) and the hook entry points (``live-work hook``,
``session-start``, ``session-stop``, ``commit-guard-hook``: git and harness
plumbing that must keep exiting 0; the rest of ``live-work`` is gated).

Cost (research/runtime-seams.md §3): the predicate's two ``stat`` calls and one
small read per checked root, plus an ``lstat`` per directory while finding the
checkout root. No subprocess, no ``charter.*`` import, and no YAML parse unless
the predicate's substring prefilter hits.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from kernel.charter_pack_paths import KITTIFY_DIRNAME

from specify_cli.migration.legacy_charter_layout import detect_legacy_charter_layout

__all__ = [
    "check_legacy_charter_layout",
    "current_checkout_root",
    "usage_errors_first",
]

#: The error code of the refusal (``contracts/errors.md``).
LEGACY_CHARTER_STATE = "LEGACY_CHARTER_STATE"

#: Top-level commands the gate never refuses.
EXEMPT_COMMANDS: frozenset[str] = frozenset({"upgrade", "init", "session-start", "session-stop", "commit-guard-hook"})
#: Hook entry points inside an otherwise gated group (AR-S3): only the harness
#: hook of ``live-work`` is plumbing; ``matrix``/``install``/``watch`` are gated.
_EXEMPT_COMMAND_PATHS: tuple[tuple[str, ...], ...] = (("live-work", "hook"),)
#: Prefix of the git merge-driver commands (all exempt).
_EXEMPT_PREFIX = "merge-driver-"
_HELP_FLAGS = frozenset({"--help", "-h"})
_VERSION_FLAGS = frozenset({"--version", "-v"})
_GIT_MARKER = ".git"
_REFUSAL_EXIT_CODE = 1

#: The refusal text (``contracts/cli.md`` "Unmigrated project (FR-011)").
_MESSAGE_HEAD = "This project uses the retired doctrine layout ({finding}).\nRun `spec-kitty upgrade` to migrate it."
_WORKTREE_SENTENCE = "In a lane worktree, upgrade the\nrepository root and merge the target into this lane (do not rebase)."
_MESSAGE_TAIL = "See docs/migrations/charter-pack-cutover.md."

#: ``(finding, in_checkout)``: the first finding, and whether it came from a
#: checkout that is not the main project root.
LegacyFinding = tuple[str, bool]


def render_legacy_charter_message(finding: str, *, in_checkout: bool) -> str:
    """Return the refusal text, with the worktree sentence only for a checkout finding."""
    head = _MESSAGE_HEAD.format(finding=finding)
    body = f"{head} {_WORKTREE_SENTENCE}" if in_checkout else head
    return f"Error ({LEGACY_CHARTER_STATE}): {body}\n{_MESSAGE_TAIL}"


def find_checkout_root(start: Path) -> Path | None:
    """Return the nearest directory at or above *start* holding a ``.git`` entry.

    A ``.git`` file (a worktree pointer) counts as well as a directory. No
    subprocess; ``None`` outside a git checkout.
    """
    for candidate in (start, *start.parents):
        if os.path.lexists(candidate / _GIT_MARKER):
            return candidate
    return None


def current_checkout_root() -> Path | None:
    """:func:`find_checkout_root` of the working directory; ``None`` when it cannot be read."""
    try:
        cwd = Path.cwd()
    except OSError:
        return None
    return find_checkout_root(cwd)


def _has_kittify_dir(root: Path) -> bool:
    return (root / KITTIFY_DIRNAME).is_dir()


def first_legacy_finding(project_root: Path, repo_root_checkout: Path | None) -> LegacyFinding | None:
    """Return the first legacy finding of *project_root*, then of *repo_root_checkout*.

    A root without a ``.kittify`` directory is not checked (an uninitialised
    project, the same early return as the schema gate). The checkout root is
    checked only when it differs from the project root.
    """
    if _has_kittify_dir(project_root):
        findings = detect_legacy_charter_layout(project_root)
        if findings:
            return findings[0], False
    if repo_root_checkout is None or _same_directory(repo_root_checkout, project_root) or not _has_kittify_dir(repo_root_checkout):
        return None
    findings = detect_legacy_charter_layout(repo_root_checkout)
    return (findings[0], True) if findings else None


def _same_directory(left: Path, right: Path) -> bool:
    try:
        return os.path.samefile(left, right)
    except OSError:
        return left == right


def _is_exempt_hook_path(argv: Sequence[str]) -> bool:
    positional = tuple(arg for arg in argv if not arg.startswith("-"))
    return any(positional[: len(path)] == path for path in _EXEMPT_COMMAND_PATHS)


def _is_exempt(invoked_subcommand: str | None, argv: Sequence[str]) -> bool:
    if invoked_subcommand is not None and (invoked_subcommand in EXEMPT_COMMANDS or invoked_subcommand.startswith(_EXEMPT_PREFIX)):
        return True
    if _is_exempt_hook_path(argv):
        return True
    if any(arg in _HELP_FLAGS for arg in argv):
        return True
    return bool(argv) and argv[0] in _VERSION_FLAGS


def check_legacy_charter_layout(
    project_root: Path,
    repo_root_checkout: Path | None,
    *,
    invoked_subcommand: str | None,
    argv: Sequence[str],
    before_refusal: Callable[[], None] | None = None,
) -> None:
    """Refuse the invocation with ``LEGACY_CHARTER_STATE`` when a checked root is unmigrated.

    *argv* is the command line after the program name. *before_refusal* runs
    only when the gate is about to refuse; the CLI root passes a check that lets
    Click report an unknown option first (exit 2), so a usage error is reported
    as one whatever the project state.

    Raises:
        SystemExit: code 1, after the refusal text is written to stderr.
    """
    if _is_exempt(invoked_subcommand, argv):
        return
    found = first_legacy_finding(project_root, repo_root_checkout)
    if found is None:
        return
    if before_refusal is not None:
        before_refusal()
    finding, in_checkout = found
    sys.stderr.write(render_legacy_charter_message(finding, in_checkout=in_checkout) + "\n")
    raise SystemExit(_REFUSAL_EXIT_CODE)


def _is_usage_error(exc: BaseException) -> bool:
    """Whether *exc* is a Click usage error (by class name: typer may vendor its own click)."""
    return any(cls.__name__ == "UsageError" for cls in type(exc).__mro__)


def _tokenize(command: Any, ctx: Any, args: list[str]) -> list[str]:
    """Run *command*'s option parser over *args* and return the positional rest.

    Only the tokenizer runs: no parameter is converted and no callback fires.
    """
    _opts, rest, _order = command.make_parser(ctx).parse_args(args=args)
    return list(rest)


def _resolve(group: Any, ctx: Any, args: list[str]) -> tuple[str | None, Any, list[str]]:
    """``group.resolve_command``, with an unknown command read as "nothing to probe".

    The legacy refusal, not "No such command", answers an unknown command: the
    gate names the project state first (a retired command name is usually
    typed on exactly such a project).
    """
    try:
        name, command, rest = group.resolve_command(ctx, args)
    except Exception as exc:  # noqa: BLE001 -- a usage error here is deliberately left to the refusal; see the docstring
        if _is_usage_error(exc):
            return None, None, []
        raise
    return name, command, list(rest)


def _probe_usage(root_ctx: Any, args: Sequence[str]) -> None:
    command, ctx = root_ctx.command, root_ctx
    remaining = _tokenize(command, ctx, list(args))
    while remaining and hasattr(command, "resolve_command"):
        name, command, remaining = _resolve(command, ctx, remaining)
        if command is None:
            return
        ctx = command.context_class(command, info_name=name, parent=ctx)
        remaining = _tokenize(command, ctx, remaining)


def usage_errors_first(root_ctx: Any, args: Sequence[str]) -> Callable[[], None]:
    """Return a ``before_refusal`` hook that raises the invocation's Click usage error, if any.

    It tokenizes *args* (the command line after the program name) down the
    command path: an unknown option raises the usage error Click would have
    raised (exit 2) instead of the legacy refusal. An unknown command and a
    missing argument are not reported here (the refusal answers them), and any
    other failure of the probe leaves the refusal to proceed.
    """

    def probe() -> None:
        try:
            _probe_usage(root_ctx, args)
        except Exception as exc:  # noqa: BLE001 -- only a usage error is re-raised; a probe failure must not mask the refusal
            if _is_usage_error(exc):
                raise

    return probe
