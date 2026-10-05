"""Seam tests for the implement phase sequence and its presentation (implement-degod WP09, SC-005).

Every test calls a phase or a presentation function directly with real values (real files, a real
git fixture, real ``LaneWorkspaceResult`` / ``StepTracker`` objects) and patches nothing in the
implement command family. The phase-order test observes the real calls with a profile hook instead
of substituting spies, so it adds no patch site either.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from types import FrameType
from typing import Any

import pytest
import typer

from specify_cli.charter_runtime.preflight.ambient_warning import _reset_surfaced_for_testing
from specify_cli.cli import StepTracker
from specify_cli.cli.commands import implement_phases
from specify_cli.cli.commands.implement import (
    _build_implement_json_payload,
    _print_workspace_ready_banner,
    _report_workspace_created,
)
from specify_cli.cli.commands.implement_phases import ImplementContext, _ensure_vcs_in_meta, detect_feature_context
from specify_cli.cli.console import console
from specify_cli.lanes.implement_support import LaneWorkspaceResult
from specify_cli.workspace.context import ResolvedWorkspace
from tests.specify_cli.cli.commands.test_implement_characterization import (
    ARGS,
    LANE_BRANCH,
    LANE_WORKTREE,
    MISSION_ID,
    SLUG,
    activate_repo,
    build_mission,
    implement_cli,
    init_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_RULE = "=" * 72
_PHASES = (
    "detect_context",
    "claim_preflight",
    "commit_planning_artifacts",
    "run_bulk_edit_gate",
    "build_operational_context",
    "select_workspace",
    "allocate",
    "record_claim",
    "commit_claim",
)
BULK_SPEC = "# Spec\nA codemod to rename across the repo: bulk edit with find-and-replace.\n"
BULK_MATCHED = "Matched: 'rename across' (3pt), 'bulk edit' (3pt), 'codemod' (3pt), 'find-and-replace' (3pt)"


@pytest.fixture(autouse=True)
def _fresh_charter_warning() -> Iterator[None]:
    """The charter preflight warning is shown once per process; re-arm it around each test."""
    _reset_surfaced_for_testing()
    yield
    _reset_surfaced_for_testing()


@pytest.fixture(autouse=True)
def _wide_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render without wrapping so captured lines compare whole."""
    monkeypatch.setenv("COLUMNS", "240")


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = init_repo(tmp_path / "repo")
    activate_repo(root, monkeypatch, tmp_path)
    return root


def _lines(text: str) -> list[str]:
    return [line.rstrip() for line in _ANSI.sub("", text).splitlines()]


def _flat(text: str) -> str:
    return " ".join(re.sub(r"[│├└─╭╮╰╯●○]", " ", _ANSI.sub("", text)).split())


# ---------------------------------------------------------------------------
# Phase order
# ---------------------------------------------------------------------------


def test_phases_run_in_the_documented_order(repo: Path) -> None:
    """A healthy claim calls every phase once, in order (observed, not spied).

    Planted break (proven red): swap the ``run_bulk_edit_gate`` and ``build_operational_context``
    calls in ``implement()``.
    """
    build_mission(repo, SLUG, MISSION_ID)
    codes = {getattr(implement_phases, name).__code__: name for name in _PHASES}
    calls: list[str] = []

    def _observe(frame: FrameType, event: str, _arg: Any) -> None:
        if event == "call" and frame.f_code in codes:
            calls.append(codes[frame.f_code])

    previous = sys.getprofile()
    sys.setprofile(_observe)
    try:
        result = implement_cli(*ARGS)
    finally:
        sys.setprofile(previous)

    assert result.exit_code == 0, result.output
    assert calls == list(_PHASES)


# ---------------------------------------------------------------------------
# run_bulk_edit_gate: every verdict
# ---------------------------------------------------------------------------


def _bulk_context(tmp_path: Path, *, meta: dict[str, object], spec: str | None, owned: str = "src/**") -> ImplementContext:
    feature_dir = tmp_path / "kitty-specs" / SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if spec is not None:
        (feature_dir / "spec.md").write_text(spec, encoding="utf-8")
    wp_file = feature_dir / "tasks" / "WP01-test.md"
    wp_file.write_text(f"---\nwork_package_id: WP01\ntitle: WP01\ndependencies: []\nowned_files:\n- {owned}\nsubtasks: []\n---\n\nBody.\n", encoding="utf-8")
    return ImplementContext(tmp_path, False, SLUG, feature_dir, wp_file, [])


