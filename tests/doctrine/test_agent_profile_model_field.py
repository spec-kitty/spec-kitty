"""Tests for the optional per-profile ``model``/``effort`` field (WP04, FR-005).

The field must reach the DOMAIN model (``AgentProfile`` in ``profile.py``),
not merely the generated schema — ``AgentProfile``'s ``model_config`` has no
explicit ``extra`` setting, which defaults to Pydantic v2's ``"ignore"``, so
an unknown key is silently dropped. This test asserts the value is present
on the *loaded* ``AgentProfile`` object.

NFR-003 back-compat: existing profiles without the field must load unchanged.

#5117 (FR-011): the class at the bottom of this module, ``TestModelSlotEndToEnd``,
additionally pins the one link nothing else tests -- consumer YAML on disk ->
``AgentProfileRepository`` load -> ``_compute_recommendation``'s dispatch
routing advisory. That is the evidence for the #5117 KEEP verdict recorded on
``schema_models.py``'s ``preferred_model`` field.
"""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

import charter.model_routing as charter_model_routing
from charter.model_routing import CatalogLoadResult
from charter.offering.agent_profiles.profile import AgentProfile
from charter.offering.agent_profiles.repository import AgentProfileRepository

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

_BASE = {
    "profile-id": "test-model-field",
    "name": "Test Profile",
    "purpose": "Test purpose",
    "specialization": {"primary-focus": "Testing"},
    "roles": ["implementer"],
}


class TestAgentProfileModelEffortField:
    def test_model_field_reaches_domain_model(self):
        """A YAML profile with ``model:`` exposes it on the loaded AgentProfile.

        This is the load-bearing assertion: it proves the value reaches the
        domain object, not just schema validation. Pre-fix, this fails
        because ``AgentProfile`` has no ``preferred_model``/``model`` field
        and ``extra="ignore"`` (the Pydantic v2 default for this model)
        silently drops the unknown ``model`` key.
        """
        profile = AgentProfile(**_BASE, model="opus")
        assert profile.preferred_model == "opus"

    def test_effort_field_reaches_domain_model(self):
        """A YAML profile with ``effort:`` exposes it on the loaded AgentProfile."""
        profile = AgentProfile(**_BASE, effort="high")
        assert profile.effort == "high"

    def test_both_model_and_effort_fields_reach_domain_model(self):
        profile = AgentProfile(**_BASE, model="sonnet", effort="medium")
        assert profile.preferred_model == "sonnet"
        assert profile.effort == "medium"

    def test_model_and_effort_default_to_none(self):
        """A profile that never declares model/effort still loads (NFR-003)."""
        profile = AgentProfile(**_BASE)
        assert profile.preferred_model is None
        assert profile.effort is None

    def test_existing_profile_without_field_loads_unchanged(self):
        """Back-compat (NFR-003): a profile missing model/effort is unaffected.

        Uses a realistic full profile shape (not just the minimal base) to
        prove the addition does not perturb any other field or validation
        path for profiles authored before this WP.
        """
        data = {
            "profile-id": "legacy-profile",
            "name": "Legacy Profile",
            "purpose": "Exercises pre-existing profile shape",
            "specialization": {"primary-focus": "Legacy behavior"},
            "roles": ["implementer"],
            "routing-priority": 75,
            "max-concurrent-tasks": 3,
        }
        profile = AgentProfile(**data)
        assert profile.routing_priority == 75
        assert profile.max_concurrent_tasks == 3
        assert profile.preferred_model is None
        assert profile.effort is None

    def test_attribute_name_avoids_protected_model_namespace(self):
        """The Python attribute is ``preferred_model``, never ``model``/``model_*``.

        Pydantic v2 reserves the ``model_`` prefix for its own namespace; the
        fixed contract aliases the YAML key ``model`` to the Python attribute
        ``preferred_model`` to avoid any collision or warning.
        """
        assert hasattr(AgentProfile, "model_fields")
        assert "preferred_model" in AgentProfile.model_fields
        field_info = AgentProfile.model_fields["preferred_model"]
        assert field_info.alias == "model"
        effort_info = AgentProfile.model_fields["effort"]
        assert effort_info.alias == "effort"


