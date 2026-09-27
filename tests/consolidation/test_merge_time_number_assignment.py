"""Tests for merge-time mission_number assignment (WP10 / FR-044).

Covers:
- T051: ``needs_number_assignment`` distinguishes pre-merge null from any
        non-null value (including legacy string forms).
- T052: ``assign_next_mission_number`` returns ``max(existing) + 1`` (or 1).
- T053: assignment is idempotent and respects already-assigned legacy missions.
- T056: assignment, idempotency, legacy no-op, and concurrent-collision
        scenarios via direct helper invocation under a test-only lock.

These tests run against fixture ``kitty-specs/<slug>/meta.json`` files in a
temporary directory and exercise the helpers directly.  They do **not**
exercise the full git merge flow — that surface is covered by the rest of the
``tests/merge/`` suite.  The priority here is to prove the logic of the
single-writer assignment.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from specify_cli.consolidation.ordering import assign_next_mission_number
from specify_cli.consolidation.state import needs_number_assignment

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_meta(
    feature_dir: Path,
    *,
    slug: str,
    mission_number: int | str | None,
    mission_type: str = "software-dev",
    target_branch: str = "main",
) -> Path:
    """Create a kitty-specs/<slug>/meta.json fixture with the given fields."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "slug": slug,
        "mission_slug": slug,
        "friendly_name": slug.replace("-", " ").title(),
        "mission_type": mission_type,
        "target_branch": target_branch,
        "created_at": "2026-04-11T00:00:00+00:00",
        "mission_number": mission_number,
    }
    meta_path = feature_dir / "meta.json"
    meta_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return meta_path


def _read_meta(feature_dir: Path) -> dict:
    return json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))


def _make_target_view(tmp_path: Path) -> tuple[Path, Path]:
    """Return (target_branch_root, kitty_specs_dir) for an empty target."""
    target_root = tmp_path / "target"
    kitty_specs = target_root / "kitty-specs"
    kitty_specs.mkdir(parents=True, exist_ok=True)
    return target_root, kitty_specs


# ---------------------------------------------------------------------------
# T051: needs_number_assignment helper
# ---------------------------------------------------------------------------


