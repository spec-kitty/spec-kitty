"""Per-invocation, layer-aware identity index (FR-006, NFR-003).

An activation token or selection may spell an artifact two ways: its file stem
(``qa-tactic-seven``) or its declared id (``qa-seven``). :class:`IdentityIndex`
maps either spelling to the artifact's declared id, and back to a stem, for every
activatable kind, honouring layer precedence (project, then org packs from last to
first declaration, then built-in -- the same first-match order as
:mod:`charter.activation.kind_vocabulary`).

The index changes how ids are spelled, never which artifacts a base contains
(C-007). Each ``(kind, layer set)`` is scanned lazily and at most once per index
instance (NFR-003); an index is never persisted, so a fresh one always re-reads disk.

Import rule: this module must not import ``charter.activation.resolver`` or
``charter.activation.profile_resolution`` (they consume the index).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from charter.activation import kind_vocabulary
from charter.activation.catalog import resolve_offering_root
from charter.activation.layer_roots import resolve_pack_chain
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.migration.id_normalizer import normalize_directive_id
from kernel.charter_pack_paths import project_pack_root

if TYPE_CHECKING:
    from charter.activation.pack_context import PackContext

__all__ = ["IdentityEntry", "IdentityIndex"]

_LAYER_PROJECT = "project"
_LAYER_ORG = "org"
_LAYER_BUILT_IN = "built-in"


@dataclass(frozen=True)
class IdentityEntry:
    """One artifact file: its stem, declared id and the layer it comes from."""

    kind: ArtifactKind
    stem: str
    declared_id: str
    layer: str


@dataclass(frozen=True)
class _KindTable:
    """Precedence-ordered entries for one kind plus first-match lookups."""

    entries: tuple[IdentityEntry, ...]
    by_stem: dict[str, IdentityEntry]
    by_id: dict[str, IdentityEntry]
    ids_by_stem: dict[str, frozenset[str]]

    @classmethod
    def from_entries(cls, entries: list[IdentityEntry]) -> _KindTable:
        by_stem: dict[str, IdentityEntry] = {}
        by_id: dict[str, IdentityEntry] = {}
        ids: dict[str, set[str]] = {}
        for entry in entries:
            by_stem.setdefault(entry.stem, entry)
            by_id.setdefault(entry.declared_id, entry)
            ids.setdefault(entry.stem, set()).add(entry.declared_id)
        return cls(tuple(entries), by_stem, by_id, {stem: frozenset(found) for stem, found in ids.items()})


def _layer_of(scan_dir: Path, project_root: Path | None, org_roots: list[Path]) -> str:
    """Name the layer a scanned directory belongs to."""
    if project_root is not None and scan_dir.is_relative_to(project_root):
        return _LAYER_PROJECT
    if any(scan_dir.is_relative_to(root) for root in org_roots):
        return _LAYER_ORG
    return _LAYER_BUILT_IN


@dataclass
class IdentityIndex:
    """Token <-> declared id <-> stem resolution across the project/org/built-in layers."""

    org_roots: list[Path]
    project_root: Path | None = None
    _offering_root: Path = field(default_factory=resolve_offering_root)
    _tables: dict[ArtifactKind, _KindTable] = field(default_factory=dict, init=False, repr=False)
    _pass: kind_vocabulary.ResolutionPass = field(default_factory=kind_vocabulary.ResolutionPass, init=False, repr=False)

    # ------------------------------------------------------------ builders --

    @classmethod
    def build(cls, repo_root: Path, *, org_roots: list[Path] | None = None) -> IdentityIndex:
        """Index *repo_root*'s layers; *org_roots* defaults to the existing configured chain."""
        chain = resolve_pack_chain(repo_root, strict=False, quiet=True) if org_roots is None else org_roots
        project = project_pack_root(repo_root)
        return cls(
            org_roots=[root for root in chain if root.is_dir()],
            project_root=project if project.is_dir() else None,
        )

    @classmethod
    def from_pack_context(cls, ctx: PackContext, *, repo_root: Path | None = None) -> IdentityIndex:
        """Index the org roots of *ctx* (existing directories only)."""
        project = project_pack_root(repo_root) if repo_root is not None else None
        return cls(
            org_roots=[root for root in ctx.org_roots if root.is_dir()],
            project_root=project if project is not None and project.is_dir() else None,
        )

    # --------------------------------------------------------------- scan ---

    def _table(self, kind: ArtifactKind) -> _KindTable:
        table = self._tables.get(kind)
        if table is None:
            table = _KindTable.from_entries(self._scan(kind))
            self._tables[kind] = table
        return table

    def _scan(self, kind: ArtifactKind) -> list[IdentityEntry]:
        pattern = kind.glob_pattern
        if not pattern:
            return []
        layer_roots = {_LAYER_PROJECT: self.project_root} if self.project_root is not None else None
        yaml = YAML(typ="safe")
        id_field = kind_vocabulary._id_field_for(kind)
        entries: list[IdentityEntry] = []
        for scan_dir, recursive in kind_vocabulary._scan_roots(
            kind,
            _offering_root=self._offering_root,
            org_roots=self.org_roots,
            layer_roots=layer_roots,
        ):
            layer = _layer_of(scan_dir, self.project_root, self.org_roots)
            for path in sorted(kind_vocabulary._scan_dir_matches(scan_dir, pattern, recursive=recursive)):
                declared = kind_vocabulary._read_id(path, id_field, yaml, self._pass)
                if declared:
                    entries.append(IdentityEntry(kind, kind_vocabulary._config_stem(path), declared, layer))
        return entries

    # ------------------------------------------------------------- lookups --

    def _lookup(self, kind: ArtifactKind, token: str) -> IdentityEntry | None:
        """Stem first, then exact declared id, then (directives) the normalised id."""
        table = self._table(kind)
        entry = table.by_stem.get(token) or table.by_id.get(token)
        if entry is None and kind is ArtifactKind.DIRECTIVE:
            entry = table.by_id.get(normalize_directive_id(token))
        return entry

    def declared_id(self, kind: ArtifactKind, token: str) -> str | None:
        """Declared id for a stem or declared-id *token*; ``None`` when unknown."""
        entry = self._lookup(kind, token)
        return entry.declared_id if entry is not None else None

    def knows(self, kind: ArtifactKind, token: str) -> bool:
        """Whether *token* names a known artifact of *kind*."""
        return self._lookup(kind, token) is not None

    def source_layer(self, kind: ArtifactKind, token: str) -> str | None:
        """Layer (``project`` / ``org`` / ``built-in``) *token* resolves in, if known."""
        entry = self._lookup(kind, token)
        return entry.layer if entry is not None else None

    def selection_id(self, kind: ArtifactKind, token: str) -> str | None:
        """Declared id for a *selection*; directives prefer a declared id over a stem.

        Mirrors :func:`charter.activation.kind_vocabulary.resolve_selected_id_to_stem`
        (directive identities beat a coincidentally equal filename).
        """
        if kind is ArtifactKind.DIRECTIVE and token in self._table(kind).by_id:
            return token
        return self.declared_id(kind, token)

    def stem(self, kind: ArtifactKind, token: str) -> str | None:
        """Activation stem for *token*; ``None`` when unknown or no stem represents the id.

        Directives are id-first (as selections are); other kinds are stem-first. A
        directive stem that two layers bind to different ids cannot stand for either.
        """
        table = self._table(kind)
        if kind is ArtifactKind.DIRECTIVE and token in table.by_id:
            return self._representable_stem(kind, token)
        if token in table.by_stem:
            return token
        declared = self.declared_id(kind, token)
        return self._representable_stem(kind, declared) if declared is not None else None

    def _representable_stem(self, kind: ArtifactKind, declared: str) -> str | None:
        table = self._table(kind)
        for entry in table.entries:
            if entry.declared_id != declared:
                continue
            if kind is not ArtifactKind.DIRECTIVE:
                return entry.stem
            if table.by_stem[entry.stem].declared_id == declared and len(table.ids_by_stem[entry.stem]) <= 1:
                return entry.stem
        return None

    def resolve_many(self, kind: ArtifactKind, tokens: Iterable[str]) -> tuple[list[str], list[str]]:
        """Split *tokens* into ``(declared ids, unknown tokens)``, order-preserving and de-duplicated."""
        ids: list[str] = []
        unknown: list[str] = []
        for token in tokens:
            declared = self.declared_id(kind, token)
            bucket, value = (unknown, token) if declared is None else (ids, declared)
            if value not in bucket:
                bucket.append(value)
        return ids, unknown

    def activation_id(self, kind: ArtifactKind, token: str, warnings: list[str]) -> str:
        """Single route for activation-list tokens (WP02/WP03/WP10 must use it).

        A known token yields its declared id. An unknown directive token falls back to
        the id normaliser, other kinds keep the token, and either way one warning is
        appended (#4240). ``anti_pattern`` has no files and passes through silently.
        """
        declared = self.declared_id(kind, token)
        if declared is not None:
            return declared
        if kind is ArtifactKind.ANTI_PATTERN:
            return token
        resolved = normalize_directive_id(token) if kind is ArtifactKind.DIRECTIVE else token
        warnings.append(f"unresolved {kind.value} activation token {token!r}; best-effort resolved to {resolved!r}")
        return resolved
