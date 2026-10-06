"""T052 -- ``DecisionGitLog`` lands at ``write_dir(DECISION_LOG)`` (coord-artifact-single-home-01M3V4BE WP09).

Covers:
- A pre-fix EMPTY coordination Mission is seeded and the resulting
  ``decisions.events.jsonl`` lands at ``write_dir(DECISION_LOG).path /
  "decisions.events.jsonl"`` in the coordination worktree.
- Dir-name agreement: ``DecisionGitLog``'s file dir, ``write_dir(DECISION_LOG).path``
  and the coordination transaction's own ``coord_mission_dir_name`` composition
  all agree for a canonical (mid8-embedding) slug, AND for a bare (non-mid8-
  embedding) slug -- ``coord_mission_dir_name`` deliberately preserves a
  pre-083 ``NNN-``-prefixed slug VERBATIM (``"060-test"`` -> ``"060-test-<mid8>"``,
  never stripped), which is exactly the shape a bare-slug caller exercises:
  ``coord_mission_dir_name(bare_slug, mid8=mid8)`` always APPENDS the suffix
  rather than assuming it is already present. Review cycle 1 (B3): the
  legacy second stream the deleted ``DecisionGitLog`` composer would have
  written at ``kitty-specs/<bare-slug>/decisions.events.jsonl`` (no mid8
  suffix) for such a caller is NOT folded here -- that is WP17's allocation
  (its own doctor fork-detection work), recorded in the design-decisions
  tracer. This file only proves the NEW design (``DecisionGitLog``,
  ``write_dir``, the transaction) is internally consistent for both slug
  shapes, matching production reality: ``decision.py``'s
  ``_resolve_repo_root_and_slug`` / ``runtime_bridge``'s own identity
  resolution both canonicalize a handle before most callers reach this
  function, but nothing enforces that universally, so this pins the
  bare-slug shape too rather than only asserting it for free.
- Review cycle 2 (same-family B1-residual fix, Decision ``plan.design.
  undeclared-coord-branch``): a genuinely BARE mission_slug (no mid8 tail at
  all, not just verbatim-preserved) driven through
  ``_wrap_with_decision_git_log`` now lands on the coordination surface too
  (``test_bare_slug_coord_routed_mission_lands_on_coordination_surface``) --
  the previously-separate defect in ``read_primary_meta``'s canonicalization
  fallback (identity forms only, missing the bare-human-slug fold
  ``_canonicalize_primary_read_handle`` already applies for the read-dir
  leg) is fixed at its source
  (``specify_cli.missions._read_path_resolver.read_primary_meta``). A
  defense-in-depth test
  (``test_wrap_refuses_when_write_dir_resolves_primary_under_coord_topology``)
  additionally pins that ``_wrap_with_decision_git_log``'s non-owned arm
  never wraps a ``DecisionGitLog`` on a PRIMARY-surfaced ``write_dir`` answer
  under a coordination-routed topology, regardless of how that mismatch
  might arise.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock

import pytest

from mission_runtime import MissionArtifactKind, MissionTopology, OwnedCheckout, TopologySurface, placement_seam
from runtime.next._internal_runtime.events import RuntimeEventEmitter
from runtime.next.runtime_bridge import DecisionGitLogUnavailable
from runtime.next.runtime_bridge_decision_log import _wrap_with_decision_git_log
from specify_cli.events.decision_log import DecisionGitLog
from specify_cli.lanes.branch_naming import coord_mission_dir_name
from tests._factories.coord_mission import COORD_TOPOLOGIES, make_prefix_coord_mission
from runtime.next import runtime_bridge_decision_log as decision_log

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_decision_git_log_lands_at_write_dir_decision_log_for_pre_fix_empty(tmp_path: Path) -> None:
    """A pre-fix EMPTY coordination Mission's ``DecisionGitLog`` stream lands
    at ``write_dir(DECISION_LOG).path`` (seeded), never a second, independent
    composition."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    inner = MagicMock(spec=RuntimeEventEmitter)

    wrapped = _wrap_with_decision_git_log(inner, coord.mission_dir_name, coord.repo_root)

    assert isinstance(wrapped, DecisionGitLog), "coord-routing must wrap, not fall back to the plain emitter"
    location = placement_seam(coord.repo_root, coord.mission_dir_name).write_dir(MissionArtifactKind.DECISION_LOG)
    expected = location.path / "decisions.events.jsonl"
    assert wrapped._decisions_file == expected
    # The coordination Mission dir was materialized AND seeded by the above
    # resolution -- never left pending.
    assert location.path.exists()


