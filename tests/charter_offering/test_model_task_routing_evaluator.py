"""Red-first tests for the routing evaluator (FR-003, NFR-004, C-004).

Pins the deterministic objective-function scorer that consumes WP01's
loaded ``ModelToTaskType`` catalog + a ``task_type`` + a WP04
``AgentProfile`` and produces a recommendation:

- ``objective: quality_first`` is the *capability lever* -- it must rank
  the strongest task-fit model highest for a high-judgment task_type,
  even when the catalog's raw weights would not otherwise favor it.
- ``tier_constraints`` caps the winner: a model excluded by a
  ``max_tier`` constraint must never win, even with the best task_fit.
- ``override_policy: advisory`` emits BOTH the catalog pick and the
  profile-declared model as provenance-tagged candidates -- neither is
  enforced (C-004: gated/required are out of scope; only advisory is
  exercised here).
- The evaluator is pure/deterministic (NFR-004): same catalog +
  task_type + profile -> identical recommendation, and it must not
  raise on "no match"/empty task_fit edge cases.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.unit]

_PROFILE_BASE = {
    "profile-id": "test-routing-profile",
    "name": "Test Routing Profile",
    "purpose": "Exercise the routing evaluator",
    "specialization": {"primary-focus": "Testing"},
    "roles": ["implementer"],
}


def _build_profile(**overrides: object):
    from charter.offering.agent_profiles.profile import AgentProfile

    return AgentProfile(**_PROFILE_BASE, **overrides)


def _build_catalog(document: dict[str, object]):
    from charter.offering.model_task_routing.models import ModelToTaskType

    return ModelToTaskType.model_validate(document)


def _base_document(
    *,
    objective: str = "quality_first",
    tier_constraints: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """A two-model catalog for a high-judgment task_type.

    ``strong-model`` has the best task_fit but is ``premium`` cost tier;
    ``weak-model`` has a lower task_fit but is a cheap ``low`` cost tier.
    Weights are deliberately cost/latency-heavy (NOT quality-heavy) so a
    naive weighted-sum-only scorer would pick ``weak-model`` -- proving
    that ``quality_first`` is a real capability lever, not an artifact of
    the weights.
    """
    return {
        "schema_version": "1.0",
        "generated_at": "2025-06-01T12:00:00Z",
        "task_types": [
            {"id": "high-judgment-review", "title": "High Judgment Review"},
        ],
        "models": [
            {
                "id": "strong-model",
                "provider": "acme",
                "task_fit": [
                    {
                        "task_type": "high-judgment-review",
                        "score": 0.95,
                        "confidence": "high",
                        "rationale": "Best fit for high-judgment review",
                    }
                ],
                "cost": {"tier": "premium"},
                "latency_tier": "high",
            },
            {
                "id": "weak-model",
                "provider": "acme",
                "task_fit": [
                    {
                        "task_type": "high-judgment-review",
                        "score": 0.4,
                        "confidence": "medium",
                    }
                ],
                "cost": {"tier": "low"},
                "latency_tier": "low",
            },
        ],
        "routing_policy": {
            "objective": objective,
            "weights": {
                "quality": 0.1,
                "cost": 0.4,
                "risk": 0.1,
                "latency": 0.4,
            },
            "tier_constraints": tier_constraints or [],
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


def test_quality_first_ranks_strongest_fit_model() -> None:
    """quality_first is the capability lever: strongest task_fit wins.

    Weights here are cost/latency-heavy, not quality-heavy -- if the
    scorer merely applied the weighted sum, ``weak-model`` (cheap, low
    latency) would win. Under ``quality_first`` the strongest-fit model
    must win regardless.
    """
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(_base_document(objective="quality_first"))
    profile = _build_profile()

    recommendation = evaluate(catalog, "high-judgment-review", profile)

    catalog_candidate = recommendation.catalog_candidate
    assert catalog_candidate is not None
    assert catalog_candidate.model_id == "strong-model"
    assert catalog_candidate.source == "catalog"


def test_tier_constraint_caps_the_winner() -> None:
    """A tier_constraints cap excludes the best-fit model from winning.

    Same catalog as above, but a ``max_tier: medium`` constraint on
    ``high-judgment-review`` excludes ``strong-model`` (premium tier)
    entirely -- ``weak-model`` (low tier) must win instead, even though
    it has the weaker task_fit and the objective is quality_first.
    """
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(
        _base_document(
            objective="quality_first",
            tier_constraints=[{"task_type": "high-judgment-review", "max_tier": "medium"}],
        )
    )
    profile = _build_profile()

    recommendation = evaluate(catalog, "high-judgment-review", profile)

    catalog_candidate = recommendation.catalog_candidate
    assert catalog_candidate is not None
    assert catalog_candidate.model_id == "weak-model"


def test_advisory_emits_both_catalog_and_profile_candidates_with_provenance() -> None:
    """Under advisory, the catalog pick and the profile's declared model are
    BOTH surfaced as provenance-tagged candidates -- neither is enforced,
    even when they disagree."""
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(_base_document(objective="quality_first"))
    profile = _build_profile(model="human-declared-model")

    recommendation = evaluate(catalog, "high-judgment-review", profile)

    sources = {c.source: c.model_id for c in recommendation.candidates}
    assert sources == {
        "catalog": "strong-model",
        "profile": "human-declared-model",
    }
    assert recommendation.override_mode == "advisory"


def test_advisory_with_no_profile_declaration_surfaces_catalog_only() -> None:
    """When the profile has no declared model, only the catalog candidate
    is surfaced -- no phantom profile candidate is fabricated."""
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(_base_document(objective="quality_first"))
    profile = _build_profile()  # no model= override -> preferred_model is None

    recommendation = evaluate(catalog, "high-judgment-review", profile)

    assert [c.source for c in recommendation.candidates] == ["catalog"]


def test_no_match_task_type_returns_no_catalog_candidate_without_raising() -> None:
    """A task_type absent from every model's task_fit is a "no match" edge
    case (NFR-004): no catalog candidate, no raise. A profile-declared
    model is still surfaced (advisory candidates are independent)."""
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(_base_document(objective="quality_first"))
    profile = _build_profile(model="human-declared-model")

    recommendation = evaluate(catalog, "no-such-task-type", profile)

    assert recommendation.catalog_candidate is None
    assert recommendation.candidates == (
        recommendation.profile_candidate,
    )
    assert recommendation.profile_candidate is not None
    assert recommendation.profile_candidate.model_id == "human-declared-model"


def test_no_match_and_no_profile_declaration_yields_empty_candidates() -> None:
    """Both catalog and profile miss -> empty candidates tuple, not a raise."""
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(_base_document(objective="quality_first"))
    profile = _build_profile()

    recommendation = evaluate(catalog, "no-such-task-type", profile)

    assert recommendation.candidates == ()
    assert recommendation.catalog_candidate is None
    assert recommendation.profile_candidate is None


def test_evaluate_is_deterministic_across_repeated_calls() -> None:
    """NFR-004: same catalog + task_type + profile -> identical recommendation,
    called repeatedly (pure function, no hidden state/caching)."""
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(_base_document(objective="quality_first"))
    profile = _build_profile(model="human-declared-model", effort="high")

    first = evaluate(catalog, "high-judgment-review", profile)
    second = evaluate(catalog, "high-judgment-review", profile)

    assert first == second
    assert first.candidates == second.candidates


def test_balanced_objective_uses_full_weighted_sum() -> None:
    """Under a non-quality_first objective, the plain weighted sum applies:
    with cost/latency-heavy weights, the cheap low-latency model wins over
    the higher-fit but premium/high-latency model."""
    from charter.offering.model_task_routing.evaluator import evaluate

    catalog = _build_catalog(_base_document(objective="balanced"))
    profile = _build_profile()

    recommendation = evaluate(catalog, "high-judgment-review", profile)

    catalog_candidate = recommendation.catalog_candidate
    assert catalog_candidate is not None
    assert catalog_candidate.model_id == "weak-model"
