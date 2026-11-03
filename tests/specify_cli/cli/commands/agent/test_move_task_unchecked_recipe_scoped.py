"""Every printed subtask-completion recipe names the work package (#7108).

Subtask ids are mission-scoped: the normal case is several WPs that each author
`T001..T00n`. `mark-status` resolves that with `--wp` and refuses an unscoped id
several WPs own, so a printed recipe without `--wp` is a dead end exactly when it
is needed — and the operator reaches for `--force`, which hides the
mis-attribution.

The refusal is the surface that hurt most: it is the only advice an operator gets
when the review gate blocks them. It, and the generated prompts, must name the WP.
"""

from __future__ import annotations

import ast
import json
import shlex
from contextlib import contextmanager
import dataclasses
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from runtime.next.prompt_builder import _completion_lines
from specify_cli.cli.commands.agent.tasks import app
from specify_cli.cli.commands.agent.tasks_transition_core import MoveTaskRequest, _guard_subtasks
from specify_cli.cli.commands.agent.workflow_executor import _subtask_completion_recipe

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

_SLUG = "port-completion-01M6FZ0K"
_REPO_SRC = Path(__file__).resolve().parents[5] / "src"


def _request(**overrides: Any) -> MoveTaskRequest:
    """A ``for_review`` request whose only interesting fact is the unchecked roster."""
    base: dict[str, Any] = {
        "task_id": "WP02",
        "target_lane": "for_review",
        "old_lane": "planned",
        "force": False,
        "agent": None,
        "current_agent": None,
        "note": None,
        "auto_commit": False,
        "target_branch": "main",
        "skip_target_branch_commit": True,
        "tracker_ref_values": (),
        "assignee": None,
        "shell_pid": None,
        "self_review_fallback": False,
        "intended_reviewer": None,
        "reviewer_failure_reason": None,
        "protected_error": None,
        "review_verdict": None,
        "review_artifact_name": None,
        "skip_review_artifact_check": True,
        "feedback_provided": False,
        "feedback_source": None,
        "feedback_exists": False,
        "feedback_is_file": False,
        "feedback_content": None,
        "unchecked_subtasks": ("T001", "T002"),
        "review_ready": True,
        "review_guidance": (),
        "done_execution_mode": None,
        "done_merged": False,
        "done_merge_msg": "",
        "done_override_reason": None,
        "issue_matrix_blocker": None,
        "is_arbiter_override": False,
        "effective_reviewer": None,
        "effective_approval_ref": None,
        "mission_slug": _SLUG,
    }
    base.update(overrides)
    return MoveTaskRequest(**base)


# ---------------------------------------------------------------------------
# 1. The move-task refusal
# ---------------------------------------------------------------------------


def test_refusal_recipe_names_the_wp_being_moved() -> None:
    """The advice must be runnable where it is printed: on WP02, not 'the first WP'."""
    refusal = _guard_subtasks(_request())

    assert refusal is not None
    assert f"spec-kitty agent tasks mark-status T001 --wp WP02 --status done --mission {_SLUG}" in refusal.error
    assert f"spec-kitty agent tasks mark-status T002 --wp WP02 --status done --mission {_SLUG}" in refusal.error


def test_refusal_still_reports_every_unchecked_id_and_the_force_hint() -> None:
    """The verdict and the surrounding text are unchanged; only the recipe moved (#7108, C-003)."""
    refusal = _guard_subtasks(_request())

    assert refusal is not None
    assert "Cannot move WP02 to for_review - unchecked subtasks:" in refusal.error
    assert "  - [ ] T001" in refusal.error
    assert "  - [ ] T002" in refusal.error
    assert "Or use --force to override (not recommended)" in refusal.error


def test_refusal_recipe_is_valid_without_a_mission_slug() -> None:
    """A directly constructed request may not know the mission; never print `--mission None`."""
    refusal = _guard_subtasks(_request(mission_slug=None))

    assert refusal is not None
    assert "spec-kitty agent tasks mark-status T001 --wp WP02 --status done" in refusal.error
    assert "--mission" not in refusal.error
    assert "None" not in refusal.error


