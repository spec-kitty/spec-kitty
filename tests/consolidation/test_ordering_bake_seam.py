"""Seam test for the relocated mission-number bake cluster (mission #2057, WP07).

Covers the bake orchestrator's short-circuits (already-baked, non-git-repo,
no-op-on-target, dry-run) and the helper predicates. The re-export-identity
guard for ``_bake_mission_number_into_mission_branch`` and the one-way-import
guard (INV-2) live in the consolidated
``tests/merge/test_merge_compat_surface.py`` (WP04,
dev-assist-retire-path-hardening-01KXAVR0 / #2565) — this file keeps only the
functional coverage plus the lazy-import guard below (C-007), which is a
distinct concern from one-way-import.
"""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from specify_cli.consolidation import ordering
from specify_cli.consolidation.mission_number import bake
from specify_cli.consolidation.state import ConsolidationState

pytestmark = pytest.mark.fast


def _state(baked: bool = False) -> ConsolidationState:
    s = ConsolidationState(mission_id="01ID", mission_slug="m", target_branch="main", wp_order=["WP01"])
    s.mission_number_baked = baked
    return s


def test_lazy_imports_stay_lazy() -> None:
    """C-007/INV-7: heavy / cycle-prone deps are imported inside functions, not at module top."""
    import ast
    import inspect

    # #2600: the cluster (and its lazy imports) moved to ``mission_number.bake``;
    # ``ordering`` is still held to the same rule.
    for module in (bake, ordering):
        tree = ast.parse(inspect.getsource(module))
        top_level_modules = {node.module for node in tree.body if isinstance(node, ast.ImportFrom) and node.module}
        # These must NOT be hoisted to module top (would risk import cycles).
        assert "specify_cli.missions._read_path_resolver" not in top_level_modules
        assert not any(m.startswith("specify_cli.lanes") for m in top_level_modules)
    lazy = {node.module for node in ast.walk(ast.parse(inspect.getsource(bake))) if isinstance(node, ast.ImportFrom) and node.module}
    assert "specify_cli.missions._read_path_resolver" in lazy, "non-vacuity: the guarded lazy import lives in mission_number.bake"


# --- _already_baked ---------------------------------------------------------


def test_already_baked() -> None:
    assert bake._already_baked(_state(baked=True)) is True
    assert bake._already_baked(_state(baked=False)) is False
    assert bake._already_baked(None) is False


# --- _is_assigned_mission_number --------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    # 0 and negatives are unassigned (#4900): ``_is_assigned_mission_number``
    # delegates to the single canonical leaf definition
    # (``consolidation.mission_number.is_assigned_mission_number``), which
    # requires an integer >= 1 to match data-model.md "Mission number" and
    # the sibling ``mission_check_prerequisites`` definition. 0 and negative
    # integers are unassigned too.
    [(5, True), (0, False), (-1, False), (True, False), (False, False), (None, False), ("3", False)],
)
def test_is_assigned_mission_number(value: object, expected: bool) -> None:
    assert bake._is_assigned_mission_number(value) is expected


# --- _mark_mission_number_baked ---------------------------------------------


def test_mark_mission_number_baked_persists(tmp_path: Path) -> None:
    saved: list[ConsolidationState] = []
    state = _state(baked=False)
    with patch("specify_cli.consolidation.state.save_state", side_effect=lambda s, _r: saved.append(s)):
        bake._mark_mission_number_baked(state, tmp_path)
    assert state.mission_number_baked is True
    assert saved == [state]


def test_mark_mission_number_baked_noop_for_none(tmp_path: Path) -> None:
    # Should not raise / not attempt to save when state is None.
    bake._mark_mission_number_baked(None, tmp_path)


# --- _bake_mission_number_into_mission_branch short-circuits ----------------


def test_bake_short_circuits_when_already_baked(tmp_path: Path) -> None:
    result = bake._bake_mission_number_into_mission_branch(tmp_path, "m", "kitty/mission-m", "main", merge_state=_state(baked=True))
    assert result is None


