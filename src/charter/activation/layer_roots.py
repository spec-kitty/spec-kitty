"""Resolve the org and project charter pack layer roots for a repository.

Layer-root discovery belongs in ``charter`` (C-007): the resolved paths are
handed to lower charter layers as data (C-008). ``roots["project"]`` is the
**project pack root** (``.kittify/charter-packs/``, resolved through
:mod:`kernel.charter_pack_paths`), so consumers join kind directories straight
onto it.
"""

from __future__ import annotations

from pathlib import Path

from charter.offering.drg.org_pack_config import (
    require_declared_org_roots,
    resolve_existing_org_roots,
    resolve_org_roots,
)
from kernel.charter_pack_paths import project_pack_root

__all__ = ["resolve_layer_roots", "resolve_pack_chain"]


def resolve_layer_roots(repo_root: Path) -> dict[str, Path]:
    """Resolve the org and project charter pack roots for *repo_root*.

    ``roots["project"]`` is the project pack root, present only when it is a
    directory (:func:`kernel.charter_pack_paths.project_pack_root`; the
    retired pre-cutover project directory is never read, FR-011).
    """
    roots: dict[str, Path] = {}

    project = project_pack_root(repo_root)
    if project.is_dir():
        roots["project"] = project

    # FR-013: register the first resolved org pack root regardless of whether it
    # nests a ``doctrine/`` subdir. Runtime resolves org packs from the *flat*
    # ``<pack>/<plural>/`` layout (``resolve_org_roots`` → ``ActiveCharterService``),
    # which has no ``<pack>/doctrine/`` subdir; gating on ``doctrine/.is_dir()``
    # silently dropped those packs so flat-layout artifacts failed to activate
    # ("Unknown <kind> ID"). The layout-tolerant scan in
    # ``pack_manager._scan_layer_dirs`` accepts both flat and nested packs.
    for org_root in resolve_org_roots(repo_root):
        if org_root.is_dir():
            roots["org"] = org_root
            break

    return roots


def resolve_pack_chain(repo_root: Path, *, strict: bool) -> list[Path]:
    """Return the ordered org-pack chain for *repo_root*: the single chain authority.

    Declaration order (last-declared-wins for consumers). ``strict`` toggles the
    posture over the same chain:

    * ``strict=False`` -- existing-filtered: a declared pack whose root is absent
      on disk is dropped (equivalent to ``resolve_existing_org_roots``).
    * ``strict=True`` -- fail-closed: the registry is read strictly and a
      declared-but-unfetched pack raises ``ValueError`` naming the pack and the
      ``spec-kitty charter fetch`` remedy (equivalent to
      ``require_declared_org_roots``).

    Zero declared packs yields ``[]`` in either posture; it never raises.
    """
    if strict:
        return list(require_declared_org_roots(repo_root))
    return list(resolve_existing_org_roots(repo_root))
