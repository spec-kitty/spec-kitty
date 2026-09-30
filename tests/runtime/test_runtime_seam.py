"""Seam-equivalence tests for WP06 — consumer switch (mission-step-authority-01KXNZMT).

WP02 injects a projected ``action_sequence``/``template_set`` into every
:class:`~charter.offering.missions.models.MissionType` at
``MissionTypeRepository._load`` time (see
``_inject_projected_fields``/``project_action_sequence``/
``project_template_set``). WP03/WP05 populated the mission-step data so the
projection is now non-empty for **all four** built-in mission types.

WP06's job was to confirm every *genuine* authority read of
``action_sequence``/``template_set`` consumes that injected/projected value —
not a bypass re-read of raw YAML — and to lock the finding with tests so a
future change cannot silently reintroduce a 5th authority (C-003).

Investigation result (T018/T019 — no code changes required, confirmation only):

- ``charter.activation.mission_type_profiles._resolve_action_slot`` (:694/697) calls
  ``charter.offering.missions.mission_type_repository.MissionTypeRepository.default()``
  and reads ``mission.action_sequence`` straight off the loaded model — the
  exact field WP02's ``_inject_projected_fields`` overlays before
  ``MissionType.model_validate()`` runs. There is no alternate/raw YAML
  re-parse in this resolver.

  **Update (S-C cutover, mission-step-creatability-01KXQA6R WP01):**
  ``_resolve_template_set_slot`` (:750, indicative) no longer reads a
  ``mission.template_set`` model field at all — that field and its
  ``_inject_projected_fields`` overlay were retired atomically (FR-001).
  The slot now computes ``project_template_set(steps)`` directly from
  ``MissionStepRepository.resolve_all_for_mission_type(mission_type,
  pack_context=None)`` at the consumption boundary — still a single
  authority (the step authority), just no longer routed through a
  ``MissionType`` model field as an intermediate.
- ``runtime.next.decision._build_prompt_or_error`` (:606) and
  ``runtime.next.runtime_bridge_composition._should_dispatch_via_composition``
  (:186) / ``_composition_dispatch_inputs`` (:321) all call
  ``charter.activation.mission_type_profiles.resolve_mission_type_context(...).action_sequence``
  — the bundle built from ``_resolve_action_slot`` above — so they consume the
  projected value transitively. No consumer reads a raw/flat field directly.

This module locks that finding with:

1. Seam-equivalence — the four built-in types' ``action_sequence``/
   ``template_set`` resolved through the seam equal the pinned authored (formerly raw
   YAML-authored) contract values (T020).
2. Consumer transitivity — the three cited call sites observe the seam's
   resolved value rather than bypassing it (T019).
3. The ``extends`` fallback check (T020) — none of the four built-in types
   sets ``extends``, so switching resolvers onto the cached model does not
   change existing ``extends``-widening behavior (there is none to change).
4. No hot-path uncached I/O (T020) — ``MissionTypeRepository.default()`` is
   memoized (``functools.cache``), so repeated resolver calls never re-walk
   the ``mission-steps/`` tree.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from charter.activation.mission_type_profiles import ResolvedMissionType, resolve_mission_type_context
from charter.offering.missions.mission_step_repository import MissionStepRepository
from charter.offering.missions.mission_type_repository import MissionTypeRepository

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_BUILTIN_TYPE_IDS = ("documentation", "plan", "research", "software-dev")


# Hand-pinned authored contract for the 4 built-in types. Post-WP07 the flat
# ``action_sequence``/``template_set`` are removed from the mission_types YAML
# (the projection from step.yaml is the sole authority), so the seam-equivalence
# assertions can no longer read the YAML as ground truth — they compare against
# this independent, human-authored pin instead (an enduring behavioural contract,
# not a tautology against the projection the seam itself uses).
_EXPECTED_AUTHORED: dict[str, dict[str, Any]] = {
    "software-dev": {
        "action_sequence": ["specify", "plan", "tasks", "implement", "review"],
        "template_set": {"spec": "spec-template.md", "plan": "plan-template.md"},
    },
    "documentation": {
        "action_sequence": [
            "discover", "audit", "design", "generate", "validate", "publish", "accept",
        ],
        # S-C Concern B (mission-step-creatability-01KXQA6R WP02, reconciled by
        # WP05, C-003/C-010): documentation authors a spec ref (discover) and a
        # plan ref (design), each with a per-type-unique template_file name
        # (NFR-006).
        "template_set": {
            "spec": "documentation-spec-template.md",
            "plan": "documentation-plan-template.md",
        },
    },
    "research": {
        "action_sequence": ["scoping", "methodology", "gathering", "synthesis", "output"],
        # S-C Concern B (mission-step-creatability-01KXQA6R WP03, C-003/C-010):
        # research authors a spec ref (scoping) and a plan ref (methodology),
        # each with a per-type-unique template_file name (NFR-006).
        "template_set": {
            "spec": "research-spec-template.md",
            "plan": "research-plan-template.md",
        },
    },
    "plan": {
        "action_sequence": ["specify", "research", "plan", "review"],
        # S-C Concern B (mission-step-creatability-01KXQA6R WP04, reconciled by
        # WP05, C-003/C-010): plan authors a spec ref (specify) and a plan ref
        # (plan), each with a per-type-unique template_file name (NFR-006).
        "template_set": {
            "spec": "plan-spec-skeleton.md",
            "plan": "plan-plan-skeleton.md",
        },
    },
}


def _expected_authored(mission_type_id: str) -> dict[str, Any]:
    """The independent hand-pinned authored contract for a built-in type.

    Replaces the pre-WP07 raw-YAML read (the YAML no longer carries these fields);
    the seam-resolved value must equal this known contract.
    """
    return _EXPECTED_AUTHORED[mission_type_id]


def _resolve_via_seam(tmp_path: Path, mission_type_id: str) -> ResolvedMissionType:
    with patch(
        "charter.activation.mission_type_profiles.existing_mission_types",
        return_value=list(_BUILTIN_TYPE_IDS),
    ):
        return resolve_mission_type_context(tmp_path, mission_type=mission_type_id)


# ---------------------------------------------------------------------------
# 1. Seam-equivalence (T020) — resolved value == pinned authored contract, all 4 types
# ---------------------------------------------------------------------------


class TestSeamEquivalence:
    """The seam's resolved action_sequence/template_set equal the pinned authored contract."""

    @pytest.mark.parametrize("mission_type_id", _BUILTIN_TYPE_IDS)
    def test_action_sequence_matches_authored_contract(
        self, tmp_path: Path, mission_type_id: str
    ) -> None:
        expected = _expected_authored(mission_type_id)
        bundle = _resolve_via_seam(tmp_path, mission_type_id)

        assert bundle.action_sequence == expected["action_sequence"]

    @pytest.mark.parametrize("mission_type_id", _BUILTIN_TYPE_IDS)
    def test_template_set_matches_authored_contract(
        self, tmp_path: Path, mission_type_id: str
    ) -> None:
        expected = _expected_authored(mission_type_id)
        bundle = _resolve_via_seam(tmp_path, mission_type_id)

        expected_template_set = expected.get("template_set")
        if expected_template_set is None:
            assert bundle.template_set is None
        else:
            assert bundle.template_set is not None
            assert dict(bundle.template_set) == expected_template_set

    def test_software_dev_template_set_is_non_empty_dict(self, tmp_path: Path) -> None:
        """Ground the dict-branch with software-dev's two content templates.
        All four built-in types now author a non-null template_set (WP01
        software-dev cutover + WP02 documentation + WP03 research + WP04
        plan, reconciled by WP05) -- see ``_EXPECTED_AUTHORED`` for each
        type's own pair, and ``test_template_set_matches_authored_contract``
        above for the generic per-type dict-branch assertion. There is no
        longer a null-``template_set`` branch among the four built-in types
        to ground here (the retired ``test_non_software_dev_template_set_is_none``
        parametrization covered that branch pre-WP05)."""
        bundle = _resolve_via_seam(tmp_path, "software-dev")
        assert bundle.template_set == {
            "spec": "spec-template.md",
            "plan": "plan-template.md",
        }


