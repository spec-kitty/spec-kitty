"""Core significance models, scoring engine, and policy parsing.

Provides foundational frozen Pydantic models for significance scoring:
- SignificanceDimension: atomic unit of significance scoring (one of 6 fixed dimensions)
- RoutingBand: significance tier determining gating behavior (low/medium/high)
- HardTriggerClass: conditions that override numeric scoring and force hard-gate
- SignificanceScore: composite evaluation result capturing full significance assessment
- TimeoutPolicy: configuration governing timeout window for decisions
- evaluate_significance(): pure function for deterministic significance evaluation
- parse_band_cutoffs_from_policy(): extract band cutoffs from MissionPolicySnapshot

All models use ConfigDict(frozen=True, extra="forbid").
All registries are fixed in V1 (no custom dimensions or triggers).
"""

# Internalized from spec-kitty-runtime 0.4.3 as part of
# `shared-package-boundary-cutover-01KQ22DS` (mission). See
# `runtime-standalone-package-retirement-01KQ20Z8` for the upstream
# public-API inventory.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kernel.clock import datetime
from runtime.next._internal_runtime.schema import RACIRoleBinding

if TYPE_CHECKING:
    from runtime.next._internal_runtime.schema import MissionPolicySnapshot


# ---------------------------------------------------------------------------
# Fixed dimension names (V1, C-001)
# ---------------------------------------------------------------------------

DIMENSION_NAMES: frozenset[str] = frozenset({
    "user_customer_impact",
    "architectural_system_impact",
    "data_security_compliance_impact",
    "operational_reliability_impact",
    "financial_commercial_impact",
    "cross_team_blast_radius",
})


# ---------------------------------------------------------------------------
# T001: SignificanceDimension model
# ---------------------------------------------------------------------------

class SignificanceDimension(BaseModel):
    """A single significance dimension with a name and score.

    Represents one of the six fixed impact dimensions. Score must be 0–3.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., min_length=1)
    score: int = Field(..., ge=0, le=3)
    description: str = ""

    @model_validator(mode="after")
    def _validate_dimension(self) -> SignificanceDimension:
        if self.name not in DIMENSION_NAMES:
            raise ValueError(
                f"Unknown dimension name: {self.name!r}. "
                f"Valid dimensions: {sorted(DIMENSION_NAMES)}"
            )
        return self


# ---------------------------------------------------------------------------
# T002: RoutingBand model with default bands
# ---------------------------------------------------------------------------

class RoutingBand(BaseModel):
    """Significance tier determining gating behavior.

    Three bands partition the 0–18 composite score range:
    - low (0–6): auto-proceed, logged
    - medium (7–11): soft gate
    - high (12–18): hard gate
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Literal["low", "medium", "high"]
    min_score: int = Field(..., ge=0, le=18)
    max_score: int = Field(..., ge=0, le=18)

    @model_validator(mode="after")
    def _validate_range(self) -> RoutingBand:
        if self.min_score > self.max_score:
            raise ValueError(
                f"min_score ({self.min_score}) > max_score ({self.max_score})"
            )
        return self


DEFAULT_BANDS: tuple[RoutingBand, ...] = (
    RoutingBand(name="low", min_score=0, max_score=6),
    RoutingBand(name="medium", min_score=7, max_score=11),
    RoutingBand(name="high", min_score=12, max_score=18),
)


# ---------------------------------------------------------------------------
# T004: Band cutoff validation logic
# ---------------------------------------------------------------------------

