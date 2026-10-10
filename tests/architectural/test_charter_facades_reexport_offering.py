"""Architectural guard — charter facades re-export charter.offering symbols by identity.

Each facade module under ``src/charter/`` that exists to proxy a doctrine
surface MUST re-export the exact doctrine object (object identity), not a
custom wrapper. This prevents a future PR from silently replacing a
re-export with a sneaky shim that drifts from charter.offering.

Mission: ``charter-mediated-doctrine-selection-01KRTZCA``.
Contract: ``kitty-specs/charter-mediated-doctrine-selection-01KRTZCA/contracts/charter-facade-modules.md``.

The table below mirrors the contract's "Symbol tables" section. When a
facade gains a new re-export, add the (symbol, doctrine-module) tuple here.
The parametrised test then asserts (a) the symbol exists on both modules
and (b) ``facade.SYMBOL is charter.offering.SYMBOL`` (object identity).
"""

from __future__ import annotations

import functools
import importlib
import pathlib
import sys
import types

import pytest

pytestmark = pytest.mark.architectural


# Mapping: charter facade module -> list of (symbol, doctrine source module).
# Keep in sync with contracts/charter-facade-modules.md "Symbol tables".
_FACADE_TABLE: dict[str, list[tuple[str, str]]] = {
    "charter.profiles": [
        ("AgentProfile", "charter.offering.agent_profiles.profile"),
        ("Role", "charter.offering.agent_profiles.profile"),
        ("AgentProfileRepository", "charter.offering.agent_profiles.repository"),
        ("DEFAULT_ROLE_CAPABILITIES", "charter.offering.agent_profiles.capabilities"),
        # Tabled during the #3321 landing squad (inverse-containment hardening,
        # below): advertised in ``__all__`` but previously identity-unchecked.
        ("SkippedProfile", "charter.offering.agent_profiles.diagnostics"),
    ],
    "charter.mission_steps": [
        # MissionStep retired from the facade contract 2026-06-11: the last src/
        # consumer was correctly retyped to MissionStepContractStep (executor.py);
        # the symbol remains an explicit PEP 484 re-export for direct importers.
        # See contracts/charter-facade-modules.md addendum.
        #
        # MissionStepRepository retired from this facade's contract 2026-08-14:
        # WP02 of mission ``up-mission-type-seam-01KZY1JB`` deleted
        # ``resolve_mission_steps`` (src/charter/activation/resolver.py), which was the
        # only src/ importer reached through *this* facade; the symbol remains
        # an explicit PEP 484 re-export for direct importers and is still
        # identity-checked (with a live src/ importer) via the
        # ``charter.missions`` facade table entry below.
        ("MissionStepContract", "charter.offering.missions.step_contracts"),
        ("MissionStepInput", "charter.offering.missions.step_contracts"),
        ("MissionStepContractRepository", "charter.offering.missions.step_contracts"),
        ("MissionStepContractStep", "charter.offering.missions.step_contracts"),
        # Widened by mission ``doctrine-public-api-surface-01KZPDSR`` WP03
        # (T011): the gate-binding model on a mission-step contract. FACADE-ONLY.
        ("GateBinding", "charter.offering.missions.step_contracts"),
    ],
    "charter.drg": [
        # PUBLIC: re-exported from the curated public surface ``charter.offering.api``
        # (WP03/T010) so the wheel symbol gains a live in-repo caller. Identity
        # holds: ``charter.offering.api.ArtifactKind is charter.offering.artifact_kinds.ArtifactKind``.
        ("ArtifactKind", "charter.offering.api"),
        # CORE_KIND_PLURALS re-export retired with ArtifactKind.core (#5824).
        ("EndpointResolutionError", "charter.offering.drg.merge"),
        ("resolve_edge_endpoint", "charter.offering.drg.merge"),
        ("dangling_endpoints", "charter.offering.drg.validator"),
        ("EndpointEdge", "charter.offering.drg.validator"),
        ("EndpointGraph", "charter.offering.drg.validator"),
        ("DRGEdge", "charter.offering.drg.models"),
        ("DRGGraph", "charter.offering.drg.models"),
        ("DRGNode", "charter.offering.drg.models"),
        ("NodeKind", "charter.offering.drg.models"),
        # Tabled by #3732 WP25 when the inverse gate started keying on charter.offering.
        ("scan_project_artifacts", "charter.offering.drg.project_scan"),
        ("slug_for", "charter.offering.artifact_kinds"),
        ("Relation", "charter.offering.drg.models"),
        ("load_graph", "charter.offering.drg"),
        ("merge_layers", "charter.offering.drg"),
        ("resolve_context", "charter.offering.drg.query"),
        ("ResolvedContext", "charter.offering.drg.query"),
        # Added by mission ``doctrine-silence-guards-01KYFV7Q`` WP08. The
        # post-merge completeness check that every runtime caller merging the
        # COMPLETE graph must run; sourced from the ``charter.offering.drg`` package
        # surface (not ``charter.offering.drg.validator``) so the package's ``__all__``
        # entry has a real ``src/`` importer instead of being a dead export.
        ("validate_dangling_references", "charter.offering.drg"),
        # Widened by mission ``doctrine-public-api-surface-01KZPDSR`` WP03
        # (T010): the DRG error hierarchy + org-root resolution + org-DRG
        # conflict absorb the ``drg.*`` reach-through cluster. All FACADE-ONLY.
        ("DRGLoadError", "charter.offering.drg"),
        ("DRGValidationError", "charter.offering.drg"),
        ("OrgDRGConflict", "charter.offering.drg.merge"),
        ("resolve_org_roots", "charter.offering.drg.org_pack_config"),
        # Added alongside ``resolve_org_roots`` above: closes the direct
        # ``specify_cli``/``runtime`` -> ``doctrine`` reach-through that
        # ``tests/architectural/test_runtime_charter_doctrine_boundary.py``
        # forbids. Same source module, same identity-reexport shape.
        ("resolve_org_dirs", "charter.offering.drg.org_pack_config"),
        # Added by the #3520 chain fold (#3525): the multi-org-pack DRG merge
        # gave `specify_cli`/`runtime` runtime callers (executor, gate_bindings)
        # a top-level need for the org-root-chain resolver and the graph loader.
        # Re-exported here — same identity-reexport shape — so those callers reach
        # doctrine through this facade rather than a lazy `doctrine.*` import that
        # `test_runtime_charter_doctrine_boundary.py` forbids.
        ("resolve_existing_org_roots", "charter.offering.drg.org_pack_config"),
        ("load_graph_or_dir", "charter.offering.drg.loader"),
        # ``charter.offering.base`` census-drift door (WP01 FACADE-ONLY): the
        # layer-collision warning belongs on the layer-merge facade beside
        # ``merge_layers`` / ``merge_three_layers``. Consumer is WP05-owned.
        ("ArtifactLayerCollisionWarning", "charter.offering.base"),
        # Tabled during the #3321 landing squad (inverse-containment hardening,
        # below). These 10 were advertised in ``charter.drg.__all__`` yet absent
        # from this table, so they were public but identity-unchecked — a
        # wrapper/shim could have replaced any of them with the gate staying
        # green. All FACADE-ONLY; identity verified live at add time.
        ("OrgDRGConflictError", "charter.offering.drg.merge"),
        ("OrgDRGFragment", "charter.offering.drg.org_pack_loader"),
        ("OrgPackEnvVarUnsetError", "charter.offering.drg.org_pack_config"),
        ("OrgPackMissingError", "charter.offering.drg.org_pack_loader"),
        # Added by mission ``doctrine-drg-silent-drop-boundary`` (#3530 landing):
        # the executor's org-pack error handling and loader reach the offering
        # layer only through ``charter.drg``, so these re-exports join the
        # identity contract. All FACADE-ONLY; identity verified live.
        ("OrgPackParseError", "charter.offering.drg.org_pack_loader"),
        ("OrgPackSchemaError", "charter.offering.drg.org_pack_loader"),
        ("load_org_pack", "charter.offering.drg.org_pack_loader"),
        ("OrgPackSubdirEscapeError", "charter.offering.drg.org_pack_config"),
        ("UnknownRelationError", "charter.offering.drg.merge"),
        ("graph_document_to_dict", "charter.offering.drg.migration.extractor"),
        ("load_built_in_graph", "charter.offering.drg.loader"),
        ("merge_three_layers", "charter.offering.drg.merge"),
        ("model_to_graph_dict", "charter.offering.drg.migration.extractor"),
        # Surfaced by the #5836 non-class re-export gate enhancement (WP01): a
        # ``frozenset`` constant advertised in ``charter.drg.__all__`` that the old
        # ``__module__``-only origin resolution silently skipped. Identity-verified
        # live at add time. FACADE-ONLY.
        ("FIELDS_WITHHELD_FROM_GRAPH_OUTPUT", "charter.offering.drg.migration.extractor"),
        # Promoted from a private doctrine helper during the #3321 landing (the
        # post-fold squad flagged charter surfacing ``charter.offering.drg.merge``'s
        # private ``_bridge_org_edge_to_drg_edge``). It is now a public symbol in
        # ``charter.offering.drg.merge.__all__`` with a live runtime consumer
        # (``specify_cli.drg_writers.registry``), so it is a plain re-export.
        ("bridge_org_edge_to_drg_edge", "charter.offering.drg.merge"),
        # Added by mission ``charter-pack-cutover-01M491G6`` WP04 (#3732, research
        # A.3 #7): the charter-pack adapters (``api_source``, ``snapshot``) reach
        # the offering tier only through this facade once the
        # ``specify_cli/doctrine`` boundary exemption is deleted. FACADE-ONLY.
        ("resolve_relative_path_within_root", "charter.offering.drg.org_pack_config"),
        # Added by WP05 (#3732): ``specify_cli.charter_packs.snapshot`` types its
        # fetch entry against the org pack config through this facade once
        # ``specify_cli.doctrine.config``'s alias re-exports are deleted (C-001).
        ("OrgPackConfig", "charter.offering.drg.org_pack_config"),
    ],
    # New door (WP03/T012): mission-template / mission-type / mission-step
    # repository surfaces. All FACADE-ONLY per the WP01 census.
    "charter.missions": [
        ("MissionsRootNotFound", "charter.offering.missions.repository"),
        ("MissionTemplateRepository", "charter.offering.missions.repository"),
        ("MissionTypeRepository", "charter.offering.missions.mission_type_repository"),
        ("builtin_mission_type_ids", "charter.offering.missions.mission_type_repository"),
        ("project_template_set", "charter.offering.missions.step_projection"),
        ("MissionStepRepository", "charter.offering.missions.mission_step_repository"),
        # Added by mission ``rc3-charter-gate-predicate-inversion-01M0GGT1`` (M3,
        # #3599): the artifact-filename seam relocated the expected-artifact
        # manifest into doctrine (C-001) and specify_cli reaches it through this
        # facade (runtime -> charter -> doctrine, test_runtime_charter_doctrine_boundary).
        ("ArtifactClassEnum", "charter.offering.missions.expected_artifact_manifest"),
        ("ExpectedArtifactManifest", "charter.offering.missions.expected_artifact_manifest"),
        ("ExpectedArtifactSpec", "charter.offering.missions.expected_artifact_manifest"),
        ("project_artifact_name_set", "charter.offering.missions.step_projection"),
        # Added by mission ``up-mission-type-seam-01KZY1JB`` WP07 (FR-006):
        # the CLI layer (``specify_cli.cli.commands.charter.mission_type``)
        # needs direct reach to the FR-001 layered factory to report a real
        # per-id ``source_layer``, not just an activation-scoped action
        # sequence -- ``specify_cli`` may only reach a FACADE-ONLY doctrine
        # module (``tests/architectural/test_doctrine_census.py``'s
        # disposition for ``charter.offering.missions.mission_type_repository``)
        # through a charter door, so this door is widened rather than a new
        # direct ``doctrine.*`` import added to a CLI command file.
        ("resolve_layered_mission_types", "charter.offering.missions.mission_type_repository"),
        # Added by mission ``expected-artifacts-loader-unification-01M1C9VQ``
        # WP01 (#3770): the relocated ``charter.activation.manifest_loader``
        # loader authority's sibling error moved back through this
        # already-established door so ``specify_cli.dossier.manifest``'s shim
        # re-export reaches it without a direct ``charter.offering.*`` import
        # (test_runtime_charter_doctrine_boundary.py forbids that).
        ("MalformedManifestError", "charter.offering.missions.repository"),
    ],
    # New door (WP03/T013): symbol-level model→task routing surface. PUBLIC —
    # re-exported from ``charter.offering.api`` (leaf callables/types only, NOT the
    # ``.loader`` / ``.evaluator`` submodules). Identity holds transitively:
    # ``charter.model_routing.load is charter.offering.api.load is
    # charter.offering.model_task_routing.loader.load``.
    "charter.model_routing": [
        ("CatalogLoadResult", "charter.offering.api"),
        ("RoutingRecommendation", "charter.offering.api"),
        ("evaluate", "charter.offering.api"),
        ("load", "charter.offering.api"),
    ],
    # New door (WP03/T014): asset-resolution surface. PUBLIC — re-exported from
    # ``charter.offering.api`` so the wheel symbols gain live in-repo callers.
    "charter.assets": [
        ("AssetManifest", "charter.offering.api"),
        ("AssetNotFoundError", "charter.offering.api"),
        ("AssetPathEscapeError", "charter.offering.api"),
        ("AssetRepository", "charter.offering.api"),
        ("AssetResolutionError", "charter.offering.api"),
    ],
    # New narrow doors (WP03/T015). All FACADE-ONLY per the WP01 census.
    "charter.glossary_packs": [
        ("GlossaryPack", "charter.offering.glossary_packs"),
    ],
    "charter.spdd_reasons": [
        ("apply_spdd_blocks_for_project", "charter.offering.spdd_reasons"),
    ],
    "charter.pack_paths": [
        ("PackRootNotFound", "charter.offering.pack_paths"),
        ("built_in_dir", "charter.offering.pack_paths"),
        ("built_in_root", "charter.offering.pack_paths"),
    ],
    # Added by mission ``operator-config-ergonomics`` (portable provenance):
    # the runtime provenance-normalizer reach-through routes through this
    # facade exactly like ``charter.pack_paths`` above, closing the direct
    # ``specify_cli``/``runtime`` -> ``charter.offering.provenance`` import that
    # ``test_runtime_charter_doctrine_boundary.py`` forbids. Same source
    # module, same identity-reexport shape. FACADE-ONLY.
    # New door (mission ``charter-pack-cutover-01M491G6`` WP04, #3732, FR-010 /
    # OD-9): the charter pack model and tooling moved from ``specify_cli.doctrine``
    # to ``charter.offering.packs``; ``specify_cli`` reaches it only through this
    # facade (research A.3 #8). FACADE-ONLY. WP05 dropped ``ValidationResult``
    # (no ``specify_cli`` caller once ``org_charter`` imports offering directly)
    # and added the two org-charter composing entries, which originate in
    # ``charter.activation.org_charter`` and so are not tabled here.
    "charter.packs": [
        ("RECOGNISED_ARTIFACT_DIRS", "charter.offering.packs.pack_manifest"),
        ("builtin_manifest_is_fresh", "charter.offering.packs.builtin_manifest"),
        ("count_snapshot_artifacts", "charter.offering.packs.pack_manifest"),
        ("generate_builtin_manifest", "charter.offering.packs.builtin_manifest"),
        ("safe_urlsplit", "charter.offering.packs.pack_manifest"),
        ("snapshot_sha256", "charter.offering.packs.pack_manifest"),
        ("source_fingerprint", "charter.offering.packs.pack_manifest"),
        ("strip_source_credentials", "charter.offering.packs.pack_manifest"),
        ("write_pack_manifest", "charter.offering.packs.pack_manifest"),
        ("AssemblyResult", "charter.offering.packs.pack_assembler"),
        ("assemble_pack", "charter.offering.packs.pack_assembler"),
        ("pack_document_dict", "charter.offering.packs.pack_assembler"),
        ("render_assembly_result", "charter.offering.packs.pack_assembler"),
        ("ValidationIssue", "charter.offering.packs.pack_validator"),
        ("artifact_schema_registry", "charter.offering.packs.pack_validator"),
        ("render_validation_result", "charter.offering.packs.pack_validator"),
        ("validate_pack", "charter.offering.packs.pack_validator"),
        # Presets and offering packs (FR-019), and the retired-field refusal (#3732);
        # tabled by WP25 when the inverse gate started keying on charter.offering.
        ("ActivationPreset", "charter.offering.packs.presets"),
        ("OfferingPack", "charter.offering.packs.presets"),
        ("PresetFormatError", "charter.offering.packs.presets"),
        ("PresetNotFoundError", "charter.offering.packs.presets"),
        ("discover_presets", "charter.offering.packs.presets"),
        ("list_offering_packs", "charter.offering.packs.presets"),
        ("load_preset", "charter.offering.packs.presets"),
        ("load_preset_file", "charter.offering.packs.presets"),
        ("preset_activation_keys", "charter.offering.packs.presets"),
        ("render_example_preset", "charter.offering.packs.presets"),
        ("write_example_preset", "charter.offering.packs.presets"),
        ("RetiredPackFieldError", "charter.offering.packs.retired_fields"),
        # Surfaced by the #5836 non-class re-export gate enhancement (WP01): a
        # ``str`` constant advertised in ``charter.packs.__all__`` that the old
        # ``__module__``-only origin resolution silently skipped. Identity-verified
        # live at add time. FACADE-ONLY.
        ("RETIRED_PACK_FIELD", "charter.offering.packs.pack_validator"),
    ],
    "charter.provenance": [
        ("is_built_in_pack_path", "charter.offering.provenance"),
        ("to_portable_source_path", "charter.offering.provenance"),
    ],
    # Widened by WP03/T015: ``resolve_template_by_id`` (WP01 found it missing;
    # ``runtime/resolver.py`` needs it in WP07/T036). FACADE-ONLY.
    "charter.template_catalog": [
        ("discover_templates", "charter.offering.template_catalog"),
        ("TemplateRef", "charter.offering.template_catalog"),
        ("TierRoot", "charter.offering.template_catalog"),
        ("resolve_template_by_id", "charter.offering.template_catalog"),
    ],
    "charter.primitives": [
        ("PrimitiveExecutionContext", "charter.offering.missions"),
        ("execute_with_glossary", "charter.offering.missions"),
    ],
    "charter.resolution": [
        ("ResolutionResult", "charter.offering.resolver"),
        ("ResolutionTier", "charter.offering.resolver"),
    ],
    "charter.versioning": [
        ("BundleCompatibilityStatus", "charter.offering.versioning"),
        ("CURRENT_BUNDLE_SCHEMA_VERSION", "charter.offering.versioning"),
        ("check_bundle_compatibility", "charter.offering.versioning"),
        ("get_bundle_schema_version", "charter.offering.versioning"),
        ("run_migration", "charter.offering.versioning"),
        # Tabled during the #3321 landing squad (inverse-containment hardening):
        # advertised in ``__all__`` but previously identity-unchecked.
        ("repair_v2_synthesis_manifest_defaults", "charter.offering.versioning"),
    ],
    # Not a pure "facade" (it carries local ``from_operator_token`` /
    # ``resolve_artifact_urn`` logic), but it DOES re-export two doctrine symbols
    # in ``__all__``. Tabled during the #3321 post-fold squad: the self-discovery
    # inverse gate below found these public but identity-unchecked (they escaped
    # the earlier key-scoped gate because this module was absent from the table).
    "charter.activation.kind_vocabulary": [
        ("ArtifactKind", "charter.offering.artifact_kinds"),
        ("MissionTypeNotAnArtifactKind", "charter.offering.artifact_kinds"),
    ],
}

