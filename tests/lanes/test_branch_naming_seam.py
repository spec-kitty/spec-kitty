"""Canonical seam tests for ``lanes.branch_naming`` (WP01, mission 01KV6510).

This module is the binding byte-identical oracle for the slug↔mid8↔name grammar.
It carries:

* a SHARED golden-value table fixture (``GOLDEN_ROWS``) that downstream routing
  WPs (WP03/04/05/06) import to assert no on-disk churn (NFR-003 / FR-005);
* failing-first regressions for #1949 (idempotent compose on the
  ``mission_id=None`` embedded-slug branch) and #1918 (authoritative resolve must
  decline a coincidental 8-char tail);
* the round-trip / fixpoint property test keyed on ``(slug, mission_id)``
  (NFR-003).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import pytest

from specify_cli.lanes import branch_naming as bn

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# ULID whose first 8 chars form this mission's own mid8.
MISSION_ID = "01KV6510ATWWFXS3K5ZJ9E5008"
MID8 = "01KV6510"
LANE = "lane-a"


# ---------------------------------------------------------------------------
# Shared golden-value table — the binding byte-identical oracle (FR-005).
# Downstream routing WPs import GOLDEN_ROWS to prove zero on-disk churn.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GoldenRow:
    """One canonical ``(slug, mission_id, lane_id)`` → expected name set."""

    label: str
    mission_slug: str
    mission_id: str | None
    lane_id: str
    mission_branch: str
    lane_branch: str
    worktree_dir: str
    mission_dir: str
    coord_dir: str
    coord_branch: str
    # The VERBATIM coordination mission-dir name (no NNN- strip), as the
    # historical coordination read/transaction composers produced it. Differs
    # from ``mission_dir`` (canonical, NNN-stripped) only for an NNN-prefixed
    # slug (#1589). Empty when the row has no real mid8 to derive a coord name.
    coord_mission_dir: str


GOLDEN_ROWS: tuple[GoldenRow, ...] = (
    # Legacy NNN- slug, no mission_id: the worktree dir carries NO mid8 — it must
    # remain byte-identical to today's allocator ``f"{slug}-{lane}"``.
    GoldenRow(
        label="legacy-NNN-no-mission-id",
        mission_slug="057-foo",
        mission_id=None,
        lane_id=LANE,
        mission_branch="kitty/mission-057-foo",
        lane_branch="kitty/mission-057-foo-lane-a",
        worktree_dir="057-foo-lane-a",
        # mission_dir / coord derivations require a real mid8; legacy rows have
        # none, so they are exercised only via the embedded row below.
        mission_dir="",
        coord_dir="",
        coord_branch="",
        coord_mission_dir="",
    ),
    # Embedded slug already carrying its mid8, mission_id present: the canonical
    # mid8-era forms. Compose must be idempotent (no double-append).
    GoldenRow(
        label="embedded-mid8-with-mission-id",
        mission_slug="foo-01KV6510",
        mission_id=MISSION_ID,
        lane_id=LANE,
        mission_branch="kitty/mission-foo-01KV6510",
        lane_branch="kitty/mission-foo-01KV6510-lane-a",
        worktree_dir="foo-01KV6510-lane-a",
        mission_dir="foo-01KV6510",
        coord_dir="foo-01KV6510-coord",
        coord_branch="kitty/mission-foo-01KV6510",
        # No NNN- prefix → verbatim == canonical.
        coord_mission_dir="foo-01KV6510",
    ),
    # #1589 regression row: a legacy NNN- slug WITH a separately-supplied mid8 —
    # exactly the live coordination read/transaction input (meta.json carries the
    # NNN- slug verbatim + a distinct mid8). The coordination composers must
    # reconstruct the EXISTING on-disk name VERBATIM (NO NNN- strip), while the
    # CANONICAL mission_branch_name / mission_dir_name (WP02 / #1978 merge path)
    # MUST keep stripping the NNN-. This row locks both grammars at once.
    GoldenRow(
        label="legacy-NNN-with-mid8-1589",
        mission_slug="060-test",
        mission_id="01COORD0ATWWFXS3K5ZJ9E5008",
        lane_id=LANE,
        # Canonical branch/lane (NNN- stripped) — the merge-path grammar.
        mission_branch="kitty/mission-test-01COORD0",
        lane_branch="kitty/mission-test-01COORD0-lane-a",
        worktree_dir="test-01COORD0-lane-a",
        # Canonical mission dir (NNN- stripped).
        mission_dir="test-01COORD0",
        # VERBATIM coordination dir/branch (NNN- preserved) — the on-disk names
        # the read/transaction path must reconstruct.
        coord_dir="060-test-01COORD0-coord",
        coord_branch="kitty/mission-060-test-01COORD0",
        coord_mission_dir="060-test-01COORD0",
    ),
)

# The mid8 for the #1589 NNN- regression row (first 8 of its mission_id).
_NNN_ROW_MID8 = "01COORD0"


def _legacy_row() -> GoldenRow:
    return next(r for r in GOLDEN_ROWS if r.mission_id is None)


def _embedded_row() -> GoldenRow:
    return next(r for r in GOLDEN_ROWS if r.mission_id is not None)


# ---------------------------------------------------------------------------
# Golden-table assertions — byte-identical compose in BOTH modes.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=lambda r: r.label)
def test_golden_table_branch_and_lane(row: GoldenRow) -> None:
    assert bn.mission_branch_name(row.mission_slug, mission_id=row.mission_id) == row.mission_branch
    assert (
        bn.lane_branch_name(row.mission_slug, row.lane_id, mission_id=row.mission_id)
        == row.lane_branch
    )


@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=lambda r: r.label)
def test_golden_table_worktree_dir(row: GoldenRow) -> None:
    """worktree_dir_name reproduces today's on-disk grammar EXACTLY in both modes."""
    assert (
        bn.worktree_dir_name(row.mission_slug, mission_id=row.mission_id, lane_id=row.lane_id)
        == row.worktree_dir
    )


