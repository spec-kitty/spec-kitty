"""Pure-logic guards for the base-aware ``meta.json`` merge driver (#5460).

The driver body is exercised through its pre-existing file-level entry point
``run_meta_driver(base, ours, theirs)`` so a red run is a content assertion, never
a ``TypeError`` from a new signature. Real-git and subprocess cases live in
``test_meta_driver_base_aware_5460.py``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation import drivers
from specify_cli.consolidation.drivers import MergeDriverError, run_meta_driver
from specify_cli.lanes import consolidation as lanes_consolidation

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# Literal on purpose: the red commit must fail on content, not on a missing constant.
TWO_WAY_ENV = "SPEC_KITTY_META_MERGE_TWO_WAY"

# Captured from the #5460 reproducer (ancestor 8a24129..., the discarding clone,
# the teammate clone that locked the VCS).
ANCESTOR: dict[str, Any] = {
    "coordination_branch": "kitty/mission-team-01M48ZJZ",
    "created_at": "2026-10-06T16:08:45.754500+00:00",
    "flattened": False,
    "friendly_name": "Team QA",
    "mid8": "01M48ZJZ",
    "mission_id": "01M48ZJZD8FVS9JFZWYD26DZHC",
    "mission_number": None,
    "mission_slug": "team-01M48ZJZ",
    "mission_type": "software-dev",
    "purpose_context": "Functional QA fixture.",
    "purpose_tldr": "Two clone QA",
    "slug": "team-01M48ZJZ",
    "target_branch": "main",
    "topology": "coord",
}
DISCARDING: dict[str, Any] = {key: value for key, value in ANCESTOR.items() if key not in {"topology", "coordination_branch"}} | {
    "flattened": True,
    "discarded_at": "2026-10-06T16:09:05.242367+00:00",
}
TEAMMATE: dict[str, Any] = ANCESTOR | {
    "vcs": "git",
    "vcs_locked_at": "2026-10-06T16:09:00.623338+00:00",
}


def _drive(
    tmp_path: Path,
    base: dict[str, Any] | str | None,
    ours: dict[str, Any],
    theirs: dict[str, Any],
) -> dict[str, Any]:
    """Run the driver on sibling O/A/B files and return the merged A payload."""
    o_path, a_path, b_path = tmp_path / "O", tmp_path / "A", tmp_path / "B"
    if isinstance(base, str):
        o_path.write_text(base, encoding="utf-8")
    elif base is not None:
        o_path.write_text(json.dumps(base), encoding="utf-8")
    a_path.write_text(json.dumps(ours), encoding="utf-8")
    b_path.write_text(json.dumps(theirs), encoding="utf-8")
    run_meta_driver(str(o_path), str(a_path), str(b_path))
    merged: dict[str, Any] = json.loads(a_path.read_text(encoding="utf-8"))
    return merged


def test_discard_survives_a_teammates_unrelated_edit(tmp_path: Path) -> None:
    """The #5460 merge: a disjoint one-sided discard must not be reverted."""
    merged = _drive(tmp_path, ANCESTOR, DISCARDING, TEAMMATE)

    assert merged.get("discarded_at") == DISCARDING["discarded_at"]
    assert merged["flattened"] is True
    assert "topology" not in merged
    assert "coordination_branch" not in merged
    assert merged["vcs"] == "git"
    assert merged["vcs_locked_at"] == TEAMMATE["vcs_locked_at"]


def test_discard_survives_when_the_sides_swap(tmp_path: Path) -> None:
    """Rebase flips ours/theirs; the result must not depend on which side is which."""
    merged = _drive(tmp_path, ANCESTOR, TEAMMATE, DISCARDING)

    assert merged.get("discarded_at") == DISCARDING["discarded_at"]
    assert merged["flattened"] is True
    assert "topology" not in merged
    assert merged["vcs"] == "git"


def test_one_sided_change_survives_from_the_ours_side(tmp_path: Path) -> None:
    merged = _drive(tmp_path, {"a": 1, "b": 1}, {"a": 2, "b": 1}, {"a": 1, "b": 2})

    assert merged == {"a": 2, "b": 2}


