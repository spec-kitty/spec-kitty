"""Charter pack activation manager (FR-001, FR-002, FR-026, FR-027).

Provides ``CharterPackManager`` — the single interface for activating and
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
then perform the single ``commit_plan`` write. The legacy ``sys.exit(1)`` in
``deactivate`` is gone — the engine raises a typed
:class:`~charter.activation.activation_engine.NoActivationRestrictionsError` that the CLI
(WP12) surfaces.

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
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.activation.activation_engine import (
    NoActivationRestrictionsError,
    UnknownActivationIdError,
    commit_plan,
    plan_activation,
    plan_deactivation,
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
from charter.activation.pack_context import CharterPackConfigError, resolve_charter_yaml_pointer
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

if TYPE_CHECKING:
    from charter.activation.invocation_context import ProjectContext

__all__ = [
    "ACTIVATION_YAML_KEYS",
    "ActivationResult",
    "AvailableArtifact",
    "CharterPackManager",
    "MergeResult",
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
ACTIVATION_YAML_KEYS: tuple[str, ...] = ("activated_kinds", *YAML_KEY_MAP.values())


#: Layer segments scanned for artifact availability (FR-026), in precedence
#: order. ``specify_cli`` resolves the org/project *roots* (C-008); this module
#: only knows the directory-segment names.
_LAYER_SEGMENTS: tuple[str, ...] = ("built-in", "org", "project")
_KITTIFY_DIRNAME = ".kittify"
_CONFIG_FILENAME = "config.yaml"
_CHARTER_FILENAME = "charter.md"
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

    Two base-dir outliers do not follow ``doctrine/<plural>``:

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
    :meth:`CharterPackManager._scan_layer_dirs`'s flat-kind branch, the one
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
    # The 7 standard artifact kinds: doctrine/<plural>/<layer>/ with the
    # canonical glob from ArtifactKind.
    return (f"doctrine/{kind.plural}", kind.glob_pattern, True)


def _resolve_org_layer_dir(root: Path, kind: ArtifactKind, base_dir: str) -> Path:
    """Resolve the org-layer scan directory, tolerant of flat vs nested layouts.

    FR-013 unifies the charter activation subsystem with runtime, which resolves
    org packs from the **flat** ``<pack>/<plural>/`` layout
    (``resolve_org_roots`` → ``DoctrineService``). Flat is therefore the
    canonical, preferred layout. The legacy nested
    ``<pack>/doctrine/<plural>/org/`` layout is kept as a fallback so packs that
    already ship the nested layout keep resolving — a layout-tolerant default,
    not a hard cutover (post-tasks squad decision; keeps the un-owned nested
    catalog fixtures green).
    """
    flat = root / kind.plural
    if flat.is_dir():
        return cast(Path, flat)
    return root / base_dir / "org"


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
    known directory layout — :meth:`CharterPackManager._scan_layer_dirs`
    then skips that layer for this kind (mirrors the pre-extraction
    ``else: continue`` branch).
    """
    if layered and layer == "project" and kind is not None:
        kind_dir = _PROJECT_KIND_DIRS.get(kind, kind.plural)
        return cast(Path, root / "doctrine" / kind_dir)
    if layered and layer == "org" and kind is not None:
        return _resolve_org_layer_dir(root, kind, base_dir)
    if layered and layer == "built-in" and kind is not None:
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
    if layer == "built-in":
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
    if kind is None and layer == "org":
        # FR-003: the org-layer mission-type roster is flat --
        # <pack_root>/mission_types/*.yaml (CL-005; see ADR
        # docs/adr/3.x/2026-08-13-1-mission-type-roster-layering-seam.md).
        # `root` here is the org pack root itself (see
        # specify_cli.cli.commands.charter._layer_roots.resolve_layer_roots
        # -> charter.drg.resolve_org_roots), the same root
        # _resolve_org_layer_dir's flat-layout branch joins onto for the
        # ArtifactKind case above. The ``mission_types`` segment is the
        # authority's own constant (#3427) -- the same one
        # resolve_layered_mission_types scans -- never a locally re-spelled
        # literal.
        return root / ORG_MISSION_TYPES_SUBDIR
    if kind is None and layer == "project":
        # FR-005: the project-layer mission-type roster is flat and
        # non-recursive -- .kittify/missions/mission_types/*.yaml (CL-005).
        # `root` here is already `repo_root / ".kittify"` (see
        # resolve_layer_roots), so the join consumes the authority's own
        # under-`.kittify` tail constant (derived in
        # charter.offering.missions.mission_type_repository beside the
        # repo-root-relative tuple it comes from, #3427) rather than
        # re-spelling the layout locally. This joins to a FLAT sibling of, not
        # nested inside, the pre-existing per-mission-instance
        # `.kittify/missions/<mission_name>/` convention --
        # `_mission_dir_if_valid` (src/specify_cli/mission.py) only
        # recognizes a subdirectory holding a file literally named
        # `mission.yaml`, which this roster's `*.yaml` files (named after
        # mission-type ids) never are.
        return root.joinpath(*PROJECT_MISSION_TYPES_RELATIVE_TO_KITTYFY_ROOT)
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