def test_bulk_edit_gate_passes_silently_for_an_ordinary_mission(tmp_path: Path) -> None:
    ctx = _bulk_context(tmp_path, meta={"mission_slug": SLUG}, spec="# Spec\nAdd a flag.\n")

    with console.capture() as capture:
        implement_phases.run_bulk_edit_gate(ctx, "WP01", acknowledge_not_bulk_edit=False)

    assert _flat(capture.get()) == ""


def test_bulk_edit_gate_refuses_a_bulk_edit_mission_without_an_occurrence_map(tmp_path: Path) -> None:
    ctx = _bulk_context(tmp_path, meta={"mission_slug": SLUG, "change_mode": "bulk_edit"}, spec=None)

    with console.capture() as capture, pytest.raises(typer.Exit) as excinfo:
        implement_phases.run_bulk_edit_gate(ctx, "WP01", acknowledge_not_bulk_edit=False)

    assert excinfo.value.exit_code == 1
    assert "Occurrence map required for bulk_edit missions." in _flat(capture.get())


def test_bulk_edit_gate_lets_a_bulk_edit_mission_with_a_valid_map_skip_the_inference(tmp_path: Path) -> None:
    ctx = _bulk_context(tmp_path, meta={"mission_slug": SLUG, "change_mode": "bulk_edit"}, spec=BULK_SPEC)
    (ctx.feature_dir / "occurrence_map.yaml").write_text(
        "target:\n  term: old\n  replacement: new\n  operation: rename\n"
        "categories:\n  code_symbols:\n    action: rename\n  import_paths:\n    action: rename\n"
        "  filesystem_paths:\n    action: rename\n  serialized_keys:\n    action: do_not_change\n"
        "  cli_commands:\n    action: rename\n  user_facing_strings:\n    action: rename\n"
        "  tests_fixtures:\n    action: rename\n  logs_telemetry:\n    action: do_not_change\n",
        encoding="utf-8",
    )

    with console.capture() as capture:
        implement_phases.run_bulk_edit_gate(ctx, "WP01", acknowledge_not_bulk_edit=False)

    assert "Bulk Edit Inference" not in _flat(capture.get())


def test_bulk_edit_inference_is_informational_for_the_wp_that_owns_the_occurrence_map(tmp_path: Path) -> None:
    ctx = _bulk_context(tmp_path, meta={"mission_slug": SLUG}, spec=BULK_SPEC, owned=f"kitty-specs/{SLUG}/occurrence_map.yaml")

    with console.capture() as capture:
        implement_phases.run_bulk_edit_gate(ctx, "WP01", acknowledge_not_bulk_edit=False)

    text = _flat(capture.get())
    assert "Bulk Edit Inference Informational" in text
    assert "but WP01 owns the occurrence-map planning artifact." in text
    assert BULK_MATCHED in text
    assert "Continuing without --acknowledge-not-bulk-edit for this planning WP." in text


def test_unacknowledged_bulk_edit_inference_blocks_with_a_warning_panel(tmp_path: Path) -> None:
    ctx = _bulk_context(tmp_path, meta={"mission_slug": SLUG}, spec=BULK_SPEC)

    with console.capture() as capture, pytest.raises(typer.Exit) as excinfo:
        implement_phases.run_bulk_edit_gate(ctx, "WP01", acknowledge_not_bulk_edit=False)

    assert excinfo.value.exit_code == 1
    text = _flat(capture.get())
    assert "Bulk Edit Inference Warning" in text
    assert BULK_MATCHED in text
    assert "If this IS a bulk edit, set change_mode to 'bulk_edit' in meta.json." in text


def test_acknowledged_bulk_edit_inference_passes_silently(tmp_path: Path) -> None:
    ctx = _bulk_context(tmp_path, meta={"mission_slug": SLUG}, spec=BULK_SPEC)

    with console.capture() as capture:
        implement_phases.run_bulk_edit_gate(ctx, "WP01", acknowledge_not_bulk_edit=True)

    assert _flat(capture.get()) == ""


# ---------------------------------------------------------------------------
# build_operational_context: the require_active_role path
# ---------------------------------------------------------------------------


def _mission_context(repo: Path) -> ImplementContext:
    mission = build_mission(repo, SLUG, MISSION_ID)
    wp_file = mission.feature_dir / "tasks" / "WP01-test.md"
    return ImplementContext(repo, False, SLUG, mission.feature_dir, wp_file, [])