def validate_band_cutoffs(cutoffs: dict[str, list[int]]) -> None:
    """Validate custom band cutoffs for contiguous, non-overlapping coverage of 0–18.

    Args:
        cutoffs: Mapping of band name to [min, max] pair.
            Example: {"low": [0, 5], "medium": [6, 10], "high": [11, 18]}

    Raises:
        ValueError: If validation fails with a specific error message.
    """
    expected_keys = {"low", "medium", "high"}
    provided_keys = set(cutoffs.keys())

    if provided_keys != expected_keys:
        raise ValueError(
            f"Expected exactly 3 bands (low, medium, high), got: {sorted(provided_keys)}"
        )

    for band_name, pair in cutoffs.items():
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError(
                f"Band '{band_name}' must be a [min, max] pair, got: {pair!r}"
            )

    # Sort bands by min_score for contiguity checks
    sorted_bands = sorted(cutoffs.items(), key=lambda item: item[1][0])

    for band_name, (lo, hi) in sorted_bands:
        if lo > hi:
            raise ValueError(
                f"Band '{band_name}': min_score ({lo}) > max_score ({hi})"
            )

    # Check boundaries
    first_name, (first_lo, _) = sorted_bands[0]
    if first_lo != 0:
        raise ValueError(
            f"Band '{first_name}' must start at 0, starts at {first_lo}"
        )

    last_name, (_, last_hi) = sorted_bands[-1]
    if last_hi != 18:
        raise ValueError(
            f"Band '{last_name}' must end at 18, ends at {last_hi}"
        )

    # Check contiguity and no overlaps
    for i in range(1, len(sorted_bands)):
        prev_name, (_, prev_hi) = sorted_bands[i - 1]
        next_name, (next_lo, _) = sorted_bands[i]

        if next_lo > prev_hi + 1:
            raise ValueError(
                f"Gap between band '{prev_name}' (max={prev_hi}) "
                f"and '{next_name}' (min={next_lo})"
            )
        if next_lo <= prev_hi:
            raise ValueError(
                f"Overlap between band '{prev_name}' (max={prev_hi}) "
                f"and '{next_name}' (min={next_lo})"
            )


def make_routing_bands(
    cutoffs: dict[str, list[int]] | None = None,
) -> tuple[RoutingBand, ...]:
    """Create routing bands from custom cutoffs or return defaults.

    Args:
        cutoffs: Optional dict mapping band names to [min, max] pairs.
            If None, returns DEFAULT_BANDS.

    Returns:
        Tuple of RoutingBand instances sorted by min_score.

    Raises:
        ValueError: If cutoffs are invalid.
    """
    if cutoffs is None:
        return DEFAULT_BANDS

    validate_band_cutoffs(cutoffs)

    bands = []
    for name in ("low", "medium", "high"):
        lo, hi = cutoffs[name]
        bands.append(RoutingBand(name=name, min_score=lo, max_score=hi))

    return tuple(sorted(bands, key=lambda b: b.min_score))


# ---------------------------------------------------------------------------
# T003: HardTriggerClass model with fixed registry
# ---------------------------------------------------------------------------