def _chain_complete_available(
    manager: CharterPackManager,
    ctx: ProjectContext,
    kind: str,
    repo_root: Path,
    layer_roots: dict[str, Path] | None,
) -> frozenset[str]:
    """``list_available`` across EVERY declared org pack, not just pack #1.

    #4399 squad MAJOR: the CLI's ``layer_roots`` map deliberately truncates the
    org chain to the first pack — a documented back-compat contract for
    ``charter list --all-layers`` and every consumer typed
    ``dict[str, Path]`` (see ``_layer_roots.resolve_org_root_chain``). Reusing
    that map as the preservation source meant artifacts in org packs 2+ were
    absent from the preserved set, so the first activation kept silently
    deactivating them — #4253's exact failure mode in a supported
    configuration. Scanning once per declared root and unioning keeps the
    truncated contract intact for its own callers while giving activation the
    whole picture.
    """
    from charter.offering.drg.org_pack_config import resolve_org_roots  # noqa: PLC0415 — lazy: avoids an import cycle

    available: set[str] = set(manager.list_available(ctx, kind, layer_roots=layer_roots))
    try:
        org_roots = [root for root in resolve_org_roots(repo_root, quiet=True) if root.is_dir()]
    except Exception as exc:  # noqa: BLE001 — a malformed pack registry must not fail the activation
        logger.debug("org-chain scan unavailable: %s", exc)
        return frozenset(available)

    for org_root in org_roots:
        roots = dict(layer_roots or {})
        roots["org"] = org_root
        try:
            available.update(manager.list_available(ctx, kind, layer_roots=roots))
        except Exception as exc:  # noqa: BLE001 — one unreadable pack must not drop the rest
            logger.debug("org pack %s unreadable for kind %r: %s", org_root, kind, exc)
    return frozenset(available)


def _effective_ids_for_kind(repo_root: Path, kind: str) -> tuple[str, ...]:
    """What the activation-aware resolver currently has in force for *kind*.

    #4253's fix materializes this set when a kind's activation key is absent
    (the unrestricted state), instead of the narrower default pack. #4399's
    squad round showed why it must come from the RESOLVER rather than from
    :meth:`CharterPackManager.list_available`:

    * ``list_available`` is handed the CLI's ``layer_roots`` map, which
      deliberately truncates the declared org chain to pack #1 (a documented
      back-compat contract — see ``_layer_roots.resolve_org_root_chain``), so
      artifacts in org packs 2+ were absent from the preserved set and stayed
      deactivated;
    * the resolver filters Pattern-B/C kinds (procedures, agent profiles, …)
      on each artifact's declared ``id:`` by plain membership, so a set
      written as filename stems is filtered straight back out whenever a
      declared id diverges from its stem.

    Reading the service's own mapping avoids both: it spans every declared
    layer and its keys are, by construction, the keys the filter compares
    against.

    Returns an empty tuple — leaving the caller on its previous
    ``available_ids`` behaviour — when the kind has no service-side mapping
    (``mission-type`` is an activation ledger, not a doctrine corpus) or when
    the service cannot be built at all. Diagnostics must never turn an
    activation into a failure.
    """
    yaml_key = YAML_KEY_MAP.get(kind, "")
    if not yaml_key.startswith("activated_"):
        return ()  # mission-type: an activation ledger, not a resolvable corpus
    if kind == "directive":
        # Pattern A: the directive getter resolves config stems through the
        # shared vocabulary (``_normalize_directive_id``), so the authored
        # stem spelling already satisfies the filter. Emitting the resolver's
        # canonical ``DIRECTIVE_NNN`` keys here would rewrite every project's
        # ``activated_directives`` into a second spelling for no gain.
        return ()
    attribute = yaml_key.removeprefix("activated_")
    try:
        from charter.activation.doctrine_service_builder import (  # noqa: PLC0415 — lazy: avoids an import cycle
            build_activation_aware_doctrine_service,
        )

        service = build_activation_aware_doctrine_service(repo_root)
        mapping = getattr(service, attribute, None)
        if not isinstance(mapping, Mapping):
            return ()
        return tuple(str(key) for key in mapping)
    except Exception as exc:  # noqa: BLE001 — preservation is best-effort; never fail an activation over it
        logger.debug("effective-set read for kind %r unavailable: %s", kind, exc)
        return ()


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


