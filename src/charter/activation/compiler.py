"""Charter compiler: interview answers + doctrine assets -> charter bundle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import functools
from io import StringIO
import logging
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.activation._io import load_charter_file
from charter.activation.catalog import DoctrineCatalog, load_doctrine_catalog, resolve_doctrine_root
from charter.activation.charter_yaml_io import (
    PreparedYamlWrite,
    apply_yaml_write,
    load_charter_yaml,
    observe_yaml_input,
    _YamlInput,
    prepare_yaml_write,
    save_charter_yaml,
    update_charter_yaml_section,
    yaml_documents_equal,
)
from kernel.clock import now_utc_stamp
from charter.activation.interview import (
    CharterInterview,
    LocalSupportDeclaration,
    validate_local_support_declarations,
)
from charter.activation.default_pack import load_default_mission_type_activations
from charter.activation.kind_vocabulary import ArtifactKind, UnknownArtifactIdError, resolve_artifact_urn
from charter.activation.language_scope import infer_repo_languages
from charter.activation.pack_context import PackContext
from charter.activation.resolver import DEFAULT_TOOL_REGISTRY
from charter.activation.schemas import (
    CharterCatalog,
    CharterCatalogReference,
    CharterYaml,
    CharterYamlMetadata,
    DirectivesConfig,
    GovernanceConfig,
)
from charter.offering.pack_paths import built_in_dir
from charter.offering.provenance import to_portable_source_path

logger = logging.getLogger(__name__)

__all__ = [
    "CharterReference",
    "CompiledCharter",
    "WriteBundleResult",
    "compile_charter",
    "provision_mission_type_activations",
    "resolve_config_activated_roots",
    "write_compiled_charter",
]

#: The flat charter/config activation key that WP04 (charter-activation-
#: authority) made mandatory for ``PackContext.from_config``. The
#: ``mission-type`` charter kind is the documented outlier that does not follow
#: the ``activated_<plural>`` pattern (see ``pack_manager.YAML_KEY_MAP``).
_MISSION_TYPE_ACTIVATIONS_KEY = "mission_type_activations"
# NOTE: ``ConfigActivatedRoots`` is intentionally NOT public API -- it is the
# return type of ``resolve_config_activated_roots`` but every real caller
# (e.g. ``specify_cli.cli.commands.charter._synthesis``) consumes the
# returned instance by attribute access and never imports the class name
# itself; only its own test module imports it directly, which does not
# count as a caller under ``test_no_public_symbol_in_all_is_unimported``
# (WP05/T021b, mission unify-charter-activation-surfaces-01KX5SJ9).


@dataclass(frozen=True)
class _SelectionBundle:
    """Bundled paradigm + directive selections passed to service-based reference builders."""

    paradigms: list[str]
    directives: list[str]


@dataclass(frozen=True)
class ConfigActivatedRoots:
    """Config-sourced activation roots (FR-001/FR-002), resolved to bare DRG ids.

    Replaces the retired ``answers.selected_*`` derivation source (WP02,
    IC-01). Directives and paradigms feed the legacy pipelines unchanged
    (directive-closure seed; paradigm direct YAML load); tactics, styleguides,
    toolguides, procedures, and agent profiles are *additionally* seeded as
    direct roots (T026) so an artefact activated directly in
    ``config.activated_*`` resolves in the compiled set even when no selected
    directive's transitive closure reaches it.
    """

    directives: list[str]
    paradigms: list[str]
    tactics: list[str]
    styleguides: list[str]
    toolguides: list[str]
    procedures: list[str]
    agent_profiles: list[str]


#: The ``PackContext`` per-artifact activation fields this compiler resolves.
#: Used to decide whether a project is "configured" (activates at least one
#: kind) for the FR-018 absence-is-empty delivery rule in
#: :func:`_resolve_config_activated_roots`.
_CONFIG_ACTIVATION_FIELDS: tuple[str, ...] = (
    "activated_directives",
    "activated_paradigms",
    "activated_tactics",
    "activated_styleguides",
    "activated_toolguides",
    "activated_procedures",
    "activated_agent_profiles",
)


def _resolve_config_activated_ids(
    kind: ArtifactKind,
    activated_stems: frozenset[str] | None,
    *,
    doctrine_root: Path,
    fallback_ids: frozenset[str],
    org_roots: list[Path] | None = None,
    layer_roots: dict[str, Path] | None = None,
) -> list[str]:
    """Resolve ``config.activated_<kind>`` stems to bare canonical DRG ids.

    ``activated_stems is None`` mirrors the three-state semantics documented
    on :class:`charter.activation.pack_context.PackContext`: the key is absent from
    ``.kittify/config.yaml`` (or no project config is available at all), so
    every built-in id for *kind* is available -- the same default already
    applied by ``charter.activation.resolver`` when filtering paradigms/procedures/agent
    profiles.

    *org_roots* extends the artefact scan to org/project-overlay pack roots
    (:attr:`charter.activation.pack_context.PackContext.pack_roots`, sans the built-in
    root at index 0) so a config-activated ORG artefact resolves instead of
    raising -- an activated stem that only exists in an org pack is not an
    unknown id (#2529).

    ``layer_roots`` adds the project doctrine overlay, using the same
    project-first precedence as runtime profile loading.

    A stem that cannot be resolved to a canonical id in any searched layer raises
    :class:`~charter.activation.kind_vocabulary.UnknownArtifactIdError` (propagated from
    :func:`~charter.activation.kind_vocabulary.resolve_artifact_urn`) rather than being
    silently dropped -- this closes the C-006 silent-drop vector that
    ``_sanitize_catalog_selection`` left open for the answers-sourced path.
    """
    if activated_stems is None:
        return sorted(fallback_ids)

    resolved = {
        resolve_artifact_urn(kind, stem, doctrine_root=doctrine_root, org_roots=org_roots, layer_roots=layer_roots).split(":", 1)[1] for stem in activated_stems
    }
    return sorted(resolved)


def _resolve_config_activated_roots(
    *,
    pack_context: PackContext | None,
    catalog: DoctrineCatalog,
    doctrine_root: Path,
) -> ConfigActivatedRoots:
    """Build the full config-sourced activation bundle for one compile."""

    # FR-018 (WP07/T038): retire the "absence => all built-ins" fallback at this
    # delivery boundary for CONFIGURED projects. A project that activates at
    # least one per-artifact kind but OMITS an ``activated_<kind>`` key delivers
    # NOTHING for that kind -- the absent key resolves to ``frozenset()``, never
    # the built-in fallback (spec scenario 7: "a project whose charter omits an
    # activated_<kind> key ... receives nothing for that kind"). A wholly
    # UNCONFIGURED project (no pack_context, or a pack_context with no
    # per-artifact activation at all -- a scaffold with no charter) keeps the
    # all-built-ins convenience default, which is not a per-project delivery
    # boundary.
    project_configured = pack_context is not None and any(getattr(pack_context, field) is not None for field in _CONFIG_ACTIVATION_FIELDS)

    def _stems(field_name: str) -> frozenset[str] | None:
        if pack_context is None:
            return None
        value: frozenset[str] | None = getattr(pack_context, field_name)
        if value is None and project_configured:
            return frozenset()
        return value

    # ``pack_context.pack_roots`` is ``(builtin_root, *org_pack_roots)``
    # (``PackContext.from_config``); the built-in root is already threaded
    # separately as ``doctrine_root``, so only the org/project-overlay
    # entries need to be passed to the resolver. Empty for non-org projects
    # (no behavior change) -- see #2529.
    org_roots: list[Path] | None = list(pack_context.pack_roots[1:]) if pack_context is not None else None

    layer_roots = {"project": pack_context.repo_root / ".kittify"} if pack_context is not None else None

    try:
        return ConfigActivatedRoots(
            directives=_resolve_config_activated_ids(
                ArtifactKind.DIRECTIVE,
                _stems("activated_directives"),
                doctrine_root=doctrine_root,
                fallback_ids=catalog.directives,
                org_roots=org_roots,
                layer_roots=layer_roots,
            ),
            paradigms=_resolve_config_activated_ids(
                ArtifactKind.PARADIGM,
                _stems("activated_paradigms"),
                doctrine_root=doctrine_root,
                fallback_ids=catalog.paradigms,
                org_roots=org_roots,
                layer_roots=layer_roots,
            ),
            tactics=_resolve_config_activated_ids(
                ArtifactKind.TACTIC,
                _stems("activated_tactics"),
                doctrine_root=doctrine_root,
                fallback_ids=catalog.tactics,
                org_roots=org_roots,
                layer_roots=layer_roots,
            ),
            styleguides=_resolve_config_activated_ids(
                ArtifactKind.STYLEGUIDE,
                _stems("activated_styleguides"),
                doctrine_root=doctrine_root,
                fallback_ids=catalog.styleguides,
                org_roots=org_roots,
                layer_roots=layer_roots,
            ),
            toolguides=_resolve_config_activated_ids(
                ArtifactKind.TOOLGUIDE,
                _stems("activated_toolguides"),
                doctrine_root=doctrine_root,
                fallback_ids=catalog.toolguides,
                org_roots=org_roots,
                layer_roots=layer_roots,
            ),
            procedures=_resolve_config_activated_ids(
                ArtifactKind.PROCEDURE,
                _stems("activated_procedures"),
                doctrine_root=doctrine_root,
                fallback_ids=catalog.procedures,
                org_roots=org_roots,
                layer_roots=layer_roots,
            ),
            agent_profiles=_resolve_config_activated_ids(
                ArtifactKind.AGENT_PROFILE,
                _stems("activated_agent_profiles"),
                doctrine_root=doctrine_root,
                fallback_ids=catalog.agent_profiles,
                org_roots=org_roots,
                layer_roots=layer_roots,
            ),
        )
    except UnknownArtifactIdError as exc:
        if pack_context is None:
            raise
        from charter.activation.pack_manager import resolve_activation_write_target

        source, _, _ = resolve_activation_write_target(pack_context.repo_root)
        raise UnknownArtifactIdError(f"{exc} Activation store: {source}.") from exc


def _direct_root_urns(config_roots: ConfigActivatedRoots) -> frozenset[str]:
    """Direct-activation root URNs (WP02 T026).

    These are the kinds that may be activated directly in
    ``config.activated_*`` with no directive edge reaching them (e.g. a
    styleguide or toolguide with only a ``suggests`` edge from an
    unreachable tactic). Directives seed the transitive closure separately
    (see :func:`_resolve_transitive_reference_graph`); paradigms are never
    DRG-reachable and are loaded directly from YAML, so neither appears here.
    """
    urns: set[str] = set()
    urns.update(f"{ArtifactKind.TACTIC.value}:{artifact_id}" for artifact_id in config_roots.tactics)
    urns.update(f"{ArtifactKind.STYLEGUIDE.value}:{artifact_id}" for artifact_id in config_roots.styleguides)
    urns.update(f"{ArtifactKind.TOOLGUIDE.value}:{artifact_id}" for artifact_id in config_roots.toolguides)
    urns.update(f"{ArtifactKind.PROCEDURE.value}:{artifact_id}" for artifact_id in config_roots.procedures)
    urns.update(f"{ArtifactKind.AGENT_PROFILE.value}:{artifact_id}" for artifact_id in config_roots.agent_profiles)
    return frozenset(urns)


def _bare_ids_for_kind(urns: frozenset[str], kind: ArtifactKind) -> list[str]:
    """Strip the ``"<kind>:"`` prefix from every URN in *urns* matching *kind*."""
    prefix = f"{kind.value}:"
    return [urn[len(prefix) :] for urn in urns if urn.startswith(prefix)]


def resolve_config_activated_roots(
    *,
    repo_root: Path,
    doctrine_catalog: DoctrineCatalog | None = None,
    pack_context: PackContext | None = None,
) -> ConfigActivatedRoots:
    """Resolve ``.kittify/config.yaml`` ``activated_*`` stems to bare canonical ids.

    Public entry point shared by both FR-002 derivation paths: this module's
    own :func:`compile_charter` (the ``references.yaml`` path) and
    ``specify_cli.cli.commands.charter._synthesis`` (the project-graph path,
    ``interview_snapshot``/``drg_snapshot``). Keeping the config-read + stem
    mapping logic here (rather than duplicating it in ``specify_cli``) is the
    charter/specify_cli layer rule for this mission: config-read and mapping
    logic live in ``charter``; ``specify_cli`` orchestrates.
    A supplied ``pack_context`` preflights proposed activations without writing them.
    """
    catalog = doctrine_catalog or load_doctrine_catalog()
    if pack_context is None:
        pack_context = PackContext.from_config(repo_root)
    doctrine_root = resolve_doctrine_root()
    return _resolve_config_activated_roots(
        pack_context=pack_context,
        catalog=catalog,
        doctrine_root=doctrine_root,
    )


if TYPE_CHECKING:
    # WP03 (charter-sole-door-bypass-closure-01KZ3WAA, FR-002/T011): this name
    # now denotes the activation-aware wrapper, not the raw
    # ``charter.offering.service.DoctrineService``. Every real caller already passes
    # (or, after this WP, receives from :func:`_default_doctrine_service`) a
    # wrapped instance -- ``generate.py``/``pack.py`` via
    # ``_build_doctrine_service_with_org_layer``, this module via the change
    # below -- so the annotation now matches what actually flows through
    # ``compile_charter``'s ``doctrine_service`` parameter and its helpers.
    from charter.activation.resolver import DoctrineService


@dataclass(frozen=True)
class CharterReference:
    """One reference item used by charter context."""

    id: str
    kind: str
    title: str
    summary: str
    source_path: str
    local_path: str
    content: str


@dataclass(frozen=True)
class CompiledCharter:
    """Compiled charter bundle."""

    mission: str
    template_set: str
    selected_paradigms: list[str]
    selected_directives: list[str]
    available_tools: list[str]
    markdown: str
    references: list[CharterReference]
    diagnostics: list[str] = field(default_factory=list)
    selected_tactics: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    #: ``None`` means "no active-language signal was found" (issue #3292) —
    #: distinct from a genuinely empty, deliberate answer. See
    #: :func:`charter.activation.language_scope.infer_repo_languages`, the single
    #: authority this field's value is sourced from.
    active_languages: list[str] | None = field(default_factory=list)


@dataclass(frozen=True)
class WriteBundleResult:
    """Filesystem write result for compiled charter bundle."""

    files_written: list[str]


def compile_charter(
    *,
    mission: str,
    interview: CharterInterview,
    template_set: str | None = None,
    doctrine_catalog: DoctrineCatalog | None = None,
    doctrine_service: DoctrineService | None = None,
    repo_root: Path | None = None,
    pack_context: PackContext | None = None,
) -> CompiledCharter:
    """Compile charter markdown, references manifest, and library docs.

    Artifact loading and transitive reference resolution always prefer the
    typed repository API and DRG-backed path. When *doctrine_service* is not
    supplied, a default service rooted at built-in doctrine (and an optional
    project overlay under *repo_root*) is constructed automatically.

    The activated-doctrine selection (paradigms, directives, tactics,
    styleguides, toolguides, procedures, agent profiles) is sourced from
    ``config.activated_*`` (FR-001/FR-002), never from
    ``interview.selected_*`` -- ``answers.selected_*`` is retired as an
    activation source and is captured purely as an interview record (see
    ``_user_profile_reference``). When *pack_context* is not supplied, it is
    built from ``.kittify/config.yaml`` under *repo_root* (mirroring
    :func:`_default_doctrine_service`); when neither is available, every kind
    resolves to "all built-ins active" -- the same absent-key default
    :class:`~charter.activation.pack_context.PackContext` already documents.

    *interview* is used as-is: doctrine-intent aliasing (e.g. the "Lynn
    Cole" free-text shorthand -> ``DIRECTIVE_039`` + ``deep-module-design``)
    happens at interview *construction* time (``charter.activation.interview``'s
    ``default_interview``/``from_dict``/``apply_answer_overrides``, all of
    which return an already-aliased :class:`CharterInterview`) and, for the
    interactive CLI flow, is promoted into ``config.activated_*`` before
    compilation ever runs (``specify_cli.cli.commands.charter.interview.
    _promote_interview_selections``). Re-aliasing here was a no-op for that
    path and had zero effect on the config-sourced activation set for any
    path (#2530) -- removed rather than re-applied a second time.
    """
    # Single authority (issue #3292): route through the SAME function the
    # doctrine-service language gate (charter.activation.doctrine_service_builder) uses,
    # passing the in-memory *interview* so a not-yet-persisted interview
    # (e.g. `charter generate --no-from-interview`) is still consulted. This
    # replaces an independent `extract_declared_languages` scan that used to
    # unconditionally stamp a (possibly meaningless-empty) list into
    # `catalog.languages`, which the next run's `infer_repo_languages` then
    # read back as authoritative "admit none" — see that function's
    # docstring for the full feedback-loop this closes.
    active_languages = infer_repo_languages(repo_root, interview=interview)
    catalog = doctrine_catalog or load_doctrine_catalog(active_languages=active_languages)
    diagnostics: list[str] = []

    if doctrine_service is None:
        doctrine_service = _default_doctrine_service(repo_root)

    if pack_context is None and repo_root is not None:
        pack_context = PackContext.from_config(repo_root)

    doctrine_root = resolve_doctrine_root()
    config_roots = _resolve_config_activated_roots(
        pack_context=pack_context,
        catalog=catalog,
        doctrine_root=doctrine_root,
    )

    template = _resolve_template_set(mission=mission, requested_template_set=template_set, catalog=catalog)
    available_tools = _sanitize_catalog_selection(
        values=interview.available_tools,
        allowed=set(DEFAULT_TOOL_REGISTRY),
        label="available_tools",
        diagnostics=diagnostics,
    )

    # Validate and normalize local support file declarations.
    # FR-008 (#3596, WP02): repo_root feeds the declared-node acceptance
    # source (charter.interview._declared_action_labels) alongside the
    # fast-path BOOTSTRAP_ACTIONS constant, so a declared non-fast-path
    # action (e.g. "tasks") is retained rather than warn-dropped.
    valid_local, local_errors = validate_local_support_declarations(
        list(interview.local_supporting_files or []),
        repo_root=repo_root,
    )
    diagnostics.extend(local_errors)

    references = _build_references(
        mission=mission,
        template_set=template,
        interview=interview,
        config_roots=config_roots,
        doctrine_service=doctrine_service,
        repo_root=repo_root,
        diagnostics=diagnostics,
    )

    # Build additive local support references.
    built_in_ids = _build_built_in_concept_ids(references)
    local_references = _build_local_support_references(
        valid_local,
        built_in_ids=built_in_ids,
        diagnostics=diagnostics,
    )
    references = references + local_references

    markdown = _render_charter_markdown(
        mission=mission,
        template_set=template,
        interview=interview,
        selected_paradigms=config_roots.paradigms,
        selected_directives=config_roots.directives,
        selected_tactics=config_roots.tactics,
        available_tools=available_tools,
        references=references,
        doctrine_service=doctrine_service,
    )

    return CompiledCharter(
        mission=mission,
        template_set=template,
        selected_paradigms=config_roots.paradigms,
        selected_directives=config_roots.directives,
        available_tools=available_tools,
        markdown=markdown,
        references=references,
        diagnostics=diagnostics,
        selected_tactics=config_roots.tactics,
        active_languages=active_languages,
    )


def write_compiled_charter(
    output_dir: Path,
    compiled: CompiledCharter,
    *,
    force: bool = False,
    repo_root: Path | None = None,
) -> WriteBundleResult:
    """Refresh ``charter.yaml``'s DERIVED sections (``catalog`` + ``metadata``).

    ``charter.md`` is a curated companion and is NEVER written by this
    function (data-model.md Landmine 3 -- the #2772 clobber, one level
    down, on a now-*tracked* file). Only ``catalog``/``metadata`` -- the
    DERIVED sections of ``charter.yaml`` -- are refreshed, through the
    shared INV-9 write helper (:mod:`charter.activation.charter_yaml_io`), which
    round-trips the document so the AUTHORED ``governance``/``directives``/
    activation/``overrides`` sections survive byte-for-byte. When
    ``charter.yaml`` does not exist yet there is nothing authored to
    preserve, so this is a one-time bootstrap (not the Landmine 3 clobber)
    rather than a merge.

    ``force`` no longer gates a destructive overwrite -- there is none left
    to gate, which is the entire point of the Landmine 3 fix. It is
    accepted for CLI/back-compat call-site stability and logged for
    diagnostic visibility only.
    """
    logger.debug(
        "write_compiled_charter(force=%s): charter.yaml writes are always "
        "either a safe partial merge (file exists) or a bootstrap create "
        "(file absent) -- force no longer gates a destructive overwrite.",
        force,
    )
    _assert_safe_charter_output_dir(output_dir, repo_root=repo_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    _assert_safe_charter_output_dir(output_dir, repo_root=repo_root)

    charter_yaml_path = output_dir / "charter.yaml"
    catalog = _build_catalog_dict(compiled)

    if charter_yaml_path.exists():
        preserved_generated_at = _preserved_generated_at(charter_yaml_path, catalog)
        metadata = _build_metadata_dict(preserved_generated_at=preserved_generated_at)
        update_charter_yaml_section(charter_yaml_path, "catalog", catalog)
        update_charter_yaml_section(charter_yaml_path, "metadata", metadata)
    else:
        metadata = _build_metadata_dict()
        _bootstrap_charter_yaml(charter_yaml_path, catalog=catalog, metadata=metadata, repo_root=repo_root)

    # WP04 (charter-activation-authority): the generated charter is the SOLE
    # mission-type activation authority, so generation MUST emit
    # ``mission_type_activations`` — otherwise the freshly written charter offers
    # NO mission types (construction reads an empty set; mission-CREATE then
    # fails closed against it). Additive and
    # idempotent: a charter that already carries the key (from the config-verbatim
    # bootstrap copy, a custom set, or an explicit ``[]`` opt-out) is untouched;
    # only an absent key is seeded from the built-in set. Skipped when there is
    # no project root to resolve the activation authority against.
    if repo_root is not None:
        provision_mission_type_activations(repo_root)

    return WriteBundleResult(files_written=["charter.yaml"])


@dataclass(frozen=True)
class _PreparedMissionTypeActivations:
    """Charter-owned projection; upgrade may adapt its write into an effect."""

    write: PreparedYamlWrite
    mission_type_activations: tuple[str, ...]
    reason: str

    def apply(self) -> bool:
        """Apply the retained bytes, refusing changed inputs without retry."""
        return apply_yaml_write(self.write)


def prepare_mission_type_activations(repo_root: Path) -> _PreparedMissionTypeActivations:
    """Read missing-key policy and prepare exact bytes without provisioning."""
    from charter.activation.default_pack import _default_pack_yaml_path
    from charter.activation.pack_manager import prepare_activation_write, resolve_activation_write_target

    repo_root = repo_root.resolve()
    initial = prepare_activation_write(repo_root, {})
    _, data, _save = resolve_activation_write_target(repo_root)
    initial.recheck()
    present = _MISSION_TYPE_ACTIVATIONS_KEY in data
    source_inputs: tuple[_YamlInput, ...] = ()
    if present:
        values = data[_MISSION_TYPE_ACTIVATIONS_KEY]
    else:
        seed = _default_pack_yaml_path(None)
        source_inputs = tuple(observe_yaml_input(path) for path in (*reversed(seed.parents), seed))
        values = load_default_mission_type_activations()
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ValueError(f"{_MISSION_TYPE_ACTIVATIONS_KEY} must be a list of strings")
    prepared = initial if present else prepare_activation_write(repo_root, {_MISSION_TYPE_ACTIVATIONS_KEY: values})
    write = prepare_yaml_write(
        prepared.target,
        prepared.desired_bytes,
        section="activation",
        inputs=initial.observations + source_inputs,
    )
    return _PreparedMissionTypeActivations(write, tuple(values), "key_present" if present else "key_missing")


def provision_mission_type_activations(repo_root: Path) -> bool:
    """Ensure the activation authority carries ``mission_type_activations``.

    WP04 (charter-activation-authority) made the provisioned charter the SOLE
    mission-type activation authority. Construction
    (:meth:`PackContext.from_config`) returns an EMPTY set when the key is
    absent (no all-four backfill); the fail-closed fires at the mission-CREATE
    boundary (``create_mission_core`` — a mission needs >=1 activated type).
    The charter *generation* path emits the key so a generated/pointer charter
    actually offers its mission types, mirroring the built-in
    ``activated_<kind>`` keys.

    Additive and idempotent (charter contract C-A2): the built-in mission-type
    set authored in ``src/charter/activation/packs/default.yaml`` is written ONLY when the
    key is entirely absent from the activation authority. An already-present
    list — a custom set or an explicit ``[]`` fail-closed opt-out — is left
    untouched.

    The write routes through
    :func:`charter.activation.pack_manager.resolve_activation_write_target` (the single
    write-side authority resolver, INV-2/INV-5/INV-9): for a migrated project
    (``config.yaml`` ``charter:`` pointer present) the target is the pointed-at
    ``charter.yaml`` and only its flat activation keys are touched; for a legacy
    project the target is ``config.yaml`` itself. That resolver never constructs
    a :class:`PackContext`, so provisioning does NOT re-trigger the fail-closed
    read it exists to repair (the WP04 chicken-and-egg where every
    ``PackContext``-building command refuses to run on an unprovisioned charter).

    Returns ``True`` when the key was written, ``False`` when provisioning was a
    no-op because the key was already present.

    Raises
    ------
    CharterPackConfigError
        When the shipped default pack declares no ``mission_type_activations``
        set (a broken install) — fail-closed rather than seeding an empty,
        equally-unusable list. Raised by the shared seed-read helper
        :func:`charter.activation.default_pack.load_default_mission_type_activations`
        (also consumed by ``spec-kitty init``/``upgrade`` provisioning), so
        both provisioners fail closed on the identical condition.
    """
    return prepare_mission_type_activations(repo_root).apply()


def _build_catalog_dict(compiled: CompiledCharter) -> dict[str, Any]:
    """Build the charter.yaml ``catalog`` section from a compiled charter.

    Mirrors the retired ``references.yaml`` body (contract G2): same
    per-reference keys, byte-equivalent content. Validated through
    :class:`~charter.activation.schemas.CharterCatalog` so a schema drift fails loud
    here rather than silently writing an invalid document.

    NFR-005: ``references`` is sorted by ``id`` here (canonical, deterministic
    order) rather than emitted in ``compiled.references``'s build order, which
    interleaves dict/set/graph-walk iteration order across paradigm, DRG-
    backed-kind, template, and local-support reference batches. A stable sort
    key on the one field every reference carries keeps a second, unchanged
    recompile a zero-line diff of this section (contract C4).
    """
    references = [
        CharterCatalogReference(
            id=reference.id,
            kind=reference.kind,
            title=reference.title,
            summary=reference.summary,
            source_path=reference.source_path,
            local_path=reference.local_path,
        )
        for reference in sorted(compiled.references, key=lambda reference: reference.id)
    ]
    catalog = CharterCatalog(
        mission=compiled.mission,
        template_set=compiled.template_set,
        # None (no active-language signal, #3292) is preserved as-is rather
        # than collapsed into `[]` -- `CharterCatalog.languages` is nullable
        # precisely so this "no signal" state round-trips as absent/null
        # instead of a persisted empty list that a later
        # `infer_repo_languages` call would treat as authoritative "admit
        # none". See that function's docstring for the full contract.
        languages=list(compiled.active_languages) if compiled.active_languages is not None else None,
        references=references,
    )
    dumped: dict[str, Any] = catalog.model_dump(mode="json")
    return dumped


def _preserved_generated_at(charter_yaml_path: Path, catalog: dict[str, Any]) -> str | None:
    """Return the on-disk ``metadata.generated_at`` when *catalog* is byte-unchanged.

    FR-008/NFR-002 (contract C4): a recompile that produces the identical
    ``catalog`` content must not restamp ``generated_at`` -- otherwise a true
    no-op recompile still shows a ``metadata`` diff. Returns ``None`` (fresh
    stamp) when the existing document cannot be read, has no comparable
    ``catalog``/``metadata.generated_at``, or the catalog content differs.
    """
    try:
        document = load_charter_yaml(charter_yaml_path)
    except (OSError, YAMLError, ValueError):
        return None
    if not isinstance(document, dict):
        return None
    existing_catalog = document.get("catalog")
    if existing_catalog is None or not yaml_documents_equal(existing_catalog, catalog):
        return None
    existing_metadata = document.get("metadata")
    if not isinstance(existing_metadata, dict):
        return None
    generated_at = existing_metadata.get("generated_at")
    return generated_at if isinstance(generated_at, str) else None


def _build_metadata_dict(*, preserved_generated_at: str | None = None) -> dict[str, Any]:
    """Build the charter.yaml ``metadata`` section (refresh timestamp).

    *preserved_generated_at*, when supplied by a caller that found the
    catalog content byte-unchanged from what is on disk (see
    :func:`_preserved_generated_at`), is used in place of a fresh stamp so a
    pure no-op recompile does not restamp ``generated_at`` (FR-008/NFR-002).
    """
    metadata = CharterYamlMetadata(
        generated_at=preserved_generated_at or now_utc_stamp(),
        bundle_schema_version=2,
    )
    dumped: dict[str, Any] = metadata.model_dump(mode="json")
    return dumped


#: Flat root activation key names read off the legacy ``config.yaml``
#: (pre-WP02 activation home). DERIVED from the single authority
#: :data:`charter.activation.pack_manager.ACTIVATION_YAML_KEYS` rather than hand-listed:
#: a hand-written literal here previously drifted from the authority (missing
#: ``activated_glossary_packs``), so charter.yaml bootstrap over a pre-WP02
#: project silently DROPPED glossary-pack activation on the READ -- the exact
#: FR-010/SC-005 data-loss the WP05 finalize migration and ``charter_yaml_io``
#: derivation eliminated on the WRITE side. The read/write distinction never
#: changed which activation keys exist, so both must derive from the same
#: authority. Lazy import breaks the ``pack_manager`` <-> ``compiler`` cycle
#: (mirrors :func:`charter.activation.charter_yaml_io._activation_keys`).
@functools.lru_cache(maxsize=1)
def _legacy_activation_keys() -> tuple[str, ...]:
    from charter.activation.pack_manager import ACTIVATION_YAML_KEYS  # noqa: PLC0415 -- avoids import cycle

    keys: tuple[str, ...] = ACTIVATION_YAML_KEYS
    return keys


def _read_legacy_config_activation(repo_root: Path) -> dict[str, list[str]]:
    """Read flat ``activated_*`` keys VERBATIM from ``.kittify/config.yaml``.

    Bootstrap-only helper: until WP02 relocates the activation ledger from
    ``config.yaml`` to ``charter.yaml``'s flat root keys, ``config.yaml``
    remains the live activation authority. Copied VERBATIM (an absent key
    stays absent, an explicit ``[]`` stays ``[]``) so bootstrap never
    invents or drops activation state (data-model.md "VERBATIM
    activation-list copy" discipline, echoed by WP07's migration).
    """
    config_path = repo_root / ".kittify" / "config.yaml"
    if not config_path.exists():
        return {}
    yaml = YAML()
    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.load(fh)
    if not isinstance(data, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key in _legacy_activation_keys():
        value = data.get(key)
        if isinstance(value, list):
            result[key] = [str(item) for item in value]
    return result


def _bootstrap_charter_yaml(
    charter_yaml_path: Path,
    *,
    catalog: dict[str, Any],
    metadata: dict[str, Any],
    repo_root: Path | None,
) -> None:
    """Create ``charter.yaml`` the first time -- NOT the Landmine 3 clobber.

    There is no prior authored content to destroy, so a full-document
    write here is a bootstrap, not a reconstruct-from-``CompiledCharter``
    clobber. ``governance``/``directives`` are seeded from the legacy
    triad when a curated ``charter.md`` is present --
    :func:`charter.activation.sync.load_governance_config` /
    :func:`~charter.activation.sync.load_directives_config` already implement
    "file missing -> empty config" gracefully (FR-4.4), which also covers
    a genuinely fresh project (no curated ``charter.md`` yet). Activation
    stays absent (three-state ``None`` == default-pack fallback, contract
    G3) unless ``repo_root``'s ``.kittify/config.yaml`` already carries
    flat ``activated_*`` keys (a pre-WP02 project) -- copied verbatim,
    never derived.
    """
    governance = GovernanceConfig()
    directives = DirectivesConfig()
    activation: dict[str, list[str]] = {}

    if repo_root is not None:
        from charter.activation.sync import load_directives_config, load_governance_config  # noqa: PLC0415

        governance = load_governance_config(repo_root)
        directives = load_directives_config(repo_root)
        activation = _read_legacy_config_activation(repo_root)

    charter_yaml = CharterYaml(
        governance=governance,
        directives=directives,
        catalog=CharterCatalog.model_validate(catalog),
        metadata=CharterYamlMetadata.model_validate(metadata),
    )
    # Activation is applied after model_dump (rather than passed as
    # constructor kwargs) so a heterogeneous **activation unpacking never
    # has to unify against CharterYaml's other, differently-typed fields
    # (e.g. schema_version: str) -- keeps this call mypy --strict clean.
    document: dict[str, Any] = charter_yaml.model_dump(mode="json", exclude_none=True)
    document.update(activation)
    save_charter_yaml(charter_yaml_path, document)

    if repo_root is not None:
        _mint_config_charter_pointer(repo_root, charter_yaml_path)


#: Config.yaml key WP02's activation-relocation reader resolves to find
#: charter.yaml (``charter: .kittify/charter/charter.yaml``). Duplicated
#: here (rather than imported) because this module must not depend on
#: WP02's activation-relocation reader for a one-line constant. (Unlike the
#: activation-key vocabulary -- see :func:`_legacy_activation_keys` above,
#: now derived from the authority -- this is a single opaque literal with no
#: authoritative source to drift from.)
_CONFIG_CHARTER_POINTER_KEY = "charter"


def _mint_config_charter_pointer(repo_root: Path, charter_yaml_path: Path) -> None:
    """Mint the ``charter:`` pointer into ``config.yaml`` on first bootstrap.

    Closes the WP02-review gap: when THIS function creates ``charter.yaml``
    for the first time (a brand-new ``spec-kitty init`` project, or any
    project that has not yet run the WP07 migration), ``config.yaml`` must
    ALSO gain the ``charter: .kittify/charter/charter.yaml`` pointer --
    otherwise the config-activation branch of WP02's reader stays
    permanently live (a project-wide split-brain rather than the intended
    *transitional* dual-branch). Comment-preserving ``ruamel.yaml``
    round-trip: every other ``config.yaml`` key/comment survives untouched;
    only the ``charter`` key is added or refreshed. A project with no
    ``config.yaml`` yet gets one containing just this key (``spec-kitty
    init`` always creates one before charter generation runs, but bootstrap
    itself must not depend on that ordering).
    """
    config_path = repo_root / ".kittify" / "config.yaml"
    yaml = YAML()
    yaml.preserve_quotes = True

    data: Any = None
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as fh:
            data = yaml.load(fh)
    if not isinstance(data, dict):
        data = {}

    try:
        pointer = charter_yaml_path.resolve(strict=False).relative_to(repo_root.resolve(strict=False)).as_posix()
    except ValueError:
        # charter_yaml_path is outside repo_root (should not happen given
        # _assert_safe_charter_output_dir already rejected that case) --
        # fall back to the canonical default location.
        pointer = ".kittify/charter/charter.yaml"

    data[_CONFIG_CHARTER_POINTER_KEY] = pointer
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)


def _assert_safe_charter_output_dir(
    output_dir: Path,
    *,
    repo_root: Path | None,
) -> None:
    """Reject symlinked charter output dirs before generated writes."""
    if repo_root is None:
        if output_dir.is_symlink():
            raise FileExistsError(
                f"Charter output directory {output_dir} is a symlink. Replace it with a normal .kittify/charter directory before running charter generate."
            )
        return

    root = repo_root.resolve(strict=False)
    candidate = output_dir if output_dir.is_absolute() else root / output_dir
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise FileExistsError(f"Charter output directory {output_dir} is outside repository root {repo_root}.") from exc

    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise FileExistsError(
                f"Charter output path {current} is a symlink. Replace it with a normal .kittify/charter directory before running charter generate."
            )

    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise FileExistsError(f"Charter output directory {output_dir} resolves outside repository root {repo_root}.") from exc


def _resolve_template_set(
    *,
    mission: str,
    requested_template_set: str | None,
    catalog: DoctrineCatalog,
) -> str:
    # ``catalog`` resolves to ``Any`` under single-file mypy, so bind the
    # attribute to its declared element type; this lets mypy infer ``str`` for
    # ``min(...)`` instead of propagating ``Any`` (no-any-return).
    template_sets: frozenset[str] = catalog.template_sets

    if requested_template_set:
        if template_sets and requested_template_set not in template_sets:
            options = ", ".join(sorted(template_sets))
            raise ValueError(f"Unknown template set '{requested_template_set}'. Available template sets: {options}")
        return requested_template_set

    mission_default = f"{mission}-default"
    if mission_default in template_sets:
        return mission_default

    if template_sets:
        return min(template_sets)

    return mission_default


def _sanitize_catalog_selection(
    *,
    values: list[str],
    allowed: set[str],
    label: str,
    diagnostics: list[str],
) -> list[str]:
    seen: list[str] = []
    missing: list[str] = []

    allowed_casefold = {item.casefold(): item for item in allowed}

    for raw in values:
        key = str(raw).strip()
        if not key:
            continue
        canonical = allowed_casefold.get(key.casefold())
        if canonical is None:
            missing.append(key)
            continue
        if canonical not in seen:
            seen.append(canonical)

    if missing:
        diagnostics.append(f"Ignored unknown {label}: {', '.join(sorted(missing))}")

    if seen:
        return seen

    # Explicitly empty selections remain empty. We do not broaden charter
    # doctrine or tool choices just because the interview provided no built-in
    # match.
    return []


def _default_doctrine_service(repo_root: Path | None) -> DoctrineService:
    """Build an activation-aware DoctrineService rooted at built-in doctrine
    plus optional project overlay.

    The project-root candidate list (in priority order):
    1. ``.kittify/doctrine/``  — Phase 3 synthesis target (FR-009 / T024).
    2. ``src/charter/offering/``       — code-local built-in-layer path.
    3. ``doctrine/``           — flat fallback.

    Discovery is conditional on directory presence: legacy projects (pre-
    synthesis) that have none of these directories see ``project_root=None``
    and byte-identical behaviour to the pre-Phase-3 default (R-2 mitigation).

    WP03 (charter-sole-door-bypass-closure-01KZ3WAA, FR-002/T011): this used
    to construct a raw, unwrapped ``charter.offering.service.DoctrineService``
    directly -- one of the six original FR-002 violation sites. When
    *repo_root* is available, construction now routes through WP01's single
    unified builder, :func:`charter.activation.doctrine_service_builder.
    build_activation_aware_doctrine_service`, which resolves the identical
    ``project_root`` via this same :func:`resolve_project_root` call
    internally, so the R-2 legacy-candidate behaviour above is unchanged.
    This does add real charter-activation filtering (a `PackContext` sourced
    from ``.kittify/config.yaml`` under *repo_root*) plus the FR-008
    "fuller behaviour" axes (``active_languages`` always computed,
    ``org_roots`` always self-resolved) -- ``compile_charter`` already runs
    its own, separate ``config_roots`` activation derivation for the
    reference set (see that function's docstring); the two are independent
    and this duplication (paradigms/directives/tactics activation, NOT
    languages) is a documented WP01/FR-005 concern, not resolved here.

    The *``active_languages``* axis specifically -- previously ALSO an
    independent duplication (``compile_charter`` ran its own
    ``extract_declared_languages`` scan for the ``catalog.languages`` stamp
    while this builder separately called
    :func:`charter.activation.language_scope.infer_repo_languages` for the doctrine
    gate) -- is unified as of issue #3292: both now route through that one
    function, called here with no *interview* override (this builder has no
    in-memory interview; it reads the on-disk transcript, matching
    ``compile_charter``'s own disk-transcript fallback when no in-memory
    interview is supplied either). See :func:`infer_repo_languages`'s
    docstring for the resolution contract this closes.

    When *repo_root* is ``None`` (no config to source a `PackContext`
    from), the raw inner service is still wrapped with `pack_context=None`
    so no code outside ``charter.activation.resolver``/the unified builder constructs
    the raw service unwrapped (NFR-001) -- this preserves the exact
    pre-mission unfiltered behaviour for legacy repo-root-less callers.
    """
    if repo_root is not None:
        from charter.activation.doctrine_service_builder import (
            build_activation_aware_doctrine_service,
        )

        return build_activation_aware_doctrine_service(repo_root)

    from charter.activation.resolver import DoctrineService as _ActivationAwareDoctrineService
    from charter.offering.service import DoctrineService as _RawDoctrineService

    # No built_in_root kwarg: repositories self-resolve packs/built-in/<kind>
    # via the built_in_dir seam (default None is behaviour-preserving here;
    # WP04 drops the now-dead param from DoctrineService entirely).
    # resolve_doctrine_root() post-relocation points at the emptied src/doctrine tree.
    return _ActivationAwareDoctrineService(_RawDoctrineService(project_root=None))


def _build_references(
    *,
    mission: str,
    template_set: str,
    interview: CharterInterview,
    config_roots: ConfigActivatedRoots,
    doctrine_service: DoctrineService,
    repo_root: Path | None = None,
    diagnostics: list[str] | None = None,
) -> list[CharterReference]:
    doctrine_root = resolve_doctrine_root()

    references: list[CharterReference] = []
    references.append(_user_profile_reference(interview))
    references.extend(
        _build_references_from_service(
            mission=mission,
            template_set=template_set,
            config_roots=config_roots,
            doctrine_root=doctrine_root,
            doctrine_service=doctrine_service,
            repo_root=repo_root,
            diagnostics=diagnostics if diagnostics is not None else [],
        )
    )
    return references


def _raw_kind_repository(doctrine_service: DoctrineService, kind: str) -> Any:
    """Return the RAW, unfiltered repository for *kind* from *doctrine_service*.

    ``compile_charter`` accepts two concrete ``doctrine_service`` shapes in
    practice (only the first is the type its annotation names, but callers --
    including in-repo tests, e.g. ``tests/charter/test_activate_resolves_no_answers_edit.py``
    -- pass the second directly too):

    - the activation-aware wrapper (``charter.activation.resolver.DoctrineService``),
      whose nine gated properties (``.directives`` et al.) return an
      ACTIVATION-FILTERED dict -- so its dedicated ``raw_repository(kind)``
      accessor is used instead (#4785 Finding 4b: a DRG-transitively-reached
      id can legitimately fall outside that filtered subset);
    - a raw, unwrapped ``charter.offering.service.DoctrineService``, whose
      same-named properties are ALREADY the unfiltered repository object (no
      ``raw_repository`` method exists on it, nor is one needed).
    """
    raw_repository = getattr(doctrine_service, "raw_repository", None)
    if callable(raw_repository):
        return raw_repository(kind)
    return getattr(doctrine_service, kind)


def _render_kind_references(
    ids: list[str],
    *,
    kind: str,
    repository: Any,
    id_of: Callable[[Any], str],
    title_of: Callable[[Any], str],
    summary_of: Callable[[Any], str],
    diagnostics: list[str],
) -> list[CharterReference]:
    """Render one :class:`CharterReference` per id, via a typed repository lookup.

    Shared by every DRG-backed kind in :func:`_build_references_from_service`
    (directive, tactic, styleguide, toolguide, procedure, agent profile) so
    the six near-identical "look up, else record unresolved" loops collapse
    to one call site per kind.

    *repository* must be the RAW, unfiltered repository for *kind*
    (:func:`_raw_kind_repository`), not one of
    ``charter.activation.resolver.DoctrineService``'s nine activation-filtered
    properties. *ids* is the DRG transitive-closure result (``graph.<kind>``),
    which legitimately reaches ids beyond direct config activation (#4785
    Finding 4b) -- looking those up against the activation-filtered view
    produced false "no bundled definition" misses for ids that resolve fine
    against the raw repository. A miss against the raw repository IS a
    genuine unresolved reference: it is recorded into *diagnostics* using the
    same ``"Unresolved reference: <kind>/<id>"`` format
    :func:`_build_references_from_service`'s own ``graph.unresolved`` loop
    uses, rather than a silent placeholder ``CharterReference`` row (contract
    C4).
    """
    references: list[CharterReference] = []
    for raw_id in ids:
        model = repository.get(raw_id)
        if model is not None:
            references.append(
                _doctrine_model_reference(
                    kind=kind,
                    raw_id=id_of(model),
                    title=title_of(model),
                    summary=summary_of(model),
                )
            )
        else:
            diagnostics.append(f"Unresolved reference: {kind}/{raw_id}")
    return references


def _build_references_from_service(
    *,
    mission: str,
    template_set: str,
    config_roots: ConfigActivatedRoots,
    doctrine_root: Path,
    doctrine_service: DoctrineService,
    repo_root: Path | None,
    diagnostics: list[str],
) -> list[CharterReference]:
    """Load references via typed repository queries and DRG-backed transitive resolution."""
    references: list[CharterReference] = []

    # Paradigms: still loaded via YAML scanning (no typed paradigm references in graph).
    # Selection-only per the mission decision -- never DRG-reachable.
    paradigm_sources = _index_yaml_assets(built_in_dir(ArtifactKind.PARADIGM), "*.paradigm.yaml")
    for paradigm in config_roots.paradigms:
        references.append(
            _doctrine_yaml_reference(
                kind="paradigm",
                raw_id=paradigm,
                source=paradigm_sources.get(paradigm.casefold()),
                project_root=repo_root,
            )
        )

    # T026: tactics/styleguides/toolguides/procedures/agent profiles activated
    # directly in config.activated_* seed the transitive walk as additional
    # roots, unioned with the directive-closure result -- so an artefact with
    # no directive edge (e.g. the #2524 baseline danglers `aggregate-design-
    # rules` / `contextive`) still resolves.
    graph = _resolve_transitive_reference_graph(
        doctrine_root=doctrine_root,
        directives=config_roots.directives,
        direct_root_urns=_direct_root_urns(config_roots),
        repo_root=repo_root,
    )

    references.extend(
        _render_kind_references(
            graph.directives,
            kind="directive",
            repository=_raw_kind_repository(doctrine_service, "directives"),
            id_of=lambda d: str(d.id),
            title_of=lambda d: str(d.title),
            summary_of=lambda d: str(d.intent),
            diagnostics=diagnostics,
        )
    )
    references.extend(
        _render_kind_references(
            graph.tactics,
            kind="tactic",
            repository=_raw_kind_repository(doctrine_service, "tactics"),
            id_of=lambda t: str(t.id),
            title_of=lambda t: str(t.name),
            summary_of=lambda t: str(t.purpose or f"Tactic: {t.name}"),
            diagnostics=diagnostics,
        )
    )
    references.extend(
        _render_kind_references(
            graph.styleguides,
            kind="styleguide",
            repository=_raw_kind_repository(doctrine_service, "styleguides"),
            id_of=lambda sg: str(sg.id),
            title_of=lambda sg: str(sg.title),
            summary_of=lambda sg: str(sg.principles[0] if sg.principles else f"Styleguide: {sg.title}"),
            diagnostics=diagnostics,
        )
    )
    references.extend(
        _render_kind_references(
            graph.toolguides,
            kind="toolguide",
            repository=_raw_kind_repository(doctrine_service, "toolguides"),
            id_of=lambda tg: str(tg.id),
            title_of=lambda tg: str(tg.title),
            summary_of=lambda tg: str(tg.summary),
            diagnostics=diagnostics,
        )
    )
    references.extend(
        _render_kind_references(
            graph.procedures,
            kind="procedure",
            repository=_raw_kind_repository(doctrine_service, "procedures"),
            id_of=lambda proc: str(proc.id),
            title_of=lambda proc: str(proc.name),
            summary_of=lambda proc: str(proc.purpose),
            diagnostics=diagnostics,
        )
    )
    references.extend(
        _render_kind_references(
            graph.agent_profiles,
            kind="agent_profile",
            repository=_raw_kind_repository(doctrine_service, "agent_profiles"),
            id_of=lambda ap: str(ap.profile_id),
            title_of=lambda ap: str(ap.name),
            summary_of=lambda ap: str(ap.description or f"Agent profile: {ap.name}"),
            diagnostics=diagnostics,
        )
    )

    # Record unresolved refs in diagnostics
    for artifact_type, artifact_id in graph.unresolved:
        diagnostics.append(f"Unresolved reference: {artifact_type}/{artifact_id}")

    references.append(_template_reference(mission=mission, template_set=template_set))

    return references


def _resolve_transitive_reference_graph(
    *,
    doctrine_root: Path,
    directives: list[str],
    repo_root: Path | None,
    direct_root_urns: frozenset[str] = frozenset(),
    pack_context: Any = None,
) -> Any:
    """Resolve the transitive closure from built-in/project DRG layers.

    *directives* seed the closure as before. *direct_root_urns* (WP02 T026)
    are additional non-directive roots -- e.g. ``"styleguide:aggregate-
    design-rules"`` -- for kinds activated directly in
    ``config.activated_*`` with no directive edge reaching them; they are
    unioned into the same BFS start set so they (and anything they in turn
    require/suggest) resolve alongside the directive closure.
    """
    from charter.activation._drg_helpers import load_validated_graph
    from charter.activation.drg_activation import filter_graph_by_activation
    from charter.offering.drg.loader import load_built_in_graph
    from charter.offering.drg.models import Relation
    from charter.offering.drg.query import ResolveTransitiveRefsResult, resolve_transitive_refs
    from charter.offering.drg.validator import assert_valid

    start_urns = {f"directive:{directive_id}" for directive_id in directives} | set(direct_root_urns)
    if not start_urns:
        return ResolveTransitiveRefsResult()

    # Graph-load-failure fallback: no transitive resolution, but the direct
    # roots must still surface (bare ids, one bucket per kind) rather than
    # silently vanishing alongside the directive closure.
    fallback = ResolveTransitiveRefsResult(
        directives=sorted(directives),
        tactics=sorted(_bare_ids_for_kind(direct_root_urns, ArtifactKind.TACTIC)),
        styleguides=sorted(_bare_ids_for_kind(direct_root_urns, ArtifactKind.STYLEGUIDE)),
        toolguides=sorted(_bare_ids_for_kind(direct_root_urns, ArtifactKind.TOOLGUIDE)),
        procedures=sorted(_bare_ids_for_kind(direct_root_urns, ArtifactKind.PROCEDURE)),
        agent_profiles=sorted(_bare_ids_for_kind(direct_root_urns, ArtifactKind.AGENT_PROFILE)),
    )

    try:
        if repo_root is not None:
            merged = load_validated_graph(repo_root)
        else:
            if not doctrine_root.exists():
                return fallback
            merged = load_built_in_graph()
            assert_valid(merged)
    except Exception:
        return fallback

    # FR-032, FR-035 (WP08): apply activation filter after load, before resolution.
    if pack_context is not None:
        merged = filter_graph_by_activation(merged, pack_context)

    return resolve_transitive_refs(
        merged,
        start_urns=start_urns,
        relations={Relation.REQUIRES, Relation.SUGGESTS},
    )


def _build_built_in_concept_ids(references: list[CharterReference]) -> frozenset[str]:
    """Return a set of '<kind>:<id>' keys for built-in (non-local) references."""
    result: set[str] = set()
    for ref in references:
        if ref.kind != "local_support":
            result.add(ref.id.upper())
    return frozenset(result)


def _build_local_support_references(
    declarations: list[LocalSupportDeclaration],
    *,
    built_in_ids: frozenset[str],
    diagnostics: list[str],
) -> list[CharterReference]:
    """Build CharterReference entries for local support file declarations."""
    return [_build_local_support_reference(decl, built_in_ids=built_in_ids, diagnostics=diagnostics) for decl in declarations]


def _build_local_support_reference(
    decl: LocalSupportDeclaration,
    *,
    built_in_ids: frozenset[str],
    diagnostics: list[str],
) -> CharterReference:
    """Build one ``CharterReference`` for a single local-support declaration."""
    warning = _detect_local_support_overlap(decl, built_in_ids, diagnostics)
    title = Path(decl.path).name
    content = "\n".join(_local_support_content_lines(decl, title, warning))
    return CharterReference(
        id=f"LOCAL:{decl.path}",
        kind="local_support",
        title=title,
        summary=_local_support_summary(decl),
        source_path=decl.path,
        local_path=f"_LIBRARY/local-{_slugify(decl.path)}.md",
        content=content,
    )


def _detect_local_support_overlap(
    decl: LocalSupportDeclaration,
    built_in_ids: frozenset[str],
    diagnostics: list[str],
) -> str | None:
    """Return a warning (and record it in *diagnostics*) when *decl* shadows a built-in artifact."""
    if not (decl.target_kind and decl.target_id):
        return None
    overlap_key = f"{decl.target_kind.upper()}:{decl.target_id.upper()}"
    if overlap_key not in {k.upper() for k in built_in_ids}:
        return None
    warning = f"Local support file overlaps built-in {decl.target_kind} {decl.target_id}; built-in content remains primary."
    diagnostics.append(f"local_supporting_files '{decl.path}': {warning}")
    return warning


def _local_support_summary(decl: LocalSupportDeclaration) -> str:
    """Return the one-line human summary for a local-support reference."""
    summary_parts = ["Local support file"]
    if decl.target_kind and decl.target_id:
        summary_parts.append(f"supplements {decl.target_kind} {decl.target_id}")
    if decl.action:
        summary_parts.append(f"(action: {decl.action})")
    return "; ".join(summary_parts) + "."


def _local_support_content_lines(
    decl: LocalSupportDeclaration,
    title: str,
    warning: str | None,
) -> list[str]:
    """Build the free-form markdown content block for a local-support reference."""
    lines: list[str] = [f"# Local Support File: {title}", ""]
    lines.append(f"- Path: `{decl.path}`")
    if decl.action:
        lines.append(f"- Action scope: `{decl.action}`")
    if decl.target_kind:
        lines.append(f"- Target kind: `{decl.target_kind}`")
    if decl.target_id:
        lines.append(f"- Target ID: `{decl.target_id}`")
    lines.append("- Relationship: additive")
    if warning:
        lines.append(f"- Warning: {warning}")
    lines.append("")
    return lines


def _index_yaml_assets(directory: Path, pattern: str) -> dict[str, dict[str, object]]:
    """Index YAML assets in *directory* by ``id`` (or file stem fallback).

    *directory* is always a flat content dir (the ``built_in_dir(kind)``
    authority, or a caller-supplied flat directory in tests); the
    pre-relocation nested ``built-in/`` subdirectory dual-read for the emptied
    ``src/charter/offering/<kind>/`` pre-move shape was removed in mission
    doctrine-built-in-seam-consolidation-01KYW3TX (WP02).
    """
    index: dict[str, dict[str, object]] = {}
    if not directory.is_dir():
        return index

    for path in sorted(directory.glob(pattern)):
        loaded = _load_yaml_asset(path)
        raw_id = str(loaded.get("id", "")).strip() if isinstance(loaded, dict) else ""
        if not raw_id:
            raw_id = path.stem.split(".")[0]

        if raw_id:
            index[raw_id.casefold()] = loaded
    return index


def _load_yaml_asset(path: Path, *, unsafe: bool = False) -> dict[str, object]:
    """Load a YAML asset through the charter encoding chokepoint.

    Propagates :class:`CharterEncodingError` (a
    :class:`kernel.errors.KittyInternalConsistencyError`) to callers so the
    operator sees the actual failure mode rather than a silent empty parse.
    Truly-unrelated YAML errors (malformed structure on a successfully-decoded
    file) still degrade to an empty dict — that is the pre-existing resilience
    contract and is exercised by the regression test.

    Args:
        path: filesystem path of the YAML asset.
        unsafe: forwarded to :func:`load_charter_file`; when True an ambiguous
            encoding is bypassed using the highest-confidence decode candidate
            and ``bypass_used=True`` is recorded in provenance.
    """
    yaml = YAML(typ="safe")
    text = load_charter_file(path, unsafe=unsafe).text
    try:
        data = yaml.load(text) or {}
    except Exception:  # noqa: BLE001 — YAML parse failures degrade to empty
        # Pre-existing resilience contract: a syntactically-broken YAML file
        # whose encoding decoded cleanly produces an empty asset rather than
        # halting the whole compile. Encoding errors are NOT caught here —
        # they raise above in load_charter_file().
        data = {}

    if not isinstance(data, dict):
        data = {}

    data.setdefault("_source_path", str(path))
    return data


def _doctrine_model_reference(
    *,
    kind: str,
    raw_id: str,
    title: str,
    summary: str,
) -> CharterReference:
    """Build a CharterReference from typed repository model data."""
    local_slug = _slugify(raw_id)
    local_path = f"_LIBRARY/{kind}-{local_slug}.md"
    content = f"# {kind.title()}: {title}\n\n- ID: `{raw_id}`\n- Summary: {summary}\n"
    return CharterReference(
        id=f"{kind.upper()}:{raw_id}",
        kind=kind,
        title=title,
        summary=summary,
        source_path="",
        local_path=local_path,
        content=content,
    )


def _doctrine_yaml_reference(
    *,
    kind: str,
    raw_id: str,
    source: dict[str, object] | None,
    project_root: Path | None = None,
) -> CharterReference:
    """Build a CharterReference from a raw YAML asset (the CATALOG source caller).

    ``source_path`` is normalized through the shared portable-provenance seam
    (:func:`charter.offering.provenance.to_portable_source_path`, C-PRV-1/2/6): a
    built-in-pack path becomes a ``${SPEC_KITTY_PACKS_ROOT}/built-in/...``
    token, an in-tree path becomes repo-relative, and anything else stays
    absolute. This is one of exactly two normalizer call sites
    (contracts/provenance-and-channel.md C-PRV-6) -- the mission-template
    reference (:func:`_template_reference`) and the local-support declaration
    reference are deliberately excluded and keep using :func:`_trim_source_path`.
    """
    source = source or {"id": raw_id, "title": raw_id, "summary": "Definition unavailable in bundled doctrine."}

    source_path = str(source.get("_source_path", ""))
    display_path = to_portable_source_path(source_path, project_root=project_root)
    title = str(source.get("title") or source.get("name") or raw_id)
    summary = str(source.get("summary") or source.get("intent") or "No summary provided.")

    source_yaml = _dump_yaml(source)
    local_slug = _slugify(raw_id)
    local_path = f"_LIBRARY/{kind}-{local_slug}.md"

    content = (
        f"# {kind.title()}: {title}\n\n"
        f"- ID: `{raw_id}`\n"
        f"- Source: `{display_path or source_path or 'N/A'}`\n"
        f"- Summary: {summary}\n\n"
        "## Raw Definition\n\n"
        "```yaml\n"
        f"{source_yaml}```\n"
    )

    return CharterReference(
        id=f"{kind.upper()}:{raw_id}",
        kind=kind,
        title=title,
        summary=summary,
        source_path=display_path or source_path,
        local_path=local_path,
        content=content,
    )


def _template_reference(*, mission: str, template_set: str) -> CharterReference:
    """Build the mission template-set reference.

    Mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H``
    (FR-005) retired this function's former ``doctrine_root`` parameter: the
    primary arm (``repo._mission_config_path``) is the one actually read below
    via ``get_mission_config``, correctly resolved through the FR-004 kernel
    primitive regardless of the mission's relocation. The display-only
    fallback (used when a mission's ``mission.yaml`` genuinely doesn't exist)
    now uses ``repo._missions_root`` -- the same promoted authority -- rather
    than a stale ``doctrine_root / "missions"`` literal naming the
    pre-relocation location.
    """
    from charter.offering.missions import MissionTemplateRepository

    repo = MissionTemplateRepository.default()
    config = repo.get_mission_config(mission)
    mission_path = repo._mission_config_path(mission) or (repo._missions_root / mission / "mission.yaml")
    raw_parsed = config.parsed if config is not None else {"name": mission}
    source: dict[str, object] = {str(key): value for key, value in raw_parsed.items()} if isinstance(raw_parsed, dict) else {"name": mission}

    summary = str(source.get("description") or f"Mission template set for {mission}.")
    content = (
        f"# Template Set: {template_set}\n\n"
        f"- Mission: `{mission}`\n"
        f"- Source: `{_trim_source_path(str(mission_path))}`\n"
        f"- Summary: {summary}\n\n"
        "## Mission Definition\n\n"
        "```yaml\n"
        f"{_dump_yaml(source)}```\n"
    )

    return CharterReference(
        id=f"TEMPLATE_SET:{template_set}",
        kind="template_set",
        title=template_set,
        summary=summary,
        source_path=_trim_source_path(str(mission_path)),
        local_path=f"_LIBRARY/template-set-{_slugify(template_set)}.md",
        content=content,
    )


def _user_profile_reference(interview: CharterInterview) -> CharterReference:
    lines: list[str] = ["# User Project Profile", ""]
    lines.append(f"- Mission: `{interview.mission}`")
    lines.append(f"- Interview profile: `{interview.profile}`")
    if interview.agent_profile:
        lines.append(f"- Agent profile: `{interview.agent_profile}`")
    if interview.agent_role:
        lines.append(f"- Agent role: `{interview.agent_role}`")
    lines.append("")
    lines.append("## Interview Answers")
    lines.append("")

    for key, value in interview.answers.items():
        label = key.replace("_", " ").strip().title()
        lines.append(f"- **{label}**: {value}")

    lines.append("")
    lines.append("## Selected Doctrine")
    lines.append("")
    lines.append(f"- Paradigms: {', '.join(interview.selected_paradigms) or '(none)'}")
    lines.append(f"- Directives: {', '.join(interview.selected_directives) or '(none)'}")
    lines.append(f"- Tools: {', '.join(interview.available_tools) or '(none)'}")
    lines.append("")

    return CharterReference(
        id="USER:PROJECT_PROFILE",
        kind="user_profile",
        title="User Project Profile",
        summary="Project-specific interview answers captured for charter compilation.",
        source_path=".kittify/charter/interview/answers.yaml",
        local_path="_LIBRARY/user-project-profile.md",
        content="\n".join(lines) + "\n",
    )


def _render_charter_markdown(
    *,
    mission: str,
    template_set: str,
    interview: CharterInterview,
    selected_paradigms: list[str],
    selected_directives: list[str],
    available_tools: list[str],
    references: list[CharterReference],
    doctrine_service: DoctrineService,
    selected_tactics: list[str] | None = None,
) -> str:
    selected_tactics = selected_tactics or []
    now = now_utc_stamp()

    testing = interview.answers.get(
        "testing_requirements",
        "Use the project's declared testing approach, or mark it as NEEDS CLARIFICATION.",
    )
    quality = interview.answers.get("quality_gates", "Tests, lint, and type checks must pass before merge.")
    performance = interview.answers.get("performance_targets", "No explicit performance policy provided.")
    deployment = interview.answers.get("deployment_constraints", "No deployment constraints provided.")
    review_policy = interview.answers.get("review_policy", "At least one reviewer validates changes.")

    policy_summary_lines = [
        f"- Intent: {interview.answers.get('project_intent', 'Not specified.')}",
        f"- Languages/Frameworks: {interview.answers.get('languages_frameworks', 'Not specified.')}",
        f"- Testing: {testing}",
        f"- Quality Gates: {quality}",
        f"- Review Policy: {review_policy}",
        f"- Performance Targets: {performance}",
        f"- Deployment Constraints: {deployment}",
    ]

    numbered_directives = _render_directives(interview, selected_directives, doctrine_service)

    reference_rows = ["| Reference ID | Kind | Summary | Local Doc |", "|---|---|---|---|"]
    for reference in references:
        reference_rows.append(f"| `{reference.id}` | {reference.kind} | {reference.summary} | `{reference.local_path}` |")

    activation_lines = [f"mission: {mission}"]
    if interview.agent_profile:
        activation_lines.append(f"agent_profile: {interview.agent_profile}")
    if interview.agent_role:
        activation_lines.append(f"agent_role: {interview.agent_role}")
    activation_lines.extend(
        [
            f"selected_paradigms: {_yaml_inline_list(selected_paradigms)}",
            f"selected_directives: {_yaml_inline_list(selected_directives)}",
            f"selected_tactics: {_yaml_inline_list(selected_tactics)}",
            f"available_tools: {_yaml_inline_list(available_tools)}",
            f"template_set: {template_set}",
        ]
    )

    amendment = interview.answers.get("amendment_process", "Amendments are proposed by PR and reviewed before adoption.")
    exception_policy = interview.answers.get("exception_policy", "Exceptions must include rationale and expiration criteria.")
    return (
        "# Project Charter\n\n"
        "<!-- Generated by `spec-kitty charter generate` -->\n\n"
        f"Generated: {now}\n\n"
        "## Testing Standards\n\n"
        f"- {testing}\n\n"
        "## Quality Gates\n\n"
        f"- {quality}\n\n"
        "## Performance Benchmarks\n\n"
        f"- {performance}\n\n"
        "## Branch Strategy\n\n"
        f"- {review_policy}\n"
        f"- Deployment constraints: {deployment}\n\n"
        "## Governance Activation\n\n"
        "```yaml\n" + "\n".join(activation_lines) + "\n"
        "```\n\n"
        "## Policy Summary\n\n" + "\n".join(policy_summary_lines) + "\n\n"
        "## Project Directives\n\n" + numbered_directives + "\n\n"
        "## Reference Index\n\n" + "\n".join(reference_rows) + "\n\n"
        "## Amendment Process\n\n"
        f"{amendment}\n\n"
        "## Exception Policy\n\n"
        f"{exception_policy}\n"
    )


def _render_directives(
    interview: CharterInterview,
    selected_directives: list[str],
    doctrine_service: DoctrineService,
) -> str:
    lines: list[str] = []
    index = 1

    for directive_id in selected_directives:
        directive = doctrine_service.directives.get(directive_id)
        if directive is None:
            lines.append(f"{index}. Apply doctrine directive `{directive_id}` to planning and implementation decisions.")
            index += 1
            continue

        lines.append(f"{index}. {directive.title} (`{directive.id}`): {directive.intent.strip()}")
        if directive.scope:
            lines.append(f"   - Scope: {directive.scope.strip()}")
        for procedure in directive.procedures:
            lines.append(f"   - Procedure: {procedure}")
        for rule in directive.integrity_rules:
            lines.append(f"   - Integrity rule: {rule}")
        for criterion in directive.validation_criteria:
            lines.append(f"   - Validation criterion: {criterion}")
        index += 1

    risk = interview.answers.get("risk_boundaries")
    if risk:
        lines.append(f"{index}. Respect risk boundaries: {risk}")
        index += 1

    docs = interview.answers.get("documentation_policy")
    if docs:
        lines.append(f"{index}. Keep documentation synchronized with workflow and behavior changes: {docs}")
        index += 1

    if not lines:
        lines.append("1. Keep specification, plan, tasks, implementation, and review artifacts consistent.")

    return "\n".join(lines)


def _dump_yaml(data: dict[str, object]) -> str:
    cleaned = {k: v for k, v in data.items() if k != "_source_path"}
    yaml = YAML()
    yaml.default_flow_style = False
    buffer = StringIO()
    yaml.dump(cleaned, buffer)
    return buffer.getvalue()


def _trim_source_path(source_path: str) -> str:
    if not source_path:
        return ""
    marker = "src/charter/offering/"
    if marker in source_path:
        return source_path[source_path.index(marker) :]
    return source_path


def _yaml_inline_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(values) + "]"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"
