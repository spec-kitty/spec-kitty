"""Custom-mission validator: discovery -> load -> structural checks.

The validator is the single entry point for translating an operator-supplied
``mission_key`` into a :class:`ValidationReport`. It NEVER raises on
operator-fixable errors; every such error is surfaced inside
``ValidationReport.errors`` so callers (CLI, future REST surface) can render
the same shape regardless of failure mode.

Boundary notes:

- The validator does NOT load or consult :class:`MissionStepContractRepository`.
  The ``MISSION_CONTRACT_REF_UNRESOLVED`` code is declared in
  :class:`LoaderErrorCode` but is intentionally NOT raised here -- that
  cross-module check happens at run-start in WP05, where the on-disk
  contract repository is loaded into the runtime registry.
- The validator does NOT register synthesized contracts. Contract synthesis
  is WP03 / WP05 territory.
- Discovery is performed via
  :func:`runtime.next._internal_runtime.discovery.discover_missions_with_warnings`;
  no parallel loader is introduced (FR-003).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError

from kernel.pack_tiers import BUILT_IN

from specify_cli.mission_loader.errors import (
    LoaderError,
    LoaderErrorCode,
    LoaderWarning,
    LoaderWarningCode,
    ValidationReport,
)
from specify_cli.mission_loader.retrospective import (
    RETROSPECTIVE_MARKER_ID,
    has_retrospective_marker,
)
from runtime.next._internal_runtime.discovery import (
    DiscoveryContext,
    DiscoveryResult,
    DiscoveryWarning,
    discover_missions_with_warnings,
    is_reserved_key,
)
from runtime.next._internal_runtime.schema import (
    AuditStep,
    DiscoveredMission,
    MissionRuntimeError,
    MissionTemplate,
    MissionTemplateHasNoStepsError,
    PromptStep,
    load_mission_template_file,
)

# Tiers that originate from mission packs (R-007). Used to scope
# MISSION_PACK_LOAD_FAILED warnings.
_PACK_TIERS: frozenset[str] = frozenset({"project_config"})

# Pydantic error 'type' values that map to MISSION_REQUIRED_FIELD_MISSING.
# Anything else maps to MISSION_YAML_MALFORMED (shape error).
_MISSING_FIELD_TYPES: frozenset[str] = frozenset({"missing"})


def validate_custom_mission(
    mission_key: str, context: DiscoveryContext
) -> ValidationReport:
    """Validate the custom mission identified by ``mission_key``.

    Performs (in order):

    1. Mission discovery via the canonical
       ``discover_missions_with_warnings`` helper.
    2. Reserved-key check (R-002): non-builtin tiers are forbidden from
       declaring a key in :data:`RESERVED_BUILTIN_KEYS`.
    3. YAML / Pydantic load of the selected mission template.
    4. Structural checks: retrospective marker (R-001), per-step
       profile-binding rules (FR-008), and dependency references and cycles.
    5. Warning aggregation: shadow warnings + pack-load-failure warnings.

    Returns a :class:`ValidationReport` whose ``ok`` is True only when a
    template loaded AND no errors were collected.
    """
    discovery_result = discover_missions_with_warnings(context)

    # Step 1: locate the selected mission for the requested key.
    selected = _find_selected(discovery_result, mission_key)
    warnings = _collect_warnings(
        discovery_result, mission_key, selected_path=selected.path if selected else None
    )

    if selected is None:
        # No selected mission. Two sub-cases:
        # (a) discovery saw the file but it failed to parse / validate ->
        #     surface as MISSION_YAML_MALFORMED or MISSION_REQUIRED_FIELD_MISSING
        #     by attempting an explicit load against the warned path.
        # (b) genuinely unknown -> MISSION_KEY_UNKNOWN.
        load_error = _try_recover_from_warning(discovery_result, mission_key)
        if load_error is not None:
            return ValidationReport(errors=[load_error], warnings=warnings)
        tiers_searched = sorted({m.precedence_tier for m in discovery_result.missions})
        return ValidationReport(
            errors=[
                LoaderError(
                    code=LoaderErrorCode.MISSION_KEY_UNKNOWN,
                    message=(
                        f"Mission '{mission_key}' was not found in any discovery tier."
                    ),
                    details={
                        "mission_key": mission_key,
                        "tiers_searched": tiers_searched,
                    },
                )
            ],
            warnings=warnings,
        )

    # Step 2: reserved-key check.
    if selected.precedence_tier != BUILT_IN and is_reserved_key(mission_key):
        return ValidationReport(
            discovered=selected,
            errors=[
                LoaderError(
                    code=LoaderErrorCode.MISSION_KEY_RESERVED,
                    message=(
                        f"Mission key '{mission_key}' is reserved for the built-in "
                        f"tier; the {selected.precedence_tier!r} tier may not "
                        f"shadow built-in keys."
                    ),
                    details={
                        "mission_key": mission_key,
                        "file": selected.path,
                        "tier": selected.precedence_tier,
                        "reserved_keys": sorted(_reserved_keys()),
                    },
                )
            ],
            warnings=warnings,
        )

    # Step 3: load the template.
    try:
        template = load_mission_template_file(Path(selected.path))
    except PydanticValidationError as exc:
        return ValidationReport(
            discovered=selected,
            errors=[_map_pydantic_error(exc, selected.path, mission_key)],
            warnings=warnings,
        )
    except yaml.YAMLError as exc:
        return ValidationReport(
            discovered=selected,
            errors=[
                LoaderError(
                    code=LoaderErrorCode.MISSION_YAML_MALFORMED,
                    message=f"Mission file is not valid YAML: {selected.path}",
                    details={
                        "file": selected.path,
                        "mission_key": mission_key,
                        "parse_error": str(exc),
                    },
                )
            ],
            warnings=warnings,
        )
    except MissionTemplateHasNoStepsError:
        return ValidationReport(
            discovered=selected,
            errors=[_missing_steps_error(selected.path, mission_key)],
            warnings=warnings,
        )
    except MissionRuntimeError as exc:
        return ValidationReport(
            discovered=selected,
            errors=[
                LoaderError(
                    code=LoaderErrorCode.MISSION_YAML_MALFORMED,
                    message=str(exc),
                    details={
                        "file": selected.path,
                        "mission_key": mission_key,
                        "parse_error": str(exc),
                    },
                )
            ],
            warnings=warnings,
        )
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return ValidationReport(
            discovered=selected,
            errors=[
                LoaderError(
                    code=LoaderErrorCode.MISSION_YAML_MALFORMED,
                    message=f"Failed to load mission file {selected.path}: {exc}",
                    details={
                        "file": selected.path,
                        "mission_key": mission_key,
                        "parse_error": str(exc),
                    },
                )
            ],
            warnings=warnings,
        )

    # Step 4: structural checks.
    errors: list[LoaderError] = []
    if not template.steps:
        errors.append(
            LoaderError(
                code=LoaderErrorCode.MISSION_REQUIRED_FIELD_MISSING,
                message=(
                    f"Required mission field(s) missing in {selected.path}: steps"
                ),
                details={
                    "file": selected.path,
                    "mission_key": mission_key,
                    "field": "steps",
                    "missing_fields": ["steps"],
                    "parse_error": "Mission template must declare at least one step.",
                },
            )
        )
    elif not has_retrospective_marker(template):
        actual_last = template.steps[-1].id if template.steps else None
        errors.append(
            LoaderError(
                code=LoaderErrorCode.MISSION_RETROSPECTIVE_MISSING,
                message=(
                    f"Mission '{mission_key}' must end with a step whose id is "
                    f"'{RETROSPECTIVE_MARKER_ID}'; got {actual_last!r}."
                ),
                details={
                    "file": selected.path,
                    "mission_key": mission_key,
                    "actual_last_step_id": actual_last,
                    "expected": RETROSPECTIVE_MARKER_ID,
                },
            )
        )

    for step in template.steps:
        if step.id == RETROSPECTIVE_MARKER_ID:
            # The retrospective marker step is a narrative terminal and is
            # exempt from profile-binding rules.
            continue
        no_inputs = len(step.requires_inputs) == 0
        no_profile = not _has_text(step.agent_profile)
        no_contract_ref = not _has_text(step.contract_ref)
        if no_inputs and no_profile and no_contract_ref:
            errors.append(
                LoaderError(
                    code=LoaderErrorCode.MISSION_STEP_NO_PROFILE_BINDING,
                    message=(
                        f"Step '{step.id}' has no requires_inputs, agent_profile, "
                        "or contract_ref binding; one is required so the "
                        "composition gate can dispatch it."
                    ),
                    details={
                        "file": selected.path,
                        "mission_key": mission_key,
                        "step_id": step.id,
                    },
                )
            )
        if _has_text(step.agent_profile) and _has_text(step.contract_ref):
            errors.append(
                LoaderError(
                    code=LoaderErrorCode.MISSION_STEP_AMBIGUOUS_BINDING,
                    message=(
                        f"Step '{step.id}' declares BOTH agent_profile and "
                        "contract_ref; pick one."
                    ),
                    details={
                        "file": selected.path,
                        "mission_key": mission_key,
                        "step_id": step.id,
                    },
                )
            )

    errors.extend(_dependency_errors(template, selected.path, mission_key))

    return ValidationReport(
        template=template,
        discovered=selected,
        errors=errors,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


def _dependency_errors(
    template: MissionTemplate, source_path: str, mission_key: str
) -> list[LoaderError]:
    """Reject missing references and cycles across prompt and audit steps."""
    steps: list[PromptStep | AuditStep] = [*template.steps, *template.audit_steps]
    dependencies = {step.id: step.depends_on for step in steps}
    details = {"file": source_path, "mission_key": mission_key}
    errors: list[LoaderError] = []

    for step in steps:
        for dependency in step.depends_on:
            if dependency not in dependencies:
                errors.append(
                    LoaderError(
                        code=LoaderErrorCode.MISSION_STEP_DEPENDENCY_INVALID,
                        message=f"Step '{step.id}' depends on unknown step '{dependency}'.",
                        details={**details, "step_id": step.id, "dependency": dependency},
                    )
                )
    if errors:
        return errors

    visited: set[str] = set()
    visiting: list[str] = []

    def visit(step_id: str) -> list[str] | None:
        if step_id in visiting:
            return [*visiting[visiting.index(step_id) :], step_id]
        if step_id in visited:
            return None
        visiting.append(step_id)
        for dependency in dependencies[step_id]:
            cycle = visit(dependency)
            if cycle is not None:
                return cycle
        visiting.pop()
        visited.add(step_id)
        return None

    for step in steps:
        cycle = visit(step.id)
        if cycle is not None:
            errors.append(
                LoaderError(
                    code=LoaderErrorCode.MISSION_STEP_DEPENDENCY_INVALID,
                    message=f"Mission dependency cycle: {' -> '.join(cycle)}.",
                    details={**details, "step_id": cycle[0], "cycle": cycle},
                )
            )
            break
    return errors


def _find_selected(
    discovery_result: DiscoveryResult, mission_key: str
) -> DiscoveredMission | None:
    for entry in discovery_result.missions:
        if entry.key == mission_key and entry.selected:
            return entry
    return None


def _collect_warnings(
    discovery_result: DiscoveryResult,
    mission_key: str,
    *,
    selected_path: str | None,
) -> list[LoaderWarning]:
    """Build the warning list from the discovery result.

    - One ``MISSION_KEY_SHADOWED`` warning per non-selected discovery entry
      that matches ``mission_key`` (FR-002 / R-002).
    - One ``MISSION_PACK_LOAD_FAILED`` per discovery warning whose tier is
      a mission-pack tier (R-007).
    """
    warnings: list[LoaderWarning] = []

    shadowed_paths = [
        entry.path
        for entry in discovery_result.missions
        if entry.key == mission_key and not entry.selected
    ]
    if shadowed_paths and selected_path is not None:
        # Use the first matching selected entry's tier in the warning.
        selected_tier = next(
            (
                entry.precedence_tier
                for entry in discovery_result.missions
                if entry.key == mission_key and entry.selected
            ),
            "unknown",
        )
        warnings.append(
            LoaderWarning(
                code=LoaderWarningCode.MISSION_KEY_SHADOWED,
                message=(
                    f"Mission '{mission_key}' is defined in multiple tiers; the "
                    f"{selected_tier!r} tier wins."
                ),
                details={
                    "mission_key": mission_key,
                    "selected_path": selected_path,
                    "selected_tier": selected_tier,
                    "shadowed_paths": shadowed_paths,
                },
            )
        )

    for warning in discovery_result.warnings:
        if warning.tier in _PACK_TIERS:
            warnings.append(
                LoaderWarning(
                    code=LoaderWarningCode.MISSION_PACK_LOAD_FAILED,
                    message=(
                        f"Mission pack entry failed to load: {warning.path}"
                    ),
                    details={
                        "pack_root": warning.origin,
                        "failed_path": warning.path,
                        "parse_error": warning.error,
                        "tier": warning.tier,
                    },
                )
            )

    return warnings


def _try_recover_from_warning(
    discovery_result: DiscoveryResult, mission_key: str
) -> LoaderError | None:
    """When discovery dropped a candidate file due to load failure, retry it.

    Discovery filters malformed mission YAML files into ``warnings`` and
    omits them from ``missions``. That hides the precise error code from the
    operator -- they would only see ``MISSION_KEY_UNKNOWN``. To preserve
    operator clarity, when there's a candidate warning whose path is shaped
    like ``.../<mission_key>/mission.yaml``, we re-attempt the load directly
    so we can map the failure to the right code.
    """
    for warning in discovery_result.warnings:
        if not _path_matches_mission_key(warning.path, mission_key):
            continue
        return _classify_load_failure(warning, mission_key)
    return None


def _path_matches_mission_key(path: str, mission_key: str) -> bool:
    """Return True iff ``path`` looks like ``<...>/<mission_key>/mission.yaml``."""
    p = Path(path)
    return p.name == "mission.yaml" and p.parent.name == mission_key


def _classify_load_failure(
    warning: DiscoveryWarning, mission_key: str
) -> LoaderError:
    """Re-attempt the failed load and map the exception type to a code."""
    path = Path(warning.path)
    try:
        load_mission_template_file(path)
    except PydanticValidationError as exc:
        return _map_pydantic_error(exc, str(path), mission_key)
    except yaml.YAMLError as exc:
        return LoaderError(
            code=LoaderErrorCode.MISSION_YAML_MALFORMED,
            message=f"Mission file is not valid YAML: {path}",
            details={
                "file": str(path),
                "mission_key": mission_key,
                "parse_error": str(exc),
            },
        )
    except MissionTemplateHasNoStepsError:
        # Typed subclass (NFR-007): distinguished from generic malformed-template
        # MissionRuntimeError by exception type / error_code, not message text.
        return _missing_steps_error(str(path), mission_key)
    except MissionRuntimeError as exc:
        # MissionRuntimeError covers shape errors that bypass Pydantic
        # (e.g. "must be a mapping").
        return LoaderError(
            code=LoaderErrorCode.MISSION_YAML_MALFORMED,
            message=str(exc),
            details={
                "file": str(path),
                "mission_key": mission_key,
                "parse_error": str(exc),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive
        return LoaderError(
            code=LoaderErrorCode.MISSION_YAML_MALFORMED,
            message=f"Failed to load mission file {path}: {exc}",
            details={
                "file": str(path),
                "mission_key": mission_key,
                "parse_error": str(exc),
            },
        )
    # Should not happen: discovery already failed on this file. If it
    # somehow succeeds the second time, surface as malformed with the
    # original warning text.
    return LoaderError(  # pragma: no cover - race-condition path
        code=LoaderErrorCode.MISSION_YAML_MALFORMED,
        message=f"Mission file failed to load (transient): {warning.error}",
        details={
            "file": str(path),
            "mission_key": mission_key,
            "parse_error": warning.error,
        },
    )


def _map_pydantic_error(
    exc: PydanticValidationError, file_path: str, mission_key: str
) -> LoaderError:
    """Map a Pydantic ValidationError to MISSION_REQUIRED_FIELD_MISSING or
    MISSION_YAML_MALFORMED (shape error fallback)."""
    missing_fields: list[str] = []
    for err in exc.errors():
        if err.get("type") in _MISSING_FIELD_TYPES:
            loc = err.get("loc", ())
            if isinstance(loc, tuple):
                missing_fields.append(".".join(str(part) for part in loc))
    if missing_fields:
        return LoaderError(
            code=LoaderErrorCode.MISSION_REQUIRED_FIELD_MISSING,
            message=(
                f"Required mission field(s) missing in {file_path}: "
                f"{', '.join(missing_fields)}"
            ),
            details={
                "file": file_path,
                "mission_key": mission_key,
                "field": missing_fields[0],
                "missing_fields": missing_fields,
                "parse_error": str(exc),
            },
        )
    return LoaderError(
        code=LoaderErrorCode.MISSION_YAML_MALFORMED,
        message=f"Mission file failed schema validation: {file_path}",
        details={
            "file": file_path,
            "mission_key": mission_key,
            "parse_error": str(exc),
        },
    )


def _missing_steps_error(file_path: str, mission_key: str) -> LoaderError:
    return LoaderError(
        code=LoaderErrorCode.MISSION_REQUIRED_FIELD_MISSING,
        message=f"Required mission field(s) missing in {file_path}: steps",
        details={
            "file": file_path,
            "mission_key": mission_key,
            "field": "steps",
            "missing_fields": ["steps"],
            "parse_error": "Mission template must declare at least one step.",
        },
    )


def _reserved_keys() -> set[str]:
    """Return a fresh set of reserved built-in keys for inclusion in details.

    Wrapped to avoid leaking the frozen-set type into JSON serialization
    paths that may not handle ``frozenset``.
    """
    from runtime.next._internal_runtime.discovery import RESERVED_BUILTIN_KEYS

    return set(RESERVED_BUILTIN_KEYS)


__all__: list[Any] = ["validate_custom_mission"]