@dataclass
class MergeResult:
    """Result of a merge_defaults() operation."""

    kinds_written: list[str] = field(default_factory=list)
    backup_path: Path | None = None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_DEFAULT_PACK_PATH = Path(__file__).parent / "packs" / "default.yaml"

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


def _save_charter_yaml_activation(charter_path: Path, data: dict[str, Any]) -> None:
    """INV-9 write path: persist activation keys through the shared helper.

    ``data`` is the full in-memory ``charter.yaml`` document (governance /
    directives / catalog / metadata / overrides plus the flat activation
    keys); only the flat activation keys known to :data:`YAML_KEY_MAP` are
    ever written, via :func:`~charter.activation.charter_yaml_io.update_charter_yaml_section`'s
    ``"activation"`` pseudo-section — so unrelated sections are structurally
    preserved rather than conventionally preserved (Landmine 3 / INV-9).

    Safe to call once per changed key (``CharterPackManager.activate`` /
    ``deactivate``) or once for a batch of keys (``merge_defaults``,
    ``charter.activation.activation_engine.promote_activations``): only the keys
    actually present in ``data`` are written, and re-writing an unchanged
    key is idempotent.
    """
    values = {key: data[key] for key in YAML_KEY_MAP.values() if key in data}
    if values:
        update_charter_yaml_section(charter_path, "activation", values)


def resolve_activation_write_target(
    repo_root: Path,
) -> tuple[Path, dict[str, Any], Callable[[Path, dict[str, Any]], None]]:
    """Resolve the ``(path, loaded document, save)`` triple for activation writes.

    Shared by :class:`CharterPackManager` and the two other activation
    writers (``specify_cli.cli.commands.charter.interview`` and
    ``specify_cli.doctrine.org_charter``) so pointer resolution has exactly
    one implementation on the write side — mirroring
    :meth:`charter.activation.pack_context.PackContext.from_config` on the read side
    (INV-2/INV-5/INV-9).

    Absent ``.kittify/config.yaml`` ``charter:`` pointer -> legacy /
    un-migrated project: the target IS ``config.yaml`` itself, written as a
    full ``ruamel`` round-trip document — the pre-relocation behavior,
    preserved byte-for-byte until the project runs the charter-bundle
    migration.

    Present pointer -> migrated project: the target is the pointed-at
    ``charter.yaml``; a dangling/unreadable pointer is a fail-loud
    :class:`~charter.activation.pack_context.CharterPackConfigError` (INV-5, re-homed
    #2530) rather than a silent fallback to the legacy config-embedded keys.
    Writes route through :func:`_save_charter_yaml_activation`, touching
    only the flat activation keys (INV-9).
    """
    config_path = repo_root / _KITTIFY_DIRNAME / _CONFIG_FILENAME
    config_data, yaml_inst = _load_config(config_path)

    charter_path = resolve_charter_yaml_pointer(repo_root, config_data)
    if charter_path is None:
        return config_path, config_data, functools.partial(_save_config, yaml=yaml_inst)

    if not charter_path.exists():
        raise CharterPackConfigError(
            f".kittify/config.yaml 'charter:' pointer names {charter_path}, "
            f"which does not exist.\nRemediation: run the charter-bundle "
            f"migration (`spec-kitty upgrade`) to (re)generate it, or fix "
            f"the 'charter:' pointer."
        )
    charter_data = load_charter_yaml(charter_path)
    if not isinstance(charter_data, dict):
        raise CharterPackConfigError(f"{charter_path} root must be a mapping.")
    return charter_path, charter_data, _save_charter_yaml_activation


def prepare_activation_write(repo_root: Path, values: dict[str, Any]) -> PreparedYamlWrite:
    """Prepare the canonical activation target, retaining config/pointer identity."""
    unknown = set(values) - set(ACTIVATION_YAML_KEYS)
    if unknown:
        raise ValueError(f"Unknown activation key(s): {sorted(unknown)}")
    config = repo_root / _KITTIFY_DIRNAME / _CONFIG_FILENAME
    inputs = tuple(observe_yaml_input(path) for path in (*reversed(config.parents), config))
    target, data, _save = resolve_activation_write_target(repo_root)
    before = observe_yaml_input(target)
    if before.content is not None and not yaml_documents_equal(YAML().load(before.content) or {}, data):
        raise ValueError(f"precondition_changed: {target}")
    if target != config:
        section = prepare_charter_yaml_section(target, "activation", values)
        desired = section.desired_bytes
    else:
        for key, value in values.items():
            if key not in data or data[key] != value:
                data[key] = value
        desired = render_yaml_document(before.content, data, YAML())
    return prepare_yaml_write(target, desired, section="activation", inputs=inputs + (before,))