@pytest.mark.parametrize(
    ("actor", "role", "model"),
    [(None, "implement-command", None), ("tester", "tester", "tester")],
    ids=["no-actor", "actor"],
)
def test_operational_context_carries_an_active_role_and_writes_nothing(repo: Path, actor: str | None, role: str, model: str | None) -> None:
    ctx = _mission_context(repo)
    events_before = (ctx.feature_dir / "status.events.jsonl").read_bytes()

    operational_context = implement_phases.build_operational_context(ctx, "WP01", actor)

    assert operational_context.require_active_role() == role
    assert operational_context.active_model == model
    assert operational_context.current_activity == "implement"
    assert (ctx.feature_dir / "status.events.jsonl").read_bytes() == events_before
    assert not (repo / ".worktrees").exists()


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------


def _lane_result(repo: Path, **overrides: Any) -> LaneWorkspaceResult:
    values: dict[str, Any] = {
        "workspace_path": repo / LANE_WORKTREE,
        "branch_name": LANE_BRANCH,
        "workspace_name": "demo-mission-lane-a",
        "lane_id": "lane-a",
        "mission_branch": f"kitty/mission-{SLUG}",
        "is_reuse": False,
        "vcs_backend_value": "git",
        "execution_mode": "worktree",
        "resolution_kind": "lane_workspace",
        "lane_test_env": {"DB_NAME": "test_demo_lane_a"},
    }
    values.update(overrides)
    return LaneWorkspaceResult(**values)


def _resolved(repo: Path) -> ResolvedWorkspace:
    return ResolvedWorkspace(
        mission_slug=SLUG,
        wp_id="WP01",
        execution_mode="code_change",
        mode_source="frontmatter",
        resolution_kind="lane_workspace",
        workspace_name="demo-mission-lane-a",
        worktree_path=repo / LANE_WORKTREE,
        branch_name=LANE_BRANCH,
        lane_id="lane-a",
        lane_wp_ids=["WP01"],
    )


def test_json_payload_golden(repo: Path) -> None:
    build_mission(repo, SLUG, MISSION_ID)
    result = _lane_result(repo)

    payload = _build_implement_json_payload(repo, SLUG, "WP01", result.workspace_path, result.branch_name, result, _resolved(repo))

    assert payload == {
        "workspace": LANE_WORKTREE,
        "workspace_path": LANE_WORKTREE,
        "branch": LANE_BRANCH,
        "mission_slug": SLUG,
        "mission_number": None,
        "mission_type": "software-dev",
        "wp_id": "WP01",
        "lane_id": "lane-a",
        "execution_mode": "worktree",
        "status": "created",
        "lane_test_env": {"DB_NAME": "test_demo_lane_a"},
    }


def test_json_payload_for_a_repository_root_workspace(repo: Path) -> None:
    build_mission(repo, SLUG, MISSION_ID)
    result = _lane_result(repo, workspace_path=repo, branch_name=None, lane_id=None, execution_mode="direct_repo", resolution_kind="repo_root", lane_test_env={})

    payload = _build_implement_json_payload(repo, SLUG, "WP01", repo, None, result, _resolved(repo))

    assert payload["workspace"] == "."
    assert payload["branch"] is None
    assert payload["lane_id"] is None
    assert payload["execution_mode"] == "direct_repo"
    assert payload["lane_test_env"] == {}


def _banner(result: LaneWorkspaceResult, workspace_path: Path) -> list[str]:
    with console.capture() as capture:
        _print_workspace_ready_banner(result, workspace_path)
    return _lines(capture.get())


def test_banner_for_repository_root_planning_work(tmp_path: Path) -> None:
    result = _lane_result(tmp_path, workspace_path=tmp_path, branch_name=None, lane_id=None, resolution_kind="repo_root", lane_test_env={})

    assert _banner(result, tmp_path) == [
        "",
        "✓ Repository-root workspace ready",
        "",
        _RULE,
        "Planning-artifact work for this WP happens in the repository root",
        _RULE,
        "",
        f"  cd {tmp_path}",
        "",
        "This WP does not get a lane worktree or workspace context file.",
        "Make planning-artifact changes directly in the repository root.",
    ]


