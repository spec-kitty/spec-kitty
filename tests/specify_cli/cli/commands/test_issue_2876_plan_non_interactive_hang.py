"""Issue #2876 — ``spec-kitty plan`` used to emit an interactive prompt (and,
in a real agent/CI harness with an open, un-closed stdin pipe, block forever
on it) under ``SPEC_KITTY_NON_INTERACTIVE=1``.

Formerly a red-first ``@pytest.mark.regression`` reproduction; relocated
here and un-marked (landing fold: make ``@pytest.mark.regression`` mean
exactly one thing) once the fix landed and this test started passing.
#2876 is fixed — this is now a permanent guard, not a red-first pin.

Defect (per the P0 report, fixed): under ``SPEC_KITTY_NON_INTERACTIVE=1`` — the
primary way agents/CI drive this tool, where stdin is closed or not a TTY —
``spec-kitty plan`` still reaches ``run_plan_interview``
(``specify_cli.missions.plan.plan_interview.run_plan_interview``), which
unconditionally prints a ``[enter]=accept default | ...`` hint line and calls
``typer.prompt(question_text, ...)`` for every question in
``PLAN_WIDEN_QUESTIONS`` — there is no ``SPEC_KITTY_NON_INTERACTIVE`` (or any
other non-interactive) gate anywhere in that call graph. Confirmed by
grepping the codebase: ``SPEC_KITTY_NON_INTERACTIVE`` is checked only in
``cli/commands/init.py`` and ``cli/commands/_auth_recovery.py`` — never in
``cli/commands/lifecycle.py`` or ``missions/plan/plan_interview.py``. In a
real non-interactive invocation with an open-but-silent stdin pipe (the
common agent-harness shape), ``typer.prompt``'s underlying ``input()`` call
blocks forever waiting for a line that will never arrive — the reported hang.

This test drives the exact, unmodified, pre-existing production entry point:
``specify_cli.cli.commands.lifecycle.plan`` (the same function object
``specify_cli/cli/commands/__init__.py`` registers as the real
``spec-kitty plan`` command), wrapped in a throwaway ``typer.Typer()`` the
same way ``tests/specify_cli/cli/commands/test_plan_widen.py`` already does
for this exact widen-interview surface. Only ``agent_feature.setup_plan``
(plan-scaffolding side effects — file/branch/commit mechanics, orthogonal to
the interview-prompt defect under test) and ``locate_project_root`` are
patched, mirroring that established harness.

Bounding the hang: CliRunner's ``input=""`` feeds an already-exhausted stdin
buffer, so ``input()`` raises ``EOFError`` on first read rather than
blocking forever in-process (a real closed/non-TTY stdin, not an open silent
pipe) — this reproduces the "still emits a prompt" half of the defect
without ever blocking the test runner. As an additional guard against any
unexpected in-process blocking (e.g. a stray network call in the widen
prereq check), the whole invocation also runs under a hard wall-clock bound
via a worker thread; a real hang surfaces as a ``TimeoutError`` failure
rather than a stuck test run.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.lifecycle import PLAN_WIDEN_QUESTIONS, plan

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_app = typer.Typer()
_app.command()(plan)

runner = CliRunner()

MISSION_SLUG = "regression-2876-plan-hang"
MISSION_ID = "01K2876NONINTERACTIVEHANG0"

# Production-shaped, substantive spec.md: real FR-001/FR-002 rows describing
# the very contract the plan command violates, committed to a real git repo
# (mirrors tests/agent/test_agent_feature.py's `_write_committed_substantive_spec`).
SUBSTANTIVE_SPEC = """# Non-Interactive Plan Invocation

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | `plan` never blocks on stdin under non-interactive mode. | Closed stdin + env var set -> returns within a bounded time. | proposed |
| FR-002 | `plan` never emits an interactive prompt under non-interactive mode. | No hint line / prompt text on stdout; defaults or fail-fast. | proposed |
"""

_TIMEOUT_SECONDS = 10.0


def _setup_repo(tmp_path: Path) -> None:
    """Real git repo + minimal init markers + a committed, substantive spec.md.

    Mirrors ``tests/specify_cli/cli/commands/test_plan_widen.py``'s
    ``_setup_repo`` (the canonical harness for this exact widen-interview
    surface), enriched with a real committed ``spec.md`` carrying FR rows so
    the fixture is production-shaped rather than a bare meta.json stub.
    """
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)

    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text("agents:\n  available: [claude]\n", encoding="utf-8")

    mission_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}),
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text(SUBSTANTIVE_SPEC, encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Spec Kitty Tests",
            "-c",
            "user.email=spec-kitty-tests@example.invalid",
            "commit",
            "-m",
            "Add regression-2876 mission scaffold",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )


def _invoke_plan_non_interactive(tmp_path: Path) -> Result:
    """Drive the real ``plan`` command with a closed stdin, cwd'd into the fixture repo."""
    with (
        contextlib.chdir(tmp_path),
        patch(
            "specify_cli.cli.commands.lifecycle.agent_feature.setup_plan",
            return_value=None,
        ),
        patch(
            "specify_cli.cli.commands.lifecycle.locate_project_root",
            return_value=tmp_path,
        ),
    ):
        return runner.invoke(
            _app,
            ["--mission", MISSION_SLUG],
            input="",  # closed/non-TTY stdin: the agent/CI invocation shape from #2876
            catch_exceptions=True,
        )


def test_plan_non_interactive_never_prompts_or_hangs_2876(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard for the fixed #2876 defect: ``spec-kitty plan`` must
    never emit an interactive prompt (and must never block on stdin) when
    ``SPEC_KITTY_NON_INTERACTIVE=1`` is set — it takes defaults or fails fast
    instead. Was a RED-FIRST P0 reproduction; #2876 is now fixed and this
    test is a permanent guard against the defect recurring.
    """
    monkeypatch.setenv("SPEC_KITTY_NON_INTERACTIVE", "1")
    _setup_repo(tmp_path)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_invoke_plan_non_interactive, tmp_path)
        try:
            result = future.result(timeout=_TIMEOUT_SECONDS)
        except FutureTimeoutError:
            pytest.fail(
                "spec-kitty plan HUNG waiting on stdin under "
                "SPEC_KITTY_NON_INTERACTIVE=1 (#2876): the widen-interview "
                f"prompt loop blocked past the {_TIMEOUT_SECONDS}s bound "
                "instead of taking defaults or failing fast."
            )

    # Defect #1 (the P0): the command must never print an interactive prompt
    # under the non-interactive contract. On buggy main, `run_plan_interview`
    # prints the question hint line and the first question's text via
    # `typer.prompt` regardless of SPEC_KITTY_NON_INTERACTIVE.
    first_question_text = PLAN_WIDEN_QUESTIONS[0][1]
    forbidden_markers = ["[enter]=accept default", first_question_text]
    leaked = [marker for marker in forbidden_markers if marker in result.output]
    assert not leaked, (
        f"spec-kitty plan emitted an interactive prompt under SPEC_KITTY_NON_INTERACTIVE=1 (#2876): {leaked!r} found in captured output:\n{result.output}"
    )
