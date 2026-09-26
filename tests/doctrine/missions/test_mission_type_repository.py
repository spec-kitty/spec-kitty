"""Tests for MissionType model and MissionTypeRepository.

Covers:
- Built-in YAML round-trip: software-dev.yaml loads with correct action_sequence
- All four built-in YAMLs load without error
- action_sequence non-empty validator fires on empty list
- action_sequence uniqueness validator fires on duplicate step IDs
- MissionType.id rejected on non-kebab-case input
- MissionTypeRepository.get("software-dev") returns the correct artifact
- MissionTypeRepository.get("nonexistent") returns None
- Repository raises on YAML with id mismatching filename stem
- Authoring ``template_set:`` (model kwarg or YAML) fails loudly (SC-002,
  mission-step-creatability-01KXQA6R WP01) -- the retired field's key is
  now rejected by ``extra="forbid"`` rather than silently honored or dropped.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import ValidationError

from charter.offering.missions.mission_type_repository import (
    MissionTypeRepository,
    resolve_layered_mission_types,
)
from charter.offering.missions.models import MissionType

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]


# ── MissionType model unit tests ─────────────────────────────────────────────


class TestMissionTypeModel:
    """Unit tests for MissionType Pydantic model validation."""

    def test_valid_mission_type_constructs_successfully(self) -> None:
        mt = MissionType(
            schema_version=1,
            id="my-type",
            display_name="My Type",
            action_sequence=["step-a", "step-b"],
        )
        assert mt.id == "my-type"
        assert mt.display_name == "My Type"
        assert mt.action_sequence == ["step-a", "step-b"]
        assert mt.extends is None
        assert not hasattr(mt, "governance_refs")
        assert not hasattr(mt, "template_set")

    def test_empty_action_sequence_raises(self) -> None:
        with pytest.raises(ValidationError, match="action_sequence must be non-empty"):
            MissionType(
                id="my-type",
                display_name="My Type",
                action_sequence=[],
            )

    def test_duplicate_action_sequence_raises(self) -> None:
        with pytest.raises(
            ValidationError, match="action_sequence must contain unique step IDs"
        ):
            MissionType(
                id="my-type",
                display_name="My Type",
                action_sequence=["step-a", "step-b", "step-a"],
            )

    def test_id_with_uppercase_rejected(self) -> None:
        with pytest.raises(ValidationError, match="IDENTIFIER_PATTERN"):
            MissionType(
                id="MyType",
                display_name="Bad",
                action_sequence=["step-a"],
            )

    def test_id_with_leading_digit_rejected(self) -> None:
        with pytest.raises(ValidationError, match="IDENTIFIER_PATTERN"):
            MissionType(
                id="1bad",
                display_name="Bad",
                action_sequence=["step-a"],
            )

    def test_id_with_underscore_rejected(self) -> None:
        with pytest.raises(ValidationError, match="IDENTIFIER_PATTERN"):
            MissionType(
                id="bad_id",
                display_name="Bad",
                action_sequence=["step-a"],
            )

    def test_template_set_kwarg_raises_validation_error(self) -> None:
        """SC-002 / FR-001: authoring the retired field now fails loudly.

        ``extra="forbid"`` rejects the unknown key regardless of value --
        this is the model-constructor half of the pack-fails-loud proof
        (T007); ``TestTemplateSetAuthoringFailsLoudly`` below exercises the
        equivalent through the YAML-loader entry point.
        """
        with pytest.raises(ValidationError, match="template_set"):
            MissionType(
                id="my-type",
                display_name="My Type",
                action_sequence=["step-a"],
                template_set={"spec": "spec-template.md"},  # type: ignore[call-arg]
            )

    def test_template_set_none_kwarg_also_raises(self) -> None:
        """Even an explicit ``None`` for the retired key is rejected -- the key's
        mere presence is forbidden, not just a non-``None`` value."""
        with pytest.raises(ValidationError, match="template_set"):
            MissionType(
                id="my-type",
                display_name="My Type",
                action_sequence=["step-a"],
                template_set=None,  # type: ignore[call-arg]
            )


# ── MissionTypeRepository with built-in YAMLs ────────────────────────────────


def _builtin_repo() -> MissionTypeRepository:
    """Return a MissionTypeRepository pointed at the doctrine-bundled mission_types dir.

    Mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H``
    (FR-005) relocated ``mission_types/`` from
    ``src/charter/offering/missions/mission_types`` to
    ``packs/built-in/missions/mission_types``.
    """
    mission_types_dir = (
        Path(__file__).parent.parent.parent.parent / "packs" / "built-in" / "missions" / "mission_types"
    )
    return MissionTypeRepository(mission_types_dir)


class TestBuiltinYamlFiles:
    """Verify the four built-in YAML files load correctly."""

    def test_software_dev_loads(self) -> None:
        repo = _builtin_repo()
        mt = repo.get("software-dev")
        assert mt is not None
        assert mt.id == "software-dev"
        assert mt.display_name == "Software Development"
        assert mt.action_sequence == ["specify", "plan", "tasks", "implement", "review"]

    def test_documentation_loads(self) -> None:
        repo = _builtin_repo()
        mt = repo.get("documentation")
        assert mt is not None
        assert mt.id == "documentation"
        assert mt.action_sequence == [
            "discover",
            "audit",
            "design",
            "generate",
            "validate",
            "publish",
            "accept",
        ]

    def test_research_loads(self) -> None:
        repo = _builtin_repo()
        mt = repo.get("research")
        assert mt is not None
        assert mt.id == "research"
        assert mt.action_sequence == [
            "scoping",
            "methodology",
            "gathering",
            "synthesis",
            "output",
        ]

    def test_plan_loads(self) -> None:
        repo = _builtin_repo()
        mt = repo.get("plan")
        assert mt is not None
        assert mt.id == "plan"
        assert mt.action_sequence == ["specify", "research", "plan", "review"]

    def test_all_four_builtin_yamls_load(self) -> None:
        repo = _builtin_repo()
        ids = repo.ids()
        assert "software-dev" in ids
        assert "documentation" in ids
        assert "research" in ids
        assert "plan" in ids

    def test_ids_sorted(self) -> None:
        repo = _builtin_repo()
        ids = repo.ids()
        assert ids == sorted(ids)

    def test_load_all_sorted_by_id(self) -> None:
        repo = _builtin_repo()
        all_types = repo.load_all()
        assert [mt.id for mt in all_types] == sorted(mt.id for mt in all_types)

    def test_software_dev_template_set(self) -> None:
        """S-C cutover (WP01, C-005): ``template_set`` is no longer a ``MissionType``
        field -- migrated to the step-authority projection (mirrors
        ``TestSoftwareDevProjectionParity`` in ``test_softwaredev_roundtrip.py``)."""
        from charter.offering.missions.mission_step_repository import MissionStepRepository
        from charter.offering.missions.step_projection import project_template_set

        steps = list(
            MissionStepRepository.default()
            .resolve_all_for_mission_type("software-dev", pack_context=None)
            .values()
        )
        assert project_template_set(steps) == {
            "spec": "spec-template.md",
            "plan": "plan-template.md",
        }

    def test_research_template_set(self) -> None:
        """S-C Concern B (WP03, C-003/C-010): ``research`` authors a ``spec`` ref
        on ``scoping`` and a ``plan`` ref on ``methodology``, with per-type-unique
        ``template_file`` names (NFR-006) -- mirrors ``test_software_dev_template_set``
        above."""
        from charter.offering.missions.mission_step_repository import MissionStepRepository
        from charter.offering.missions.step_projection import project_template_set

        steps = list(
            MissionStepRepository.default()
            .resolve_all_for_mission_type("research", pack_context=None)
            .values()
        )
        assert project_template_set(steps) == {
            "spec": "research-spec-template.md",
            "plan": "research-plan-template.md",
        }

    def test_documentation_template_set(self) -> None:
        """S-C Concern B (mission-step-creatability-01KXQA6R WP02, reconciled by
        WP05, C-003/C-010): ``documentation`` authors a ``spec`` ref on
        ``discover`` and a ``plan`` ref on ``design``, with per-type-unique
        ``template_file`` names (NFR-006) -- mirrors ``test_research_template_set``
        above. ``documentation`` was removed from the now-deleted
        ``test_non_software_builtin_template_set_is_explicitly_null``
        parametrization once WP02 authored these refs."""
        from charter.offering.missions.mission_step_repository import MissionStepRepository
        from charter.offering.missions.step_projection import project_template_set

        steps = list(
            MissionStepRepository.default()
            .resolve_all_for_mission_type("documentation", pack_context=None)
            .values()
        )
        assert project_template_set(steps) == {
            "spec": "documentation-spec-template.md",
            "plan": "documentation-plan-template.md",
        }

    def test_plan_template_set(self) -> None:
        """S-C Concern B (mission-step-creatability-01KXQA6R WP04, reconciled by
        WP05, C-003/C-010): ``plan`` authors a ``spec`` ref on ``specify`` and a
        ``plan`` ref on ``plan``, with per-type-unique ``template_file`` names
        (NFR-006) -- mirrors ``test_research_template_set`` above. ``plan`` was
        removed from the now-deleted
        ``test_non_software_builtin_template_set_is_explicitly_null``
        parametrization once WP04 authored these refs."""
        from charter.offering.missions.mission_step_repository import MissionStepRepository
        from charter.offering.missions.step_projection import project_template_set

        steps = list(
            MissionStepRepository.default()
            .resolve_all_for_mission_type("plan", pack_context=None)
            .values()
        )
        assert project_template_set(steps) == {
            "spec": "plan-spec-skeleton.md",
            "plan": "plan-plan-skeleton.md",
        }


# ── MissionTypeRepository lookup behavior ────────────────────────────────────


class TestMissionTypeRepositoryLookup:
    """Test get() and ids() semantics."""

    def test_get_known_id_returns_mission_type(self) -> None:
        repo = _builtin_repo()
        mt = repo.get("software-dev")
        assert isinstance(mt, MissionType)

    def test_get_nonexistent_returns_none(self) -> None:
        repo = _builtin_repo()
        result = repo.get("nonexistent")
        assert result is None

    def test_get_empty_string_returns_none(self) -> None:
        repo = _builtin_repo()
        result = repo.get("")
        assert result is None

    def test_empty_directory_returns_empty_repo(self, tmp_path: Path) -> None:
        repo = MissionTypeRepository(tmp_path)
        assert repo.ids() == []
        assert repo.load_all() == []

    def test_nonexistent_directory_returns_empty_repo(self, tmp_path: Path) -> None:
        repo = MissionTypeRepository(tmp_path / "no-such-dir")
        assert repo.ids() == []
        assert repo.load_all() == []


# ── MissionTypeRepository YAML loading ────────────────────────────────────────


class TestMissionTypeRepositoryYamlLoading:
    """Test YAML parsing and id-stem validation."""

    def _write_yaml(self, directory: Path, filename: str, content: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_text(content, encoding="utf-8")

    def test_valid_yaml_round_trip(self, tmp_path: Path) -> None:
        self._write_yaml(
            tmp_path,
            "my-mission.yaml",
            "schema_version: 1\n"
            "id: my-mission\n"
            "display_name: My Mission\n"
            "action_sequence:\n"
            "  - step-one\n"
            "  - step-two\n",
        )
        repo = MissionTypeRepository(tmp_path)
        mt = repo.get("my-mission")
        assert mt is not None
        assert mt.action_sequence == ["step-one", "step-two"]

    def test_id_mismatch_with_filename_stem_raises(self, tmp_path: Path) -> None:
        self._write_yaml(
            tmp_path,
            "correct-name.yaml",
            "schema_version: 1\n"
            "id: wrong-name\n"
            "display_name: Wrong\n"
            "action_sequence:\n"
            "  - step-one\n",
        )
        with pytest.raises(ValueError, match="does not match filename stem"):
            MissionTypeRepository(tmp_path)

    def test_non_mapping_yaml_raises(self, tmp_path: Path) -> None:
        self._write_yaml(tmp_path, "list-type.yaml", "- step-one\n- step-two\n")
        with pytest.raises(ValueError, match="Expected a YAML mapping"):
            MissionTypeRepository(tmp_path)

    def test_invalid_model_yaml_raises_validation_error(self, tmp_path: Path) -> None:
        self._write_yaml(
            tmp_path,
            "bad-model.yaml",
            "schema_version: 1\n"
            "id: bad-model\n"
            "display_name: Bad\n"
            "action_sequence: []\n",  # empty — fails non-empty validator
        )
        with pytest.raises((ValueError, Exception)):
            MissionTypeRepository(tmp_path)

    def test_multiple_yamls_all_indexed(self, tmp_path: Path) -> None:
        for slug, step in [("alpha-type", "step-x"), ("beta-type", "step-y")]:
            self._write_yaml(
                tmp_path,
                f"{slug}.yaml",
                f"schema_version: 1\nid: {slug}\ndisplay_name: {slug}\n"
                f"action_sequence:\n  - {step}\n",
            )
        repo = MissionTypeRepository(tmp_path)
        assert set(repo.ids()) == {"alpha-type", "beta-type"}


class TestTemplateSetAuthoringFailsLoudly:
    """SC-002 / FR-001 (S-C cutover, mission-step-creatability-01KXQA6R WP01).

    A ``mission_types/*.yaml`` that (incorrectly) authors ``template_set:``
    must fail loudly at load time -- neither silently honored nor silently
    dropped. This is the YAML-loader-entry-point half of the pack-fails-loud
    proof (T007); ``TestMissionTypeModel.test_template_set_kwarg_raises_validation_error``
    covers the equivalent at the bare model-constructor level.

    ``_inject_projected_fields`` no longer overlays a ``template_set`` key
    (the entire overlay assignment was dropped, FR-001) -- ``payload =
    dict(raw)`` preserves the authored key verbatim, and ``MissionType``'s
    ``extra="forbid"`` rejects it during ``MissionType.model_validate``,
    which ``MissionTypeRepository.__init__`` (eager) surfaces immediately.
    """

    def _write_yaml(self, directory: Path, filename: str, content: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_text(content, encoding="utf-8")

    def test_authored_template_set_raises_validation_error(self, tmp_path: Path) -> None:
        self._write_yaml(
            tmp_path,
            "rogue-type.yaml",
            "schema_version: 1\n"
            "id: rogue-type\n"
            "display_name: Rogue\n"
            "action_sequence:\n"
            "  - step-one\n"
            "template_set:\n"
            "  spec: spec-template.md\n",
        )
        with pytest.raises(ValidationError, match="template_set"):
            MissionTypeRepository(tmp_path)


# ── Layered lookup (FR-001, mission up-mission-type-seam-01KZY1JB WP03) ─────


def _builtin_mission_types_dir() -> Path:
    """Return the doctrine-bundled mission_types dir (mirrors ``_builtin_repo``)."""
    return (
        Path(__file__).parent.parent.parent.parent / "packs" / "built-in" / "missions" / "mission_types"
    )


@dataclass(frozen=True)
class _StubPackContext:
    """Minimal structural stand-in for ``charter.activation.pack_context.PackContext``.

    Mirrors ``tests/doctrine/missions/test_mission_step_resolver.py``'s own
    ``_StubPackContext`` -- satisfies ``_PackContextLike`` (``pack_roots``,
    ``repo_root``, ``__hash__`` synthesized by ``@dataclass(frozen=True)``).
    """

    pack_roots: tuple[Path, ...]
    repo_root: Path


def _write_layered_yaml(directory: Path, filename: str, content: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path


def _mission_type_yaml(mission_type_id: str, *, action_sequence: list[str]) -> str:
    steps = "\n".join(f"  - {step}" for step in action_sequence)
    return (
        f"schema_version: 1\nid: {mission_type_id}\ndisplay_name: "
        f"{mission_type_id.title()}\naction_sequence:\n{steps}\n"
    )


def _mission_type_yaml_steps_only(mission_type_id: str) -> str:
    """Sibling to :func:`_mission_type_yaml` -- NO ``action_sequence:`` key at all.

    WP01/NFR-001's steps-only fixture shape: the org/project mission-type
    YAML authors only ``schema_version``/``id``/``display_name``, so
    ``action_sequence`` must come entirely from step-file projection
    (:func:`~charter.offering.missions.step_projection.project_action_sequence`) --
    the exact defect shape issue #3701 reports (``_inject_projected_fields``
    hardcoding ``pack_context=None`` means this projection was always empty
    for org/project types). ``_mission_type_yaml`` above always writes an
    explicit ``action_sequence:`` key and is reused by other tests in this
    file that depend on that exact behavior, so this is a new sibling
    helper rather than a repurposing of it.
    """
    return (
        f"schema_version: 1\nid: {mission_type_id}\ndisplay_name: "
        f"{mission_type_id.title()}\n"
    )


def _write_step_with_sequence(
    root: Path,
    mission_type_id: str,
    step_id: str,
    *,
    sequence_index: int,
    display_name: str = "Test Step",
) -> Path:
    """Write a ``step.yaml`` under *root* carrying ``sequence_index``/``in_action_sequence``.

    ``tests/doctrine/missions/test_mission_step_resolver.py``'s
    ``_write_step``/``_write_org_step``/``_write_project_step`` write
    minimal ``step.yaml`` files that omit ``sequence_index``/
    ``in_action_sequence``, so they project to an empty sequence as-is and
    do not fit this WP's fixtures. Per this WP's own no-cross-file-helper-
    import convention (each test file's helpers are local), this is a new,
    local helper rather than an import of those. *root* is the directory
    that directly contains ``<mission_type_id>/<step_id>/step.yaml`` (e.g.
    an org pack's ``mission-steps/`` dir or a project's
    ``.kittify/overrides/mission-steps/`` dir) -- callers pass the
    layer-specific parent, mirroring the field shape confirmed live in a
    built-in ``step.yaml`` (e.g.
    ``packs/built-in/missions/mission-steps/software-dev/specify/step.yaml``).
    """
    step_dir = root / mission_type_id / step_id
    step_dir.mkdir(parents=True, exist_ok=True)
    (step_dir / "step.yaml").write_text(
        f"id: {step_id}\ndisplay_name: {display_name!r}\nstep_type: agent\n"
        f"prompt_template: prompt.md\nsequence_index: {sequence_index}\n"
        "in_action_sequence: true\n",
        encoding="utf-8",
    )
    return step_dir


_STEPS_ONLY_FIXTURE_STEP_IDS: tuple[str, ...] = (
    "discovery",
    "specify",
    "plan",
    "tasks",
    "implement",
    "review",
    "accept",
)


class TestLayeredProjectionThreadsPackContext:
    """WP01/T002 red-first (NFR-001, Acceptance Scenarios 1 & 2): an org-tier
    steps-only mission-type YAML (no ``action_sequence:`` key) must resolve
    a non-empty ``action_sequence`` from its step-file projection once
    ``pack_context`` is threaded through ``_inject_projected_fields`` and
    the three functions above it in the call chain. Before the fix,
    ``_inject_projected_fields`` hardcoded ``pack_context=None`` regardless
    of what its callers held, so every org/project type relying on
    step-file projection (no explicit ``action_sequence:`` authored)
    resolved ``action_sequence = None``/``[]`` and the governed entry point
    (``charter.mission_type_profiles.resolve_mission_type_context``) raised
    :class:`~charter.activation.mission_type_profiles.MissionTypeEmptyActionSequenceError`.

    Both assertions in this class MUST fail against the pre-fix production
    code (T002 step 2) and pass once T003's threading lands (T003 step 7) --
    this is the red-first pin, not incidental coverage.
    """

    def setup_method(self) -> None:
        resolve_layered_mission_types.cache_clear()

    def teardown_method(self) -> None:
        resolve_layered_mission_types.cache_clear()

    def _write_steps_only_org_fixture(self, org_root: Path, mission_type_id: str) -> None:
        _write_layered_yaml(
            org_root / "mission_types",
            f"{mission_type_id}.yaml",
            _mission_type_yaml_steps_only(mission_type_id),
        )
        step_root = org_root / "mission-steps"
        for index, step_id in enumerate(_STEPS_ONLY_FIXTURE_STEP_IDS):
            _write_step_with_sequence(
                step_root, mission_type_id, step_id, sequence_index=index
            )

    def test_org_tier_steps_only_projection_resolves_non_empty_sequence(
        self, tmp_path: Path
    ) -> None:
        """Direct assertion against :func:`resolve_layered_mission_types` --
        the low-level function at the bottom of the four-function chain."""
        org_root = tmp_path / "org"
        self._write_steps_only_org_fixture(org_root, "qa")

        dirs = (tmp_path / "builtin" / "mission_types",)
        ctx = _StubPackContext(
            pack_roots=(dirs[0].parent, org_root), repo_root=tmp_path / "project"
        )

        result = resolve_layered_mission_types(dirs, ctx)

        assert result["qa"].action_sequence == list(_STEPS_ONLY_FIXTURE_STEP_IDS)

    def test_governed_entry_point_does_not_raise_for_steps_only_org_type(
        self, tmp_path: Path
    ) -> None:
        """Also closes Acceptance Scenario 2: the *governed* seam
        (``resolve_mission_type_context``) must succeed for a steps-only
        org type, not raise ``MissionTypeEmptyActionSequenceError``.
        Follows the exact two-patch pattern
        ``TestGoldenParityUnaffectedByPackContextThreading`` already uses in
        ``tests/runtime/test_runtime_seam.py`` (patch target strings are
        CI-validated, so this reuses those exact strings rather than
        inventing a new patch shape)."""
        from unittest.mock import patch

        from charter.activation.mission_type_profiles import resolve_mission_type_context

        org_root = tmp_path / "org"
        self._write_steps_only_org_fixture(org_root, "qa")

        dirs = (tmp_path / "builtin" / "mission_types",)
        repo_root = tmp_path / "project"
        ctx = _StubPackContext(pack_roots=(dirs[0].parent, org_root), repo_root=repo_root)

        with (
            patch(
                "charter.activation.mission_type_profiles.existing_mission_types",
                return_value=["qa"],
            ),
            patch(
                "charter.activation.pack_context.PackContext.from_config",
                return_value=ctx,
            ),
        ):
            bundle = resolve_mission_type_context(repo_root, mission_type="qa")

        assert bundle.action_sequence == list(_STEPS_ONLY_FIXTURE_STEP_IDS)

    def test_project_tier_steps_only_projection_resolves(self, tmp_path: Path) -> None:
        """WP01/T005 (Acceptance Scenario 5, spec.md line 62): a dedicated,
        project-tier-specific case -- distinct from the org-tier cases above
        even though structurally similar, per this WP's own instruction not
        to silently fold Scenario 5 into T002's org-tier docstring/name.

        Path conventions confirmed live against
        ``mission_step_repository.py``'s own source before writing this
        fixture (not assumed): the project-tier mission-*type* YAML lives at
        ``<repo_root>/.kittify/missions/mission_types/<id>.yaml``
        (``PROJECT_MISSION_TYPES_RELATIVE``, this module), while the
        project-tier *step-tree* lives at
        ``<repo_root>/.kittify/overrides/mission-steps/<id>/<step>/step.yaml``
        (``_project_mission_type_dir``/``_resolve_project_layer``,
        ``mission_step_repository.py``) -- a distinct subtree
        (``overrides/mission-steps``, not ``missions/mission_types``) from
        the mission-type YAML's own project path, and distinct from the
        org-tier ``<pack_root>/mission-steps/`` convention this class's
        other tests exercise.
        """
        repo_root = tmp_path / "project"
        _write_layered_yaml(
            repo_root / ".kittify" / "missions" / "mission_types",
            "qa.yaml",
            _mission_type_yaml_steps_only("qa"),
        )
        step_root = repo_root / ".kittify" / "overrides" / "mission-steps"
        for index, step_id in enumerate(_STEPS_ONLY_FIXTURE_STEP_IDS):
            _write_step_with_sequence(step_root, "qa", step_id, sequence_index=index)

        dirs = (tmp_path / "builtin" / "mission_types",)
        ctx = _StubPackContext(pack_roots=(dirs[0].parent,), repo_root=repo_root)

        result = resolve_layered_mission_types(dirs, ctx)

        assert result["qa"].action_sequence == list(_STEPS_ONLY_FIXTURE_STEP_IDS)


class TestLayeredMissionTypesCacheKeyAndClear:
    """FR-001/NFR-001: cache-hit/miss identity, two-project isolation, cache_clear()."""

    def setup_method(self) -> None:
        resolve_layered_mission_types.cache_clear()

    def teardown_method(self) -> None:
        resolve_layered_mission_types.cache_clear()

    def test_same_key_is_a_cache_hit(self, tmp_path: Path) -> None:
        org_root = tmp_path / "org"
        _write_layered_yaml(
            org_root / "mission_types",
            "custom.yaml",
            _mission_type_yaml("custom", action_sequence=["step-a"]),
        )
        dirs = (tmp_path / "builtin" / "mission_types",)
        ctx = _StubPackContext(pack_roots=(dirs[0].parent, org_root), repo_root=tmp_path / "project")

        first = resolve_layered_mission_types(dirs, ctx)
        # Mutate the org file after the first resolution -- a genuine cache
        # HIT must not observe this (proves identity, not just equal content).
        _write_layered_yaml(
            org_root / "mission_types",
            "custom.yaml",
            _mission_type_yaml("custom", action_sequence=["step-a", "step-b"]),
        )
        second = resolve_layered_mission_types(dirs, ctx)

        assert second is first
        assert second["custom"].action_sequence == ["step-a"]

    def test_two_projects_same_process_return_distinct_correct_results(
        self, tmp_path: Path
    ) -> None:
        """NFR-001: same-process, two-project regression -- the mission's
        own binding requirement for the new factory's cache key."""
        builtin_dirs = (tmp_path / "builtin" / "mission_types",)

        project_a_org = tmp_path / "project-a-org"
        _write_layered_yaml(
            project_a_org / "mission_types",
            "alpha.yaml",
            _mission_type_yaml("alpha", action_sequence=["step-a"]),
        )
        ctx_a = _StubPackContext(
            pack_roots=(builtin_dirs[0].parent, project_a_org),
            repo_root=tmp_path / "project-a",
        )

        project_b_org = tmp_path / "project-b-org"
        _write_layered_yaml(
            project_b_org / "mission_types",
            "beta.yaml",
            _mission_type_yaml("beta", action_sequence=["step-b"]),
        )
        ctx_b = _StubPackContext(
            pack_roots=(builtin_dirs[0].parent, project_b_org),
            repo_root=tmp_path / "project-b",
        )

        result_a = resolve_layered_mission_types(builtin_dirs, ctx_a)
        result_b = resolve_layered_mission_types(builtin_dirs, ctx_b)

        assert "alpha" in result_a
        assert "beta" not in result_a
        assert "beta" in result_b
        assert "alpha" not in result_b

        # Re-resolving project A after B must still return A's own,
        # unpoisoned result.
        result_a_again = resolve_layered_mission_types(builtin_dirs, ctx_a)
        assert result_a_again is result_a
        assert "alpha" in result_a_again
        assert "beta" not in result_a_again

    def test_cache_clear_forces_a_rewalk(self, tmp_path: Path) -> None:
        org_root = tmp_path / "org"
        mt_dir = org_root / "mission_types"
        _write_layered_yaml(mt_dir, "custom.yaml", _mission_type_yaml("custom", action_sequence=["step-a"]))
        dirs = (tmp_path / "builtin" / "mission_types",)
        ctx = _StubPackContext(pack_roots=(dirs[0].parent, org_root), repo_root=tmp_path / "project")

        first = resolve_layered_mission_types(dirs, ctx)
        assert first["custom"].action_sequence == ["step-a"]

        _write_layered_yaml(mt_dir, "custom.yaml", _mission_type_yaml("custom", action_sequence=["step-a", "step-b"]))
        MissionTypeRepository.cache_clear()
        second = resolve_layered_mission_types(dirs, ctx)

        assert second is not first
        assert second["custom"].action_sequence == ["step-a", "step-b"]

    def test_default_cache_and_roster_unaffected_by_layered_factory(self) -> None:
        """User Story 3 AC2: default()'s own cache key/roster are provably
        unaffected by activity on the new factory."""
        default_before = MissionTypeRepository.default()
        ids_before = default_before.ids()

        resolve_layered_mission_types((_builtin_mission_types_dir(),), None)
        MissionTypeRepository.cache_clear()
        resolve_layered_mission_types((_builtin_mission_types_dir(),), None)

        default_after = MissionTypeRepository.default()
        assert default_after is default_before
        assert default_after.ids() == ids_before

    def test_none_pack_context_resolves_only_builtin_equivalent_layer(self) -> None:
        result = resolve_layered_mission_types((_builtin_mission_types_dir(),), None)
        assert "software-dev" in result

    def test_nonexistent_project_layer_directory_is_not_an_error(self, tmp_path: Path) -> None:
        """spec.md Edge Cases: an unactivated project-layer dir resolves as
        'no contributions', not an error/crash."""
        dirs = (tmp_path / "builtin" / "mission_types",)
        ctx = _StubPackContext(pack_roots=(dirs[0].parent,), repo_root=tmp_path / "project")

        result = resolve_layered_mission_types(dirs, ctx)

        assert result == {}

    def test_project_layer_fully_replaces_org_layer_entry(self, tmp_path: Path) -> None:
        """spec.md Edge Cases: project overrides org via full per-compound-key
        replacement, not field-level merge."""
        org_root = tmp_path / "org"
        _write_layered_yaml(
            org_root / "mission_types",
            "shared.yaml",
            _mission_type_yaml("shared", action_sequence=["org-step"]),
        )
        repo_root = tmp_path / "project"
        _write_layered_yaml(
            repo_root / ".kittify" / "missions" / "mission_types",
            "shared.yaml",
            _mission_type_yaml("shared", action_sequence=["project-step"]),
        )
        dirs = (tmp_path / "builtin" / "mission_types",)
        ctx = _StubPackContext(pack_roots=(dirs[0].parent, org_root), repo_root=repo_root)

        result = resolve_layered_mission_types(dirs, ctx)

        assert result["shared"].action_sequence == ["project-step"]


class TestLayeredMissionTypesMalformedYamlLoudFail:
    """CL-006/NFR-002 (spec.md Edge Cases): a malformed org/project-layer
    mission-type YAML fails loudly, naming the offending file -- never
    silently skipped and resolved as though it did not exist.

    Red-first (T005): before the wrap-and-re-raise fix, the underlying
    ``ruamel.yaml`` parser error carries no file identity of its own (it
    parses a bare ``str``, not a named stream), so these two assertions
    fail against the naive/unwrapped call shape -- confirmed by hand
    (recorded in this WP's commit history / Activity Log) before the fix
    landed.
    """

    def setup_method(self) -> None:
        resolve_layered_mission_types.cache_clear()

    def teardown_method(self) -> None:
        resolve_layered_mission_types.cache_clear()

    def test_malformed_org_layer_yaml_raises_naming_the_file(self, tmp_path: Path) -> None:
        org_root = tmp_path / "org"
        bad_file = org_root / "mission_types" / "broken.yaml"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text("key: [unterminated\n  - a\n", encoding="utf-8")

        builtin_dirs = (tmp_path / "builtin" / "mission_types",)
        ctx = _StubPackContext(
            pack_roots=(builtin_dirs[0].parent, org_root), repo_root=tmp_path / "project"
        )

        with pytest.raises(Exception) as exc_info:  # noqa: PT011 - message content is the assertion
            resolve_layered_mission_types(builtin_dirs, ctx)

        assert str(bad_file) in str(exc_info.value)

    def test_malformed_project_layer_yaml_raises_naming_the_file(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "project"
        bad_file = repo_root / ".kittify" / "missions" / "mission_types" / "broken.yaml"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text("key: [unterminated\n  - a\n", encoding="utf-8")

        builtin_dirs = (tmp_path / "builtin" / "mission_types",)
        ctx = _StubPackContext(pack_roots=(builtin_dirs[0].parent,), repo_root=repo_root)

        with pytest.raises(Exception) as exc_info:  # noqa: PT011 - message content is the assertion
            resolve_layered_mission_types(builtin_dirs, ctx)

        assert str(bad_file) in str(exc_info.value)

    def test_non_mapping_org_layer_yaml_raises_naming_the_file(self, tmp_path: Path) -> None:
        """NFR-002: a non-mapping document (e.g. a bare YAML list) in an
        org-layer file must raise, not silently resolve as though the file
        did not exist."""
        org_root = tmp_path / "org"
        bad_file = org_root / "mission_types" / "list-type.yaml"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text("- step-one\n- step-two\n", encoding="utf-8")

        builtin_dirs = (tmp_path / "builtin" / "mission_types",)
        ctx = _StubPackContext(
            pack_roots=(builtin_dirs[0].parent, org_root), repo_root=tmp_path / "project"
        )

        with pytest.raises(ValueError, match="Expected a YAML mapping"):
            resolve_layered_mission_types(builtin_dirs, ctx)

    def test_org_layer_id_mismatch_with_filename_stem_raises(self, tmp_path: Path) -> None:
        """NFR-002: an id/filename-stem mismatch in an org-layer file must
        raise, mirroring MissionTypeRepository._load's own check."""
        org_root = tmp_path / "org"
        _write_layered_yaml(
            org_root / "mission_types",
            "correct-name.yaml",
            _mission_type_yaml("wrong-name", action_sequence=["step-a"]),
        )

        builtin_dirs = (tmp_path / "builtin" / "mission_types",)
        ctx = _StubPackContext(
            pack_roots=(builtin_dirs[0].parent, org_root), repo_root=tmp_path / "project"
        )

        with pytest.raises(ValueError, match="does not match filename stem"):
            resolve_layered_mission_types(builtin_dirs, ctx)


class TestLayeredMissionTypesUnreadableDirectoryLoudFail:
    """WP03 review finding (Severity 3): "directory exists but is
    unreadable" must NOT collapse to the same ``{}`` result as "directory
    does not exist" (NFR-002/CL-006 -- this mission exists because a
    misconfigured org pack silently degraded to "contributes nothing";
    reintroducing that shape inside this fix would be the worst available
    outcome).

    Empirically (``chmod 000`` on a directory containing one valid YAML
    file): ``pathlib.Path.glob()`` silently swallows ``PermissionError``
    during ``scandir`` and returns ``[]`` -- ``directory.is_dir()`` doesn't
    catch this either, since ``stat`` only needs search permission on the
    *parent* directories, not on the target directory itself, so it
    succeeds even at mode 000. Only actually listing the directory's
    contents (e.g. ``Path.iterdir()``) requires read+execute on the
    directory itself and raises ``PermissionError`` directly (confirmed by
    hand before this fix landed -- see this WP's commit history for the
    red-first evidence).
    """

    def setup_method(self) -> None:
        resolve_layered_mission_types.cache_clear()

    def teardown_method(self) -> None:
        resolve_layered_mission_types.cache_clear()

    def test_unreadable_org_layer_directory_raises_naming_the_directory(
        self, tmp_path: Path
    ) -> None:
        if os.name != "posix" or os.geteuid() == 0:
            pytest.skip("chmod-based unreadability needs POSIX and a non-root user")

        org_root = tmp_path / "org"
        mt_dir = org_root / "mission_types"
        _write_layered_yaml(
            mt_dir, "custom.yaml", _mission_type_yaml("custom", action_sequence=["step-a"])
        )

        builtin_dirs = (tmp_path / "builtin" / "mission_types",)
        ctx = _StubPackContext(
            pack_roots=(builtin_dirs[0].parent, org_root), repo_root=tmp_path / "project"
        )

        os.chmod(mt_dir, 0o000)
        try:
            with pytest.raises(Exception) as exc_info:  # noqa: PT011 - message content is the assertion
                resolve_layered_mission_types(builtin_dirs, ctx)
            assert str(mt_dir) in str(exc_info.value)
        finally:
            os.chmod(mt_dir, 0o755)