class HardTriggerClass(BaseModel):
    """A predefined condition that overrides numeric scoring and forces hard-gate.

    V1 defines exactly five fixed hard-trigger classes (C-003).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    class_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)


HARD_TRIGGER_REGISTRY: dict[str, HardTriggerClass] = {
    "production_data_destructive": HardTriggerClass(
        class_id="production_data_destructive",
        description="Production data-destructive or schema-impacting changes",
    ),
    "security_privacy_access_control": HardTriggerClass(
        class_id="security_privacy_access_control",
        description="Security/privacy/access-control changes",
    ),
    "legal_compliance_regulatory": HardTriggerClass(
        class_id="legal_compliance_regulatory",
        description="Legal/compliance/regulatory impact",
    ),
    "billing_financial_commitment": HardTriggerClass(
        class_id="billing_financial_commitment",
        description="Billing/financial commitment changes",
    ),
    "architecture_foundation": HardTriggerClass(
        class_id="architecture_foundation",
        description="Architecture-foundation changes (language, framework, runtime, datastore, infrastructure)",
    ),
}


def resolve_hard_triggers(class_ids: list[str]) -> tuple[HardTriggerClass, ...]:
    """Resolve hard-trigger class IDs to HardTriggerClass instances.

    Args:
        class_ids: List of hard-trigger class ID strings.

    Returns:
        Tuple of resolved HardTriggerClass instances.

    Raises:
        ValueError: For unknown class_ids.
    """
    resolved = []
    for cid in class_ids:
        if cid not in HARD_TRIGGER_REGISTRY:
            raise ValueError(
                f"Unknown hard-trigger class: {cid!r}. "
                f"Valid: {sorted(HARD_TRIGGER_REGISTRY.keys())}"
            )
        resolved.append(HARD_TRIGGER_REGISTRY[cid])
    return tuple(resolved)


# ---------------------------------------------------------------------------
# T005: Validation helpers and exports
# ---------------------------------------------------------------------------

def validate_dimension_scores(scores: dict[str, int]) -> None:
    """Validate that dimension scores contain exactly the 6 required dimensions, each scored 0–3.

    Args:
        scores: Mapping of dimension name to score (0–3).

    Raises:
        ValueError: If dimensions are missing/extra or scores are out of range.
    """
    provided = set(scores.keys())
    if provided != DIMENSION_NAMES:
        missing = DIMENSION_NAMES - provided
        extra = provided - DIMENSION_NAMES
        parts = []
        if missing:
            parts.append(f"missing: {sorted(missing)}")
        if extra:
            parts.append(f"unexpected: {sorted(extra)}")
        raise ValueError(
            f"Dimension scores must contain exactly {len(DIMENSION_NAMES)} dimensions. "
            f"{', '.join(parts)}"
        )
    for name, score in scores.items():
        if not (0 <= score <= 3):
            raise ValueError(f"Dimension '{name}' score must be 0-3, got {score}")


# ---------------------------------------------------------------------------
# T006: SignificanceScore model
# ---------------------------------------------------------------------------

class SignificanceScore(BaseModel):
    """Composite evaluation result capturing the full significance assessment.

    Contains all six dimension scores, the computed composite, the numeric band,
    any hard-trigger overrides, and the effective routing band.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    dimensions: tuple[SignificanceDimension, ...] = Field(...)
    composite: int = Field(..., ge=0, le=18)
    band: RoutingBand
    hard_trigger_classes: tuple[HardTriggerClass, ...] = Field(default_factory=tuple)
    effective_band: RoutingBand

    @model_validator(mode="after")
    def _validate_score(self) -> SignificanceScore:
        # Exactly 6 dimensions, one per fixed name
        dim_names = {d.name for d in self.dimensions}
        if dim_names != DIMENSION_NAMES:
            missing = DIMENSION_NAMES - dim_names
            extra = dim_names - DIMENSION_NAMES
            parts = []
            if missing:
                parts.append(f"missing: {sorted(missing)}")
            if extra:
                parts.append(f"unexpected: {sorted(extra)}")
            raise ValueError(
                f"dimensions must contain exactly 6 fixed dimensions. "
                f"{', '.join(parts)}"
            )

        # composite must equal sum of dimension scores
        expected = sum(d.score for d in self.dimensions)
        if self.composite != expected:
            raise ValueError(
                f"composite ({self.composite}) != sum of scores ({expected})"
            )

        # effective_band must be 'high' when hard triggers present
        if self.hard_trigger_classes and self.effective_band.name != "high":
            raise ValueError(
                "effective_band must be 'high' when hard_trigger_classes present"
            )

        # When no hard triggers, effective_band must equal band
        if not self.hard_trigger_classes and self.effective_band != self.band:
            raise ValueError(
                "effective_band must equal band when no hard triggers"
            )

        return self


# ---------------------------------------------------------------------------
# T007: evaluate_significance() pure function
# ---------------------------------------------------------------------------