#: Module prefixes whose re-exports through a charter ``__all__`` MUST carry an
#: identity contract: ``charter.offering`` (the offering surface the facades proxy)
#: plus the external shared-contract packages (per the Shared Package Boundary). A
#: charter-local definition (any other ``charter.*`` module) is not a re-export; a
#: stdlib value instance such as a ``pathlib.Path`` constant is not one either —
#: both are correctly excluded by keying on these origins rather than on "not
#: charter". (Until #3732 WP25 this keyed on the top-level package ``doctrine``,
#: which no longer exists, so no offering re-export was ever checked.)
_IDENTITY_REQUIRED_ORIGINS = frozenset({"charter.offering", "spec_kitty_events", "spec_kitty_tracker"})

_CHARTER_SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "charter"


def _charter_modules() -> list[str]:
    """Self-discover every top-level ``charter.*`` module from ``src/charter/``.

    The inverse-containment gate iterates THIS, not ``_FACADE_TABLE.keys()``, so a
    re-export module simply never added to the table (e.g. ``charter.activation.kind_vocabulary``,
    caught by the #3321 post-fold squad) cannot hide from the check.
    """
    return [f"charter.{path.stem}" for path in sorted(_CHARTER_SRC.glob("*.py")) if path.stem != "__init__"]


def _flat_cases() -> list[tuple[str, str, str]]:
    """Flatten the facade table into a list of (facade, symbol, offering) tuples."""
    return [(facade, symbol, offering) for facade, items in _FACADE_TABLE.items() for symbol, offering in items]