@pytest.mark.parametrize("worktree", ["absent", "empty"])
def test_decision_git_log_dir_name_agrees_with_transaction_composition(tmp_path: Path, worktree: Literal["absent", "empty"]) -> None:
    """Dir-name agreement (T051 edge case): ``DecisionGitLog``'s file dir,
    ``write_dir(DECISION_LOG).path`` and the coordination transaction's own
    ``coord_mission_dir_name(slug, mid8=mid8)`` composition all agree, for a
    canonical (mid8-embedding) slug, across both reachable pre-write states
    (``absent`` -> UNMATERIALIZED, ``empty`` -> MATERIALIZED-but-EMPTY)."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree=worktree)
    inner = MagicMock(spec=RuntimeEventEmitter)

    wrapped = _wrap_with_decision_git_log(inner, coord.mission_dir_name, coord.repo_root)
    assert isinstance(wrapped, DecisionGitLog)

    location = placement_seam(coord.repo_root, coord.mission_dir_name).write_dir(MissionArtifactKind.DECISION_LOG)
    transaction_dir_name = coord_mission_dir_name(coord.mission_slug, mid8=coord.mid8)

    decision_git_log_dir = wrapped._decisions_file.parent
    write_dir_path = location.path
    transaction_path = coord.coord_worktree_path / "kitty-specs" / transaction_dir_name

    assert decision_git_log_dir == write_dir_path == transaction_path, (
        f"dir-name disagreement: DecisionGitLog={decision_git_log_dir!r} write_dir={write_dir_path!r} transaction={transaction_path!r}"
    )


def test_decision_git_log_dir_name_agrees_for_a_bare_non_mid8_embedding_slug(tmp_path: Path) -> None:
    """Review cycle 1 (B3, P-M4 binding): for a bare (non-mid8-embedding)
    ``mission_slug`` -- the pre-083 ``NNN-``-prefixed legacy shape
    ``coord_mission_dir_name``'s own docstring example describes
    (``"060-test"`` -> ``"060-test-<mid8>"``) -- ``DecisionGitLog``,
    ``write_dir`` and the coordination transaction all agree on the SAME
    canonical (mid8-appended) dir, never the legacy bare-named one the
    deleted ``DecisionGitLog`` composer used to write
    (``kitty-specs/<bare-slug>/...``, no mid8).

    ``_wrap_with_decision_git_log`` is driven with the CANONICAL
    (mid8-embedding) slug here -- the shape production actually reaches it
    with (this WP09's own ``decision.py``/``runtime_bridge`` identity
    resolution both canonicalize a handle before most callers get here).

    (Review cycle 2 update: driving this SAME function with the genuinely
    bare slug used to trip a separate defect in ``read_primary_meta`` (its
    own canonicalization fallback covered only identity forms -- bare
    ``mid8``/ULID/numeric prefix -- never the bare-HUMAN-SLUG fold), fixed in
    cycle 2 and now pinned directly by
    ``test_bare_slug_coord_routed_mission_lands_on_coordination_surface``
    below -- this test keeps pinning the ``coord_mission_dir_name``
    bare-vs-canonical equivalence claim on the CANONICAL-slug call shape.)
    """
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    assert not coord.mission_slug.endswith(coord.mid8), "fixture precondition: mission_slug must be bare (not mid8-embedding)"

    # coord_mission_dir_name itself: bare input -> the SAME canonical dir
    # name the fixture's own (already-canonical) mission_dir_name carries.
    canonical_dir_name = coord_mission_dir_name(coord.mission_slug, mid8=coord.mid8)
    assert canonical_dir_name == coord.mission_dir_name

    inner = MagicMock(spec=RuntimeEventEmitter)
    wrapped = _wrap_with_decision_git_log(inner, coord.mission_dir_name, coord.repo_root)
    assert isinstance(wrapped, DecisionGitLog)

    location = placement_seam(coord.repo_root, coord.mission_dir_name).write_dir(MissionArtifactKind.DECISION_LOG)
    transaction_path = coord.coord_worktree_path / "kitty-specs" / canonical_dir_name

    decision_git_log_dir = wrapped._decisions_file.parent
    assert decision_git_log_dir == location.path == transaction_path, (
        f"bare-slug dir-name disagreement: DecisionGitLog={decision_git_log_dir!r} write_dir={location.path!r} transaction={transaction_path!r}"
    )
    # The legacy (bare, non-mid8) dir name -- what the deleted DecisionGitLog
    # composer would have written for a caller passing the bare slug
    # directly -- is NEVER where the new design lands.
    legacy_bare_dir = coord.coord_worktree_path / "kitty-specs" / coord.mission_slug
    assert decision_git_log_dir != legacy_bare_dir


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_bare_slug_coord_routed_mission_lands_on_coordination_surface(tmp_path: Path, topology: MissionTopology) -> None:
    """Review cycle 2 (same-family B1-residual fix): a genuinely BARE
    ``mission_slug`` (the raw human slug, no mid8 tail at all -- unlike the
    sibling test above, which drives the already-canonical slug) routed
    through ``_wrap_with_decision_git_log`` now lands a ``DecisionGitLog`` on
    the COORDINATION surface, never the primary checkout.

    Before the cycle-2 fix, ``read_primary_meta``'s canonicalization fallback
    covered only identity-form handles (bare ``mid8`` / full ULID / numeric
    prefix) -- never the bare-HUMAN-SLUG fold ``_canonicalize_primary_read_
    handle`` already applies for the read-dir leg -- so a bare-slug caller's
    ``establish_coord_write_location`` read EMPTY meta, lost
    ``coordination_branch``/``topology`` entirely, and silently degraded to
    the PRIMARY write location even though ``_mission_routes_through_
    coordination`` (a DIFFERENT, already-canonicalizing call path) correctly
    classified the SAME Mission as coordination-routed.
    """
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="empty")
    assert not coord.mission_slug.endswith(coord.mid8), "fixture precondition: mission_slug must be bare (not mid8-embedding)"
    inner = MagicMock(spec=RuntimeEventEmitter)

    wrapped = _wrap_with_decision_git_log(inner, coord.mission_slug, coord.repo_root)

    assert isinstance(wrapped, DecisionGitLog), "a bare-slug coord-routed Mission must still get a durable DecisionGitLog"
    decision_git_log_dir = wrapped._decisions_file.parent
    assert str(coord.coord_worktree_path) in str(decision_git_log_dir), f"bare-slug DecisionGitLog landed off the coordination worktree: {decision_git_log_dir!r}"
    legacy_primary_dir = coord.repo_root / "kitty-specs" / coord.mission_dir_name
    assert decision_git_log_dir != legacy_primary_dir, "must never land on the PRIMARY checkout for a coordination-routed topology"


def test_wrap_refuses_when_write_dir_resolves_primary_under_coord_topology(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Defense in depth (review cycle 2, "same family" as B1-residual): when
    ``_mission_routes_through_coordination`` says the STORED topology routes
    through coordination but ``write_dir(DECISION_LOG)`` nonetheless hands
    back a PRIMARY-surfaced location -- however that mismatch might arise --
    ``_wrap_with_decision_git_log``'s non-owned arm refuses with
    ``DecisionGitLogUnavailable`` rather than silently wrapping a
    ``DecisionGitLog`` on the wrong surface.
    """
    import mission_runtime
    from mission_runtime import Establishment, WriteLocation
    from mission_runtime import placement_seam as _real_placement_seam

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    monkeypatch.setattr(decision_log, "_mission_routes_through_coordination", lambda *_a, **_k: True)
    fake_location = WriteLocation(
        path=coord.repo_root / "kitty-specs" / coord.mission_dir_name,
        surface_root=coord.repo_root,
        surface=TopologySurface.PRIMARY,
        coord_state_before=None,
        establishment=Establishment.NONE,
    )

    class _FakeSeam:
        """Overrides ONLY write_dir; every other attribute (notably read_dir,
        which _resolve_coordination_branch's identity resolution calls BEFORE
        write_dir is ever reached) delegates to the REAL seam -- an
        AttributeError here would be swallowed by the generic ``except
        Exception`` below and silently produce a DIFFERENT, GENERIC
        DecisionGitLogUnavailable, giving this test a false-positive pass
        without ever exercising the surface check under test.

        Typed to match ``placement_seam``'s own signature exactly (review
        cycle 3 nit) rather than ``*args: object, **kwargs: object`` + a
        suppression -- the real call site passes ``(repo_root, mission_slug)``
        positionally plus the ``owned=`` keyword (``None`` for a non-owned
        caller; WP20 unified the owned and non-owned arms onto one
        ``write_dir`` call), so this is a precise, not a widened, signature.
        """

        def __init__(self, repo_root: Path, mission_slug: str, *, owned: OwnedCheckout | None = None) -> None:
            self._real = _real_placement_seam(repo_root, mission_slug, owned=owned)

        def write_dir(self, _kind: object) -> WriteLocation:
            return fake_location

        def __getattr__(self, name: str) -> object:
            return getattr(self._real, name)

    monkeypatch.setattr(mission_runtime, "placement_seam", _FakeSeam)
    inner = MagicMock(spec=RuntimeEventEmitter)

    with pytest.raises(DecisionGitLogUnavailable, match="resolved a PRIMARY surface"):
        _wrap_with_decision_git_log(inner, coord.mission_dir_name, coord.repo_root)


