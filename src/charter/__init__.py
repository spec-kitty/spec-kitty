"""Charter parsing and configuration extraction.

This subpackage provides tools for:
- Parsing charter markdown into structured sections
- Extracting configuration from markdown tables, YAML blocks, and prose
- Validating extracted config against Pydantic schemas
- Emitting YAML config files for consumption by other modules

Provides:
- load_governance_config() / load_directives_config(): read the
  hand-authored ``governance`` / ``directives`` sections directly from
  ``charter.yaml`` (IC-04 -- the prose->triad scrape is retired).
- sync(): retained for its ``charter.md`` staleness-check contract; no
  longer extracts or writes anything (see ``charter.activation.sync`` module docstring).

Lazy re-export table (mission ``charter-activation-split-01M16ZSE``, MAP-B):
this module used to eagerly ``from .X import Y`` all 15 blocks below, which
meant merely doing ``import charter.offering`` (or any single top-level
offering facade) dragged the entire activation layer (interview, compiler,
DRG activation filtering, pack management, ...) into the import graph. The
``__getattr__`` below (PEP 562) resolves each public name on first access and
caches it on this module's ``globals()``, so ``charter.offering.*`` importers
no longer pay for (or transitively depend on) the activation layer. All 15
re-exports are verified side-effect-free at import time, so lazily deferring
them changes nothing observable about *when* a name becomes available --
only whether merely importing ``charter`` (or ``charter.offering``) forces
its owning submodule to load.

``_LAZY_IMPORTS`` uses the ``{name: (module_path, attr)}`` 2-tuple shape
(matching ``src/specify_cli/sync/__init__.py`` / ``src/specify_cli/missions/
__init__.py`` -- the codebase's established lazy-facade idiom, recognized by
the architectural dead-code scanners' facade detector), not the simpler
``{name: module_path}`` 1-value shape used by ``src/runtime/next/__init__.py``
/ ``src/doctrine.py``: this module re-exports many *different* names across
many owning submodules (rather than one submodule's whole surface), and the
2-tuple shape is also what lets ``tests/architectural/test_no_dead_symbols.py``
register a real caller-edge for each re-exported symbol instead of reporting
every one as an orphan.
"""

from __future__ import annotations

import importlib
from typing import Any

