"""WP01 (mission runtime-advance-guard-topology-wp-completion-01M1W6VZ, issue
#3884): direct + non-coord end-to-end reproduction for the ``_wp_blocks_step``
``Lane.UNINITIALIZED`` disjunct (FR-004/FR-005).

Written against ``_should_advance_wp_step``'s CURRENT, plain 2-arg signature
only -- no directory I/O beyond a plain ``tasks/`` dir, no ``placement_seam``,
no coord-topology fixture -- so this file has zero dependency on WP02's coord
fixture (only on WP02's WP itself finishing first, per the ``dependencies:
[WP02]`` edge on this WP's own tasks file).

A work package file under ``tasks/`` that was never claimed folds to
``Lane.UNINITIALIZED`` forever (``committed_authority.wp_ending``,
``src/runtime/next/committed_authority.py``). Before this WP's fix,
``_wp_blocks_step("implement", state, has_provenance)`` fell through both
disjuncts of its ``implement``-branch return expression for this state and
returned ``False`` (did not block) -- by omission, not by any deliberate
"this is fine" decision. See ``kitty-specs/runtime-advance-guard-topology-
wp-completion-01M1W6VZ/plan.md``'s Test Strategy item 1 for the full citation
this file implements (do not re-derive the reasoning here).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.next.runtime_bridge_guards import _should_advance_wp_step, _wp_blocks_step
from specify_cli.status.models import Lane
from specify_cli.status.wp_state import UninitializedState, wp_state_for

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_WP_ID = "WP01"


def _build_non_coord_fixture(tmp_path: Path, *, with_tasks_dir: bool = True) -> Path:
    """A plain (non-coord) ``feature_dir`` directly containing ``tasks/``.

    ``status.events.jsonl`` is touched empty (never any event appended for
    ``_WP_ID``) so ``committed_authority.wp_ending`` folds the WP to
    ``WpEnding(lane="uninitialized", acceptable=False, reason_source=None)`` --
    a genuinely never-claimed WP, not a mocked stand-in for one.
    """
    feature_dir = tmp_path / "feature"
    feature_dir.mkdir()
    (feature_dir / "status.events.jsonl").touch()
    if with_tasks_dir:
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / f"{_WP_ID}-sample.md").write_text(
            f"---\nwork_package_id: {_WP_ID}\ntitle: sample\n---\n# {_WP_ID}\n",
            encoding="utf-8",
        )
    return feature_dir


class TestT007DirectCallReproduction:
    """Step 2: the isolated direct-call test Sonar coverage attribution needs."""

    def test_wp_blocks_step_blocks_uninitialized_for_implement(self) -> None:
        state = UninitializedState()

        assert _wp_blocks_step("implement", state, has_provenance=False) is True


class TestT007EndToEndReproduction:
    """Step 3 (AC-2): the mission-as-a-whole answer for a non-coord fixture."""

    def test_should_advance_wp_step_blocks_for_never_claimed_wp(self, tmp_path: Path) -> None:
        feature_dir = _build_non_coord_fixture(tmp_path)

        result = _should_advance_wp_step("implement", feature_dir)

        assert result is False, "a WP scaffolded under tasks/ but never claimed (Lane.UNINITIALIZED) must block the implement -> review advance"


class TestT007RegressionPinsUnanchoredOnly:
    """Step 4: regression pins for the plain 2-arg (un-anchored) call only --
    the "anchored" variant lives in T012, since it needs T008's extended
    signature."""

    def test_no_tasks_dir_still_advances_unanchored(self, tmp_path: Path) -> None:
        """AC-3: the legitimate no-op case (a mission type with no ``tasks/``
        directory at all, e.g. ``plan``-family, per
        ``docs/architecture/mission-system.md:317``) is untouched by this
        fix."""
        feature_dir = _build_non_coord_fixture(tmp_path, with_tasks_dir=False)
        assert not (feature_dir / "tasks").is_dir()

        result = _should_advance_wp_step("implement", feature_dir)

        assert result is True

    def test_except_valueerror_block_does_not_fire_for_uninitialized(self) -> None:
        """AC-4: ``"uninitialized"`` IS a recognized lane string in
        ``wp_state.wp_state_for`` -- it resolves to a genuine
        ``UninitializedState``, never a ``ValueError``-triggered fallback (the
        ``except ValueError`` block at ``runtime_bridge.py``'s
        ``_should_advance_wp_step`` guards a DIFFERENT failure mode: a truly
        unknown lane string, which "uninitialized" is not)."""
        state = wp_state_for(str(Lane.UNINITIALIZED))

        assert isinstance(state, UninitializedState)
        assert state.lane is Lane.UNINITIALIZED


class TestGenesisLaneBlocksImplement:
    """Landing fold (#3981): Lane.GENESIS is the symmetric partner of
    Lane.UNINITIALIZED -- the other member of ``NON_DISPLAY_LANES``.

    ``GenesisState`` reports ``is_blocked=False`` and ``is_run_affecting=False``
    (a WP created but never lifecycled past genesis has entered no active lane),
    so before this fold it fell through the same ``implement``-branch disjunct
    the UNINITIALIZED fix closed and returned ``False`` (did not block) -- the
    exact fail-open class #3884 exists to close. A genesis-lane WP is pending
    work and must block the ``implement -> review`` advance.
    """

    def test_wp_blocks_step_blocks_genesis_for_implement(self) -> None:
        state = wp_state_for("genesis")

        assert state.is_blocked is False
        assert state.is_run_affecting is False
        assert _wp_blocks_step("implement", state, has_provenance=False) is True

    def test_genesis_still_advances_when_handed_off_partners_do_not_regress(self) -> None:
        # Guard-rail: the fold widens only the never-lifecycled case; genuinely
        # handed-off / accepted lanes must still NOT block (no over-blocking).
        for lane in ("for_review", "approved"):
            assert _wp_blocks_step("implement", wp_state_for(lane)) is False
