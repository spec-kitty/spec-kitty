"""Generic three-source loading base class for all doctrine asset repositories.

All doctrine sub-repositories share an identical ``_load()`` pattern:
walk a built-in YAML directory (rglob), optionally walk an org override
directory (glob), optionally walk a project override directory (glob),
parse each file with Pydantic ``model_validate``, merge overrides into
built-in instances at field level, and warn on bad files.
``BaseDoctrineRepository[T]`` captures that pattern once.

The loading order is: built-in → org → project, where each subsequent layer
can override or add artifacts from the previous layers.

Subclasses declare:

- ``_schema`` — the Pydantic model class (abstract property)
- ``_glob``   — the YAML file glob pattern, e.g. ``"*.paradigm.yaml"``
  (abstract property)

Subclasses may override:

- ``_key(obj)``             — extract the dict key; default is ``obj.id``
- ``_pre_validate(data, f)`` — hook called before ``model_validate``; default
  is a no-op.  Use it for inline-ref rejection or other pre-checks.
- ``_project_scan(dir)``    — return the list of project YAML files; default
  is a non-recursive ``glob``.  Override with ``rglob`` for repos that allow
  subdirectory structure in the project layer (e.g. styleguides).
"""

from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.discovery_recursion import overlay_scan_is_recursive
from charter.offering.shared.scoping import applies_to_languages_match, normalize_languages
from charter.offering.yaml_utils import parse_shipped_yaml

T = TypeVar("T", bound=BaseModel)


class DoctrineLayerCollisionWarning(UserWarning):
    """Emitted when a higher doctrine layer shadows an artifact from a lower layer.

    Field-level merge semantics apply (see ADR
    ``docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md``):
    fields present in the higher layer's YAML replace same-named fields in the
    lower layer; absent fields fall through. This warning makes the collision
    operator-visible so silent shadowing of builtin or org artifacts cannot
    surprise consumers. Operators who maintain heavy overrides can filter
    this category via standard ``warnings`` machinery.
    """


def _emit_collision_warning(
    *,
    kind: str,
    item_id: str,
    higher_layer: str,
    lower_layer: str,
    higher_data: dict[str, Any],
    lower_dump: dict[str, Any],
) -> None:
    """Emit a DoctrineLayerCollisionWarning for a single artifact ID collision."""
    higher_keys = set(higher_data.keys())
    lower_keys = set(lower_dump.keys())
    replaced = len(higher_keys & lower_keys)
    inherited = len(lower_keys - higher_keys)
    warnings.warn(
        f"Doctrine override: {kind} {item_id} from {higher_layer} shadowed "
        f"{lower_layer} ({replaced} field(s) replaced; "
        f"{inherited} field(s) inherited).",
        DoctrineLayerCollisionWarning,
        stacklevel=3,
    )


