"""Regression tests for #2570.1 (dirty-tree guard) + #2816 claim byte-stability.

**Post-#2816 (WP04) cutover.** ``spec-kitty implement WP##`` no longer writes
``shell_pid``/``shell_pid_created_at`` into ``tasks/WP##.md`` at claim time — the
frontmatter dual-write mirror was removed in the unconditional reader/writer
cutover, so the claim rides the event log / ``policy_metadata`` sidecar only and
the WP prompt file is **byte-identical across the claim** (NFR-003 / SC-004).

Section A (unchanged) drives the pure dirty-tree-guard cores
(``_is_runtime_frontmatter_only_wp_diff``, and -- since WP14 / IC-07d merged
``_drop_runtime_frontmatter_only_wp`` and its vcs-lock structural twin into
one predicate -- ``_is_self_write_only_diff``) directly against a real git
repo. That guard is still load-bearing: a
runtime-field-only WP##.md diff from ANY writer (e.g. ``move-task``, or a
migration repair) is excluded from the guard ONLY when every differing
frontmatter key is in the ONE canonical
:data:`specify_cli.frontmatter.WP_RUNTIME_FIELDS` source AND the markdown body
is byte-identical (K-1/NFR-005: a body edit, or any non-runtime frontmatter key
change, must still block). The default ``auto_commit=True`` path is a
byte-identical no-op (NFR-001).

Section B runs the REAL claim phases against a real git repository (real claim
events, nothing in the implement command family patched) across N sequential
lanes and asserts the post-cutover invariant directly: every ``WP##.md`` prompt
file is **byte-identical** before and after its claim (0 runtime bytes written),
so the claim itself never dirties a prompt file -- and, since #3471 exempts each
claim's own status append from the next claim's planning-artifact guard, no
inter-allocation commit is ever needed.
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from specify_cli.cli.commands.implement_cores import _is_runtime_frontmatter_only_wp_diff, _is_self_write_only_diff, resolve_planning_artifact_staging
from specify_cli.frontmatter import WP_RUNTIME_FIELDS
from specify_cli.cli.commands import implement_phases
from specify_cli.cli.commands.implement_phases import AllocationResult
from specify_cli.lanes.implement_support import LaneWorkspaceResult
from specify_cli.status.reducer import wp_snapshot_state
from tests.specify_cli.cli.commands.test_implement_characterization import (
    MISSION_ID,
    SLUG,
    activate_repo,
    build_mission,
    git,
    init_repo,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_MISSION_SLUG = "runtime-frontmatter-claim-demo"

_BODY = "# WP01\n\nDo the thing.\n"


# ---------------------------------------------------------------------------
# Section A helpers: a single committed WP prompt + direct core calls.
# ---------------------------------------------------------------------------


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True, text=True)


def _base_wp_frontmatter() -> dict[str, Any]:
    """A realistic claimed-and-workspace-created WP01 snapshot -- the shape
    ``spec-kitty implement`` leaves once BOTH the workspace-creation write
    (``base_branch``/``base_commit``/``planning_base_branch``) and the
    claim-time write (``shell_pid``/``shell_pid_created_at``) have landed."""
    return {
        "work_package_id": "WP01",
        "title": "WP01 root work",
        "dependencies": [],
        "requirement_refs": ["FR-001"],
        "planning_base_branch": "feat/demo",
        "merge_target_branch": "feat/demo",
        "base_branch": "kitty/mission-demo",
        "base_commit": "a" * 40,
        "created_at": "2026-07-12T00:00:00Z",
        "subtasks": ["T001"],
        "phase": "planned",
        "agent": "claude",
        "shell_pid": "424242",
        "shell_pid_created_at": "2026-07-12T00:00:01+00:00",
    }


def _render_wp(frontmatter: dict[str, Any], body: str = _BODY) -> str:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=2, offset=0)
    buffer = io.StringIO()
    buffer.write("---\n")
    yaml.dump(frontmatter, buffer)
    buffer.write("---\n")
    buffer.write(body)
    return buffer.getvalue()


def _init_repo_with_wp(tmp_path: Path, frontmatter: dict[str, Any], body: str = _BODY) -> tuple[Path, str]:
    """Seed a real git repo with a single committed
    ``kitty-specs/<mission>/tasks/WP01-plan.md`` and return ``(path, repo-rel)``."""
    tasks_dir = tmp_path / "kitty-specs" / _MISSION_SLUG / "tasks"
    tasks_dir.mkdir(parents=True)
    wp_path = tasks_dir / "WP01-plan.md"
    wp_path.write_text(_render_wp(frontmatter, body), encoding="utf-8")
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test Runner")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "seed WP01")
    return wp_path, wp_path.relative_to(tmp_path).as_posix()


# ---------------------------------------------------------------------------
# Section A: T003 -- every runtime field, dropped when it is the ONLY diff.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", sorted(WP_RUNTIME_FIELDS))
def test_drop_helper_drops_single_runtime_field_change(tmp_path: Path, field: str) -> None:
    """T003: a WP file whose ONLY diff vs the placement ref is a single runtime
    field is dropped from the uncommitted-artifact set (no block)."""
    base = _base_wp_frontmatter()
    wp_path, repo_rel = _init_repo_with_wp(tmp_path, base)
    working = dict(base)
    working[field] = f"{base[field]}-changed"
    wp_path.write_text(_render_wp(working), encoding="utf-8")

    dropped = _is_self_write_only_diff(tmp_path, repo_rel, None)

    assert dropped is True, f"a runtime-only change to {field!r} must be dropped"


def test_drop_helper_drops_multiple_runtime_fields_changed_together(tmp_path: Path) -> None:
    """All 5 runtime fields changing at once (the realistic
    claim-then-workspace-creation shape) is still runtime-only."""
    base = _base_wp_frontmatter()
    wp_path, repo_rel = _init_repo_with_wp(tmp_path, base)
    working = {key: (f"{value}-changed" if key in WP_RUNTIME_FIELDS else value) for key, value in base.items()}
    wp_path.write_text(_render_wp(working), encoding="utf-8")

    assert _is_self_write_only_diff(tmp_path, repo_rel, None) is True


def test_ignores_non_wp_filenames(tmp_path: Path) -> None:
    """The runtime-frontmatter leg is scoped strictly to ``WP##[-slug].md``
    paths -- a path that is neither ``meta.json`` (the sibling vcs-lock leg)
    nor WP##.md-shaped is never dropped by this predicate, even if it does
    not exist on disk (the defensive existence check short-circuits first)."""
    assert _is_self_write_only_diff(tmp_path, "kitty-specs/demo/tasks.md", None) is False


# ---------------------------------------------------------------------------
# Section A: T004 -- true positives preserved + auto_commit=True no-op.
# ---------------------------------------------------------------------------


def test_body_change_alongside_runtime_field_still_blocks(tmp_path: Path) -> None:
    """K-1/NFR-005 load-bearing true positive: a markdown BODY edit, even
    alongside a runtime-field change, must still block -- proving the helper
    asserts body-byte-identity and does not drop on the frontmatter-diff
    being a runtime-field subset alone. Without the body check this test goes
    RED (the helper would wrongly drop the entry)."""
    base = _base_wp_frontmatter()
    wp_path, repo_rel = _init_repo_with_wp(tmp_path, base)
    working = dict(base)
    working["shell_pid"] = "999999"
    wp_path.write_text(
        _render_wp(working, _BODY + "\nAn implementer edited the body too.\n"),
        encoding="utf-8",
    )

    dropped = _is_self_write_only_diff(tmp_path, repo_rel, None)

    assert dropped is False, "a body edit must still block even alongside a runtime-only frontmatter change"


def test_non_runtime_frontmatter_change_still_blocks(tmp_path: Path) -> None:
    """A non-runtime frontmatter key change (here ``title``) must still block,
    even with the body left untouched -- the exclusion is strictly
    runtime-field-only, never a blanket WP##.md bypass."""
    base = _base_wp_frontmatter()
    wp_path, repo_rel = _init_repo_with_wp(tmp_path, base)
    working = dict(base)
    working["title"] = "WP01 retitled by an operator"
    wp_path.write_text(_render_wp(working), encoding="utf-8")

    dropped = _is_self_write_only_diff(tmp_path, repo_rel, None)

    assert dropped is False, "a non-runtime frontmatter key change must still block"