def evaluate_significance(
    dimension_scores: dict[str, int],
    hard_trigger_classes: list[str] | None = None,
    band_cutoffs: dict[str, list[int]] | None = None,
) -> SignificanceScore:
    """Evaluate the significance of a decision.

    Pure function: same inputs always produce identical output.
    No side effects, no randomness, no external state.

    Args:
        dimension_scores: Mapping of dimension name to score (0-3) for all 6 dimensions.
        hard_trigger_classes: Optional list of hard-trigger class IDs.
        band_cutoffs: Optional custom band cutoffs. If None, defaults are used.

    Returns:
        A fully computed SignificanceScore.

    Raises:
        ValueError: If inputs are invalid.
    """
    # Validate dimension scores
    validate_dimension_scores(dimension_scores)

    # Build SignificanceDimension instances, sorted by name for deterministic ordering
    dims = tuple(sorted(
        [SignificanceDimension(name=k, score=v) for k, v in dimension_scores.items()],
        key=lambda d: d.name,
    ))

    # Compute composite
    composite = sum(dimension_scores.values())

    # Build routing bands
    bands = make_routing_bands(band_cutoffs)

    # Resolve numeric band
    band: RoutingBand | None = None
    for b in bands:
        if b.min_score <= composite <= b.max_score:
            band = b
            break

    if band is None:
        raise ValueError(
            f"composite score {composite} does not fall within any band"
        )

    # Resolve hard triggers
    triggers = resolve_hard_triggers(hard_trigger_classes or [])

    # Hard triggers override to high band.
    effective_band = next(b for b in bands if b.name == "high") if triggers else band

    return SignificanceScore(
        dimensions=dims,
        composite=composite,
        band=band,
        hard_trigger_classes=triggers,
        effective_band=effective_band,
    )


# ---------------------------------------------------------------------------
# T008: TimeoutPolicy model
# ---------------------------------------------------------------------------

class TimeoutPolicy(BaseModel):
    """Configuration governing the timeout window for decisions.

    Default timeout is 600 seconds (10 minutes). Per-decision override
    can be set by a responsible human at decision time.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    default_timeout_seconds: int = Field(default=600, gt=0)
    per_decision_timeout_seconds: int | None = Field(default=None)

    @property
    def effective_timeout_seconds(self) -> int:
        """Return the effective timeout: per-decision override if set, else default."""
        if self.per_decision_timeout_seconds is not None:
            return self.per_decision_timeout_seconds
        return self.default_timeout_seconds

    @model_validator(mode="after")
    def _validate_timeouts(self) -> TimeoutPolicy:
        if self.per_decision_timeout_seconds is not None and self.per_decision_timeout_seconds <= 0:
            raise ValueError(
                f"per_decision_timeout_seconds must be > 0, got {self.per_decision_timeout_seconds}"
            )
        return self


# ---------------------------------------------------------------------------
# T009: parse_band_cutoffs_from_policy()
# ---------------------------------------------------------------------------

def parse_band_cutoffs_from_policy(
    policy: MissionPolicySnapshot,
) -> dict[str, list[int]] | None:
    """Extract band cutoffs from policy extras.

    Returns None if not configured (use defaults).
    Raises ValueError if configured but invalid.
    """
    cutoffs = policy.extras.get("significance_band_cutoffs")
    if cutoffs is None:
        return None
    if not isinstance(cutoffs, dict):
        raise ValueError(
            f"significance_band_cutoffs must be a dict, got {type(cutoffs).__name__}"
        )
    for band_name, bounds in cutoffs.items():
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise ValueError(
                f"Band '{band_name}' cutoff must be [min, max], got {bounds}"
            )
        if not all(isinstance(b, int) for b in bounds):
            raise ValueError(
                f"Band '{band_name}' cutoff values must be integers"
            )
    validate_band_cutoffs(cutoffs)
    return cutoffs


# ---------------------------------------------------------------------------
# T011: SignificanceEvaluatedPayload
# ---------------------------------------------------------------------------

class SignificanceEvaluatedPayload(BaseModel):
    """Event payload emitted when a decision's significance is scored and routed.

    Persisted in JSONL event log. Field names align with
    contracts/significance-evaluation.yaml.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(..., min_length=1)
    decision_id: str = Field(..., min_length=1)
    step_id: str = Field(..., min_length=1)
    significance_score: dict[str, Any]  # Serialized SignificanceScore
    hard_trigger_classes: tuple[str, ...] = Field(default_factory=tuple)
    effective_band: Literal["low", "medium", "high"]
    actor: RACIRoleBinding  # System actor (service/runtime)


# ---------------------------------------------------------------------------
# T012: TimeoutExpiredPayload
# ---------------------------------------------------------------------------

