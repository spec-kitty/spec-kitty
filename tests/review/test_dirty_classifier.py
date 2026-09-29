"""Unit tests for dirty_classifier.py.

Covers the classify_dirty_paths() function which partitions git-status paths
into (blocking, benign) buckets for review handoff validation.
"""

from __future__ import annotations

import pytest

from specify_cli.review.dirty_classifier import (
    _is_review_handoff_survivor_path,
    classify_dirty_paths,
    owning_wp_for_path,
)

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _classify(paths: list[str], wp_id: str = "WP01", mission_slug: str = "066-test") -> tuple[list[str], list[str]]:
    """Thin wrapper so tests stay concise."""
    return classify_dirty_paths(paths, wp_id=wp_id, mission_slug=mission_slug)


# ---------------------------------------------------------------------------
# 1. Empty input
# ---------------------------------------------------------------------------

def test_empty_dirty_list():
    blocking, benign = _classify([])
    assert blocking == []
    assert benign == []


# ---------------------------------------------------------------------------
# 2. Status artifacts are benign
# ---------------------------------------------------------------------------

def test_status_artifacts_are_benign():
    paths = [
        "kitty-specs/066-test/status.events.jsonl",
        "kitty-specs/066-test/status.json",
    ]
    blocking, benign = _classify(paths)
    assert blocking == []
    assert set(benign) == set(paths)


# ---------------------------------------------------------------------------
# 3. Other WP task files are benign (WP02 when checking WP01)
# ---------------------------------------------------------------------------

def test_other_wp_task_files_are_benign():
    paths = [
        "kitty-specs/066-test/tasks/WP02-some-feature.md",
        "kitty-specs/066-test/tasks/WP03-another-feature.md",
        "kitty-specs/066-test/tasks/WP10-double-digit.md",
    ]
    blocking, benign = _classify(paths, wp_id="WP01")
    assert blocking == []
    assert set(benign) == set(paths)


# ---------------------------------------------------------------------------
# 4. Own task file is benign (planning artifact, auto-committed by move-task)
# ---------------------------------------------------------------------------

def test_own_task_file_is_benign():
    """WP task files are planning artifacts modified by move-task itself.
    They should not block review handoff even for the current WP."""
    paths = ["kitty-specs/066-test/tasks/WP01-my-feature.md"]
    blocking, benign = _classify(paths, wp_id="WP01")
    assert blocking == []
    assert benign == ["kitty-specs/066-test/tasks/WP01-my-feature.md"]


# ---------------------------------------------------------------------------
# 5. Source files are blocking
# ---------------------------------------------------------------------------

def test_source_files_are_blocking():
    paths = [
        "src/specify_cli/review/dirty_classifier.py",
        "tests/review/test_dirty_classifier.py",
        "pyproject.toml",
    ]
    blocking, benign = _classify(paths)
    assert set(blocking) == set(paths)
    assert benign == []


# ---------------------------------------------------------------------------
# 6. meta.json is benign
# ---------------------------------------------------------------------------

def test_meta_json_is_benign():
    paths = ["kitty-specs/066-test/meta.json"]
    blocking, benign = _classify(paths)
    assert blocking == []
    assert benign == ["kitty-specs/066-test/meta.json"]


# ---------------------------------------------------------------------------
# 7. .kittify/ paths are benign
# ---------------------------------------------------------------------------

def test_kittify_paths_are_benign():
    paths = [
        ".kittify/config.yaml",
        ".kittify/metadata.yaml",
        ".kittify/skills-manifest.json",
    ]
    blocking, benign = _classify(paths)
    assert blocking == []
    assert set(benign) == set(paths)


# ---------------------------------------------------------------------------
# 8. Mixed dirty paths — correct partition
# ---------------------------------------------------------------------------

def test_mixed_dirty_paths():
    blocking_paths = [
        "src/specify_cli/tasks.py",
    ]
    benign_paths = [
        "kitty-specs/066-test/tasks/WP01-my-feature.md",
        "kitty-specs/066-test/status.events.jsonl",
        "kitty-specs/066-test/status.json",
        "kitty-specs/066-test/tasks/WP02-other.md",
        ".kittify/config.yaml",
        "kitty-specs/066-test/meta.json",
        "kitty-specs/066-test/lanes.json",
    ]
    all_paths = blocking_paths + benign_paths

    blocking, benign = _classify(all_paths, wp_id="WP01")

    assert set(blocking) == set(blocking_paths)
    assert set(benign) == set(benign_paths)


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

def test_lanes_json_is_benign():
    paths = ["kitty-specs/066-test/lanes.json"]
    blocking, benign = _classify(paths)
    assert blocking == []
    assert benign == ["kitty-specs/066-test/lanes.json"]


def test_root_tasks_md_is_benign():
    """The summary tasks.md at the mission root is auto-updated by mark-status."""
    paths = ["kitty-specs/066-test/tasks.md"]
    blocking, benign = _classify(paths)
    assert blocking == []
    assert benign == paths


