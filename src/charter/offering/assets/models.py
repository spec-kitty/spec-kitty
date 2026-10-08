"""ASSET sidecar manifest domain model.

An ASSET (:attr:`charter.offering.artifact_kinds.ArtifactKind.ASSET`) is a
loose-contract doctrine kind: the referenced binary/text blob (image, font,
template fixture, ...) is never parsed or schema-validated directly. Instead
a small YAML *sidecar manifest* (``*.asset.yaml``) describes it, and it is the
manifest that is the validated surface.

:class:`AssetManifest` intentionally carries only the well-formedness
contract (required ``id``/``mime``/``path``, optional ``title``). The two
safety checks that give the loose contract its teeth — path containment
under the pack's ``assets/`` root and ``mime``/extension consistency — are
NOT expressed as Pydantic field constraints; they live in
``charter.offering.packs.pack_validator._validate_asset_manifests`` (and its
``_check_asset_path_containment`` / ``_check_asset_mime`` helpers) because
they need cross-field/cross-pack context (the owning pack's root directory)
that a single-model validator does not have.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["AssetManifest"]


class AssetManifest(BaseModel):
    """Sidecar manifest describing one ASSET blob.

    Fields
    ------
    id:
        Stable artifact identifier, unique per pack per kind (global
        cross-pack uniqueness is enforced separately by the merge scan, not
        here).
    mime:
        Declared MIME type of the referenced blob, e.g. ``"image/png"``.
        Shape (``type/subtype``) and consistency with ``path``'s extension
        are validated by the pack validator, not here.
    path:
        Path to the blob, relative to the pack's ``assets/`` directory.
        Containment (no absolute path, no ``..`` escape, no symlink escape)
        is enforced by the pack validator, not here.
    title:
        Optional human-facing display name.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    mime: str = Field(min_length=1)
    path: str = Field(min_length=1)
    title: str | None = None