def test_auto_commit_true_is_byte_identical_noop(tmp_path: Path) -> None:
    """NFR-001: under ``auto_commit=True`` the exclusion is a byte-identical
    no-op -- a WP##.md path stays in the staging plan's commit set even when
    its only diff is runtime fields, so the default path's commit semantics
    never change.

    WP14 / IC-07d: the ``auto_commit`` gate moved from the retired
    ``_drop_runtime_frontmatter_only_wp`` helper itself to its caller
    (:func:`resolve_planning_artifact_staging` applies :func:`_drop_if` only
    when ``not auto_commit``), so this is now exercised at the staging-plan
    level rather than the bare predicate.
    """
    base = _base_wp_frontmatter()
    wp_path, repo_rel = _init_repo_with_wp(tmp_path, base)
    working = dict(base)
    working["shell_pid"] = "999999"
    wp_path.write_text(_render_wp(working), encoding="utf-8")

    plan = resolve_planning_artifact_staging(tmp_path, tmp_path / "kitty-specs" / _MISSION_SLUG, None, [], auto_commit=True)

    assert repo_rel in plan.files_to_commit, "auto_commit=True must be a byte-identical no-op (NFR-001)"


# ---------------------------------------------------------------------------
# Section A: pure-function truth table for _is_runtime_frontmatter_only_wp_diff.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("committed_front", "working_front", "committed_tail", "working_tail", "expected"),
    [
        # Runtime-field-only frontmatter diff, body unchanged -> runtime-only.
        ({"shell_pid": "1"}, {"shell_pid": "2"}, "\nbody\n", "\nbody\n", True),
        # No diff at all -> nothing to exclude.
        ({"shell_pid": "1"}, {"shell_pid": "1"}, "\nbody\n", "\nbody\n", False),
        # A non-runtime key changed -> NOT runtime-only.
        ({"title": "a"}, {"title": "b"}, "\nbody\n", "\nbody\n", False),
        # Runtime field changed AND body changed -> NOT runtime-only (K-1).
        ({"shell_pid": "1"}, {"shell_pid": "2"}, "\nbody\n", "\nbody changed\n", False),
        # Committed frontmatter unparseable -> never runtime-only.
        (None, {"shell_pid": "2"}, "\nbody\n", "\nbody\n", False),
        # Working frontmatter unparseable -> never runtime-only.
        ({"shell_pid": "1"}, None, "\nbody\n", "\nbody\n", False),
        # Multiple runtime fields changed together -> still runtime-only.
        (
            {"shell_pid": "1", "base_branch": "main"},
            {"shell_pid": "2", "base_branch": "kitty/mission-x"},
            "\nbody\n",
            "\nbody\n",
            True,
        ),
    ],
)
def test_is_runtime_frontmatter_only_wp_diff_truth_table(
    committed_front: dict[str, Any] | None,
    working_front: dict[str, Any] | None,
    committed_tail: str,
    working_tail: str,
    expected: bool,
) -> None:
    assert _is_runtime_frontmatter_only_wp_diff(committed_front, working_front, committed_tail, working_tail) is expected


