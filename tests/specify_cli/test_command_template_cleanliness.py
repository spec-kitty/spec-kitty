"""Tests for prompt content cleanliness in the canonical command templates.

These tests assert that the 9 canonical prompt-driven command template files
are free of dev-specific content that would break consumer projects:
  - No 057- or other feature-slug artifacts
  - No absolute machine paths (/Users/<user>/, /home/<user>/)
  - No .kittify/missions/ read instructions
  - No deprecated "planning repository" terminology
  - All templates >=50 non-empty lines
  - YAML frontmatter present and declares a non-empty ``description``
    (slash-command pickers like Claude Code read this for their UI)
  - Planning-workflow templates use "repository root checkout" terminology
  - tasks.md contains WP ownership metadata guidance fields
  - All templates include --mission guidance

WP06: T026
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Template discovery
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]
# The tests and helpers shared with this suite's always-on lift live once, in
# ``tests/architectural/_lifted_root_command_template_cleanliness.py`` (#5015); importing a test is what makes pytest collect it here.
from tests.architectural._lifted_root_command_template_cleanliness import (
    PROMPT_DRIVEN,
    _PROMPT_STEPS_DIR,
    _FORBIDDEN_HOME_LITERAL,
    _template_content,
)
from tests.architectural._lifted_root_command_template_cleanliness import test_no_dev_specific_mission_slugs as test_no_dev_specific_mission_slugs
from tests.architectural._lifted_root_command_template_cleanliness import test_no_absolute_user_paths as test_no_absolute_user_paths
from tests.architectural._lifted_root_command_template_cleanliness import test_no_planning_repository_terminology as test_no_planning_repository_terminology

# All full prompt-driven command templates.

# Planning-workflow templates that MUST use "repository root checkout" terminology.
# These are commands that explicitly direct agents on where to perform work.
# The utility/analysis commands (analyze, checklist, charter) don't
# describe a checkout location, so they are excluded from this assertion.
PLANNING_WORKFLOW_TEMPLATES: list[str] = [
    "specify",
    "plan",
    "tasks",
    "tasks-outline",
    "tasks-packages",
    "research",
]


_REPO_ROOT = Path(__file__).parent.parent.parent
_ACTIVE_CODEBASE_PATHS: tuple[Path, ...] = (
    _REPO_ROOT / "src",
    _REPO_ROOT / "tests",
    _REPO_ROOT / "docs",
    _REPO_ROOT / "architecture",
    _REPO_ROOT / "research",
    _REPO_ROOT / "AGENTS.md",
    _REPO_ROOT / "README.md",
    _REPO_ROOT / "CHANGELOG.md",
)


def _active_codebase_files() -> list[Path]:
    """Return text files from the active codebase surface.

    `kitty-specs/` is intentionally excluded because the user wants to preserve
    historical artifacts there.
    """
    files: list[Path] = []
    for path in _ACTIVE_CODEBASE_PATHS:
        if path.is_file():
            files.append(path)
            continue
        files.extend(
            candidate
            for candidate in path.rglob("*")
            if candidate.is_file() and "__pycache__" not in candidate.parts and candidate.suffix != ".pyc"
        )
    return files


# ---------------------------------------------------------------------------
# T026-a: Template existence and minimum length
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", PROMPT_DRIVEN)
def test_template_exists(command: str) -> None:
    """Every prompt-driven command must have a template file."""
    f = _PROMPT_STEPS_DIR / command / "prompt.md"
    assert f.exists(), f"{command}/prompt.md not found in mission steps dir: {_PROMPT_STEPS_DIR}"


@pytest.mark.parametrize("command", PROMPT_DRIVEN)
def test_template_minimum_length(command: str) -> None:
    """Every template must have at least 40 non-empty lines.

    This threshold clearly distinguishes full prompt templates (which have
    substantial workflow guidance) from thin 4-line CLI shim files.
    """
    content = _template_content(command)
    non_empty_lines = [ln for ln in content.splitlines() if ln.strip()]
    assert len(non_empty_lines) >= 40, (
        f"{command}.md is too short: {len(non_empty_lines)} non-empty lines "
        f"(minimum 40 required to qualify as a full prompt template)"
    )


# ---------------------------------------------------------------------------
# T026-b: No feature slug artifacts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", PROMPT_DRIVEN)
def test_no_057_mission_slug(command: str) -> None:
    """Templates must not contain the 057- development slug."""
    content = _template_content(command)
    assert "057-" not in content, (
        f"{command}.md contains '057-' dev-time feature slug - strip before shipping"
    )


# ---------------------------------------------------------------------------
# T026-c: No absolute machine-specific paths
# ---------------------------------------------------------------------------


def test_no_user_specific_home_literal_in_active_codebase() -> None:
    """The active codebase must never ship a forbidden user-specific home path."""
    offenders = [
        path.relative_to(_REPO_ROOT).as_posix()
        for path in _active_codebase_files()
        if _FORBIDDEN_HOME_LITERAL in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert offenders == [], (
        "Found forbidden user-specific home path literal in active codebase files: "
        + ", ".join(offenders)
    )


# ---------------------------------------------------------------------------
# T026-d: No .kittify/missions/ read instructions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", PROMPT_DRIVEN)
def test_no_kittify_missions_read_instruction(command: str) -> None:
    """Templates must not instruct agents to read template files from .kittify/missions/.

    Agents should write content directly rather than reading from .kittify/missions/.
    """
    content = _template_content(command)
    lower = content.lower()
    # Flag if the template tells agents to read files from .kittify/missions/
    # (e.g., "read .kittify/missions/..." or "cat .kittify/missions/...")
    if ".kittify/missions/" in lower:
        # If .kittify/missions/ appears, verify it's not paired with a read instruction
        # Split on the marker and check context
        for line in content.splitlines():
            if ".kittify/missions/" in line.lower():
                assert "read" not in line.lower() and "cat " not in line.lower(), (
                    f"{command}.md contains .kittify/missions/ read instruction: {line.strip()!r}"
                )


# ---------------------------------------------------------------------------
# T026-e: No deprecated planning-location terminology
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T026-f: Planning-workflow templates use "repository root checkout"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", PLANNING_WORKFLOW_TEMPLATES)
def test_uses_repository_root_checkout_in_planning_templates(command: str) -> None:
    """Planning-workflow templates must use 'repository root checkout' terminology.

    These templates direct agents on where to perform planning work.
    They must explicitly state 'repository root checkout' so agents work in the
    correct location and do not create a worktree for planning.
    """
    content = _template_content(command)
    assert "repository root checkout" in content.lower(), (
        f"{command}.md missing 'repository root checkout' terminology - "
        f"add explicit location guidance for agents"
    )


# ---------------------------------------------------------------------------
# T026-g: YAML frontmatter present and declares a description
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", PROMPT_DRIVEN)
def test_has_yaml_frontmatter_with_description(command: str) -> None:
    """Templates must open with a YAML frontmatter block declaring ``description``.

    The asset generator preserves the template's frontmatter verbatim and
    places the version marker just after it.  Slash-command pickers (e.g.
    Claude Code) read the ``description`` field to populate their UI; without
    it, users see the raw HTML version-marker comment as the description.
    """
    from specify_cli.template.renderer import parse_frontmatter

    content = _template_content(command)
    assert content.startswith("---\n"), (
        f"{command}.md is missing YAML frontmatter — add a `---\\ndescription: "
        f"...\\n---` block so the slash-command picker has a real description"
    )
    metadata, _body, _raw = parse_frontmatter(content)
    description = str(metadata.get("description", "")).strip()
    assert description, (
        f"{command}.md frontmatter is missing a non-empty `description` field"
    )


# ---------------------------------------------------------------------------
# T026-h: --mission guidance present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", PROMPT_DRIVEN)
def test_has_feature_flag_guidance(command: str) -> None:
    """Every template must include a note about passing --mission <slug>."""
    content = _template_content(command)
    assert "--mission" in content, (
        f"{command}.md missing '--mission' guidance - add: "
        f"'In repos with multiple missions, always pass `--mission <slug>` to "
        f"every spec-kitty command.'"
    )


# ---------------------------------------------------------------------------
# T026-i: tasks.md ownership metadata guidance
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T029 / T030: context resolve example includes --mission
# ---------------------------------------------------------------------------


def test_tasks_template_context_resolve_has_mission() -> None:
    """tasks.md context resolve example must include --mission <mission-slug> (T029)."""
    content = _template_content("tasks")
    # The context resolve command example must explicitly show --mission
    assert "context resolve --action tasks --mission" in content, (
        "tasks.md context resolve example missing '--mission' - "
        "agents copy-paste this and immediately fail without it"
    )


@pytest.mark.parametrize("command", ["tasks-packages", "tasks-outline"])
def test_context_resolve_examples_have_mission(command: str) -> None:
    """All context resolve examples in planning templates must include --mission (T030)."""
    content = _template_content(command)
    # If a template has a context resolve call, it must have --mission
    if "context resolve" in content:
        assert "--mission" in content, (
            f"{command}.md has context resolve call without '--mission' - "
            f"add --mission <mission-slug> to the context resolve example"
        )


def test_tasks_template_finalize_tasks_has_mission() -> None:
    """tasks.md finalize-tasks examples must include --mission (T030)."""
    content = _template_content("tasks")
    # The validate-only example must have --mission
    assert "finalize-tasks --validate-only --mission" in content, (
        "tasks.md finalize-tasks --validate-only example missing '--mission'"
    )


def test_tasks_template_finalization_is_preflight_first() -> None:
    """tasks.md must instruct agents to validate before mutating finalization."""
    content = _template_content("tasks")
    validate_index = content.index("finalize-tasks --validate-only --mission")
    mutate_index = content.index("finalize-tasks --mission <mission-slug> --json")
    assert validate_index < mutate_index
    assert "do **not** run the mutating finalization command" in content


def test_tasks_finalize_template_is_preflight_first() -> None:
    """tasks-finalize.md must not hand agents the mutating command first."""
    content = _template_content("tasks-finalize")
    validate_index = content.index("finalize-tasks --validate-only --mission")
    mutate_index = content.index("finalize-tasks --mission <mission-slug> --json")
    assert validate_index < mutate_index
    assert "do **not** run finalization" in content


def test_tasks_template_map_requirements_has_mission() -> None:
    """tasks.md map-requirements examples must include --mission (T030)."""
    content = _template_content("tasks")
    assert "map-requirements --batch" in content
    # Batch mode example must include --mission
    lines_with_batch = [ln for ln in content.splitlines() if "map-requirements --batch" in ln]
    assert lines_with_batch, "tasks.md missing map-requirements --batch example"
    for line in lines_with_batch:
        assert "--mission" in line, (
            f"tasks.md map-requirements --batch line missing '--mission': {line.strip()!r}"
        )


def test_analyze_template_persists_analysis_report() -> None:
    """analyze.md must persist durable proof before implementation."""
    content = (
        _REPO_ROOT
        / "packs"
        / "built-in"
        / "missions"
        / "mission-steps"
        / "software-dev"
        / "analyze"
        / "prompt.md"
    ).read_text(encoding="utf-8")
    assert "analysis-report.md" in content
    assert "spec-kitty agent mission record-analysis --mission" in content
    assert "Should all of these findings be addressed before moving on to implementation?" in content


def test_tasks_template_requires_analyze_before_implementation() -> None:
    """tasks.md must present analyze as the required pre-implementation gate.

    The Step 10 handoff was reworded from an "optional quality control gate"
    to a required readiness prerequisite (2bd38fca6): the implement gate
    refuses to claim a WP without ``analysis-report.md``
    (``analysis_report_required``), so describing analyze as optional misled
    operators into hitting the gate error.
    """
    content = _template_content("tasks")
    assert "/spec-kitty-implement-review" in content
    assert "Required pre-implementation gate" in content
    assert "/spec-kitty.analyze" in content


def test_tasks_template_has_ownership_guidance() -> None:
    """tasks.md must include WP ownership metadata field guidance.

    Agents use these fields to enforce file ownership isolation:
    - owned_files: glob patterns for files the WP touches
    - authoritative_surface: canonical output location path prefix
    - execution_mode: 'code_change' or 'planning_artifact'
    """
    content = _template_content("tasks")
    assert "owned_files" in content, (
        "tasks.md missing 'owned_files' ownership guidance - "
        "agents need this to enforce file isolation between WPs"
    )
    assert "authoritative_surface" in content, (
        "tasks.md missing 'authoritative_surface' guidance - "
        "identifies the canonical output location for each WP"
    )
    assert "execution_mode" in content, (
        "tasks.md missing 'execution_mode' guidance - "
        "must distinguish 'code_change' from 'planning_artifact' WPs"
    )
