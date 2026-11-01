"""Canonical kind & artifact-ID vocabulary resolver (FR-027, R-009, R-011-D).

This module is the single seam through which charter-layer consumers route two
vocabularies that were previously re-declared across five+ modules with three
incompatible spellings (research R-009):

1. **Operator kind tokens** (hyphenated CLI surface, e.g. ``agent-profile``) →
   canonical :class:`~charter.offering.artifact_kinds.ArtifactKind`. That mapping lives
   on the enum itself (:meth:`ArtifactKind.from_operator_token`); this module
   re-exports the related error type for charter callers.

2. **Artifact config-stem IDs ↔ DRG URN node IDs** (research R-011-D, the dual
   "config stem vs DRG ``id``" system). A config/file-stem ID such as
   ``001-architectural-integrity-standard`` resolves to the DRG URN node ID
   ``directive:DIRECTIVE_001`` (and back) by reading the artifact's existing
   ``id:`` field — the same field already read by
   :func:`charter.activation.catalog._extract_artifact_id`.

Canonical charter kind universe
-------------------------------
The charter kind universe is the 8 artifact :class:`ArtifactKind` kinds **plus**
``mission-type`` (which is *not* an :class:`ArtifactKind` member and is handled
mission-tier; see FR-032 / WP04). ``template`` *is* an :class:`ArtifactKind`
member but is resolved specially (mission-tier, no glob) and has no config-stem
↔ URN entry. Consumers must route every kind string through
:meth:`ArtifactKind.from_operator_token` (CC-4) — no second kind enumeration may
be re-declared in a consumer.

Layering
--------
Charter layer: this module may import ``doctrine`` and ``kernel`` but never
``specify_cli``. Org/project roots are passed in **as data** (C-008); this module
does not resolve them.

This WP (WP01) delivers the resolver and its tests only. Consumer rewiring
(``pack_manager`` WP09, ``list`` WP16, ``context`` WP17) lives in later WPs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.artifact_kinds import (
    CHARTER_KIND_TOKENS,
    MISSION_TYPE_TOKEN,
    PROJECT_KIND_DIRS as _PROJECT_KIND_DIRS,
    ArtifactKind,
    MissionTypeNotAnArtifactKind,
)
from charter.offering.discovery_recursion import overlay_scan_is_recursive
from charter.offering.missions.repository import MissionsRootNotFound
from charter.offering.missions.step_contracts import MissionStepContractRepository
from charter.offering.pack_paths import (
    BuiltInContentDirNotAvailable,
    PackRootNotFound,
    built_in_dir,
)

if TYPE_CHECKING:
    # Annotation-only: ``identity_index`` imports this module, so the facade imports
    # it inside the function that needs it (#6433).
    from charter.activation.identity_index import IdentityIndex

#: Public re-export of :data:`charter.offering.artifact_kinds.PROJECT_KIND_DIRS`.
#:
#: Landing-fold addition (write-side-seam-matrix-tracer Wave B / #3070):
#: the ``spec-kitty charter new`` scaffolder
#: (``specify_cli.cli.commands.charter.authoring``) needs the project-tier
#: directory-per-kind mapping but, as a runtime-layer module, may not import
#: ``charter.offering.*`` directly (the runtime -> charter facade ->
#: charter.offering boundary ratchet, ``test_runtime_charter_doctrine_boundary.py``).
#: This module already imports the mapping privately (as
#: ``_PROJECT_KIND_DIRS``, kept for the existing internal partial-table
#: distinction below); this public alias is the thin facade re-export the
#: boundary doc's Phase-2 recipe calls for, without disturbing the private
#: name other tests already import.
PROJECT_KIND_DIRS = _PROJECT_KIND_DIRS

__all__ = [
    "ArtifactKind",
    "CHARTER_KIND_TOKENS",
    "MISSION_TYPE_TOKEN",
    "PROJECT_KIND_DIRS",
    "MissionTypeNotAnArtifactKind",
    "ResolutionPass",
    "UnknownArtifactIdError",
    "UnrepresentableDirectiveIdError",
    "resolve_artifact_urn",
    "resolve_config_id",
    "resolve_selected_id_to_stem",
    "unknown_artifact_id_error",
]


class UnknownArtifactIdError(ValueError):
    """Raised when a config-stem ID or DRG URN node ID cannot be resolved.

    Used by downstream unknown-ID validation (WP10) and cascade resolution
    (WP11). The message names both the kind and the offending ID so the error
    is actionable without grepping.
    """


#: YAML key holding the artifact ID, per kind. Most artifacts use ``id``;
#: agent profiles use ``profile-id`` (matching ``catalog._load_yaml_id_catalog``).
_ID_FIELD_BY_KIND: dict[ArtifactKind, str] = {
    ArtifactKind.AGENT_PROFILE: "profile-id",
}
_DEFAULT_ID_FIELD = "id"
#: The project-tier overlay directory name per kind is the single canonical
#: authority :data:`charter.offering.artifact_kinds.PROJECT_KIND_DIRS` (imported and
#: re-exported above as ``PROJECT_KIND_DIRS`` — the runtime→charter→doctrine
#: boundary facade for this mapping; see ``cli/commands/charter/authoring.py``'s
#: ``new`` scaffolder for the consumer). It is *total*, so
#: ``.get(kind, kind.plural)`` below never actually falls back — the default
#: is retained only as a belt-and-braces guard against a future partial
#: authority. No mapping is re-declared here (WP03 T014).


def _id_field_for(kind: ArtifactKind) -> str:
    return _ID_FIELD_BY_KIND.get(kind, _DEFAULT_ID_FIELD)


def _read_id(
    path: Path,
    id_field: str,
    yaml: YAML,
    resolution_pass: ResolutionPass | None = None,
    *,
    text: str | None = None,
) -> str | None:
    """Return the artifact ID from a YAML file, falling back to the file stem.

    Mirrors the logic behind :func:`charter.activation.catalog._extract_artifact_id`
    (without the language-scoping filter, which is not relevant to ID identity).
    With a *resolution_pass*, each file is parsed at most once per pass. A caller
    that already read the file (the :class:`~charter.activation.identity_index.IdentityIndex`
    fast-id probe) passes its *text* so the file is read once, not twice.
    """
    if resolution_pass is None:
        return _parse_id(path, id_field, yaml, text=text)
    key = (path, id_field)
    if key not in resolution_pass.ids:
        resolution_pass.ids[key] = _parse_id(path, id_field, yaml, text=text)
    return resolution_pass.ids[key]


def _parse_id(path: Path, id_field: str, yaml: YAML, *, text: str | None = None) -> str | None:
    """Parse *path* (or the already-read *text*) and return its declared ID, falling back to the file stem."""
    try:
        data = yaml.load(text if text is not None else path.read_text(encoding="utf-8")) or {}
    except (OSError, YAMLError, TypeError):
        return None
    if isinstance(data, dict):
        raw_id = str(data.get(id_field, "")).strip()
        if raw_id:
            return raw_id
    fallback = path.stem.split(".")[0].strip()
    return fallback or None


def _config_stem(path: Path) -> str:
    """Return the config/file-stem ID for an artifact path.

    The config stem is the filename with all extension suffixes removed
    (e.g. ``001-architectural-integrity-standard.directive.yaml`` →
    ``001-architectural-integrity-standard``).
    """
    return path.name.split(".", 1)[0]


def _scan_roots(
    kind: ArtifactKind,
    *,
    _offering_root: Path,
    org_roots: list[Path] | None,
    layer_roots: dict[str, Path] | None,
) -> list[tuple[Path, bool]]:
    """Return the ``(directory, recursive)`` pairs to scan for *kind*.

    Roots are supplied as data (C-008). ``_offering_root`` is the resolved
    ``charter.offering`` package root -- retained in the signature for call-site symmetry
    with :func:`_iter_artifact_paths` (and its callers' diagnostics) but no
    longer used as a scan root itself: built-in content was flattened out of
    ``<offering_root>/<kind>/built-in`` into ``packs/built-in/<kind>``
    (relocation mission doctrine-built-in-seam-consolidation-01KYW3TX, WP02),
    which resolves via the shared :func:`~charter.offering.pack_paths.built_in_dir`
    seam below instead. ``org_roots`` contributes, for each root, the flat
    ``<root>/<plural>`` layout that every real org pack uses today -- plus,
    additively, the legacy package-shaped ``<root>/<plural>/built-in`` layout
    (``recursive=True``) where that also separately exists.

    The flat entry's ``recursive`` flag is sourced from the single shared
    recursion authority :func:`charter.offering.discovery_recursion.overlay_scan_is_recursive`
    -- the same authority the live loader consults
    (:meth:`charter.offering.base.BaseArtifactRepository._project_scan`, which now
    recurses unconditionally for every kind's org/project overlay, and
    :meth:`charter.offering.agent_profiles.repository.AgentProfileRepository._load`).
    So the resolver and the loader recurse identically for **every** kind
    (C-001, unconditional), reading nested org/project subdirectories such as
    ``styleguides/writing/`` the same way. The prior divergence -- where the
    resolver emitted ``recursive=False`` while only the ``styleguide`` and
    ``asset`` repositories overrode ``_project_scan`` to ``rglob`` -- is closed:
    those redundant overrides were removed in favour of the recursive base, and
    the parity/totality gate pins loader↔resolver agreement.
    ``layer_roots`` is the modern charter layer map.
    Only the project layer is read from it: its root is the project pack root
    (``.kittify/charter-packs/``) and kind directories join onto it; org packs
    are scanned flat through ``org_roots``. Resolution scans project first, then org packs from last to
    first declaration, then built-in, matching runtime overlay precedence.

    Several built-in kinds (tactics, styleguides, toolguides) organize
    artifacts into category subdirectories (e.g.
    ``tactics/built-in/testing/acceptance-test-first.tactic.yaml``), which a
    non-recursive scan would silently miss -- the exact silent-drop failure
    mode C-006 forbids; the shared authority makes org/project match built-in
    here.
    """
    # Resolution is first-match-wins; repositories overlay in the opposite
    # order: built-in, org packs in declaration order, then project.
    layers = layer_roots or {}
    ordered_layers = dict(sorted(layers.items(), key=lambda item: item[0] != "project"))
    dirs = _layer_scan_dirs(kind, ordered_layers)
    dirs.extend(_org_scan_dirs(kind, list(reversed(org_roots or []))))
    built_in = _built_in_scan_dir(kind)
    if built_in is not None:
        dirs.append(built_in)
    return dirs


def _built_in_scan_dir(kind: ArtifactKind) -> tuple[Path, bool] | None:
    """Return the flattened built-in scan dir for *kind*, or ``None``.

    ``None`` covers both the fail-soft ``built_in_dir`` errors (see the
    ``_scan_roots`` docstring) and the case where the resolved directory does
    not exist on disk.

    ``mission_step_contract`` has no ``packs/built-in/<plural>/`` content dir;
    its built-in files live in the flat ``missions/built_in_step_contracts``
    directory, the one :class:`MissionStepContractRepository` loads (FR-015,
    #6527), so every resolver over this scan sees them as the runtime does.
    """
    if kind is ArtifactKind.MISSION_STEP_CONTRACT:
        return _built_in_step_contract_dir()
    try:
        flattened_built_in = built_in_dir(kind)
    except (PackRootNotFound, BuiltInContentDirNotAvailable):
        return None
    if flattened_built_in is not None and flattened_built_in.is_dir():
        return (flattened_built_in, True)
    return None


def _built_in_step_contract_dir() -> tuple[Path, bool] | None:
    """The flat built-in step-contract directory (non-recursive), or ``None`` when it cannot be located."""
    try:
        directory = MissionStepContractRepository.built_in_dir()
    except (PackRootNotFound, MissionsRootNotFound):
        return None
    return (directory, False) if directory.is_dir() else None


def _org_scan_dirs(kind: ArtifactKind, org_roots: list[Path] | None) -> list[tuple[Path, bool]]:
    """Return the flat and legacy ``built-in`` org-pack dirs that exist.

    For every configured org root, contributes (in this order) the flat
    ``<root>/<plural>`` layout when it exists, then the legacy
    ``<root>/<plural>/built-in`` layout (``recursive=True``, unchanged)
    when it separately exists. Neither directory existing is not an error --
    fewer entries are returned, never a raise.

    **Recursion is sourced from the shared authority (#3426 closed).** The
    flat entry's ``recursive`` flag comes from
    :func:`doctrine.discovery_recursion.overlay_scan_is_recursive` -- the same
    single authority the live loader (``BaseArtifactRepository._project_scan``
    and ``AgentProfileRepository._load``) consults -- so the resolver and the
    loader recurse identically for every kind (unconditional per C-001). This
    closes the prior list-vs-activate divergence: a ``styleguide`` (or any
    charter-activatable kind) stored under *any* subdirectory of an org root --
    e.g. ``styleguides/writing/`` -- now resolves for ``charter activate`` just
    as it already loads at runtime and already lists via
    ``pack_manager.list_available_detailed`` (which was always ``rglob``). The
    parity/totality gate pins loader↔resolver agreement so the divergence
    cannot silently return.

    **Global flat-before-legacy grouping** (PR-BOUNDARY-002 fix, pre-merge
    adversarial squad, severity 3; operator-ruled "fix it properly" rather
    than merely documenting the gap). FR-001's precedence rule is worded
    "for one org root" -- this widens it beyond that literal text, a
    deliberate, operator-authorized scope expansion to close the defect
    class rather than leave it as a documented limitation: the returned
    list is grouped as *every flat entry, in org-root order* followed by
    *every legacy entry, in org-root order* -- entries are **not**
    interleaved per root as they were before this fix. Previously, with
    ``org_roots=[a, b]``, a legacy entry from ``a`` could precede a flat
    entry from ``b`` in the returned list, so a same-config-stem collision
    straddling two different org packs -- one legacy-shaped, one
    flat-shaped -- was decided by ``org_roots`` order, not by flat-vs-legacy
    shape, contradicting the documented flat-wins invariant whenever the
    legacy-shaped root happened to be listed first.
    :func:`resolve_artifact_urn`'s first-match-wins semantics over this
    grouped list now make the flat-layout file win a same-config-stem
    collision regardless of which org root either file came from, or which
    order the roots were supplied in -- see
    ``TestOrgScanDirsHelper.test_multi_root_precedence_flat_wins_regardless_of_root_order``
    (``tests/charter/test_kind_vocabulary_scan_roots.py``) for the
    regression, exercised in both root orderings.
    """
    flat_dirs: list[tuple[Path, bool]] = []
    legacy_dirs: list[tuple[Path, bool]] = []
    recursive = overlay_scan_is_recursive(kind)
    for root in org_roots or []:
        flat = root / kind.plural
        if flat.is_dir():
            flat_dirs.append((flat, recursive))
        legacy = flat / "built-in"
        if legacy.is_dir():
            legacy_dirs.append((legacy, True))
    return flat_dirs + legacy_dirs


def _layer_candidate_dir(kind: ArtifactKind, layer: str, root: Path) -> Path | None:
    """Return the candidate dir for *kind* within a single *layer*, or ``None``.

    Only the project layer is resolved here: its *root* is the project pack
    root (``.kittify/charter-packs/``), so kind directories join straight onto
    it. Org packs are scanned flat through ``org_roots`` (:func:`_org_scan_dirs`)
    and the built-in pack through :func:`_built_in_scan_dir`; the retired nested
    ``<pack>/doctrine/<plural>/<layer>`` layout is not read (FR-011).
    """
    if layer != "project":
        return None
    project_dir: Path = root / PROJECT_KIND_DIRS.get(kind, kind.plural)
    return project_dir


def _layer_scan_dirs(kind: ArtifactKind, layer_roots: dict[str, Path] | None) -> list[tuple[Path, bool]]:
    """Return layer doctrine dirs that exist for *kind*, across *layer_roots*."""
    dirs: list[tuple[Path, bool]] = []
    recursive = overlay_scan_is_recursive(kind)
    for layer, root in (layer_roots or {}).items():
        candidate = _layer_candidate_dir(kind, layer, root)
        if candidate is not None and candidate.is_dir():
            dirs.append((candidate, recursive))
    return dirs


@dataclass
class ResolutionPass:
    """A resolution-pass-scoped memo of layer scans and artifact ID reads.

    Callers that perform several resolutions within a single logical pass
    (e.g. `resolve_config_id`'s per-stem directive round-trip, or a CLI render
    loop that maps every cascade-reported URN back to its config stem) create
    one of these and thread it through every nested call, so each distinct
    layer set is walked at most once (FR-001) and each artifact file is parsed
    at most once per pass. The memo is never module-level or persisted across
    calls -- a caller that omits it (the default) gets the old unmemoized
    behaviour, and a fresh pass always re-scans and re-reads, so a later
    resolution after an on-disk change is unaffected (FR-002; no invalidation
    logic is needed because nothing outlives its own pass). A pass must
    therefore never span a write to the artifact files it reads.
    """

    scans: dict[tuple[object, ...], list[Path]] = field(default_factory=dict)
    ids: dict[tuple[Path, str], str | None] = field(default_factory=dict)
    #: One identity index per root set, so a facade call inside the pass reuses the
    #: index (and its fast-id reads) instead of rebuilding it (#6433, NFR-004). The
    #: value type is opaque: this module must not import ``identity_index``, which
    #: imports it.
    indexes: dict[tuple[object, ...], object] = field(default_factory=dict)


def _scan_cache_key(
    kind: ArtifactKind,
    offering_root: Path,
    org_roots: list[Path] | None,
    layer_roots: dict[str, Path] | None,
) -> tuple[object, ...]:
    """Return a hashable key identifying one `_iter_artifact_paths` input set."""
    org_key = tuple(org_roots) if org_roots else ()
    layer_key = tuple(sorted((layer_roots or {}).items()))
    return (kind, offering_root, org_key, layer_key)


def _iter_artifact_paths(
    kind: ArtifactKind,
    *,
    offering_root: Path,
    org_roots: list[Path] | None,
    layer_roots: dict[str, Path] | None,
    resolution_pass: ResolutionPass | None = None,
) -> list[Path]:
    cache_key = None
    if resolution_pass is not None:
        cache_key = _scan_cache_key(kind, offering_root, org_roots, layer_roots)
        cached = resolution_pass.scans.get(cache_key)
        if cached is not None:
            return cached
    pattern = kind.glob_pattern
    if not pattern:
        paths: list[Path] = []
    else:
        paths = []
        for scan_dir, recursive in _scan_roots(
            kind,
            _offering_root=offering_root,
            org_roots=org_roots,
            layer_roots=layer_roots,
        ):
            paths.extend(sorted(_scan_dir_matches(scan_dir, pattern, recursive=recursive)))
    if resolution_pass is not None and cache_key is not None:
        resolution_pass.scans[cache_key] = paths
    return paths


def _scan_dir_matches(scan_dir: Path, pattern: str, *, recursive: bool) -> list[Path]:
    """Return the artifact files under *scan_dir* matching *pattern*.

    A recursive scan excludes the reserved ``built-in/`` subtree (handled by its
    own dedicated entry — see :func:`_under_reserved_builtin_subdir`); a
    non-recursive scan is a flat glob.
    """
    if not recursive:
        return list(scan_dir.glob(pattern))
    return [match for match in scan_dir.rglob(pattern) if not _under_reserved_builtin_subdir(match, scan_dir)]


def _under_reserved_builtin_subdir(match: Path, scan_dir: Path) -> bool:
    """Return whether *match* is directly under the reserved ``built-in/`` child.

    The **immediate** child ``<plural>/built-in`` is the reserved legacy
    package-shaped layer, scanned by its **own** dedicated
    ``(<plural>/built-in, recursive=True)`` entry (see :func:`_org_scan_dirs`).
    A now-recursive flat ``<plural>`` entry would otherwise double-cover it and —
    because a ``built-in/`` file would sort ahead of the sibling flat file —
    silently invert the flat-wins-over-legacy precedence guarantee (FR-001 / the
    ``TestOrgScanDirsHelper`` precedence regressions). Excluding it from the
    recursive flat scan leaves ``built-in/`` to its dedicated, later-ordered
    entry so flat still wins.

    The check is scoped to the **immediate** child (``parts[0] == "built-in"``),
    NOT any ``built-in`` component at arbitrary depth: the compensating dedicated
    entry only covers ``<plural>/built-in``, so excluding a deeper
    ``<plural>/<category>/built-in/`` would drop it from the resolver while the
    loader (``base._project_scan`` rglob, no exclusion) still loads it — exactly
    the loader↔resolver discovery divergence this mission eliminates. Deeper
    ``built-in`` components (a user directory that merely happens to be named
    ``built-in`` below a category) stay discoverable, matching the loader.
    """
    parts = match.relative_to(scan_dir).parts
    return len(parts) > 1 and parts[0] == "built-in"


def _identity_index(
    *,
    offering_root: Path,
    org_roots: list[Path] | None,
    layer_roots: dict[str, Path] | None,
    resolution_pass: ResolutionPass | None,
) -> IdentityIndex:
    """The one identity authority for a facade call, over exactly the roots the caller passed.

    ``identity_index`` imports this module, so the dependency is a function-local
    import (the module-load-time cycle the package already avoids elsewhere).
    """
    from charter.activation.identity_index import IdentityIndex  # noqa: PLC0415

    return IdentityIndex.from_roots(
        offering_root=offering_root,
        org_roots=org_roots,
        layer_roots=layer_roots,
        resolution_pass=resolution_pass,
    )


def resolve_artifact_urn(
    kind: ArtifactKind,
    config_id: str,
    *,
    offering_root: Path,
    org_roots: list[Path] | None = None,
    layer_roots: dict[str, Path] | None = None,
    resolution_pass: ResolutionPass | None = None,
) -> str:
    """Resolve a config/file-stem ID to its DRG URN node ID -- a facade over ``IdentityIndex``.

    The index is the one stem<->id authority (#6433): it applies the layer
    precedence (project, then org packs last-declared-first, then built-in) and the
    stem-before-declared-id rule, and it accepts every spelling the runtime gate
    accepts -- a file stem, a declared id, a ``<kind>:<id>`` URN (FR-011) or a
    normalised directive id such as ``24``. This function only turns the answer
    into a URN and fails closed, so the same token can no longer resolve in the gate
    and be refused here.

    A directive declared id is accepted only when some filename represents it
    (:meth:`IdentityIndex.stem_for_declared_id`): this recovers entries written by
    older org-required promotion and refuses an id every candidate filename binds to
    another identity, exactly as before. A *file stem* input needs no such check: the
    file the reader names wins, even when two layers bind that stem to different ids
    (:meth:`IdentityIndex.names_a_file`), so persisted stems keep first-match
    precedence.

    Args:
        kind: The artifact kind (route raw kind strings through
            :meth:`ArtifactKind.from_operator_token` first).
        config_id: The config/file-stem ID, declared ID or ``<kind>:<id>`` URN, e.g.
            ``"001-architectural-integrity-standard"``.
        offering_root: Resolved charter offering root (passed as data, C-008).
        org_roots: Optional additional org/project doctrine roots to scan.
        layer_roots: Optional modern layer map, e.g. ``{"org": <pack-root>}``.
        resolution_pass: Optional memo shared by several resolutions in one
            read-only pass (see :class:`ResolutionPass`).

    Returns:
        The DRG URN node ID, e.g. ``"directive:DIRECTIVE_001"``.

    Raises:
        UnknownArtifactIdError: if no artifact in the searched layers is known by
            that stem, declared id or URN, or if a directive is known only by an id
            every filename binds to another identity (this function has always
            reported the unrepresentable case as unknown; ``resolve_config_id`` is
            the entry point that names it precisely).
    """
    identity = _identity_index(
        offering_root=offering_root,
        org_roots=org_roots,
        layer_roots=layer_roots,
        resolution_pass=resolution_pass,
    )
    declared: str | None = identity.declared_id(kind, config_id)
    if declared is not None and (
        kind is not ArtifactKind.DIRECTIVE or identity.names_a_file(kind, config_id) or identity.stem_for_declared_id(kind, declared) is not None
    ):
        return f"{kind.value}:{declared}"
    # Unknown, or a directive id no filename represents. Both keep this function's
    # long-standing single refusal type and message: callers catch
    # ``UnknownArtifactIdError`` here, and ``resolve_config_id`` is the surface that
    # distinguishes the unrepresentable case (`UnrepresentableDirectiveIdError`).
    raise unknown_artifact_id_error(kind, config_id, offering_root=offering_root, org_roots=org_roots, layer_roots=layer_roots)


def unknown_artifact_id_error(
    kind: ArtifactKind,
    config_id: str,
    *,
    offering_root: Path,
    org_roots: list[Path] | None = None,
    layer_roots: dict[str, Path] | None = None,
) -> UnknownArtifactIdError:
    """The refusal for a token no searched layer knows; it names the searched layers (C-006)."""
    return UnknownArtifactIdError(
        f"No {kind.value} artifact with config ID {config_id!r} found under "
        f"doctrine root {offering_root}{_org_roots_clause(org_roots)}. "
        f"Searched layers: {_searched_layers(kind, org_roots, layer_roots)}. "
        f"Check activated_{kind.plural} in the charter.yaml activation store "
        f"selected by `.kittify/config.yaml` (or its legacy inline activations) for a stale or "
        f"misspelled entry, or run `spec-kitty doctor charter-packs` to verify the "
        f"doctrine corpus (including any org packs) is intact."
    )


def _searched_layers(
    kind: ArtifactKind,
    org_roots: list[Path] | None,
    layer_roots: dict[str, Path] | None,
) -> str:
    """Include candidate directories even when a missing layer does not exist."""
    roots = [f"{layer}: {_layer_candidate_dir(kind, layer, root)}" for layer, root in (layer_roots or {}).items()]
    roots.extend(f"org: {root / kind.plural}" for root in org_roots or [])
    builtin = _built_in_scan_dir(kind)
    roots.append(f"built-in: {builtin[0]}" if builtin is not None else "built-in: unavailable")
    return "; ".join(roots)


def _org_roots_clause(org_roots: list[Path] | None) -> str:
    """Name the org roots that were also scanned, when any were supplied."""
    if not org_roots:
        return ""
    return f" or org/project pack roots {[str(root) for root in org_roots]}"


class UnrepresentableDirectiveIdError(UnknownArtifactIdError):
    """A declared directive exists, but every filename selects another ID."""


def resolve_config_id(
    urn: str,
    *,
    offering_root: Path,
    org_roots: list[Path] | None = None,
    layer_roots: dict[str, Path] | None = None,
    resolution_pass: ResolutionPass | None = None,
) -> str:
    """Resolve a DRG URN node ID back to its config/file-stem ID -- a facade over ``IdentityIndex``.

    Inverse of :func:`resolve_artifact_urn`, answering from the same index (#6433).
    Parses the ``kind:id`` URN and returns the stem whose *declared id* is that id
    (:meth:`IdentityIndex.stem_for_declared_id`), in layer-precedence order; a
    directive id is returned only through a stem that round-trips to it and that no
    other layer binds to a different id. A lower-layer stem may select higher-layer
    repository content.

    Args:
        urn: A DRG URN node ID, e.g. ``"directive:DIRECTIVE_001"``.
        offering_root: Resolved charter offering root (passed as data, C-008).
        org_roots: Optional additional org/project doctrine roots to scan.
        layer_roots: Optional modern layer map, e.g. ``{"org": <pack-root>}``.
        resolution_pass: Optional memo shared by several resolutions in one
            read-only pass (see :class:`ResolutionPass`).

    Returns:
        The config/file-stem ID, e.g. ``"001-architectural-integrity-standard"``.

    Raises:
        ValueError: if *urn* is malformed (missing ``kind:`` prefix or an
            unknown kind value).
        UnknownArtifactIdError: if no artifact with that ID exists for the kind.
        UnrepresentableDirectiveIdError: if a directive exists but every candidate
            filename stem resolves to another identity.
    """
    kind_value, sep, artifact_id = urn.partition(":")
    if not sep or not kind_value or not artifact_id:
        raise ValueError(f"Malformed URN {urn!r}; expected '<kind>:<artifact_id>'.")
    try:
        kind = ArtifactKind(kind_value)
    except ValueError as exc:
        raise ValueError(f"Malformed URN {urn!r}; unknown kind {kind_value!r}.") from exc

    identity = _identity_index(
        offering_root=offering_root,
        org_roots=org_roots,
        layer_roots=layer_roots,
        resolution_pass=resolution_pass,
    )
    stem: str | None = identity.stem_for_declared_id(kind, artifact_id)
    if stem is not None:
        return stem
    if identity.has_declared_id(kind, artifact_id):
        raise UnrepresentableDirectiveIdError(
            f"Directive filename stems cannot represent {artifact_id!r}: each resolves to another identity. "
            "Rename an artifact to an unambiguous filename before selecting it."
        )
    raise UnknownArtifactIdError(
        f"No {kind.value} artifact with id {artifact_id!r} found under "
        f"doctrine root {offering_root}{_org_roots_clause(org_roots)}. "
        f"Searched layers: {_searched_layers(kind, org_roots, layer_roots)}. "
        f"Check activated_{kind.plural} in the charter.yaml activation store "
        f"selected by `.kittify/config.yaml` (or its legacy inline activations) for a stale or "
        f"misspelled entry, or run `spec-kitty doctor charter-packs` to verify the "
        f"doctrine corpus (including any org packs) is intact."
    )


def resolve_selected_id_to_stem(
    kind: ArtifactKind,
    raw_id: str,
    *,
    offering_root: Path,
    org_roots: list[Path] | None = None,
    layer_roots: dict[str, Path] | None = None,
) -> str | None:
    """Map a selection's declared ID or filename stem to an activation stem -- a facade over ``IdentityIndex``.

    Directive identities take precedence over a coincidentally equal filename;
    other kinds retain their existing stem-first selection contract
    (:meth:`IdentityIndex.stem`). Discovery is unfiltered so inactive org artifacts
    can be selected. Unresolvable selections return ``None`` for the caller's
    warning policy. Known directive identities without a safe stem raise rather than
    promoting another policy.
    """
    identity = _identity_index(offering_root=offering_root, org_roots=org_roots, layer_roots=layer_roots, resolution_pass=None)
    stem: str | None = identity.stem(kind, raw_id)
    if stem is None and kind is ArtifactKind.DIRECTIVE and identity.has_declared_id(kind, raw_id):
        # Known ambiguous identities must never be promoted verbatim or
        # reinterpreted as another filename.
        raise UnrepresentableDirectiveIdError(
            f"Directive filename stems cannot represent {raw_id!r}: each resolves to another identity. "
            "Rename an artifact to an unambiguous filename before selecting it."
        )
    return stem
