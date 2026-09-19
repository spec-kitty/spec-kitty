"""Helpers for canonical selector resolution and deprecated aliases.

Mission handle resolution
-------------------------
``resolve_mission_handle`` wraps :func:`~specify_cli.context.mission_resolver.resolve_mission`
and translates resolver exceptions into user-facing error messages.  Call it
after obtaining a raw ``--mission`` / ``--feature`` flag value and before
performing any kitty-specs directory access.

Example::

    from specify_cli.cli.selector_resolution import resolve_mission_handle

    resolved = resolve_mission_handle(raw_handle, repo_root, json_mode=False)
    feature_dir = resolved.feature_dir
    mission_slug = resolved.mission_slug
"""

from __future__ import annotations

import json as _json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
import typer
from specify_cli.cli.console import err_console as _err_console

from specify_cli.context.mission_resolver import (
    AmbiguousHandleError,
    MissionNotFoundError,
    ResolvedMission,
    resolve_mission,
)
from specify_cli.core.paths import require_explicit_feature

_warned: set[tuple[int, str, str]] = set()
_direct_invocation_counter: int = 0


@dataclass(frozen=True, slots=True)
class SelectorResolution:
    """Resolved selector value plus metadata about how it was chosen."""

    canonical_value: str
    canonical_flag: str
    alias_used: bool
    alias_flag: str | None
    warning_emitted: bool

    def __post_init__(self) -> None:
        if self.alias_used and not self.alias_flag:
            raise ValueError("alias_flag is required when alias_used=True")
        if not self.alias_used and self.alias_flag is not None:
            raise ValueError("alias_flag must be None when alias_used=False")
        if not self.canonical_value.strip():
            raise ValueError("canonical_value must be non-empty")


def _doc_path_for(alias_flag: str) -> str:
    return {
        "--mission": "docs/migrations/mission-type-flag-deprecation.md",
    }[alias_flag]


def _emit_deprecation_warning(
    canonical_flag: str,
    alias_flag: str,
    suppress_env_var: str,
) -> bool:
    """Emit a single warning per CLI invocation for one canonical/alias pair.

    Inside a click invocation we key on the click context id so the same
    canonical/alias pair only warns once per command. Outside a click context
    (direct programmatic calls) we use a monotonically increasing counter
    instead of ``id(object())`` — the latter can collide because Python may
    reuse memory for short-lived temporaries, which would suppress the warning
    on the second back-to-back call.
    """

    global _direct_invocation_counter
    ctx = click.get_current_context(silent=True)
    if ctx is not None:
        invocation_id = id(ctx)
    else:
        _direct_invocation_counter += 1
        invocation_id = _direct_invocation_counter
    pair = (invocation_id, canonical_flag, alias_flag)
    if pair in _warned:
        return False
    if os.environ.get(suppress_env_var) == "1":
        return False

    _warned.add(pair)
    _err_console.print(f"[yellow]Warning:[/yellow] {alias_flag} is deprecated; use {canonical_flag}. See: {_doc_path_for(alias_flag)}")
    return True


def _normalize_selector(value: Any | None) -> str | None:
    """Normalize a parsed selector value to a non-empty string or ``None``.

    Typer-decorated command functions can leak ``OptionInfo`` sentinels when
    they are called directly from wrapper commands. Treat non-string values as
    unset so selector resolution fails deterministically instead of crashing on
    ``.strip()``.
    """

    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def resolve_selector(
    *,
    canonical_value: str | None,
    canonical_flag: str,
    alias_value: str | None,
    alias_flag: str,
    suppress_env_var: str,
    command_hint: str | None = None,
) -> SelectorResolution:
    """Resolve a canonical selector plus one deprecated alias."""

    canonical_norm = _normalize_selector(canonical_value)
    alias_norm = _normalize_selector(alias_value)

    if canonical_norm is None and alias_norm is None:
        try:
            require_explicit_feature(None, command_hint=command_hint or f"{canonical_flag} <value>")
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        raise typer.BadParameter("Selector value is required.")

    if canonical_norm and alias_norm and canonical_norm != alias_norm:
        raise typer.BadParameter(
            f"Conflicting selectors: {canonical_flag}={canonical_norm!r} "
            f"and {alias_flag}={alias_norm!r} were both provided with different values. "
            f"{alias_flag} is a hidden deprecated alias for {canonical_flag}; pass only {canonical_flag}."
        )

    if canonical_norm and alias_norm:
        warning_emitted = _emit_deprecation_warning(canonical_flag, alias_flag, suppress_env_var)
        return SelectorResolution(
            canonical_value=canonical_norm,
            canonical_flag=canonical_flag,
            alias_used=True,
            alias_flag=alias_flag,
            warning_emitted=warning_emitted,
        )

    if canonical_norm:
        return SelectorResolution(
            canonical_value=canonical_norm,
            canonical_flag=canonical_flag,
            alias_used=False,
            alias_flag=None,
            warning_emitted=False,
        )

    warning_emitted = _emit_deprecation_warning(canonical_flag, alias_flag, suppress_env_var)
    return SelectorResolution(
        canonical_value=alias_norm or "",
        canonical_flag=canonical_flag,
        alias_used=True,
        alias_flag=alias_flag,
        warning_emitted=warning_emitted,
    )


# ---------------------------------------------------------------------------
# Mission handle resolver (T036 / T037 / T038)
# ---------------------------------------------------------------------------