def test_wp_task_file_with_double_digit_wp_id():
    """All WP task files are benign planning artifacts, even the current WP's."""
    paths = ["kitty-specs/066-test/tasks/WP10-big-feature.md"]
    blocking, benign = _classify(paths, wp_id="WP10")
    assert blocking == []
    assert benign == paths


def test_wp_task_file_other_double_digit_is_benign():
    """WP10 is benign when checking WP01."""
    paths = ["kitty-specs/066-test/tasks/WP10-big-feature.md"]
    blocking, benign = _classify(paths, wp_id="WP01")
    assert blocking == []
    assert benign == paths


# ---------------------------------------------------------------------------
# WP01 (dirty-tree-guard-wp-scoped-01M3M3TT), T003: owning_wp_for_path /
# classify_dirty_paths ownership-attribution unit coverage (FR-001/002/003/
# 004/007/008, PLAN-ARCH-001, Compatibility & Reflexivity).
# ---------------------------------------------------------------------------


def test_cross_wp_directory_file_is_benign_regardless_of_extension():
    """FR-001/FR-002: a non-.md file nested under a DIFFERENT WP's task
    directory is benign, extension-independent (#5151 ask 3's in-progress
    script). Mutation control: the extension itself does not matter."""
    for suffix in (".py", ".md", ""):
        path = f"kitty-specs/066-test/tasks/WP02-foo/script{suffix}"
        blocking, benign = _classify([path], wp_id="WP01")
        assert blocking == [], f"suffix={suffix!r} wrongly blocked"
        assert benign == [path]


def test_wholly_untracked_wp_directory_path_is_benign():
    """FR-003: the bare WP directory path itself (trailing slash, no
    filename -- the shape git reports for a wholly-untracked WP subdirectory,
    kentonium3's Friction 2) is benign for a different WP."""
    path = "kitty-specs/066-test/tasks/WP02-foo/"
    blocking, benign = _classify([path], wp_id="WP01")
    assert blocking == []
    assert benign == [path]


def test_unattributable_path_still_blocks_for_every_wp_id():
    """FR-004 (fail-closed): a stray path matching no WP directory always
    blocks, for every wp_id -- paired with FR-001's positive control above
    (SC-003)."""
    paths = ["kitty-specs/066-test/some-stray-file.txt"]
    for wp_id in ("WP01", "WP02", "WP10"):
        blocking, benign = _classify(paths, wp_id=wp_id)
        assert blocking == paths, f"expected blocking for wp_id={wp_id}"
        assert benign == []


def test_own_directory_non_task_file_residue_still_blocks():
    """FR-007: a non-task-file nested under the MOVING WP's own directory
    keeps blocking -- the cross-WP exemption must not leak to a WP's own
    residue. Mutation control: still blocks regardless of extension."""
    for suffix in (".py", ""):
        path = f"kitty-specs/066-test/tasks/WP01-foo/scratch{suffix}"
        blocking, benign = _classify([path], wp_id="WP01")
        assert blocking == [path], f"suffix={suffix!r} wrongly passed as benign"
        assert benign == []


def test_cross_mission_wp_directory_is_not_a_match():
    """FR-008: a same-numbered WP under a DIFFERENT mission's kitty-specs/
    tree is never mistaken for an owner -- the path still blocks (or at
    minimum is not benign) when the caller's mission_slug is the current
    mission, not the other one. Mutation control: mission_slug itself is
    what flips the outcome, not the WP number."""
    path = "kitty-specs/077-other/tasks/WP01-foo/x.md"
    blocking, benign = _classify([path], wp_id="WP01", mission_slug="066-test")
    assert blocking == [path]
    assert benign == []


def test_own_directory_nested_md_file_still_blocks():
    """PLAN-ARCH-001 regression: spec.md's own literal AC3 path -- a nested
    .md file under the MOVING WP's own directory -- must resolve to
    blocking. The un-tightened wp_task_pattern (`.+` crossing `/`) wrongly
    classified this benign before owning_wp_for_path was ever consulted."""
    path = "kitty-specs/066-test/tasks/WP01-foo/scratch.md"
    blocking, benign = _classify([path], wp_id="WP01")
    assert blocking == [path]
    assert benign == []


def test_cross_mission_nested_md_file_still_blocks():
    """PLAN-ARCH-001 regression, FR-008 companion: a nested cross-mission
    .md path must not reach benign via the (now-tightened) flat-file
    short-circuit before owning_wp_for_path's own mission-scoping is
    consulted."""
    path = "kitty-specs/077-other/tasks/WP01-foo/x.md"
    blocking, benign = _classify([path], wp_id="WP01", mission_slug="066-test")
    assert blocking == [path]
    assert benign == []


def test_flat_non_task_file_directly_in_tasks_dir_is_not_wp_owned():
    """Risk control: a bare flat non-.md file directly in tasks/ (NOT inside
    a WP subdirectory) must not be mistaken for WP-owned residue -- the
    `(?:\\.md|/.*)` alternation requires either a flat `.md` suffix or a `/`
    boundary, neither of which a bare `tasks/WP01-foo.py` satisfies."""
    path = "kitty-specs/066-test/tasks/WP01-foo.py"
    blocking, benign = _classify([path], wp_id="WP01")
    assert blocking == [path]
    assert benign == []