def test_bake_short_circuits_when_not_git_repo(tmp_path: Path) -> None:
    with patch.object(bake, "_is_git_repo", return_value=False):
        result = bake._bake_mission_number_into_mission_branch(tmp_path, "m", "kitty/mission-m", "main", merge_state=_state())
    assert result is None


def test_bake_returns_none_when_target_already_assigned(tmp_path: Path) -> None:
    with (
        patch.object(bake, "_is_git_repo", return_value=True),
        patch.object(bake, "_compute_next_mission_number_or_none", return_value=None),
    ):
        result = bake._bake_mission_number_into_mission_branch(tmp_path, "m", "kitty/mission-m", "main", merge_state=_state())
    assert result is None


def test_bake_dry_run_logs_without_write(tmp_path: Path) -> None:
    with (
        patch.object(bake, "_is_git_repo", return_value=True),
        patch.object(bake, "_compute_next_mission_number_or_none", return_value=7),
        patch.object(bake, "_write_mission_number_to_branch") as write_mock,
    ):
        result = bake._bake_mission_number_into_mission_branch(tmp_path, "m", "kitty/mission-m", "main", dry_run=True, merge_state=_state())
    assert result is None
    write_mock.assert_not_called()


def test_bake_writes_and_never_marks_baked_itself_on_success(tmp_path: Path) -> None:
    """#4900: a fresh write returns the number but never marks
    ``mission_number_baked`` itself -- only the executor does, after
    target-side verification."""
    marked: list[bool] = []
    state = _state()
    with (
        patch.object(bake, "_is_git_repo", return_value=True),
        patch.object(bake, "_compute_next_mission_number_or_none", return_value=9),
        patch.object(bake, "_write_mission_number_to_branch", return_value=True),
        patch.object(bake, "_mark_mission_number_baked", side_effect=lambda *_a: marked.append(True)),
    ):
        result = bake._bake_mission_number_into_mission_branch(tmp_path, "m", "kitty/mission-m", "main", merge_state=state)
    assert result == 9
    assert marked == []


def test_bake_keeps_number_when_write_skipped(tmp_path: Path) -> None:
    """#4900: a skipped/failed mission-branch write must not discard
    the computed number -- the executor's target-tree write + read-back is the
    authority and needs it."""
    with (
        patch.object(bake, "_is_git_repo", return_value=True),
        patch.object(bake, "_compute_next_mission_number_or_none", return_value=9),
        patch.object(bake, "_write_mission_number_to_branch", return_value=False),
    ):
        result = bake._bake_mission_number_into_mission_branch(tmp_path, "m", "kitty/mission-m", "main", merge_state=_state())
    assert result == 9


def test_bake_refuses_loudly_when_no_number_can_be_determined(tmp_path: Path) -> None:
    """#4900: an unsafe slug means no number can ever be decided --
    raise the typed verification error (executor -> ``Error:`` + exit 1)
    instead of a silent ``None`` that leaves the target ``null`` with exit 0."""
    from specify_cli.consolidation.baseline import MissionNumberVerificationError

    with (
        patch.object(bake, "_is_git_repo", return_value=True),
        patch.object(bake, "_compute_next_mission_number_or_none") as compute_mock,
        pytest.raises(MissionNumberVerificationError, match="cannot determine a mission_number"),
    ):
        bake._bake_mission_number_into_mission_branch(tmp_path, "../evil", "kitty/mission-evil", "main", merge_state=_state())
    compute_mock.assert_not_called()


def test_bake_onto_target_tree_refuses_absent_meta(tmp_path: Path) -> None:
    """#4900: never fabricate a one-key stub meta.json on the target."""
    from specify_cli.consolidation.baseline import MissionNumberVerificationError

    feature_dir = tmp_path / "kitty-specs" / "m"
    feature_dir.mkdir(parents=True)
    with pytest.raises(MissionNumberVerificationError, match="target meta.json is missing"):
        bake._bake_mission_number_onto_target_tree(feature_dir, 3)
    assert not (feature_dir / "meta.json").exists()


