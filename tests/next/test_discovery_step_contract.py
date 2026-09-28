"""End-to-end contract: the issued ``discovery`` prompt is executable (#5254).

An agent following only the prompt ``spec-kitty next`` issues for the
software-dev ``discovery`` step must be able to finish that step using only
supported, working commands — before any spec or plan exists (FR-001..FR-003,
FR-008, FR-012). This test creates a fresh software-dev mission, obtains the
issued ``discovery`` prompt through the real ``next`` CLI, extracts every
``spec-kitty ...`` invocation the prompt tells the agent to run, runs each one
through the real CLI, and then advances ``next`` past ``discovery`` via the
supported path (no ``--result success`` shortcut that bypasses guards).

A second case (FR-012, "Research-type missions only") checks that on a
research-type mission with a filled plan, the fenced research-only
invocation still resolves and scaffolds all four advertised artifacts.

RED-first (ADR 2026-07-17-1): committed failing against the pre-fix prompt
(the old prompt's location pre-flight STOPs on ``main``, so the only
extracted invocation for a software-dev mission is a bare, no-op
``spec-kitty research`` command missing ``--mission``); the failure is
recorded in the WP Activity Log / final report, then this file is converted
to a focused test (no ``regression`` marker) once the prompt is fixed.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from tests._factories import provision_test_charter

pytestmark = [pytest.mark.git_repo]

runner = CliRunner()

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RESEARCH_PROMPT = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "research" / "prompt.md"
_PLAN_PROMPT = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "plan" / "prompt.md"

FILLED_PLAN = """\
# Implementation Plan — Discovery Contract Fixture

## Technical Context
Language/Version: Python 3.11
Primary Dependencies: typer, rich
Storage: filesystem