def test_no_previously_benign_path_becomes_blocking():
    """Compatibility & Reflexivity (plan.md Design Decision (d)): benign only
    ever grows, never shrinks. Sweeps every path this file's *existing*
    benign-classification tests already exercise, across a representative
    set of wp_id values, and asserts every one stays benign after this
    mission's ownership-attribution change."""
    previously_benign_paths = [
        "kitty-specs/066-test/status.events.jsonl",
        "kitty-specs/066-test/status.json",
        "kitty-specs/066-test/tasks/WP02-some-feature.md",
        "kitty-specs/066-test/tasks/WP03-another-feature.md",
        "kitty-specs/066-test/tasks/WP10-double-digit.md",
        "kitty-specs/066-test/tasks/WP01-my-feature.md",
        "kitty-specs/066-test/meta.json",
        ".kittify/config.yaml",
        ".kittify/metadata.yaml",
        ".kittify/skills-manifest.json",
        "kitty-specs/066-test/lanes.json",
        "kitty-specs/066-test/tasks.md",
    ]
    for wp_id in ("WP01", "WP02", "WP10", "WP99"):
        blocking, benign = _classify(previously_benign_paths, wp_id=wp_id)
        assert blocking == [], f"regressed to blocking for wp_id={wp_id}: {blocking}"
        assert set(benign) == set(previously_benign_paths)


# ---------------------------------------------------------------------------
# PR-FRESH-001 (issue #5007): a "git status --porcelain" rename entry
# ("R  old -> new") is a single composite path string. Neither
# ``_is_review_handoff_survivor_path``'s ``wp_task_pattern`` (Bug A,
# pre-existing) nor ``owning_wp_for_path``'s trailing alternation (Bug B,
# introduced by this diff) was anchored/bounded against an embedded
# " -> new-path" tail, so a composite string could satisfy either end-to-end
# and fail-open. These are unit tests on the two helpers/entry points
# directly -- the real end-to-end repro (a REAL git-staged rename through the
# CLI) lives in test_tasks.py.
# ---------------------------------------------------------------------------


def test_wp_task_pattern_rejects_composite_rename_tail_bug_a():
    """Bug A: a rename whose NEW side happens to look like a flat WPxx task
    file must not short-circuit to benign via
    ``_is_review_handoff_survivor_path`` -- the un-anchored ``.search()``
    let a composite "garbage -> real-taskfile" string match on its trailing
    component alone, even though the composite as a whole is not itself a
    flat task-file path."""
    composite = "not-even-a-real-path -> kitty-specs/066-test/tasks/WP05-x.md"
    assert _is_review_handoff_survivor_path(composite) is False


def test_classify_dirty_paths_rename_composite_bug_a_stays_blocking():
    """Bug A reproduced through the public classify_dirty_paths entry point,
    using the exact composite from PR-FRESH-001's evidence: an
    unattributable rename must not resolve benign just because the rename's
    *new* side happens to look like a flat task file for an unrelated WP."""
    composite = "not-even-a-real-path -> kitty-specs/066-test/tasks/WP05-x.md"
    blocking, benign = classify_dirty_paths([composite], wp_id="WP01", mission_slug="066-test")
    assert blocking == [composite]
    assert benign == []


def test_owning_wp_for_path_rejects_composite_rename_bug_b():
    """Bug B: owning_wp_for_path's ``(?:\\.md|/.*)$`` alternation absorbed an
    embedded " -> new-path" tail, so a rename whose OLD side matched a
    different WP's directory resolved ownership from the OLD path's prefix
    alone -- even though the NEW side lands inside the moving WP's own
    directory. A composite string must resolve to None (unattributable),
    never to the old side's WP."""
    composite = "kitty-specs/066-test/tasks/WP02-foo/old.py -> kitty-specs/066-test/tasks/WP01-own/new.py"
    assert owning_wp_for_path(composite, "066-test") is None


def test_classify_dirty_paths_rename_composite_bug_b_stays_blocking():
    """Bug B reproduced through classify_dirty_paths: a rename INTO the
    moving WP's own directory from a different WP's directory must not
    resolve benign via the old path's prefix (FR-007, Clarifications Q2)."""
    composite = "kitty-specs/066-test/tasks/WP02-foo/old.py -> kitty-specs/066-test/tasks/WP01-own/new.py"
    blocking, benign = classify_dirty_paths([composite], wp_id="WP01", mission_slug="066-test")
    assert blocking == [composite]
    assert benign == []


def test_owning_wp_for_path_rejects_second_kitty_specs_occurrence():
    """Defensive hardening companion to Bug B: a composite whose tail embeds
    a second ``kitty-specs/`` occurrence (not just a bare rename arrow) must
    also fail to resolve to a WP, not just the literal ``" -> "`` shape."""
    composite = "kitty-specs/066-test/tasks/WP01-own/kitty-specs/066-test/tasks/WP01-own/x.py"
    assert owning_wp_for_path(composite, "066-test") is None
