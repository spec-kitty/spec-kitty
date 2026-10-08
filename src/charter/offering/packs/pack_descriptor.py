"""Authored pack descriptor model for pack identity and lineage.

The ``PackDescriptor`` represents the stable, immutable identity and lineage
metadata for a pack — the ``pack_id`` (ULID), ``pack_version`` (scoped to
built-in; authored here), lineage edge (``parent_pack``), and human handle
(``name``).

This is distinct from the generated ``PackManifest`` (``pack-manifest.yaml``),
which holds the manifest schema, constituents, and provenance.

:func:`load_pack_descriptor` reads one ``pack.yaml``. A descriptor that still
carries a retired field (``accompanies_doctrine_pack``, #3732) is rejected with
:class:`~charter.offering.packs.retired_fields.RetiredPackFieldError` (code
``RETIRED_PACK_FIELD``) naming the file, the field and its replacement, before
pydantic's generic "extra fields not permitted" error. Identity resolution is
handled elsewhere (the single-authority ``extends`` resolver via an id→key
adapter).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from ruamel.yaml import YAML

from charter.offering.packs.retired_fields import SCOPE_PACK_DESCRIPTOR, raise_retired_field_at, reject_retired_fields

__all__ = ["load_pack_descriptor"]


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
    name : str
        Human-readable handle. No longer the identity key; used for display and
        in resolved commands. Resolver disambiguates with no silent fallback.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _reject_retired_fields(cls, data: object) -> object:
        # Runs before the generic extra-field check; ``load_pack_descriptor``
        # relocates the error to the file it read (``raise_retired_field_at``).
        reject_retired_fields(data, scope=SCOPE_PACK_DESCRIPTOR, path=None)
        return data

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
    name: str = Field(
        ...,
        description="Human-readable handle; not the runtime identity.",
    )


def load_pack_descriptor(path: Path) -> PackDescriptor:
    """Read and validate the authored ``pack.yaml`` at *path*.

    Raises:
        RetiredPackFieldError: the descriptor carries a retired field; the
            error names *path*, the field and its replacement.
        pydantic.ValidationError: any other schema failure (an unknown field,
            a missing ``pack_id``, ...).
        ruamel.yaml.YAMLError, OSError: the file cannot be read or parsed.
    """
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    try:
        return PackDescriptor.model_validate(data)
    except ValidationError as exc:
        raise_retired_field_at(exc, path)
        raise
