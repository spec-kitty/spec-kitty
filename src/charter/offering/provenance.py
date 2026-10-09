"""Portable provenance path normalizer (charter offering).

Single 3-class ``source_path`` normalizer shared by both provenance carriers
-- the charter catalog (``charter.activation.compiler._doctrine_yaml_reference``) and
the agent-profile projection manifest
(``specify_cli.tool_surface.profiles.projection._manifest_source_path``) --
so a committed ``charter.yaml`` / ``agent_profiles_manifest.json`` never
bakes in an operator- or platform-specific absolute filesystem path for a
built-in-pack source (contracts/provenance-and-channel.md C-PRV-1..3/6).

Lives in ``charter.offering`` (below the ``charter`` facades/``specify_cli`` in the
dependency stack) so ``charter`` can import this without an upward
dependency violation -- mirrors how ``charter.offering.pack_paths`` and
``kernel.paths`` are already consumed from ``charter``.

Three classes, checked in this priority order:

1. **Built-in pack path** -- anything resolving under
   :func:`kernel.paths.get_built_in_pack_root` becomes a portable
   ``${SPEC_KITTY_PACKS_ROOT}/built-in/<rest>`` token. The token is the
   stored artifact -- it is never re-baked to an absolute path even when
   ``SPEC_KITTY_PACKS_ROOT`` is set in the *emitting* process's environment
   (C-PRV-2, the re-bake gate): this module never reads that env var, it
   only ever composes the literal token string.
2. **In-tree project/org path** -- anything under the caller-supplied
   ``project_root`` becomes a repo-relative POSIX string (the pre-existing
   behaviour for non-built-in sources, preserved).
3. **Out-of-tree, non-pack path** -- neither of the above: the resolved
   absolute path is preserved unchanged (there is no portable form for it).
"""

from __future__ import annotations

from pathlib import Path

from kernel.paths import BUILT_IN_PACK_SIBLING_PATTERN, get_built_in_pack_root, to_posix
from kernel.sibling_paths import SiblingPathNotFound

__all__ = ["is_built_in_pack_path", "to_portable_source_path"]

#: The env var a stored built-in-pack token defers resolution to, at READ
#: time. ``kernel.env_expand``'s default-injection registry already knows
#: how to fill this in when the var is unset -- this module only ever WRITES
#: the token string, never expands one, so it does not import that module's
#: raising/injecting expansion machinery for it.
_PACKS_ROOT_ENV_VAR_NAME = "SPEC_KITTY_PACKS_ROOT"

#: The fixed "built-in" path segment inside the token -- derived from the one
#: owned kernel constant (:data:`~kernel.paths.BUILT_IN_PACK_SIBLING_PATTERN`)
#: rather than hand-typed a second time here.
_BUILT_IN_SEGMENT = BUILT_IN_PACK_SIBLING_PATTERN.name

#: The fixed ``${SPEC_KITTY_PACKS_ROOT}/built-in`` token prefix every built-in
#: pack path normalizes to (composed once, module scope -- Sonar S1192: it is
#: referenced from both branches of :func:`to_portable_source_path` below).
_BUILT_IN_TOKEN_PREFIX = f"${{{_PACKS_ROOT_ENV_VAR_NAME}}}/{_BUILT_IN_SEGMENT}"


def _resolve_built_in_root() -> Path | None:
    """Resolve the built-in pack root, tolerating an unavailable install.

    An offering-side caller (e.g. a test fixture with no packaged
    ``packs/built-in`` sibling reachable from its anchor) must not hard-crash
    the normalizer -- classes (b)/(c) still need to work when the built-in
    tree genuinely cannot be located. Kernel's own resolver already warns
    loudly on a misconfigured ``SPEC_KITTY_PACKS_ROOT`` override before
    falling through to the installed sibling; this only guards the final
    fail-closed :class:`~kernel.sibling_paths.SiblingPathNotFound`.
    """
    try:
        return get_built_in_pack_root().resolve()
    except SiblingPathNotFound:
        return None


def _relative_to_built_in(resolved: Path) -> Path | None:
    """Return *resolved*'s path relative to the built-in pack root, or ``None``."""
    built_in_root = _resolve_built_in_root()
    if built_in_root is None:
        return None
    try:
        return resolved.relative_to(built_in_root)
    except ValueError:
        return None


def is_built_in_pack_path(path: Path | str) -> bool:
    """Return ``True`` when *path* resolves under the built-in pack root.

    Shared classification predicate: the heal migration
    (``m_3_2_7_heal_provenance_paths``) and the leak-check doctor sibling
    (``cli.commands._provenance_doctor``) both need to answer "is this
    already-committed absolute path a healable built-in-pack path" without
    re-deriving :func:`to_portable_source_path`'s own class-(a) branch.
    """
    raw = str(path)
    if not raw:
        return False
    return _relative_to_built_in(Path(path).resolve()) is not None


def to_portable_source_path(path: Path | str, *, project_root: Path | None) -> str:
    """Return a portable string form of *path* for committed provenance.

    Args:
        path: the source path to normalize. An empty string/path returns
            ``""`` unchanged (mirrors the pre-existing ``_trim_source_path``
            empty-input contract in ``charter.activation.compiler``).
        project_root: the project root used to classify an in-tree,
            non-built-in path as repo-relative (class b). ``None`` disables
            class (b) entirely -- such a path then falls through to class
            (c), absolute.

    Returns:
        - ``${SPEC_KITTY_PACKS_ROOT}/built-in/<rest>`` when *path* resolves
          under the built-in pack root (class a).
        - A repo-relative POSIX string when *path* resolves under
          *project_root* (class b).
        - The resolved absolute path as a string otherwise (class c).
    """
    raw = str(path)
    if not raw:
        return ""

    resolved = Path(path).resolve()

    rest = _relative_to_built_in(resolved)
    if rest is not None:
        rest_posix = "" if str(rest) == "." else to_posix(rest)
        return f"{_BUILT_IN_TOKEN_PREFIX}/{rest_posix}" if rest_posix else _BUILT_IN_TOKEN_PREFIX

    if project_root is not None:
        try:
            rel = resolved.relative_to(project_root.resolve())
        except ValueError:
            pass
        else:
            return to_posix(rel)

    return str(resolved)