def test_golden_table_mission_and_coord_derivations() -> None:
    """mission_dir / coord_dir / coord_branch match the workspace + _create grammar."""
    row = _embedded_row()
    assert bn.mission_dir_name(row.mission_slug, mid8=MID8) == row.mission_dir
    assert bn.coord_dir_name(row.mission_slug, mid8=MID8) == row.coord_dir
    assert bn.coord_branch_name(row.mission_slug, mission_id=row.mission_id) == row.coord_branch
    assert bn.coord_mission_dir_name(row.mission_slug, mid8=MID8) == row.coord_mission_dir


def _nnn_row() -> GoldenRow:
    return next(r for r in GOLDEN_ROWS if r.label == "legacy-NNN-with-mid8-1589")


def test_1589_coordination_composers_verbatim_no_nnn_strip() -> None:
    """#1589 LOCK: the coordination grammar reconstructs an NNN- name VERBATIM.

    The live coordination read/transaction path reads ``meta.json.mission_slug``
    verbatim (here ``060-test``) with a separately-supplied ``mid8``. The
    coordination composers MUST reproduce the EXISTING on-disk names byte-for-byte
    (NO NNN- strip), per the pre-WP06 algorithm
    ``slug if slug.endswith(f"-{mid8}") else f"{slug}-{mid8}"``. A canonical
    (stripping) compose here drifts to a name that was never created on disk,
    orphaning the coord worktree and breaking status reads.
    """
    row = _nnn_row()
    assert bn.coord_mission_dir_name(row.mission_slug, mid8=_NNN_ROW_MID8) == row.coord_mission_dir
    assert bn.coord_dir_name(row.mission_slug, mid8=_NNN_ROW_MID8) == row.coord_dir
    assert bn.coord_reconstruct_branch(row.mission_slug, mid8=_NNN_ROW_MID8) == row.coord_branch
    # Pre-WP06 algorithm, recomputed inline as the byte-identical oracle.
    suffix = f"-{_NNN_ROW_MID8}"
    expected_dir = (
        row.mission_slug
        if row.mission_slug.endswith(suffix)
        else f"{row.mission_slug}{suffix}"
    )
    assert bn.coord_mission_dir_name(row.mission_slug, mid8=_NNN_ROW_MID8) == expected_dir