class BaseDoctrineRepository(ABC, Generic[T]):
    """Abstract base for all doctrine asset repositories.

    Provides the three-source loading pattern (built-in rglob + org glob + project glob)
    with field-level merge semantics and warning emission on bad files.

    The loading order is: built-in → org → project, where each layer can override
    or add artifacts from the previous layer.  Every resolved artifact is tagged
    with its source layer in ``_provenance``.
    """

    def __init__(
        self,
        built_in_dir: Path,
        *,
        org_dirs: list[Path] | None = None,
        project_dir: Path | None = None,
        active_languages: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self._built_in_dir = built_in_dir
        self._org_dirs: list[Path] = list(org_dirs) if org_dirs else []
        self._project_dir = project_dir
        self._active_languages = None if active_languages is None else normalize_languages(active_languages)
        self._items: dict[str, T] = {}
        self._provenance: dict[str, str] = {}
        self._scope_filtered_ids: set[str] = set()
        self._load()

    # ------------------------------------------------------------------ #
    # Abstract interface — subclasses must implement these                 #
    # ------------------------------------------------------------------ #

    @property
    @abstractmethod
    def _schema(self) -> type[T]:
        """Pydantic model class for this repository's asset type."""
        ...

    @property
    @abstractmethod
    def _glob(self) -> str:
        """YAML file glob pattern, e.g. ``"*.paradigm.yaml"``."""
        ...

    # ------------------------------------------------------------------ #
    # Virtual hooks — subclasses may override                              #
    # ------------------------------------------------------------------ #

    def _pre_validate(self, data: dict[str, Any], yaml_file: Path) -> None:
        """Called on raw YAML data before ``model_validate``. Default: no-op.

        Override to add inline-ref rejection or other pre-checks.
        """

    def _post_validate(self, obj: T, yaml_file: Path) -> None:
        """Called after a successful ``model_validate``/merge. Default: no-op.

        Fired at all three item-entry points (built-in load, overlay merge
        branch, overlay new-item branch), gated by the same
        ``_include_item`` condition that gates the actual ``self._items``
        write — so a scope-filtered-but-valid item is not recorded here
        either. Use this (not ``_pre_validate``) for bookkeeping that must
        reflect only artifacts that actually loaded, e.g. a source-path
        index: ``_pre_validate`` runs before the validation/merge that can
        still fail, so success-gated state belongs here instead.
        """

    def _key(self, obj: T) -> str:
        """Extract the dict key for a loaded asset. Default: ``obj.id``."""
        return obj.id  # type: ignore[attr-defined, no-any-return]

    def _project_scan(self, project_dir: Path) -> list[Path]:
        """Return the org/project overlay YAML files to load.

        Recursion is sourced from the single doctrine recursion authority
        (:func:`doctrine.discovery_recursion.overlay_scan_is_recursive`),
        unconditional per C-001, so org/project overlays discover nested
        artifacts with the same completeness as the built-in tier's ``rglob``
        (:meth:`_load_built_in_items`). The kind-specific ``self._glob`` (C-002)
        means a recursive walk never captures ``.provenance/*.yaml`` sidecars or
        ``.md`` files. Subclasses no longer override this to add ``rglob`` — the
        authority is the single source both loader and resolver share.
        """
        recursive = overlay_scan_is_recursive(self._overlay_scan_kind())
        scan = (
            project_dir.rglob(self._glob)
            if recursive
            else project_dir.glob(self._glob)
        )
        return sorted(scan)

    def _overlay_scan_kind(self) -> ArtifactKind | None:
        """Resolve this repository's :class:`ArtifactKind` from its glob pattern.

        Each canonical kind carries a unique :attr:`ArtifactKind.glob_pattern`
        (e.g. ``*.tactic.yaml``), so ``self._glob`` identifies the kind without a
        second per-repo kind declaration. Returns ``None`` when the glob is not a
        canonical pattern (a test stub or a future non-enum kind); the recursion
        authority treats ``None`` as the same unconditional recursive policy
        (C-001), so an unmapped repository still recurses. Kept as a live call
        into the authority — not a hardcoded ``True`` — so the parity gate can
        falsify a reintroduced per-kind divergence.
        """
        for kind in ArtifactKind:
            if kind.glob_pattern and kind.glob_pattern == self._glob:
                return kind
        return None

    def _include_item(self, obj: T) -> bool:
        """Return whether a loaded asset applies to the active language scope."""
        included: bool = applies_to_languages_match(
            getattr(obj, "applies_to_languages", None),
            self._active_languages,
        )
        return included

    # ------------------------------------------------------------------ #
    # Concrete implementation                                              #
    # ------------------------------------------------------------------ #

    @property
    def _kind(self) -> str:
        """Human-readable asset kind derived from the class name."""
        return type(self).__name__.removesuffix("Repository").lower()

    def _load_built_in_items(self, yaml_parser: YAML) -> dict[str, T]:
        """Parse all built-in YAML files and return a keyed dict."""
        built_in: dict[str, T] = {}
        if not self._built_in_dir.exists():
            return built_in
        for yaml_file in sorted(self._built_in_dir.rglob(self._glob)):
            try:
                data = parse_shipped_yaml(yaml_file, yaml_parser.load, variant="safe")
                if data is None:
                    continue
                self._pre_validate(data, yaml_file)
                obj = self._schema.model_validate(data)
                if not self._include_item(obj):
                    self._scope_filtered_ids.add(self._key(obj))
                    continue
                self._post_validate(obj, yaml_file)
                built_in[self._key(obj)] = obj
            except (YAMLError, ValidationError, OSError) as exc:
                warnings.warn(
                    f"Skipping invalid built-in {self._kind} {yaml_file.name}: {exc}",
                    UserWarning,
                    stacklevel=3,
                )
        return built_in

    def _record_collision_if_present(
        self,
        *,
        item_id: str,
        higher_layer: str,
        higher_data: dict[str, Any],
    ) -> None:
        """Emit a DoctrineLayerCollisionWarning iff ``item_id`` is already loaded.

        Called at write time before ``self._items[item_id]`` is overwritten so
        the lower-layer dump is still available for field-count accounting.
        """
        if item_id not in self._items:
            return
        existing = self._items[item_id]
        lower_layer = self._provenance.get(item_id, "unknown")
        _emit_collision_warning(
            kind=self._kind,
            item_id=item_id,
            higher_layer=higher_layer,
            lower_layer=lower_layer,
            higher_data=higher_data,
            lower_dump=existing.model_dump(),
        )

    def _apply_overlay_layer(
        self,
        dirs: Sequence[Path],
        layer_name: str,
        *,
        yaml_parser: YAML,
        built_in: dict[str, T],
    ) -> None:
        """Apply a stack of overlay directories to ``self._items`` with the given provenance.

        Used for both the org and project layers. Mirrors the field-merge semantics
        ratified by ADR 2026-05-16-1: for each YAML file in each dir, parse + validate
        + merge-or-insert against ``built_in``. Tag every resulting item with the given
        layer_name as provenance.

        Emits a ``DoctrineLayerCollisionWarning`` whenever an overlay artifact
        shadows an already-loaded artifact from a lower layer (FR-003 wording
        per ADR 2026-05-16-1).

        Args:
            dirs: ordered list of overlay directories. Later dirs override earlier
                  ones for the same artifact ID (FR-006, C-004 of the org-layer
                  mission).
            layer_name: provenance string ("org" or "project").
            yaml_parser: pre-configured YAML loader.
            built_in: the resolved built-in items map (target of merge-on-collision).
        """
        for overlay_dir in dirs:
            if not overlay_dir.exists():
                continue
            for yaml_file in self._project_scan(overlay_dir):
                self._apply_overlay_file(
                    yaml_file, layer_name, yaml_parser=yaml_parser, built_in=built_in
                )

    def _apply_overlay_file(
        self,
        yaml_file: Path,
        layer_name: str,
        *,
        yaml_parser: YAML,
        built_in: dict[str, T],
    ) -> None:
        """Parse, validate, and merge-or-insert one overlay YAML file.

        Extracted from :meth:`_apply_overlay_layer` to keep its cognitive
        complexity within the ruff C901 limit (15); the per-file logic now
        starts at nesting level 0 instead of nested under two loops. Moving
        this one stack frame deeper than the original inline block bumps the
        ``warnings.warn`` ``stacklevel`` from 3 to 4 so the warning is still
        attributed to the repository's construction call site.
        """
        try:
            data = yaml_parser.load(yaml_file)
            if data is None:
                return
            self._pre_validate(data, yaml_file)
            item_id = data.get("id")
            if not item_id:
                warnings.warn(
                    f"Skipping {layer_name} {self._kind} {yaml_file.name}: no id",
                    UserWarning,
                    stacklevel=4,
                )
                return
            if item_id in built_in:
                self._merge_overlay_item(item_id, data, yaml_file, built_in, layer_name)
            else:
                self._insert_overlay_item(data, yaml_file, layer_name)
        except (YAMLError, ValidationError, OSError) as exc:
            warnings.warn(
                f"Skipping invalid {layer_name} {self._kind} {yaml_file.name}: {exc}",
                UserWarning,
                stacklevel=4,
            )

    def _merge_overlay_item(
        self,
        item_id: str,
        data: dict[str, Any],
        yaml_file: Path,
        built_in: dict[str, T],
        layer_name: str,
    ) -> None:
        """Field-merge an overlay item that shares an ID with a built-in item.

        Extracted from :meth:`_apply_overlay_file` (itself extracted from
        :meth:`_apply_overlay_layer`) to keep cognitive complexity within the
        ruff C901 limit (15).
        """
        merged = self._merge(built_in[item_id], data)
        if not self._include_item(merged):
            self._scope_filtered_ids.add(item_id)
            return
        self._record_collision_if_present(
            item_id=item_id,
            higher_layer=layer_name,
            higher_data=data,
        )
        self._post_validate(merged, yaml_file)
        self._items[item_id] = merged
        self._provenance[item_id] = layer_name
        self._scope_filtered_ids.discard(item_id)

    def _insert_overlay_item(
        self,
        data: dict[str, Any],
        yaml_file: Path,
        layer_name: str,
    ) -> None:
        """Validate and insert a new overlay item with no built-in counterpart.

        Extracted from :meth:`_apply_overlay_file` (itself extracted from
        :meth:`_apply_overlay_layer`) to keep cognitive complexity within the
        ruff C901 limit (15).
        """
        obj = self._schema.model_validate(data)
        if not self._include_item(obj):
            self._scope_filtered_ids.add(self._key(obj))
            return
        key = self._key(obj)
        self._record_collision_if_present(
            item_id=key,
            higher_layer=layer_name,
            higher_data=data,
        )
        self._post_validate(obj, yaml_file)
        self._items[key] = obj
        self._provenance[key] = layer_name
        # An admitted overlay supersedes a built-in of the same id that the
        # language scope filtered out: the id is live, not filtered (F1).
        self._scope_filtered_ids.discard(key)

    def _load(self) -> None:
        """Walk built-in + org + project dirs, parse, merge, warn on failure."""
        yaml_parser = YAML(typ="safe")
        built_in = self._load_built_in_items(yaml_parser)
        self._items = built_in.copy()
        # Tag all built-in items as 'builtin'
        self._provenance = dict.fromkeys(self._items, "builtin")
        # Org layer overrides built-in
        self._apply_overlay_layer(
            self._org_dirs, "org", yaml_parser=yaml_parser, built_in=built_in
        )
        # Project layer overrides built-in + org
        self._apply_overlay_layer(
            [self._project_dir] if self._project_dir else [],
            "project",
            yaml_parser=yaml_parser,
            built_in=built_in,
        )

    def _merge(self, built_in: T, project_data: dict[str, Any]) -> T:
        """Merge project override into a built-in instance at field level."""
        merged = {**built_in.model_dump(), **project_data}
        return type(built_in).model_validate(merged)

    def list_all(self) -> list[T]:
        """Return all loaded assets sorted by key."""
        return sorted(self._items.values(), key=lambda obj: self._key(obj))

    def all(self) -> list[T]:
        """Alias for :meth:`list_all` — used by Mission B ATDD tests that
        iterate the catalog to force three-layer load and surface collision
        warnings.  Added in WP06 (charter-mediated-doctrine-selection)
        because the test suite uses the more conversational ``.all()``
        name while existing call sites use ``.list_all()``."""
        return self.list_all()

    def get(self, item_id: str) -> T | None:
        """Get asset by ID."""
        return self._items.get(item_id)

    def get_provenance(self, item_id: str) -> str | None:
        """Return the source layer for the given artifact ID.

        Returns one of ``"builtin"``, ``"org"``, or ``"project"``, or
        ``None`` if the artifact is not loaded.
        """
        return self._provenance.get(item_id)

    @property
    def scope_filtered_ids(self) -> frozenset[str]:
        """IDs of artifacts that were excluded by the active language scope filter.

        An artifact appears here when it exists on disk and passed schema
        validation, but its ``applies_to_languages`` field did not overlap
        with the active language set configured at construction time.  The
        set is populated during :meth:`_load` and is read-only after that.
        Callers should use this to distinguish a scope-filtered miss
        (``SCOPE_FILTERED``) from a genuinely absent artifact
        (``MISSING_ARTIFACT``).
        """
        return frozenset(self._scope_filtered_ids)


__all__ = ["BaseDoctrineRepository"]
