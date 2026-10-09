"""Cross-grain (type ⊕ action) doctrine-integrity gate + non-vacuity twin (FR-013).

A mission type's governance is the union of its *type grain*
(``governance-profile.yaml`` ``selected_*``) and its *action grain* (the
union of every ``actions/<action>/index.yaml``, WP02's
:func:`charter.activation.action_grain.aggregate_action_grain`). A single artifact URN
MUST appear in **at most one** grain — a double declaration is a
construction-time error
(:class:`charter.activation.mission_type_profiles.CrossGrainDoubleDeclarationError`),
never a silent de-duplication (FR-013).

This is the **load-bearing** enforcer for that invariant (ADR
2026-07-14-2's Enduring-verification: FR-013's home is a doctrine-module +
integration test with a non-vacuity twin). The resolver's lazy raise
(``charter.activation.mission_type_profiles.resolve_mission_type_context``, WP03) is
only a fast-fail path; this gate is the regression-protection surface,
exercised against the real shipped tree on every run.

T012 (gate)
-----------
For every shipped mission type: the union of the real type grain and the
real action grain must not raise. This is exactly WP02's IC-11 dup-scan
(:func:`charter.activation.action_grain.scan_builtin_cross_grain_duplicates`) — that
helper **is** the assertion; this test does not re-implement the
union/collision check (C-002).

Shipped doctrine is authored disjoint **on purpose**
(``plan/actions/plan/index.yaml``: "kept disjoint (FR-013)"), so today's
shipped tree passing this gate catches no existing defect — it is
forward-looking regression protection for future org/pack-authored grains.
T013 below proves the gate is not vacuously green.

Non-empty guard (CRITICAL — post-task squad correction)
---------------------------------------------------------
All four shipped mission types have an ``actions/`` directory, but
``plan``'s action indexes are *intentionally* all-empty-content
(``plan/actions/plan/index.yaml`` lists every field as ``[]``, by design) —
its aggregated action grain is legitimately empty, not a loader failure.
The non-empty assertion therefore keys on the **content-bearing allow-list**
``{software-dev, research, documentation}`` and never on ``actions/``-dir
presence; asserting non-empty for ``plan`` would red-main this gate on the
shipped tree (violates SC-002). Grain-line counts at authoring time:
software-dev 20, research 14, documentation 18, plan 0.

T013 (non-vacuity twin)
------------------------
A purpose-authored ``tmp_path`` tree with a deliberate type∩action URN
collision, loaded through the same production seam
(``MissionTypeProfileRepository`` -> ``_profile_type_grain`` +
``aggregate_action_grain`` -> ``ResolvedGovernance.from_grains``), must
raise ``CrossGrainDoubleDeclarationError``. This proves T012's green result
reflects a real disjointness check, not a loader that silently returns
empty grains.

Self-contained: uses the real shipped missions root (path-derived, mirroring
``test_shipped_graph_valid.py``'s ``SHIPPED_GRAPH`` constant) and
``tmp_path`` for the synthetic fixture — no new conftest.py is added to
``tests/charter_offering/drg/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.action_grain import aggregate_action_grain, scan_builtin_cross_grain_duplicates
from charter.activation.mission_type_profiles import (
    CrossGrainDoubleDeclarationError,
    ResolvedGovernance,
    _profile_type_grain,
)
from charter.activation.mission_type_profile_repository import MissionTypeProfileRepository
from charter.offering.missions.mission_type_repository import builtin_mission_type_ids

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]

#: The shipped missions root: ``packs/built-in/missions`` (relocated from
#: ``src/charter/offering/missions`` by mission
#: doctrine-consumer-surface-missions-extraction-01KZ6G6H, FR-005).
#: Path-derived from this file (mirrors ``test_shipped_graph_valid.py``'s
#: ``SHIPPED_GRAPH`` constant) rather than a shared fixture, per the
#: no-new-conftest constraint for this directory.
MISSIONS_ROOT = Path(__file__).resolve().parents[3] / "packs" / "built-in" / "missions"

#: Mission types whose action grain is expected to carry real content.
#: ``plan`` is deliberately excluded — its action indexes are intentionally
#: all-empty-content (see module docstring "Non-empty guard" above); keying
#: this allow-list on ``actions/``-dir presence instead would red-main the
#: gate on the shipped tree.
CONTENT_BEARING_MISSION_TYPES: frozenset[str] = frozenset({"software-dev", "research", "documentation"})


# ---------------------------------------------------------------------------
# T012 — doctrine-integrity gate
# ---------------------------------------------------------------------------


class TestCrossGrainIntegrityGate:
    """Every shipped mission type's type grain and action grain are disjoint."""

    def test_all_shipped_mission_types_are_cross_grain_disjoint(self) -> None:
        """WP02's IC-11 dup-scan is the assertion — no second scanner (C-002)."""
        scanned = scan_builtin_cross_grain_duplicates()

        assert set(scanned) == set(builtin_mission_type_ids())

    @pytest.mark.parametrize("mission_type", sorted(CONTENT_BEARING_MISSION_TYPES))
    def test_content_bearing_type_action_grain_is_non_empty(self, mission_type: str) -> None:
        """A vacuously-empty action grain would make the disjointness check meaningless."""
        grain = aggregate_action_grain(MISSIONS_ROOT, mission_type)

        assert any(grain[kind] for kind in grain), (
            f"{mission_type} action grain must be non-empty (content-bearing allow-list); got all-empty kinds {sorted(grain)}"
        )

    def test_plan_action_grain_is_legitimately_empty_not_vacuous(self) -> None:
        """``plan`` is excluded from the non-empty allow-list *because* its actions/
        directories exist but declare no content by design — confirm both halves of
        that claim so the exclusion above can't silently paper over a real regression.
        """
        actions_dir = MISSIONS_ROOT / "plan" / "actions"
        assert actions_dir.is_dir(), "plan must ship a real actions/ dir (empty CONTENT, not a missing dir)"

        grain = aggregate_action_grain(MISSIONS_ROOT, "plan")

        assert all(value == [] for value in grain.values())


