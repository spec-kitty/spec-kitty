"""Strictness policy system for glossary enforcement.

This module implements the strictness policy system with three enforcement modes
(off/medium/max) and four-tier precedence resolution (global → mission → step → runtime).
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ruamel.yaml

if TYPE_CHECKING:
    from .models import SemanticConflict, Severity


class Strictness(StrEnum):
    """Glossary enforcement strictness levels.

    - OFF: No enforcement, generation always proceeds
    - MEDIUM: Warn broadly, block only high-severity conflicts
    - MAX: Block any unresolved conflict regardless of severity
    """

    OFF = "off"
    MEDIUM = "medium"
    MAX = "max"


def resolve_strictness(
    global_default: Strictness = Strictness.MEDIUM,
    mission_override: Strictness | None = None,
    step_override: Strictness | None = None,
    runtime_override: Strictness | None = None,
) -> Strictness:
    """Resolve effective strictness using precedence chain.

    Precedence (highest to lowest):
    1. Runtime override (CLI --strictness flag)
    2. Step metadata (glossary_check_strictness in step definition)
    3. Mission config (mission.yaml default)
    4. Global default (Strictness.MEDIUM)

    Args:
        global_default: Global default strictness (typically from config.yaml)
        mission_override: Mission-level strictness (from mission.yaml)
        step_override: Step-level strictness (from step metadata)
        runtime_override: Runtime override (from CLI flag)

    Returns:
        The effective strictness mode to apply.

    Examples:
        >>> resolve_strictness()  # All None
        <Strictness.MEDIUM: 'medium'>

        >>> resolve_strictness(runtime_override=Strictness.OFF)
        <Strictness.OFF: 'off'>

        >>> resolve_strictness(
        ...     mission_override=Strictness.MAX,
        ...     step_override=Strictness.OFF,
        ... )
        <Strictness.OFF: 'off'>  # Step wins over mission
    """
    # Apply precedence: most specific wins
    if runtime_override is not None:
        return runtime_override
    if step_override is not None:
        return step_override
    if mission_override is not None:
        return mission_override
    return global_default


def load_global_strictness(repo_root: Path) -> Strictness:
    """Load global strictness from .kittify/config.yaml.

    This function reads the global strictness setting from the project config.
    If the config file doesn't exist, is malformed, or has no strictness setting,
    returns the safe default (Strictness.MEDIUM).

    Args:
        repo_root: Path to repository root

    Returns:
        Global strictness setting, or Strictness.MEDIUM if not configured

    Examples:
        >>> from pathlib import Path
        >>> load_global_strictness(Path("/nonexistent"))
        <Strictness.MEDIUM: 'medium'>
    """
    config_path = repo_root / ".kittify" / "config.yaml"
    if not config_path.exists():
        return Strictness.MEDIUM

    yaml = ruamel.yaml.YAML(typ="safe")
    try:
        with config_path.open() as f:
            config = yaml.load(f)

        if config and "glossary" in config and "strictness" in config["glossary"]:
            value = config["glossary"]["strictness"]
            return Strictness(value)
    except Exception:  # noqa: S110
        # Invalid config (malformed YAML, invalid enum value, etc.)
        # Return safe default rather than crashing
        pass

    return Strictness.MEDIUM


def coerce_strictness(value: Any) -> Strictness | None:
    """Normalise a strictness value coming from a context, a config or a CLI flag.

    Contexts and callers may carry a :class:`Strictness`, its string value, or
    nothing at all. Anything unrecognised returns ``None`` so the caller can fall
    back to the documented default instead of publishing a policy value that was
    never configured.

    Args:
        value: ``Strictness``, string, or ``None``.

    Returns:
        The matching :class:`Strictness`, or ``None`` when absent/unrecognised.
    """
    if value is None:
        return None
    if isinstance(value, Strictness):
        return value
    if hasattr(value, "value"):
        value = value.value
    try:
        return Strictness(value)
    except ValueError:
        return None


def resolve_context_strictness(
    context: Any,
    *,
    repo_root: Path | None = None,
    runtime_override: Strictness | None = None,
) -> Strictness:
    """Resolve the effective strictness for a primitive execution context.

    This is the single resolution path for the whole glossary pipeline: the
    semantic-check emitter (which records the value on ``SemanticCheckEvaluated``)
    and the generation gate (which enforces it) both call it, so the event and the
    enforcement cannot drift apart (#7065).

    Precedence, highest first: runtime override, step metadata, mission config,
    global default from ``.kittify/config.yaml``. Tiers are read from
    ``context.step_strictness`` and ``context.mission_strictness``; unknown or
    malformed values are ignored, leaving the documented ``medium`` default in
    force rather than raising during emission.

    Args:
        context: Execution context carrying optional mission/step overrides.
        repo_root: Repository root used to load the global default. When ``None``
            the global default is :attr:`Strictness.MEDIUM`.
        runtime_override: CLI ``--strictness`` value (highest precedence).

    Returns:
        The effective :class:`Strictness` for this context.
    """
    global_default = load_global_strictness(repo_root) if repo_root is not None else Strictness.MEDIUM

    return resolve_strictness(
        global_default=global_default,
        mission_override=coerce_strictness(getattr(context, "mission_strictness", None)),
        step_override=coerce_strictness(getattr(context, "step_strictness", None)),
        runtime_override=coerce_strictness(runtime_override),
    )


def should_block(
    strictness: Strictness,
    conflicts: list[SemanticConflict],
) -> bool:
    """Determine if generation should be blocked.

    Blocking rules:
    - OFF: Never block (return False regardless of conflicts)
    - MEDIUM: Block only if ANY high-severity conflict exists
    - MAX: Block if ANY conflict exists (regardless of severity)

    Args:
        strictness: The effective strictness mode
        conflicts: List of detected semantic conflicts

    Returns:
        True if generation should be blocked, False otherwise

    Examples:
        >>> from glossary.models import SemanticConflict, Severity, TermSurface, ConflictType
        >>> high_conflict = SemanticConflict(
        ...     term=TermSurface(surface_text="test"),
        ...     conflict_type=ConflictType.AMBIGUOUS,
        ...     severity=Severity.HIGH,
        ...     confidence=0.9,
        ...     candidate_senses=[],
        ...     context="test",
        ... )

        >>> should_block(Strictness.OFF, [high_conflict])
        False

        >>> should_block(Strictness.MEDIUM, [high_conflict])
        True

        >>> should_block(Strictness.MAX, [high_conflict])
        True
    """
    if strictness == Strictness.OFF:
        return False

    if strictness == Strictness.MAX:
        return len(conflicts) > 0

    # MEDIUM mode: block only on high-severity.
    # Unknown/invalid severities are treated as HIGH for safety --
    # an unrecognised severity must not silently pass through.
    # Import inside function to avoid circular dependency
    from .models import Severity

    _known_severities = set(Severity)
    return any(c.severity == Severity.HIGH or c.severity not in _known_severities for c in conflicts)


def categorize_conflicts(
    conflicts: list[SemanticConflict],
) -> dict[Severity, list[SemanticConflict]]:
    """Group conflicts by severity level for reporting.

    This helper function organizes conflicts into severity buckets,
    making it easier to generate reports and determine blocking behavior.

    Args:
        conflicts: List of detected semantic conflicts

    Returns:
        Dict mapping severity to list of conflicts at that level.
        All three severity levels (LOW, MEDIUM, HIGH) are present as keys,
        even if some have empty lists.

    Examples:
        >>> from glossary.models import (
        ...     SemanticConflict, Severity, TermSurface, ConflictType
        ... )
        >>> low = SemanticConflict(
        ...     term=TermSurface(surface_text="test"),
        ...     conflict_type=ConflictType.UNKNOWN,
        ...     severity=Severity.LOW,
        ...     confidence=0.3,
        ...     candidate_senses=[],
        ...     context="test",
        ... )
        >>> categorized = categorize_conflicts([low])
        >>> list(categorized.keys())
        [<Severity.LOW: 'low'>, <Severity.MEDIUM: 'medium'>, <Severity.HIGH: 'high'>]
        >>> len(categorized[Severity.LOW])
        1
    """
    # Import inside function to avoid circular dependency
    from .models import Severity

    categorized: dict[Severity, list[SemanticConflict]] = {
        Severity.LOW: [],
        Severity.MEDIUM: [],
        Severity.HIGH: [],
    }

    for conflict in conflicts:
        # Unknown/invalid severities are bucketed as HIGH for safety.
        # This prevents KeyError and ensures unrecognised severities
        # never silently pass through as non-blocking.
        bucket = conflict.severity if conflict.severity in categorized else Severity.HIGH
        categorized[bucket].append(conflict)

    return categorized