#: Public name -> ``(fully-qualified owning submodule, attribute name in that
#: module)``. Resolved on first attribute access via :func:`__getattr__`
#: below. The attribute name always equals the public name here (no charter
#: re-export renames its source symbol), but the pair is kept explicit to
#: match the established ``_LAZY_IMPORTS`` shape.
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # .bundle (stays top-level -- shared primitive, neither layer owns it)
    "CANONICAL_MANIFEST": ("charter.bundle", "CANONICAL_MANIFEST"),
    "CharterBundleManifest": ("charter.bundle", "CharterBundleManifest"),
    "SCHEMA_VERSION": ("charter.bundle", "SCHEMA_VERSION"),
    # .catalog -> charter.activation.catalog
    "OfferingCatalog": ("charter.activation.catalog", "OfferingCatalog"),
    "load_offering_catalog": ("charter.activation.catalog", "load_offering_catalog"),
    # .compiler -> charter.activation.compiler
    "CompiledCharter": ("charter.activation.compiler", "CompiledCharter"),
    "CharterReference": ("charter.activation.compiler", "CharterReference"),
    "WriteBundleResult": ("charter.activation.compiler", "WriteBundleResult"),
    "compile_charter": ("charter.activation.compiler", "compile_charter"),
    "write_compiled_charter": ("charter.activation.compiler", "write_compiled_charter"),
    # .context -> charter.activation.context
    "CharterContextResult": ("charter.activation.context", "CharterContextResult"),
    "build_charter_context": ("charter.activation.context", "build_charter_context"),
    # .interview -> charter.activation.interview
    "CharterInterview": ("charter.activation.interview", "CharterInterview"),
    "MINIMAL_QUESTION_ORDER": ("charter.activation.interview", "MINIMAL_QUESTION_ORDER"),
    "QUESTION_ORDER": ("charter.activation.interview", "QUESTION_ORDER"),
    "QUESTION_PROMPTS": ("charter.activation.interview", "QUESTION_PROMPTS"),
    "apply_answer_overrides": ("charter.activation.interview", "apply_answer_overrides"),
    "default_interview": ("charter.activation.interview", "default_interview"),
    "read_interview_answers": ("charter.activation.interview", "read_interview_answers"),
    "write_interview_answers": ("charter.activation.interview", "write_interview_answers"),
    # .parser (stays top-level -- shared primitive)
    "CharterParser": ("charter.parser", "CharterParser"),
    "CharterSection": ("charter.parser", "CharterSection"),
    # .schemas -> charter.activation.schemas
    "BranchStrategyConfig": ("charter.activation.schemas", "BranchStrategyConfig"),
    "CommitConfig": ("charter.activation.schemas", "CommitConfig"),
    "DoctrineSelectionConfig": ("charter.activation.schemas", "DoctrineSelectionConfig"),
    "Directive": ("charter.activation.schemas", "Directive"),
    "DirectivesConfig": ("charter.activation.schemas", "DirectivesConfig"),
    "ExtractionMetadata": ("charter.activation.schemas", "ExtractionMetadata"),
    "GovernanceConfig": ("charter.activation.schemas", "GovernanceConfig"),
    "PerformanceConfig": ("charter.activation.schemas", "PerformanceConfig"),
    "QualityConfig": ("charter.activation.schemas", "QualityConfig"),
    "SectionsParsed": ("charter.activation.schemas", "SectionsParsed"),
    "CharterTestingConfig": ("charter.activation.schemas", "CharterTestingConfig"),
    "emit_yaml": ("charter.activation.schemas", "emit_yaml"),
    # .scope -> charter.activation.scope
    "CharterScope": ("charter.activation.scope", "CharterScope"),
    "CharterScopeConfig": ("charter.activation.scope", "CharterScopeConfig"),
    "CharterScopeConflict": ("charter.activation.scope", "CharterScopeConflict"),
    "CharterScopeNotFound": ("charter.activation.scope", "CharterScopeNotFound"),
    # .sync -> charter.activation.sync
    "SyncResult": ("charter.activation.sync", "SyncResult"),
    "load_directives_config": ("charter.activation.sync", "load_directives_config"),
    "load_governance_config": ("charter.activation.sync", "load_governance_config"),
    "sync": ("charter.activation.sync", "sync"),
    # .extends -> charter.offering.packs.extends
    "ExtendsBaseNotFoundError": ("charter.offering.packs.extends", "ExtendsBaseNotFoundError"),
    "ExtendsCycleError": ("charter.offering.packs.extends", "ExtendsCycleError"),
    "resolve_extends_order": ("charter.offering.packs.extends", "resolve_extends_order"),
    # .mission_type_profiles -> charter.activation.mission_type_profiles
    "CrossGrainDoubleDeclarationError": (
        "charter.activation.mission_type_profiles",
        "CrossGrainDoubleDeclarationError",
    ),
    "GovernancePayload": ("charter.activation.mission_type_profiles", "GovernancePayload"),
    "MissionTypeProfile": ("charter.activation.mission_type_profiles", "MissionTypeProfile"),
    "ResolvedGovernance": ("charter.activation.mission_type_profiles", "ResolvedGovernance"),
    "ResolvedMissionType": ("charter.activation.mission_type_profiles", "ResolvedMissionType"),
    "UnknownMissionTypeError": ("charter.activation.mission_type_profiles", "UnknownMissionTypeError"),
    "existing_mission_types": ("charter.activation.mission_type_profiles", "existing_mission_types"),
    "resolve_mission_type_context": (
        "charter.activation.mission_type_profiles",
        "resolve_mission_type_context",
    ),
    # .resolver -> charter.activation.resolver
    "GovernanceResolution": ("charter.activation.resolver", "GovernanceResolution"),
    "GovernanceResolutionError": ("charter.activation.resolver", "GovernanceResolutionError"),
    "collect_governance_diagnostics": ("charter.activation.resolver", "collect_governance_diagnostics"),
    "resolve_governance_for_profile": ("charter.activation.resolver", "resolve_governance_for_profile"),
    "resolve_project_governance": ("charter.activation.resolver", "resolve_project_governance"),
    # .template_resolver -> charter.activation.template_resolver
    "CharterTemplateResolver": ("charter.activation.template_resolver", "CharterTemplateResolver"),
    # .pack_context -> charter.activation.pack_context
    "PackContext": ("charter.activation.pack_context", "PackContext"),
    # .exceptions -> charter.activation.exceptions
    "CharterActivationError": ("charter.activation.exceptions", "CharterActivationError"),
}


def __getattr__(name: str) -> Any:
    """Lazily resolve ``charter.<name>`` against its owning submodule.

    Caches the resolved value on this module's ``globals()`` so repeat
    access after the first does not re-run the import/lookup.
    """
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_path), attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_IMPORTS))


__all__ = [
    "CANONICAL_MANIFEST",
    "CharterBundleManifest",
    "SCHEMA_VERSION",
    "OfferingCatalog",
    "load_offering_catalog",
    "CompiledCharter",
    "CharterReference",
    "WriteBundleResult",
    "compile_charter",
    "write_compiled_charter",
    "CharterContextResult",
    "build_charter_context",
    "CharterInterview",
    "QUESTION_ORDER",
    "MINIMAL_QUESTION_ORDER",
    "QUESTION_PROMPTS",
    "default_interview",
    "read_interview_answers",
    "write_interview_answers",
    "apply_answer_overrides",
    "CharterParser",
    "CharterSection",
    "BranchStrategyConfig",
    "CommitConfig",
    "DoctrineSelectionConfig",
    "Directive",
    "DirectivesConfig",
    "ExtractionMetadata",
    "GovernanceConfig",
    "PerformanceConfig",
    "QualityConfig",
    "SectionsParsed",
    "CharterTestingConfig",
    "emit_yaml",
    "CharterScope",
    "CharterScopeConfig",
    "CharterScopeConflict",
    "CharterScopeNotFound",
    "SyncResult",
    "load_directives_config",
    "load_governance_config",
    "sync",
    "GovernanceResolution",
    "GovernanceResolutionError",
    "resolve_governance_for_profile",
    "resolve_project_governance",
    "collect_governance_diagnostics",
    "CrossGrainDoubleDeclarationError",
    "GovernancePayload",
    "MissionTypeProfile",
    "ResolvedGovernance",
    "ResolvedMissionType",
    "UnknownMissionTypeError",
    "existing_mission_types",
    "resolve_mission_type_context",
    "CharterTemplateResolver",
    "PackContext",
    "CharterActivationError",
    "ExtendsBaseNotFoundError",
    "ExtendsCycleError",
    "resolve_extends_order",
]
