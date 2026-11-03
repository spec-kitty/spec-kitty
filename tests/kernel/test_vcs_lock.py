"""``tests/kernel/`` coverage for :mod:`kernel.vcs_lock` -- the unified
VCS-lock comparator (``kernel-tests`` CI job coverage floor, 90%, #3259
landing pass).

No test exercised this module from ``tests/kernel/`` before this file, so the
``kernel-tests`` job's ``--cov=src/kernel`` measurement (scoped to
``tests/kernel/`` only, see ``.github/workflows/ci-quality.yml``) read it as
0% covered. These tests pin :func:`kernel.vcs_lock.is_vcs_lock_only_change`'s
contract directly: the VCS-lock field set, the absent-vs-present-but-``None``
sentinel distinction (C-005), and the ``before=None`` shorthand.
"""

from __future__ import annotations

import pytest

from kernel.vcs_lock import VCS_LOCK_META_FIELDS, is_vcs_lock_only_change, project_metadata_without_vcs_lock

pytestmark = pytest.mark.fast


def test_vcs_lock_field_set_is_exactly_two_fields() -> None:
    """Pin the canonical field set -- a change here is a deliberate contract
    change, not an incidental one (module docstring, NFR-002)."""
    assert frozenset({"vcs", "vcs_locked_at"}) == VCS_LOCK_META_FIELDS


def test_identical_mappings_are_vcs_lock_only() -> None:
    """No differing keys at all -- the empty diff is trivially a subset of
    the lock fields (docstring: 'Two identical mappings ... return True')."""
    before = {"mission_id": "01ABC", "target_branch": "main"}
    after = dict(before)
    assert is_vcs_lock_only_change(before, after) is True


def test_only_vcs_lock_fields_differ_is_true() -> None:
    before = {"mission_id": "01ABC", "vcs": "git@old", "vcs_locked_at": "t0"}
    after = {"mission_id": "01ABC", "vcs": "git@new", "vcs_locked_at": "t1"}
    assert is_vcs_lock_only_change(before, after) is True


def test_non_lock_field_differing_is_false() -> None:
    before = {"mission_id": "01ABC", "target_branch": "main"}
    after = {"mission_id": "01ABC", "target_branch": "develop"}
    assert is_vcs_lock_only_change(before, after) is False


def test_mixed_lock_and_non_lock_diff_is_false() -> None:
    """Even when a lock field also differs, a non-lock diff anywhere in the
    key set fails the "only" contract."""
    before = {"mission_id": "01ABC", "vcs": "git@old"}
    after = {"mission_id": "01XYZ", "vcs": "git@new"}
    assert is_vcs_lock_only_change(before, after) is False


def test_before_none_is_treated_as_empty_mapping() -> None:
    """``before=None`` (no committed meta.json) shorthands to ``{}`` -- every
    key in ``after`` is then 'newly present'."""
    after_lock_only = {"vcs": "git@new"}
    assert is_vcs_lock_only_change(None, after_lock_only) is True

    after_non_lock = {"target_branch": "main"}
    assert is_vcs_lock_only_change(None, after_non_lock) is False


def test_key_absent_on_one_side_and_lock_field_is_true() -> None:
    """A lock field appearing/disappearing entirely (not just changing value)
    is still 'only a lock-field difference' -- the ``key not in
    VCS_LOCK_META_FIELDS`` guard on the presence-mismatch arm."""
    before = {"mission_id": "01ABC"}
    after = {"mission_id": "01ABC", "vcs": "git@new"}
    assert is_vcs_lock_only_change(before, after) is True


def test_key_absent_on_one_side_and_non_lock_field_is_false() -> None:
    before = {"mission_id": "01ABC"}
    after = {"mission_id": "01ABC", "extra_field": "value"}
    assert is_vcs_lock_only_change(before, after) is False


def test_present_but_none_differs_from_absent_c005() -> None:
    """C-005: a key absent on one side and present-but-``None`` on the other
    counts as a difference -- ``.get()`` would erase this distinction by
    returning ``None`` for both, so the sentinel-based comparison is
    load-bearing. Pinned for a non-lock field (must report a difference)."""
    before: dict[str, object] = {"mission_id": "01ABC"}
    after: dict[str, object] = {"mission_id": "01ABC", "coordination_branch": None}
    assert is_vcs_lock_only_change(before, after) is False


def test_present_but_none_lock_field_is_still_lock_only() -> None:
    """Same absent-vs-present-but-None distinction, but for a lock field --
    the presence-mismatch still counts as 'a difference', and it is still a
    lock-only one."""
    before: dict[str, object] = {"mission_id": "01ABC"}
    after: dict[str, object] = {"mission_id": "01ABC", "vcs": None}
    assert is_vcs_lock_only_change(before, after) is True


def test_empty_mappings_are_vcs_lock_only() -> None:
    assert is_vcs_lock_only_change({}, {}) is True


# --------------------------------------------------------------------------- #
# ``project_metadata_without_vcs_lock`` -- the lock normalisation other modules
# use instead of inspecting the field set themselves (#7106).
# --------------------------------------------------------------------------- #
def test_projection_drops_the_timestamp_whenever_present() -> None:
    """The write timestamp never carries planning meaning, whatever its value."""
    projected = project_metadata_without_vcs_lock({"mission_id": "01ABC", "vcs_locked_at": "t0"})
    assert projected == {"mission_id": "01ABC"}
    assert project_metadata_without_vcs_lock({"mission_id": "01ABC", "vcs_locked_at": None}) == {"mission_id": "01ABC"}


def test_projection_treats_absent_and_supported_backend_alike() -> None:
    """An absent selector and the backend a claim writes are the same state."""
    absent = project_metadata_without_vcs_lock({"mission_id": "01ABC"})
    written = project_metadata_without_vcs_lock({"mission_id": "01ABC", "vcs": "git", "vcs_locked_at": "t0"})
    assert absent == written == {"mission_id": "01ABC"}


@pytest.mark.parametrize("value", ["hg", "", None, 0])
def test_projection_preserves_any_other_backend_value(value: object) -> None:
    """Anything a claim would not write stays visible, so corruption is not silenced."""
    projected = project_metadata_without_vcs_lock({"mission_id": "01ABC", "vcs": value})
    assert projected == {"mission_id": "01ABC", "vcs": value}


def test_projection_does_not_mutate_its_input() -> None:
    original = {"mission_id": "01ABC", "vcs": "git", "vcs_locked_at": "t0"}
    snapshot = dict(original)
    project_metadata_without_vcs_lock(original)
    assert original == snapshot