@pytest.mark.parametrize(
    ("facade_module", "symbol", "offering_module"),
    _flat_cases(),
    ids=[f"{facade}.{symbol}" for facade, symbol, _ in _flat_cases()],
)
def test_facade_reexports_offering_symbol_by_identity(facade_module: str, symbol: str, offering_module: str) -> None:
    """Each facade symbol MUST be the same object as its offering source.

    Identity (``is``) — not equality (``==``) — is the invariant. A facade
    that wraps, aliases, or copies an offering symbol is a contract violation.
    """
    facade = importlib.import_module(facade_module)
    offering = importlib.import_module(offering_module)
    facade_obj = getattr(facade, symbol)
    offering_obj = getattr(offering, symbol)
    assert facade_obj is offering_obj, (
        f"{facade_module}.{symbol} must be the same object as "
        f"{offering_module}.{symbol}. Facade modules are pure re-exports — "
        "no wrappers, no aliases, no shims. "
        f"Got facade={facade_obj!r}, offering={offering_obj!r}."
    )


@pytest.mark.parametrize("facade_module", sorted(_FACADE_TABLE.keys()))
def test_facade_all_lists_every_reexport(facade_module: str) -> None:
    """Every contract symbol MUST appear in the facade's ``__all__``.

    This catches the case where a future edit imports a new doctrine symbol
    into a facade but forgets to advertise it in ``__all__``, which would
    silently break ``from charter.<facade> import *`` callers and leave the
    public surface ambiguous.
    """
    facade = importlib.import_module(facade_module)
    all_ = getattr(facade, "__all__", None)
    assert all_ is not None, f"{facade_module} must define __all__"
    expected_symbols = {symbol for symbol, _ in _FACADE_TABLE[facade_module]}
    missing = expected_symbols - set(all_)
    assert not missing, f"{facade_module}.__all__ is missing contract symbols: {sorted(missing)}. Add them to __all__ or update the contract table."