# ---------------------------------------------------------------------------
# T013 — non-vacuity twin
# ---------------------------------------------------------------------------


def _write_colliding_tree(tmp_path: Path, *, mission_type: str, colliding_urn: str) -> None:
    """Author a temp-tree where ``mission_type`` declares ``colliding_urn`` in
    both its type grain (``governance-profile.yaml``) and its action grain
    (a single ``actions/<action>/index.yaml``).
    """
    type_dir = tmp_path / mission_type
    type_dir.mkdir(parents=True)
    (type_dir / "governance-profile.yaml").write_text(
        f"id: {mission_type}\nmission_type: {mission_type}\nselected_directives:\n  - {colliding_urn}\n",
        encoding="utf-8",
    )

    action_dir = type_dir / "actions" / "implement"
    action_dir.mkdir(parents=True)
    (action_dir / "index.yaml").write_text(
        f"action: implement\ndirectives:\n  - {colliding_urn}\n",
        encoding="utf-8",
    )


class TestNonVacuityTwin:
    """Proves T012's green result is a real check, not a vacuously-empty one."""

    def test_deliberate_type_action_collision_raises(self, tmp_path: Path) -> None:
        mission_type = "twin-type"
        _write_colliding_tree(tmp_path, mission_type=mission_type, colliding_urn="099-fake-directive")

        # Same production seam as scan_builtin_cross_grain_duplicates, pointed
        # at the synthetic tree instead of the shipped one: MissionTypeProfileRepository
        # -> _profile_type_grain + aggregate_action_grain -> ResolvedGovernance.from_grains.
        profile = MissionTypeProfileRepository(built_in_dir=tmp_path).get(mission_type)
        type_grain = _profile_type_grain(profile)
        action_grain = aggregate_action_grain(tmp_path, mission_type)

        with pytest.raises(CrossGrainDoubleDeclarationError) as exc_info:
            ResolvedGovernance.from_grains(type_grain=type_grain, action_grain=action_grain)

        assert exc_info.value.kind == "directives"
        assert exc_info.value.artifact == "099-fake-directive"

    def test_disjoint_synthetic_tree_does_not_raise(self, tmp_path: Path) -> None:
        """Control: the same seam over a non-colliding synthetic tree is clean.

        Confirms the twin's failure above is caused by the collision, not by
        some incidental defect in the synthetic-tree shape itself.
        """
        mission_type = "twin-type-clean"
        type_dir = tmp_path / mission_type
        type_dir.mkdir(parents=True)
        (type_dir / "governance-profile.yaml").write_text(
            f"id: {mission_type}\nmission_type: {mission_type}\nselected_directives:\n  - 001-type-only\n",
            encoding="utf-8",
        )
        action_dir = type_dir / "actions" / "implement"
        action_dir.mkdir(parents=True)
        (action_dir / "index.yaml").write_text(
            "action: implement\ndirectives:\n  - 002-action-only\n",
            encoding="utf-8",
        )

        profile = MissionTypeProfileRepository(built_in_dir=tmp_path).get(mission_type)
        type_grain = _profile_type_grain(profile)
        action_grain = aggregate_action_grain(tmp_path, mission_type)

        resolved = ResolvedGovernance.from_grains(type_grain=type_grain, action_grain=action_grain)

        assert resolved.selected_directives == ["001-type-only", "002-action-only"]