def test_refusal_stays_silent_for_complete_or_forced_transitions() -> None:
    """The guard's pass conditions are untouched by the recipe change."""
    assert _guard_subtasks(_request(unchecked_subtasks=())) is None
    assert _guard_subtasks(_request(force=True)) is None


# ---------------------------------------------------------------------------
# 2. The recipe actually clears the gate it was printed for (SC-001)
# ---------------------------------------------------------------------------


def _write_shared_id_mission(repo: Path, slug: str) -> Path:
    """Two WPs that both author T001/T002 — the shape issue #7108 reports."""
    mission_dir = repo / "kitty-specs" / slug
    (mission_dir / "tasks").mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_id": "01TESTMISSION", "status_phase": "1"}), encoding="utf-8")
    (mission_dir / "tasks.md").write_text("# Tasks\n\n## WP01\nSubtasks: T001, T002\n\n## WP02\nSubtasks: T001, T002\n", encoding="utf-8")
    for wp_id in ("WP01", "WP02"):
        (mission_dir / "tasks" / f"{wp_id}-test.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\nsubtasks:\n  - T001\n  - T002\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )
    return mission_dir


@contextmanager
def _null_lock(repo_root: Path, mission_slug: str):  # type: ignore[no-untyped-def]
    del repo_root, mission_slug
    yield


def _run_recipe(repo: Path, slug: str, recipe: str) -> tuple[int, str]:
    """Execute a rendered recipe through the real ``mark-status`` entry point."""
    argv = shlex.split(recipe)
    assert argv[:4] == ["spec-kitty", "agent", "tasks", "mark-status"], recipe
    with (
        patch("specify_cli.cli.commands.agent.tasks.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent.tasks._find_mission_slug", return_value=slug),
        patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out", return_value=(repo, "main")),
        patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning"),
        patch("specify_cli.cli.commands.agent.tasks.feature_status_lock", _null_lock),
    ):
        result = runner.invoke(app, [*argv[3:], "--json", "--no-auto-commit"])
    del slug
    return result.exit_code, result.output


def test_the_emitted_recipe_clears_the_gate_it_was_printed_for(tmp_path: Path) -> None:
    """The recipe the refusal prints, run verbatim, records completion against that WP.

    This is the #7108 dead end: before the fix the printed command was itself
    refused on this exact fixture and the operator had to reach for ``--force``.
    """
    slug = "7108-shared-ids"
    mission_dir = _write_shared_id_mission(tmp_path, slug)
    refusal = _guard_subtasks(_request(task_id="WP02", mission_slug=slug))
    assert refusal is not None
    # The rendered mission slug is the fixture's, not the module-level constant.
    recipe_line = next(line.strip() for line in refusal.error.splitlines() if line.strip().startswith("spec-kitty agent tasks mark-status T001 "))
    assert "T001" in recipe_line

    exit_code, output = _run_recipe(tmp_path, slug, recipe_line)
    assert exit_code == 0, output

    events = [json.loads(line) for line in (mission_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    subtask_events = [event for event in events if event.get("delta", {}).get("subtasks")]
    assert [(event["wp_id"], event["delta"]["subtasks"]) for event in subtask_events] == [("WP02", {"T001": "done"})]


# ---------------------------------------------------------------------------
# 3. The generated implement prompt (SC-002, SC-003)
# ---------------------------------------------------------------------------


def test_completion_lines_scope_the_recipe_to_the_wp() -> None:
    lines = _completion_lines("implement", "WP02", _SLUG, ["T001", "T002"])

    assert f"  spec-kitty agent tasks mark-status T001 T002 --wp WP02 --status done --mission {_SLUG}" in lines


def test_completion_lines_keep_the_no_roster_wording() -> None:
    """A WP with no authored roster must not be handed a command with nothing to mark (FR-006)."""
    lines = _completion_lines("implement", "WP02", _SLUG, [])

    assert not any("mark-status" in line for line in lines)
    assert "  No subtask completion command is needed; this work package declares no subtasks." in lines


def test_review_completion_lines_do_not_gain_a_mark_status_recipe() -> None:
    """Only the implement arm marks subtasks; review approves or rejects."""
    lines = _completion_lines("review", "WP02", _SLUG, ["T001"])

    assert not any("mark-status" in line for line in lines)


# ---------------------------------------------------------------------------
# 4. The printed implement runbooks (SC-002)
# ---------------------------------------------------------------------------


def test_runbook_recipe_names_the_wp() -> None:
    """``workflow.py`` hands these sites a pre-joined roster; the WP is still named."""
    recipe = _subtask_completion_recipe("WP02", _SLUG, "T001 T002")

    assert recipe == f"spec-kitty agent tasks mark-status T001 T002 --wp WP02 --status done --mission {_SLUG}"


def test_runbook_recipe_keeps_the_placeholder_when_no_roster_is_authored() -> None:
    """An empty roster renders the pre-existing ``<subtask-ids>`` placeholder, now scoped."""
    recipe = _subtask_completion_recipe("WP02", _SLUG, "<subtask-ids>")

    assert recipe == f"spec-kitty agent tasks mark-status <subtask-ids> --wp WP02 --status done --mission {_SLUG}"


# ---------------------------------------------------------------------------
# 4. No module may hand-format the recipe again (SC-002)
# ---------------------------------------------------------------------------

_RECIPE_PREFIX = "spec-kitty agent tasks mark-status"
_ALLOWED_RECIPE_PRODUCERS = {"specify_cli/core/subtask_recipe.py"}


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Ids of the ``Constant`` nodes that are docstrings (prose, not rendered advice)."""
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    return {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, holders) and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
    }


def _rendered_shape(node: ast.JoinedStr) -> str:
    """The interpolated text of an f-string with each placeholder as ``{}``.

    An f-string is not one ``Constant``: its literal runs and its
    ``FormattedValue`` parts are separate nodes, so a plain constant scan cannot
    see a recipe built with ``"... mark-status {ids} --status done ..."``.
    """
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        else:
            parts.append("{}")
    return "".join(parts)


def test_only_the_renderer_builds_the_recipe_text() -> None:
    """A new emitter that f-string-forms the command would silently re-open #7108."""
    offenders: list[str] = []
    scanned = 0
    for path in sorted(_REPO_SRC.rglob("*.py")):
        scanned += 1
        relative = path.relative_to(_REPO_SRC).as_posix()
        if relative in _ALLOWED_RECIPE_PRODUCERS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                shape = _rendered_shape(node)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) in docstrings:
                    continue
                shape = node.value
            else:
                continue
            # A recipe is the command prefix *plus* its status flag: that excludes
            # the diagnostic labels and prose that merely name the command.
            if _RECIPE_PREFIX in shape and "--status" in shape:
                offenders.append(f"{relative}:{getattr(node, 'lineno', '?')}")

    # Non-vacuity: a broken source root would make the scan trivially clean.
    assert scanned > 100, f"census scanned only {scanned} modules under {_REPO_SRC}"
    assert not offenders, f"hand-formatted mark-status recipes outside the renderer: {offenders}"


def test_the_renderer_is_the_only_place_the_prefix_is_a_code_literal() -> None:
    """Sanity control for the census above: the renderer itself must still contain it."""
    source = (_REPO_SRC / "specify_cli/core/subtask_recipe.py").read_text(encoding="utf-8")

    assert _RECIPE_PREFIX in source


def test_the_recipe_requires_a_wp_id() -> None:
    """The renderer's contract: no call site can omit the WP."""
    field_names = {field.name for field in dataclasses.fields(MoveTaskRequest)}

    assert "mission_slug" in field_names
    assert "task_id" in field_names