class TestGoldenParityUnaffectedByPackContextThreading:
    """WP04/T010 step 3 — golden-parity extension (User Story 3 AC1).

    WP04 threads a real, non-``None`` ``PackContext`` into
    ``_resolve_action_slot``/``_resolve_template_set_slot`` (FR-002). This
    class extends ``TestSeamEquivalence`` above by exercising that real
    threading against a ``PackContext`` that carries a genuine (but
    unrelated) org pack root, and asserting all 4 built-in types still
    resolve byte-identically to the pinned authored contract.

    Not a red-first pin (unlike ``TestPackContextProjection`` in
    ``tests/charter/test_mission_type_profiles.py``): built-in types already
    resolve correctly pre-WP04 -- ``TestSeamEquivalence`` above never mocks
    ``PackContext.from_config`` either, so it already exercises this WP's
    new code path incidentally. This class is the deliberate regression
    backstop (not incidental coverage) proving a real org pack root, present
    but declaring nothing for any built-in type id, never perturbs built-in
    output -- the mechanism CL-001 requires: no cross-project/cross-layer
    pollution.
    """

    @pytest.mark.parametrize("mission_type_id", _BUILTIN_TYPE_IDS)
    def test_builtin_type_unaffected_by_real_pack_context_with_org_root(
        self, tmp_path: Path, mission_type_id: str
    ) -> None:
        from charter.activation.pack_context import PackContext

        expected = _expected_authored(mission_type_id)
        org_root = tmp_path / "org-pack"
        (org_root / "mission_types").mkdir(parents=True)
        pack_context = PackContext(
            activated_kinds=frozenset(),
            activated_mission_types=frozenset(_BUILTIN_TYPE_IDS),
            pack_roots=(tmp_path / "unused-builtin-placeholder", org_root),
            org_pack_names=("org-pack",),
            repo_root=tmp_path,
        )

        with patch(
            "charter.activation.pack_context.PackContext.from_config", return_value=pack_context
        ):
            bundle = _resolve_via_seam(tmp_path, mission_type_id)

        assert bundle.action_sequence == expected["action_sequence"]
        expected_template_set = expected.get("template_set")
        if expected_template_set is None:
            assert bundle.template_set is None
        else:
            assert bundle.template_set is not None
            assert dict(bundle.template_set) == expected_template_set

    def test_builtin_layer_scan_receives_the_real_pack_context_once_per_type(
        self, tmp_path: Path
    ) -> None:
        """WP01/T004 (NFR-004, mission mission-types-empty-action-sequence-01M0RMCA,
        #3701): closes two claims with call-level evidence rather than
        architectural assertion alone.

        1. **No new filesystem walk**: threading ``pack_context`` into the
           built-in-equivalent layer's own ``scan_mission_types_dir(base_dir,
           pack_context=pack_context)`` call (this WP's fix) must not cause
           ``"software-dev"``'s own step set to be resolved more than once.
        2. **Not vacuous**: an empirical revert of just that one call site
           (confirmed manually per this subtask's own instructions -- not
           committed) leaves the sibling test directly above
           (``test_builtin_type_unaffected_by_real_pack_context_with_org_root``)
           passing unchanged, because this fixture's org root declares no
           content for any built-in type id -- the byte-level parity
           assertion is correctly invariant either way (an *unrelated* org
           pack must never perturb output, by design), so it cannot by
           itself prove the new call site is live. This test closes that
           gap directly: it asserts the resolved call for ``"software-dev"``
           actually received *this* real, non-``None`` ``pack_context``
           instance (identity, not just a truthy check), which only WP01's
           fix could deliver -- pre-fix, ``_inject_projected_fields``
           hardcoded ``pack_context=None`` regardless of what its callers
           held (see that function's own pre-WP01 docstring in git history).

        Spy shape (deviation from the WP prompt's literal instance-``patch.object``
        suggestion, recorded here and in the tracer files per this mission's own
        "verify rather than trust" standard): ``MissionStepRepository.default()``
        is a plain ``@classmethod`` with **no** ``functools.cache`` -- unlike
        ``MissionTypeRepository.default()`` -- so it returns a *fresh* instance on
        every call. An instance-level
        ``patch.object(instance, "resolve_all_for_mission_type", wraps=...)``
        against a pre-captured ``instance`` therefore observes **zero** calls
        (empirically confirmed: the seam's own internal
        ``MissionStepRepository.default()`` call constructs a *different* object),
        not a `TypeError`. This test instead reuses the plain-function
        class-attribute-spy shape ``TestMemoizedDefaultNoHotPathIO.
        test_default_does_not_rewalk_mission_steps_on_repeat_calls`` above already
        applies successfully in this same file: a plain function (not a ``Mock``)
        set as the class attribute correctly binds ``self`` via Python's normal
        descriptor protocol when accessed through *any* instance, sidestepping the
        instance-identity problem entirely.

        Counts only calls whose ``mission_type_id`` is ``"software-dev"``:
        the built-in-equivalent layer's scan loads all 4 built-in YAML
        files in one pass (``TestMemoizedDefaultNoHotPathIO`` above pins
        this: ``len(calls) == len(_BUILTIN_TYPE_IDS)`` for a full-roster
        resolution), so a raw, unfiltered call count would conflate "one
        walk per type in the directory" (expected, unrelated to this WP)
        with "one walk for the single type this test resolves" (the actual
        claim under test).
        """
        from charter.activation.pack_context import PackContext

        org_root = tmp_path / "org-pack"
        (org_root / "mission_types").mkdir(parents=True)
        pack_context = PackContext(
            activated_kinds=frozenset(),
            activated_mission_types=frozenset(_BUILTIN_TYPE_IDS),
            pack_roots=(tmp_path / "unused-builtin-placeholder", org_root),
            org_pack_names=("org-pack",),
            repo_root=tmp_path,
        )

        original = MissionStepRepository.resolve_all_for_mission_type
        calls: list[tuple[str, Any]] = []

        def _spy(
            self: MissionStepRepository,
            mission_type_id: str,
            pack_context: Any = None,
        ) -> dict[str, Any]:
            calls.append((mission_type_id, pack_context))
            return original(self, mission_type_id, pack_context)

        with (
            patch.object(MissionStepRepository, "resolve_all_for_mission_type", _spy),
            patch(
                "charter.activation.pack_context.PackContext.from_config",
                return_value=pack_context,
            ),
        ):
            _resolve_via_seam(tmp_path, "software-dev")

        calls_for_software_dev = [c for c in calls if c[0] == "software-dev"]
        assert len(calls_for_software_dev) == 1
        assert calls_for_software_dev[0][1] is pack_context

    def test_org_root_content_actually_resolves_through_the_seam(
        self, tmp_path: Path
    ) -> None:
        """PR-TESTS-001 (pre-merge squad, mission up-mission-type-seam-01KZY1JB):
        the sibling test above (``test_builtin_type_unaffected_by_real_pack_
        context_with_org_root``) `mkdir`'s the org root's ``mission_types/``
        directory but never writes a YAML into it -- the org layer always
        scans to ``[]``, so that test's assertions hold identically whether
        WP04's ``PackContext`` threading exists or is fully reverted
        (empirically confirmed by the squad: reverting
        ``_resolve_action_slot``/``_resolve_template_set_slot`` to bypass
        ``resolve_layered_mission_types``/``pack_context`` entirely still
        left that test 4/4 green). This test gives the SAME kind of org root
        real, non-colliding content -- a custom id sharing nothing with any
        built-in type -- so the layered-merge code path this class claims to
        guard is actually exercised end to end, closing the vacuity gap.
        """
        from charter.activation.pack_context import PackContext

        org_root = tmp_path / "org-pack"
        mt_dir = org_root / "mission_types"
        mt_dir.mkdir(parents=True)
        (mt_dir / "unrelated-custom.yaml").write_text(
            "schema_version: 1\n"
            "id: unrelated-custom\n"
            "display_name: Unrelated Custom\n"
            "action_sequence:\n"
            "  - design\n"
            "  - implement\n",
            encoding="utf-8",
        )
        activated = ["unrelated-custom", *_BUILTIN_TYPE_IDS]
        pack_context = PackContext(
            activated_kinds=frozenset(),
            activated_mission_types=frozenset(activated),
            pack_roots=(tmp_path / "unused-builtin-placeholder", org_root),
            org_pack_names=("org-pack",),
            repo_root=tmp_path,
        )

        MissionTypeRepository.cache_clear()
        try:
            with (
                patch(
                    "charter.activation.mission_type_profiles.existing_mission_types",
                    return_value=activated,
                ),
                patch(
                    "charter.activation.pack_context.PackContext.from_config",
                    return_value=pack_context,
                ),
            ):
                bundle = resolve_mission_type_context(tmp_path, mission_type="unrelated-custom")
        finally:
            MissionTypeRepository.cache_clear()

        assert bundle.action_sequence == ["design", "implement"]