def _requires_identity(origin: str) -> bool:
    return any(origin == prefix or origin.startswith(f"{prefix}.") for prefix in _IDENTITY_REQUIRED_ORIGINS)


def _origin_by_identity(obj: object) -> str | None:
    """Resolve the origin module of a plain value by identity-scanning the identity-required modules.

    A plain value (``tuple`` / ``frozenset``) carries no usable ``__module__``, so its
    ``__module__``-based origin is ``None`` and the fast path below skips it — which previously
    let a non-class ``charter.offering`` constant be re-exported through a charter ``__all__``
    without an identity contract. Scan the already-imported :data:`_IDENTITY_REQUIRED_ORIGINS`
    modules (and their submodules) in ``sys.modules`` for an attribute that ``is`` ``obj`` and
    report the first such module. Identity (``is``), never equality, so two equal-but-distinct
    values are not conflated. The scan is confined to the identity-required origins — never a
    broad ``sys.modules`` walk.
    """
    for name in sorted(sys.modules):
        if not _requires_identity(name):
            continue
        module = sys.modules[name]
        if module is None:
            continue
        try:
            attrs = list(vars(module).values())
        except TypeError:
            continue
        if any(attr is obj for attr in attrs):
            return name
    return None


def _untabled_reexports(facade: types.ModuleType, covered: set[str]) -> list[tuple[str, str]]:
    """``(name, origin)`` for every ``__all__`` symbol that needs an identity contract and has none."""
    untabled: list[tuple[str, str]] = []
    for name in getattr(facade, "__all__", None) or []:
        obj = getattr(facade, name, None)
        # Fast path: classes/functions carry a usable ``__module__``.
        origin = getattr(obj, "__module__", None)
        if not origin and obj is not None:
            # Plain value (no ``__module__``): resolve origin by identity instead.
            origin = _origin_by_identity(obj)
        if origin and _requires_identity(origin) and name not in covered:
            untabled.append((name, origin))
    return untabled


