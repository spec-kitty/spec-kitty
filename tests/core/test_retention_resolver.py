"""Unit tests for the merge retention resolver (#3131 WP01).

Covers `read_retention_from_meta` and `resolve_merge_retention` /
`RetentionDecision` per `contracts/retention-resolver-contract.md` (the C1-C6
precedence table), plus malformed-value fail-closed handling, corrupt-meta
propagation, provenance, and the `teardown_coordination` truth table.

Pure-logic: a `tmp_path` meta.json fixture only, no git.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.core.paths import (
    MissionMetaReadError,
    RetentionDecision,
    read_retention_from_meta,
    resolve_merge_retention,
)

pytestmark = [pytest.mark.unit]


def _write_meta(meta_dir: Path, payload: dict[str, object] | None) -> None:
    meta_dir.mkdir(parents=True, exist_ok=True)
    if payload is None:
        return
    (meta_dir / "meta.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_corrupt_meta(meta_dir: Path) -> None:
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "meta.json").write_text("{not valid json", encoding="utf-8")


# ---------------------------------------------------------------------------
# read_retention_from_meta
# ---------------------------------------------------------------------------


def test_read_retention_from_meta_absent_file_returns_none_none(tmp_path: Path) -> None:
    meta_dir = tmp_path / "mission"
    meta_dir.mkdir()
    assert read_retention_from_meta(meta_dir) == (None, None)


def test_read_retention_from_meta_absent_fields_returns_none_none(tmp_path: Path) -> None:
    meta_dir = tmp_path / "mission"
    _write_meta(meta_dir, {"mission_slug": "x"})
    assert read_retention_from_meta(meta_dir) == (None, None)


def test_read_retention_from_meta_returns_raw_values_uncoerced(tmp_path: Path) -> None:
    meta_dir = tmp_path / "mission"
    _write_meta(meta_dir, {"retain_branches": "true", "retain_worktrees": 0})
    branches, worktrees = read_retention_from_meta(meta_dir)
    # RAW: not coerced to bool -- caller must detect the non-bool types itself.
    assert branches == "true"
    assert isinstance(branches, str)
    assert worktrees == 0
    assert isinstance(worktrees, int)
    assert not isinstance(worktrees, bool)


def test_read_retention_from_meta_corrupt_raises(tmp_path: Path) -> None:
    meta_dir = tmp_path / "mission"
    _write_corrupt_meta(meta_dir)
    with pytest.raises(MissionMetaReadError):
        read_retention_from_meta(meta_dir)


# ---------------------------------------------------------------------------
# resolve_merge_retention -- C1-C6 contract table (branches column; worktrees
# is symmetric via `explicit_remove_worktree` / `retain_worktrees`)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "explicit_delete_branch", "meta_retain_branches", "expected_delete_branch", "expected_source"),
    [
        # C1: unset, no policy -> default True (delete)
        ("C1-absent", None, None, True, "default"),
        ("C1-false", None, False, True, "default"),
        # C2: unset, retain -> False (keep), source meta
        ("C2", None, True, False, "meta"),
        # C4: explicit keep wins over any meta state
        ("C4-vs-no-policy", False, None, False, "cli"),
        ("C4-vs-retain", False, True, False, "cli"),
        # C5: explicit delete, no policy -> True, source cli
        ("C5", True, None, True, "cli"),
        ("C5-false", True, False, True, "cli"),
        # C6: explicit delete overrides retain -> True, source cli
        ("C6", True, True, True, "cli"),
    ],
)
def test_resolve_merge_retention_branches_contract_table(
    tmp_path: Path,
    case: str,
    explicit_delete_branch: bool | None,
    meta_retain_branches: bool | None,
    expected_delete_branch: bool,
    expected_source: str,
) -> None:
    meta_dir = tmp_path / case
    payload: dict[str, object] = {}
    if meta_retain_branches is not None:
        payload["retain_branches"] = meta_retain_branches
    _write_meta(meta_dir, payload)

    decision = resolve_merge_retention(
        meta_dir,
        explicit_delete_branch=explicit_delete_branch,
        explicit_remove_worktree=None,
    )

    assert decision.delete_branch is expected_delete_branch
    assert decision.branch_source == expected_source


@pytest.mark.parametrize(
    ("case", "explicit_remove_worktree", "meta_retain_worktrees", "expected_remove_worktree", "expected_source"),
    [
        ("C1-absent", None, None, True, "default"),
        ("C1-false", None, False, True, "default"),
        ("C2", None, True, False, "meta"),
        ("C4-vs-no-policy", False, None, False, "cli"),
        ("C4-vs-retain", False, True, False, "cli"),
        ("C5", True, None, True, "cli"),
        ("C5-false", True, False, True, "cli"),
        ("C6", True, True, True, "cli"),
    ],
)
def test_resolve_merge_retention_worktrees_contract_table(
    tmp_path: Path,
    case: str,
    explicit_remove_worktree: bool | None,
    meta_retain_worktrees: bool | None,
    expected_remove_worktree: bool,
    expected_source: str,
) -> None:
    meta_dir = tmp_path / case
    payload: dict[str, object] = {}
    if meta_retain_worktrees is not None:
        payload["retain_worktrees"] = meta_retain_worktrees
    _write_meta(meta_dir, payload)

    decision = resolve_merge_retention(
        meta_dir,
        explicit_delete_branch=None,
        explicit_remove_worktree=explicit_remove_worktree,
    )

    assert decision.remove_worktree is expected_remove_worktree
    assert decision.worktree_source == expected_source


def test_c2_unset_retain_emits_warning_naming_source(tmp_path: Path) -> None:
    meta_dir = tmp_path / "c2"
    _write_meta(meta_dir, {"retain_branches": True})

    decision = resolve_merge_retention(meta_dir, explicit_delete_branch=None, explicit_remove_worktree=None)

    assert decision.delete_branch is False
    assert len(decision.warnings) == 1
    assert "meta.json" in decision.warnings[0]
    assert decision.override_notices == ()


def test_c6_explicit_delete_over_retain_emits_override_notice(tmp_path: Path) -> None:
    meta_dir = tmp_path / "c6"
    _write_meta(meta_dir, {"retain_branches": True})

    decision = resolve_merge_retention(meta_dir, explicit_delete_branch=True, explicit_remove_worktree=None)

    assert decision.delete_branch is True
    assert decision.branch_source == "cli"
    assert decision.warnings == ()
    assert len(decision.override_notices) == 1
    assert "overrode" in decision.override_notices[0].lower()


def test_c5_explicit_delete_no_policy_emits_no_notices(tmp_path: Path) -> None:
    meta_dir = tmp_path / "c5"
    _write_meta(meta_dir, {})

    decision = resolve_merge_retention(meta_dir, explicit_delete_branch=True, explicit_remove_worktree=None)

    assert decision.delete_branch is True
    assert decision.branch_source == "cli"
    assert decision.warnings == ()
    assert decision.override_notices == ()


# ---------------------------------------------------------------------------
# Malformed (non-boolean) meta values -- fail-closed data-loss trap
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("malformed", ["", 0, "true", "false"])
def test_malformed_retain_branches_value_retains_with_warning(tmp_path: Path, malformed: object) -> None:
    meta_dir = tmp_path / "malformed"
    _write_meta(meta_dir, {"retain_branches": malformed})

    decision = resolve_merge_retention(meta_dir, explicit_delete_branch=None, explicit_remove_worktree=None)

    assert decision.delete_branch is False, f"malformed value {malformed!r} must retain, never coerce"
    assert decision.branch_source == "meta"
    assert len(decision.warnings) == 1
    assert "malformed" in decision.warnings[0].lower()


@pytest.mark.parametrize("malformed", ["", 0, "true", "false"])
def test_malformed_retain_worktrees_value_retains_with_warning(tmp_path: Path, malformed: object) -> None:
    meta_dir = tmp_path / "malformed-wt"
    _write_meta(meta_dir, {"retain_worktrees": malformed})

    decision = resolve_merge_retention(meta_dir, explicit_delete_branch=None, explicit_remove_worktree=None)

    assert decision.remove_worktree is False, f"malformed value {malformed!r} must retain, never coerce"
    assert decision.worktree_source == "meta"
    assert len(decision.warnings) == 1
    assert "malformed" in decision.warnings[0].lower()


def test_explicit_json_null_behaves_as_absent_not_malformed(tmp_path: Path) -> None:
    """DEVIATION NOTE (see WP01 report): the contract's malformed-value list
    (data-model.md, WP01 T004) names JSON `null` alongside `""`/`0`/`"true"`/
    `"false"`. But T002 mandates `read_retention_from_meta` return raw
    `meta.get(key)` values, and `dict.get()` cannot distinguish a key that is
    absent from a key present with a JSON `null` value -- both decode to
    Python `None`. Given that literal read-path instruction, `null` and
    "field absent" are necessarily indistinguishable downstream, so both
    resolve via the `default` path (no policy stated), not the `malformed`
    retain-with-warning path. This test pins that (necessary) behavior so a
    future change is a deliberate decision, not a silent regression.
    """
    meta_dir = tmp_path / "explicit-null"
    _write_meta(meta_dir, {"retain_branches": None, "retain_worktrees": None})

    decision = resolve_merge_retention(meta_dir, explicit_delete_branch=None, explicit_remove_worktree=None)

    assert decision.delete_branch is True
    assert decision.branch_source == "default"
    assert decision.remove_worktree is True
    assert decision.worktree_source == "default"
    assert decision.warnings == ()


def test_malformed_value_explicit_delete_still_overrides(tmp_path: Path) -> None:
    """A malformed meta value is treated as retaining, so an explicit delete
    over it must still record an override_notice (same as a well-formed
    `true`)."""
    meta_dir = tmp_path / "malformed-override"
    _write_meta(meta_dir, {"retain_branches": "not-a-bool"})

    decision = resolve_merge_retention(meta_dir, explicit_delete_branch=True, explicit_remove_worktree=None)

    assert decision.delete_branch is True
    assert decision.branch_source == "cli"
    assert len(decision.override_notices) == 1


def test_isinstance_true_is_int_trap_true_is_not_treated_as_malformed(
    tmp_path: Path,
) -> None:
    """Regression for the isinstance(True, int) trap: a real JSON `true` must
    hit the C2 retain-with-warning path, never the malformed path."""
    meta_dir = tmp_path / "bool-is-not-int"
    _write_meta(meta_dir, {"retain_branches": True})

    decision = resolve_merge_retention(meta_dir, explicit_delete_branch=None, explicit_remove_worktree=None)

    assert decision.delete_branch is False
    assert "malformed" not in decision.warnings[0].lower()
    assert "honored" in decision.warnings[0].lower() or "retention" in decision.warnings[0].lower()


# ---------------------------------------------------------------------------
# Corrupt meta.json propagation
# ---------------------------------------------------------------------------


def test_resolve_merge_retention_corrupt_meta_raises(tmp_path: Path) -> None:
    meta_dir = tmp_path / "corrupt"
    _write_corrupt_meta(meta_dir)

    with pytest.raises(MissionMetaReadError):
        resolve_merge_retention(meta_dir, explicit_delete_branch=None, explicit_remove_worktree=None)


# ---------------------------------------------------------------------------
# teardown_coordination truth table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("delete_branch", "remove_worktree", "expected_teardown"),
    [
        (True, True, True),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    ],
)
def test_teardown_coordination_truth_table(
    tmp_path: Path,
    delete_branch: bool,
    remove_worktree: bool,
    expected_teardown: bool,
) -> None:
    meta_dir = tmp_path / f"teardown-{delete_branch}-{remove_worktree}"
    _write_meta(meta_dir, {})

    decision = resolve_merge_retention(
        meta_dir,
        explicit_delete_branch=delete_branch,
        explicit_remove_worktree=remove_worktree,
    )

    assert decision.delete_branch is delete_branch
    assert decision.remove_worktree is remove_worktree
    assert decision.teardown_coordination is expected_teardown


def test_retention_decision_is_frozen(tmp_path: Path) -> None:
    meta_dir = tmp_path / "frozen"
    _write_meta(meta_dir, {})

    decision = resolve_merge_retention(meta_dir, explicit_delete_branch=None, explicit_remove_worktree=None)

    assert isinstance(decision, RetentionDecision)
    with pytest.raises(AttributeError):
        decision.delete_branch = False


# ---------------------------------------------------------------------------
# Independence: branches and worktrees resolve independently
# ---------------------------------------------------------------------------


def test_branches_and_worktrees_resolve_independently(tmp_path: Path) -> None:
    meta_dir = tmp_path / "independent"
    _write_meta(meta_dir, {"retain_branches": True, "retain_worktrees": False})

    decision = resolve_merge_retention(meta_dir, explicit_delete_branch=None, explicit_remove_worktree=None)

    assert decision.delete_branch is False
    assert decision.branch_source == "meta"
    assert decision.remove_worktree is True
    assert decision.worktree_source == "default"
    assert len(decision.warnings) == 1
