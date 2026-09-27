"""Documentation State Management for Spec Kitty.

This module manages documentation mission state persistence in feature meta.json files.
State includes iteration mode, selected Divio types, configured generators, and audit metadata.

Documentation State Schema for meta.json
========================================

The documentation_state field is added to feature meta.json files for
documentation mission features. It persists state between iterations.

Schema:
{
    "documentation_state": {
        "iteration_mode": "initial" | "gap_filling" | "mission_specific",
        "divio_types_selected": ["tutorial", "how-to", "reference", "explanation"],
        "generators_configured": [
            {
                "name": "sphinx" | "jsdoc" | "rustdoc",
                "language": "python" | "javascript" | "typescript" | "rust",
                "config_path": "relative/path/to/config.py"
            }
        ],
        "target_audience": "developers" | "end-users" | "contributors" | "operators",
        "last_audit_date": "2026-01-12T00:00:00Z" | null,
        "coverage_percentage": 0.75  # 0.0 to 1.0
    }
}

Fields:
- iteration_mode: How this documentation mission was run. The legacy token
  ``feature_specific`` is still accepted on input and read back as
  ``mission_specific`` (Terminology Canon, #5205); it is never written.
- divio_types_selected: Which Divio types user chose to include
- generators_configured: Which generators were set up and where
- target_audience: Primary documentation audience
- last_audit_date: When gap analysis last ran (null if never)
- coverage_percentage: Overall doc coverage from most recent audit (0.0 if initial)
"""

from __future__ import annotations

from kernel.clock import datetime
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from specify_cli.core.paths import load_meta_fail_closed
from specify_cli.mission_metadata import write_meta


IterationMode = Literal["initial", "gap_filling", "mission_specific"]

ITERATION_MODES: frozenset[str] = frozenset({"initial", "gap_filling", "mission_specific"})

# Read-only legacy input aliases: accepted from existing meta.json files and
# callers, normalized to the canonical token, never written back (#5205).
_LEGACY_ITERATION_MODE_ALIASES: dict[str, IterationMode] = {"feature_specific": "mission_specific"}


def canonical_iteration_mode(value: object) -> IterationMode | None:
    """Return the canonical iteration mode for *value*, or ``None`` if unknown.

    Accepts the canonical tokens and the legacy ``feature_specific`` alias.
    """
    if not isinstance(value, str):
        return None
    if value in _LEGACY_ITERATION_MODE_ALIASES:
        return _LEGACY_ITERATION_MODE_ALIASES[value]
    if value in ITERATION_MODES:
        return cast(IterationMode, value)
    return None


def _require_iteration_mode(value: object) -> IterationMode:
    """Normalize *value* to a canonical iteration mode, or raise ``ValueError``."""
    mode = canonical_iteration_mode(value)
    if mode is None:
        raise ValueError(f"Invalid iteration_mode: {value}. Must be one of: {sorted(ITERATION_MODES)}")
    return mode


class GeneratorConfig(TypedDict):
    """Generator configuration entry."""

    name: Literal["sphinx", "jsdoc", "rustdoc"]
    language: str
    config_path: str


class DocumentationState(TypedDict):
    """Documentation state schema for meta.json."""

    iteration_mode: IterationMode
    divio_types_selected: list[str]
    generators_configured: list[GeneratorConfig]
    target_audience: str
    last_audit_date: str | None  # ISO datetime or null
    coverage_percentage: float  # 0.0 to 1.0


def _require_meta(meta_file: Path) -> dict[str, Any]:
    """Load ``meta_file``'s meta.json fail-closed, or raise if it is missing.

    Single shared guard for every reader in this module (FR-007 route): a
    MISSING meta.json is the ``None`` answer from ``load_meta_fail_closed``
    (raised here as ``FileNotFoundError``, unchanged); a CORRUPT one raises
    the typed ``MissionMetaReadError`` and propagates undisturbed. The two
    are deliberately NOT collapsed -- reporting corruption as "no such file"
    would be a false diagnosis.

    Args:
        meta_file: Path to meta.json (its parent directory is loaded).

    Returns:
        The parsed meta.json contents.

    Raises:
        FileNotFoundError: If meta.json doesn't exist.
        MissionMetaReadError: If meta.json is invalid JSON or not a JSON
            object (propagated from ``load_meta_fail_closed`` unchanged).
    """
    meta = load_meta_fail_closed(meta_file.parent)
    if meta is None:
        raise FileNotFoundError(f"No such file or directory: '{meta_file}'")
    return meta


# ============================================================================
# Individual Field Setters (T041-T044)
# ============================================================================


def set_iteration_mode(meta_file: Path, iteration_mode: str) -> None:
    """Set iteration mode in feature meta.json.

    Args:
        meta_file: Path to meta.json
        iteration_mode: Iteration mode to store (the legacy ``feature_specific``
            alias is accepted and stored as ``mission_specific``)

    Raises:
        FileNotFoundError: If meta.json doesn't exist
        ValueError: If iteration_mode is invalid
    """
    mode = _require_iteration_mode(iteration_mode)

    # Read existing meta.json (fail-closed on corruption; raises if missing)
    meta = _require_meta(meta_file)

    # Initialize documentation_state if not present
    if "documentation_state" not in meta:
        meta["documentation_state"] = {}

    # Set iteration mode
    meta["documentation_state"]["iteration_mode"] = mode

    # Write back with standard formatting (tolerant — no top-level validation)
    write_meta(meta_file.parent, meta, validate=False)