def test_planted_non_identical_offering_reexport_is_reported() -> None:
    """Self-test: a wrapper of a ``charter.offering`` function advertised in ``__all__`` is reported.

    ``functools.wraps`` copies ``__module__``, so the wrapper looks like a re-export of
    ``charter.offering.artifact_kinds`` while not being the same object. A charter-local
    definition next to it is not reported.
    """
    from charter.offering import artifact_kinds

    def local() -> None:
        """A charter-local definition."""

    planted = types.ModuleType("charter.planted_facade")
    wrapper = functools.wraps(artifact_kinds.slug_for)(lambda *a, **k: artifact_kinds.slug_for(*a, **k))
    local.__module__ = planted.__name__
    vars(planted).update(slug_for=wrapper, local=local, __all__=["slug_for", "local"])
    assert wrapper is not artifact_kinds.slug_for
    assert _untabled_reexports(planted, set()) == [("slug_for", "charter.offering.artifact_kinds")]
    assert _untabled_reexports(planted, {"slug_for"}) == []


def test_planted_non_class_offering_reexport_is_reported() -> None:
    """Self-test: a non-class ``charter.offering`` constant advertised in ``__all__`` is reported.

    A plain value (``tuple`` / ``frozenset``) carries no usable ``__module__``, so the
    ``__module__``-only resolution silently skipped it — a doctrine-origin constant could
    be re-exported through a charter ``__all__`` without a ``_FACADE_TABLE`` row and stay
    identity-UNCHECKED. Reusing a real ``charter.offering`` tuple keeps identity (``is``)
    true, so origin is resolved by scanning the identity-required modules.
    """
    from charter.offering import artifact_kinds

    planted = types.ModuleType("charter.planted_value_facade")
    vars(planted).update(
        LAYERED_REPOSITORY_KIND_PLURALS=artifact_kinds.LAYERED_REPOSITORY_KIND_PLURALS,
        __all__=["LAYERED_REPOSITORY_KIND_PLURALS"],
    )
    assert planted.LAYERED_REPOSITORY_KIND_PLURALS is artifact_kinds.LAYERED_REPOSITORY_KIND_PLURALS
    assert _untabled_reexports(planted, set()) == [("LAYERED_REPOSITORY_KIND_PLURALS", "charter.offering.artifact_kinds")]
    assert _untabled_reexports(planted, {"LAYERED_REPOSITORY_KIND_PLURALS"}) == []


