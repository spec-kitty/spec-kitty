"""The ledger-projection posture reader (a LOCAL, non-hosted concern).

The ledger flag (``.kittify/config.yaml`` → ``ledger.projection``) gates only
the *derived*, gitignored execution-state projection
(``status/views.py::refresh_execution_projection`` → ``.kittify/derived/<slug>/``).
It is explicitly NOT a hosted concern (ADR ``2026-09-26-3`` D-2/FR-010): the
committed lane/decision ledgers are never gated by it. This reader was split out
of the former ``core/hosted_posture.py`` when the hosted drain/relay surface was
removed from open-core (#6164); only the ledger posture survives, here, as a
local feature.

**Fail-open-to-default parsing**: an unparseable ``.kittify/config.yaml`` or a
present-but-non-boolean ``ledger.projection`` value counts as the default
(``True``) and emits a ``warnings.warn`` on every read (Python's default
filter dedups per call site, not per process), never crashes.

**No caching**: :func:`ledger_posture` opens the one small config file on every
call. There is no mtime cache and no frozen-at-import value.

**Call-site style (fixture effectiveness).** A caller MUST reach the reader
through the MODULE ATTRIBUTE (``from specify_cli.core import ledger_posture``
then ``ledger_posture.ledger_posture(...)``) so a test can monkeypatch the
``ledger_posture`` module attribute. A local binding via
``from specify_cli.core.ledger_posture import ledger_posture`` captures the
function object at import time and silently bypasses such a monkeypatch.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

from specify_cli.core.constants import KITTIFY_DIR
from specify_cli.core.paths import WorkspaceRootNotFound, locate_project_root, resolve_canonical_root

__all__ = [
    "LedgerPosture",
    "ledger_posture",
]

_REPO_CONFIG_RELATIVE = Path(".kittify") / "config.yaml"


@dataclass(frozen=True)
class LedgerPosture:
    """The resolved ledger-projection posture. Defaults to enabled."""

    enabled: bool
    source: str


def _walk_up_to_kittify_marker(start: Path) -> Path | None:
    """Walk up from *start* looking for a bare ``.kittify`` marker directory.

    Mirrors :func:`locate_project_root`'s tier-3 fallback, minus its tier-1
    ``SPECIFY_REPO_ROOT`` env-var override: that override is only correct for
    the "no explicit root at all, resolve from CWD" case
    (:func:`_resolve_repo_root`'s ``project_root is None`` branch) -- letting
    it hijack an EXPLICIT ``project_root`` here would mean an ambient
    ``SPECIFY_REPO_ROOT`` could silently redirect one repo's ledger read onto
    an unrelated directory. Git-worktree-following is already covered by
    :func:`specify_cli.core.paths.resolve_canonical_root`, tried first by the
    caller; this is only the ``.kittify``-only fallback tier for a project
    that predates or omits a ``.git`` directory.
    """
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / KITTIFY_DIR).is_dir():
            return candidate
    return None


def _resolve_repo_root(project_root: Path | None) -> Path | None:
    """Resolve the repository root a posture read should key ``.kittify/config.yaml``
    lookups off of.

    An explicit ``project_root`` is a caller-supplied *starting point*, not
    necessarily the repo root itself: a lifecycle envelope's ``cwd`` can be
    ``kitty-specs/<mission>/`` or ``.kittify/runtime/runs/<id>/``, and a
    ``<subdir>/.kittify/config.yaml`` never exists. Canonicalise it the same
    way every other repo-root consumer does -- walk up to the real repo root
    (and map a worktree to its main checkout) via
    :func:`specify_cli.core.paths.resolve_canonical_root`; when that git-based
    walk finds no repository (a project with ``.kittify`` but no ``.git``),
    fall back to a plain ``.kittify``-marker walk-up
    (:func:`_walk_up_to_kittify_marker`) that, unlike
    :func:`locate_project_root`, never lets an ambient ``SPECIFY_REPO_ROOT``
    override an explicit root.

    When BOTH fail to find anything at or above ``project_root``, fail closed:
    return ``None`` rather than silently falling back to CWD, which would read
    an unrelated repository's posture. With no ``project_root`` at all, keep
    the existing CWD behaviour via :func:`locate_project_root`.
    """
    if project_root is not None:
        try:
            return resolve_canonical_root(project_root)
        except WorkspaceRootNotFound:
            return _walk_up_to_kittify_marker(project_root)
    return locate_project_root()


def _read_repo_ledger_key(repo_root: Path | None) -> tuple[bool | None, str]:
    """``.kittify/config.yaml`` → ``ledger.projection``.

    Missing file/dir/section/key, or a value that cannot be parsed, reads as
    unset. A parse failure or a non-bool value each warn exactly once.
    """
    label = "using default (True)"
    if repo_root is None:
        return None, "no repository root resolved"
    config_path = repo_root / _REPO_CONFIG_RELATIVE
    source = str(config_path)
    if not config_path.exists():
        return None, source

    from ruamel.yaml import YAML  # noqa: PLC0415 -- lazy: pay the YAML import only when the file exists.

    try:
        data = YAML(typ="safe").load(config_path)
    except Exception:  # noqa: BLE001 -- best-effort read: a malformed file must fail
        # to the default, never raise.
        # stacklevel=3: warn -> _read_repo_ledger_key -> ledger_posture -> caller.
        warnings.warn(f"{config_path}: could not parse YAML; {label}", stacklevel=3)
        return None, source

    if not isinstance(data, dict):
        return None, source
    section_value = data.get("ledger")
    if not isinstance(section_value, dict) or "projection" not in section_value:
        return None, source
    value = section_value["projection"]
    if not isinstance(value, bool):
        warnings.warn(
            f"{config_path}: ledger.projection is not a boolean ({value!r}); {label}",
            stacklevel=3,
        )
        return None, source
    return value, source


def ledger_posture(project_root: Path | None = None) -> LedgerPosture:
    """The effective ledger-projection posture. Defaults to enabled (``True``)
    when the key is absent, the file is missing, or the value cannot be parsed
    as a boolean. ``source`` always names the config path (or "no repository
    root resolved") the reader consulted -- even on the default-``True`` path --
    so an operator can tell a genuinely absent file apart from one that was
    read but held an invalid value."""
    repo_root = _resolve_repo_root(project_root)
    value, source = _read_repo_ledger_key(repo_root)
    if value is None:
        return LedgerPosture(enabled=True, source=source)
    return LedgerPosture(enabled=value, source=source)