# ---------------------------------------------------------------------------
# 2. Consumer transitivity (T019) — the three cited call sites read the seam
# ---------------------------------------------------------------------------


class TestConsumerTransitivity:
    """decision.py:606 and runtime_bridge_composition.py:186/321 observe the
    seam's resolved action_sequence rather than bypassing it.
    """

    def test_should_dispatch_via_composition_true_for_seam_action(
        self, tmp_path: Path
    ) -> None:
        from runtime.next.runtime_bridge_composition import (
            _should_dispatch_via_composition,
        )

        with patch(
            "charter.activation.mission_type_profiles.existing_mission_types",
            return_value=list(_BUILTIN_TYPE_IDS),
        ):
            result = _should_dispatch_via_composition(
                "software-dev", "specify", run_dir=None, repo_root=tmp_path
            )

        assert result is True

    def test_should_dispatch_via_composition_false_for_action_outside_sequence(
        self, tmp_path: Path
    ) -> None:
        from runtime.next.runtime_bridge_composition import (
            _should_dispatch_via_composition,
        )

        with patch(
            "charter.activation.mission_type_profiles.existing_mission_types",
            return_value=list(_BUILTIN_TYPE_IDS),
        ):
            result = _should_dispatch_via_composition(
                "software-dev",
                "not-a-real-action",
                run_dir=None,
                repo_root=tmp_path,
            )

        assert result is False

    def test_composition_dispatch_inputs_short_circuits_on_seam_action(
        self, tmp_path: Path
    ) -> None:
        from runtime.next.runtime_bridge_composition import (
            _composition_dispatch_inputs,
        )

        with patch(
            "charter.activation.mission_type_profiles.existing_mission_types",
            return_value=list(_BUILTIN_TYPE_IDS),
        ):
            result = _composition_dispatch_inputs(
                repo_root=tmp_path,
                run_dir=tmp_path / "does-not-exist",
                mission="software-dev",
                step_id="specify",
                action="specify",
            )

        # A seam-recognised action short-circuits to (None, None) without
        # ever touching run_dir (which does not exist on disk).
        assert result == (None, None)

    def test_build_prompt_or_error_bypasses_prompt_builder_for_seam_action(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """decision.py's composed-action fast path (:606) never reaches the
        file-based ``build_prompt`` for an action the seam recognises."""
        from runtime.next.decision import _build_prompt_or_error

        def _fail_if_called(**_kwargs: object) -> None:
            raise AssertionError(
                "build_prompt should not be called for a seam-recognised "
                "composed action"
            )

        monkeypatch.setattr(
            "runtime.next.prompt_builder.build_prompt", _fail_if_called
        )

        with patch(
            "charter.activation.mission_type_profiles.existing_mission_types",
            return_value=list(_BUILTIN_TYPE_IDS),
        ):
            path, err, _code = _build_prompt_or_error(
                action="specify",
                feature_dir=tmp_path / "kitty-specs" / "some-mission",
                mission_slug="some-mission",
                wp_id=None,
                agent="claude",
                repo_root=tmp_path,
                mission_type="software-dev",
            )

        assert err is None
        assert path is not None
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# 3. extends-fallback check (T020) — inert for all 4 built-in types
# ---------------------------------------------------------------------------


class TestExtendsFallbackInert:
    """None of the 4 built-in mission types relies on the ``extends``
    fallback in ``_resolve_action_slot`` (:692-695) to supply an
    otherwise-empty ``action_sequence``.

    Switching the resolvers onto the cached projected model therefore cannot
    regress ``extends``-based inheritance for any built-in type: there is
    none in play today. This is a pre-existing-behavior-preservation check,
    not a new feature.
    """

    @pytest.mark.parametrize("mission_type_id", _BUILTIN_TYPE_IDS)
    def test_builtin_type_does_not_set_extends(self, mission_type_id: str) -> None:
        mission = MissionTypeRepository.default().get(mission_type_id)
        assert mission is not None
        assert mission.extends is None

    @pytest.mark.parametrize("mission_type_id", _BUILTIN_TYPE_IDS)
    def test_builtin_type_action_sequence_is_authored_not_inherited(
        self, mission_type_id: str
    ) -> None:
        """Every built-in type's action_sequence comes from its own (projected)
        value, never from a parent via ``extends`` (there is no parent)."""
        mission = MissionTypeRepository.default().get(mission_type_id)
        assert mission is not None
        assert mission.action_sequence  # non-empty per the model's validator


# ---------------------------------------------------------------------------
# 4. No hot-path uncached I/O (T020) — memoized default()
# ---------------------------------------------------------------------------


class TestMemoizedDefaultNoHotPathIO:
    """``MissionTypeRepository.default()`` is memoized: repeated resolver
    calls never re-walk the ``mission-steps/`` tree that the WP02 injection
    reads via ``MissionStepRepository.resolve_all_for_mission_type``.
    """

    def test_default_returns_identical_cached_instance(self) -> None:
        first = MissionTypeRepository.default()
        second = MissionTypeRepository.default()
        assert first is second

    def test_default_does_not_rewalk_mission_steps_on_repeat_calls(self) -> None:
        MissionTypeRepository.default.cache_clear()
        original = MissionStepRepository.resolve_all_for_mission_type
        calls: list[str] = []

        def _spy(
            self: MissionStepRepository,
            mission_type_id: str,
            pack_context: Any = None,
        ) -> dict[str, Any]:
            calls.append(mission_type_id)
            return original(self, mission_type_id, pack_context)

        try:
            with patch.object(
                MissionStepRepository, "resolve_all_for_mission_type", _spy
            ):
                MissionTypeRepository.default()
                MissionTypeRepository.default()
                MissionTypeRepository.default()
        finally:
            # Rebuild the real (unpatched) cache so later tests in the same
            # process see the genuine repository, not one built via the spy
            # wrapper's closure.
            MissionTypeRepository.default.cache_clear()
            MissionTypeRepository.default()

        # One walk per built-in type during the SINGLE underlying _load(),
        # not one walk per default() call (3 calls above, 4 built-in types).
        assert len(calls) == len(_BUILTIN_TYPE_IDS)
        assert set(calls) == set(_BUILTIN_TYPE_IDS)
