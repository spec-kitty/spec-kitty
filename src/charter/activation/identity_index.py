"""Per-invocation, layer-aware identity index (FR-006, NFR-003).

An activation token or selection may spell an artifact two ways: its file stem
(``qa-tactic-seven``) or its declared id (``qa-seven``). :class:`IdentityIndex`
maps either spelling to the artifact's declared id, and back to a stem, for every
activatable kind. Entries are ordered by layer precedence (project, then org packs
from last to first declaration, then built-in). A lookup is stem-first across ALL
layers, then declared id across all layers, each first-match in that order -- the
same rule as :func:`charter.activation.kind_vocabulary.resolve_artifact_urn`; a
higher layer's declared id does not beat a lower layer's matching stem.

The index changes how ids are spelled, never which artifacts a base contains
(C-007). Each ``(kind, layer set)`` is scanned lazily and at most once per index
instance (NFR-003); an index is never persisted, so a fresh one always re-reads disk.

Import rule: this module must not import ``charter.activation.resolver`` or
``charter.activation.profile_resolution`` (they consume the index).
"""

from __future__ import annotations

import re
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


#: Conservative plain-string shape ruamel types as ``str``: a letter first, then ``[A-Za-z0-9_.-]``.
_PLAIN_ID_VALUE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*")
#: YAML scalars that are not strings (any case); a match always goes to the full parse.
_YAML_SPECIAL_SCALARS = frozenset({"true", "false", "yes", "no", "on", "off", "null", "y", "n", "~", ".nan", ".inf"})
_DOC_MARKER = re.compile(r"^(?:---|\.\.\.)(?:[ \t]|$)", re.MULTILINE)
_BLANK_OR_COMMENT = re.compile(r"(?:[ \t]*(?:#[^\n]*)?\n)*")


def _has_foreign_document_marker(text: str) -> bool:
    """Whether *text* has a ``...`` line or a ``---`` other than a leading one (after comments)."""
    markers = list(_DOC_MARKER.finditer(text))
    if not markers:
        return False
    first = markers[0]
    leading = first.group(0).startswith("---") and _BLANK_OR_COMMENT.fullmatch(text[: first.start()]) is not None
    return len(markers) > 1 or not leading


def _next_line_is_continuation(text: str, line_end: int) -> bool:
    """Whether the line after the one ending at *line_end* is indented (a multi-line plain scalar)."""
    following = text[line_end + 1 :]
    return following[:1] in (" ", "\t")


def _fast_plain_id(text: str, id_field: str) -> str | None:
    """The id when *text* declares it once as a plain string scalar, else ``None`` (use the full parse)."""
    if "\ufeff" in text or "\r" in text or _has_foreign_document_marker(text):
        return None
    key = re.escape(id_field)
    if len(re.findall(rf"^[\"']?{key}[\"']?[ \t]*:", text, re.MULTILINE)) != 1:
        return None
    found = re.search(rf"^{key}:[ \t]+(\S+)[ \t]*$", text, re.MULTILINE)
    if found is None:
        return None
    if "\t" in found.group(0) or _next_line_is_continuation(text, found.end()):
        return None
    value = found.group(1)
    if _PLAIN_ID_VALUE.fullmatch(value) is None or value.lower() in _YAML_SPECIAL_SCALARS:
        return None
    return value


def _declared_id_of(
    path: Path,
    id_field: str,
    yaml: YAML,
    resolution_pass: kind_vocabulary.ResolutionPass,
    fast_ids: dict[tuple[Path, str], str] | None = None,
) -> str | None:
    """Declared id of *path*; a single plain-string top-level ``id:`` line skips the full YAML parse (NFR-003).

    The fast path is taken only when the text has exactly one top-level ``<field>:`` key,
    its value is a conservative plain string (letter first, ``[A-Za-z0-9_.-]``, no comment,
    not a YAML special scalar), and the text has no BOM, CR or extra document markers.
    Everything else (numbers, booleans, null, quoted, commented, multi-document,
    duplicate keys, CRLF, BOM) falls back to :func:`kind_vocabulary._read_id`.

    Fast-path values are kept in the private *fast_ids* cache only; the shared
    *resolution_pass* is seeded exclusively by the canonical reader, so other
    consumers of the pass never see a value the canonical parse did not produce.

    Known, accepted limitation: syntax errors elsewhere in the file are not detected
    cheaply, so such a file yields its id here where the full parse yields ``None``. The
    artifact repositories reject that file when they load it, so it is never activatable.
    """
    key = (path, id_field)
    if key in resolution_pass.ids:
        return resolution_pass.ids[key]
    if fast_ids is not None and key in fast_ids:
        return fast_ids[key]
    try:
        fast = _fast_plain_id(path.read_text(encoding="utf-8"), id_field)
    except OSError:
        fast = None
    if fast is None:
        return kind_vocabulary._read_id(path, id_field, yaml, resolution_pass)
    if fast_ids is not None:
        fast_ids[key] = fast
    return fast


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
    _fast_ids: dict[tuple[Path, str], str] = field(default_factory=dict, init=False, repr=False)

    # ------------------------------------------------------------ builders --

    @classmethod
    def build(
        cls,
        repo_root: Path,
        *,
        org_roots: list[Path] | None = None,
        resolution_pass: kind_vocabulary.ResolutionPass | None = None,
    ) -> IdentityIndex:
        """Index *repo_root*'s layers; *org_roots* defaults to the existing configured chain.

        A caller that already resolved the roots passes *org_roots* and its shared
        *resolution_pass* so each file is read once per plan (NFR-003).
        """
        chain = resolve_pack_chain(repo_root, strict=False, quiet=True) if org_roots is None else org_roots
        project = project_pack_root(repo_root)
        index = cls(
            org_roots=[root for root in chain if root.is_dir()],
            project_root=project if project.is_dir() else None,
        )
        if resolution_pass is not None:
            index._pass = resolution_pass
        return index

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
                declared = _declared_id_of(path, id_field, yaml, self._pass, self._fast_ids)
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

    def declared_id_in_layer(self, kind: ArtifactKind, stem: str, layer: str) -> str | None:
        """Declared id of the file *stem* in exactly *layer*; ``None`` when that layer has no such file.

        Unlike :meth:`declared_id` (first match across layers), this never lets a
        higher layer that reuses the stem answer for a shadowed lower-layer row.
        """
        for entry in self._table(kind).entries:
            if entry.stem == stem and entry.layer == layer:
                return entry.declared_id
        return None

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

    @staticmethod
    def unindexed_key(kind: ArtifactKind | None, token: str) -> str:
        """Key for a *token* no index knows: the directive id normaliser, else the token itself."""
        return normalize_directive_id(token) if kind is ArtifactKind.DIRECTIVE else token

    def lookup_key(self, kind: ArtifactKind | None, token: str, *, selection: bool = False) -> str:
        """Repository / comparison key of *token* (stem or declared id): the declared id when known.

        One route for every surface that keys by declared id (selection rendering,
        ``--include`` lookup, preset comparison; FR-017, #6406). An unknown token
        falls back to :meth:`unindexed_key`. The two precedences differ only for
        directives: ``selection=True`` uses :meth:`selection_id` (a declared id beats a
        coincidentally equal filename, as selections do); the default uses
        :meth:`declared_id` (stem first, as activation lists and ``--include`` do).
        """
        if kind is not None:
            known = self.selection_id(kind, token) if selection else self.declared_id(kind, token)
            if known is not None:
                return known
        return self.unindexed_key(kind, token)

    def activation_id(self, kind: ArtifactKind, token: str, warnings: list[str]) -> str:
        """Single route for activation-list tokens.

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