class TestNeedsNumberAssignment:
    """``needs_number_assignment`` reads meta.json via the canonical loader."""

    def test_null_means_needs_assignment(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "083-foo"
        _write_meta(feature_dir, slug="083-foo", mission_number=None)

        assert needs_number_assignment(feature_dir) is True

    def test_zero_is_already_assigned(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "000-zero"
        _write_meta(feature_dir, slug="000-zero", mission_number=0)

        # ``0`` is a legitimate integer; the gate should treat it as assigned.
        assert needs_number_assignment(feature_dir) is False

    def test_positive_int_is_already_assigned(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "042-something"
        _write_meta(feature_dir, slug="042-something", mission_number=42)

        assert needs_number_assignment(feature_dir) is False

    def test_legacy_string_is_already_assigned(self, tmp_path: Path) -> None:
        # T054: legacy "042" string must be treated as already-assigned because
        # the metadata loader coerces it to int 42 at read time.
        feature_dir = tmp_path / "kitty-specs" / "042-legacy"
        _write_meta(feature_dir, slug="042-legacy", mission_number="042")

        assert needs_number_assignment(feature_dir) is False

    def test_missing_meta_returns_false(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "999-nope"
        feature_dir.mkdir(parents=True, exist_ok=True)
        # No meta.json written.

        assert needs_number_assignment(feature_dir) is False


# ---------------------------------------------------------------------------
# T052: assign_next_mission_number helper
# ---------------------------------------------------------------------------


class TestAssignNextMissionNumber:
    """``assign_next_mission_number`` walks the target's kitty-specs view."""

    def test_empty_target_returns_one(self, tmp_path: Path) -> None:
        target_root, kitty_specs = _make_target_view(tmp_path)

        assert assign_next_mission_number(target_root, kitty_specs) == 1

    def test_missing_kitty_specs_returns_one(self, tmp_path: Path) -> None:
        target_root = tmp_path / "target"
        target_root.mkdir(parents=True, exist_ok=True)
        kitty_specs = target_root / "kitty-specs"
        # Do NOT create kitty_specs.

        assert assign_next_mission_number(target_root, kitty_specs) == 1

    def test_dense_sequence_returns_max_plus_one(self, tmp_path: Path) -> None:
        target_root, kitty_specs = _make_target_view(tmp_path)
        for n in range(1, 43):  # 1..42 inclusive
            _write_meta(
                kitty_specs / f"{n:03d}-feature-{n}",
                slug=f"{n:03d}-feature-{n}",
                mission_number=n,
            )

        assert assign_next_mission_number(target_root, kitty_specs) == 43

    def test_excludes_pre_merge_null_missions(self, tmp_path: Path) -> None:
        # Pre-merge missions on the target branch should NOT participate
        # in the max computation.
        target_root, kitty_specs = _make_target_view(tmp_path)
        _write_meta(kitty_specs / "001-old", slug="001-old", mission_number=1)
        _write_meta(kitty_specs / "002-old", slug="002-old", mission_number=2)
        _write_meta(kitty_specs / "999-pre", slug="999-pre", mission_number=None)

        assert assign_next_mission_number(target_root, kitty_specs) == 3

    def test_handles_legacy_string_numbers(self, tmp_path: Path) -> None:
        target_root, kitty_specs = _make_target_view(tmp_path)
        _write_meta(kitty_specs / "001-old", slug="001-old", mission_number="001")
        _write_meta(kitty_specs / "042-other", slug="042-other", mission_number="042")

        assert assign_next_mission_number(target_root, kitty_specs) == 43

    def test_handles_collision_in_existing_data(self, tmp_path: Path) -> None:
        # Drift case: two missions both claim 42.  Shouldn't happen post
        # migration but the algorithm should still pick 43.
        target_root, kitty_specs = _make_target_view(tmp_path)
        _write_meta(kitty_specs / "042-a", slug="042-a", mission_number=42)
        _write_meta(kitty_specs / "042-b", slug="042-b", mission_number=42)

        assert assign_next_mission_number(target_root, kitty_specs) == 43

    def test_skips_directories_without_meta(self, tmp_path: Path) -> None:
        target_root, kitty_specs = _make_target_view(tmp_path)
        _write_meta(kitty_specs / "001-good", slug="001-good", mission_number=1)
        # A bare directory with no meta.json should be silently ignored.
        (kitty_specs / "templates").mkdir()
        (kitty_specs / "templates" / "README.md").write_text("hi", encoding="utf-8")

        assert assign_next_mission_number(target_root, kitty_specs) == 2

    def test_skips_non_directory_entries(self, tmp_path: Path) -> None:
        """Files directly under kitty-specs/ are ignored during the scan."""
        target_root, kitty_specs = _make_target_view(tmp_path)
        _write_meta(kitty_specs / "001-good", slug="001-good", mission_number=1)
        (kitty_specs / "README.md").write_text("hi", encoding="utf-8")

        assert assign_next_mission_number(target_root, kitty_specs) == 2

    def test_skips_malformed_mission_numbers(self, tmp_path: Path) -> None:
        """Malformed mission_number values are warned on and skipped."""
        target_root, kitty_specs = _make_target_view(tmp_path)
        _write_meta(kitty_specs / "001-good", slug="001-good", mission_number=1)
        _write_meta(kitty_specs / "broken", slug="broken", mission_number=[])

        assert assign_next_mission_number(target_root, kitty_specs) == 2


# ---------------------------------------------------------------------------
# T056 — Test 1: assignment writes an integer into meta.json
# ---------------------------------------------------------------------------


def _simulate_assignment(
    target_root: Path,
    kitty_specs: Path,
    feature_dir: Path,
    *,
    lock: threading.Lock | None = None,
) -> int | None:
    """In-process simulation of the merge-time assignment step.

    Mirrors the locked write semantics of
    :func:`specify_cli.cli.commands.consolidate._bake_mission_number_into_mission_branch`
    without the git worktree dance.  This isolates the assignment logic so the
    tests run in milliseconds and remain reliable.
    """
    if lock is not None:
        lock.acquire()
    try:
        if not needs_number_assignment(feature_dir):
            return None
        next_number = assign_next_mission_number(target_root, kitty_specs)
        meta = _read_meta(feature_dir)
        meta["mission_number"] = next_number
        (feature_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        # The "merge" step: copy the now-numbered meta into the target view so
        # subsequent assignments observe the new max.
        target_copy = kitty_specs / feature_dir.name
        target_copy.mkdir(parents=True, exist_ok=True)
        (target_copy / "meta.json").write_text(
            (feature_dir / "meta.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return next_number
    finally:
        if lock is not None:
            lock.release()


class TestMergeTimeAssignmentScenarios:
    """End-to-end scenarios for the WP10 four-case grid (T056)."""

    def test_assignment_writes_integer(self, tmp_path: Path) -> None:
        target_root, kitty_specs = _make_target_view(tmp_path)
        # Seed target branch with one already-assigned mission to verify the
        # next number is computed correctly.
        _write_meta(kitty_specs / "042-existing", slug="042-existing", mission_number=42)

        # Pre-merge mission lives in the worktree (not yet on target).
        feature_dir = tmp_path / "worktree" / "kitty-specs" / "083-pre-merge"
        _write_meta(feature_dir, slug="083-pre-merge", mission_number=None)
        assert needs_number_assignment(feature_dir) is True

        assigned = _simulate_assignment(target_root, kitty_specs, feature_dir)

        assert assigned == 43
        meta = _read_meta(feature_dir)
        assert meta["mission_number"] == 43
        assert isinstance(meta["mission_number"], int)
        assert needs_number_assignment(feature_dir) is False

    def test_idempotency_second_run_no_op(self, tmp_path: Path) -> None:
        target_root, kitty_specs = _make_target_view(tmp_path)
        feature_dir = tmp_path / "worktree" / "kitty-specs" / "083-pre-merge"
        _write_meta(feature_dir, slug="083-pre-merge", mission_number=None)

        first = _simulate_assignment(target_root, kitty_specs, feature_dir)
        assert first == 1
        assert _read_meta(feature_dir)["mission_number"] == 1

        # Second invocation: gate returns False, so no assignment happens.
        second = _simulate_assignment(target_root, kitty_specs, feature_dir)
        assert second is None
        assert _read_meta(feature_dir)["mission_number"] == 1

    def test_legacy_already_assigned_no_op(self, tmp_path: Path) -> None:
        target_root, kitty_specs = _make_target_view(tmp_path)
        # Seed target with some other missions so the "next" would be 100 if
        # we naively reassigned.
        _write_meta(kitty_specs / "099-other", slug="099-other", mission_number=99)

        feature_dir = tmp_path / "worktree" / "kitty-specs" / "042-legacy"
        _write_meta(feature_dir, slug="042-legacy", mission_number=42)

        # Gate must short-circuit: already assigned.
        assigned = _simulate_assignment(target_root, kitty_specs, feature_dir)
        assert assigned is None

        meta = _read_meta(feature_dir)
        assert meta["mission_number"] == 42, "Existing integer must be preserved"

    def test_legacy_string_form_no_op(self, tmp_path: Path) -> None:
        # T054 fixture: a legacy mission stored as string "042" passes through
        # untouched.  After the no-op, the on-disk value remains "042" because
        # the assignment helper does not rewrite already-assigned missions.
        target_root, kitty_specs = _make_target_view(tmp_path)
        feature_dir = tmp_path / "worktree" / "kitty-specs" / "042-legacy-string"
        _write_meta(feature_dir, slug="042-legacy-string", mission_number="042")

        assigned = _simulate_assignment(target_root, kitty_specs, feature_dir)
        assert assigned is None

        # On-disk form is preserved (write path was never invoked).
        meta = _read_meta(feature_dir)
        assert meta["mission_number"] == "042"

    def test_concurrent_collision_produces_distinct_numbers(self, tmp_path: Path) -> None:
        """Two merge paths against the same target each get a distinct integer.

        Spawning real ``spec-kitty merge`` processes is overkill for the
        invariant under test (mutual exclusion + max+1 monotonicity), so we
        use threads under a shared lock that mirrors the per-mission
        merge-state lock contract.
        """
        target_root, kitty_specs = _make_target_view(tmp_path)
        # Pre-existing mission so the "next" starts at 43.
        _write_meta(kitty_specs / "042-base", slug="042-base", mission_number=42)

        feature_a = tmp_path / "wt-a" / "kitty-specs" / "083-mission-a"
        feature_b = tmp_path / "wt-b" / "kitty-specs" / "084-mission-b"
        _write_meta(feature_a, slug="083-mission-a", mission_number=None)
        _write_meta(feature_b, slug="084-mission-b", mission_number=None)

        lock = threading.Lock()
        results: dict[str, int | None] = {}

        def _runner(name: str, feature_dir: Path) -> None:
            results[name] = _simulate_assignment(
                target_root, kitty_specs, feature_dir, lock=lock
            )

        threads = [
            threading.Thread(target=_runner, args=("a", feature_a)),
            threading.Thread(target=_runner, args=("b", feature_b)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Both ran, both produced an integer, both integers are distinct
        # and >= 43.  We don't care which mission got 43 vs 44 — only that
        # the lock prevented a duplicate.
        assert results["a"] is not None
        assert results["b"] is not None
        assert {results["a"], results["b"]} == {43, 44}

        # And the on-disk values match.
        assert _read_meta(feature_a)["mission_number"] in {43, 44}
        assert _read_meta(feature_b)["mission_number"] in {43, 44}
        assert _read_meta(feature_a)["mission_number"] != _read_meta(feature_b)["mission_number"]
