"""WP01 (mission 01KV7SFD): ``resolve_mid8`` is the sole public mid8 door.

These tests pin the SSOT-entrypoint contract introduced when ``mid8`` was demoted
to the private ``_mid8`` and ``resolve_mid8`` became the only public mid8 surface:

* ``resolve_mid8`` declines (``""``) without a declared ``mission_id`` and resolves
  to ``mission_id[:8]`` with one, with the declared identity governing over a
  divergent slug tail (NFR-003);
* the mission-id-only equivalence ``resolve_mid8("", mission_id=full) == full[:8]``
  that WP04's mission-id-only callers rely on;
* ``_mid8`` is private (not importable as a public name) and still raises on a
  short/``None`` argument (internal primitive contract);
* the one-shot legacy-failover ``DeprecationWarning`` fires exactly once and
  ``reset_legacy_failover_warning`` re-arms it;
* the composed branch/worktree names are **byte-identical** to the pre-demotion
  output for representative slugs — the RHS golden values are hard-coded literals
  captured from HEAD before the rename (anti-gaming: never ``f(x) == f(x)``).
"""

from __future__ import annotations

import warnings
from typing import Any

import pytest

from specify_cli.lanes import branch_naming
from specify_cli.lanes.branch_naming import (
    InvalidMissionIdentity,
    _mid8,
    code_lane_branch_name,
    mission_branch_name,
    reset_legacy_failover_warning,
    resolve_branch_name,
    resolve_mid8,
    resolve_transaction_mid8,
    worktree_dir_name,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# A full 26-char ULID and a *different* full ULID, used to prove the declared
# identity governs over a divergent embedded slug tail.
_FULL_ID = "01KV6510ABCDEFGHJKMNPQRSTV"
_FULL_ID_MID8 = "01KV6510"
_OTHER_ID = "01KNXQS9ATWWFXS3K5ZJ9E5008"
_OTHER_ID_MID8 = "01KNXQS9"


# ---------------------------------------------------------------------------
# T002 — resolve_mid8 is the sole PUBLIC mid8 door; _mid8 is private.
# ---------------------------------------------------------------------------


def test_public_mid8_symbol_is_gone() -> None:
    """The bare ``mid8`` slicer is no longer a public symbol of the module."""
    assert not hasattr(branch_naming, "mid8")
    assert "mid8" not in branch_naming.__all__


def test_resolve_mid8_is_public() -> None:
    """``resolve_mid8`` (and the transaction resolver) remain the public door."""
    assert "resolve_mid8" in branch_naming.__all__
    assert "resolve_transaction_mid8" in branch_naming.__all__
    assert callable(resolve_mid8)
    assert callable(resolve_transaction_mid8)


def test__mid8_not_exported_but_still_private_primitive() -> None:
    """``_mid8`` is private: not in ``__all__`` and underscore-prefixed."""
    assert "_mid8" not in branch_naming.__all__
    # The primitive still exists as a private module attribute for the internal
    # branch/worktree composers.
    assert hasattr(branch_naming, "_mid8")


# ---------------------------------------------------------------------------
# T002 / T004 — resolve_mid8 contracts (decline, mission-id, divergent tail).
# ---------------------------------------------------------------------------


def test_resolve_mid8_declines_without_mission_id() -> None:
    """No declared ``mission_id`` ⇒ decline a (possibly coincidental) tail (#1918)."""
    assert resolve_mid8("foo-01KV6510", mission_id=None) == ""
    assert resolve_mid8("plain-slug", mission_id=None) == ""
    assert resolve_mid8("", mission_id=None) == ""


def test_resolve_mid8_returns_mission_id_prefix_when_declared() -> None:
    """A declared ``mission_id`` (>= 8 chars) resolves to its first 8 chars."""
    assert resolve_mid8("plain-slug", mission_id=_FULL_ID) == _FULL_ID_MID8
    assert resolve_mid8("foo-01KV6510", mission_id=_FULL_ID) == _FULL_ID_MID8


def test_resolve_mid8_mission_id_only_equivalence() -> None:
    """The mission-id-only equivalence WP04 callers rely on: ``""`` slug ⇒ id[:8]."""
    assert resolve_mid8("", mission_id=_FULL_ID) == _FULL_ID_MID8
    # Stated as the equivalence the prompt mandates (no f(x)==f(x) tautology).
    assert resolve_mid8("", mission_id=_FULL_ID) == _FULL_ID[:8]


def test_resolve_mid8_declared_identity_governs_over_divergent_tail() -> None:
    """A slug carrying a *stale/foreign* mid8 tail never wins over the declared id."""
    # slug embeds 01KV6510 but the declared identity is _OTHER_ID → declared wins.
    assert resolve_mid8("foo-01KV6510", mission_id=_OTHER_ID) == _OTHER_ID_MID8


# ---------------------------------------------------------------------------
# T001 / T004 — _mid8 internal primitive raises on short/None.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "short", "01KV651"])  # 0 / 5 / 7 chars
def test__mid8_raises_on_short(bad: str) -> None:
    """``_mid8`` raises the typed ``InvalidMissionIdentity`` on a
    shorter-than-8-char argument (#5108 residual: raised at the source so
    every caller gets the same typed refusal, never a bare ``ValueError``)."""
    with pytest.raises(InvalidMissionIdentity):
        _mid8(bad)


def test__mid8_raises_on_none() -> None:
    """``_mid8(None)`` is a programming error: ``len(None)`` raises ``TypeError``."""
    # Passing ``None`` is a deliberate type violation; route it through an
    # ``Any``-typed local so the assertion stays honest without an inline
    # suppression (the charter discourages unnecessary ``# type: ignore``).
    bad_arg: Any = None
    with pytest.raises(TypeError):
        _mid8(bad_arg)


def test__mid8_slices_first_eight() -> None:
    """``_mid8`` returns the first 8 chars of a full ULID (golden literal)."""
    assert _mid8(_FULL_ID) == "01KV6510"
    assert _mid8(_OTHER_ID) == "01KNXQS9"


# ---------------------------------------------------------------------------
# T003 — failover machinery: one-shot warning + reset seam intact.
# ---------------------------------------------------------------------------


def test_legacy_failover_warning_fires_once_then_reset_rearms() -> None:
    """The legacy-failover ``DeprecationWarning`` is one-shot; reset re-arms it."""
    reset_legacy_failover_warning()
    with warnings.catch_warnings(record=True) as first:
        warnings.simplefilter("always")
        resolve_branch_name("057-legacy-mission", mission_id=None)
        resolve_branch_name("057-legacy-mission", mission_id=None)
    dep = [w for w in first if issubclass(w.category, DeprecationWarning)]
    assert len(dep) == 1, "legacy-failover warning must fire exactly once per process"

    # Re-arm and confirm it fires again after the reset seam.
    reset_legacy_failover_warning()
    with warnings.catch_warnings(record=True) as second:
        warnings.simplefilter("always")
        resolve_branch_name("057-legacy-mission", mission_id=None)
    dep2 = [w for w in second if issubclass(w.category, DeprecationWarning)]
    assert len(dep2) == 1, "reset_legacy_failover_warning must re-arm the one-shot"


def test_reset_seam_is_callable_and_idempotent() -> None:
    """``reset_legacy_failover_warning`` is the public test seam and is idempotent."""
    reset_legacy_failover_warning()
    reset_legacy_failover_warning()  # second call must not raise


# ---------------------------------------------------------------------------
# T004 — byte-parity of composed names (golden literals captured from HEAD).
# ---------------------------------------------------------------------------

# (slug, mission_id, expected_mission_branch)
# Golden RHS values were captured from HEAD before the mid8→_mid8 rename.
# ``mission_branch_name`` still takes ``mission_id`` (it names Mission
# branches, not lanes) and its column stays byte-identical (NFR-001).
_PARITY_CASES = [
    (
        "mission-id-canonical-identity-migration",
        _OTHER_ID,
        "kitty/mission-mission-id-canonical-identity-migration-01KNXQS9",
    ),
    (
        "083-my-feature",
        _OTHER_ID,
        "kitty/mission-my-feature-01KNXQS9",
    ),
    (
        "foo-01KV6510",
        _FULL_ID,
        "kitty/mission-foo-01KV6510",
    ),
    (
        "057-my-feature",
        None,
        "kitty/mission-057-my-feature",
    ),
    (
        "plain-slug",
        _FULL_ID,
        "kitty/mission-plain-slug-01KV6510",
    ),
]


@pytest.mark.parametrize(
    ("slug", "mission_id", "mission_branch"),
    _PARITY_CASES,
)
def test_mission_branch_name_byte_identical_to_head(
    slug: str,
    mission_id: str | None,
    mission_branch: str,
) -> None:
    """``mission_branch_name`` is byte-identical to the pre-rename output (unchanged column)."""
    assert mission_branch_name(slug, mission_id=mission_id) == mission_branch


# (slug, expected_lane_branch, expected_worktree_dir)
# ``lane_branch_name``/``worktree_dir_name`` take no ``mission_id`` (FR-002)
# — a lane name is keyed on the creation input (slug + lane id) alone. Rows 1,
# 2 and 5 (identity-injected via ``_OTHER_ID``/``_FULL_ID`` above) are
# RE-PINNED here to the created name (the identity-injected form pinned the
# #5108 defect). Rows 3
# ("foo-01KV6510", the slug already embeds the matching mid8) and 4
# ("057-my-feature", pure legacy) compose the SAME bytes with or without an
# identity, so they are unchanged.
_LANE_WORKTREE_PARITY_CASES = [
    (
        "mission-id-canonical-identity-migration",
        "kitty/mission-mission-id-canonical-identity-migration-lane-a",
        "mission-id-canonical-identity-migration-lane-a",
    ),
    (
        "083-my-feature",
        "kitty/mission-083-my-feature-lane-a",
        "083-my-feature-lane-a",
    ),
    (
        "foo-01KV6510",
        "kitty/mission-foo-01KV6510-lane-a",
        "foo-01KV6510-lane-a",
    ),
    (
        "057-my-feature",
        "kitty/mission-057-my-feature-lane-a",
        "057-my-feature-lane-a",
    ),
    (
        "plain-slug",
        "kitty/mission-plain-slug-lane-a",
        "plain-slug-lane-a",
    ),
]


@pytest.mark.parametrize(
    ("slug", "lane_branch", "worktree_dir"),
    _LANE_WORKTREE_PARITY_CASES,
)
def test_lane_and_worktree_names_are_the_created_form(
    slug: str,
    lane_branch: str,
    worktree_dir: str,
) -> None:
    """Lane/worktree names are keyed on the creation input alone (no mission_id)."""
    assert code_lane_branch_name(slug, "lane-a") == lane_branch
    assert worktree_dir_name(slug, lane_id="lane-a") == worktree_dir


# ---------------------------------------------------------------------------
# T003 — resolve_transaction_mid8 still resolves its declared-source cascade.
# ---------------------------------------------------------------------------


def test_resolve_transaction_mid8_cascade_preserved() -> None:
    """The transaction resolver's declared-source cascade is intact (T003)."""
    # explicit mid8 wins
    assert resolve_transaction_mid8("foo", mission_id=None, mid8="01EXPLCT") == "01EXPLCT"
    # mission_id[:8]
    assert resolve_transaction_mid8("foo", mission_id=_FULL_ID, mid8=None) == _FULL_ID_MID8
    # embedded slug tail
    assert resolve_transaction_mid8("foo-01KV6510", mission_id=None, mid8=None) == "01KV6510"
    # legacy NNN- slug carves out to the bare-slug surface (empty mid8)
    assert resolve_transaction_mid8("057-legacy", mission_id=None, mid8=None) == ""