@pytest.mark.parametrize("facade_module", _charter_modules())
def test_facade_all_reexports_are_tabled(facade_module: str) -> None:
    """Reverse of :func:`test_facade_all_lists_every_reexport`, enforced repo-wide:
    every symbol a charter module advertises in ``__all__`` whose object ORIGINATES
    from charter.offering (or an external shared-contract package) MUST carry an identity
    contract — an entry in ``_FACADE_TABLE``.

    Without this the identity gate is one-directional: a re-export placed in
    ``__all__`` but omitted from the table is public yet identity-UNCHECKED, so a
    later PR could replace it with a wrapper/shim and every gate stays green.

    Two scoping choices make the guard complete rather than manually curated:
    it is parametrized over **every** ``charter.*`` module self-discovered from
    ``src/charter/`` (not just ``_FACADE_TABLE.keys()``), so a re-export module
    absent from the table cannot hide (the ``charter.activation.kind_vocabulary`` escape the
    #3321 post-fold squad found); and it keys on
    :data:`_IDENTITY_REQUIRED_ORIGINS`, which includes doctrine-origin re-exports
    while excluding both charter-local definitions and stdlib value instances
    (e.g. a ``pathlib.Path`` module-level constant).
    """
    facade = importlib.import_module(facade_module)
    covered = {symbol for symbol, _ in _FACADE_TABLE.get(facade_module, [])}
    untabled = _untabled_reexports(facade, covered)
    assert not untabled, (
        f"{facade_module}.__all__ advertises re-exported symbols with no "
        f"identity contract (public but UNCHECKED): {sorted(untabled)}. Add each "
        f"to _FACADE_TABLE (promote a private doctrine symbol to a public name "
        f"before re-exporting it, rather than aliasing a private symbol)."
    )