def _load_default_pack() -> dict[str, list[str]]:
    """Load the built-in default pack IDs from the shipped default.yaml."""
    import yaml as _yaml

    with _DEFAULT_PACK_PATH.open("r", encoding="utf-8") as fh:
        raw: Any = _yaml.safe_load(fh)
    if not isinstance(raw, dict):
        return {}
    return {k: list(v) for k, v in raw.items() if isinstance(v, list)}


# ---------------------------------------------------------------------------
# CharterPackManager
# ---------------------------------------------------------------------------


class CharterPackManager:
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

    def activate(
        self,
        ctx: ProjectContext,
        kind: str,
        artifact_id: str,
        *,
        cascade: bool = False,  # noqa: ARG002 — kept for caller API stability
        layer_roots: dict[str, Path] | None = None,
    ) -> ActivationResult:
        """Activate ``artifact_id`` for ``kind`` in the project charter pack.

        Thin wrapper over :func:`charter.activation.activation_engine.plan_activation` +
        :func:`~charter.activation.activation_engine.commit_plan` (WP10). The engine
        validates the artifact ID *before* computing any post-state and, when
        the kind has no explicit activation set, materializes what is
        currently IN FORCE into the plan (#4253) — not the narrower default
        pack, whose materialization silently deactivated everything outside
        it. This method supplies that effective set (see
        :func:`_effective_ids_for_kind`) and performs the single
        ``commit_plan`` write.

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

        available = self.list_available(ctx, kind, layer_roots=layer_roots)
        # Preservation source (#4253 + #4399): every declared org pack, plus —
        # for the kinds the resolver filters by raw ``id:`` — the resolver's
        # own keys, so a declared id that diverges from its filename stem is
        # not written in a spelling the filter drops.
        preserved = set(_chain_complete_available(self, ctx, kind, repo_root, layer_roots))
        preserved.update(_effective_ids_for_kind(repo_root, kind))

        # plan_activation validates BEFORE computing any post-state (NFR-003);
        # on an unknown ID it raises UnknownActivationIdError and no write
        # happens.
        plan = plan_activation(
            kind,
            artifact_id,
            yaml_key=yaml_key,
            available_ids=available,
            config_data=data,
            effective_ids=sorted(preserved),
        )

        result = ActivationResult(activated=list(plan.activated), warnings=list(plan.warnings))

        commit_plan(target_path, data, plan, save=save)
        return result

    def deactivate(
        self,
        ctx: ProjectContext,
        kind: str,
        artifact_id: str,
        *,
        cascade: bool = False,  # noqa: ARG002 — kept for caller API stability
        layer_roots: dict[str, Path] | None = None,
    ) -> ActivationResult:
        """Deactivate ``artifact_id`` for ``kind`` in the project charter pack.

        Thin wrapper over :func:`charter.activation.activation_engine.plan_deactivation` +
        :func:`~charter.activation.activation_engine.commit_plan` (WP10). A kind with no
        explicit activation set has no known baseline, so the engine raises a
        typed :class:`~charter.activation.activation_engine.NoActivationRestrictionsError`
        (the CLI, WP12, surfaces the "run upgrade first" guidance) — there is no
        ``sys.exit`` here.

        Parameters
        ----------
        ctx:
            Project context providing access to the repository root.
        kind:
            Charter kind operator token (e.g. ``"directive"``).
        artifact_id:
            Artifact ID to deactivate.
        cascade:
            Accepted for signature stability; DRG shared-reference analysis is
            handled by the CLI-level ``charter cascade`` command. No warning is emitted.
        layer_roots:
            Accepted for caller symmetry with ``activate``. Deactivation validates
            against the current activation list, not the availability catalog.

        Returns
        -------
        ActivationResult
            Contains deactivated IDs and warnings.

        Raises
        ------
        ValueError
            If ``kind`` is not in the canonical charter kind universe.
        NoActivationRestrictionsError
            If the kind has no explicit activation set (the engine raises this;
            the CLI surfaces the upgrade guidance).
        """
        del layer_roots  # Accepted for API symmetry with activate(); deactivation ignores external layer maps.
        self._require_kind(kind)
        yaml_key = YAML_KEY_MAP[kind]

        repo_root = ctx.require_repo_root()
        target_path, data, save = resolve_activation_write_target(repo_root)

        plan = plan_deactivation(
            kind,
            artifact_id,
            yaml_key=yaml_key,
            config_data=data,
        )

        result = ActivationResult(deactivated=list(plan.deactivated), warnings=list(plan.warnings))

        # Guard only the side effect: a no-op removal (ID not present) writes
        # nothing and leaves the activation source bytes untouched. The returned
        # result is identical on both paths (S3516 -> single return).
        if plan.deactivated:
            commit_plan(target_path, data, plan, save=save)
        return result

    def list_activated(
        self,
        ctx: ProjectContext,
    ) -> dict[str, frozenset[str] | None]:
        """Return activated artifact IDs keyed by charter kind token.

        A ``None`` value means the kind has no explicit activation set (in
        ``charter.yaml`` for a migrated project, or in ``config.yaml`` for a
        legacy/un-migrated one — the project has not yet been upgraded to
        the pack-based model for that kind).

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
        _, data, _ = resolve_activation_write_target(repo_root)

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
    ) -> list[tuple[str, Path]]:
        """Return ``(layer, directory)`` pairs to scan for *kind_token*.

        The built-in layer is rooted under the installed doctrine package
        (``src/doctrine``). Org/project roots are supplied **as data** (C-008).
        Org roots use the pack layout ``doctrine/<plural>/org``. Project roots
        use the live project overlay layout ``doctrine/<singular>`` for kinds
        synthesized into ``.kittify/doctrine``. Non-existent directories are
        skipped so a layer that is simply not present contributes nothing.
        """
        kind = _resolve_kind(kind_token)
        base_dir, _glob, layered = _scan_layout_for(kind)
        roots: dict[str, Path] = {"built-in": _SRC_ROOT}
        if layer_roots:
            roots.update(layer_roots)

        dirs: list[tuple[str, Path]] = []
        for layer in _LAYER_SEGMENTS:
            root = roots.get(layer)
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
            for layer, scan_dir in self._scan_layer_dirs(kind, layer_roots=layer_roots):
                for mission_type in scan_mission_types_dir(scan_dir):
                    mt_entries.append(AvailableArtifact(artifact_id=mission_type.id, layer=layer))
            return mt_entries

        entries: list[AvailableArtifact] = []
        for layer, scan_dir in self._scan_layer_dirs(kind, layer_roots=layer_roots):
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
        return frozenset(entry.artifact_id for entry in self.list_available_detailed(ctx, kind, layer_roots=layer_roots))

    def merge_defaults(
        self,
        ctx: ProjectContext,
    ) -> MergeResult:
        """Merge the default pack into the activation source for all absent kinds.

        Only absent keys are written; present keys are not overwritten. The
        activation source is ``charter.yaml`` for a migrated project (a
        ``charter:`` pointer is present in ``config.yaml``) or ``config.yaml``
        itself for a legacy/un-migrated one — see
        :func:`resolve_activation_write_target`. If ``.kittify/charter/charter.md``
        exists it is backed up before any write.

        Parameters
        ----------
        ctx:
            Project context providing access to the repository root.

        Returns
        -------
        MergeResult
            Contains kinds written, backup path (if any), and warnings.
        """
        from kernel.clock import now_utc_compact_stamp

        repo_root = ctx.require_repo_root()
        charter_md_path = repo_root / _KITTIFY_DIRNAME / "charter" / _CHARTER_FILENAME

        result = MergeResult()

        # Backup charter.md if it exists before any write
        if charter_md_path.exists():
            ts = now_utc_compact_stamp()
            backup_dir = repo_root / _KITTIFY_DIRNAME / "charter" / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"charter-{ts}.md"
            backup_path.write_bytes(charter_md_path.read_bytes())
            result.backup_path = backup_path

        target_path, data, save = resolve_activation_write_target(repo_root)
        default_pack = _load_default_pack()

        for yaml_key in YAML_KEY_MAP.values():
            raw = _activation_list_or_error(data, yaml_key)
            if raw is None:
                default_ids = default_pack.get(yaml_key, [])
                data[yaml_key] = list(default_ids)
                # Map yaml_key back to CLI kind for the result
                kind = next(k for k, v in YAML_KEY_MAP.items() if v == yaml_key)
                result.kinds_written.append(kind)

        if result.kinds_written:
            save(target_path, data)

        return result


# Re-export the engine's structured errors for callers that import them from
# ``pack_manager`` (the CLI, WP12, catches these to surface guidance).
__all__ += ["NoActivationRestrictionsError", "UnknownActivationIdError"]