class TestSchemaExposesModelEffort:
    """The generated JSON-schema contract MUST expose ``model``/``effort``.

    ``AgentProfileSchema`` has ``extra="forbid"``, so if the schema source did
    not register these fields (e.g. a bare ``model`` attribute that fails to
    register), a profile declaring ``model:`` would be *rejected* by
    schema validation despite the domain model accepting it — a silent
    contract/runtime mismatch. Guard both the schema-source model and the
    generated ``by_alias`` JSON schema.
    """

    def test_schema_source_registers_fields_with_aliases(self):
        from charter.offering.agent_profiles.schema_models import AgentProfileSchema

        assert "preferred_model" in AgentProfileSchema.model_fields
        assert AgentProfileSchema.model_fields["preferred_model"].alias == "model"
        assert "effort" in AgentProfileSchema.model_fields

    def test_generated_json_schema_exposes_model_and_effort(self):
        from charter.offering.agent_profiles.schema_models import AgentProfileSchema

        props = AgentProfileSchema.model_json_schema(by_alias=True)["properties"]
        assert "model" in props, "profiles declaring model: would fail schema validation"
        assert "effort" in props


class TestDeprecatedScalarRoleStandaloneValid:
    """Fixture-proof for WP03/FR-002's AC-1 premise (model layer only, no new
    runtime code here — C-004's own annotation for this file).

    A profile using the deprecated scalar ``role:`` field (instead of the
    canonical ``roles:`` list) validates successfully *standalone* via
    ``AgentProfile.model_validate`` — ``_coerce_scalar_role``
    (``profile.py``) coerces it into ``roles: [<value>]`` and only warns.
    This is the same shape ``pack_validator.py``'s existing generic per-file
    schema scan already accepts without a ``schema_invalid`` error. WP03's
    pack-level ATDD test (``test_pack_validator.py``) documents why a
    *merge-time* failure of this same-shaped fixture (colliding with a
    real built-in profile's already-resolved ``roles:``) is a distinct,
    legitimate ``profile_skipped`` case — this test pins the standalone-valid
    half of that premise.
    """

    def test_deprecated_scalar_role_validates_standalone(self):
        data = {
            "profile-id": "analyst-annie",
            "role": "implementer",
            "name": "Override",
            "purpose": "test purpose",
            "specialization": {"primary-focus": "test focus"},
        }

        with pytest.warns(DeprecationWarning, match="scalar 'role:' field is deprecated"):
            profile = AgentProfile.model_validate(data)

        assert profile.roles == ["implementer"]


def _write_consumer_profile_yaml(path: Path, *, model_id: str) -> None:
    """Write a minimal, valid consumer profile YAML declaring ``model:``.

    Matches the repository's ``*.agent.yaml`` glob (``repository.py:37``) and
    reuses the ``_BASE`` shape plus the ``model`` alias key under test.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {**_BASE, "profile-id": "consumer-model-profile", "model": model_id}
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)


class TestModelSlotEndToEnd:
    """Disk -> ``AgentProfileRepository`` -> dispatch routing advisory.

    The alias/mapping half of the chain (YAML ``model:`` -> ``AgentProfile.
    preferred_model``) is already pinned above by ``TestAgentProfileModelEffortField``,
    and the evaluator's dual-candidate emission is pinned by
    ``test_model_task_routing_evaluator.py``. The one untested link is this
    one: a profile YAML written to disk, loaded through the repository, and
    carried all the way to ``_compute_recommendation``'s advisory.
    """

    _MODEL_ID = "claude-test-model-id"

    def test_disk_profile_model_reaches_dispatch_advisory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Charter model-task-routing catalogue is not guaranteed to be
        # non-stale forever; force a fresh, non-stale wrapper around the real
        # loaded catalog so this test never depends on wall-clock freshness.
        real = charter_model_routing.load()
        assert real is not None, "shipped model-to-task_type catalog failed to load"
        monkeypatch.setattr(
            charter_model_routing,
            "load",
            lambda *a, **k: CatalogLoadResult(catalog=real.catalog, is_stale=False),
        )

        profiles_dir = tmp_path / "profiles"
        _write_consumer_profile_yaml(profiles_dir / "consumer-model.agent.yaml", model_id=self._MODEL_ID)

        repo = AgentProfileRepository(project_dir=profiles_dir)
        profile = repo.get("consumer-model-profile")

        assert profile is not None, "consumer profile failed to load"
        skipped_paths = {entry.path for entry in repo.skipped_profiles()}
        consumer_path = str(profiles_dir / "consumer-model.agent.yaml")
        assert consumer_path not in skipped_paths, "consumer profile was silently skipped -- the test would be vacuous"
        assert profile.preferred_model == self._MODEL_ID

        from specify_cli.invocation.executor import _compute_recommendation
        from specify_cli.invocation.task_class_map import task_type_for_verb

        task_type = task_type_for_verb("implement")
        assert task_type == "code-implementation"

        rec = _compute_recommendation(profile, "implement")

        assert rec is not None
        assert rec.profile_candidate is not None
        assert rec.profile_candidate.model_id == self._MODEL_ID
        assert rec.profile_candidate.source == "profile"
