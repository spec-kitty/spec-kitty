"""Authored pack descriptor model for pack identity, lineage and level.

The ``PackDescriptor`` represents the stable, immutable identity and lineage
metadata for a pack — the ``pack_id`` (ULID), ``pack_version`` (authored and
required for built-in, optional otherwise), lineage edge (``parent_pack``),
human handle (``name``), the declared Charter Pack ``pack_level`` (the single
:mod:`kernel.pack_tiers` authority — ``built-in`` / ``org`` / ``project``), and
the optional vendoring/layout metadata (``requires_core``, ``active_charter``,
``pack_drg``).

This is distinct from the generated ``PackManifest`` (``pack-manifest.yaml``),
which holds the manifest schema, constituents, and provenance.

:func:`load_pack_descriptor` reads one ``pack.yaml``. A descriptor that still
carries a retired field (see :mod:`~charter.offering.packs.retired_fields`, #3732) is rejected with
:class:`~charter.offering.packs.retired_fields.RetiredPackFieldError` (code
``RETIRED_PACK_FIELD``) naming the file, the field and its replacement, before
pydantic's generic "extra fields not permitted" error. Identity resolution is
handled elsewhere (the single-authority ``extends`` resolver via an id→key
adapter).
"""

from __future__ import annotations

from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from ruamel.yaml import YAML

from charter.offering.packs.retired_fields import SCOPE_PACK_DESCRIPTOR, raise_retired_field_at, reject_retired_fields
from kernel.pack_tiers import BUILT_IN, PackTier

#: Diagnostic code: a pack's declared ``pack_level`` disagrees with the
#: configured position it was loaded from (FR-006). The single authority for
#: this code string; the load/validate layer and the org load path both import
#: it rather than re-spelling the literal.
PACK_LEVEL_MISMATCH = "PACK_LEVEL_MISMATCH"

#: Diagnostic code: a ``pack.yaml`` is present but carries no ``pack_level``
#: (FR-007). A warning during the deprecation window; a refusal only behind the
#: load/validate layer's single deprecation switch.
PACK_LEVEL_MISSING = "PACK_LEVEL_MISSING"

__all__ = ["PACK_LEVEL_MISMATCH", "PACK_LEVEL_MISSING", "load_pack_descriptor"]


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
    pack_level : PackTier
        The declared Charter Pack tier (``built-in`` / ``org`` / ``project``),
        reusing the single :data:`kernel.pack_tiers.PackTier` authority — no new
        enum. Required; an unknown value is a schema error.
    requires_core : str | None
        An optional PEP 440 version-specifier range (e.g. ``">=4.0,<5.0"``)
        naming the Spec Kitty core versions this pack supports. Validated as a
        :class:`packaging.specifiers.SpecifierSet`; an unparsable value is a
        schema error naming the field. ``None`` means no constraint.
    active_charter : str | None
        An optional pack-relative path to the active-charter file
        (``org-charter.yaml`` for an org pack). A plain string here; in-pack
        path resolution (no ``..`` escape) is validated by ``charter pack
        validate`` (WP02), not at model time.
    pack_drg : str | None
        An optional pack-relative path to the DRG source. A plain string here;
        in-pack path resolution is validated by ``charter pack validate``.
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
    pack_version: str | None = Field(
        default=None,
        description="Semantic version string; required for built-in, optional for org/project.",
    )
    parent_pack: str | None = Field(
        default=None,
        description="Parent pack ULID; None for root packs.",
    )
    name: str = Field(
        ...,
        description="Human-readable handle; not the runtime identity.",
    )
    pack_level: PackTier = Field(
        ...,
        description="Declared Charter Pack tier (kernel.pack_tiers authority): built-in / org / project.",
    )
    requires_core: str | None = Field(
        default=None,
        description="Optional PEP 440 version-specifier range of supported core versions.",
    )
    active_charter: str | None = Field(
        default=None,
        description="Optional pack-relative path to the active-charter file.",
    )
    pack_drg: str | None = Field(
        default=None,
        description="Optional pack-relative path to the DRG source.",
    )

    @field_validator("requires_core")
    @classmethod
    def _validate_requires_core(cls, value: str | None) -> str | None:
        """Reject a ``requires_core`` that is not a PEP 440 version specifier (FR-002)."""
        if value is None:
            return value
        try:
            SpecifierSet(value)
        except InvalidSpecifier as exc:
            raise ValueError(f"requires_core is not a valid version specifier: {value!r}") from exc
        return value

    @model_validator(mode="after")
    def _require_version_for_built_in(self) -> PackDescriptor:
        """A built-in pack must carry ``pack_version``; org/project need not (FR-005)."""
        if self.pack_level == BUILT_IN and self.pack_version is None:
            raise ValueError("pack_version is required when pack_level is 'built-in'")
        return self


def load_pack_descriptor(path: Path, *, inferred_level: PackTier | None = None) -> PackDescriptor:
    """Read and validate the authored ``pack.yaml`` at *path*.

    The model keeps ``pack_level`` strictly required (a direct
    ``PackDescriptor(...)`` construction without it is a schema error). During
    the FR-007 deprecation window a *file* may still omit ``pack_level``; a
    position-aware caller passes ``inferred_level`` (the configured tier) so the
    loader injects it and proceeds rather than crashing. The caller owns the
    ``PACK_LEVEL_MISSING`` diagnostic — this function only tolerates the gap, it
    does not warn. Without ``inferred_level`` the strict requirement stands, so a
    context-free load of a field-less file still raises ``ValidationError``.

    Raises:
        RetiredPackFieldError: the descriptor carries a retired field; the
            error names *path*, the field and its replacement.
        pydantic.ValidationError: any other schema failure (an unknown field,
            a missing ``pack_id``, a missing ``pack_level`` with no inferred
            level, ...).
        ruamel.yaml.YAMLError, OSError: the file cannot be read or parsed.
    """
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    if inferred_level is not None and isinstance(data, dict) and "pack_level" not in data:
        # Window tolerance (FR-007): a field-less file loads under the
        # configured position's tier. The model field stays required.
        data = {**data, "pack_level": inferred_level}
    try:
        return PackDescriptor.model_validate(data)
    except ValidationError as exc:
        raise_retired_field_at(exc, path)
        raise