## Architecture
Regression fixture for #5254 — a research-type mission with a filled plan
must still scaffold research.md/data-model.md from the shipped templates.
"""


# ---------------------------------------------------------------------------
# Invocation extraction (Risks & Mitigations: brittle-prose guard)
# ---------------------------------------------------------------------------

_COMMAND_LINE = re.compile(r"^spec-kitty\s+[a-z][\w .<>/'\"-]*$")
_RESEARCH_ONLY_HEADING = re.compile(r"^#{1,6}\s*Research-type missions only")
_NEXT_HEADING = re.compile(r"^#{1,6}\s")
_FENCE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_DO_NOT_RUN = re.compile(r"do not run|never run", re.IGNORECASE)


def extract_invocations(prompt_text: str, *, include_research_only: bool) -> list[str]:
    """Extract every ``spec-kitty ...`` command the prompt tells the agent to run.

    Scans fenced code blocks and inline code spans for lines beginning with
    ``spec-kitty``. Lines inside a code fence immediately preceded (within the
    same block) by a comment matching "do not run" / "never run" are skipped
    (Risks & Mitigations). The "Research-type missions only" section is
    skipped unless *include_research_only* is True, mirroring how an agent on
    a mission type without research templates would read the prompt.
    """
    invocations: list[str] = []
    in_fence = False
    in_research_only = False
    skip_next_command = False

    for line in prompt_text.splitlines():
        if _RESEARCH_ONLY_HEADING.match(line):
            in_research_only = True
            continue
        if in_research_only and _NEXT_HEADING.match(line) and not _RESEARCH_ONLY_HEADING.match(line):
            in_research_only = False

        skip_section = in_research_only and not include_research_only

        if _FENCE.match(line):
            in_fence = not in_fence
            skip_next_command = False
            continue

        if in_fence:
            stripped = line.strip()
            if stripped.startswith("#"):
                if _DO_NOT_RUN.search(stripped):
                    skip_next_command = True
                continue
            if _COMMAND_LINE.match(stripped):
                if not skip_section and not skip_next_command:
                    invocations.append(stripped)
                skip_next_command = False
            continue

        for match in _INLINE_CODE.finditer(line):
            candidate = match.group(1).strip()
            if _COMMAND_LINE.match(candidate) and not skip_section:
                if _DO_NOT_RUN.search(line):
                    continue
                invocations.append(candidate)

    return invocations


def substitute_placeholders(invocation: str, *, mission_slug: str) -> str:
    """Replace ``<handle>`` / ``<mission_slug>`` placeholders with a real slug."""
    return invocation.replace("<mission_slug>", mission_slug).replace("<handle>", mission_slug)


# ---------------------------------------------------------------------------
# Extractor unit coverage (Risks & Mitigations: positive + negative sample)
# ---------------------------------------------------------------------------


def test_extractor_finds_fenced_and_inline_commands() -> None:
    text = "Run this:\n\n```bash\nspec-kitty agent mission branch-context --json\n```\n\nOr inline: `spec-kitty research --mission <handle>`.\n"
    found = extract_invocations(text, include_research_only=True)
    assert found == [
        "spec-kitty agent mission branch-context --json",
        "spec-kitty research --mission <handle>",
    ]


def test_extractor_skips_do_not_run_examples() -> None:
    text = "```bash\n# do NOT run this bare form\nspec-kitty research\n```\n"
    assert extract_invocations(text, include_research_only=True) == []


def test_extractor_skips_research_only_section_when_excluded() -> None:
    text = (
        "## Research-type missions only\n\n"
        "```bash\nspec-kitty research --mission <handle>\n```\n\n"
        "## Success Criteria\n\n"
        "```bash\nspec-kitty agent mission branch-context --json\n```\n"
    )
    found = extract_invocations(text, include_research_only=False)
    assert found == ["spec-kitty agent mission branch-context --json"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same bypass as ``test_next_command_integration.py`` — these fixtures
    stage minimal mission state without running ``spec-kitty charter sync``.
    """
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    result = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_args, **_kwargs: result,
    )
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_for_dashboard",
        lambda *_args, **_kwargs: result,
    )


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def _scaffold_mission(
    tmp_path: Path,
    mission_slug: str,
    *,
    mission_type: str = "software-dev",
    filled_plan: bool = False,
) -> Path:
    """Scaffold a minimal spec-kitty project with one mission, no plan.md
    (unless *filled_plan*), mirroring ``test_next_command_integration.py``'s
    ``_scaffold_project`` helper (kept local so this module stays independent).
    """
    repo_root = tmp_path / "project"
    repo_root.mkdir()
    _init_git_repo(repo_root)

    kittify = repo_root / ".kittify"
    kittify.mkdir()
    provision_test_charter(repo_root)

    from specify_cli.identity.project import ensure_identity

    ensure_identity(repo_root)

    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_type": mission_type}),
        encoding="utf-8",
    )
    if filled_plan:
        (feature_dir / "plan.md").write_text(FILLED_PLAN, encoding="utf-8")

    return repo_root


# ---------------------------------------------------------------------------
# FR-008 / SC-001: software-dev discovery step is fully executable
# ---------------------------------------------------------------------------