class TimeoutExpiredPayload(BaseModel):
    """Event payload emitted when a decision exceeds its configured timeout window.

    Field names align with contracts/timeout-expired-event.yaml.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(..., min_length=1)
    decision_id: str = Field(..., min_length=1)
    step_id: str = Field(..., min_length=1)
    significance_score: dict[str, Any]  # Serialized SignificanceScore
    effective_band: Literal["medium", "high"]  # Never "low" — low auto-proceeds
    timeout_configured_seconds: int = Field(..., gt=0)
    escalation_targets: tuple[RACIRoleBinding, ...] = Field(default_factory=tuple)
    raci_snapshot: dict[str, Any]  # Serialized ResolvedRACIBinding
    actor: RACIRoleBinding  # System actor (service/runtime)


# ---------------------------------------------------------------------------
# T013: SoftGateDecision model
# ---------------------------------------------------------------------------

class SoftGateDecision(BaseModel):
    """Captures the responsible human's action on a medium-band decision.

    Per FR-005 and FR-006. Field names align with
    contracts/soft-gate-decision.yaml.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str = Field(..., min_length=1)
    action: Literal["decide_solo", "open_stand_up", "defer"]
    actor: RACIRoleBinding  # Must be human
    timestamp: datetime  # UTC
    significance_score: SignificanceScore
    participants: tuple[RACIRoleBinding, ...] = Field(default_factory=tuple)
    outcome: str | None = None  # approve/reject/defer — None until resolved
    rationale: str | None = None

    @model_validator(mode="after")
    def _validate_actor_human(self) -> SoftGateDecision:
        if self.actor.actor_type != "human":
            raise ValueError(
                f"SoftGateDecision actor must be human, got {self.actor.actor_type}"
            )
        return self


# ---------------------------------------------------------------------------
# T014: DimensionScoreOverride model
# ---------------------------------------------------------------------------

class DimensionScoreOverride(BaseModel):
    """Audit record for runtime score overrides.

    The secondary scoring path where a human adjusts template-declared scores.
    Per research R-004 and ED-4.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str = Field(..., min_length=1)
    overridden_by: RACIRoleBinding  # Must be human (FR-018)
    override_reason: str = Field(..., min_length=1)  # Mandatory justification
    original_scores: dict[str, int]  # dimension_name → before value
    new_scores: dict[str, int]  # dimension_name → after value
    override_timestamp: datetime  # UTC

    @model_validator(mode="after")
    def _validate_override(self) -> DimensionScoreOverride:
        if self.overridden_by.actor_type != "human":
            raise ValueError(
                f"Overrides must be by human actors, got {self.overridden_by.actor_type}"
            )
        # Validate that overridden dimensions exist in DIMENSION_NAMES
        for name in {**self.original_scores, **self.new_scores}:
            if name not in DIMENSION_NAMES:
                raise ValueError(f"Unknown dimension: {name}")
        return self


__all__ = [
    # Constants
    # DIMENSION_NAMES: demoted — intra-module constant used in validators;
    # no cross-module src/ from-import callers (WP01 harden-dead-symbol-gate-01KW0RJR).
    # DEFAULT_BANDS: demoted — no cross-module src/ from-import callers (WP01).
    "HARD_TRIGGER_REGISTRY",
    # Models (WP01)
    # SignificanceDimension: demoted — no cross-module src/ from-import callers (WP01).
    # RoutingBand: demoted — no cross-module src/ from-import callers (WP01).
    # HardTriggerClass: demoted — no cross-module src/ from-import callers (WP01).
    # Models (WP02)
    "SignificanceScore",
    # TimeoutPolicy: demoted — no cross-module src/ from-import callers (WP01).
    # Models (WP03)
    "SignificanceEvaluatedPayload",
    "TimeoutExpiredPayload",
    "SoftGateDecision",
    # DimensionScoreOverride: demoted — no cross-module src/ from-import callers (WP01).
    # Functions (WP01)
    # make_routing_bands: demoted — no cross-module src/ from-import callers (WP01).
    # validate_band_cutoffs: demoted — no cross-module src/ from-import callers (WP01).
    # resolve_hard_triggers: demoted — no cross-module src/ from-import callers (WP01).
    "validate_dimension_scores",
    # Functions (WP02)
    "evaluate_significance",
    "parse_band_cutoffs_from_policy",
]