def test_1589_canonical_branch_grammar_still_strips_nnn() -> None:
    """#1589 LOCK: the CANONICAL merge-path grammar (WP02 / #1978) still strips NNN-.

    The fix must NOT relax the canonical branch/dir grammar — ``mission_branch_name``
    / ``mission_branch_name_required`` / ``mission_dir_name`` keep stripping the
    NNN- prefix (post-083 canonical grammar that WP02's #1978 merge fix depends on).
    Only the dedicated coordination *reconstruct* primitives are verbatim.
    """
    row = _nnn_row()
    # Canonical branch grammar: NNN- stripped (WP02 / #1978 merge path).
    assert bn.mission_branch_name(row.mission_slug, mission_id=row.mission_id) == row.mission_branch
    assert (
        bn.mission_branch_name_required(row.mission_slug, row.mission_id) == row.mission_branch
    )
    # Canonical mission-dir grammar: NNN- stripped.
    assert bn.mission_dir_name(row.mission_slug, mid8=_NNN_ROW_MID8) == row.mission_dir
    # The two grammars genuinely DIFFER for an NNN- slug — that is the contract.
    assert row.mission_dir != row.coord_mission_dir
    assert row.mission_branch != row.coord_branch


def test_worktree_dir_legacy_matches_allocator_fstring() -> None:
    """The legacy worktree dir is byte-identical to ``f"{slug}-{lane}"`` (no mid8)."""
    row = _legacy_row()
    assert (
        bn.worktree_dir_name(row.mission_slug, mission_id=None, lane_id=row.lane_id)
        == f"{row.mission_slug}-{row.lane_id}"
    )


def test_worktree_path_emits_under_worktrees(tmp_path) -> None:
    row = _embedded_row()
    path = bn.worktree_path(
        tmp_path, row.mission_slug, mission_id=row.mission_id, lane_id=row.lane_id
    )
    assert path == tmp_path / ".worktrees" / row.worktree_dir


def test_coord_dir_matches_workspace_compose() -> None:
    """coord_dir_name must equal the ``_compose_mission_dir(...)-coord`` grammar."""
    row = _embedded_row()
    # _compose_mission_dir dedups when the slug already embeds the mid8.
    assert bn.coord_dir_name("foo", mid8=MID8) == "foo-01KV6510-coord"
    assert bn.coord_dir_name(row.mission_slug, mid8=MID8) == "foo-01KV6510-coord"


# ---------------------------------------------------------------------------
# #1949 regression: idempotent compose on the mission_id=None embedded branch.
# RED-FIRST: before the fix, mission_branch_name("foo-01KV6510") returns the
# bare embedded slug unchanged (it is a valid embedded form) — but a slug that
# embeds a mid8 with NO mission_id MUST still compose a *resolvable* name. The
# genuine residual is the mission_id=None branch doing NO dedup at all: passing
# an already-embedded slug WITH mission_id used to be safe; passing it with
# mission_id=None must not silently differ from the resolvable embedded form.
# ---------------------------------------------------------------------------


def test_1949_compose_idempotent_with_mission_id_LOCK() -> None:
    """Regression-LOCK (green by design): the mission_id path never double-appends."""
    # Bare slug + mission_id → single mid8.
    assert bn.mission_branch_name("foo", mission_id=MISSION_ID) == "kitty/mission-foo-01KV6510"
    # Already-embedded slug + mission_id → still single mid8 (idempotent).
    assert (
        bn.mission_branch_name("foo-01KV6510", mission_id=MISSION_ID)
        == "kitty/mission-foo-01KV6510"
    )
    assert (
        bn.lane_branch_name("foo-01KV6510", LANE, mission_id=MISSION_ID)
        == "kitty/mission-foo-01KV6510-lane-a"
    )


def test_1949_compose_idempotent_mission_id_none_embedded() -> None:
    """RED-FIRST #1949: mission_id=None embedded slug must compose the resolvable form.

    The genuine residual is a slug carrying BOTH a stale ``NNN-`` prefix AND an
    embedded mid8 (``057-foo-01KV6510``). The mission_id path strips the NNN and
    keeps the single mid8 (``kitty/mission-foo-01KV6510``), but the old
    ``mission_id=None`` branch did NO dedup → it produced the divergent,
    never-created ``kitty/mission-057-foo-01KV6510``. Compose must be a fixpoint on
    the embedded form regardless of whether ``mission_id`` is supplied.
    """
    with_id = bn.mission_branch_name("057-foo-01KV6510", mission_id=MISSION_ID)
    without_id = bn.mission_branch_name("057-foo-01KV6510", mission_id=None)
    assert without_id == with_id == "kitty/mission-foo-01KV6510"

    lane_with_id = bn.lane_branch_name("057-foo-01KV6510", LANE, mission_id=MISSION_ID)
    lane_without_id = bn.lane_branch_name("057-foo-01KV6510", LANE, mission_id=None)
    assert lane_without_id == lane_with_id == "kitty/mission-foo-01KV6510-lane-a"


