"""Shared pack-root resolver for Charter Packs (built-in, org, project).

This module is the single seam through which every consumer resolves the
filesystem root of a Charter Pack tier. ``packs/built-in/`` is deliberately
*not* a Python package -- the hyphen in ``built-in`` is not a legal identifier
-- so a package-relative :func:`importlib.resources.files` lookup cannot
address it. A filesystem walk is required instead.

Resolution order for the ``built-in`` tier (delegated wholesale to the kernel
floor primitive, :func:`kernel.paths.get_built_in_pack_root` -- FR-001/FR-004,
mission ``resolution-activation-foundation-01KZ9FKG``, WP02): this module no
longer forks its own ``SPEC_KITTY_PACKS_ROOT`` read or ancestor-walk call --
:func:`kernel.paths.get_built_in_pack_root` owns the entire three-step order
below, and every layer above it (this module's :func:`_resolve_built_in`, and
``charter.offering.missions.repository.default_missions_root``) delegates to that one
primitive (DR-1):

1. ``SPEC_KITTY_PACKS_ROOT`` environment override -> ``<env>/built-in`` if it
   exists.
2. Ancestor walk: the nearest ancestor of :mod:`kernel.paths`'s resolved
   location that contains ``packs/built-in/``. ``Path(__file__).resolve()``
   is called **before** iterating ``.parents`` so that symlinked editable
   installs still walk up the real repository tree rather than the symlink's
   parent. This single walk covers both the editable-checkout case and the
   installed-wheel case: ``packs/`` ships as a site-packages sibling of every
   top-level package (hatch ``force-include``), including ``kernel``'s own
   containing package, and the site-packages directory is always one of
   ``Path(__file__).resolve()``'s ancestors -- so there is no separate
   "installed wheel" probe distinct from this walk.
3. Otherwise the primitive's own :class:`~kernel.sibling_paths.SiblingPathNotFound`
   is caught and re-raised as :class:`PackRootNotFound` -- fail-closed; never
   fall open to an arbitrary tree or to a path inside ``src/charter/offering/``.

For the ``org`` / ``project`` tiers the seam is shared but the input differs:
the caller-supplied root is returned unchanged.

Two additional authorities (mission ``doctrine-built-in-seam-consolidation-01KYW3TX``,
WP01) sit on top of the tier resolver above: :func:`built_in_root` (the bare
built-in root, for callers like the DRG loader/extractor that need no kind
subdirectory) and :func:`built_in_dir` (the per-kind
``packs/built-in/<plural>/`` directory, refusing the 3-kind carve-out with
:class:`BuiltInContentDirNotAvailable`). These are the seam every offering
repository default and DRG root caller routes through -- no other module
should compose its own ``resolve_pack_root("built-in") / ...`` join.

Layer note (C-004): ``charter.offering`` sits below the charter facades/specify_cli in the dependency
graph and must not import upward. This module imports only the standard
library (``pathlib``, :func:`importlib.resources.files`) plus
:class:`~charter.offering.artifact_kinds.ArtifactKind` (an in-layer sibling, itself a
zero-dependency leaf importing only ``enum``), :mod:`kernel.sibling_paths`,
and :mod:`kernel.paths` (the root layer *below* the offering -- a downward,
allowed import per ``kernel (root) <- charter.offering <- charter <- specify_cli``)
-- so this stays import-cycle-safe. The ``files("charter.offering")`` call inside
:func:`offering_package_dir` is an in-layer self-reference and is made lazily
*inside* the function to avoid an import cycle with ``charter/offering/__init__.py``;
:func:`_resolve_built_in` no longer calls it directly (FR-004) -- see
:func:`offering_package_dir`'s own docstring for its remaining callers.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Literal

from charter.offering.artifact_kinds import ArtifactKind
from kernel.paths import MISSION_ASSETS_SIBLING_PATTERN, get_built_in_pack_root
from kernel.sibling_paths import SiblingPathNotFound

# ``PackTier`` is intentionally *not* exported: it is the internal annotation
# for ``resolve_pack_root``'s ``tier`` parameter and has no external importer, so
# listing it in ``__all__`` would trip the symbol-level dead-code gate
# (tests/architectural/test_no_dead_symbols.py). It stays a module-level name
# usable as ``pack_paths.PackTier``; re-export it here once a real consumer imports it.
#
# ``resolve_pack_root`` is likewise not exported: after the built-in seam
# consolidation (doctrine-built-in-seam-consolidation) every external caller
# resolves built-in location through the ``built_in_dir``/``built_in_root``
# authorities (C1.6 — it is the internal tier resolver those two wrap), so it has
# no external ``src/`` importer and would trip the dead-code gate. It remains a
# module-level name (``pack_paths.resolve_pack_root``); re-export it if a real
# non-seam consumer (e.g. org/project-tier resolution) imports it directly.
__all__ = [
    "BuiltInContentDirNotAvailable",
    "PackRootNotFound",
    "built_in_dir",
    "built_in_missions_root",
    "built_in_root",
    "offering_package_dir",
]

PackTier = Literal["built-in", "org", "project"]

_BUILT_IN = "built-in"


class PackRootNotFound(Exception):
    """Raised when no pack root can be resolved for a tier (fail-closed)."""

    def __init__(self, tier: str) -> None:
        self.tier = tier
        super().__init__(f"No pack root found for tier {tier!r}")


class BuiltInContentDirNotAvailable(Exception):
    """Raised by :func:`built_in_dir` for a kind with no built-in content dir.

    The refused kinds are the derived complement of
    :attr:`~charter.offering.artifact_kinds.ArtifactKind.has_built_in_content_dir`
    (currently ``MISSION_STEP_CONTRACT``, ``TEMPLATE``, ``ANTI_PATTERN``) --
    package-resource/graph-only kinds with no shipped
    ``packs/built-in/<plural>/`` directory (see mission #3091 for the
    step-contract/template relocation). Raising a named error here instead of
    silently joining to a non-existent path is the C1.4 contract obligation.
    """

    def __init__(self, kind: ArtifactKind) -> None:
        self.kind = kind
        super().__init__(
            f"ArtifactKind.{kind.name} has no packs/built-in/ content "
            "directory (package-resource/graph-only kind; see mission #3091 "
            "for the step-contract/template relocation)."
        )


def resolve_pack_root(
    tier: PackTier,
    *,
    org_root: Path | None = None,
    project_root: Path | None = None,
) -> Path:
    """Resolve the filesystem root of a Charter Pack *tier*.

    :param tier: ``"built-in"``, ``"org"``, or ``"project"``.
    :param org_root: caller-supplied root for the ``org`` tier.
    :param project_root: caller-supplied root for the ``project`` tier.
    :returns: an existing directory for the requested tier.
    :raises PackRootNotFound: when the tier cannot be resolved. Fail-closed:
        never returns a path inside ``src/charter/offering/`` and never falls open to an
        arbitrary tree.

    Pure and idempotent: same inputs (and environment) yield the same path.
    """
    if tier == "org":
        if org_root is None:
            raise PackRootNotFound("org")
        return org_root
    if tier == "project":
        if project_root is None:
            raise PackRootNotFound("project")
        return project_root
    return _resolve_built_in()


def built_in_root() -> Path:
    """Return the filesystem root of the built-in pack tier (FR-001b / C1.6).

    The single callable a root-needing reader (e.g. the DRG loader, the DRG
    migration extractor, a reference-pointer walk, ``charter pack
    regenerate-graph``) uses instead of scattering bare
    ``resolve_pack_root("built-in")`` calls across modules.

    :raises PackRootNotFound: when the built-in pack root cannot be located
        (fail-closed -- see :func:`resolve_pack_root`).
    """
    return resolve_pack_root("built-in")


def built_in_dir(kind: ArtifactKind) -> Path:
    """Return the built-in content directory for *kind* (FR-001).

    ``resolve_pack_root("built-in") / kind.plural`` -- the canonical plural is
    read from :class:`~charter.offering.artifact_kinds.ArtifactKind`, never a
    hand-typed string.

    The refusal below is computed straight from
    :attr:`~charter.offering.artifact_kinds.ArtifactKind.has_built_in_content_dir` --
    there is no hand-listed complement set in this module (FR-005 / NFR-005).
    A kind gaining or losing a content dir is a one-place edit in
    ``artifact_kinds.py``; this function needs no change.

    :raises BuiltInContentDirNotAvailable: for a kind with no shipped content
        dir (the derived complement -- currently ``MISSION_STEP_CONTRACT``,
        ``TEMPLATE``, ``ANTI_PATTERN``; C1.4).
    :raises PackRootNotFound: when the built-in pack root cannot be located
        (C1.3 -- no empty-set substitute).
    """
    if not kind.has_built_in_content_dir:
        raise BuiltInContentDirNotAvailable(kind)
    return resolve_pack_root("built-in") / kind.plural


def built_in_missions_root() -> Path:
    """Return the built-in pack's shipped ``missions`` leaf path (unchecked).

    ``built_in_root() / <missions-leaf-name>`` -- composed here because this
    module is the one file the built-in-location architectural ratchet
    (``tests/architectural/test_built_in_location_authority.py``) permits to
    join a path onto :func:`built_in_root`'s result; a caller composing its
    own ``built_in_root() / ...`` join elsewhere would trip that gate. This
    lets ``charter.offering.missions.repository.default_missions_root`` (mission
    ``resolution-activation-foundation-01KZ9FKG``, WP02) route through the
    one built-in-root authority for its ``missions`` leaf without forking a
    second join site. The leaf name itself is read from
    :data:`kernel.paths.MISSION_ASSETS_SIBLING_PATTERN`'s final path segment
    rather than a re-typed ``"missions"`` string literal, so the leaf name
    stays owned once at the kernel floor (FR-012).

    Returns the joined path unconditionally -- it may not exist on disk.
    Callers needing fail-closed semantics (e.g.
    ``charter.offering.missions.repository.MissionsRootNotFound``) perform their own
    ``.is_dir()`` check on the result.

    :raises PackRootNotFound: when the built-in pack root itself (not the
        ``missions`` leaf) cannot be located -- propagated unchanged from
        :func:`built_in_root`.
    """
    return built_in_root() / MISSION_ASSETS_SIBLING_PATTERN.name


def _resolve_built_in() -> Path:
    """Resolve the ``built-in`` tier via the shared kernel primitive (FR-001/FR-004).

    Delegates *wholesale* to :func:`kernel.paths.get_built_in_pack_root` -- the
    one kernel-floor primitive that owns both the ``SPEC_KITTY_PACKS_ROOT``
    env read and the ancestor walk (DR-1: exactly one env read across the
    whole resolution stack). This module no longer forks a second env read or
    composes its own ``sibling_relative_path`` -- see the module docstring
    above for the full 3-step order the primitive owns.

    Kernel cannot import :class:`PackRootNotFound` (layer direction), so the
    primitive's own :class:`~kernel.sibling_paths.SiblingPathNotFound` is
    caught and translated here -- at least one consumer
    (``charter/offering/packs/pack_validator.py``'s
    ``except (PackRootNotFound, BuiltInContentDirNotAvailable)``) depends on
    the specific :class:`PackRootNotFound` type surviving at this boundary.
    """
    try:
        return get_built_in_pack_root()
    except SiblingPathNotFound as exc:
        raise PackRootNotFound(_BUILT_IN) from exc


def offering_package_dir() -> Path | None:
    """Return the installed ``charter.offering`` package directory, or ``None``.

    ``files("charter.offering")`` is called lazily here (not at import time)
    to avoid an import cycle with ``charter/offering/__init__.py``. Public
    (WP01-fold, mission ``doctrine-built-in-seam-consolidation-01KYW3TX``) so
    :mod:`charter.offering.drg.migration.extractor` can import this instead
    of carrying a byte-identical private copy.
    """
    try:
        return Path(str(files("charter.offering")))
    except (ModuleNotFoundError, TypeError):
        return None
