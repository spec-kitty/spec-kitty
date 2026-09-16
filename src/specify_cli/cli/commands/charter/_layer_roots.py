"""Resolve doctrine layer roots for charter CLI commands."""

from __future__ import annotations

from pathlib import Path

__all__ = ["resolve_layer_roots", "resolve_org_root_chain"]


def resolve_layer_roots(repo_root: Path) -> dict[str, Path]:
    """Resolve org/project doctrine roots for *repo_root*.

    Root resolution lives in ``specify_cli`` and the resolved paths are handed
    to lower charter/doctrine layers as data (C-008).
    """
    from charter.drg import resolve_org_roots

    roots: dict[str, Path] = {}

    project_root = repo_root / ".kittify"
    if (project_root / "doctrine").is_dir():
        roots["project"] = project_root

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
    """Return the full, declaration-ordered chain of existing org doctrine roots.

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
    resolution -- matching this module's existing role as the layer-root
    resolution seam for the charter CLI commands.
    """
    # Reached through the `charter.drg` proxy, never `doctrine.*` directly:
    # a lazy, function-body import is NOT exempt from the runtime->charter->
    # doctrine boundary (tests/architectural/
    # test_runtime_charter_doctrine_boundary.py). `charter.drg` re-exports this
    # primitive for exactly this purpose, and the module-level TYPE_CHECKING
    # import above already uses the same door.
    from charter.drg import resolve_existing_org_roots

    return resolve_existing_org_roots(repo_root)