def test_1949_legacy_NNN_without_mid8_keeps_prefix() -> None:
    """A pure legacy ``NNN-`` slug (no embedded mid8) must KEEP its prefix.

    The mission_id=None dedup must only strip NNN when an embedded mid8 tail is
    present — a genuine pre-083 legacy slug has no mid8 and its branch is
    ``kitty/mission-057-foo`` (NNN preserved).
    """
    assert bn.mission_branch_name("057-foo", mission_id=None) == "kitty/mission-057-foo"
    assert bn.lane_branch_name("057-foo", LANE, mission_id=None) == "kitty/mission-057-foo-lane-a"


# ---------------------------------------------------------------------------
# #1918 regression: authoritative resolve_mid8 declines a coincidental tail.
# ---------------------------------------------------------------------------


def test_1918_resolve_mid8_authoritative_from_mission_id() -> None:
    """resolve_mid8 derives the mid8 from the declared mission_id (primary)."""
    assert bn.resolve_mid8("foo", mission_id=MISSION_ID) == MID8
    # Even when the slug embeds a (matching) tail, mission_id is authoritative.
    assert bn.resolve_mid8("foo-01KV6510", mission_id=MISSION_ID) == MID8


def test_1918_resolve_mid8_declines_coincidental_tail() -> None:
    """RED-FIRST #1918: a coincidental 8-char tail with NO mission_id must DECLINE.

    ``resolve_mid8`` is the correctness path: without a mission_id to confirm
    against, it must NOT assume an arbitrary 8-Crockford tail is a real mid8.
    """
    assert bn.resolve_mid8("feature-12345678", mission_id=None) == ""
    assert bn.resolve_mid8("my-feature-01KT3YBD", mission_id=None) == ""


def test_1918_resolve_mid8_accepts_provably_matching_tail() -> None:
    """When mission_id is absent but the embedded tail provably matches, accept it.

    Here the caller passes mission_id and the embedded tail agrees — the resolve
    path returns the confirmed mid8 rather than declining.
    """
    assert bn.resolve_mid8("foo-01KV6510", mission_id="01KV6510ATWWFXS3K5ZJ9E5008") == MID8
    # Mismatched embedded tail vs mission_id → mission_id wins (authoritative).
    assert bn.resolve_mid8("foo-DEADBEE1", mission_id=MISSION_ID) == MID8


# ---------------------------------------------------------------------------
# Do-not-regress the heuristic detector + its two final-fallback consumers.
# A genuine embedded-mid8 slug must STILL resolve through resolve_transaction_mid8.
# ---------------------------------------------------------------------------


def test_mid8_from_slug_remains_heuristic_detector() -> None:
    """mid8_from_slug stays a best-effort detector (keeps str return)."""
    # Genuine embedded tail → extracted (final-fallback consumers rely on this).
    assert bn.mid8_from_slug("foo-01KV6510") == "01KV6510"
    assert bn.mid8_from_slug("feature-12345678") == "12345678"
    # No tail → empty.
    assert bn.mid8_from_slug("legacy-feature") == ""
    assert bn.mid8_from_slug("012-old-style-mission") == ""


def test_resolve_transaction_mid8_still_resolves_embedded_tail() -> None:
    """The embedded-mid8 final fallback must NOT newly fail-close (FR-004)."""
    # No declared mid8/mission_id, but the slug carries a genuine mid8 tail.
    assert (
        bn.resolve_transaction_mid8(
            "foo-01KV6510", mission_id=None, mid8=None, coordination_branch="kitty/mission-foo-01KV6510"
        )
        == "01KV6510"
    )
    # Declared mid8 still wins.
    assert (
        bn.resolve_transaction_mid8("foo-01KV6510", mission_id=None, mid8="DEADBEE1")
        == "DEADBEE1"
    )