def set_divio_types_selected(meta_file: Path, divio_types: list[str]) -> None:
    """Set selected Divio types in feature meta.json.

    Args:
        meta_file: Path to meta.json
        divio_types: List of Divio types to store

    Raises:
        FileNotFoundError: If meta.json doesn't exist
        ValueError: If any type is invalid
    """
    valid_types = {"tutorial", "how-to", "reference", "explanation"}
    invalid_types = set(divio_types) - valid_types
    if invalid_types:
        raise ValueError(f"Invalid Divio types: {invalid_types}. Must be one of: {valid_types}")

    # Read existing meta.json (fail-closed on corruption; raises if missing)
    meta = _require_meta(meta_file)

    # Initialize documentation_state if not present
    if "documentation_state" not in meta:
        meta["documentation_state"] = {}

    # Set Divio types
    meta["documentation_state"]["divio_types_selected"] = divio_types

    # Write back with standard formatting (tolerant — no top-level validation)
    write_meta(meta_file.parent, meta, validate=False)


def set_generators_configured(meta_file: Path, generators: list[GeneratorConfig]) -> None:
    """Set configured generators in feature meta.json.

    Args:
        meta_file: Path to meta.json
        generators: List of generator configs, each with:
            - name: Generator name (sphinx, jsdoc, rustdoc)
            - language: Language (python, javascript, rust)
            - config_path: Path to config file (relative to project root)

    Raises:
        FileNotFoundError: If meta.json doesn't exist
        ValueError: If generator config is invalid
    """
    # Validate generator configs
    valid_names = {"sphinx", "jsdoc", "rustdoc"}
    for gen in generators:
        if "name" not in gen:
            raise ValueError(f"Generator config missing 'name' field: {gen}")
        if gen["name"] not in valid_names:
            raise ValueError(f"Invalid generator name: {gen['name']}. Must be one of: {valid_names}")
        if "language" not in gen:
            raise ValueError(f"Generator config missing 'language' field: {gen}")
        if "config_path" not in gen:
            raise ValueError(f"Generator config missing 'config_path' field: {gen}")

    # Read existing meta.json (fail-closed on corruption; raises if missing)
    meta = _require_meta(meta_file)

    # Initialize documentation_state if not present
    if "documentation_state" not in meta:
        meta["documentation_state"] = {}

    # Set generators
    meta["documentation_state"]["generators_configured"] = generators

    # Write back with standard formatting (tolerant — no top-level validation)
    write_meta(meta_file.parent, meta, validate=False)


def set_audit_metadata(meta_file: Path, last_audit_date: datetime | None, coverage_percentage: float) -> None:
    """Set audit metadata in feature meta.json.

    Args:
        meta_file: Path to meta.json
        last_audit_date: When gap analysis last ran (None if never)
        coverage_percentage: Overall doc coverage (0.0 to 1.0)

    Raises:
        FileNotFoundError: If meta.json doesn't exist
        ValueError: If coverage_percentage is out of range
    """
    if not (0.0 <= coverage_percentage <= 1.0):
        raise ValueError(f"coverage_percentage must be 0.0-1.0, got {coverage_percentage}")

    # Read existing meta.json (fail-closed on corruption; raises if missing)
    meta = _require_meta(meta_file)

    # Initialize documentation_state if not present
    if "documentation_state" not in meta:
        meta["documentation_state"] = {}

    # Set audit metadata
    meta["documentation_state"]["last_audit_date"] = last_audit_date.isoformat() if last_audit_date else None
    meta["documentation_state"]["coverage_percentage"] = coverage_percentage

    # Write back with standard formatting (tolerant — no top-level validation)
    write_meta(meta_file.parent, meta, validate=False)


# ============================================================================
# Comprehensive State Read/Write Functions (T045)
# ============================================================================


def read_documentation_state(meta_file: Path) -> DocumentationState | None:
    """Read documentation state from feature meta.json.

    Args:
        meta_file: Path to meta.json

    Returns:
        DocumentationState dict if present, None if not a documentation mission
        or if state is missing (backward compatibility)

    Raises:
        FileNotFoundError: If meta.json doesn't exist
        MissionMetaReadError: If meta.json is invalid JSON or not a JSON object
            (FR-007 / NFR-003 -- the typed fail-closed contract; this reader
            never surfaces a raw ``ValueError`` for a corrupt meta.json)
    """
    # FR-007 route: the previous ``allow_missing=False`` strict contract is
    # reproduced explicitly via ``_require_meta`` -- ``load_meta_fail_closed``
    # answers ``None`` for a MISSING file (-> FileNotFoundError, per the
    # docstring) and raises the typed ``MissionMetaReadError`` for a CORRUPT
    # one. It is deliberately NOT re-wrapped into a raw ``ValueError``:
    # re-raising ``ValueError`` here is precisely the leak NFR-003 forbids.
    meta = _require_meta(meta_file)
    if not isinstance(meta, dict):
        return None

    # Check if this is a documentation mission
    if meta.get("mission_type") != "documentation":
        return None

    # Get documentation_state (may be missing for old features)
    state = meta.get("documentation_state")
    if not isinstance(state, dict):
        return None
    # Read-only legacy alias: surface ``feature_specific`` as ``mission_specific``
    # without rewriting the file.
    mode = canonical_iteration_mode(state.get("iteration_mode"))
    if mode is not None and mode != state.get("iteration_mode"):
        state = {**state, "iteration_mode": mode}
    return cast(DocumentationState, state)


