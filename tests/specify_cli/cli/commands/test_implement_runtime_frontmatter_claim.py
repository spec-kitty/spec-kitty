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

Section B drives the REAL claim surface (``implement()``) across N sequential
lanes and asserts the post-cutover invariant directly: every ``WP##.md`` prompt
file is **byte-identical** before and after its claim (0 runtime bytes written),
so no inter-allocation commit is ever needed.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer
from ruamel.yaml import YAML

from specify_cli.cli.commands.implement import implement
from specify_cli.cli.commands.implement_cores import _is_runtime_frontmatter_only_wp_diff, _is_self_write_only_diff, resolve_planning_artifact_staging
from specify_cli.frontmatter import WP_RUNTIME_FIELDS
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json

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

    assert dropped is False, (
        "a body edit must still block even alongside a runtime-only frontmatter change"
    )


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

    plan = resolve_planning_artifact_staging(
        tmp_path, tmp_path / "kitty-specs" / _MISSION_SLUG, None, [], auto_commit=True
    )

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
    assert (
        _is_runtime_frontmatter_only_wp_diff(committed_front, working_front, committed_tail, working_tail)
        is expected
    )


# ---------------------------------------------------------------------------
# Section B: T003 SC -- N sequential lanes, zero inter-allocation commits.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests do not stage a charter; bypass the preflight gate so the
    claim reaches the dirty-tree guard under test rather than failing earlier
    with ``charter_source missing``."""
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    result = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_args, **_kwargs: result,
    )


def _write_meta(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": feature_dir.name,
                "slug": feature_dir.name,
                "friendly_name": feature_dir.name,
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-07-12T00:00:00Z",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_lanes(feature_dir: Path, wp_ids: list[str]) -> None:
    lanes = [
        ExecutionLane(
            lane_id=f"lane-{chr(ord('a') + index)}",
            wp_ids=(wp_id,),
            write_scope=(f"src/{wp_id.lower()}/**",),
            predicted_surfaces=("runtime",),
            depends_on_lanes=(),
            parallel_group=0,
        )
        for index, wp_id in enumerate(wp_ids)
    ]
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=feature_dir.name,
            mission_id=f"mission-{feature_dir.name}",
            mission_branch=f"kitty/mission-{feature_dir.name}",
            target_branch="main",
            lanes=lanes,
            computed_at="2026-07-12T00:00:00Z",
            computed_from="test",
        ),
    )


def _write_wp_prompt(tasks_dir: Path, wp_id: str, owned_glob: str) -> None:
    (tasks_dir / f"{wp_id}-plan.md").write_text(
        "---\n"
        f"work_package_id: {wp_id}\n"
        f"title: {wp_id} root work\n"
        "dependencies: []\n"
        "execution_mode: code_change\n"
        "owned_files:\n"
        f"  - {owned_glob}\n"
        f"authoritative_surface: {owned_glob.rstrip('*')}\n"
        "---\n"
        f"# {wp_id}\n",
        encoding="utf-8",
    )


def _seed_event(mission_slug: str, wp_id: str, event_suffix: str) -> dict[str, Any]:
    return {
        "actor": "seed",
        "at": "2026-07-12T00:00:00+00:00",
        "event_id": f"01HXYZ0123456789ABCDEFG{event_suffix}",
        "evidence": None,
        "execution_mode": "worktree",
        "force": False,
        "from_lane": "genesis",
        "mission_slug": mission_slug,
        "reason": "seed",
        "review_ref": None,
        "to_lane": "planned",
        "wp_id": wp_id,
    }


def _build_multi_wp_mission_repo(tmp_path: Path, wp_ids: list[str]) -> Path:
    """Seed a realistic N-root-WP mission in a real git repo, committed on
    ``main``. Every WP is a dependency-free root, seeded into ``planned`` (as
    ``finalize-tasks`` does), each on its own lane."""
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_meta(feature_dir)
    _write_lanes(feature_dir, wp_ids)
    (feature_dir / "spec.md").write_text(
        "# Spec\n\nDeliver independent root work packages.\n",
        encoding="utf-8",
    )
    for index, wp_id in enumerate(wp_ids):
        _write_wp_prompt(tasks_dir, wp_id, f"src/{chr(ord('a') + index)}/**")
    events = "".join(
        json.dumps(_seed_event(_MISSION_SLUG, wp_id, f"S{index:02d}"), sort_keys=True) + "\n"
        for index, wp_id in enumerate(wp_ids)
    )
    (feature_dir / "status.events.jsonl").write_text(events, encoding="utf-8")

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test Runner")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "seed mission")
    return feature_dir


def _workspace_mock(feature_dir: Path, lane_id: str) -> MagicMock:
    return MagicMock(
        workspace_path=feature_dir.parent.parent / ".worktrees" / f"{feature_dir.name}-{lane_id}",
        branch_name=f"kitty/mission-{feature_dir.name}-{lane_id}",
        lane_id=lane_id,
        mission_branch=f"kitty/mission-{feature_dir.name}",
        is_reuse=False,
    )


@contextmanager
def _claim_through_guard(tmp_path: Path, feature_dir: Path, lane_id: str) -> Iterator[MagicMock]:
    """Drive the REAL dirty-tree guard via ``implement()`` while patching only
    the post-guard worktree allocation and status emission (mirrors the proven
    pattern in ``test_implement_vcs_lock_claim.py``)."""
    create_mock = MagicMock(return_value=_workspace_mock(feature_dir, lane_id))
    status_mock = MagicMock(return_value=MagicMock(status_changed=False))
    with (
        patch("specify_cli.cli.commands.implement.find_repo_root", return_value=tmp_path),
        patch(
            "specify_cli.cli.commands.implement.detect_feature_context",
            return_value=(None, feature_dir.name),
        ),
        patch(
            "specify_cli.workspace.context.resolve_mission_target_branch",
            return_value="main",
        ),
        patch("specify_cli.cli.commands.implement.create_lane_workspace", create_mock),
        patch("specify_cli.cli.commands.implement.start_implementation_status", status_mock),
    ):
        yield create_mock


def test_sequential_n_lane_allocation_writes_zero_wp_file_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-004 / NFR-003 (#2816 cutover): N sequential dependency-free root claims
    under ``auto_commit=False`` each write **0 bytes** to their WP prompt file.

    Post-cutover the claim no longer self-writes ``shell_pid`` into
    ``tasks/WP##.md`` (the dual-write mirror was removed), so every ``WP##.md`` is
    byte-identical across its claim and NO inter-allocation commit is ever needed
    — the dirty-tree guard has nothing to drop. This test performs no ``git
    commit`` between iterations and asserts the prompt files never change.
    """
    wp_ids = ["WP01", "WP02", "WP03"]
    feature_dir = _build_multi_wp_mission_repo(tmp_path, wp_ids)
    monkeypatch.chdir(tmp_path)
    tasks_dir = feature_dir / "tasks"
    before = {wp_id: (tasks_dir / f"{wp_id}-plan.md").read_bytes() for wp_id in wp_ids}

    for index, wp_id in enumerate(wp_ids):
        lane_id = f"lane-{chr(ord('a') + index)}"
        with (
            _claim_through_guard(tmp_path, feature_dir, lane_id) as create_mock,
            contextlib.suppress(typer.Exit),
        ):
            implement(wp_id, mission=feature_dir.name, auto_commit=False, recover=False)

        assert create_mock.called, (
            f"{wp_id} (lane {index + 1} of {len(wp_ids)}) was blocked before "
            "reaching workspace allocation"
        )

    # Byte-stability (SC-004): the claim wrote 0 runtime bytes to any WP prompt
    # file — every WP##.md is byte-identical to its pre-claim content, so the
    # working tree carries no WP##.md change at all.
    for wp_id in wp_ids:
        after = (tasks_dir / f"{wp_id}-plan.md").read_bytes()
        assert after == before[wp_id], (
            f"{wp_id}'s prompt file must be byte-identical across its claim (0 runtime bytes)"
        )

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    for wp_id in wp_ids:
        assert f"{wp_id}-plan.md" not in status, (
            f"{wp_id}'s prompt file must stay unmodified after a byte-stable claim"
        )