# ---------------------------------------------------------------------------
# Section B: T003 SC -- N sequential claims, zero WP prompt-file bytes.
# ---------------------------------------------------------------------------


def _lane_allocation(repo: Path, lane_id: str) -> AllocationResult:
    """The ``allocate`` phase value for a lane workspace (the allocation itself is not under test)."""
    return AllocationResult(
        result=LaneWorkspaceResult(
            workspace_path=repo / ".worktrees" / f"{SLUG}-{lane_id}",
            branch_name=f"kitty/mission-{SLUG}-{lane_id}",
            workspace_name=f"{SLUG}-{lane_id}",
            lane_id=lane_id,
            mission_branch=f"kitty/mission-{SLUG}",
            is_reuse=False,
            vcs_backend_value="git",
            execution_mode="worktree",
            resolution_kind="lane_workspace",
        ),
        effective_base=None,
    )


def test_sequential_n_lane_claims_write_zero_wp_file_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-004 / NFR-003 (#2816 cutover): N sequential dependency-free root claims
    under ``auto_commit=False`` each write **0 bytes** to their WP prompt file.

    Post-cutover the claim no longer self-writes ``shell_pid`` into
    ``tasks/WP##.md`` (the dual-write mirror was removed): the claim rides the
    event log only. This test runs the REAL claim phases (``claim_preflight``,
    ``commit_planning_artifacts``, ``record_claim``, ``commit_claim``) for N WPs in
    sequence against a real git repository, with no ``git commit`` between
    iterations, and asserts that every claim passed the planning-artifact guard
    (#3471: no inter-allocation commit is ever needed) and landed in the event log
    while every prompt file stayed byte-identical.
    (The workspace allocation's own ``base_branch``/``base_commit`` stamp is a
    separate, workspace-creation write and is not part of the claim.)
    """
    repo = init_repo(tmp_path / "repo")
    activate_repo(repo, monkeypatch, tmp_path)
    wp_ids = ["WP01", "WP02", "WP03"]
    lane_ids = [f"lane-{chr(ord('a') + index)}" for index in range(len(wp_ids))]
    mission = build_mission(
        repo,
        SLUG,
        MISSION_ID,
        wps={wp_id: ("code_change", []) for wp_id in wp_ids},
        layout=tuple((lane_id, (wp_id,), ()) for lane_id, wp_id in zip(lane_ids, wp_ids, strict=True)),
    )
    tasks_dir = mission.feature_dir / "tasks"
    before = {wp_id: (tasks_dir / f"{wp_id}-test.md").read_bytes() for wp_id in wp_ids}

    for wp_id, lane_id in zip(wp_ids, lane_ids, strict=True):
        ctx = implement_phases.detect_context(SLUG, wp_id, repo, False, json_mode=False)
        preflight = implement_phases.claim_preflight(ctx, wp_id)
        # #3471: the previous claims' uncommitted status appends do not block this one.
        implement_phases.commit_planning_artifacts(ctx, wp_id, preflight)
        status = implement_phases.record_claim(ctx, wp_id, "tester", _lane_allocation(repo, lane_id), "worktree")
        implement_phases.commit_claim(ctx, wp_id, status)

    # Every claim really landed: each WP is in_progress in the real event log.
    for wp_id in wp_ids:
        assert (wp_snapshot_state(mission.feature_dir, wp_id) or {}).get("lane") == "in_progress"

    # Byte-stability (SC-004): the claim wrote 0 runtime bytes to any WP prompt
    # file — every WP##.md is byte-identical to its pre-claim content, so the
    # working tree carries no WP##.md change at all.
    for wp_id in wp_ids:
        after = (tasks_dir / f"{wp_id}-test.md").read_bytes()
        assert after == before[wp_id], f"{wp_id}'s prompt file must be byte-identical across its claim (0 runtime bytes)"

    status_lines = git(repo, "status", "--porcelain")
    for wp_id in wp_ids:
        assert f"{wp_id}-test.md" not in status_lines, f"{wp_id}'s prompt file must stay unmodified after a byte-stable claim"