def test_bake_onto_target_tree_writes_existing_meta(tmp_path: Path) -> None:
    import json as _json

    feature_dir = tmp_path / "kitty-specs" / "m"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(_json.dumps({"mission_slug": "m", "mission_number": None}), encoding="utf-8")
    result = bake._bake_mission_number_onto_target_tree(feature_dir, 3)
    assert result == feature_dir / "meta.json"
    written = _json.loads(result.read_text(encoding="utf-8"))
    assert written["mission_number"] == 3
    assert written["mission_slug"] == "m"


# --- _write_mission_number_to_branch: missing-branch early return -----------


def test_write_skips_when_branch_missing(tmp_path: Path) -> None:
    with patch.object(bake, "_has_branch_ref", return_value=False):
        assert bake._write_mission_number_to_branch(tmp_path, "kitty/mission-m", "m", 3, target_branch="main") is False


# --- _assign_planning_only_mission_number_if_needed -------------------------


def test_planning_only_assignment_noop_when_not_needed(tmp_path: Path) -> None:
    with patch("specify_cli.consolidation.state.needs_number_assignment", return_value=False):
        assert bake._assign_planning_only_mission_number_if_needed(tmp_path, tmp_path) is None


def test_planning_only_assignment_writes_meta(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "m"
    feature_dir.mkdir(parents=True)
    written: list[dict[str, object]] = []
    with (
        patch("specify_cli.consolidation.state.needs_number_assignment", return_value=True),
        patch.object(bake, "assign_next_mission_number", return_value=4),
        patch.object(bake, "load_meta", return_value={"mission_slug": "m"}),
        patch.object(bake, "write_meta", side_effect=lambda _d, meta, **_k: written.append(meta)),
    ):
        result = bake._assign_planning_only_mission_number_if_needed(tmp_path, feature_dir)
    assert result == 4
    assert written[0]["mission_number"] == 4


def test_planning_only_assignment_writes_meta_when_load_returns_none(tmp_path: Path) -> None:
    """load_meta returning None must still produce a fresh meta dict (the ``or {}``)."""
    feature_dir = tmp_path / "kitty-specs" / "m"
    feature_dir.mkdir(parents=True)
    written: list[dict[str, object]] = []
    with (
        patch("specify_cli.consolidation.state.needs_number_assignment", return_value=True),
        patch.object(bake, "assign_next_mission_number", return_value=2),
        patch.object(bake, "load_meta", return_value=None),
        patch.object(bake, "write_meta", side_effect=lambda _d, meta, **_k: written.append(meta)),
    ):
        result = bake._assign_planning_only_mission_number_if_needed(tmp_path, feature_dir)
    assert result == 2
    assert written[0] == {"mission_number": 2}


# --- has_dependency_info ----------------------------------------------------


def test_has_dependency_info() -> None:
    assert ordering.has_dependency_info({"WP01": ["WP02"], "WP02": []}) is True
    assert ordering.has_dependency_info({"WP01": [], "WP02": []}) is False
    assert ordering.has_dependency_info({}) is False


# --- get_merge_order --------------------------------------------------------


def _ws(wp_id: str) -> tuple[Path, str, str]:
    return (Path(f"/wt/{wp_id}"), wp_id, f"kitty/{wp_id}")


def test_get_merge_order_empty_returns_empty(tmp_path: Path) -> None:
    assert ordering.get_merge_order([], tmp_path) == []


def test_get_merge_order_no_deps_falls_back_to_numeric(tmp_path: Path) -> None:
    workspaces = [_ws("WP02"), _ws("WP01")]
    with patch.object(ordering, "build_dependency_graph", return_value={"WP01": [], "WP02": []}):
        result = ordering.get_merge_order(workspaces, tmp_path)
    assert [wp for _, wp, _ in result] == ["WP01", "WP02"]


def test_get_merge_order_topo_sorts_dependencies_first(tmp_path: Path) -> None:
    workspaces = [_ws("WP02"), _ws("WP01")]
    # WP02 depends on WP01 -> WP01 must come first.
    with patch.object(ordering, "build_dependency_graph", return_value={"WP01": [], "WP02": ["WP01"]}):
        result = ordering.get_merge_order(workspaces, tmp_path)
    assert [wp for _, wp, _ in result] == ["WP01", "WP02"]


def test_get_merge_order_raises_on_cycle(tmp_path: Path) -> None:
    workspaces = [_ws("WP01"), _ws("WP02")]
    with (
        patch.object(ordering, "build_dependency_graph", return_value={"WP01": ["WP02"], "WP02": ["WP01"]}),
        pytest.raises(ordering.MergeOrderError, match="Circular dependency"),
    ):
        ordering.get_merge_order(workspaces, tmp_path)


def test_get_merge_order_wraps_topological_value_error(tmp_path: Path) -> None:
    workspaces = [_ws("WP01")]
    with (
        patch.object(ordering, "build_dependency_graph", return_value={"WP01": ["WP02"]}),
        patch.object(ordering, "detect_cycles", return_value=[]),
        patch.object(ordering, "topological_sort", side_effect=ValueError("bad graph")),
        pytest.raises(ordering.MergeOrderError, match="bad graph"),
    ):
        ordering.get_merge_order(workspaces, tmp_path)


# --- _compute_next_mission_number_or_none -----------------------------------


def test_compute_next_falls_back_when_worktree_add_fails(tmp_path: Path) -> None:
    """git worktree add failure -> fall back to scanning main_repo (lines 286-292)."""

    def _fake_run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        if args[:3] == ["git", "worktree", "add"]:
            return CompletedProcess(args, 1, stdout="", stderr="cannot add worktree")
        return CompletedProcess(args, 0, stdout="", stderr="")

    with (
        patch("subprocess.run", side_effect=_fake_run),
        patch.object(bake, "assign_next_mission_number", return_value=11) as assign_mock,
    ):
        result = bake._compute_next_mission_number_or_none(tmp_path, "m", "main")
    assert result == 11
    # Fallback scanned main_repo, not a tmp worktree.
    assert assign_mock.call_args.args[0] == tmp_path


def test_compute_next_returns_none_when_target_already_assigned(tmp_path: Path) -> None:
    """meta.json on target already carries an integer -> no-op None (lines 299-308)."""
    import json as _json

    def _fake_run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        if args[:3] == ["git", "worktree", "add"]:
            # Materialise the scan worktree's target meta.json.
            scan_root = Path(args[4])
            specs = scan_root / "kitty-specs" / "m"
            specs.mkdir(parents=True, exist_ok=True)
            (specs / "meta.json").write_text(_json.dumps({"mission_number": 5}), encoding="utf-8")
            return CompletedProcess(args, 0, stdout="", stderr="")
        return CompletedProcess(args, 0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=_fake_run):
        result = bake._compute_next_mission_number_or_none(tmp_path, "m", "main")
    assert result is None


def test_compute_next_rejects_unsafe_mission_slug(tmp_path: Path) -> None:
    """#2037: a traversal-shaped slug aborts the entire assignment step.

    Without the ``assert_safe_path_segment`` guard, ``scan_specs /
    "../evil" / "meta.json"`` collapses to ``tmp_path / "evil" / "meta.json"``
    (escaping the intended ``kitty-specs/`` scan root) — planting an
    already-assigned ``mission_number`` there would make the function
    wrongly return ``None`` (no-op) instead of assigning a fresh number. The
    guard must fail closed before creating a worktree or assigning a number.
    """
    import json as _json

    def _fake_run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        if args[:3] == ["git", "worktree", "add"]:
            return CompletedProcess(args, 1, stdout="", stderr="cannot add worktree")
        return CompletedProcess(args, 0, stdout="", stderr="")

    escape_target = tmp_path / "evil" / "meta.json"
    escape_target.parent.mkdir(parents=True)
    escape_target.write_text(_json.dumps({"mission_number": 5}), encoding="utf-8")
    # The scan root must exist so that ``scan_specs / "../evil" / "meta.json"``
    # can actually traverse to the planted file without the guard (otherwise the
    # peek fails on ENOENT and this test would be vacuous).
    (tmp_path / "kitty-specs").mkdir()

    with (
        patch("subprocess.run", side_effect=_fake_run),
        patch.object(bake, "assign_next_mission_number", return_value=11) as assign_mock,
    ):
        result = bake._compute_next_mission_number_or_none(tmp_path, "../evil", "main")

    assert result is None
    assign_mock.assert_not_called()


def test_write_rejects_unsafe_mission_slug_before_git_or_file_io(tmp_path: Path) -> None:
    """#2037: the write seam independently confines the composed meta path."""
    with (
        patch.object(bake, "_has_branch_ref") as branch_mock,
        patch("subprocess.run") as run_mock,
        patch("specify_cli.missions._read_path_resolver.compose_meta_json_path") as compose_mock,
    ):
        result = bake._write_mission_number_to_branch(tmp_path, "kitty/mission-m", "/outside-repo", 99, target_branch="main")

    assert result is False
    branch_mock.assert_not_called()
    run_mock.assert_not_called()
    compose_mock.assert_not_called()


# --- _write_mission_number_to_branch: error/cleanup branches ----------------


def test_write_skips_when_worktree_add_fails(tmp_path: Path) -> None:
    """git worktree add failure on the write path -> False (lines 357-363)."""

    def _fake_run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        if args[:3] == ["git", "worktree", "add"]:
            return CompletedProcess(args, 1, stdout="", stderr="add failed")
        return CompletedProcess(args, 0, stdout="", stderr="")

    with (
        patch.object(bake, "_has_branch_ref", return_value=True),
        patch("subprocess.run", side_effect=_fake_run),
    ):
        assert bake._write_mission_number_to_branch(tmp_path, "kitty/mission-m", "m", 3, target_branch="main") is False


def test_write_skips_when_meta_missing(tmp_path: Path) -> None:
    """meta.json absent on the mission branch worktree -> False (lines 385-391)."""

    def _fake_run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(args, 0, stdout="", stderr="")

    with (
        patch.object(bake, "_has_branch_ref", return_value=True),
        patch.object(bake, "path_is_under_worktrees", return_value=False),
        patch("subprocess.run", side_effect=_fake_run),
    ):
        # The composed meta path under the tmp scan worktree never exists.
        assert bake._write_mission_number_to_branch(tmp_path, "kitty/mission-m", "m", 3, target_branch="main") is False


def test_write_refuses_when_meta_path_under_worktrees(tmp_path: Path) -> None:
    """Resolved meta path under .worktrees/ -> refuse to bake (lines 377-384)."""

    def _fake_run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(args, 0, stdout="", stderr="")

    with (
        patch.object(bake, "_has_branch_ref", return_value=True),
        patch.object(bake, "path_is_under_worktrees", return_value=True),
        patch("subprocess.run", side_effect=_fake_run),
        patch(
            "specify_cli.missions._read_path_resolver.compose_meta_json_path",
            side_effect=lambda wt, slug: wt / ".worktrees" / "m-coord" / "meta.json",
        ),
    ):
        assert bake._write_mission_number_to_branch(tmp_path, "kitty/mission-m", "m", 3, target_branch="main") is False


def test_write_refuses_when_meta_not_a_dict(tmp_path: Path) -> None:
    """meta.json is a JSON list, not an object -> refuse (lines 395-399)."""
    import json as _json

    def _fake_run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        if args[:3] == ["git", "worktree", "add"]:
            scan_root = Path(args[4])
            specs = scan_root / "kitty-specs" / "m"
            specs.mkdir(parents=True, exist_ok=True)
            (specs / "meta.json").write_text(_json.dumps(["not", "a", "dict"]), encoding="utf-8")
            return CompletedProcess(args, 0, stdout="", stderr="")
        return CompletedProcess(args, 0, stdout="", stderr="")

    with (
        patch.object(bake, "_has_branch_ref", return_value=True),
        patch.object(bake, "path_is_under_worktrees", return_value=False),
        patch("subprocess.run", side_effect=_fake_run),
        patch(
            "specify_cli.missions._read_path_resolver.compose_meta_json_path",
            side_effect=lambda wt, slug: wt / "kitty-specs" / slug / "meta.json",
        ),
    ):
        assert bake._write_mission_number_to_branch(tmp_path, "kitty/mission-m", "m", 3, target_branch="main") is False


def test_write_idempotency_hit_never_marks_baked_returns_false(tmp_path: Path) -> None:
    """meta already has the exact number -> idempotency skip, no write (lines 402-414).

    #4900: this seam never marks ``mission_number_baked`` itself --
    that flag is set ONLY by the executor, after target-side verification.
    """
    import json as _json

    def _fake_run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        if args[:3] == ["git", "worktree", "add"]:
            scan_root = Path(args[4])
            specs = scan_root / "kitty-specs" / "m"
            specs.mkdir(parents=True, exist_ok=True)
            (specs / "meta.json").write_text(_json.dumps({"mission_number": 9}), encoding="utf-8")
            return CompletedProcess(args, 0, stdout="", stderr="")
        return CompletedProcess(args, 0, stdout="", stderr="")

    marked: list[bool] = []
    with (
        patch.object(bake, "_has_branch_ref", return_value=True),
        patch.object(bake, "path_is_under_worktrees", return_value=False),
        patch("subprocess.run", side_effect=_fake_run),
        patch.object(bake, "_mark_mission_number_baked", side_effect=lambda *_a: marked.append(True)),
        patch(
            "specify_cli.missions._read_path_resolver.compose_meta_json_path",
            side_effect=lambda wt, slug: wt / "kitty-specs" / slug / "meta.json",
        ),
    ):
        result = bake._write_mission_number_to_branch(tmp_path, "kitty/mission-m", "m", 9, target_branch="main")
    assert result is False
    assert marked == [], "the idempotency-hit seam must never mark mission_number_baked (#4900)"


def test_write_commit_argv_names_only_meta(tmp_path: Path) -> None:
    """#5443 / C-005: the temp-worktree commit is ``commit --only ... -- <rel_meta>``.

    Restoring the bare ``git commit -m`` (or a pathspec-less ``git add``) fails here.
    """
    import json as _json

    recorded: list[list[str]] = []

    def _fake_run(args: list[str], **kwargs: object) -> CompletedProcess[str]:
        recorded.append(list(args))
        if args[:3] == ["git", "worktree", "add"]:
            specs = Path(args[4]) / "kitty-specs" / "m"
            specs.mkdir(parents=True, exist_ok=True)
            (specs / "meta.json").write_text(_json.dumps({"mission_number": None}), encoding="utf-8")
        return CompletedProcess(args, 0, stdout="abc123\n", stderr="")

    with (
        patch.object(bake, "_has_branch_ref", return_value=True),
        patch.object(bake, "path_is_under_worktrees", return_value=False),
        patch.object(bake, "advance_branch_ref") as advance_mock,
        patch("subprocess.run", side_effect=_fake_run),
        patch(
            "specify_cli.missions._read_path_resolver.compose_meta_json_path",
            side_effect=lambda wt, slug: wt / "kitty-specs" / slug / "meta.json",
        ),
    ):
        result = bake._write_mission_number_to_branch(tmp_path, "kitty/mission-m", "m", 4, target_branch="main")

    assert result is True
    advance_mock.assert_called_once()
    commits = [argv for argv in recorded if "commit" in argv]
    assert len(commits) == 1
    assert "--only" in commits[0]
    assert commits[0][-2:] == ["--", "kitty-specs/m/meta.json"]
    assert not [argv for argv in recorded if argv[:2] == ["git", "add"] and "--" not in argv]