def test_wrap_chains_coord_branch_undeclared_and_absent_code_through_the_refusal(tmp_path: Path) -> None:
    """Review cycle 3 (C3-N1): a non-owned ``_wrap_with_decision_git_log``
    call on a coordination-routed Mission whose ``coordination_branch`` is
    undeclared AND whose deterministically-derived branch does not exist in
    git either reaches ``write_dir``'s ``CoordBranchUndeclaredAndAbsent``
    refusal. The bridge folds it (N2, cycle 1) into ``DecisionGitLogUnavailable``
    -- this pins that the chained typed code survives the fold, matching
    ``(COORD_BRANCH_UNDECLARED_AND_ABSENT)`` verbatim in the message so an
    operator reading the fail-closed error still sees it.
    """
    import json

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, branch_deleted=True)
    meta_path = coord.root_mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text())
    assert meta.get("topology"), "fixture precondition: topology must survive the strip"
    del meta["coordination_branch"]
    meta_path.write_text(json.dumps(meta))
    inner = MagicMock(spec=RuntimeEventEmitter)

    with pytest.raises(DecisionGitLogUnavailable, match=r"\(COORD_BRANCH_UNDECLARED_AND_ABSENT\)"):
        _wrap_with_decision_git_log(inner, coord.mission_dir_name, coord.repo_root)