def test_discovery_prompt_is_fully_executable_for_software_dev(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission_slug = "042-discovery-contract"
    repo_root = _scaffold_mission(tmp_path, mission_slug, mission_type="software-dev")
    monkeypatch.chdir(repo_root)

    # Issue the discovery step (the supported advancing path, not a query).
    issued = runner.invoke(
        cli_app,
        ["next", "--agent", "claude", "--mission", mission_slug, "--result", "success", "--json"],
    )
    assert issued.exit_code == 0, issued.output
    decision = json.loads(issued.stdout)
    assert decision["kind"] == "step"
    assert decision["mission_state"] == "discovery"

    prompt_file = decision["prompt_file"]
    assert prompt_file, "kind='step' must carry a non-empty prompt_file"
    prompt_text = Path(prompt_file).read_text(encoding="utf-8")

    # FR-002: no STOP / "not main" location instruction survives into the
    # issued prompt.
    assert "STOP" not in prompt_text.upper() or "⛔" not in prompt_text
    assert "NOT main" not in prompt_text
    assert "main branch" not in prompt_text.lower() or "not " not in prompt_text.lower().split("main branch")[0][-20:]

    # FR-001: the prompt names research.md as create-or-extend.
    assert "research.md" in prompt_text
    assert "create" in prompt_text.lower() and "extend" in prompt_text.lower()

    invocations = extract_invocations(prompt_text, include_research_only=False)
    assert invocations, "the issued discovery prompt must name at least one runnable command"

    for raw in invocations:
        command = substitute_placeholders(raw, mission_slug=mission_slug)
        tokens = command.split()
        assert tokens[0] == "spec-kitty"
        result = runner.invoke(cli_app, tokens[1:])
        assert result.exit_code == 0, f"{command!r} failed: {result.output}"

    # Every success-criteria bullet names only artifacts the prompt told the
    # agent it may author (research.md and the optional research/ evidence
    # dir) — never data-model.md or the CSV stubs, which this mission type
    # never gets and the old prompt falsely promised.
    success_section = prompt_text.split("## Success Criteria", 1)[-1]
    assert "data-model.md" not in success_section
    assert "evidence-log.csv" not in success_section
    assert "source-register.csv" not in success_section

    # FR-008: advancing past discovery via the supported path (no shortcut) —
    # a second ``--result success`` completes the no-artifact-required step.
    advanced = runner.invoke(
        cli_app,
        ["next", "--agent", "claude", "--mission", mission_slug, "--result", "success", "--json"],
    )
    assert advanced.exit_code == 0, advanced.output
    next_decision = json.loads(advanced.stdout)
    assert next_decision["mission_state"] != "discovery"


# ---------------------------------------------------------------------------
# FR-012: the research-type "Research-type missions only" invocation still
# resolves and scaffolds all 4 artifacts once that mission's plan is filled.
# ---------------------------------------------------------------------------


def test_research_only_invocation_scaffolds_four_artifacts_for_research_mission(
    tmp_path: Path,
) -> None:
    mission_slug = "research-contract"
    repo_root = _scaffold_mission(
        tmp_path,
        mission_slug,
        mission_type="research",
        filled_plan=True,
    )

    prompt_text = _RESEARCH_PROMPT.read_text(encoding="utf-8")
    invocations = extract_invocations(prompt_text, include_research_only=True)
    research_invocations = [inv for inv in invocations if inv.split()[1] == "research"]
    assert research_invocations, "expected a 'spec-kitty research ...' invocation in the research-only section"

    import os

    old_cwd = Path.cwd()
    os.chdir(repo_root)
    try:
        for raw in research_invocations:
            command = substitute_placeholders(raw, mission_slug=mission_slug)
            tokens = command.split()
            result = runner.invoke(cli_app, tokens[1:])
            assert result.exit_code == 0, f"{command!r} failed: {result.output}"
    finally:
        os.chdir(old_cwd)

    feature_dir = repo_root / "kitty-specs" / mission_slug
    for rel in (
        "research.md",
        "data-model.md",
        Path("research") / "evidence-log.csv",
        Path("research") / "source-register.csv",
    ):
        dest = feature_dir / rel
        assert dest.exists(), f"{rel} was not created"
        assert dest.stat().st_size > 0, f"{rel} is empty"


# ---------------------------------------------------------------------------
# FR-004: the plan prompt's Phase 0 says extend, not replace.
# ---------------------------------------------------------------------------


def test_plan_prompt_phase0_says_extend_not_replace() -> None:
    plan_text = _PLAN_PROMPT.read_text(encoding="utf-8")
    phase0_marker = "Phase 0"
    assert phase0_marker in plan_text
    phase0_section = plan_text.split(phase0_marker, 1)[-1][:2000]
    assert "extend" in phase0_section.lower()
    assert "research.md" in phase0_section
    assert "do not replace" in phase0_section.lower() or "not replace" in phase0_section.lower()
