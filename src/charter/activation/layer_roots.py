"""Resolve the org and project charter pack layer roots for a repository.

Layer-root discovery belongs in ``charter`` (C-007): the resolved paths are
handed to lower charter layers as data (C-008). ``roots["project"]`` is the
**project pack root** (``.kittify/charter-packs/``, resolved through
:mod:`kernel.charter_pack_paths`), so consumers join kind directories straight
onto it.
"""

from __future__ import annotations

from pathlib import Path

from charter.offering.drg.org_pack_config import resolve_existing_org_roots, resolve_org_roots
from kernel.charter_pack_paths import resolve_project_pack_read_root

__all__ = ["resolve_layer_roots", "resolve_org_root_chain"]


def resolve_layer_roots(repo_root: Path) -> dict[str, Path]:
    """Resolve the org and project charter pack roots for *repo_root*.

    ``roots["project"]`` is the project pack root, present only when it is a
    directory. It reads through
    :func:`kernel.charter_pack_paths.resolve_project_pack_read_root` (quietly),
    so a project that still has the retired ``.kittify/doctrine/`` tree is read
    from there until the migration moves it.
    """
    roots: dict[str, Path] = {}

    project = resolve_project_pack_read_root(repo_root, quiet=True)
    if project.is_dir():
        roots["project"] = project

    # FR-013: register the first resolved org pack root regardless of whether it
    # nests a ``doctrine/`` subdir. Runtime resolves org packs from the *flat*
    # ``<pack>/<plural>/`` layout (``resolve_org_roots`` → ``DoctrineService``),
    # which has no ``<pack>/doctrine/`` subdir; gating on ``doctrine/.is_dir()``
    # silently dropped those packs so flat-layout artifacts failed to activate
    # ("Unknown <kind> ID"). The layout-tolerant scan in
    # ``pack_manager._scan_layer_dirs`` accepts both flat and nested packs.
    for org_root in resolve_org_roots(repo_root):
        if org_root.is_dir():
            roots["org"] = org_root
            break

    return roots


def resolve_org_root_chain(repo_root: Path) -> list[Path]:
    """Return the full, declaration-ordered chain of existing org charter pack roots.

    WP02 (mission ``cascade-org-inert-01M07E9P``) T008 — the ID-mapping half of
    the cascade-org-inert fix. ``resolve_layer_roots``'s ``roots["org"]`` key
    deliberately stays single-``Path`` (pack #1 only, unchanged): it is a
    load-bearing back-compat contract for
    :meth:`charter.activation.pack_manager.CharterPackManager.list_available_detailed`
    (``charter list --all-layers`` — verified by
    ``test_org_cascade_chain.py::TestListAllLayersBackCompat``) and every other
    consumer typed ``layer_roots: dict[str, Path] | None``
    (``pack_manager._scan_layer_dirs`` / ``kind_vocabulary._layer_scan_dirs``
    unconditionally do ``root / ...`` assuming each dict value is a single
    ``Path``). Smuggling a ``list[Path]`` chain into that dict under a new key
    would either break those call sites outright or, worse, silently resolve
    to a directory that never exists (an NFR-002 "silent success" the DoD
    forbids) rather than raising -- so the chain is exposed as a SEPARATE
    function instead of a new dict key.

    Callers that need the full chain for ID-mapping
    (``_cascade_shared.py``'s ``drg_urn_to_config_id`` and
    ``activate.py``/``deactivate.py``'s ``_source_urn``/``_active_urns``)
    pass this list through
    :func:`charter.activation.kind_vocabulary.resolve_artifact_urn` /
    ``resolve_config_id``'s existing, independent ``org_roots: list[Path] |
    None`` keyword -- ``kind_vocabulary._org_scan_dirs`` already walks the
    FULL supplied chain, not just its first entry -- so a cascade-reported DRG
    ID that only resolves through org pack 2..N now maps back to its
    config-stem ID correctly, not just pack 1's.

    A thin, single-authority delegation to
    :func:`charter.offering.drg.org_pack_config.resolve_existing_org_roots` (the same
    primitive #3525 introduced for ``load_validated_graph``'s ``org_roots``
    threading), kept here rather than imported separately by both
    ``activate.py`` and ``deactivate.py`` so the two CLI commands share one
    resolution -- matching this module's role as the layer-root resolution
    seam for the charter pack layers.
    """
    chain: list[Path] = resolve_existing_org_roots(repo_root)
    return chain
