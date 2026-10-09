"""Override-precedence tests for the step model-tier offer seam (FR-008;
NFR-003; D4/C-002; WP08).

Pins the ``evaluate()`` live consumer of a step's ``recommended_model_tier``
offer, wired through ``charter.offering.missions.step_offer_seam``:

- With a charter/runtime override present, the override wins 100% of the
  time -- the step's offer is surfaced only as advisory provenance, never
  as the effective value (NFR-003, C-002: no routing-authority leak).
- With no override, the step's offer is used as the effective value.
- With neither supplied, the evaluator's ``model_tier`` result is ``None``
  and every other field is byte-for-byte identical to calling
  ``evaluate()`` with no keyword arguments at all -- proving the new
  seam is behavior-preserving for the (today: universal) callers that
  pass no offer.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.unit]

_PROFILE_BASE = {
    "profile-id": "test-override-precedence-profile",
    "name": "Test Override Precedence Profile",
    "purpose": "Exercise the step model-tier offer seam",
    "specialization": {"primary-focus": "Testing"},
    "roles": ["implementer"],
}


def _build_profile(**overrides: object):
    from charter.offering.agent_profiles.profile import AgentProfile

    return AgentProfile(**_PROFILE_BASE, **overrides)


def _build_catalog(document: dict[str, object]):
    from charter.offering.model_task_routing.models import ModelToTaskType

    return ModelToTaskType.model_validate(document)


def _base_document() -> dict[str, object]:
    """A single-model catalog -- the offer/override resolution under test
    is independent of catalog scoring, so a minimal fixture suffices."""
    return {
        "schema_version": "1.0",
        "generated_at": "2025-06-01T12:00:00Z",
        "task_types": [
            {"id": "implement", "title": "Implement"},
        ],
        "models": [
            {
                "id": "solo-model",
                "provider": "acme",
                "task_fit": [
                    {"task_type": "implement", "score": 0.8, "confidence": "high"},
                ],
                "cost": {"tier": "medium"},
            },
        ],
        "routing_policy": {
            "objective": "quality_first",
            "weights": {"quality": 1.0, "cost": 0.0, "risk": 0.0, "latency": 0.0},
            "tier_constraints": [],
            "override_policy": {"mode": "advisory", "require_reason": False},
        },
        "sources": [
            {
                "name": "test fixture",
                "url": "https://example.com",
                "access_method": "manual",
                "snapshot_at": "2025-06-01T00:00:00Z",
            }
        ],
    }


def test_override_wins_over_step_offer_every_time() -> None:
    """NFR-003: an override present alongside a step offer -- the override
    is the effective value in 100% of cases; the step offer is preserved
    only as advisory provenance, never as ``effective`` (C-002)."""
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(_base_document())
    profile = _build_profile()

    recommendation = evaluate(
        catalog,
        "implement",
        profile,
        recommended_model_tier="low",
        model_tier_override="premium",
    )

    assert recommendation.model_tier is not None
    assert recommendation.model_tier.effective == "premium"
    assert recommendation.model_tier.source == "override"
    assert recommendation.model_tier.offer == "low"


@pytest.mark.parametrize(
    ("step_offer", "override"),
    [
        ("low", "premium"),
        ("premium", "low"),
        ("medium", "medium"),
    ],
)
def test_override_wins_regardless_of_agreement_with_offer(
    step_offer: str, override: str
) -> None:
    """The override wins whether it agrees, disagrees, or coincides with
    the step's offer -- precedence is unconditional, not a tie-break."""
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(_base_document())
    profile = _build_profile()

    recommendation = evaluate(
        catalog,
        "implement",
        profile,
        recommended_model_tier=step_offer,
        model_tier_override=override,
    )

    assert recommendation.model_tier is not None
    assert recommendation.model_tier.effective == override
    assert recommendation.model_tier.source == "override"


def test_step_offer_used_when_no_override_present() -> None:
    """With no charter/runtime override, the step's advisory offer becomes
    the effective value."""
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(_base_document())
    profile = _build_profile()

    recommendation = evaluate(
        catalog,
        "implement",
        profile,
        recommended_model_tier="high",
    )

    assert recommendation.model_tier is not None
    assert recommendation.model_tier.effective == "high"
    assert recommendation.model_tier.source == "offer"
    assert recommendation.model_tier.offer == "high"


def test_no_offer_and_no_override_yields_no_model_tier_resolution() -> None:
    """Neither supplied -> ``model_tier`` is ``None`` (not a resolution
    with empty fields) -- the absent-offer state is explicit."""
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(_base_document())
    profile = _build_profile()

    recommendation = evaluate(catalog, "implement", profile)

    assert recommendation.model_tier is None


def test_offer_seam_does_not_change_catalog_or_profile_candidates() -> None:
    """The step model-tier offer/override is additive-only: it never
    influences ``catalog_candidate``/``profile_candidate`` scoring, so
    doctrine cannot leak into routing authority (C-002)."""
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(_base_document())
    profile = _build_profile(model="human-declared-model")

    baseline = evaluate(catalog, "implement", profile)
    with_offer = evaluate(
        catalog,
        "implement",
        profile,
        recommended_model_tier="low",
        model_tier_override="premium",
    )

    assert with_offer.candidates == baseline.candidates
    assert with_offer.catalog_candidate == baseline.catalog_candidate
    assert with_offer.profile_candidate == baseline.profile_candidate
    assert with_offer.override_mode == baseline.override_mode
    assert with_offer.objective == baseline.objective


def test_evaluate_with_no_offer_arguments_is_unchanged_from_pre_wp08_call() -> None:
    """Behavior-preservation guard: calling ``evaluate()`` exactly as
    every pre-WP08 caller does (positional args only, no keyword offer
    arguments) produces a recommendation whose non-``model_tier`` fields
    are identical to a call that explicitly passes ``None`` for both new
    keyword arguments."""
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(_base_document())
    profile = _build_profile()

    legacy_call = evaluate(catalog, "implement", profile)
    explicit_none_call = evaluate(
        catalog,
        "implement",
        profile,
        recommended_model_tier=None,
        model_tier_override=None,
    )

    assert legacy_call == explicit_none_call
    assert legacy_call.model_tier is None
