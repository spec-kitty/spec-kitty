"""Asset repository — three-tier resolution of ASSET blobs to filesystem paths.

An :class:`~charter.offering.assets.models.AssetManifest` (``*.asset.yaml`` sidecar)
names a blob by ``path`` relative to its pack's ``assets/`` root. This
repository loads those manifests across the built-in, organisation and project
tiers (via :class:`~charter.offering.base.BaseArtifactRepository`) and resolves an
asset identifier to the on-disk blob path, fail-closed.

Two traps the base class does not handle for this kind, addressed here:

1. **Anchor asymmetry** (A-2). The service constructs this repository with
   ``built_in_dir = <root>/assets/built-in`` but ``org_dirs``/``project_dir``
   at ``<root>/assets`` (the ``assets/`` root itself). Built-in blob ``path``
   values carry the leading ``built-in/`` segment, so they anchor at the
   **parent** of ``built_in_dir``; org/project paths anchor at the directory
   itself. A single shared anchor rule would double the segment
   (``.../assets/built-in/built-in/...``).
2. **Layer-correct containment** (A-4). Containment is enforced through the
   offering-layer :func:`resolve_relative_path_within_root` primitive — never
   the ``specify_cli`` pack-validator convenience helper, which ``charter.offering``
   may not import upward (C-001). Traversal and symlink escapes raise a typed,
   named error (NFR-006, fail-closed).
"""

from __future__ import annotations

from pathlib import Path

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.assets.models import AssetManifest
from charter.offering.pack_paths import built_in_dir
from charter.offering.base import BaseArtifactRepository
from charter.offering.drg.org_pack_config import (
    OrgPackSubdirEscapeError,
    resolve_relative_path_within_root,
)

__all__ = [
    "AssetNotFoundError",
    "AssetPathEscapeError",
    "AssetRepository",
    "AssetResolutionError",
]


class AssetResolutionError(Exception):
    """Base class for asset-resolution failures (typed, fail-closed — NFR-006)."""


class AssetNotFoundError(AssetResolutionError):
    """Raised when an asset id resolves to no loaded manifest.

    Carries the offending :attr:`asset_id` so callers can branch on identity
    rather than parsing a message string.
    """

    def __init__(self, asset_id: str) -> None:
        self.asset_id = asset_id
        super().__init__(f"No asset manifest resolves id {asset_id!r}.")


class AssetPathEscapeError(AssetResolutionError):
    """Raised when an asset blob ``path`` escapes its anchoring root (NFR-006).

    Wraps the offering-layer :class:`OrgPackSubdirEscapeError` in an
    asset-domain type so containment refusals are catchable by identity.
    """

    def __init__(self, asset_id: str, blob_path: str, root: Path) -> None:
        self.asset_id = asset_id
        self.blob_path = blob_path
        self.root = root
        super().__init__(
            f"Asset {asset_id!r} blob path {blob_path!r} escapes its root {root}."
        )


class AssetRepository(BaseArtifactRepository[AssetManifest]):
    """Three-tier repository resolving asset ids to on-disk blob paths."""

    def __init__(
        self,
        built_in_dir: Path | None = None,
        *,
        org_dirs: list[Path] | None = None,
        project_dir: Path | None = None,
    ) -> None:
        # Must exist before ``super().__init__`` triggers ``_load`` -> the
        # ``_post_validate`` hook records into it (mirrors AgentProfileRepository).
        self._source_paths: dict[str, Path] = {}
        super().__init__(
            built_in_dir=built_in_dir or self._default_built_in_dir(),
            org_dirs=org_dirs,
            project_dir=project_dir,
        )

    @staticmethod
    def _default_built_in_dir() -> Path:
        """Return the shipped built-in asset directory from package data."""
        return built_in_dir(ArtifactKind.ASSET)

    @property
    def _schema(self) -> type[AssetManifest]:
        return AssetManifest

    @property
    def _glob(self) -> str:
        return "*.asset.yaml"

    def _post_validate(self, obj: AssetManifest, yaml_file: Path) -> None:
        """Record the declaring manifest file per id, only on successful load.

        The base ``_load`` visits built-in, then org, then project files in
        precedence order, calling this hook with the validated manifest and
        its file for every item that actually enters ``self._items``.
        Last-write-wins here mirrors the layer precedence the base applies to
        ``_items``/``_provenance``, so the tracked path always belongs to the
        tier that actually won the id. Firing on success only (rather than in
        ``_pre_validate``, before ``model_validate`` can still fail) means a
        manifest that fails validation never gets a stale ``_source_paths``
        entry — ``source_path(id)`` and ``get(id)`` agree.
        """
        self._source_paths[obj.id] = yaml_file

    def source_path(self, asset_id: str) -> Path:
        """Return the manifest file that declared *asset_id*.

        Raises:
            AssetNotFoundError: if no manifest declared the id.
        """
        source = self._source_paths.get(asset_id)
        if source is None:
            raise AssetNotFoundError(asset_id)
        return source

    def resolve_path(self, asset_id: str) -> Path:
        """Resolve *asset_id* to the on-disk blob path, fail-closed.

        Anchors the manifest ``path`` at the tier-correct root (A-2) and
        enforces containment through the offering-layer
        :func:`resolve_relative_path_within_root` primitive (A-4).

        Raises:
            AssetNotFoundError: if no manifest resolves the id.
            AssetPathEscapeError: if the blob ``path`` escapes its anchoring
                root via a ``..`` traversal or a symlink (NFR-006).
        """
        manifest = self.get(asset_id)
        if manifest is None:
            raise AssetNotFoundError(asset_id)
        anchor = self._anchor_for(asset_id)
        try:
            return resolve_relative_path_within_root(anchor, manifest.path)
        except OrgPackSubdirEscapeError as exc:
            raise AssetPathEscapeError(asset_id, manifest.path, anchor) from exc

    def _anchor_for(self, asset_id: str) -> Path:
        """Return the containment root the manifest ``path`` is relative to.

        Built-in blobs anchor at the **parent** of ``built_in_dir`` (the
        ``path`` already carries the ``built-in/`` segment); org/project blobs
        anchor at the overlay ``assets/`` directory that supplied the id.
        """
        provenance = self.get_provenance(asset_id)
        if provenance == "builtin":
            return self._built_in_dir.parent
        if provenance == "project" and self._project_dir is not None:
            return self._project_dir
        if provenance == "org":
            org_anchor = self._org_anchor_for(asset_id)
            if org_anchor is not None:
                return org_anchor
        raise AssetNotFoundError(asset_id)

    def _org_anchor_for(self, asset_id: str) -> Path | None:
        """Return the configured org ``assets/`` dir that contains the manifest."""
        source = self._source_paths.get(asset_id)
        if source is None:
            return None
        resolved_source = source.resolve(strict=False)
        for org_dir in self._org_dirs:
            if resolved_source.is_relative_to(org_dir.resolve(strict=False)):
                return org_dir
        return None