def resolve_mission_handle(
    handle: str,
    repo_root: Path,
    *,
    json_mode: bool = False,
) -> ResolvedMission:
    """Resolve a user-supplied mission handle to a canonical :class:`~specify_cli.context.mission_resolver.ResolvedMission`.

    Accepted input forms (priority order):

    1. Full 26-char ULID ``mission_id``
    2. 8-char ``mid8`` prefix
    3. Full slug with numeric prefix (e.g. ``"083-foo-bar"``)
    4. Human slug without prefix (e.g. ``"foo-bar"``)
    5. Numeric prefix alone (e.g. ``"083"``)

    On success the :class:`~specify_cli.context.mission_resolver.ResolvedMission`
    is returned. On human-output failure the appropriate error message is
    printed to *stderr* and :func:`sys.exit` is called with exit code 2. On
    JSON-output failure a structured envelope is printed to stdout and
    :func:`sys.exit` is called with exit code 1.

    Args:
        handle: Raw flag value from ``--mission`` or ``--feature``.
        repo_root: Absolute path to the repository root.
        json_mode: When ``True``, error payloads are emitted as JSON (for
            callers that pass ``--json``).

    Returns:
        The uniquely resolved mission.

    Raises:
        SystemExit: Exit 2 in human mode; exit 1 in JSON mode.
    """

    def _emit_json_error(
        *,
        error_code: str,
        message: str,
        data: dict[str, object] | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "success": False,
            "error_code": error_code,
            "error": message,
        }
        if data:
            payload.update(data)
        print(_json.dumps(payload))
        sys.exit(1)

    try:
        return resolve_mission(handle, repo_root)
    except AmbiguousHandleError as exc:
        if json_mode:
            details = exc.to_dict()
            _emit_json_error(
                error_code=str(details["error"]),
                message=str(exc),
                data={
                    "handle": exc.handle,
                    "candidates": details["candidates"],
                },
            )
        else:
            _err_console.print(str(exc))
        sys.exit(2)
    except MissionNotFoundError as exc:
        if json_mode:
            _emit_json_error(
                error_code="MISSION_NOT_FOUND",
                message=str(exc),
                data={"handle": exc.handle},
            )
        else:
            _err_console.print(
                f'[red]Error:[/red] No mission found for handle "{exc.handle}". Check that the handle is correct and that the mission exists in kitty-specs/.'
            )
        sys.exit(2)


def resolve_mission_dir_with_bare_modern_fold(
    handle: str,
    repo_root: Path,
    *,
    json_mode: bool = False,
) -> Path:
    """Resolve ``--mission`` to a directory, folding a bare human slug onto its
    composed ``<slug>-<mid8>`` primary dir FIRST (#4723).

    ``resolve_mission_handle`` (above) delegates to the identity resolver
    (:func:`~specify_cli.context.mission_resolver.resolve_mission`), which
    keys strictly on the stored ``mission_slug`` / ``mission_id`` and has no
    notion of the on-disk composed ``<slug>-<mid8>`` directory name a bare
    human slug may name before any coord worktree is materialized (#2050
    read mirror). For such a handle it falls through every priority rung to
    ``MissionNotFoundError`` -- even when the bare slug is genuinely
    AMBIGUOUS (matches more than one composed dir), which used to surface as
    a misleading ``MISSION_NOT_FOUND`` instead of the structured ambiguity
    error (#4723 / C-CTX-4 / C-009).

    This wrapper tries the shared bare-modern-slug primitive
    (:func:`~mission_runtime.placement_seam` -> the read-path resolver
    family) FIRST -- the SAME seam ``agent status`` / ``agent tasks``
    already consume (NFR-004) -- so an ambiguous bare slug raises
    :class:`~specify_cli.missions._read_path_resolver.MissionSelectorAmbiguous`,
    rendered here with the identical envelope shape ``resolve_mission_handle``
    uses for ``AmbiguousHandleError`` (a caller cannot tell which resolver
    caught the ambiguity from the output alone). Falls back to
    ``resolve_mission_handle`` untouched for every handle the read-path leg
    does not resolve to an existing directory (mid8 / ULID / numeric-prefix
    forms, and genuinely unknown handles).

    Args:
        handle: Raw flag value from ``--mission``.
        repo_root: Absolute path to the repository root.
        json_mode: When ``True``, error payloads are emitted as JSON.

    Returns:
        The resolved mission directory.

    Raises:
        SystemExit: Exit 2 in human mode; exit 1 in JSON mode (matches
            ``resolve_mission_handle``'s contract).
    """
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    try:
        legacy_dir = placement_seam(repo_root, handle).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    except MissionSelectorAmbiguous as exc:
        if json_mode:
            print(
                _json.dumps(
                    {
                        "success": False,
                        "error_code": exc.error_code,
                        "error": str(exc),
                        "handle": exc.handle,
                        "candidates": exc.candidates,
                    }
                )
            )
            sys.exit(1)
        _err_console.print(f"[red]Error:[/red] {exc}")
        sys.exit(2)
    if legacy_dir.exists():
        return legacy_dir
    # Explicit ``Path`` annotation: under the project's ``follow_imports =
    # "skip"`` mypy config, ``ResolvedMission.feature_dir`` (a same-package
    # but separately-checked module) resolves as ``Any`` here; the
    # annotation re-narrows it to the type it is actually declared as.
    resolved_dir: Path = resolve_mission_handle(handle, repo_root, json_mode=json_mode).feature_dir
    return resolved_dir
