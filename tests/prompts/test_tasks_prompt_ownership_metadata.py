"""Regression tests for /spec-kitty.tasks ownership metadata guidance."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TASKS_PROMPT_SURFACES = (
    _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "tasks" / "prompt.md",
    _REPO_ROOT / ".kittify" / "overrides" / "missions" / "software-dev" / "command-templates" / "tasks.md",
)
_STAGED_TASKS_PROMPT_SURFACES = (
    _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "tasks-outline" / "prompt.md",
    _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "tasks-packages" / "prompt.md",
)
_OWNERSHIP_RULE_PROMPT_SURFACES = _TASKS_PROMPT_SURFACES + _STAGED_TASKS_PROMPT_SURFACES
_TASK_PROMPT_TEMPLATE = _REPO_ROOT / "packs" / "built-in" / "missions" / "software-dev" / "templates" / "task-prompt-template.md"


def _ownership_metadata_section(prompt_path: Path) -> str:
    text = prompt_path.read_text(encoding="utf-8")
    marker = "**OWNERSHIP METADATA (required by finalize-tasks)**"
    start = text.index(marker)
    next_heading = text.index("**Ownership rules**", start)
    return text[start:next_heading]


def _repo_relative_id(path: Path) -> str:
    """Repo-relative parametrize id, stable across checkout locations.

    Absolute-path ids embed the worktree root in the pytest node-id, so any
    frozen node-id baseline only matches the exact checkout path it was frozen
    from (#2607).
    """
    return path.relative_to(_REPO_ROOT).as_posix()


@pytest.mark.parametrize("prompt_path", _TASKS_PROMPT_SURFACES, ids=_repo_relative_id)
def test_tasks_prompt_documents_create_intent_with_required_ownership_fields(prompt_path: Path) -> None:
    section = _ownership_metadata_section(prompt_path)

    for field in ("`execution_mode`", "`owned_files`", "`authoritative_surface`", "`create_intent`"):
        assert field in section


@pytest.mark.parametrize("prompt_path", _TASKS_PROMPT_SURFACES, ids=_repo_relative_id)
def test_tasks_prompt_explains_create_intent_for_planned_new_owned_files(prompt_path: Path) -> None:
    section = _ownership_metadata_section(prompt_path)

    assert "planned-new" in section or "planned new" in section
    assert "zero-match" in section or "zero match" in section


@pytest.mark.parametrize("prompt_path", _TASKS_PROMPT_SURFACES, ids=_repo_relative_id)
def test_tasks_prompt_prevents_duplicate_create_intent_stubs(prompt_path: Path) -> None:
    section = _ownership_metadata_section(prompt_path)

    assert "single `create_intent` key" in section
    assert "stub `create_intent: []`" in section
    assert "replace it instead of adding a duplicate block" in section


# --- kitty-specs owned_files rule (#3934) ---------------------------------------
#
# finalize-tasks enforces the kitty-specs owned_files ban
# (INVALID_WP_OWNED_FILES_KITTY_SPECS): a code_change WP may not own kitty-specs/
# paths, and the only exemption is a planning_artifact WP whose EVERY owned_files
# entry is confined to kitty-specs/ or docs/ (mission_parsing._is_confined_
# planning_wp, ownership.validation._PLANNING_PREFIXES). These tests pin the
# /spec-kitty.tasks prompt and the WP template to that validator so the rule is
# stated where authors write owned_files, instead of being discovered as a
# finalize-tasks round-trip (#3934).


@pytest.mark.parametrize("prompt_path", _OWNERSHIP_RULE_PROMPT_SURFACES, ids=_repo_relative_id)
def test_tasks_prompt_states_kitty_specs_ban_for_code_change_wps(prompt_path: Path) -> None:
    text = prompt_path.read_text(encoding="utf-8")

    assert "INVALID_WP_OWNED_FILES_KITTY_SPECS" in text, (
        f"{prompt_path} must name the finalize-tasks error code so authors can connect the prompt rule to the validation failure."
    )
    assert "code_change" in text and "kitty-specs/" in text
    assert "must NOT list any `kitty-specs/` path" in text


@pytest.mark.parametrize("prompt_path", _OWNERSHIP_RULE_PROMPT_SURFACES, ids=_repo_relative_id)
def test_tasks_prompt_states_planning_artifact_confinement(prompt_path: Path) -> None:
    text = prompt_path.read_text(encoding="utf-8")

    assert "planning_artifact" in text
    assert "`kitty-specs/` or `docs/`" in text, (
        f"{prompt_path} must state the confinement guard: the planning_artifact exemption applies only when EVERY owned_files entry is under kitty-specs/ or docs/."
    )
    assert "not exempt" in text


@pytest.mark.parametrize("prompt_path", _OWNERSHIP_RULE_PROMPT_SURFACES, ids=_repo_relative_id)
def test_tasks_prompt_states_where_per_wp_design_notes_go(prompt_path: Path) -> None:
    text = prompt_path.read_text(encoding="utf-8")

    assert "design notes" in text, (
        f"{prompt_path} must state where per-WP design notes / kitty-specs deliverables are declared (a separate confined planning_artifact WP)."
    )
    assert "separate confined `planning_artifact` WP" in text or ("their own confined `planning_artifact` WP" in text)


def test_task_prompt_template_states_kitty_specs_owned_files_rule() -> None:
    """The WP template frontmatter must carry the same rule as the prompt.

    The template's ``owned_files``/``execution_mode`` comments are the first
    place a WP author looks when filling in ownership metadata; if the ban and
    the planning_artifact confinement live only in the tasks prompt, a template
    author still has no declarable home for kitty-specs deliverables (#3934).
    """
    text = _TASK_PROMPT_TEMPLATE.read_text(encoding="utf-8")

    assert "INVALID_WP_OWNED_FILES_KITTY_SPECS" in text
    assert "code_change WPs may never own kitty-specs/ paths" in text
    assert "confine every owned_files entry to kitty-specs/ or docs/" in text
    assert "separate planning_artifact WP" in text
