"""Unit tests for charter.activation.mission_type_profiles (WP05).

Covers:
- MissionTypeProfile.mission_type accepts any str (no Literal constraint)
- UnknownMissionTypeError carries mission_type_id and registered_ids
- resolve_mission_type_context() uses existing_mission_types() for validation
- Backward-compat: the hard-fail policy still works for truly unknown types

T034 — update ATDD test suite: MissionTypeProfile(mission_type="custom-type", ...)
       succeeds; UnknownMissionTypeError raised by resolve_mission_type_context.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML

from charter.activation.action_grain import scan_builtin_cross_grain_duplicates
from charter.activation.mission_type_profiles import (
    MissionTypeEmptyActionSequenceError,
    MissionTypeProfile,
    UnknownMissionTypeError,
    _load_mission_type_profile,
    resolve_mission_type_context,
)
from charter.activation.pack_context import PackContext
from charter.offering.base import DoctrineLayerCollisionWarning
from charter.offering.missions.mission_type_repository import MissionTypeRepository


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# T029 — MissionTypeProfile.mission_type is now str (no Literal constraint)
# ---------------------------------------------------------------------------


class TestMissionTypeProfileOpenStr:
    """MissionTypeProfile.mission_type MUST accept any string at model construction
    time. The Literal constraint was removed in T029 (FR-009).
    """

    def test_canonical_types_still_accepted(self) -> None:
        """The four canonical mission types remain valid."""
        for mt in ("software-dev", "documentation", "research", "plan"):
            profile = MissionTypeProfile(mission_type=mt)
            assert profile.mission_type == mt

    def test_custom_type_accepted_without_validation_error(self) -> None:
        """MissionTypeProfile(mission_type='custom-type') MUST NOT raise ValidationError.

        Before T029 this would fail with pydantic.ValidationError because the
        field was typed as Literal["software-dev", "documentation", "research", "plan"].
        After T029 the annotation is str — any value is accepted at model time.
        """
        profile = MissionTypeProfile(mission_type="custom-type")
        assert profile.mission_type == "custom-type"

    def test_arbitrary_string_accepted(self) -> None:
        """Any non-empty string is valid at model construction time."""
        profile = MissionTypeProfile(mission_type="compliance-audit")
        assert profile.mission_type == "compliance-audit"


# ---------------------------------------------------------------------------
# T030 — UnknownMissionTypeError carries registered_ids
# ---------------------------------------------------------------------------


class TestUnknownMissionTypeError:
    """UnknownMissionTypeError MUST include registered_ids (FR-009)."""

    def test_message_contains_mission_type_id(self) -> None:
        """The exception message MUST contain the unknown mission_type_id verbatim."""
        err = UnknownMissionTypeError("compliance-audit")
        assert "compliance-audit" in str(err)

    def test_message_contains_registered_ids_when_provided(self) -> None:
        """When registered_ids are provided, the message lists them."""
        err = UnknownMissionTypeError(
            "compliance-audit",
            registered_ids=["documentation", "plan", "research", "software-dev"],
        )
        msg = str(err)
        assert "compliance-audit" in msg
        assert "documentation" in msg
        assert "software-dev" in msg

    def test_registered_ids_attribute_is_set(self) -> None:
        """err.registered_ids MUST be the list passed at construction."""
        ids = ["documentation", "plan", "research", "software-dev"]
        err = UnknownMissionTypeError("unknown-type", registered_ids=ids)
        assert err.registered_ids == ids

    def test_registered_ids_defaults_to_empty_list(self) -> None:
        """When no registered_ids are provided, the attribute defaults to []."""
        err = UnknownMissionTypeError("something")
        assert err.registered_ids == []

    def test_mission_type_id_attribute_is_set(self) -> None:
        """err.mission_type_id MUST equal the first positional argument."""
        err = UnknownMissionTypeError("compliance-audit", registered_ids=["software-dev"])
        assert err.mission_type_id == "compliance-audit"

    def test_is_value_error_subclass(self) -> None:
        """UnknownMissionTypeError MUST remain a ValueError subclass."""
        err = UnknownMissionTypeError("bad-type")
        assert isinstance(err, ValueError)

    def test_formatted_message_matches_fr009_contract(self) -> None:
        """FR-009: message format is 'Unknown mission type X. Registered types: A, B, C.'"""
        err = UnknownMissionTypeError(
            "compliance-audit",
            registered_ids=["documentation", "plan", "research", "software-dev"],
        )
        msg = str(err)
        assert "Unknown mission type" in msg
        assert "compliance-audit" in msg
        assert "Registered types:" in msg


# ---------------------------------------------------------------------------
# T033 — resolve_mission_type_context uses existing_mission_types()
# ---------------------------------------------------------------------------


def _git_init_minimal(repo_root: Path) -> None:
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )


class TestResolveMissionTypeGovernanceValidation:
    """resolve_mission_type_context() uses existing_mission_types() for
    validation (T033).
    """

    def test_known_type_resolves_successfully(self, tmp_path: Path) -> None:
        """A mission type returned by existing_mission_types() resolves without error."""
        _git_init_minimal(tmp_path)
        feature_dir = tmp_path / "kitty-specs" / "test-mission-001"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps({"mission_type": "software-dev", "mission_slug": "test-mission-001"}),
            encoding="utf-8",
        )

        # Mock existing_mission_types to return a controlled set including software-dev
        with patch(
            "charter.activation.mission_type_profiles.existing_mission_types",
            return_value=["documentation", "plan", "research", "software-dev"],
        ):
            bundle = resolve_mission_type_context(tmp_path, feature_dir=feature_dir)

        assert bundle.mission_type == "software-dev"

    def test_unknown_type_raises_unknown_mission_type_error(self, tmp_path: Path) -> None:
        """A mission type not in existing_mission_types() raises UnknownMissionTypeError."""
        _git_init_minimal(tmp_path)
        feature_dir = tmp_path / "kitty-specs" / "unknown-001"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {"mission_type": "totally-custom-type", "mission_slug": "unknown-001"}
            ),
            encoding="utf-8",
        )

        # Mock: no project overrides, limited activation set
        with (
            patch(
                "charter.activation.mission_type_profiles.existing_mission_types",
                return_value=["documentation", "plan", "research", "software-dev"],
            ),
            patch(
                "charter.activation.mission_type_profiles._project_has_doctrine_overrides",
                return_value=False,
            ),
            pytest.raises(UnknownMissionTypeError) as exc_info,
        ):
            resolve_mission_type_context(tmp_path, feature_dir=feature_dir)

        assert "totally-custom-type" in str(exc_info.value)

    def test_error_includes_registered_ids(self, tmp_path: Path) -> None:
        """UnknownMissionTypeError from resolve_mission_type_context carries registered_ids."""
        _git_init_minimal(tmp_path)
        feature_dir = tmp_path / "kitty-specs" / "unknown-001"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {"mission_type": "compliance-audit", "mission_slug": "unknown-001"}
            ),
            encoding="utf-8",
        )

        activated = ["documentation", "plan", "research", "software-dev"]
        with (
            patch(
                "charter.activation.mission_type_profiles.existing_mission_types",
                return_value=activated,
            ),
            patch(
                "charter.activation.mission_type_profiles._project_has_doctrine_overrides",
                return_value=False,
            ),
            pytest.raises(UnknownMissionTypeError) as exc_info,
        ):
            resolve_mission_type_context(tmp_path, feature_dir=feature_dir)

        err = exc_info.value
        assert err.registered_ids == activated

    def test_project_with_overrides_does_not_hard_fail_for_unknown_type(
        self, tmp_path: Path
    ) -> None:
        """When project has doctrine overrides, unknown type skips the profile
        (no hard fail) — the governance grain's *tolerant* policy.
        """
        _git_init_minimal(tmp_path)
        feature_dir = tmp_path / "kitty-specs" / "custom-mission-001"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {"mission_type": "custom-type", "mission_slug": "custom-mission-001"}
            ),
            encoding="utf-8",
        )

        with (
            patch(
                "charter.activation.mission_type_profiles.existing_mission_types",
                return_value=["documentation", "plan", "research", "software-dev"],
            ),
            patch(
                "charter.activation.mission_type_profiles._project_has_doctrine_overrides",
                return_value=True,
            ),
        ):
            # Should NOT raise — project overrides bypass the unknown-type check.
            bundle = resolve_mission_type_context(tmp_path, feature_dir=feature_dir)

        assert bundle.mission_type == "custom-type"
        # An unregistered-but-tolerated type has no built-in action sequence.
        assert bundle.action_sequence == []

    def test_activated_but_unresolvable_profile_message_is_not_contradictory(
        self, tmp_path: Path
    ) -> None:
        """An activated custom type with no loadable profile must not be told,
        in the same breath, that it is both unknown and registered (#3183,
        FR-006 / SC-003).

        Unlike ``test_unknown_type_raises_unknown_mission_type_error`` (which
        covers an id absent from ``existing_mission_types()``), this test's
        id IS present in the activation set — that is the actual defect
        scenario. There is deliberately no built-in ``my-custom`` doctrine
        mission-type definition on disk, so ``_resolve_action_slot`` cannot
        resolve a profile for it even though it is activated.
        """
        _git_init_minimal(tmp_path)
        feature_dir = tmp_path / "kitty-specs" / "custom-002"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps({"mission_type": "my-custom", "mission_slug": "custom-002"}),
            encoding="utf-8",
        )

        # "my-custom" IS activated (present in existing_mission_types()) but
        # has no resolvable MissionTypeProfile / mission-type YAML on disk.
        with (
            patch(
                "charter.activation.mission_type_profiles.existing_mission_types",
                return_value=["my-custom"],
            ),
            pytest.raises(UnknownMissionTypeError) as exc_info,
        ):
            resolve_mission_type_context(tmp_path, feature_dir=feature_dir)

        msg = str(exc_info.value)
        assert "my-custom" in msg

        # The defect: the id appears in BOTH an "Unknown mission type ..."
        # clause AND a "Registered types: my-custom" list in the same
        # message. Assert that self-contradiction is absent, without pinning
        # exact prose.
        if "Registered types:" in msg:
            registered_clause = msg.split("Registered types:", 1)[1]
            assert "my-custom" not in registered_clause, (
                "Message calls 'my-custom' unknown while also listing it "
                f"among the registered types: {msg!r}"
            )

        # Positive shape: the message must separately state the two real
        # facts -- the id is activated, and it has no loadable profile.
        lowered = msg.lower()
        assert "activated" in lowered, f"Message does not mention activation: {msg!r}"
        assert "no loadable profile" in lowered, (
            f"Message does not state the profile-loadability fact: {msg!r}"
        )

    def test_other_activated_types_clause_excludes_self(self, tmp_path: Path) -> None:
        """When multiple types are activated, the "Other activated mission
        types:" clause must not re-list the failing id (reviewer follow-up
        on WP06, #3183 / FR-006).

        ``test_activated_but_unresolvable_profile_message_is_not_contradictory``
        pins self-exclusion from the "Registered types:" sentence, but its
        ``registered_ids`` fixture is a single-element list
        (``["my-custom"]``), so the ``if other_registered:`` branch that
        renders "Other activated mission types: ..." never executes there —
        that test cannot catch a regression that re-lists the id under this
        second clause instead. This test activates ``my-custom`` alongside
        two other types so the clause actually renders, then asserts the
        failing id occurs exactly once in the whole message — a check that
        is agnostic to *which* clause a future regression re-lists it under.
        """
        _git_init_minimal(tmp_path)
        feature_dir = tmp_path / "kitty-specs" / "custom-003"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps({"mission_type": "my-custom", "mission_slug": "custom-003"}),
            encoding="utf-8",
        )

        # "my-custom" IS activated, alongside two other registered types, so
        # the "Other activated mission types:" clause renders. It still has
        # no resolvable MissionTypeProfile / mission-type YAML on disk.
        with (
            patch(
                "charter.activation.mission_type_profiles.existing_mission_types",
                return_value=["my-custom", "research", "software-dev"],
            ),
            pytest.raises(UnknownMissionTypeError) as exc_info,
        ):
            resolve_mission_type_context(tmp_path, feature_dir=feature_dir)

        msg = str(exc_info.value)
        assert "Other activated mission types:" in msg, (
            f"Expected the multi-activated clause to render: {msg!r}"
        )
        assert msg.count("my-custom") == 1, (
            "'my-custom' must appear exactly once in the message -- once "
            "as the failing id, and NOT again inside the 'Other activated "
            f"mission types:' clause: {msg!r}"
        )
        assert "research" in msg
        assert "software-dev" in msg

    def test_missing_mission_type_key_degrades_neutrally(self, tmp_path: Path) -> None:
        """meta.json without 'mission_type' key degrades to the neutral bundle (FR-003a).

        The retired ``resolve_mission_type_governance`` raised a ValueError here;
        the WP02 canonicalizer + resolver now treat an absent type as *typeless*
        and degrade neutrally — never a software-dev default.
        """
        _git_init_minimal(tmp_path)
        feature_dir = tmp_path / "kitty-specs" / "no-type-001"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps({"mission_slug": "no-type-001"}),
            encoding="utf-8",
        )

        with patch(
            "charter.activation.mission_type_profiles.existing_mission_types",
            return_value=["software-dev"],
        ):
            bundle = resolve_mission_type_context(tmp_path, feature_dir=feature_dir)

        assert bundle.mission_type is None
        assert bundle.governance is None
        assert bundle.governance_text == ""
        assert bundle.action_sequence == []


# ---------------------------------------------------------------------------
# WP04/T010 — thread the real PackContext into action-sequence/template-set
# projection (FR-002). Written and committed FIRST, RED against the
# pre-WP04 code (``_resolve_action_slot`` still calling
# ``MissionTypeRepository.default()``, ``_resolve_template_set_slot`` still
# hardcoding ``pack_context=None``), per C-011 red-first discipline.
# ---------------------------------------------------------------------------


def _write_layered_mission_type_yaml(
    directory: Path,
    filename: str,
    mission_type_id: str,
    *,
    action_sequence: list[str] | None = None,
) -> None:
    """Write a minimal mission-type YAML for the layered lookup (WP03 shape).

    Mirrors ``tests/doctrine/missions/test_mission_type_repository.py``'s
    own ``_mission_type_yaml`` helper. ``action_sequence=None`` omits the
    field entirely (the CL-003 empty-action-sequence edge case).
    """
    directory.mkdir(parents=True, exist_ok=True)
    lines = [
        "schema_version: 1",
        f"id: {mission_type_id}",
        f"display_name: {mission_type_id.title()}",
    ]
    if action_sequence is not None:
        lines.append("action_sequence:")
        lines.extend(f"  - {step}" for step in action_sequence)
    (directory / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_org_mission_step_yaml(
    org_root: Path,
    mission_type_id: str,
    step_id: str,
    *,
    artifact_key: str | None = None,
    template_file: str | None = None,
    sequence_index: int = 0,
) -> None:
    """Write a step.yaml in the org-pack layout, optionally carrying a
    template ref.

    Org-pack layout convention (mirrors
    ``tests/doctrine/missions/test_mission_step_resolver.py::_write_org_step``):
    ``{org_root}/mission-steps/{mission_type_id}/{step_id}/step.yaml``.

    ``artifact_key``/``template_file`` default to ``None``; the ``template:``
    block is emitted only when both are provided, matching
    ``MissionStep.template`` being optional (``None`` for template-less
    steps).
    """
    step_dir = org_root / "mission-steps" / mission_type_id / step_id
    step_dir.mkdir(parents=True, exist_ok=True)
    content = (
        f"id: {step_id}\n"
        f"display_name: {step_id.title()}\n"
        "step_type: agent\n"
        "prompt_template: prompt.md\n"
        "in_action_sequence: true\n"
        f"sequence_index: {sequence_index}\n"
    )
    if artifact_key is not None and template_file is not None:
        content += (
            "template:\n"
            f"  artifact_key: {artifact_key}\n"
            f"  template_file: {template_file}\n"
        )
    (step_dir / "step.yaml").write_text(content, encoding="utf-8")


class TestPackContextProjection:
    """FR-002 (WP04/T010): ``resolve_mission_type_context`` threads the real
    ``PackContext`` it already constructs into both the action-sequence and
    template-set projection slots, so an org/project mission type resolves
    real, non-empty projected fields instead of degrading to built-in-only
    defaults (User Story 1 AC2).

    RED-first (C-011): both tests below fail against the pre-WP04 code --
    ``_resolve_action_slot`` calls the built-in-only
    ``MissionTypeRepository.default()`` with no ``pack_context`` parameter
    at all, so an org-pack-only type id resolves to ``mission is None`` and
    raises :class:`UnknownMissionTypeError` instead of returning the
    org-pack's declared fields.
    """

    def setup_method(self) -> None:
        # PR-TESTS-002 (pre-merge squad, mission up-mission-type-seam-01KZY1JB):
        # every other test file that patches ``PackContext.from_config`` and
        # drives resolution through ``resolve_layered_mission_types``'s
        # module-level cache also clears it before/after -- this class
        # previously relied only on the incidental fact that ``PackContext``
        # is a frozen, field-hashed dataclass built from pytest's
        # per-test-unique ``tmp_path``, so no two tests here could construct
        # an *equal* cache key. Explicit discipline now, matching
        # ``tests/cli/test_charter_mission_type_commands.py`` and
        # ``tests/doctrine/missions/test_mission_type_repository.py``.
        MissionTypeRepository.cache_clear()

    def teardown_method(self) -> None:
        MissionTypeRepository.cache_clear()

    def test_org_pack_type_projects_real_action_sequence_and_template_set(
        self, tmp_path: Path
    ) -> None:
        """An org-pack type with a populated action_sequence, activated in a
        test project, resolves through ``resolve_mission_type_context`` with
        real, non-empty projected fields matching the org-pack's declared
        steps exactly -- not empty, not silently substituted with a
        built-in default (spec.md User Story 1 AC2).
        """
        _git_init_minimal(tmp_path)
        org_root = tmp_path / "org-pack"
        _write_layered_mission_type_yaml(
            org_root / "mission_types",
            "qa.yaml",
            "qa",
            action_sequence=["design", "implement"],
        )
        _write_org_mission_step_yaml(
            org_root,
            "qa",
            "design",
            artifact_key="spec",
            template_file="qa-spec-template.md",
        )
        _write_org_mission_step_yaml(
            org_root,
            "qa",
            "implement",
            sequence_index=1,
        )
        pack_context = PackContext(
            activated_kinds=frozenset(),
            activated_mission_types=frozenset({"qa"}),
            pack_roots=(tmp_path / "unused-builtin-placeholder", org_root),
            org_pack_names=("org-pack",),
            repo_root=tmp_path,
        )

        with patch(
            "charter.activation.pack_context.PackContext.from_config", return_value=pack_context
        ):
            bundle = resolve_mission_type_context(tmp_path, mission_type="qa")

        assert bundle.action_sequence == ["design", "implement"]
        assert bundle.template_set is not None
        assert dict(bundle.template_set) == {"spec": "qa-spec-template.md"}

    def test_project_layer_omitting_action_sequence_raises_named_error(
        self, tmp_path: Path
    ) -> None:
        """A project-layer file overriding an org-layer entry with the same
        ``id``, where the project-layer file omits ``action_sequence``, must
        raise :class:`MissionTypeEmptyActionSequenceError` naming the
        ``project`` layer -- not a field-merged inherit of the org-layer's
        populated value (spec.md Edge Cases, full per-compound-key
        replacement -- MissionTypeRepository does not inherit
        BaseArtifactRepository, so the field-merge ADR
        ``docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md`` does
        not govern it) and not a silent resolve to ``[]`` (CL-003/FR-004,
        closed by WP06).

        Before WP06 this test asserted ``bundle.action_sequence == []`` --
        its own docstring at the time said so explicitly ("This test does
        not yet assert the eventual loud failure ... that is WP06's job").
        That was always documented as the CL-003 silent-degradation gap
        WP06 closes, not a contract this test intended to freeze, so it is
        re-pinned to the loud-failure contract here (DIRECTIVE_041: judge
        the test, not git-blame) rather than deleted -- the setup (project
        overriding org, full-replace semantics) remains valid coverage.
        """
        _git_init_minimal(tmp_path)
        org_root = tmp_path / "org-pack"
        _write_layered_mission_type_yaml(
            org_root / "mission_types",
            "shared.yaml",
            "shared",
            action_sequence=["org-step"],
        )
        _write_layered_mission_type_yaml(
            tmp_path / ".kittify" / "missions" / "mission_types",
            "shared.yaml",
            "shared",
            action_sequence=None,
        )
        pack_context = PackContext(
            activated_kinds=frozenset(),
            activated_mission_types=frozenset({"shared"}),
            pack_roots=(tmp_path / "unused-builtin-placeholder", org_root),
            org_pack_names=("org-pack",),
            repo_root=tmp_path,
        )

        with (
            patch("charter.activation.pack_context.PackContext.from_config", return_value=pack_context),
            pytest.raises(MissionTypeEmptyActionSequenceError) as exc_info,
        ):
            resolve_mission_type_context(tmp_path, mission_type="shared")

        # Full-replace, not field-merge: the project layer's own missing
        # action_sequence wins outright -- it must NOT silently inherit the
        # org layer's populated ["org-step"], and it must not silently
        # resolve to [] either (CL-003/FR-004).
        err = exc_info.value
        assert isinstance(err, MissionTypeEmptyActionSequenceError)
        assert err.mission_type_id == "shared"
        assert err.layer == "project"


# ---------------------------------------------------------------------------
# WP06/T013-T014 — loud-fail for the empty-action-sequence degradation
# (FR-004/CL-003/NFR-005). The regression test below was committed RED
# first (NFR-005): at that commit MissionTypeEmptyActionSequenceError did
# not exist in production code and _resolve_action_slot still returned
# `list(mission.action_sequence or [])` unconditionally, silently
# degrading to `[]` -- confirmed by running this test in isolation before
# the fix commit landed (see this WP's commit history for the verbatim RED
# output). The fix commit (T014) added the exception class and its raise
# site and made this test GREEN.
# ---------------------------------------------------------------------------


class TestResolveActionSequenceLayerHelper:
    """Direct coverage of ``resolve_action_sequence_layer``'s own two
    remaining branches (WP06 diff-coverage): the protected-pack-root skip
    and the built-in fallback. Neither is reachable through the full
    ``resolve_mission_type_context()`` pipeline, given that helper's own
    precondition -- it is only ever called once a type's action sequence is
    already known to be empty, which no built-in type's is (see
    :class:`MissionTypeEmptyActionSequenceError`'s docstring) -- so this
    exercises the private helper directly, mirroring this file's own
    ``_action_sequence()``-direct-import convention in
    ``test_action_sequence_dispatch.py``.
    """

    def test_protected_pack_root_is_skipped_and_falls_through_to_builtin(
        self, tmp_path: Path
    ) -> None:
        """A ``pack_root`` equal to the built-in-equivalent directory's
        parent is skipped (already covered by that layer), and when no
        other layer has the file either, the helper falls through to the
        honest ``"built-in"`` default rather than raising a second error.
        """
        from charter.activation.mission_type_profiles import resolve_action_sequence_layer

        mission_types_dirs = (tmp_path / "builtin-equivalent" / "mission_types",)
        pack_context = PackContext(
            activated_kinds=frozenset(),
            activated_mission_types=frozenset(),
            pack_roots=(tmp_path / "builtin-equivalent",),
            org_pack_names=(),
            repo_root=tmp_path,
        )

        layer = resolve_action_sequence_layer(
            "no-such-type",
            mission_types_dirs=mission_types_dirs,
            pack_context=pack_context,
        )

        assert layer == "built-in"


class TestEmptyActionSequenceLoudFail:
    """FR-004/CL-003 (WP06): resolving a non-built-in-layer mission type
    whose YAML carries only ``schema_version``/``id``/``display_name`` (no
    ``action_sequence``) must raise :class:`MissionTypeEmptyActionSequenceError`
    naming both the mission-type id and the resolving layer -- not silently
    degrade to ``[]``. This is the mission's own dominant risk (CL-003): a
    mission of that type would otherwise resolve "successfully" and plan
    nothing, with no error anywhere.
    """

    def setup_method(self) -> None:
        # PR-TESTS-002: see ``TestPackContextProjection.setup_method``.
        MissionTypeRepository.cache_clear()

    def teardown_method(self) -> None:
        MissionTypeRepository.cache_clear()

    def test_org_layer_type_with_no_action_sequence_raises_named_error(
        self, tmp_path: Path
    ) -> None:
        """The canonical CL-003 example: an org-pack mission-type YAML with
        no ``action_sequence`` key at all resolves loudly, naming the id and
        the ``org`` layer it resolved from -- not a clean resolve to ``[]``.
        """
        _git_init_minimal(tmp_path)
        org_root = tmp_path / "org-pack"
        _write_layered_mission_type_yaml(
            org_root / "mission_types",
            "qa.yaml",
            "qa",
            action_sequence=None,
        )
        pack_context = PackContext(
            activated_kinds=frozenset(),
            activated_mission_types=frozenset({"qa"}),
            pack_roots=(tmp_path / "unused-builtin-placeholder", org_root),
            org_pack_names=("org-pack",),
            repo_root=tmp_path,
        )

        with (
            patch("charter.activation.pack_context.PackContext.from_config", return_value=pack_context),
            pytest.raises(MissionTypeEmptyActionSequenceError) as exc_info,
        ):
            resolve_mission_type_context(tmp_path, mission_type="qa")

        err = exc_info.value
        assert isinstance(err, MissionTypeEmptyActionSequenceError)
        assert err.mission_type_id == "qa"
        assert err.layer == "org"
        assert "qa" in str(err)
        assert "org" in str(err)


# ---------------------------------------------------------------------------
# WP06/T015 — mission create propagates the same exception TYPE (User Story
# 2 AC2). isinstance-only, never message substring-matching.
# ---------------------------------------------------------------------------


class TestMissionCreatePropagatesEmptyActionSequenceError:
    """``mission create`` against a misconfigured org/project mission type
    propagates :class:`MissionTypeEmptyActionSequenceError` -- the SAME
    exception type FR-004's resolver-level raise produces, asserted via
    ``isinstance`` (User Story 2 AC2), not message substring-matching.

    Call-path trace confirming no intermediate ``except Exception`` swallows
    or re-wraps the exception: ``create_mission_core``
    (``src/specify_cli/core/mission_creation.py``) calls
    ``resolve_mission_type_context`` directly at its mission-type-resolution
    step, with no surrounding try/except of its own -- the only two
    ``except Exception`` blocks in that function guard unrelated
    best-effort event emission far downstream, after the point this call
    never reaches once it raises. ``create_mission_core``'s own docstring
    states it is "the programmatic API ... [it] returns a structured result
    and raises domain exceptions instead of calling ``typer.Exit()``" --
    unlike the Typer CLI command wrapper
    (``specify_cli/cli/commands/agent/mission_create.py``'s
    ``_run_create_core_phase``), which DOES catch ``except Exception`` and
    convert to ``typer.Exit(1)`` at the CLI presentation boundary. This test
    calls ``create_mission_core`` directly for that reason -- it is the
    documented entry point that raises the real exception type rather than
    a process exit code.
    """

    def setup_method(self) -> None:
        # PR-TESTS-002: see ``TestPackContextProjection.setup_method``.
        MissionTypeRepository.cache_clear()

    def teardown_method(self) -> None:
        MissionTypeRepository.cache_clear()

    def test_create_mission_propagates_named_exception_type(self, tmp_path: Path) -> None:
        from specify_cli.core.mission_creation import create_mission_core  # noqa: PLC0415

        _git_init_minimal(tmp_path)
        subprocess.run(
            ["git", "commit", "-m", "init", "--allow-empty"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        org_root = tmp_path / "org-pack"
        _write_layered_mission_type_yaml(
            org_root / "mission_types",
            "qa.yaml",
            "qa",
            action_sequence=None,
        )
        pack_context = PackContext(
            activated_kinds=frozenset(),
            activated_mission_types=frozenset({"qa"}),
            pack_roots=(tmp_path / "unused-builtin-placeholder", org_root),
            org_pack_names=("org-pack",),
            repo_root=tmp_path,
        )

        with (
            patch("charter.activation.pack_context.PackContext.from_config", return_value=pack_context),
            pytest.raises(MissionTypeEmptyActionSequenceError) as exc_info,
        ):
            create_mission_core(
                tmp_path,
                "qa-mission",
                mission="qa",
                friendly_name="QA Mission",
                purpose_tldr="Exercise the misconfigured qa type.",
                purpose_context=(
                    "Confirms create_mission_core propagates FR-004's exception "
                    "type end to end, not a re-wrapped generic error."
                ),
                # This test asserts exception-type propagation, not worktree
                # policy — allow_worktree_context=True keeps it from tripping
                # the unrelated is_worktree_context guard when the ambient cwd
                # happens to be a linked worktree (e.g. the CI runner's tree).
                allow_worktree_context=True,
            )

        err = exc_info.value
        assert isinstance(err, MissionTypeEmptyActionSequenceError)
        assert err.mission_type_id == "qa"
        assert err.layer == "org"


# ---------------------------------------------------------------------------
# WP04/T017-T019 — org-tier threading for the governance-profile repository
# (FR-004). `_mission_type_profile_repository` now threads `org_dirs` (via
# WP01's `resolve_org_dirs(repo_root, "mission_types")`) into
# `MissionTypeProfileRepository.for_project`, so an org-pack
# `mission_types/<type>/governance-profile.yaml` override is visible in
# `resolve_mission_type_context(...).governance_text` on every call — not
# just when some lazy accessor happens to be invoked (`_resolve_governance_slot`'s
# own docstring: provenance/governance are resolved eagerly there; only the
# FR-013 type-grain/action-grain union is deferred).
# ---------------------------------------------------------------------------

_ORG_OVERRIDE_TEMPLATE_SET = "org-tier-governance-override"


def _write_org_pack_config(
    repo_root: Path,
    *,
    packs: list[tuple[str, Path]],
    activated_mission_types: list[str],
) -> None:
    """Write a single, real ``.kittify/config.yaml`` carrying both the
    mission-type activation set and the ``doctrine.org.packs`` registry.

    Combines the shape ``test_mission_type_profile_override.py``'s
    ``_git_init_minimal`` writes (``mission_type_activations``) with the
    shape ``tests/doctrine/drg/test_org_pack_config_resolve_org_dirs.py``'s
    ``_write_config`` writes (``doctrine.org.packs``) into one file, so both
    ``existing_mission_types()`` and ``resolve_org_dirs()`` — and therefore
    the real ``resolve_mission_type_context()`` seam under test — read
    exactly what an operator would configure. No ``PackContext`` mocking:
    this is an end-to-end proof through real disk state.
    """
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = ["mission_type_activations:"]
    for mission_type in activated_mission_types:
        lines.append(f"  - {mission_type}")
    if packs:
        lines += ["charter_packs:", "  org:", "    packs:"]
        for name, local_path in packs:
            lines.append(f"      - name: {name}")
            lines.append(f"        local_path: {local_path}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_org_governance_profile(org_root: Path, mission_type: str, data: dict) -> None:
    """Write ``<org_root>/mission_types/<mission_type>/governance-profile.yaml``.

    Mirrors ``test_mission_type_profile_override.py``'s ``_write_profile``,
    adapted for the org-pack layout WP01's ``resolve_org_dirs`` resolves:
    ``<org_root>/mission_types/`` is the ``subdir="mission_types"`` join, and
    ``MissionTypeProfileRepository._project_scan`` recurses (``rglob``) into
    the per-type subdirectory below it.
    """
    profile_dir = org_root / "mission_types" / mission_type
    profile_dir.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with (profile_dir / "governance-profile.yaml").open("w") as fh:
        yaml.dump(data, fh)


class TestOrgTierGovernanceProfileThreading:
    """T017/T018 (WP04, FR-004): an org-pack governance-profile override
    becomes visible through the full `resolve_mission_type_context` seam
    once `_mission_type_profile_repository` threads `org_dirs` — proven as
    a before/after measurement (NFR-001), not a bare assertion.
    """

    def test_org_override_becomes_visible_after_configuring_org_pack(
        self, tmp_path: Path
    ) -> None:
        _git_init_minimal(tmp_path)
        _write_org_pack_config(
            tmp_path, packs=[], activated_mission_types=["software-dev"]
        )

        # BEFORE: no org pack configured at all — shipped baseline only.
        before = resolve_mission_type_context(tmp_path, mission_type="software-dev")
        assert before.provenance == "builtin"
        assert "software-dev-default" in before.governance_text
        assert _ORG_OVERRIDE_TEMPLATE_SET not in before.governance_text

        # AFTER: configure an org pack declaring a `mission_types` override
        # for the SAME registered type.
        org_root = tmp_path / "org-pack"
        _write_org_governance_profile(
            org_root,
            "software-dev",
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": _ORG_OVERRIDE_TEMPLATE_SET,
            },
        )
        _write_org_pack_config(
            tmp_path,
            packs=[("acme", org_root)],
            activated_mission_types=["software-dev"],
        )

        with pytest.warns(DoctrineLayerCollisionWarning, match="software-dev"):
            after = resolve_mission_type_context(tmp_path, mission_type="software-dev")

        assert after.provenance == "org"
        assert _ORG_OVERRIDE_TEMPLATE_SET in after.governance_text
        assert "software-dev-default" not in after.governance_text

    def test_two_org_packs_resolve_in_declaration_order(self, tmp_path: Path) -> None:
        """NFR-003: two org packs declaring the SAME type override resolve
        in declaration order — the later-declared pack wins, matching
        ``doctrine/service.py:47-52``'s documented "later configured org
        pack overrides an earlier one" contract. This WP's change threads a
        *list* of org dirs (declaration-ordered, per WP01's
        ``resolve_org_dirs``) into ``MissionTypeProfileRepository.for_project``,
        so an ordering regression here would be this WP's own fault, not a
        pre-existing one — hence the explicit two-pack fixture rather than
        relying solely on the generic ``resolve_org_dirs``/``BaseArtifactRepository``
        coverage elsewhere.
        """
        _git_init_minimal(tmp_path)
        first_org_root = tmp_path / "z-org-pack"
        second_org_root = tmp_path / "a-org-pack"
        # Declared first -> should be overridden by the second.
        _write_org_governance_profile(
            first_org_root,
            "software-dev",
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": "first-org-pack-template",
            },
        )
        # Declared second -> later declaration wins for the same id.
        _write_org_governance_profile(
            second_org_root,
            "software-dev",
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": "second-org-pack-template",
            },
        )
        _write_org_pack_config(
            tmp_path,
            packs=[("z-pack", first_org_root), ("a-pack", second_org_root)],
            activated_mission_types=["software-dev"],
        )

        with pytest.warns(DoctrineLayerCollisionWarning, match="software-dev"):
            bundle = resolve_mission_type_context(tmp_path, mission_type="software-dev")

        assert bundle.provenance == "org"
        assert "second-org-pack-template" in bundle.governance_text
        assert "first-org-pack-template" not in bundle.governance_text


# ---------------------------------------------------------------------------
# T026 (WP05, FR-008/SC-005): org-tier expected-artifacts.yaml override,
# reached through `_resolve_expected_artifacts_slot` via the full
# `resolve_mission_type_context` seam.
# ---------------------------------------------------------------------------


def _write_org_expected_artifacts(org_root: Path, mission_type: str, data: dict) -> None:
    """Write ``<org_root>/missions/<mission_type>/expected-artifacts.yaml``.

    Raw-root shape (C-4): unlike ``_write_org_governance_profile`` (which
    joins the ``subdir="mission_types"`` segment ``resolve_org_dirs``
    produces), FR-008's helper takes raw org roots and joins
    ``missions/<mission_type>`` directly — see ``org_expected_artifacts.py``'s
    module docstring for why (``mission_type`` varies per call, so it cannot
    be baked into a fixed ``subdir`` string).
    """
    target_dir = org_root / "missions" / mission_type
    target_dir.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with (target_dir / "expected-artifacts.yaml").open("w") as fh:
        yaml.dump(data, fh)


class TestOrgTierExpectedArtifactsThreading:
    """T026 (WP05, FR-008): an org-pack expected-artifacts.yaml override
    becomes visible through `_resolve_expected_artifacts_slot`, reached via
    the full `resolve_mission_type_context` seam — proven as a before/after
    measurement (NFR-001), not a bare assertion.
    """

    def test_org_override_changes_required_always_count(self, tmp_path: Path) -> None:
        _git_init_minimal(tmp_path)
        _write_org_pack_config(
            tmp_path, packs=[], activated_mission_types=["software-dev"]
        )

        # BEFORE: no org pack configured — built-in manifest only.
        before = resolve_mission_type_context(tmp_path, mission_type="software-dev")
        before_manifest = before.expected_artifacts
        assert before_manifest is not None
        before_count = len(before_manifest.get("required_always", []))

        # AFTER: configure an org pack declaring an EXTRA required_always
        # artifact for the same registered built-in type.
        org_root = tmp_path / "org-pack"
        _write_org_expected_artifacts(
            org_root,
            "software-dev",
            {
                "schema_version": "1.0",
                "mission_type": "software-dev",
                "manifest_version": "org-1",
                "required_always": [
                    {
                        "artifact_key": "policy.org-required",
                        "artifact_class": "policy",
                        "path_pattern": "org-policy.md",
                        "blocking": True,
                    }
                ],
            },
        )
        _write_org_pack_config(
            tmp_path,
            packs=[("acme", org_root)],
            activated_mission_types=["software-dev"],
        )

        after = resolve_mission_type_context(tmp_path, mission_type="software-dev")
        after_manifest = after.expected_artifacts
        assert after_manifest is not None
        after_count = len(after_manifest.get("required_always", []))

        # A delta, not merely "no exception" — proves the count/content
        # actually changed relative to the built-in-only baseline.
        assert after_count == before_count + 1
        assert after_manifest["manifest_version"] == "org-1"
        assert any(
            spec["artifact_key"] == "policy.org-required"
            for spec in after_manifest["required_always"]
        )

    def test_org_file_fully_replaces_builtin_not_field_merged(
        self, tmp_path: Path
    ) -> None:
        """SC-005 Given #3: whole-file precedence. The org file's content is
        what's returned — the built-in file's `required_by_step.plan`
        entries (`output.plan.main`, `output.tasks.list`) must NOT survive,
        which would only be possible under a field-merge.
        """
        _git_init_minimal(tmp_path)
        org_root = tmp_path / "org-pack"
        _write_org_expected_artifacts(
            org_root,
            "software-dev",
            {
                "schema_version": "1.0",
                "mission_type": "software-dev",
                "manifest_version": "org-only",
                # Deliberately omits required_by_step entirely — the
                # built-in file's `plan`/`specify`/`implement` step entries
                # exist on disk but must not leak through if this were
                # (incorrectly) a field-merge rather than a whole-file swap.
            },
        )
        _write_org_pack_config(
            tmp_path,
            packs=[("acme", org_root)],
            activated_mission_types=["software-dev"],
        )

        bundle = resolve_mission_type_context(tmp_path, mission_type="software-dev")
        manifest = bundle.expected_artifacts

        assert manifest is not None
        assert manifest["manifest_version"] == "org-only"
        assert "required_by_step" not in manifest or not manifest.get(
            "required_by_step", {}
        ).get("plan")


# ---------------------------------------------------------------------------
# WP02 (#3770, FR-006): `_resolve_expected_artifacts_slot` now routes through
# the validated authority instead of returning the raw, unvalidated parsed
# mapping -- gaining schema validation. Previously an org-tier manifest
# failing `ExpectedArtifactManifest` schema validation would silently return
# as-is (this slot bypassed validation entirely); it now raises
# `ManifestSchemaError` on first access, exactly like the other two
# authority delegates (`resolve_configured_artifact_name` /
# `gather_artifact_presence`).
# ---------------------------------------------------------------------------


class TestExpectedArtifactsSlotSchemaValidation:
    """The slot gains real schema validation (was previously bypassed)."""

    def test_org_tier_schema_invalid_manifest_raises_on_access(self, tmp_path: Path) -> None:
        from charter.activation.manifest_loader import ManifestSchemaError

        _git_init_minimal(tmp_path)
        org_root = tmp_path / "org-pack"
        _write_org_expected_artifacts(
            org_root,
            "software-dev",
            # Missing the required `mission_type` field -> pydantic
            # ValidationError, wrapped into ManifestSchemaError by the
            # authority.
            {"schema_version": "1.0", "manifest_version": "broken"},
        )
        _write_org_pack_config(
            tmp_path,
            packs=[("acme", org_root)],
            activated_mission_types=["software-dev"],
        )

        bundle = resolve_mission_type_context(tmp_path, mission_type="software-dev")

        # The slot is memoised behind `@cached_property` (NFR-001) -- the
        # raise fires on first ACCESS of `.expected_artifacts`, not at
        # `resolve_mission_type_context()` call time.
        with pytest.raises(ManifestSchemaError) as exc_info:
            _ = bundle.expected_artifacts

        assert exc_info.value.mission_type == "software-dev"
        assert "org-tier" in exc_info.value.origin


# ---------------------------------------------------------------------------
# WP02 T009 (#3770): the slot now delegates to the authority -- proves the
# delegation is live, not an inert local copy that happens to agree with the
# authority today.
# ---------------------------------------------------------------------------


class TestExpectedArtifactsSlotRoutesThroughAuthority:
    def test_delegates_to_manifest_loader_load_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import charter.activation.manifest_loader as manifest_loader_module

        _git_init_minimal(tmp_path)
        _write_org_pack_config(tmp_path, packs=[], activated_mission_types=["software-dev"])

        calls: list[tuple[str, Path | None]] = []
        original_load_manifest = manifest_loader_module.load_manifest

        def _tracking_load_manifest(mission_type: str, repo_root: Path | None = None) -> object:
            calls.append((mission_type, repo_root))
            return original_load_manifest(mission_type, repo_root=repo_root)

        monkeypatch.setattr(manifest_loader_module, "load_manifest", _tracking_load_manifest)

        bundle = resolve_mission_type_context(tmp_path, mission_type="software-dev")
        _ = bundle.expected_artifacts

        assert calls == [("software-dev", tmp_path)]


class TestActionGrainBuiltinOnlyPathUnaffected:
    """T019 (WP04): `charter.activation.action_grain`'s built-in-only call site — which
    calls `_load_mission_type_profile(mission_type)` with NO `repo_root`
    (`action_grain.py`, inside `scan_builtin_cross_grain_duplicates`) — must
    stay built-in-only even when an org pack declaring a `mission_types`
    override for the same type is configured for the project. This WP's
    fix only threads `org_dirs` on the `repo_root is not None` branch of
    `_mission_type_profile_repository`; `action_grain.py` never passes
    `repo_root`, so it should already be unaffected — this test exists to
    make that fact durable against a future refactor, not because the fix
    is expected to break it today.
    """

    def test_builtin_only_lookup_ignores_org_override_present_on_disk(
        self, tmp_path: Path
    ) -> None:
        _git_init_minimal(tmp_path)
        org_root = tmp_path / "org-pack"
        _write_org_governance_profile(
            org_root,
            "software-dev",
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": _ORG_OVERRIDE_TEMPLATE_SET,
            },
        )
        _write_org_pack_config(
            tmp_path,
            packs=[("acme", org_root)],
            activated_mission_types=["software-dev"],
        )

        # Sanity: the WP04-fixed, repo_root-threaded path DOES see the org
        # override (same fixture as TestOrgTierGovernanceProfileThreading).
        with pytest.warns(DoctrineLayerCollisionWarning, match="software-dev"):
            threaded = _load_mission_type_profile("software-dev", repo_root=tmp_path)
        assert threaded is not None
        assert threaded.template_set == _ORG_OVERRIDE_TEMPLATE_SET

        # action_grain.py's own call shape: repo_root omitted (defaults to
        # None) — must resolve the shipped baseline, untouched by the org
        # override that exists on disk for this same project.
        builtin_only = _load_mission_type_profile("software-dev")
        assert builtin_only is not None
        assert builtin_only.template_set == "software-dev-default"
        assert builtin_only.template_set != _ORG_OVERRIDE_TEMPLATE_SET

    def test_scan_builtin_cross_grain_duplicates_unaffected_by_org_override(
        self, tmp_path: Path
    ) -> None:
        """The real `action_grain.py:220`-adjacent call path — exercised via
        its own public entry point — completes without raising and without
        picking up the org override, confirming the guard holds at the
        actual call site, not just at the `_load_mission_type_profile` unit
        level above.
        """
        _git_init_minimal(tmp_path)
        org_root = tmp_path / "org-pack"
        _write_org_governance_profile(
            org_root,
            "software-dev",
            {
                "id": "software-dev",
                "mission_type": "software-dev",
                "template_set": _ORG_OVERRIDE_TEMPLATE_SET,
            },
        )
        _write_org_pack_config(
            tmp_path,
            packs=[("acme", org_root)],
            activated_mission_types=["software-dev"],
        )

        scanned = scan_builtin_cross_grain_duplicates()

        assert "software-dev" in scanned
