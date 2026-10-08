"""Authored pack descriptor model for pack identity and lineage.

The ``PackDescriptor`` represents the stable, immutable identity and lineage
metadata for a pack — the ``pack_id`` (ULID), ``pack_version`` (scoped to
built-in; authored here), lineage edges (``parent_pack``, ``accompanies_doctrine_pack``),
and human handle (``name``).

This is distinct from the generated ``PackManifest`` (``pack-manifest.yaml``),
which holds the manifest schema, constituents, and provenance.

**Not for direct I/O**: this module defines the schema only. Authored
persistence and identity resolution are handled elsewhere (pack.yaml round-trip,
backed by the single-authority ``extends`` resolver via an id→key adapter).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PackDescriptor(BaseModel):
    """Authored descriptor for a pack's identity and lineage.

    Fields
    ------
    pack_id : str
        Stable, immutable ULID (26 chars). Sole runtime identity for the pack.
        Minted once at creation; never changed. Mirrors the ``mission_id`` model.
    pack_version : str
        Semantic versioning string. Author-managed **for the built-in pack only**.
        For fetched/org packs, ``pack_version`` remains generated provenance on the
        manifest side (see data-model.md). Consumers read authored-when-present,
        else generated.
    parent_pack : str | None
        ULID of the parent pack, if this pack extends another. Resolved via
        identity→key adapter feeding ``extends.resolve_extends_order``.
        ``None`` for root packs. An unresolvable ``parent_pack`` (pre-backfill)
        fails closed, never silently degrades.
    accompanies_doctrine_pack : str | None
        ULID of the paired doctrine pack for charter packs. Binding at the pack
        level (was per-activation in an earlier model). ``None`` for non-charter packs.
        Unresolvable values fail closed.
    name : str
        Human-readable handle. No longer the identity key; used for display and
        in resolved commands. Resolver disambiguates with no silent fallback.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_id: str = Field(
        ...,
        description="Stable ULID identity (26 chars); immutable sole runtime identity.",
    )
    pack_version: str = Field(
        ...,
        description="Semantic version string (authored for built-in; generated for org/fetched).",
    )
    parent_pack: str | None = Field(
        default=None,
        description="Parent pack ULID; None for root packs.",
    )
    accompanies_doctrine_pack: str | None = Field(
        default=None,
        description="Doctrine pack ULID for charter packs; None for non-charter.",
    )
    name: str = Field(
        ...,
        description="Human-readable handle; not the runtime identity.",
    )
