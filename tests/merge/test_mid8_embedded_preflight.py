"""Regression: merge preflight must compose the mid8-era mission branch (#1978).

The merge-blocking false-negative (#1978): the three "false-compose" sites
reconstructed the mission integration branch with a bare ``f"kitty/mission-{slug}"``
f-string. That f-string drops the ``-<mid8>`` disambiguator and never strips a stale
``NNN-`` prefix, so for a mid8-era mission whose slug carries a stale numeric prefix
(or whose canonical branch differs from the naive compose) preflight reports a
*missing* mission branch even though the real branch exists.

This mission's own slug embeds its mid8 (``…-01KV6510``), making it the P1
dogfooding driver: its merge depends on these sites routing through the WP01 seam
``mission_branch_name_required(slug, mission_id)`` instead of the f-string.

The cases below pin:
  * RED-first: a mid8-era mission (stale ``NNN-`` prefix + declared ``mission_id``)
    whose real branch is ``kitty/mission-<human-slug>-<mid8>`` — the f-string compose
    mis-targets ``kitty/mission-<NNN>-<slug>`` (false-negative). After the fix the
    seam composes the correct branch.
  * an embedded-mid8 slug with no declared ``mission_id`` still resolves (the
    embedded tail is the disambiguator).
  * a legacy ``NNN-`` slug with no ``mission_id`` still resolves to the legacy branch.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.cli.commands.merge import _check_mission_branch
from specify_cli.lanes.branch_naming import (
    reset_legacy_failover_warning,
    worktree_path,
)
from specify_cli.merge.preflight import target_branch_sync_remediation

pytestmark = pytest.mark.fast


# A mid8-era mission whose slug still carries a stale NNN- prefix. The canonical
# branch strips the prefix and keeps the mid8: kitty/mission-foo-bar-01KV6510.
_NNN_SLUG = "057-foo-bar-01KV6510"
_MISSION_ID = "01KV6510ATWWFXS3K5ZJ9E5008"
_CANONICAL_BRANCH = "kitty/mission-foo-bar-01KV6510"
_NAIVE_FSTRING_BRANCH = f"kitty/mission-{_NNN_SLUG}"  # the wrong, never-created branch


class TestCheckMissionBranchMid8:
    def test_mid8_mission_resolves_canonical_branch_not_fstring(
        self, tmp_path: Path
    ) -> None:
        """RED-first (#1978): preflight must look for the seam-composed branch.

        Before the fix, ``expected_branch`` falls back to ``f"kitty/mission-{slug}"``
        which is ``kitty/mission-057-foo-bar-01KV6510`` — a branch that was never
        created. The real branch is ``kitty/mission-foo-bar-01KV6510``. We assert the
        preflight targets the canonical branch (so an existing canonical branch is
        FOUND, not falsely reported missing).
        """
        assert _CANONICAL_BRANCH != _NAIVE_FSTRING_BRANCH  # guards the regression

        # The canonical branch exists; the naive f-string branch does not.
        def has_ref(_repo: Path, ref: str) -> bool:
            return ref == _CANONICAL_BRANCH

        with patch(
            "specify_cli.merge.preflight._has_branch_ref",
            side_effect=has_ref,
        ):
            exists, blocker = _check_mission_branch(
                _NNN_SLUG, tmp_path, mission_id=_MISSION_ID
            )

        assert exists is True, (
            "preflight must resolve the canonical mid8-era branch, not the naive "
            "f-string compose that drops the mid8 / keeps the stale NNN- prefix"
        )
        assert blocker is None

    def test_mid8_mission_blocker_reports_canonical_branch(
        self, tmp_path: Path
    ) -> None:
        """When the canonical branch is genuinely missing, the blocker names it."""
        with patch(
            "specify_cli.merge.preflight._has_branch_ref",
            return_value=False,
        ), patch(
            "specify_cli.merge.preflight.run_command",
            return_value=(0, "abc1234def5678\n", ""),
        ):
            exists, blocker = _check_mission_branch(
                _NNN_SLUG, tmp_path, mission_id=_MISSION_ID
            )

        assert exists is False
        assert blocker is not None
        assert blocker["expected_branch"] == _CANONICAL_BRANCH
        assert blocker["expected_branch"] != _NAIVE_FSTRING_BRANCH

    def test_embedded_mid8_slug_without_mission_id_resolves(
        self, tmp_path: Path
    ) -> None:
        """A slug already carrying its mid8 tail resolves without a declared id."""
        slug = "mission-identity-seam-and-1908-panel-01KV6510"
        canonical = f"kitty/mission-{slug}"
        with patch(
            "specify_cli.merge.preflight._has_branch_ref",
            side_effect=lambda _repo, ref: ref == canonical,
        ):
            exists, blocker = _check_mission_branch(slug, tmp_path, mission_id=None)

        assert exists is True
        assert blocker is None

    def test_legacy_nnn_slug_without_mission_id_resolves(
        self, tmp_path: Path
    ) -> None:
        """A pre-083 legacy NNN- slug still composes the legacy branch."""
        slug = "017-my-legacy-feature"
        canonical = f"kitty/mission-{slug}"
        with patch(
            "specify_cli.merge.preflight._has_branch_ref",
            side_effect=lambda _repo, ref: ref == canonical,
        ):
            exists, blocker = _check_mission_branch(slug, tmp_path, mission_id=None)

        assert exists is True
        assert blocker is None

    def test_explicit_expected_branch_still_wins(self, tmp_path: Path) -> None:
        """A recorded lanes.json.mission_branch is honoured verbatim."""
        recorded = "kitty/mission-explicitly-recorded-01KQTEST"
        with patch(
            "specify_cli.merge.preflight._has_branch_ref",
            side_effect=lambda _repo, ref: ref == recorded,
        ):
            exists, blocker = _check_mission_branch(
                _NNN_SLUG,
                tmp_path,
                expected_branch=recorded,
                mission_id=_MISSION_ID,
            )

        assert exists is True
        assert blocker is None


class TestTargetBranchSyncRemediationMid8:
    def _status(self) -> object:
        from specify_cli.merge.push_preflight import TargetBranchSyncStatus

        return TargetBranchSyncStatus(
            target_branch="main",
            tracking_branch="origin/main",
            state="ahead",
            ahead_count=1,
            behind_count=0,
        )

    def test_remediation_routes_mid8_branch_via_seam(self) -> None:
        """RED-first (#1978): the focused-PR source branch must be the canonical one.

        Without a recorded ``mission_branch`` the remediation previously fell back to
        ``f"kitty/mission-{slug}"`` — which for a mid8-era NNN- slug is the wrong,
        never-created branch. With the seam it composes the canonical branch.
        """
        lines = target_branch_sync_remediation(
            self._status(),
            mission_slug=_NNN_SLUG,
            mission_branch=None,
            mission_id=_MISSION_ID,
        )
        focused_pr_line = next(
            line for line in lines if "git switch -c" in line
        )
        assert _CANONICAL_BRANCH in focused_pr_line
        assert _NAIVE_FSTRING_BRANCH not in focused_pr_line

    def test_remediation_honours_recorded_mission_branch(self) -> None:
        """A recorded mission_branch is used verbatim (no recompose)."""
        recorded = "kitty/mission-recorded-branch-01KQTEST"
        lines = target_branch_sync_remediation(
            self._status(),
            mission_slug=_NNN_SLUG,
            mission_branch=recorded,
            mission_id=_MISSION_ID,
        )
        focused_pr_line = next(line for line in lines if "git switch -c" in line)
        assert recorded in focused_pr_line


class TestCheckMissionBranchResolverWarning:
    """WP02 c1: ``_check_mission_branch`` now RESOLVES via ``resolve_branch_name``.

    The seam carries the canonical-first / legacy-failover-with-one-shot-warning
    contract (FR-004). These cases pin that the warning behaviour propagates
    through the preflight search path:
      * canonical / embedded-mid8 slug → correct branch, NO deprecation warning;
      * legacy ``NNN-`` slug (no mission_id) → correct legacy branch + EXACTLY ONE
        deprecation warning (asserted one-shot via ``reset_legacy_failover_warning``).
    """

    def test_embedded_slug_resolves_without_warning(self, tmp_path: Path) -> None:
        """A canonical/embedded slug resolves to its branch and emits no warning."""
        reset_legacy_failover_warning()
        slug = "mission-identity-seam-and-1908-panel-01KV6510"
        canonical = f"kitty/mission-{slug}"
        with patch(
            "specify_cli.merge.preflight._has_branch_ref",
            side_effect=lambda _repo, ref: ref == canonical,
        ), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            exists, blocker = _check_mission_branch(slug, tmp_path, mission_id=None)

        assert exists is True
        assert blocker is None
        dep = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert dep == [], "canonical/embedded resolution must not warn"

    def test_legacy_slug_resolves_with_one_shot_warning(self, tmp_path: Path) -> None:
        """A legacy NNN- slug failovers with exactly one deprecation warning."""
        reset_legacy_failover_warning()
        slug = "017-my-legacy-feature"
        canonical = f"kitty/mission-{slug}"
        with patch(
            "specify_cli.merge.preflight._has_branch_ref",
            side_effect=lambda _repo, ref: ref == canonical,
        ), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            # Two preflight checks in the same process: the deprecation warning
            # must fire AT MOST once (one-shot guard).
            first_exists, first_blocker = _check_mission_branch(
                slug, tmp_path, mission_id=None
            )
            _second_exists, _second_blocker = _check_mission_branch(
                slug, tmp_path, mission_id=None
            )

        assert first_exists is True
        assert first_blocker is None
        dep = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(dep) == 1, "legacy failover must warn exactly once per process"


class TestWorktreeTeardownSeamRouting:
    """WP02 c1 (#1899): merge teardown must resolve the allocator-created path.

    The ``--remove-worktree`` teardown loop previously guessed
    ``f"{mission_slug}-{lane_id}"`` with NO mid8. For a mid8-era mission whose slug
    embeds its mid8 the allocator creates ``<slug-with-mid8>-<lane>``; the bare
    guess happens to match there ONLY because the mid8 is in the slug. Routing the
    teardown through ``worktree_path(main_repo, slug, mission_id=…, lane_id=…)`` —
    fed the REAL ``mission_id`` (resolved exactly as ``_baseline_mission_id``) —
    makes the resolution explicit and authoritative, and proves byte-identical to
    the allocator path for the embedded-mid8 case (this mission's own shape).
    """

    def test_embedded_mission_teardown_matches_allocator_path(
        self, tmp_path: Path
    ) -> None:
        """Teardown seam path == the WP03 allocator's on-disk worktree path."""
        slug = "mission-identity-seam-and-1908-panel-01KV6510"
        lane_id = "lane-b"

        # What the WP03 allocator (worktree_allocator.py) composes on disk.
        allocator_path = tmp_path / ".worktrees" / f"{slug}-{lane_id}"

        # What the routed teardown now resolves, fed the REAL mission_id.
        teardown_path = worktree_path(
            tmp_path, slug, mission_id=_MISSION_ID, lane_id=lane_id
        )

        assert teardown_path == allocator_path, (
            "the routed teardown must resolve the SAME path the allocator created; "
            "the old no-mid8 f-string is the resolution the seam now subsumes"
        )

    def test_teardown_seam_keeps_mid8_segment_for_nnn_slug(
        self, tmp_path: Path
    ) -> None:
        """With a real mission_id the seam keeps the mid8 — the old bare guess dropped it."""
        slug = "057-foo-bar"
        lane_id = "lane-a"

        old_bare_guess = tmp_path / ".worktrees" / f"{slug}-{lane_id}"
        teardown_path = worktree_path(
            tmp_path, slug, mission_id=_MISSION_ID, lane_id=lane_id
        )

        # The seam now embeds the mid8 (and strips the stale NNN- prefix); the old
        # bare f-string guess that the routing replaces did neither.
        assert teardown_path != old_bare_guess
        assert teardown_path.name == "foo-bar-01KV6510-lane-a"
