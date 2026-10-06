"""Shared, read-only Typer surface walker.

Walks a ``typer.Typer`` instance recursively and returns a deterministic
list of :class:`CommandPathEntry` records describing every command and
sub-group reachable from the root.

The walker is **strictly read-only**: it must never mutate the Typer
application or any descendant command/group object. Callers using this
walker to inspect the live ``specify_cli.app`` must set the relevant
environment variables (``SPEC_KITTY_ENABLE_SAAS_SYNC``,
``SPEC_KITTY_NO_UPGRADE_CHECK``) **before** importing ``specify_cli`` —
the walker itself does not enforce that, but the freshness / builder
scripts that consume it do.

Surface decisions match ``cli-audit-3-2.md``:

* Group naming preference: ``group.name`` then ``group.typer_instance.info.name``
  (mirrors ``tests/architectural/test_safety_registry_completeness.py``).
* Hidden detection: respects Typer's ``DefaultPlaceholder`` sentinels by
  falling back through (command attr ``hidden``) → (group attr ``hidden``)
  → (group's ``typer_instance.info.hidden``). A path under a hidden group
  is hidden too: ``--help`` never lists it.
* Deprecation detection: respects Typer's ``deprecated`` flag and a
  case-insensitive ``"Deprecated"`` prefix on the help summary.
* ``requires_saas_sync``: any path under ``tracker`` and the
  ``issue-search`` command depend on ``SPEC_KITTY_ENABLE_SAAS_SYNC=1`` at
  import time.

Determinism: results are sorted lexicographically by the ``path`` tuple
so two walks of the same app produce byte-identical output.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Literal

import typer
from typer.models import DefaultPlaceholder

__all__ = [
    "CommandPathEntry",
    "walk",
]


CommandKind = Literal["command", "group"]


@dataclass(frozen=True, slots=True)
class CommandPathEntry:
    """A single addressable Typer command path.

    Attributes:
        path: Tuple of name segments from the root. Empty tuple is invalid.
        kind: ``"command"`` for leaf commands; ``"group"`` for sub-typers.
        hidden: ``True`` if the command is hidden from ``--help`` output.
        deprecated: ``True`` if the command is marked deprecated (flag or
            help-text prefix).
        help_summary: First non-empty line of the help / short_help text,
            trimmed. ``""`` if no help is available.
        help_body: Full command help text, including callback docstrings that
            Typer resolves only when it builds the Click command. ``""`` if
            no help is available.
        source_file: File path of the registered callback, if discoverable
            via :func:`inspect.getsourcefile`. ``None`` otherwise.
        source_function: Qualified function name of the callback if
            discoverable. ``None`` otherwise.
        requires_saas_sync: ``True`` for paths that require
            ``SPEC_KITTY_ENABLE_SAAS_SYNC=1`` to be visible (currently the
            ``tracker`` subtree and the ``issue-search`` top-level command).
    """

    path: tuple[str, ...]
    kind: CommandKind
    hidden: bool
    deprecated: bool
    help_summary: str
    source_file: str | None
    source_function: str | None
    requires_saas_sync: bool
    help_body: str = ""


def _resolve_flag(*candidates: Any) -> bool:
    """Resolve a Typer flag, respecting :class:`DefaultPlaceholder` sentinels.

    Returns the first concrete (non-placeholder) truthy/falsy value.
    Falls back to ``False`` if all candidates are placeholders or None.
    """
    for value in candidates:
        if value is None:
            continue
        if isinstance(value, DefaultPlaceholder):
            continue
        return bool(value)
    return False


def _resolve_text(*candidates: Any) -> str:
    """Resolve a Typer text attribute (help, short_help, etc.).

    Returns the first concrete non-empty string. Falls back to ``""``.
    """
    for value in candidates:
        if value is None:
            continue
        if isinstance(value, DefaultPlaceholder):
            continue
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _summarize_help(help_text: str) -> str:
    """Return the first non-empty trimmed line of ``help_text``."""
    if not help_text:
        return ""
    for line in help_text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return help_text.strip()


def _is_saas_path(path: tuple[str, ...]) -> bool:
    """Return ``True`` if the path is gated by ``SPEC_KITTY_ENABLE_SAAS_SYNC``."""
    if not path:
        return False
    if path[0] == "tracker":
        return True
    return path == ("issue-search",)


def _callback_source(callback: Any) -> tuple[str | None, str | None]:
    """Try to resolve (file, qualified-name) for a Typer callback."""
    if callback is None:
        return (None, None)
    try:
        source_file = inspect.getsourcefile(callback)
    except (TypeError, OSError):
        source_file = None
    qualname = getattr(callback, "__qualname__", None) or getattr(
        callback, "__name__", None
    )
    return (source_file, qualname)


def walk(app: typer.Typer) -> list[CommandPathEntry]:
    """Walk a Typer app and return a deterministic list of ``CommandPathEntry``.

    The walk visits both ``registered_commands`` and ``registered_groups``
    recursively. Duplicates (same path + kind) are deduplicated, which is
    important because Typer can re-register the same sub-group in some
    initialization paths. Results are sorted by ``(path, kind)`` so the
    output is stable across runs.
    """
    out: list[CommandPathEntry] = []
    seen: set[tuple[tuple[str, ...], CommandKind]] = set()

    def _recurse(typer_app: typer.Typer, prefix: tuple[str, ...], parent_hidden: bool) -> None:
        for cmd in typer_app.registered_commands:
            name = cmd.name or (
                cmd.callback.__name__.replace("_", "-")
                if cmd.callback is not None
                else None
            )
            if not name:
                continue
            path = prefix + (name,)
            key: tuple[tuple[str, ...], CommandKind] = (path, "command")
            if key in seen:
                continue
            seen.add(key)
            # A command under a hidden group is not reachable from --help
            # either, so it inherits the group's hidden flag.
            hidden = parent_hidden or _resolve_flag(cmd.hidden)
            help_text = _resolve_text(cmd.help, cmd.short_help)
            callback_help = inspect.getdoc(cmd.callback) if cmd.callback else ""
            help_body = _resolve_text(cmd.help, callback_help, cmd.short_help)
            summary = _summarize_help(help_text)
            deprecated_flag = _resolve_flag(cmd.deprecated)
            deprecated_by_help = summary.lower().startswith("deprecated")
            src_file, src_func = _callback_source(cmd.callback)
            out.append(
                CommandPathEntry(
                    path=path,
                    kind="command",
                    hidden=hidden,
                    deprecated=deprecated_flag or deprecated_by_help,
                    help_summary=summary,
                    source_file=src_file,
                    source_function=src_func,
                    requires_saas_sync=_is_saas_path(path),
                    help_body=help_body,
                )
            )

        for grp in typer_app.registered_groups:
            gname = grp.name
            if not gname and grp.typer_instance is not None:
                gname = grp.typer_instance.info.name
            if not gname:
                continue
            path = prefix + (gname,)
            key = (path, "group")
            if key in seen:
                # Still recurse in case nested children differ — but Typer
                # always points at the same sub-typer, so children would
                # be deduped too. Skip to keep the walk O(N).
                continue
            seen.add(key)
            info_hidden = (
                grp.typer_instance.info.hidden if grp.typer_instance is not None else None
            )
            info_deprecated = (
                grp.typer_instance.info.deprecated
                if grp.typer_instance is not None
                else None
            )
            info_help = (
                grp.typer_instance.info.help
                if grp.typer_instance is not None
                else None
            )
            hidden = parent_hidden or _resolve_flag(grp.hidden, info_hidden)
            callback = grp.callback or (
                grp.typer_instance.info.callback
                if grp.typer_instance is not None
                else None
            )
            help_text = _resolve_text(grp.help, grp.short_help, info_help)
            callback_help = inspect.getdoc(callback) if callback else ""
            help_body = _resolve_text(
                grp.help, info_help, callback_help, grp.short_help
            )
            summary = _summarize_help(help_text)
            deprecated_flag = _resolve_flag(grp.deprecated, info_deprecated)
            deprecated_by_help = summary.lower().startswith("deprecated")
            src_file, src_func = _callback_source(callback)
            out.append(
                CommandPathEntry(
                    path=path,
                    kind="group",
                    hidden=hidden,
                    deprecated=deprecated_flag or deprecated_by_help,
                    help_summary=summary,
                    source_file=src_file,
                    source_function=src_func,
                    requires_saas_sync=_is_saas_path(path),
                    help_body=help_body,
                )
            )
            if grp.typer_instance is not None:
                _recurse(grp.typer_instance, path, hidden)

    _recurse(app, (), False)
    out.sort(key=lambda e: (e.path, e.kind))
    return out
