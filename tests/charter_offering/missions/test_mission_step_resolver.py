"""Tests for MissionStepRepository — compound-key layered resolution.

Covers:
- Built-in layer resolution
- Org-layer shadowing (overrides built-in)
- Project-layer shadowing (overrides both org and built-in)
- Compound-key isolation: ``software-dev/review`` shadow does NOT affect
  ``documentation/review``
- Missing step returns ``None`` (no raise)
- ``resolve_all_for_mission_type`` returns dict keyed by step_id with
  shadowing applied
- The shared ``resolve_all_for_mission_type`` cache (NFR-003, S-C cutover,
  mission-step-creatability-01KXQA6R WP01): one filesystem walk per
  ``(builtin_root, mission_type_id, pack_context)``, shared across instances
  and call sites, plus the ``cache_clear()`` test seam.

FR-012: MissionStep compound-key shadowing
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from charter.offering.missions.mission_step_repository import MissionStepRepository, StepKey
from charter.offering.missions.models import MissionStep

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ---------------------------------------------------------------------------
# Minimal PackContext stub (WP06 provides the real one; this file tests only
# the repository, so a minimal dataclass is sufficient).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StubPackContext:
    """Minimal stand-in for charter.activation.pack_context.PackContext (FR-012 tests)."""

    pack_roots: tuple[Path, ...]
    repo_root: Path


# ---------------------------------------------------------------------------
# Helpers — fixture builders
# ---------------------------------------------------------------------------


def _write_step(
    root: Path,
    mission_type_id: str,
    step_id: str,
    *,
    display_name: str = "Test Step",
    depends_on: list[str] | None = None,
) -> Path:
    """Write a minimal step.yaml at the expected path under *root*."""
    step_dir = root / mission_type_id / step_id
    step_dir.mkdir(parents=True, exist_ok=True)
    depends_on_yaml = ""
    if depends_on:
        items = "\n".join(f"- {d}" for d in depends_on)
        depends_on_yaml = f"\ndepends_on:\n{items}"
    (step_dir / "step.yaml").write_text(
        f"id: {step_id}\ndisplay_name: {display_name!r}\nstep_type: agent\nprompt_template: prompt.md{depends_on_yaml}\n",
        encoding="utf-8",
    )
    return step_dir


def _write_org_step(
    org_root: Path,
    mission_type_id: str,
    step_id: str,
    *,
    display_name: str = "Org Step",
) -> Path:
    """Write a step.yaml in the org-pack layout under *org_root*.

    Org-pack layout convention (data-model.md §4, T025):
        ``{org_root}/mission-steps/{mission_type_id}/{step_id}/step.yaml``
    """
    step_dir = org_root / "mission-steps" / mission_type_id / step_id
    step_dir.mkdir(parents=True, exist_ok=True)
    (step_dir / "step.yaml").write_text(
        f"id: {step_id}\ndisplay_name: {display_name!r}\nstep_type: agent\nprompt_template: prompt.md\n",
        encoding="utf-8",
    )
    return step_dir


def _write_project_step(
    repo_root: Path,
    mission_type_id: str,
    step_id: str,
    *,
    display_name: str = "Project Step",
) -> Path:
    """Write a step.yaml in the project-layer layout under *repo_root*."""
    step_dir = (
        repo_root / ".kittify" / "overrides" / "mission-steps" / mission_type_id / step_id
    )
    step_dir.mkdir(parents=True, exist_ok=True)
    (step_dir / "step.yaml").write_text(
        f"id: {step_id}\ndisplay_name: {display_name!r}\nstep_type: agent\nprompt_template: prompt.md\n",
        encoding="utf-8",
    )
    return step_dir


# ---------------------------------------------------------------------------
# StepKey compound-key identity
# ---------------------------------------------------------------------------


class TestStepKey:
    """StepKey equality and hash semantics."""

    def test_same_key_is_equal(self) -> None:
        a = StepKey("software-dev", "review")
        b = StepKey("software-dev", "review")
        assert a == b

    def test_different_mission_type_is_not_equal(self) -> None:
        # Compound-key isolation: same step_id, different mission_type_id → different keys.
        a = StepKey("software-dev", "review")
        b = StepKey("documentation", "review")
        assert a != b

    def test_different_step_id_is_not_equal(self) -> None:
        a = StepKey("software-dev", "review")
        b = StepKey("software-dev", "specify")
        assert a != b

    def test_hashable_and_usable_as_dict_key(self) -> None:
        mapping: dict[StepKey, str] = {}
        mapping[StepKey("software-dev", "review")] = "sd-review"
        mapping[StepKey("documentation", "review")] = "doc-review"
        assert mapping[StepKey("software-dev", "review")] == "sd-review"
        assert mapping[StepKey("documentation", "review")] == "doc-review"


# ---------------------------------------------------------------------------
# Built-in layer resolution
# ---------------------------------------------------------------------------


class TestBuiltinLayer:
    """resolve() returns the built-in step when no overrides exist."""

    def test_builtin_step_found(self, tmp_path: Path) -> None:
        _write_step(tmp_path, "software-dev", "specify")
        repo = MissionStepRepository(builtin_steps_root=tmp_path)
        step = repo.resolve("software-dev", "specify")
        assert step is not None
        assert step.id == "specify"

    def test_builtin_step_title_mapped_from_display_name(self, tmp_path: Path) -> None:
        _write_step(tmp_path, "software-dev", "specify", display_name="Specification")
        repo = MissionStepRepository(builtin_steps_root=tmp_path)
        step = repo.resolve("software-dev", "specify")
        assert step is not None
        assert step.title == "Specification"

    def test_builtin_step_depends_on(self, tmp_path: Path) -> None:
        _write_step(tmp_path, "software-dev", "review", depends_on=["implement"])
        repo = MissionStepRepository(builtin_steps_root=tmp_path)
        step = repo.resolve("software-dev", "review")
        assert step is not None
        assert "implement" in step.depends_on

    def test_missing_step_returns_none(self, tmp_path: Path) -> None:
        repo = MissionStepRepository(builtin_steps_root=tmp_path)
        step = repo.resolve("software-dev", "nonexistent")
        assert step is None

    def test_missing_mission_type_returns_none(self, tmp_path: Path) -> None:
        repo = MissionStepRepository(builtin_steps_root=tmp_path)
        step = repo.resolve("no-such-type", "specify")
        assert step is None

    def test_no_pack_context_only_uses_builtin(self, tmp_path: Path) -> None:
        _write_step(tmp_path, "software-dev", "specify", display_name="Built-in")
        repo = MissionStepRepository(builtin_steps_root=tmp_path)
        step = repo.resolve("software-dev", "specify", pack_context=None)
        assert step is not None
        assert step.title == "Built-in"


# ---------------------------------------------------------------------------
# Org-layer shadowing
# ---------------------------------------------------------------------------


class TestOrgLayer:
    """Org-layer shadow overrides the built-in layer."""

    def test_org_shadow_overrides_builtin(self, tmp_path: Path) -> None:
        builtin_root = tmp_path / "builtin"
        org_root = tmp_path / "org"

        _write_step(builtin_root, "software-dev", "specify", display_name="Built-in Specify")
        _write_org_step(org_root, "software-dev", "specify", display_name="Org Specify")

        ctx = _StubPackContext(
            pack_roots=(org_root,),
            repo_root=tmp_path / "project",
        )
        repo = MissionStepRepository(builtin_steps_root=builtin_root)
        step = repo.resolve("software-dev", "specify", pack_context=ctx)  # type: ignore[arg-type]
        assert step is not None
        assert step.title == "Org Specify"

    def test_first_org_pack_wins(self, tmp_path: Path) -> None:
        builtin_root = tmp_path / "builtin"
        org1 = tmp_path / "org1"
        org2 = tmp_path / "org2"

        _write_step(builtin_root, "software-dev", "specify", display_name="Built-in")
        _write_org_step(org1, "software-dev", "specify", display_name="Org1")
        _write_org_step(org2, "software-dev", "specify", display_name="Org2")

        ctx = _StubPackContext(
            pack_roots=(org1, org2),
            repo_root=tmp_path / "project",
        )
        repo = MissionStepRepository(builtin_steps_root=builtin_root)
        step = repo.resolve("software-dev", "specify", pack_context=ctx)  # type: ignore[arg-type]
        assert step is not None
        assert step.title == "Org1"

    def test_org_layer_skipped_when_no_pack_context(self, tmp_path: Path) -> None:
        builtin_root = tmp_path / "builtin"
        org_root = tmp_path / "org"

        _write_step(builtin_root, "software-dev", "specify", display_name="Built-in")
        _write_org_step(org_root, "software-dev", "specify", display_name="Org")

        repo = MissionStepRepository(builtin_steps_root=builtin_root)
        # No pack_context → org layer not consulted
        step = repo.resolve("software-dev", "specify")
        assert step is not None
        assert step.title == "Built-in"

    def test_org_without_shadow_falls_back_to_builtin(self, tmp_path: Path) -> None:
        builtin_root = tmp_path / "builtin"
        org_root = tmp_path / "org"

        _write_step(builtin_root, "software-dev", "specify", display_name="Built-in")
        # org has NO specify step

        ctx = _StubPackContext(pack_roots=(org_root,), repo_root=tmp_path / "project")
        repo = MissionStepRepository(builtin_steps_root=builtin_root)
        step = repo.resolve("software-dev", "specify", pack_context=ctx)  # type: ignore[arg-type]
        assert step is not None
        assert step.title == "Built-in"

    def test_builtin_pack_root_in_pack_roots_does_not_double_resolve(
        self, tmp_path: Path
    ) -> None:
        """Regression: built-in pack root in pack_roots must NOT shadow the built-in layer.

        When ``PackContext.pack_roots`` includes the parent of the built-in
        ``mission-steps/`` directory (as WP06 does), the org-layer loop MUST
        skip that entry.  The result should be the built-in step unchanged —
        not a spurious "not found" or double-resolution.
        """
        builtin_steps_root = tmp_path / "doctrine" / "missions" / "mission-steps"
        _write_step(builtin_steps_root, "software-dev", "specify", display_name="Built-in Specify")

        # Simulate PackContext.pack_roots[0] being the built-in missions/ dir.
        builtin_missions_dir = builtin_steps_root.parent  # .../doctrine/missions/

        ctx = _StubPackContext(
            pack_roots=(builtin_missions_dir,),
            repo_root=tmp_path / "project",
        )
        repo = MissionStepRepository(builtin_steps_root=builtin_steps_root)
        step = repo.resolve("software-dev", "specify", pack_context=ctx)  # type: ignore[arg-type]

        # Built-in step found via the built-in layer; org loop skipped the built-in root.
        assert step is not None
        assert step.title == "Built-in Specify"


# ---------------------------------------------------------------------------
# Project-layer shadowing
# ---------------------------------------------------------------------------


class TestProjectLayer:
    """Project-layer shadow overrides both org and built-in layers."""

    def test_project_shadow_overrides_builtin(self, tmp_path: Path) -> None:
        builtin_root = tmp_path / "builtin"
        repo_root = tmp_path / "project"

        _write_step(builtin_root, "software-dev", "specify", display_name="Built-in")
        _write_project_step(repo_root, "software-dev", "specify", display_name="Project")

        ctx = _StubPackContext(pack_roots=(), repo_root=repo_root)
        repo = MissionStepRepository(builtin_steps_root=builtin_root)
        step = repo.resolve("software-dev", "specify", pack_context=ctx)  # type: ignore[arg-type]
        assert step is not None
        assert step.title == "Project"

    def test_project_shadow_overrides_org(self, tmp_path: Path) -> None:
        builtin_root = tmp_path / "builtin"
        org_root = tmp_path / "org"
        repo_root = tmp_path / "project"

        _write_step(builtin_root, "software-dev", "specify", display_name="Built-in")
        _write_org_step(org_root, "software-dev", "specify", display_name="Org")
        _write_project_step(repo_root, "software-dev", "specify", display_name="Project")

        ctx = _StubPackContext(pack_roots=(org_root,), repo_root=repo_root)
        repo = MissionStepRepository(builtin_steps_root=builtin_root)
        step = repo.resolve("software-dev", "specify", pack_context=ctx)  # type: ignore[arg-type]
        assert step is not None
        assert step.title == "Project"

    def test_project_layer_skipped_when_no_pack_context(self, tmp_path: Path) -> None:
        builtin_root = tmp_path / "builtin"
        repo_root = tmp_path / "project"

        _write_step(builtin_root, "software-dev", "specify", display_name="Built-in")
        _write_project_step(repo_root, "software-dev", "specify", display_name="Project")

        repo = MissionStepRepository(builtin_steps_root=builtin_root)
        step = repo.resolve("software-dev", "specify")  # no pack_context
        assert step is not None
        assert step.title == "Built-in"


# ---------------------------------------------------------------------------
# Compound-key isolation
# ---------------------------------------------------------------------------


class TestCompoundKeyIsolation:
    """A shadow for software-dev/review must NOT affect documentation/review."""

    def test_software_dev_shadow_does_not_affect_documentation(
        self, tmp_path: Path
    ) -> None:
        """Core compound-key isolation invariant (FR-012).

        An org shadow for (software-dev, review) must leave
        (documentation, review) resolved from the built-in layer.
        """
        builtin_root = tmp_path / "builtin"
        org_root = tmp_path / "org"
        repo_root = tmp_path / "project"

        # Built-in steps for both mission types
        _write_step(builtin_root, "software-dev", "review", display_name="Built-in SD Review")
        _write_step(builtin_root, "documentation", "review", display_name="Built-in Doc Review")

        # Org shadow exists ONLY for software-dev/review
        _write_org_step(org_root, "software-dev", "review", display_name="Org SD Review")

        ctx = _StubPackContext(pack_roots=(org_root,), repo_root=repo_root)
        repo = MissionStepRepository(builtin_steps_root=builtin_root)

        # software-dev/review → org shadow wins
        sd_step = repo.resolve("software-dev", "review", pack_context=ctx)  # type: ignore[arg-type]
        assert sd_step is not None
        assert sd_step.title == "Org SD Review"

        # documentation/review → built-in still used (compound-key isolation)
        doc_step = repo.resolve("documentation", "review", pack_context=ctx)  # type: ignore[arg-type]
        assert doc_step is not None
        assert doc_step.title == "Built-in Doc Review"

    def test_project_shadow_for_one_mission_type_does_not_leak(
        self, tmp_path: Path
    ) -> None:
        builtin_root = tmp_path / "builtin"
        repo_root = tmp_path / "project"

        _write_step(builtin_root, "software-dev", "specify", display_name="Built-in SD Specify")
        _write_step(builtin_root, "documentation", "specify", display_name="Built-in Doc Specify")
        _write_project_step(repo_root, "software-dev", "specify", display_name="Project SD Specify")

        ctx = _StubPackContext(pack_roots=(), repo_root=repo_root)
        repo = MissionStepRepository(builtin_steps_root=builtin_root)

        sd_step = repo.resolve("software-dev", "specify", pack_context=ctx)  # type: ignore[arg-type]
        assert sd_step is not None
        assert sd_step.title == "Project SD Specify"

        doc_step = repo.resolve("documentation", "specify", pack_context=ctx)  # type: ignore[arg-type]
        assert doc_step is not None
        assert doc_step.title == "Built-in Doc Specify"

    def test_step_key_different_mission_type_same_step_id_distinct(self) -> None:
        """StepKey directly enforces the isolation invariant."""
        key_sd = StepKey("software-dev", "review")
        key_doc = StepKey("documentation", "review")
        assert key_sd != key_doc
        assert hash(key_sd) != hash(key_doc) or key_sd != key_doc  # at minimum unequal


# ---------------------------------------------------------------------------
# Missing step: returns None (no raise)
# ---------------------------------------------------------------------------


class TestMissingStep:
    """resolve() returns None for unknown steps (no exception raised)."""

    def test_unknown_step_id_returns_none(self, tmp_path: Path) -> None:
        _write_step(tmp_path, "software-dev", "specify")
        repo = MissionStepRepository(builtin_steps_root=tmp_path)
        assert repo.resolve("software-dev", "nonexistent") is None

    def test_unknown_mission_type_returns_none(self, tmp_path: Path) -> None:
        repo = MissionStepRepository(builtin_steps_root=tmp_path)
        assert repo.resolve("no-such-type", "specify") is None

    def test_empty_builtin_root_returns_none(self, tmp_path: Path) -> None:
        repo = MissionStepRepository(builtin_steps_root=tmp_path / "does-not-exist")
        assert repo.resolve("software-dev", "specify") is None


# ---------------------------------------------------------------------------
# resolve_all_for_mission_type
# ---------------------------------------------------------------------------


class TestResolveAllForMissionType:
    """resolve_all_for_mission_type returns all steps with shadowing applied."""

    def test_builtin_only(self, tmp_path: Path) -> None:
        _write_step(tmp_path, "software-dev", "specify")
        _write_step(tmp_path, "software-dev", "plan")
        _write_step(tmp_path, "software-dev", "implement")

        repo = MissionStepRepository(builtin_steps_root=tmp_path)
        result = repo.resolve_all_for_mission_type("software-dev")

        assert set(result.keys()) == {"specify", "plan", "implement"}
        for step in result.values():
            assert isinstance(step, MissionStep)

    def test_shadowed_steps_reflected(self, tmp_path: Path) -> None:
        builtin_root = tmp_path / "builtin"
        org_root = tmp_path / "org"

        _write_step(builtin_root, "software-dev", "specify", display_name="Built-in")
        _write_step(builtin_root, "software-dev", "review", display_name="Built-in Review")
        _write_org_step(org_root, "software-dev", "specify", display_name="Org Specify")

        ctx = _StubPackContext(pack_roots=(org_root,), repo_root=tmp_path / "project")
        repo = MissionStepRepository(builtin_steps_root=builtin_root)
        result = repo.resolve_all_for_mission_type("software-dev", pack_context=ctx)  # type: ignore[arg-type]

        assert "specify" in result
        assert "review" in result
        assert result["specify"].title == "Org Specify"  # org shadow wins
        assert result["review"].title == "Built-in Review"  # no shadow

    def test_empty_mission_type_returns_empty_dict(self, tmp_path: Path) -> None:
        repo = MissionStepRepository(builtin_steps_root=tmp_path)
        result = repo.resolve_all_for_mission_type("no-such-type")
        assert result == {}

    def test_project_shadow_in_all_result(self, tmp_path: Path) -> None:
        builtin_root = tmp_path / "builtin"
        repo_root = tmp_path / "project"

        _write_step(builtin_root, "software-dev", "specify", display_name="Built-in")
        _write_project_step(repo_root, "software-dev", "specify", display_name="Project")

        ctx = _StubPackContext(pack_roots=(), repo_root=repo_root)
        repo = MissionStepRepository(builtin_steps_root=builtin_root)
        result = repo.resolve_all_for_mission_type("software-dev", pack_context=ctx)  # type: ignore[arg-type]

        assert result["specify"].title == "Project"

    def test_cross_mission_type_steps_not_mixed(self, tmp_path: Path) -> None:
        _write_step(tmp_path, "software-dev", "specify")
        _write_step(tmp_path, "documentation", "gap-analysis")

        repo = MissionStepRepository(builtin_steps_root=tmp_path)

        sd_result = repo.resolve_all_for_mission_type("software-dev")
        doc_result = repo.resolve_all_for_mission_type("documentation")

        assert "specify" in sd_result
        assert "gap-analysis" not in sd_result
        assert "gap-analysis" in doc_result
        assert "specify" not in doc_result


# ---------------------------------------------------------------------------
# Shared resolve_all_for_mission_type cache (NFR-003, T007 proof #4,
# mission-step-creatability-01KXQA6R WP01)
# ---------------------------------------------------------------------------


class TestSharedResolveAllForMissionTypeCache:
    """One filesystem walk per ``(builtin_root, mission_type_id, pack_context)``,
    shared across instances/call sites -- not scoped to ``self`` and not
    dependent on ``MissionStepRepository.default()`` being memoised (it isn't;
    only ``MissionTypeRepository.default()`` singletons the repo *object*)."""

    def setup_method(self) -> None:
        MissionStepRepository.cache_clear()

    def teardown_method(self) -> None:
        MissionStepRepository.cache_clear()

    def _spy_walks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> list[str]:
        """Patch the cache-miss path and return the list it appends mission_type_ids to."""
        walk_calls: list[str] = []
        original_uncached = MissionStepRepository._resolve_all_for_mission_type_uncached

        def _spy(
            self: MissionStepRepository,
            mission_type_id: str,
            pack_context: object,
        ) -> dict[str, MissionStep]:
            walk_calls.append(mission_type_id)
            return original_uncached(self, mission_type_id, pack_context)  # type: ignore[arg-type]

        monkeypatch.setattr(
            MissionStepRepository, "_resolve_all_for_mission_type_uncached", _spy
        )
        return walk_calls

    def test_repeated_calls_across_instances_share_one_walk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_step(tmp_path, "software-dev", "specify")
        _write_step(tmp_path, "software-dev", "plan")
        walk_calls = self._spy_walks(monkeypatch)

        # Two independent, freshly-constructed instances against the SAME
        # builtin_root -- mirrors MissionStepRepository.default() NOT being
        # memoised (a fresh instance per call site) while the cache stays
        # shared regardless.
        repo_a = MissionStepRepository(builtin_steps_root=tmp_path)
        repo_b = MissionStepRepository(builtin_steps_root=tmp_path)

        repo_a.resolve_all_for_mission_type("software-dev", pack_context=None)
        repo_a.resolve_all_for_mission_type("software-dev", pack_context=None)
        repo_b.resolve_all_for_mission_type("software-dev", pack_context=None)

        assert walk_calls == ["software-dev"]

    def test_cache_clear_forces_a_rewalk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_step(tmp_path, "software-dev", "specify")
        walk_calls = self._spy_walks(monkeypatch)
        repo = MissionStepRepository(builtin_steps_root=tmp_path)

        repo.resolve_all_for_mission_type("software-dev", pack_context=None)
        MissionStepRepository.cache_clear()
        repo.resolve_all_for_mission_type("software-dev", pack_context=None)

        assert walk_calls == ["software-dev", "software-dev"]

    def test_distinct_mission_type_id_is_a_distinct_cache_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_step(tmp_path, "software-dev", "specify")
        _write_step(tmp_path, "documentation", "discover")
        walk_calls = self._spy_walks(monkeypatch)
        repo = MissionStepRepository(builtin_steps_root=tmp_path)

        repo.resolve_all_for_mission_type("software-dev", pack_context=None)
        repo.resolve_all_for_mission_type("documentation", pack_context=None)
        repo.resolve_all_for_mission_type("software-dev", pack_context=None)

        assert walk_calls == ["software-dev", "documentation"]

    def test_distinct_builtin_root_is_a_distinct_cache_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        _write_step(root_a, "software-dev", "specify", display_name="A")
        _write_step(root_b, "software-dev", "specify", display_name="B")
        walk_calls = self._spy_walks(monkeypatch)

        repo_a = MissionStepRepository(builtin_steps_root=root_a)
        repo_b = MissionStepRepository(builtin_steps_root=root_b)

        result_a = repo_a.resolve_all_for_mission_type("software-dev", pack_context=None)
        result_b = repo_b.resolve_all_for_mission_type("software-dev", pack_context=None)

        assert walk_calls == ["software-dev", "software-dev"]
        assert result_a["specify"].title == "A"
        assert result_b["specify"].title == "B"

    def test_two_consumers_of_the_same_key_share_one_walk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mirrors the real production shape post-cutover (FR-002): the
        retained ``action_sequence`` overlay and the projected ``template_set``
        slot both resolve steps for the same ``(mission_type, pack_context)``
        -- this must cost one walk, not two."""
        _write_step(tmp_path, "software-dev", "specify")
        walk_calls = self._spy_walks(monkeypatch)
        repo = MissionStepRepository(builtin_steps_root=tmp_path)

        # Consumer 1: the action_sequence overlay's resolution shape.
        steps_for_action_sequence = repo.resolve_all_for_mission_type(
            "software-dev", pack_context=None
        )
        # Consumer 2: the template_set slot's resolution shape (a separate
        # call, potentially from a different MissionStepRepository instance
        # in production -- MissionStepRepository.default() is not memoised).
        steps_for_template_set = MissionStepRepository(
            builtin_steps_root=tmp_path
        ).resolve_all_for_mission_type("software-dev", pack_context=None)

        assert walk_calls == ["software-dev"]
        assert steps_for_action_sequence == steps_for_template_set