def write_documentation_state(meta_file: Path, state: DocumentationState) -> None:
    """Write complete documentation state to feature meta.json.

    Args:
        meta_file: Path to meta.json
        state: Complete documentation state to write

    Raises:
        FileNotFoundError: If meta.json doesn't exist
        ValueError: If state is invalid
    """
    # Validate state structure
    required_fields = {
        "iteration_mode",
        "divio_types_selected",
        "generators_configured",
        "target_audience",
        "last_audit_date",
        "coverage_percentage",
    }
    missing_fields = required_fields - set(state.keys())
    if missing_fields:
        raise ValueError(f"State missing required fields: {missing_fields}")

    # Read existing meta.json (fail-closed on corruption; raises if missing)
    meta = _require_meta(meta_file)

    # Update documentation_state, always persisting the canonical iteration mode
    meta["documentation_state"] = {**state, "iteration_mode": _require_iteration_mode(state["iteration_mode"])}

    # Write back with standard formatting (tolerant — no top-level validation)
    write_meta(meta_file.parent, meta, validate=False)


def initialize_documentation_state(
    meta_file: Path,
    iteration_mode: str,
    divio_types: list[str],
    generators: list[GeneratorConfig],
    target_audience: str,
) -> DocumentationState:
    """Initialize documentation state for a new documentation mission.

    Args:
        meta_file: Path to meta.json
        iteration_mode: initial, gap_filling, or mission_specific (legacy
            ``feature_specific`` is accepted and normalized)
        divio_types: Selected Divio types
        generators: Configured generators
        target_audience: Primary documentation audience

    Returns:
        Initialized DocumentationState

    Raises:
        FileNotFoundError: If meta.json doesn't exist
    """
    state: DocumentationState = {
        "iteration_mode": _require_iteration_mode(iteration_mode),
        "divio_types_selected": divio_types,
        "generators_configured": generators,
        "target_audience": target_audience,
        "last_audit_date": None,
        "coverage_percentage": 0.0,
    }

    write_documentation_state(meta_file, state)
    return state


def update_documentation_state(meta_file: Path, **updates: Any) -> DocumentationState:
    """Update specific fields in documentation state.

    Args:
        meta_file: Path to meta.json
        **updates: Fields to update (iteration_mode, divio_types_selected, etc.)

    Returns:
        Updated DocumentationState

    Raises:
        FileNotFoundError: If meta.json doesn't exist
        ValueError: If state doesn't exist (call initialize first)
    """
    # Read current state
    state = read_documentation_state(meta_file)

    if state is None:
        raise ValueError(f"No documentation state found in {meta_file}. Call initialize_documentation_state() first.")

    # Update fields
    for key, value in updates.items():
        if key in state:
            state[key] = _require_iteration_mode(value) if key == "iteration_mode" else value  # type: ignore

    # Write back
    write_documentation_state(meta_file, state)
    return state


# ============================================================================
# Backward Compatibility / Migration (T046)
# ============================================================================


def ensure_documentation_state(meta_file: Path) -> None:
    """Ensure meta.json has documentation_state field.

    For backward compatibility with old documentation mission features.
    If feature is a documentation mission but lacks documentation_state,
    initialize with sensible defaults.

    Args:
        meta_file: Path to meta.json
    """
    # Read existing meta.json (fail-closed on corruption; raises if missing)
    meta = _require_meta(meta_file)

    # Check if documentation mission
    if meta.get("mission_type") != "documentation":
        return  # Not a documentation mission, nothing to do

    # Check if state already exists
    if "documentation_state" in meta:
        return  # Already has state

    # Initialize with defaults
    meta["documentation_state"] = {
        "iteration_mode": "initial",  # Assume first run
        "divio_types_selected": [],  # Unknown, user must specify
        "generators_configured": [],  # Unknown, user must configure
        "target_audience": "developers",  # Reasonable default
        "last_audit_date": None,
        "coverage_percentage": 0.0,
    }

    # Write back with standard formatting (tolerant — no top-level validation)
    write_meta(meta_file.parent, meta, validate=False)


def get_state_version(state: DocumentationState) -> int:
    """Get state schema version for future migrations.

    Currently all states are version 1.

    Args:
        state: Documentation state

    Returns:
        Schema version number
    """
    return state.get("_schema_version", 1)  # type: ignore
