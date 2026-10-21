"""Charter pack activation manager (FR-001, FR-002, FR-026, FR-027).

Provides ``ActiveCharterManager`` — the single interface for activating and
deactivating doctrine artifacts in a project's ``.kittify/config.yaml`` and for
discovering which artifacts are *available* across the built-in, org-pack, and
project doctrine layers.

All mutating methods use ``ruamel.yaml`` round-trip mode so that existing
comments and formatting in ``config.yaml`` are preserved across writes.

Canonical kind vocabulary (FR-027, R-009)
-----------------------------------------
There is **no** second kind enumeration in this module. Kind validation routes
through :meth:`charter.offering.artifact_kinds.ArtifactKind.from_operator_token` (the
single canonical resolver, WP01), and ``mission-type`` is the one charter-tier
token that is *not* an :class:`ArtifactKind` member (handled explicitly).

``YAML_KEY_MAP`` is **derived** from the canonical charter kind universe
(:data:`charter.offering.artifact_kinds.CHARTER_KIND_TOKENS`): every kind maps to
``activated_<plural>`` except the ``mission-type`` outlier
(``mission_type_activations``). ``ACTIVATION_YAML_KEYS`` extends that with
the ``activated_kinds`` coarse ledger key -- it is the single authority
:mod:`charter.activation.charter_yaml_io` and the ``consolidate_charter_bundle_fold``
upgrade migration derive their own activation-key vocabularies from (WP05 /
FR-010), so the three copies can never independently drift again.

Layer model (FR-026)
--------------------
``list_available`` scans the *built-in* layer plus any caller-supplied org /
project doctrine roots, returning artifact IDs taken from each artifact's
``id:`` field (not the filename stem). :meth:`list_available_detailed` exposes
the same scan annotated by source layer for ``charter list --all`` (WP16). The
built-in layer's per-kind directory is resolved through
:func:`charter.offering.pack_paths.built_in_dir` (WP01/T020) rather than a locally
composed ``resolve_pack_root("built-in") / kind.plural`` join.

Org/project roots are passed in **as data** (C-008): ``specify_cli`` resolves
them and hands them to this module. This module MUST NOT import from
``specify_cli`` (C-001, hard ratchet pinned by
``tests/architectural/test_layer_rules.py``).

Activation seam (FR-011/012, NFR-003)
-------------------------------------
``activate()`` and ``deactivate()`` are thin wrappers over the pure
:mod:`charter.activation.activation_engine` plan/commit seam (WP10): they load the config,
discover the available-ID universe, call ``plan_activation`` /
``plan_deactivation`` (which validate *before* computing any post-state), and
then perform the single ``commit_plan`` write. ``deactivate`` records an
exclusion (``deactivated_<plural>``), also under "absent = all"; an org-required
id is refused with :class:`~charter.activation.activation_engine.RequiredArtifactDeactivationError`
(a :class:`~charter.activation.activation_engine.DeactivationRefused`), which the
CLI surfaces.

Cascade parameter (FR-006/007)
--------------------------------
``activate()`` and ``deactivate()`` accept a ``cascade`` parameter for
signature stability, but DRG edge traversal is owned by the CLI layer
(``charter.activation.cascade``). **No warning is emitted** when ``cascade=True`` is
passed; the parameter is silently accepted and forwarded. FR-007 (cascade
execute) is a CLI-level concern — ``pack_manager`` does not interpret or act
on this flag.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable, Iterable, Mapping, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.activation.bundle_restamp import restamp_bundle_hash
from charter.activation.activation_engine import (
    NARROW_UNRESOLVED_WARNING,
    DeactivationRefused,
    RequiredArtifactDeactivationError,
    UnknownActivationIdError,
    check_deactivation_permitted,
    commit_plan,
    deny_delta,
    plan_activation,
    plan_deactivation,
)
from charter.activation.activation_ledger import (
    DENY_KEYS,
    LEDGER_KEYS,
    UNMIGRATED_REMEDY,
    DenyListChoice,
    _deny_changes,
    _effective_deny,
    deny_key as _deny_key,
    load_activation_ledger,
    prepare_ledger_write,
    resolve_ledger_source,
)
from charter.activation.charter_yaml_io import (
    PreparedYamlWrite,
    apply_yaml_write,
    load_charter_yaml,
    observe_yaml_input,
    prepare_charter_yaml_section,
    prepare_yaml_write,
    render_yaml_document,
    yaml_documents_equal,
    update_charter_yaml_section,
)
from charter.activation.org_pack_discovery import RequiringPack, read_org_required_provenance
from charter.activation.pack_context import ActiveCharterConfigError, PackContext, resolve_charter_yaml_pointer
from charter.offering.missions.mission_type_repository import (
    ORG_MISSION_TYPES_SUBDIR,
    PROJECT_MISSION_TYPES_RELATIVE_TO_KITTYFY_ROOT,
    scan_mission_types_dir,
)
from charter.offering.missions.repository import MissionTemplateRepository
from charter.offering.pack_paths import built_in_dir
from charter.offering.artifact_kinds import (
    CHARTER_KIND_TOKENS,
    MISSION_TYPE_TOKEN,
    PROJECT_KIND_DIRS as _PROJECT_KIND_DIRS,
    ArtifactKind,
    MissionTypeNotAnArtifactKind,
)
from kernel.activation_ledger_store import ACTIVATION_LEDGER, ActivationSource, activation_ledger_path
from kernel.pack_tiers import BUILT_IN, ORG, PACK_TIERS, PROJECT

if TYPE_CHECKING:
    from charter.activation.invocation_context import ProjectContext

__all__ = [
    "ACTIVATION_YAML_KEYS",
    "AvailableArtifact",
    "ActiveCharterManager",
    "DenyListChoice",
    "YAML_KEY_MAP",
    "resolve_activation_write_target",
    "prepare_activation_write",
]
# ``AvailableArtifact`` is exported now that ``charter list --all`` (WP16)
# imports it as a live ``src/`` consumer (it is the per-layer value object
# returned by ``list_available_detailed``). Before WP16 the symbol-level
# dead-code gate (tests/architectural/test_no_dead_symbols.py) required a live
# importer before the symbol could be exported; WP16 is that importer.

# ---------------------------------------------------------------------------
# Canonical kind tables (derived from the WP01 resolver — no re-enumeration)
# ---------------------------------------------------------------------------


def _yaml_key_for_token(token: str) -> str:
    """Return the ``config.yaml`` activation key for a charter kind *token*.

    The ``mission-type`` token is the documented outlier
    (``mission_type_activations``); every other kind follows the
    ``activated_<plural>`` pattern, with the plural taken from the canonical
    :class:`ArtifactKind` rather than a hand-maintained table (R-009 / CC-4).
    """
    if token == MISSION_TYPE_TOKEN:
        return "mission_type_activations"
    return f"activated_{ArtifactKind.from_operator_token(token).plural}"


#: Maps charter kind operator tokens (hyphenated CLI surface) to ``config.yaml``
#: activation keys. Derived from :data:`CHARTER_KIND_TOKENS` (the canonical kind
#: universe, WP01) so no second kind enumeration is maintained here.
#:
#: The ``mission-type`` → ``mission_type_activations`` mapping is the outlier;
#: all other kinds follow the ``activated_<plural>`` pattern.
YAML_KEY_MAP: dict[str, str] = {token: _yaml_key_for_token(token) for token in CHARTER_KIND_TOKENS}


#: Cheap plain-tuple constant (WP05 / FR-010 / C4.1-C4.2): the single
#: derived authority for the FULL flat activation-key vocabulary that
#: ``charter.yaml`` (and, pre-migration, ``config.yaml``) carries as
#: top-level keys. ``"activated_kinds"`` is a coarse "which kinds have been
#: touched at all" ledger key -- distinct from the per-kind lists in
#: :data:`YAML_KEY_MAP` and not itself derivable from
#: :data:`CHARTER_KIND_TOKENS` -- so it is prepended explicitly; every other
#: entry is exactly :data:`YAML_KEY_MAP`'s values.
#:
#: Two independent hand-restated copies of this vocabulary used to drift
#: from each other and from this authority: ``charter.activation.charter_yaml_io.
#: _ACTIVATION_KEYS`` and the ``consolidate_charter_bundle_fold`` finalize
#: migration's ``ACTIVATION_KEYS`` (the latter was missing
#: ``activated_glossary_packs`` -- a live data-loss drift, FR-010/SC-005).
#: Both now derive from this constant via a lazy, function-scoped import
#: (avoiding a circular import back onto this module, and keeping the
#: migration's registry-discovery import cheap -- see
#: ``charter_yaml_io._activation_keys`` /
#: ``m_unify_charter_activation_finalize._activation_keys``). Guarded by
#: ``tests/charter/test_activation_vocabulary_setequal.py``.
#:
#: Charter-activatable kinds that have no operator token (today only
#: ``anti_pattern``: charter-activatable per ``ArtifactKind.activatable``, #5409,
#: but excluded from :data:`CHARTER_KIND_TOKENS` because it has no standalone
#: artifact file) are appended, derived from the enum, so the single writer
#: (:func:`prepare_activation_write`) can set and remove ``activated_anti_patterns``
#: when ``charter activate --preset`` applies a preset that governs it (#3732).
_TOKENLESS_ACTIVATION_KEYS: tuple[str, ...] = tuple(
    f"activated_{kind.plural}" for kind in ArtifactKind if kind.activatable and f"activated_{kind.plural}" not in YAML_KEY_MAP.values()
)
ACTIVATION_YAML_KEYS: tuple[str, ...] = ("activated_kinds", *YAML_KEY_MAP.values(), *_TOKENLESS_ACTIVATION_KEYS)


#: Layer segments scanned for artifact availability (FR-026), in precedence
#: order. ``specify_cli`` resolves the org/project *roots* (C-008); this module
#: only knows the directory-segment names.
_LAYER_SEGMENTS: tuple[str, ...] = PACK_TIERS
_KITTIFY_DIRNAME = ".kittify"
_CONFIG_FILENAME = "config.yaml"
_LEDGER_REL = ACTIVATION_LEDGER.as_posix()
#: The project-tier overlay directory name per kind is the single canonical
#: authority :data:`charter.offering.artifact_kinds.PROJECT_KIND_DIRS` (imported above
#: as ``_PROJECT_KIND_DIRS``). It is *total*, so the ``.get(kind, kind.plural)``
#: read below never actually falls back; the default is retained defensively.
#: No mapping is re-declared here (WP03 T014).


def _resolve_kind(token: str) -> ArtifactKind | None:
    """Resolve a charter kind *token* to its :class:`ArtifactKind`.

    Returns ``None`` for the ``mission-type`` token (which is part of the
    charter kind universe but is *not* an :class:`ArtifactKind` member — it is
    handled mission-tier). Raises :class:`ValueError` for any token outside the
    canonical universe.

    This is the **single** kind-resolution path in ``pack_manager`` (R-009 /
    CC-4); the kind set is never re-declared here.
    """
    try:
        return ArtifactKind.from_operator_token(token)
    except MissionTypeNotAnArtifactKind:
        return None


def _scan_layout_for(kind: ArtifactKind | None) -> tuple[str, str, bool]:
    """Return ``(base_dir, glob_pattern, layered)`` for a charter kind.

    ``base_dir`` is relative to ``src/`` (the parent of the ``charter`` package
    root). ``layered`` indicates whether the per-layer ``{built-in, org,
    project}`` segment is appended under ``base_dir`` (FR-026); kinds that live
    in a flat directory (``mission-type``) iterate that directory directly.

    The glob pattern is taken from :attr:`ArtifactKind.glob_pattern` (WP01) for
    artifact kinds — suffixes are never re-declared here (T041). ``mission-type``
    is not an :class:`ArtifactKind`, so its flat-directory layout and ``*.yaml``
    glob are spelled out explicitly.

    The standard kinds' ``base_dir`` is ``<plural>``. Two base-dir outliers
    do not follow it:

    * ``mission-step-contract`` lives under
      ``missions/built_in_step_contracts`` (a flat directory, not a
      ``built-in`` layer segment) — historically there is no org/project layer
      for step contracts, so ``layered`` is ``False``.
    * ``mission-type`` lives under ``missions/mission_types`` (flat).

    Both outliers' ``base_dir`` is relative to
    :meth:`charter.offering.missions.repository.MissionTemplateRepository.default_missions_root`
    (``packs/built-in/missions/``), **not** ``_SRC_ROOT`` — mission
    ``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` (FR-005)
    relocated ``missions/``'s data subdirectories there; see
    :meth:`ActiveCharterManager._scan_layer_dirs`'s flat-kind branch, the one
    place this distinction actually matters for resolution.

    Templates (FR-025) are intentionally **not** handled here; ``template`` is
    resolved mission-tier with mission-qualified IDs by WP18, which extends this
    catalog via :meth:`list_available_detailed`.
    """
    if kind is None:
        # mission-type: flat mission-tier directory, not an ArtifactKind.
        return ("missions/mission_types", "*.yaml", False)
    if kind is ArtifactKind.MISSION_STEP_CONTRACT:
        # Step contracts live in a single flat directory (no layer segment).
        return ("missions/built_in_step_contracts", kind.glob_pattern, False)
    # The standard artifact kinds: a flat <plural>/ directory per layer root,
    # with the canonical glob from ArtifactKind.
    return (kind.plural, kind.glob_pattern, True)


def _resolve_org_layer_dir(root: Path, kind: ArtifactKind) -> Path:
    """Return the org-layer scan directory: the flat ``<pack>/<plural>/`` layout.

    FR-013 unifies the charter activation subsystem with runtime, which resolves
    org packs from the flat layout (``resolve_org_roots`` → ``ActiveCharterService``).
    The retired nested ``<pack>/doctrine/<plural>/org/`` layout is not read
    (mission ``charter-pack-cutover-01M491G6``, FR-011: no read-side fallback
    for the retired doctrine layout).
    """
    return cast(Path, root / kind.plural)


def _kittify_root_of_project_pack(project_pack_root: Path) -> Path:
    """Return the ``.kittify`` directory that holds *project_pack_root*.

    The project layer root handed out by
    :func:`charter.activation.layer_roots.resolve_layer_roots` is always a
    direct child of ``<repo>/.kittify`` (the project pack root), so its parent
    is ``.kittify``.
    Project mission types live at ``.kittify/missions/mission_types/``, outside
    the pack, and are resolved from here.
    """
    return project_pack_root.parent


def _resolve_layer_candidate(
    layer: str,
    root: Path,
    kind: ArtifactKind | None,
    base_dir: str,
    *,
    layered: bool,
) -> Path | None:
    """Resolve the scan directory for one ``(layer, root)`` pair.

    Returns ``None`` when the ``(layer, kind, layered)`` combination has no
    known directory layout — :meth:`ActiveCharterManager._scan_layer_dirs`
    then skips that layer for this kind (mirrors the pre-extraction
    ``else: continue`` branch).
    """
    if layered and layer == PROJECT and kind is not None:
        # ``root`` is the project pack root (``.kittify/charter-packs/``).
        kind_dir = _PROJECT_KIND_DIRS.get(kind, kind.plural)
        return cast(Path, root / kind_dir)
    if layered and layer == ORG and kind is not None:
        return _resolve_org_layer_dir(root, kind)
    if layered and layer == BUILT_IN and kind is not None:
        # The built-in layer relocated from ``src/charter/offering/<plural>/built-in``
        # to the flattened ``packs/built-in/<plural>`` tree
        # (mission relocate-builtin-doctrine-packs). Resolve it through the
        # canonical per-kind seam (mission
        # doctrine-built-in-seam-consolidation-01KYW3TX, WP01/T020)
        # rather than composing the ``resolve_pack_root("built-in") /
        # kind.plural`` join locally -- this branch only runs when
        # ``layered`` is ``True`` (see ``_scan_layout_for``), and
        # ``mission_step_contract`` is the sole charter-activatable
        # kind (``CHARTER_KIND_TOKENS``) with
        # ``has_built_in_content_dir is False``; it is also the sole
        # kind for which ``_scan_layout_for`` returns
        # ``layered=False``, so the ``layered`` guard above already
        # excludes it before ``built_in_dir(kind)`` is ever called --
        # this never raises ``BuiltInContentDirNotAvailable``.
        return cast(Path, built_in_dir(kind))
    if layered:
        return root / base_dir / layer
    if layer == BUILT_IN:
        # Flat-directory kinds (mission-type / step contracts) only have
        # the built-in layer. Their content lives under
        # packs/built-in/missions/<segment> (mission #3091/FR-005
        # relocated missions/ there), not under _SRC_ROOT. Neither
        # outlier is resolvable through built_in_dir(kind) --
        # mission-type is not an ArtifactKind at all, and
        # MISSION_STEP_CONTRACT is part of the derived complement
        # built_in_dir refuses (no packs/built-in/<plural>/ content
        # dir) -- and `built_in_root() / base_dir` would be the exact
        # "reuse the bare-root seam and reconstruct a path locally"
        # drift the architectural gate
        # (test_no_builtin_path_joins_outside_pack_paths_authority)
        # exists to catch. Route through the SAME missions-root
        # authority charter.offering.missions.repository.MissionTemplateRepository
        # already provides instead (one of the three sanctioned
        # kernel.sibling_paths convergent call sites). `base_dir` is
        # always "missions/<segment>" for both outlier kinds (see
        # _scan_layout_for), so only its final segment is joined onto
        # the missions root. (`root` here is `_SRC_ROOT`, deliberately
        # unused in this branch.)
        return cast(Path, MissionTemplateRepository.default_missions_root() / Path(base_dir).name)
    if kind is None and layer == ORG:
        # FR-003: the org-layer mission-type roster is flat --
        # <pack_root>/mission_types/*.yaml (CL-005; see ADR
        # docs/adr/3.x/2026-08-13-1-mission-type-roster-layering-seam.md).
        # `root` here is the org pack root itself (see
        # charter.activation.layer_roots.resolve_layer_roots
        # -> charter.drg.resolve_org_roots), the same root
        # _resolve_org_layer_dir joins onto for the
        # ArtifactKind case above. The ``mission_types`` segment is the
        # authority's own constant (#3427) -- the same one
        # resolve_layered_mission_types scans -- never a locally re-spelled
        # literal.
        return root / ORG_MISSION_TYPES_SUBDIR
    if kind is None and layer == PROJECT:
        # FR-005: the project-layer mission-type roster is flat and
        # non-recursive -- .kittify/missions/mission_types/*.yaml (CL-005).
        # `root` here is the project pack root (see
        # charter.activation.layer_roots.resolve_layer_roots), which is NOT
        # where the roster lives: the roster sits under `.kittify` itself, so
        # the join starts from `_kittify_root_of_project_pack(root)` and
        # consumes the authority's own under-`.kittify` tail constant
        # (charter.offering.missions.mission_type_repository, #3427) rather
        # than re-spelling the layout locally. This joins to a FLAT sibling
        # of, not nested inside, the pre-existing per-mission-instance
        # `.kittify/missions/<mission_name>/` convention --
        # `_mission_dir_if_valid` (src/specify_cli/mission.py) only
        # recognizes a subdirectory holding a file literally named
        # `mission.yaml`, which this roster's `*.yaml` files (named after
        # mission-type ids) never are.
        return _kittify_root_of_project_pack(root).joinpath(*PROJECT_MISSION_TYPES_RELATIVE_TO_KITTYFY_ROOT)
    return None


def _config_stem(path: Path) -> str:
    """Return the config/file-stem ID for an artifact path.

    The config stem is the filename with all extension suffixes removed
    (e.g. ``001-architectural-integrity-standard.directive.yaml`` →
    ``001-architectural-integrity-standard``). Mirrors
    :func:`charter.activation.kind_vocabulary._config_stem`.
    """
    return path.name.split(".", 1)[0]


#: YAML field that holds an artifact's canonical ID, per kind. Most artifacts
#: use ``id``; agent profiles use ``profile-id`` (matching the WP01 resolver and
#: ``catalog._load_yaml_id_catalog``).
_ID_FIELD_BY_KIND: dict[ArtifactKind, str] = {
    ArtifactKind.AGENT_PROFILE: "profile-id",
}


def _declared_id(path: Path, kind: ArtifactKind | None, yaml: YAML) -> str | None:
    """Return the artifact's declared ``id:`` (URN-side) field, or ``None``.

    Reads the same field the WP01 resolver and ``catalog._extract_artifact_id``
    read (``id`` for most kinds, ``profile-id`` for agent profiles). Returns
    ``None`` when the file is unreadable, not a mapping, or carries no ``id:``.
    """
    id_field = _ID_FIELD_BY_KIND.get(kind, "id") if kind is not None else "id"
    try:
        data = yaml.load(path.read_text(encoding="utf-8")) or {}
    except (OSError, YAMLError, TypeError):
        return None
    if isinstance(data, dict):
        raw_id = str(data.get(id_field, "")).strip()
        if raw_id:
            return raw_id
    return None


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


logger = logging.getLogger(__name__)


def _preservation_set(
    repo_root: Path,
    kind: str,
    yaml_key: str,
    data: Mapping[str, Any],
    available: frozenset[str],
    when_absent: str,
    deny: _DenyInputs | None = None,
) -> tuple[list[str], list[str], bool]:
    """What ``activate`` materializes for an absent key (#4253, #4399, #4400).

    Returns ``(ids, warnings, in_force)``. ``in_force`` is ``True`` when *ids*
    is what was in force while the key was absent, so the engine may say that
    nothing in force was deactivated; ``False`` when *ids* is a substitute and
    *warnings* already says what was used.

    A present key needs no set (it is appended to). For an absent key of a
    "required" kind (skills) the in-force set is what ``PackContext`` puts in
    force while the key is absent (org-required plus built-in defaults), never
    the whole catalogue (``activate skill X`` would activate every skill). For
    an "all" kind the set comes from the one public seam. When the seam cannot
    resolve it, activation stays tolerant but never narrower than the whole
    readable chain: it seeds from the seam's ``fallback_ids`` (built-in, every
    readable declared org root, project). ``mission-type`` is an activation
    ledger whose absent key puts nothing in force; it is seeded from the same
    chain-wide ``fallback_ids``, so every org pack is treated alike.
    """
    ids, warnings, in_force = _preservation_ids(repo_root, kind, yaml_key, data, available, when_absent)
    # The effective deny (``D*``) is subtracted in stem space: materialising never re-adds an exclusion (FR-009).
    return (_without_denied(ids, deny) if deny is not None else ids), warnings, in_force


def _preservation_ids(
    repo_root: Path,
    kind: str,
    yaml_key: str,
    data: Mapping[str, Any],
    available: frozenset[str],
    when_absent: str,
) -> tuple[list[str], list[str], bool]:
    """The in-force set an absent key materialises, before the deny subtraction (see :func:`_preservation_set`)."""
    if data.get(yaml_key) is not None:
        return [], [], True
    if when_absent != "all":
        in_force = PackContext.from_config(repo_root).allow_for(ArtifactKind.from_plural(yaml_key.removeprefix("activated_")))
        return sorted(str(item) for item in in_force or ()), [], True
    from charter.activation.effective_set import resolve_effective_sets

    effective = resolve_effective_sets(repo_root, [yaml_key])[yaml_key]
    if effective.resolved:
        return sorted(effective.ids), [], True
    seeded = sorted(effective.fallback_ids | available)
    if kind == MISSION_TYPE_TOKEN:
        note = (
            f"Kind {kind!r} had no explicit activation set, so no mission type was in force; "
            f"initialized from the {len(seeded)} mission types available across all readable layers."
        )
        return seeded, [note], False
    logger.debug("effective set for %r unresolved: %s", yaml_key, effective.reason)
    warning = (
        f"The effective {kind} set could not be resolved because {effective.reason}; initialized from the {len(seeded)} ids available across all readable layers."
    )
    return seeded, [warning], False


@dataclass(frozen=True)
class _DenyInputs:
    """The deny state ``activate`` hands the engine: key, ``D*`` in stems and the written id."""

    key: str | None
    effective: frozenset[str]
    artifact_id: str
    stem_of: Callable[[str], str]
    stored: tuple[str, ...] = ()


def _stored_deny(repo_root: Path, kind: ArtifactKind) -> tuple[str, ...]:
    """The deny-list of *kind* as the activation ledger seam reads it (``()`` on a legacy source, FR-017).

    Never the write-target mapping: on an unmigrated project that is
    ``config.yaml`` / ``charter.yaml``, whose hand-written ``deactivated_<kind>``
    key is reported, never applied.
    """
    stored: tuple[str, ...] = load_activation_ledger(repo_root, report_stray=False).deny_for(kind)
    return stored


def _deny_inputs(repo_root: Path, kind: ArtifactKind | None, artifact_id: str) -> _DenyInputs:
    """``D* = D − R`` for *kind* (stems), read only when the kind's deny-list is non-empty (NFR-003).

    *D* comes from the activation ledger seam (:func:`_stored_deny`). The
    required floor is read strictly (FR-013): an unreadable declared org pack
    refuses rather than subtracting a required id. *artifact_id* becomes its stem
    when that stem is denied, so the activation clears the stored entry.
    """
    if kind is None or not kind.activatable:
        return _DenyInputs(None, frozenset(), artifact_id, lambda token: token)
    key = _deny_key(kind)
    deny = list(_stored_deny(repo_root, kind))
    if not deny:
        return _DenyInputs(key, frozenset(), artifact_id, lambda token: token)
    from charter.activation.identity_index import IdentityIndex

    index = IdentityIndex.build(repo_root)
    floor = read_org_required_provenance(repo_root, kind, strict=True)
    effective = _effective_deny(kind, deny, floor, index).stems

    def stem_of(token: str) -> str:
        return index.stem(kind, token) or token

    stem = stem_of(artifact_id)
    return _DenyInputs(key, effective, stem if stem in deny else artifact_id, stem_of, tuple(deny))


def _without_denied(ids: list[str], deny: _DenyInputs) -> list[str]:
    """*ids* less the effective-denied ones (stem comparison), for an absent-list materialisation."""
    if not deny.effective:
        return ids
    return [item for item in ids if deny.stem_of(item) not in deny.effective or item == deny.artifact_id]


@dataclass(frozen=True)
class _NarrowInputs:
    """What ``activate(only=True)`` hands the engine (#6408)."""

    base: list[str]
    previous: list[str]
    artifact_id: str
    warnings: list[str]


def _narrow_inputs(
    repo_root: Path,
    kind: ArtifactKind | None,
    artifact_id: str,
    yaml_key: str,
    data: Mapping[str, Any],
    preserved: list[str],
    in_force: bool,
) -> _NarrowInputs:
    """Org-required base, previous in-force ids and written id, all in activation-stem spelling.

    The effective set lists org non-directive artifacts by declared id while a
    present activation list holds stems, so *previous* and *artifact_id* are mapped
    through the identity index first: a stem != id artifact that is kept is then
    never reported as dropped.

    *previous* only ever holds ids that were in force: the present list, or *preserved*
    when it is the in-force set. When the effective set could not be resolved,
    *preserved* is a stand-in (ids available across the chain), so *previous* is
    empty and a warning says the dropped list cannot be computed.
    """
    from charter.activation.identity_index import IdentityIndex
    from charter.activation.org_charter import org_required_stems

    warnings: list[str] = []
    present = data.get(yaml_key)
    if present is not None:
        previous = [str(item) for item in present]
    elif in_force:
        previous = list(preserved)
    else:
        previous = []
        warnings.append(NARROW_UNRESOLVED_WARNING)
    if kind is None:  # mission-type: no ArtifactKind, no org-required base
        return _NarrowInputs([], previous, artifact_id, warnings)
    index = IdentityIndex.build(repo_root)
    base = org_required_stems(repo_root, kind.plural, warnings)
    stems = [index.stem(kind, item) or item for item in previous]
    return _NarrowInputs(base, list(dict.fromkeys(stems)), index.stem(kind, artifact_id) or artifact_id, warnings)


@dataclass(frozen=True)
class AvailableArtifact:
    """A single available artifact, annotated by its source layer (FR-026).

    Attributes
    ----------
    artifact_id:
        The artifact's canonical ``id:`` value (R-011-D), e.g.
        ``"001-architectural-integrity-standard"``.
    layer:
        The source layer the artifact was discovered in: ``"built-in"``,
        ``"org"``, or ``"project"``.
    """

    artifact_id: str
    layer: str


@dataclass
class ActivationResult:
    """Result of a single activate() or deactivate() operation."""

    activated: list[str] = field(default_factory=list)
    deactivated: list[str] = field(default_factory=list)
    cascade_activated: dict[str, list[str]] = field(default_factory=dict)
    cascade_deactivated: dict[str, list[str]] = field(default_factory=dict)
    skipped_shared: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

#: Doctrine is installed alongside the charter package in ``src/``.
#: ``pack_manager.py`` lives one level deeper than before (moved into
#: ``charter/activation/`` by mission charter-activation-split-01M16ZSE,
#: MAP-A MOVE), hence the extra ``.parent``.
_SRC_ROOT = Path(__file__).parent.parent.parent  # src/charter/activation/.. → src/


def _load_config(config_path: Path) -> tuple[Any, YAML]:
    """Load config.yaml using ruamel.yaml round-trip mode.

    Returns (data_dict_or_empty_dict, yaml_instance).
    If the file does not exist, returns ({}, yaml_instance).
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as fh:
            data = yaml.load(fh)
    else:
        data = {}
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(".kittify/config.yaml root must be a mapping.")
    return data, yaml


def _activation_list_or_error(data: Any, yaml_key: str) -> list[Any] | None:
    raw = data.get(yaml_key)
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError(f".kittify/config.yaml key '{yaml_key}' must be a list, got {type(raw).__name__}.")
    return raw


def _save_config(config_path: Path, data: Any, yaml: YAML) -> None:
    """Write data back to config_path, creating parent dirs as needed."""
    before = observe_yaml_input(config_path)
    desired = render_yaml_document(before.content, data, yaml)
    apply_yaml_write(prepare_yaml_write(config_path, desired, section="activation", inputs=(before,)))


def _refuse_legacy_deny(target: Path, before: Mapping[str, Any], after: Mapping[str, Any]) -> None:
    """C-003, hole 1: a legacy save never records or changes a deny entry.

    Refuses when *after* would add, remove or change a ``deactivated_<kind>``
    entry against *before* (absent, ``[]`` and ``null`` are equal). An explicit
    deny choice that changes nothing (``charter activate``, ``--preset
    --force``, cascade ``--include-deactivated`` with nothing denied) passes,
    so allow-only commands keep working on an unmigrated project.
    """
    changed = [key for key, _added, _removed in _deny_changes(before, after)]
    if changed:
        raise ActiveCharterConfigError(
            f"Refused to write {', '.join(changed)} to the legacy activation surface {target}: a deactivation "
            f"(deactivated_<kind>) is recorded only in {_LEDGER_REL}. {UNMIGRATED_REMEDY} Nothing was written."
        )


def _save_legacy_config(config_path: Path, data: Any, *, yaml: YAML, deny_change: DenyListChoice | None = None) -> None:
    """The legacy ``config.yaml`` save: today's full round-trip write, behind the C-003 deny refusal.

    *deny_change* is accepted for the write-target triple's signature; a legacy
    save records no deny entry whatever the choice.
    """
    del deny_change
    current, _yaml = _load_config(config_path)
    _refuse_legacy_deny(config_path, current, data)
    _save_config(config_path, data, yaml)


def _save_charter_yaml_activation(charter_path: Path, data: dict[str, Any], *, deny_change: DenyListChoice | None = None) -> None:
    """INV-9 write path: persist activation keys through the shared helper.

    ``data`` is the full in-memory ``charter.yaml`` document (governance /
    directives / catalog / metadata / overrides plus the flat activation
    keys); only the flat allow keys known to :data:`YAML_KEY_MAP` are ever
    written, via :func:`~charter.activation.charter_yaml_io.update_charter_yaml_section`'s
    ``"activation"`` pseudo-section -- so unrelated sections are structurally
    preserved rather than conventionally preserved (Landmine 3 / INV-9).

    Safe to call once per changed key (``ActiveCharterManager.activate`` /
    ``deactivate``) or once for a batch of keys
    (``charter.activation.activation_engine.promote_activations``): only the keys
    actually present in ``data`` are written, and re-writing an unchanged
    key is idempotent. A save that would change a deny entry refuses (C-003);
    *deny_change* is accepted for the triple's signature only.
    """
    del deny_change
    current = load_charter_yaml(charter_path)
    _refuse_legacy_deny(charter_path, current if isinstance(current, dict) else {}, data)
    values = {key: data[key] for key in YAML_KEY_MAP.values() if key in data}
    if values:
        update_charter_yaml_section(charter_path, "activation", values)


def _save_ledger(
    path: Path,
    data: Mapping[str, Any],
    *,
    repo_root: Path,
    loaded: list[bytes | None],
    deny_change: DenyListChoice | None = None,
) -> None:
    """The ledger save behind the write-target triple: *data* is the whole ledger mapping.

    Accepts ``commit_plan``'s positional ``(path, data)`` call; a key of
    :data:`LEDGER_KEYS` absent from *data* is removed. The write goes through
    the seam's one writer, so the deny guard applies (*deny_change*). An empty
    mapping for a project with no ledger yet writes nothing. *loaded* holds the
    ledger's bytes as this triple last saw them (its read, then each of its own
    writes): a ledger that changed otherwise is a ``precondition_changed``
    refusal (as the legacy path), because the removals derived from *data*
    would otherwise drop a concurrent write.
    """
    del path  # the ledger path is repo_root's; the triple hands it back unchanged
    ledger_path = activation_ledger_path(repo_root)
    if observe_yaml_input(ledger_path).content != loaded[0]:
        raise ValueError(f"precondition_changed: {ledger_path}")
    values = {key: data[key] for key in LEDGER_KEYS if key in data}
    if not values and not activation_ledger_path(repo_root).is_file():
        return  # nothing to record: never create an empty ledger for a fresh project
    removals = tuple(key for key in LEDGER_KEYS if key not in data)
    apply_yaml_write(prepare_ledger_write(repo_root, values, remove=removals, deny_change=deny_change))
    loaded[0] = observe_yaml_input(ledger_path).content  # the triple's own write is the next baseline


def _ledger_write_target(repo_root: Path) -> tuple[Path, dict[str, Any], Callable[[Path, dict[str, Any]], None]]:
    """The ledger triple: path, round-trip mapping (``{}`` before the first write), save."""
    load_activation_ledger(repo_root)  # validates the ledger (L1/L2) with the seam's texts
    path = activation_ledger_path(repo_root)
    loaded = observe_yaml_input(path).content
    document = YAML().load(loaded) if loaded is not None else None
    data: dict[str, Any] = document if isinstance(document, dict) else {}
    return path, data, functools.partial(_save_ledger, repo_root=repo_root, loaded=[loaded])


def resolve_activation_write_target(
    repo_root: Path,
) -> tuple[Path, dict[str, Any], Callable[[Path, dict[str, Any]], None]]:
    """Resolve the ``(path, loaded document, save)`` triple for activation writes.

    Shared by :class:`ActiveCharterManager` and the two other activation
    writers (``specify_cli.cli.commands.charter.interview`` and
    ``charter.activation.org_charter``) so source resolution has exactly
    one implementation on the write side — the kernel resolver through the
    activation ledger seam (FR-017), mirroring
    :meth:`charter.activation.pack_context.PackContext.from_config` on the read side.

    ``LEDGER`` -> the target is ``.kittify/charter/activation.yaml``; the save
    takes ``commit_plan``'s positional ``(path, data)`` call plus a
    ``deny_change=`` keyword and writes through the seam's guarded writer.

    ``LEGACY`` (inside the upgrade scope, or an unmigrated project) -> today's
    pointer rule, unchanged; the ledger is never created here (hole 3). Absent ``.kittify/config.yaml``
    ``charter:`` pointer: the target IS ``config.yaml`` itself, written as a
    full ``ruamel`` round-trip document. Present pointer: the target is the
    pointed-at ``charter.yaml``; a dangling/unreadable pointer is a fail-loud
    :class:`~charter.activation.pack_context.ActiveCharterConfigError` (INV-5,
    re-homed #2530). Writes route through :func:`_save_charter_yaml_activation`,
    touching only the flat activation keys (INV-9). Both legacy saves refuse a
    change to a deny entry (C-003).
    """
    config_path = repo_root / _KITTIFY_DIRNAME / _CONFIG_FILENAME
    config_data, yaml_inst = _load_config(config_path)

    if resolve_ledger_source(repo_root).source is ActivationSource.LEDGER:
        return _ledger_write_target(repo_root)

    charter_path = resolve_charter_yaml_pointer(repo_root, config_data)
    if charter_path is None:
        return config_path, config_data, functools.partial(_save_legacy_config, yaml=yaml_inst)

    if not charter_path.exists():
        raise ActiveCharterConfigError(
            f".kittify/config.yaml 'charter:' pointer names {charter_path}, "
            f"which does not exist.\nRemediation: run the charter-bundle "
            f"migration (`spec-kitty upgrade`) to (re)generate it, or fix "
            f"the 'charter:' pointer."
        )
    charter_data = load_charter_yaml(charter_path)
    if not isinstance(charter_data, dict):
        raise ActiveCharterConfigError(f"{charter_path} root must be a mapping.")
    return charter_path, charter_data, _save_charter_yaml_activation


def _check_legacy_write_keys(values: Mapping[str, Any], removals: tuple[str, ...]) -> None:
    """Today's key checks of the legacy writer (the deny keys are split off before, by the C-003 refusal)."""
    unknown = (set(values) | set(removals)) - set(ACTIVATION_YAML_KEYS)
    if unknown:
        raise ValueError(f"Unknown activation key(s): {sorted(unknown)}")
    overlap = sorted(set(values) & set(removals))
    if overlap:
        raise ValueError(f"Activation key(s) both written and removed: {overlap}")


def _applied(data: Mapping[str, Any], values: Mapping[str, Any], removals: Iterable[str]) -> dict[str, Any]:
    """*data* with *values* set and *removals* deleted (a plain copy; *data* is untouched)."""
    merged = {**data, **values}
    for key in removals:
        merged.pop(key, None)
    return merged


def prepare_activation_write(
    repo_root: Path,
    values: dict[str, Any],
    *,
    remove: Iterable[str] = (),
    deny_change: DenyListChoice | None = None,
) -> PreparedYamlWrite:
    """Prepare the canonical activation target, retaining config/pointer identity.

    *values* are written; the keys named in *remove* are deleted (an absent key
    is a no-op). A key in both is a ``ValueError``. This is the single
    activation writer for every target: the ledger (through the seam's guarded
    :func:`~charter.activation.activation_ledger.prepare_ledger_write`, where
    *deny_change* authorises a deny-list change), or the legacy ``config.yaml``
    / pointed ``charter.yaml``, where a write that changes a deny entry refuses
    and a deny key that changes nothing is dropped (C-003).
    """
    removals = tuple(dict.fromkeys(remove))
    config = repo_root / _KITTIFY_DIRNAME / _CONFIG_FILENAME
    inputs = tuple(observe_yaml_input(path) for path in (*reversed(config.parents), config))
    if resolve_ledger_source(repo_root).source is ActivationSource.LEDGER:
        ledger = prepare_ledger_write(repo_root, values, remove=removals, deny_change=deny_change)
        observed = {item.path: item for item in (*inputs, *ledger.observations)}
        return prepare_yaml_write(ledger.target, ledger.desired_bytes, section="activation", inputs=tuple(observed.values()))
    allow_values = {key: value for key, value in values.items() if key not in DENY_KEYS}
    allow_removals = tuple(key for key in removals if key not in DENY_KEYS)
    _check_legacy_write_keys(allow_values, allow_removals)
    target, data, _save = resolve_activation_write_target(repo_root)
    _refuse_legacy_deny(target, data, _applied(data, values, removals))
    values, removals = allow_values, allow_removals
    before = observe_yaml_input(target)
    if before.content is not None and not yaml_documents_equal(YAML().load(before.content) or {}, data):
        raise ValueError(f"precondition_changed: {target}")
    if target != config:
        section = prepare_charter_yaml_section(target, "activation", values, remove=removals)
        desired = section.desired_bytes
    else:
        for key, value in values.items():
            if key not in data or data[key] != value:
                data[key] = value
        for key in removals:
            data.pop(key, None)
        desired = render_yaml_document(before.content, data, YAML())
    return prepare_yaml_write(target, desired, section="activation", inputs=inputs + (before,))


# ---------------------------------------------------------------------------
# ActiveCharterManager
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DeactivationInputs:
    """What ``deactivate`` hands the planner: the stem, every other spelling, the deny key and the floor."""

    stem: str
    spellings: tuple[str, ...]
    deny_key: str | None
    required_by: dict[str, tuple[RequiringPack, ...]]
    stored_deny: tuple[str, ...] = ()


def _deactivation_inputs(repo_root: Path, kind: ArtifactKind | None, artifact_id: str) -> _DeactivationInputs:
    """The deactivation inputs; the strict floor is always read (FR-013).

    ``spellings`` holds *artifact_id* and the artifact's declared id, so a
    deactivation by stem also removes a declared-id allow entry (#6423).
    ``mission-type`` (``kind is None``) has no deny-list and no required floor.
    """
    if kind is None:
        return _DeactivationInputs(artifact_id, (artifact_id,), None, {})
    from charter.activation.identity_index import IdentityIndex

    required_by = read_org_required_provenance(repo_root, kind, strict=True)
    index = IdentityIndex.build(repo_root)
    stem = index.stem(kind, artifact_id) or artifact_id
    declared = index.declared_id(kind, artifact_id)
    spellings = tuple(dict.fromkeys(item for item in (artifact_id, declared) if item))
    if not kind.activatable:
        return _DeactivationInputs(stem, spellings, None, required_by)
    return _DeactivationInputs(stem, spellings, _deny_key(kind), required_by, _stored_deny(repo_root, kind))


def _collapse_spellings(ids: Iterable[Any], stem_of: Callable[[str], str]) -> list[str]:
    """*ids* with every entry in stem spelling, first occurrence kept (one artifact, one entry; #6423)."""
    return list(dict.fromkeys(stem_of(str(item)) for item in ids))


def _identity_normalised(
    repo_root: Path, kind: ArtifactKind | None, artifact_id: str, yaml_key: str, data: MutableMapping[str, Any], available: frozenset[str]
) -> str:
    """*artifact_id* in stem spelling; a present allow list is collapsed to stems in place (#6423, ruling R3).

    A declared id (``DIRECTIVE_024``, an org ``EVD_003``) is not a stem, so it is
    not in *available*; it becomes its stem before the availability check. The
    identity index is built only when a token is not a known stem (NFR-003).
    """
    present = data.get(yaml_key)
    present_list = [str(item) for item in present] if isinstance(present, list) else []
    if kind is None or (artifact_id in available and all(item in available for item in present_list)):
        return artifact_id
    from charter.activation.identity_index import IdentityIndex

    index = IdentityIndex.build(repo_root)

    def stem_of(token: str) -> str:
        return index.stem(kind, token) or token

    collapsed = _collapse_spellings(present_list, stem_of)
    if present_list and collapsed != present_list:
        data[yaml_key] = collapsed
    return stem_of(artifact_id)


def _availability_roots(repo_root: Path, layer_roots: dict[str, Path] | None, org_root_chain: list[Path] | None) -> dict[str, Any]:
    """The layer roots and org chain a deactivation validates against (resolved when omitted)."""
    from charter.activation.layer_roots import resolve_layer_roots, resolve_pack_chain

    return {
        "layer_roots": layer_roots if layer_roots is not None else resolve_layer_roots(repo_root),
        "org_root_chain": org_root_chain if org_root_chain is not None else resolve_pack_chain(repo_root, strict=False),
    }


class ActiveCharterManager:
    """Manages activation/deactivation and availability of doctrine artifacts.

    All mutating methods read from and write to ``.kittify/config.yaml`` using
    ``ruamel.yaml`` round-trip mode (comments and formatting preserved), and
    delegate the validate/plan/commit logic to :mod:`charter.activation.activation_engine`.
    """

    def _require_kind(self, kind: str) -> ArtifactKind | None:
        """Validate *kind* against the canonical universe.

        Returns the :class:`ArtifactKind` (or ``None`` for ``mission-type``).
        Raises :class:`ValueError` with the legacy ``Unknown activation kind``
        message for tokens outside the charter kind universe.
        """
        if kind not in YAML_KEY_MAP:
            raise ValueError(f"Unknown activation kind '{kind}'. Valid kinds: {sorted(YAML_KEY_MAP)}")
        return _resolve_kind(kind)

    def _effective_when_absent(self, kind: str) -> str:
        """The kind's absent-key meaning; ``mission-type`` (no ArtifactKind) is ``"all"``."""
        resolved = self._require_kind(kind)
        return resolved.effective_when_absent if resolved is not None else "all"

    def activate(
        self,
        ctx: ProjectContext,
        kind: str,
        artifact_id: str,
        *,
        cascade: bool = False,  # noqa: ARG002 — kept for caller API stability
        layer_roots: dict[str, Path] | None = None,
        org_root_chain: list[Path] | None = None,
        only: bool = False,
        reinstate: DenyListChoice = DenyListChoice.ACTIVATE,
    ) -> ActivationResult:
        """Activate ``artifact_id`` for ``kind`` in the project charter pack.

        Thin wrapper over :func:`charter.activation.activation_engine.plan_activation` +
        :func:`~charter.activation.activation_engine.commit_plan` (WP10). The engine
        validates the artifact ID *before* computing any post-state and, when
        the kind has no explicit activation set, materializes what is
        currently IN FORCE into the plan (#4253) — not a narrower shipped
        list, whose materialization silently deactivated everything outside
        it. This method supplies that effective set from the one public seam,
        :func:`charter.activation.effective_set.resolve_effective_sets`, and
        performs the single ``commit_plan`` write. Activation stays tolerant:
        when the set cannot be resolved it falls back to the available ids
        (an explicit activation has already validated its id) and says so in
        :attr:`ActivationResult.warnings`.

        Parameters
        ----------
        ctx:
            Project context providing access to the repository root.
        kind:
            Charter kind operator token (e.g. ``"directive"``,
            ``"mission-type"``).
        artifact_id:
            Artifact ID to activate.
        cascade:
            Accepted for signature stability; DRG edge traversal is handled by
            the CLI-level ``charter cascade`` command. No warning is emitted.
        layer_roots:
            Optional org/project doctrine roots, passed as data by CLI callers.
            When omitted, validation remains built-in-only for compatibility.
        org_root_chain:
            Optional full, declaration-ordered org-pack chain. When supplied,
            availability is validated in one scan across every chain root
            (last-declared first) instead of the single ``layer_roots["org"]``
            slot; when ``None`` the single-slot behaviour is unchanged.
        only:
            Opt-in narrowing (#6408): the kind's list becomes *artifact_id* plus
            the org-required ids (as stems), replacing any present list;
            :attr:`ActivationResult.deactivated` names what stopped being in force.
        reinstate:
            The explicit choice recorded when the id's exclusion is cleared
            (:attr:`DenyListChoice.ACTIVATE` for ``charter activate``; the
            cascade's ``--include-deactivated`` passes its own).

        Returns
        -------
        ActivationResult
            Contains activated IDs, warnings, and cascade info.

        Raises
        ------
        ValueError
            If ``kind`` is not in the canonical charter kind universe, or the
            artifact ID is unknown (the engine raises the typed
            :class:`~charter.activation.activation_engine.UnknownActivationIdError`, a
            ``ValueError`` subclass).
        """
        self._require_kind(kind)
        yaml_key = YAML_KEY_MAP[kind]

        repo_root = ctx.require_repo_root()
        target_path, data, save = resolve_activation_write_target(repo_root)

        available = self.list_available(ctx, kind, layer_roots=layer_roots, org_root_chain=org_root_chain)
        when_absent = self._effective_when_absent(kind)
        artifact_id = _identity_normalised(repo_root, self._require_kind(kind), artifact_id, yaml_key, data, available)
        deny = _deny_inputs(repo_root, self._require_kind(kind), artifact_id)
        artifact_id = deny.artifact_id
        preserved, preservation_warnings, in_force = _preservation_set(repo_root, kind, yaml_key, data, available, when_absent, deny)

        narrow: _NarrowInputs | None = None
        available_ids: Iterable[str] = available
        if only and artifact_id in available:
            narrow = _narrow_inputs(repo_root, self._require_kind(kind), artifact_id, yaml_key, data, preserved, in_force)
            available_ids = {*available, narrow.artifact_id}
            artifact_id = narrow.artifact_id
            preservation_warnings = [*preservation_warnings, *narrow.warnings]

        # plan_activation validates BEFORE computing any post-state (NFR-003);
        # on an unknown ID it raises UnknownActivationIdError and no write
        # happens.
        plan = plan_activation(
            kind,
            artifact_id,
            yaml_key=yaml_key,
            available_ids=available_ids,
            config_data=data,
            effective_ids=preserved,
            effective_when_absent=when_absent,
            effective_ids_in_force=in_force,
            narrow_base=narrow.base if narrow is not None else None,
            previous_ids=narrow.previous if narrow is not None else (),
            deny_key=deny.key,
            current_deny=deny.stored,
            deny_change=reinstate,
            effective_deny=deny.effective,
        )

        _added, reinstated = deny_delta(deny.stored, plan.new_deny_list) if plan.deny_key else ([], [])
        result = ActivationResult(
            activated=list(plan.activated),
            deactivated=list(plan.deactivated),
            warnings=preservation_warnings + list(plan.warnings) + [f"Cleared the exclusion of {item!r} ({deny.key})." for item in reinstated],
        )

        commit_plan(target_path, data, plan, save=save)
        restamp_bundle_hash(repo_root)
        return result

    def deactivate(
        self,
        ctx: ProjectContext,
        kind: str,
        artifact_id: str,
        *,
        cascade: bool = False,  # noqa: ARG002 — kept for caller API stability
        layer_roots: dict[str, Path] | None = None,
        org_root_chain: list[Path] | None = None,
        record_exclusion: bool = True,
    ) -> ActivationResult:
        """Deactivate ``artifact_id`` for ``kind`` in the project charter pack (FR-007).

        Thin wrapper over :func:`charter.activation.activation_engine.plan_deactivation` +
        :func:`~charter.activation.activation_engine.commit_plan`. It **always**
        reads the strict required floor first: an id any declared org pack
        requires (directly or through ``extends:``) raises
        :class:`~charter.activation.activation_engine.RequiredArtifactDeactivationError`
        and nothing is written; an unreadable declared pack raises
        :class:`ActiveCharterConfigError`. Otherwise the id (in stem spelling)
        is removed from a present allow list and recorded in
        ``deactivated_<plural>`` — also when the allow list is absent. An id
        that is already denied writes nothing and warns.

        Parameters
        ----------
        ctx:
            Project context providing access to the repository root.
        kind:
            Charter kind operator token (e.g. ``"directive"``).
        artifact_id:
            Artifact ID to deactivate (a stem or a declared id).
        cascade:
            Accepted for signature stability; DRG shared-reference analysis is
            handled by the CLI-level ``charter cascade`` command. No warning is emitted.
        layer_roots:
            Org/project doctrine roots for the availability check (resolved
            from *ctx* when omitted).
        org_root_chain:
            The full org-pack chain for the availability check (resolved from
            *ctx* when omitted).
        record_exclusion:
            ``False`` for a cascade child: it only loses its allow-list entry
            and gets no deny entry (D-11).

        Returns
        -------
        ActivationResult
            Contains deactivated IDs and warnings.

        Raises
        ------
        ValueError
            If ``kind`` is not in the canonical charter kind universe, or the
            id is unknown (:class:`UnknownActivationIdError`).
        DeactivationRefused
            If the id is required by an org pack.
        """
        kind_enum = self._require_kind(kind)
        yaml_key = YAML_KEY_MAP[kind]

        repo_root = ctx.require_repo_root()
        target_path, data, save = resolve_activation_write_target(repo_root)
        inputs = _deactivation_inputs(repo_root, kind_enum, artifact_id)
        stem, deny_key, required_by = inputs.stem, inputs.deny_key, inputs.required_by
        # Refuse a required id before the availability scan (the planner checks again: it is pure and self-contained).
        check_deactivation_permitted(kind, stem, required_by)
        available = self.list_available(ctx, kind, **_availability_roots(repo_root, layer_roots, org_root_chain))

        plan = plan_deactivation(
            kind,
            stem,
            yaml_key=yaml_key,
            config_data=data,
            available_ids=available,
            required_by=required_by,
            deny_key=deny_key,
            current_deny=inputs.stored_deny,
            record_exclusion=record_exclusion,
            also_matches=inputs.spellings,
        )

        result = ActivationResult(deactivated=list(plan.deactivated), warnings=list(plan.warnings))

        # Guard only the side effect: a no-op plan writes nothing and leaves the
        # activation source bytes untouched (NFR-001).
        if not plan.noop:
            commit_plan(target_path, data, plan, save=save)
            restamp_bundle_hash(repo_root)
        return result

    def list_activated(
        self,
        ctx: ProjectContext,
    ) -> dict[str, frozenset[str] | None]:
        """Return activated artifact IDs keyed by charter kind token.

        A ``None`` value means the kind has no explicit activation set in the
        source the activation ledger seam resolves (the ledger, or before the
        ledger migration ``charter.yaml`` / ``config.yaml``).

        Parameters
        ----------
        ctx:
            Project context providing access to the repository root.

        Returns
        -------
        dict[str, frozenset[str] | None]
            Mapping of charter kind token to activated IDs (or ``None``).
        """
        repo_root = ctx.require_repo_root()
        data = load_activation_ledger(repo_root).raw()

        result: dict[str, frozenset[str] | None] = {}
        for kind, yaml_key in YAML_KEY_MAP.items():
            raw = _activation_list_or_error(data, yaml_key)
            if raw is None:
                result[kind] = None
            else:
                result[kind] = frozenset(str(item) for item in raw)
        return result

    def _scan_layer_dirs(
        self,
        kind_token: str,
        *,
        layer_roots: dict[str, Path] | None,
        org_root_chain: list[Path] | None = None,
    ) -> list[tuple[str, Path]]:
        """Return ``(layer, directory)`` pairs to scan for *kind_token*.

        The built-in layer is rooted under the installed built-in pack
        (``packs/built-in``). Org/project roots are supplied **as data** (C-008).
        Org roots use the flat pack layout ``<plural>/``. The project
        root is the project pack root (``.kittify/charter-packs/``) and uses
        the flat ``<singular>`` kind layout. Non-existent directories are
        skipped so a layer that is simply not present contributes nothing.

        When *org_root_chain* is non-empty, the ORG layer emits one scan pair
        per chain root, last-declared first (the last declared pack wins),
        replacing the single ``layer_roots["org"]`` slot. When ``None`` or
        empty, the single-slot behaviour is unchanged.
        """
        kind = _resolve_kind(kind_token)
        base_dir, _glob, layered = _scan_layout_for(kind)
        roots: dict[str, Path] = {BUILT_IN: _SRC_ROOT}
        if layer_roots:
            roots.update(layer_roots)

        dirs: list[tuple[str, Path]] = []
        for layer in _LAYER_SEGMENTS:
            layer_candidates = org_root_chain[::-1] if layer == ORG and org_root_chain else [roots.get(layer)]
            for root in layer_candidates:
                if root is None:
                    continue
                candidate = _resolve_layer_candidate(layer, root, kind, base_dir, layered=layered)
                if candidate is not None and candidate.is_dir():
                    dirs.append((layer, candidate))
        return dirs

    def list_available_detailed(
        self,
        ctx: ProjectContext,  # noqa: ARG002 — kept for signature symmetry; roots are data (C-008)
        kind: str,
        *,
        layer_roots: dict[str, Path] | None = None,
        org_root_chain: list[Path] | None = None,
    ) -> list[AvailableArtifact]:
        """Return available artifacts for *kind*, annotated by source layer.

        Scans the built-in layer plus any caller-supplied org / project doctrine
        roots (FR-026), reading each artifact's ``id:`` field (R-011-D) rather
        than its filename stem. Org/project roots are passed in **as data**
        (C-008); this method never imports ``specify_cli`` and performs no root
        resolution of its own.

        Parameters
        ----------
        ctx:
            Project context (unused for scanning; roots are passed as data).
        kind:
            Charter kind operator token (e.g. ``"directive"``).
        layer_roots:
            Optional mapping of layer name (``"org"`` / ``"project"``) to the
            resolved doctrine root for that layer. When omitted, only the
            built-in layer is scanned (backward compatible).
        org_root_chain:
            Optional full org-pack chain; when supplied the ORG layer is
            scanned across every chain root (last-declared first) instead of
            the single ``layer_roots["org"]`` slot.

        Returns
        -------
        list[AvailableArtifact]
            One entry per discovered artifact, with its operator-facing
            config-stem ID (the form used in ``config.yaml`` activation lists,
            e.g. ``"003-decision-documentation-requirement"``) and its source
            layer. For the 7 standard ``ArtifactKind`` kinds, files that do
            not parse or carry no ``id:`` field are skipped — R-011-D
            id-awareness: the catalog validates the declared ``id:`` rather
            than blindly trusting the filename. When the same ID appears in
            multiple layers, each layer yields its own entry (the caller
            decides precedence/rendering).

            For the ``mission-type`` outlier (``kind is None``), a malformed
            file or an unreadable ``mission_types/`` directory RAISES instead
            of being skipped (PR-CONTRACT-002) — this branch reuses
            :func:`~charter.offering.missions.mission_type_repository.scan_mission_types_dir`,
            the same schema-validating, loud-fail primitive
            ``resolve_layered_mission_types`` uses post-activation, so the
            pre-activation availability catalog cannot silently disagree with
            subsequent resolution of the same file.

        Raises
        ------
        ValueError
            If ``kind`` is not in the canonical charter kind universe.
        ValueError
            (mission-type only) If a scanned ``mission_types/`` file is
            malformed, fails :class:`~charter.offering.missions.models.MissionType`
            schema validation, or a scanned directory exists but cannot be
            read.
        """
        _ = ctx
        kind_enum = self._require_kind(kind)
        yaml = YAML(typ="safe")
        _base_dir, glob, _layered = _scan_layout_for(kind_enum)
        if not glob:
            # template kind has no glob; resolved mission-tier by WP18.
            return []

        if kind_enum is None:
            # PR-CONTRACT-002 (pre-merge squad, mission
            # up-mission-type-seam-01KZY1JB): route the mission-type branch
            # through the SAME schema-validating, loud-fail, non-recursive
            # scan primitive (``scan_mission_types_dir``)
            # ``resolve_layered_mission_types`` already uses post-activation,
            # instead of the generic ``rglob`` + tolerant ``_declared_id``
            # walk below. Pre-fix, a malformed or unreadable org/project
            # ``mission_types/`` entry was silently dropped here (swallowed
            # by ``_declared_id``'s broad except / ``rglob``'s own
            # ``PermissionError`` swallowing) while the identical file
            # already loud-failed post-activation -- two contradictory
            # behaviours for the same input. Kept as a SEPARATE branch (not
            # a change to the loop below) so the other 7
            # charter-activatable kinds keep their existing tolerant scan
            # unchanged: this is the narrowest fix that makes the two
            # mission-type paths agree, not a blast-radius change to
            # ``list_available_detailed``'s shared per-kind loop.
            mt_entries: list[AvailableArtifact] = []
            for layer, scan_dir in self._scan_layer_dirs(kind, layer_roots=layer_roots, org_root_chain=org_root_chain):
                for mission_type in scan_mission_types_dir(scan_dir):
                    mt_entries.append(AvailableArtifact(artifact_id=mission_type.id, layer=layer))
            return mt_entries

        entries: list[AvailableArtifact] = []
        for layer, scan_dir in self._scan_layer_dirs(kind, layer_roots=layer_roots, org_root_chain=org_root_chain):
            for yaml_file in sorted(scan_dir.rglob(glob)):
                # R-011-D: confirm the artifact declares an ``id:`` (parse it)
                # rather than trusting the filename; surface the operator-facing
                # config-stem ID that ``config.yaml`` activation lists use.
                if _declared_id(yaml_file, kind_enum, yaml) is None:
                    continue
                entries.append(AvailableArtifact(artifact_id=_config_stem(yaml_file), layer=layer))
        return entries

    def list_available(
        self,
        ctx: ProjectContext,
        kind: str,
        *,
        layer_roots: dict[str, Path] | None = None,
        org_root_chain: list[Path] | None = None,
    ) -> frozenset[str]:
        """Return the set of available artifact IDs for *kind* across layers.

        Backward-compatible flat view over :meth:`list_available_detailed`:
        returns the union of artifact ``id:`` values across the built-in, org,
        and project layers (FR-026). Existing callers
        (``consistency_check``, ``charter list --show-available``) keep the
        ``frozenset[str]`` contract; ``layer_roots`` is keyword-only with a safe
        default so the built-in-only call site is unchanged.

        Parameters
        ----------
        ctx:
            Project context (roots are passed as data, C-008).
        kind:
            Charter kind operator token (e.g. ``"directive"``).
        layer_roots:
            Optional mapping of org/project layer name to its doctrine root.
        org_root_chain:
            Optional full org-pack chain scanned in place of the single org slot.

        Returns
        -------
        frozenset[str]
            Available artifact IDs (from each artifact's ``id:`` field). Empty
            when no scannable directory exists for the kind.

        Raises
        ------
        ValueError
            If ``kind`` is not in the canonical charter kind universe.
        """
        entries = self.list_available_detailed(ctx, kind, layer_roots=layer_roots, org_root_chain=org_root_chain)
        return frozenset(entry.artifact_id for entry in entries)


# Re-export the engine's structured errors for callers that import them from
# ``pack_manager`` (the CLI, WP12, catches these to surface guidance).
__all__ += ["DeactivationRefused", "RequiredArtifactDeactivationError", "RequiringPack", "UnknownActivationIdError"]