def test_one_sided_deletion_survives(tmp_path: Path) -> None:
    merged = _drive(tmp_path, {"a": 1, "b": 1}, {"b": 1}, {"a": 1, "b": 1, "c": 3})

    assert merged == {"b": 1, "c": 3}


def test_deleted_vs_changed_planning_key_is_a_conflict_theirs_wins(tmp_path: Path) -> None:
    kept = _drive(tmp_path, {"x": 1}, {}, {"x": 2})
    assert kept == {"x": 2}


def test_deleted_by_theirs_vs_changed_by_ours_planning_key_is_absent(tmp_path: Path) -> None:
    gone = _drive(tmp_path, {"x": 1}, {"x": 2}, {})
    assert "x" not in gone


def test_null_and_absent_are_distinct_values(tmp_path: Path) -> None:
    """base {x:1}, ours {x:null}, theirs {} -> a conflict (planning key: theirs, absent)."""
    merged = _drive(tmp_path, {"x": 1, "y": 0}, {"x": None, "y": 0}, {"y": 0})
    assert "x" not in merged

    # null is a value: ours changed 1->null, theirs untouched -> null survives.
    kept_null = _drive(tmp_path, {"x": 1}, {"x": None}, {"x": 1})
    assert kept_null == {"x": None}


def test_coupled_flatten_group_moves_as_one_unit(tmp_path: Path) -> None:
    """One member conflicts, another is one-sided: the whole triple comes from one side."""
    base = {"topology": "coord", "coordination_branch": "c", "flattened": False}
    ours = {"flattened": True}  # flattened (deleted topology/branch, set flag)
    theirs = {"topology": "coord", "coordination_branch": "c2", "flattened": False}
    merged = _drive(tmp_path, base, ours, theirs)

    # Both sides changed the unit differently -> planning precedence -> theirs, whole.
    assert merged == theirs


def test_acceptance_history_dropped_on_one_side_is_still_unioned(tmp_path: Path) -> None:
    entry = {"accepted_at": "2026-10-01T00:00:00Z", "accepted_by": "a"}
    base = {"acceptance_history": [entry], "k": 1}
    merged = _drive(tmp_path, base, {"k": 2}, {"acceptance_history": [entry], "k": 1})

    assert merged["acceptance_history"] == [entry]
    assert merged["k"] == 2


def test_assigned_mission_number_is_never_replaced_by_unassigned(tmp_path: Path) -> None:
    """base 5 / ours null / theirs 5 -> 5 even though only ours 'changed' (#4900)."""
    merged = _drive(tmp_path, {"mission_number": 5}, {"mission_number": None}, {"mission_number": 5})

    assert merged["mission_number"] == 5


def test_both_sides_adding_the_same_key_collapse_to_one(tmp_path: Path) -> None:
    merged = _drive(tmp_path, {"a": 1}, {"a": 1, "n": "v"}, {"a": 1, "n": "v", "m": 2})

    assert merged == {"a": 1, "n": "v", "m": 2}


def test_genuine_conflict_keeps_target_authoritative_precedence(tmp_path: Path) -> None:
    base = {"purpose_tldr": "a", "status": "in_review"}
    ours = {"purpose_tldr": "b", "status": "accepted"}
    theirs = {"purpose_tldr": "c", "status": "approved"}

    merged = _drive(tmp_path, base, ours, theirs)

    assert merged == {"purpose_tldr": "c", "status": "accepted"}


def test_malformed_ancestor_fails_loud_and_writes_nothing(tmp_path: Path) -> None:
    a_path = tmp_path / "A"
    (tmp_path / "O").write_text("{ not json", encoding="utf-8")
    a_path.write_text(json.dumps({"k": 1}), encoding="utf-8")
    (tmp_path / "B").write_text(json.dumps({"k": 2}), encoding="utf-8")

    with pytest.raises(MergeDriverError) as excinfo:
        run_meta_driver(str(tmp_path / "O"), str(a_path), str(tmp_path / "B"))

    assert str(tmp_path / "O") in str(excinfo.value)
    assert json.loads(a_path.read_text(encoding="utf-8")) == {"k": 1}


