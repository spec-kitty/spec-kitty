"""Shared infrastructure for the ``spec-kitty doctor`` command surface.

This module is the **single canonical home (H1, I-3)** for the cross-cutting
infrastructure every ``doctor`` sibling needs: the shared Rich ``console``
singleton, the root-resolution guard, and the module constants. The canonical
CLI JSON contract is re-exported from :mod:`specify_cli.cli.json_contract`. Extracting
it first (WP02, #2059) gives WP03–WP10 a stable surface to import, and removes
the dominant circular-import hazard: every module that emits output MUST use the
SAME :class:`rich.console.Console` instance, never re-instantiate one (a
per-module ``Console()`` breaks ``--json`` stdout cleanliness and the byte-pinned
doctrine-selections snapshot).

Import discipline (one-way graph, I-2): this module imports only the standard
library, Typer, the CLI JSON contract, core env helpers, and
:mod:`._profile_health_render` (for the ``console`` singleton). It must NEVER import a cluster sibling or ``doctor.py``.

Canonical console direction: ``console`` is instantiated exactly once in
:mod:`._profile_health_render` and re-exported here. ``doctor.py`` and every
extracted sibling import ``console`` from this module, so a single
:class:`~rich.console.Console` instance backs the whole surface.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal, overload

import typer

from specify_cli.cli.json_contract import (
    json_error as _json_error,
    json_output_guard as _json_output_guard,
)

from specify_cli.core.env import is_interactive, is_truthy

# The single Console() instance lives in _profile_health_render; re-export it so
# this module is the one import site for siblings while preserving one instance.
from ._profile_health_render import console as console

__all__ = [
    "console",
    "_CI_ENV_VARS",
    "_STARTED_AT_COLUMN",
    "_NOT_IN_PROJECT_MESSAGE",
    "_is_interactive_environment",
    "_json_output_guard",
    "_json_error",
    "_emit_not_in_project",
    "resolve_project_root_or_exit",
]

# CI env-vars that should force non-interactive behaviour even when stdin
# happens to be a TTY. Conservative list per WP04 Risks: a false positive
# here would block an operator from remediating in a real local shell, so
# only well-known names are included.
_CI_ENV_VARS = (
    "CI",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "BUILDKITE",
    "JENKINS_URL",
    "CIRCLECI",
)

#: Column header for the invocation/op start timestamp, reused across the
#: orphan/open/closed invocation tables rendered by ``spec-kitty doctor``.
_STARTED_AT_COLUMN = "Started At"
_NOT_IN_PROJECT_MESSAGE = "Not in a spec-kitty project"


def _is_interactive_environment() -> bool:
    """Return True iff stdin is a TTY AND no common CI env var is set.

    Matches the FR-023 contract: in CI / non-interactive environments,
    ``doctor sparse-checkout --fix`` must print a remediation pointer and
    exit non-zero rather than prompting.

    The interactivity base routes through the single ``is_interactive``
    authority (so ``SPEC_KITTY_NON_INTERACTIVE`` / ``SPEC_KITTY_FORCE_INTERACTIVE``
    are honored here too, #2912); the CI-env-var veto is layered on top so a CI
    run never prompts even if it happens to hold a TTY.
    """
    if not is_interactive():
        return False
    return all(not is_truthy(os.environ.get(var)) for var in _CI_ENV_VARS)


def _emit_not_in_project(json_output: bool) -> None:
    """Emit the not-in-project error on the channel the caller contracted for.

    Under ``--json`` the machine contract requires a JSON error object on stdout
    (never bare human prose), matching the ``skills`` exemplar frozen by
    ``test_doctor_skills_not_in_project_envelope_frozen``. Human callers get the
    Rich error line on the console instead. This is the single canonical
    renderer every ``doctor`` command routes its not-in-project guard through so
    the whole family honors ``--json`` identically (#4242).
    """
    if json_output:
        console.emit_json(_json_error("not_in_project", _NOT_IN_PROJECT_MESSAGE))
    else:
        console.print(f"[red]Error:[/red] {_NOT_IN_PROJECT_MESSAGE}")


@overload
def resolve_project_root_or_exit(resolver: Callable[[], Path | None], json_output: bool, *, exit_code: int = 1, allow_none: Literal[False] = False) -> Path: ...


@overload
def resolve_project_root_or_exit(resolver: Callable[[], Path | None], json_output: bool, *, exit_code: int = 1, allow_none: bool) -> Path | None: ...


def resolve_project_root_or_exit(resolver: Callable[[], Path | None], json_output: bool, *, exit_code: int = 1, allow_none: bool = False) -> Path | None:
    """Resolve through the caller's patchable seam or emit the doctor error.

    ``allow_none`` preserves mission-state's fixtures-only return; a raised
    resolver is always an error, even when fixtures permit an absent project.
    Each command retains its own failure exit code.
    """
    try:
        root = resolver()
    except Exception as exc:
        _emit_not_in_project(json_output)
        raise typer.Exit(exit_code) from exc
    if root is None and not allow_none:
        _emit_not_in_project(json_output)
        raise typer.Exit(exit_code)
    return root