# ---------------------------------------------------------------------------
# Canonical-first / legacy-failover resolve path with one-shot deprecation warning.
# ---------------------------------------------------------------------------


def test_resolve_branch_prefers_canonical_no_warning() -> None:
    """Canonical (slug, mission_id) path resolves WITHOUT a deprecation warning."""
    bn.reset_legacy_failover_warning()
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning becomes an error
        assert (
            bn.resolve_branch_name("foo-01KV6510", mission_id=MISSION_ID)
            == "kitty/mission-foo-01KV6510"
        )


def test_resolve_branch_legacy_emits_one_shot_warning(monkeypatch) -> None:
    """Legacy NNN- failover emits EXACTLY ONE deprecation warning per process."""
    monkeypatch.delenv(bn.LEGACY_FAILOVER_SUPPRESS_ENV, raising=False)
    bn.reset_legacy_failover_warning()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        first = bn.resolve_branch_name("057-foo", mission_id=None)
        second = bn.resolve_branch_name("058-bar", mission_id=None)
    assert first == "kitty/mission-057-foo"
    assert second == "kitty/mission-058-bar"
    dep = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(dep) == 1, (  # (one-shot-firing invariant)
        f"expected exactly one one-shot warning, got {len(dep)}"
    )


def test_resolve_branch_legacy_warning_suppressed_by_env(monkeypatch) -> None:
    monkeypatch.setenv(bn.LEGACY_FAILOVER_SUPPRESS_ENV, "1")
    bn.reset_legacy_failover_warning()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        bn.resolve_branch_name("057-foo", mission_id=None)
    dep = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert dep == []


def test_resolve_branch_modern_unresolvable_fails_closed() -> None:
    """A modern slug with no mission_id, no NNN-, no mid8 tail → fail closed."""
    with pytest.raises(bn.BranchIdentityUnresolved):
        bn.resolve_branch_name("modern-slug", mission_id=None)


# ---------------------------------------------------------------------------
# Round-trip / fixpoint property test keyed on (slug, mission_id) (NFR-003).
# ---------------------------------------------------------------------------

ROUND_TRIP_CASES = [
    # (slug, mission_id, expected_parsed_slug, expected_mid8_token)
    ("foo-01KV6510", MISSION_ID, "foo", MID8),  # embedded == mid8(mission_id)
    ("foo", MISSION_ID, "foo", MID8),  # bare + mission_id → composed
    ("057-foo", None, "057-foo", None),  # legacy NNN-
]


@pytest.mark.parametrize("slug,mission_id,exp_slug,exp_mid8", ROUND_TRIP_CASES)
def test_compose_parse_round_trip(
    slug: str, mission_id: str | None, exp_slug: str, exp_mid8: str | None
) -> None:
    branch = bn.mission_branch_name(slug, mission_id=mission_id)
    parsed = bn.parse_mission_slug_from_branch(branch)
    assert parsed is not None
    assert parsed.slug == exp_slug
    assert parsed.mid8_token == exp_mid8


@pytest.mark.parametrize("slug,mission_id", [("foo-01KV6510", MISSION_ID), ("057-foo", None)])
def test_compose_is_fixpoint(slug: str, mission_id: str | None) -> None:
    """Composing a slug that already carries its identity is a fixpoint."""
    once = bn.mission_branch_name(slug, mission_id=mission_id)
    # Re-derive the embedded slug from the composed branch and recompose.
    parsed = bn.parse_mission_slug_from_branch(once)
    assert parsed is not None
    if parsed.mid8_token is not None:
        re_slug = f"{parsed.slug}-{parsed.mid8_token}"
        twice = bn.mission_branch_name(re_slug, mission_id=mission_id)
    else:
        twice = bn.mission_branch_name(parsed.slug, mission_id=mission_id)
    assert once == twice


def test_compose_mismatched_embedded_tail_uses_mission_id() -> None:
    """embedded-tail ≠ mid8(mission_id): mission_id is authoritative (no double-strip)."""
    # Slug embeds DEADBEE1 but mission_id says 01KV6510 → keep slug body, append mid8.
    branch = bn.mission_branch_name("foo-DEADBEE1", mission_id=MISSION_ID)
    assert branch == "kitty/mission-foo-DEADBEE1-01KV6510"