def test_whitespace_only_ancestor_selects_the_two_way_rule(tmp_path: Path) -> None:
    merged = _drive(tmp_path, "\n  \n", {"a": 2, "b": 1}, {"a": 1, "b": 2})

    # two-way: every key from theirs (no target-authoritative key involved).
    assert merged == {"a": 1, "b": 2}


def test_absent_and_empty_object_ancestors_select_the_two_way_rule(tmp_path: Path) -> None:
    (tmp_path / "absent").mkdir()
    absent = _drive(tmp_path / "absent", None, {"a": 2}, {"a": 1})
    empty = _drive(tmp_path, {}, {"a": 2}, {"a": 1})

    assert absent == empty == {"a": 1}


def test_squash_pipeline_sets_the_two_way_opt_out_on_its_merge_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The mission->target squash subprocess carries the opt-out; `_make_merge_env` does not."""
    seen: list[dict[str, str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:3] == ["git", "merge", "--squash"]:
            seen.append(dict(kwargs["env"]))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(lanes_consolidation.subprocess, "run", fake_run)

    lanes_consolidation._run_squash_merge(tmp_path, tmp_path, "src", "tgt", lanes_consolidation._make_merge_env())

    assert len(seen) == 1
    assert seen[0].get(TWO_WAY_ENV) == "1"
    assert TWO_WAY_ENV not in lanes_consolidation._make_merge_env()


def test_two_way_keyword_ignores_the_ancestor(tmp_path: Path) -> None:
    """``two_way=True`` (the squash opt-out) never reads %O, even a corrupt one."""
    (tmp_path / "O").write_text("{ not json", encoding="utf-8")
    (tmp_path / "A").write_text(json.dumps({"a": 2, "b": 1}), encoding="utf-8")
    (tmp_path / "B").write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")

    run_meta_driver(str(tmp_path / "O"), str(tmp_path / "A"), str(tmp_path / "B"), two_way=True)

    assert json.loads((tmp_path / "A").read_text(encoding="utf-8")) == {"a": 1, "b": 2}


def test_opt_out_constant_value_and_pipeline_env_authority() -> None:
    assert drivers.META_DRIVER_TWO_WAY_ENV == TWO_WAY_ENV
    assert TWO_WAY_ENV not in lanes_consolidation._make_merge_env()


def test_acceptance_stamp_group_is_the_five_stamp_keys() -> None:
    groups = {key for group in drivers._META_COUPLED_KEY_GROUPS for key in group}
    stamps = {"accepted_at", "accepted_by", "accepted_from_commit", "acceptance_mode", "accept_commit"}

    assert stamps <= groups
    assert not {"vcs", "vcs_locked_at"} & groups


def test_merged_block_conflict_resolves_as_one_target_authoritative_unit(tmp_path: Path) -> None:
    """A reopen deleted the block on one side; the other re-recorded it: never a half block."""
    base = {"merged_at": "t0", "merged_by": "x", "merged_commit": "c0", "k": 1}
    ours = {"merged_at": "t1", "merged_by": "y", "merged_commit": "c1", "k": 1}
    # theirs deletes the three recorded keys (a conflict with ours' edits) and adds
    # merged_push alone: a one-sided add that key-by-key logic would keep. Only the
    # coupled-group rule drops it, so the whole block must come from ours.
    theirs = {"merged_push": True, "k": 1}

    merged = _drive(tmp_path, base, ours, theirs)

    assert "merged_push" not in merged
    assert merged == ours


def test_acceptance_stamps_move_as_one_unit(tmp_path: Path) -> None:
    base = {"accepted_at": "t0", "accepted_by": "a", "acceptance_mode": "m", "k": 1}
    ours = {"accepted_at": "t1", "accepted_by": "b", "acceptance_mode": "m", "k": 1}
    theirs = {"accepted_at": "t0", "accepted_by": "a", "acceptance_mode": "m2", "k": 2}

    merged = _drive(tmp_path, base, ours, theirs)

    # Conflict on the stamp unit -> target-authoritative -> ours as a whole; k is one-sided.
    assert merged == {"accepted_at": "t1", "accepted_by": "b", "acceptance_mode": "m", "k": 2}