def test_banner_for_a_single_branch_code_wp(tmp_path: Path) -> None:
    result = _lane_result(
        tmp_path, workspace_path=tmp_path, branch_name="kitty/mission-demo", lane_id="lane-planning", resolution_kind="repo_root", lane_test_env={}
    )

    assert _banner(result, tmp_path) == [
        "",
        "✓ Repository-root workspace ready",
        "",
        "  Work in the repository root checkout on branch kitty/mission-demo",
        f"  cd {tmp_path}",
        "",
        "This WP runs directly in the repository root; commit your work on this branch yourself.",
    ]


def test_banner_for_a_lane_worktree_with_the_lane_test_env(tmp_path: Path) -> None:
    result = _lane_result(tmp_path)
    workspace = tmp_path / LANE_WORKTREE

    assert _banner(result, workspace) == [
        "",
        "✓ Lane worktree ready",
        "",
        _RULE,
        "CRITICAL: Change to the lane worktree before editing files",
        _RULE,
        "",
        f"  cd {workspace}",
        "",
        "All file edits, writes, and commits MUST happen in this directory.",
        "Writing to the main repository instead of the lane worktree is a critical error.",
        "",
        "Lane-specific test environment (FR-006):",
        "  export DB_NAME=test_demo_lane_a",
        "Two parallel SaaS / Django lanes will collide on a single shared test DB unless these are exported in the lane's test process.",
    ]


def _tracker() -> StepTracker:
    tracker = StepTracker("Implement WP01")
    tracker.add("create", "Resolve execution workspace")
    tracker.start("create")
    return tracker


@pytest.mark.parametrize(
    ("overrides", "step_line", "branch_lines"),
    [
        (
            {},
            f"Lane lane-a: {LANE_WORKTREE}",
            [f"→ Mission branch: kitty/mission-{SLUG}", f"→ Lane branch: {LANE_BRANCH}"],
        ),
        (
            {"is_reuse": True},
            f"Reused lane lane-a: {LANE_WORKTREE}",
            [f"→ Mission branch: kitty/mission-{SLUG}", f"→ Lane branch: {LANE_BRANCH}"],
        ),
        (
            {"lane_id": None, "branch_name": None, "mission_branch": None},
            f"Repository root: {LANE_WORKTREE}",
            ["→ Workspace contract: repository root planning workspace"],
        ),
    ],
    ids=["new-lane", "reused-lane", "repository-root"],
)
def test_report_workspace_created(tmp_path: Path, overrides: dict[str, Any], step_line: str, branch_lines: list[str]) -> None:
    result = _lane_result(tmp_path, **overrides)
    tracker = _tracker()

    with console.capture() as capture:
        _report_workspace_created(tracker, result, tmp_path / LANE_WORKTREE, tmp_path)

    lines = _lines(capture.get())
    assert step_line in _flat(capture.get())
    assert lines[-len(branch_lines) :] == branch_lines


# ---------------------------------------------------------------------------
# detect_feature_context and _ensure_vcs_in_meta (moved from tests/agent/test_implement_command.py, WP10)
# ---------------------------------------------------------------------------


def create_meta_json(feature_dir: Path, vcs: str = "git") -> Path:
    meta_path = feature_dir / "meta.json"
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta_content = {
        "feature_number": feature_dir.name.split("-")[0],
        "mission_slug": feature_dir.name,
        "created_at": "2026-01-17T00:00:00Z",
        "friendly_name": feature_dir.name,
        "mission_type": "software-dev",
        "slug": feature_dir.name,
        "target_branch": "main",
    }
    if vcs:
        meta_content["vcs"] = vcs
    meta_path.write_text(json.dumps(meta_content, indent=2))
    return meta_path


class TestDetectFeatureContext:
    def test_detect_with_explicit_flag(self) -> None:
        number, slug = detect_feature_context("010-lane-only-runtime")
        assert number == "010"
        assert slug == "010-lane-only-runtime"

    def test_detect_failure_no_flag(self) -> None:
        with pytest.raises(typer.Exit):
            detect_feature_context(None)

    def test_detect_invalid_format(self) -> None:
        number, slug = detect_feature_context("lane-only-runtime")
        assert number is None
        assert slug == "lane-only-runtime"


class TestEnsureVcsInMeta:
    def test_existing_vcs_is_preserved(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "010-feature"
        create_meta_json(feature_dir, vcs="git")
        assert _ensure_vcs_in_meta(feature_dir, tmp_path).value == "git"

    def test_missing_meta_errors(self, tmp_path: Path) -> None:
        with pytest.raises(typer.Exit):
            _ensure_vcs_in_meta(tmp_path / "kitty-specs" / "010-feature", tmp_path)
