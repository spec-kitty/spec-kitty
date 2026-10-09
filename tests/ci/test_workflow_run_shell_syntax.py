"""Every workflow ``run:`` script must parse as bash and use single-backslash continuations (#3732).

A ``run: |`` block scalar keeps every character, so a continuation line written as ``\\\\``
(two backslashes) reaches bash as an escaped literal backslash: the newline after it ends the
command, the remaining "arguments" run as commands of their own, and the step fails. The
selection parsers in this directory tokenize paths and never run the shell, so they cannot see
it (WP03 review cycle 2 found exactly this in ``tests-corpus-blocking``).

This guard extracts each ``run:`` script with ``yaml.safe_load`` and

* rejects any line whose trailing backslash run has an even length >= 2 (a doubled
  continuation; a lone ``\\`` is a continuation, three is an escaped backslash plus one);
* runs ``bash -n`` over it (skipped when bash is unavailable). Steps whose effective
  ``shell:`` is not bash (``pwsh``, ``python``, ...) are skipped.

Self-tests plant a bad script to prove both checks are load-bearing.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.fast

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
BASH = shutil.which("bash")
_TRAILING_BACKSLASHES = re.compile(r"(\\+)$")


@dataclass(frozen=True)
class RunStep:
    workflow: str
    job: str
    index: int
    script: str

    @property
    def label(self) -> str:
        return f"{self.workflow}:{self.job}:steps[{self.index}]"


def _default_shell(node: dict[str, Any]) -> str | None:
    defaults = node.get("defaults") or {}
    run = defaults.get("run") or {}
    shell = run.get("shell")
    return str(shell) if shell is not None else None


def _is_bash(shell: str | None, runs_on: object) -> bool:
    if shell is None:
        # No shell key: bash on Linux/macOS runners, pwsh on Windows runners.
        return "windows" not in str(runs_on).lower()
    return shell.split()[0] in {"bash", "sh"}


def collect_run_steps(workflow: Path) -> list[RunStep]:
    """Every bash ``run:`` script of one workflow file."""
    doc = yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}
    workflow_shell = _default_shell(doc)
    steps: list[RunStep] = []
    for job_name, job in (doc.get("jobs") or {}).items():
        job_shell = _default_shell(job) or workflow_shell
        for index, step in enumerate(job.get("steps") or []):
            if "run" not in step:
                continue
            shell = step.get("shell") or job_shell
            if not _is_bash(shell, job.get("runs-on")):
                continue
            steps.append(RunStep(workflow.name, str(job_name), index, str(step["run"])))
    return steps


def doubled_continuations(script: str) -> list[str]:
    """Lines ending in an even run (>= 2) of backslashes: a broken continuation."""
    bad: list[str] = []
    for line in script.splitlines():
        match = _TRAILING_BACKSLASHES.search(line)
        if match and len(match.group(1)) >= 2 and len(match.group(1)) % 2 == 0:
            bad.append(line)
    return bad


def bash_syntax_error(script: str) -> str | None:
    """``bash -n`` diagnostics for *script*, or ``None`` when it parses."""
    assert BASH is not None
    result = subprocess.run([BASH, "-n"], input=script, text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return None
    return result.stderr.strip() or f"exit {result.returncode}"


def _all_run_steps() -> list[RunStep]:
    steps: list[RunStep] = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        steps.extend(collect_run_steps(workflow))
    return steps


ALL_RUN_STEPS = _all_run_steps()


def test_run_steps_were_found() -> None:
    # Non-vacuity: the guard must actually see the workflows it protects.
    assert len(ALL_RUN_STEPS) > 50
    assert any(s.job == "tests-corpus-blocking" for s in ALL_RUN_STEPS)


def test_no_doubled_backslash_continuations() -> None:
    offenders = {s.label: bad for s in ALL_RUN_STEPS if (bad := doubled_continuations(s.script))}
    assert not offenders, f"run: lines ending in a doubled backslash (use a single \\): {offenders}"


@pytest.mark.skipif(BASH is None, reason="bash unavailable")
def test_every_run_step_parses_as_bash() -> None:
    offenders = {s.label: err for s in ALL_RUN_STEPS if (err := bash_syntax_error(s.script))}
    assert not offenders, f"run: scripts that fail bash -n: {offenders}"


_PLANTED_WORKFLOW = """\
name: planted
on: push
jobs:
  bad:
    runs-on: ubuntu-24.04
    steps:
      - run: |
          uv run --frozen pytest -m "corpus" \\
            tests/a.py \\\\
            tests/b.py
      - run: |
          if true; then echo unterminated
      - shell: pwsh
        run: |
          Write-Host "not bash" \\\\
  windows:
    runs-on: windows-latest
    steps:
      - run: |
          Write-Host "default pwsh" \\\\
"""


def test_self_test_planted_bad_workflow_is_caught(tmp_path: Path) -> None:
    workflow = tmp_path / "planted.yml"
    workflow.write_text(_PLANTED_WORKFLOW, encoding="utf-8")
    steps = collect_run_steps(workflow)
    # The pwsh steps (explicit, and a Windows runner's default) are out of scope.
    assert [(s.job, s.index) for s in steps] == [("bad", 0), ("bad", 1)]
    flagged = doubled_continuations(steps[0].script)
    assert len(flagged) == 1
    assert flagged[0].strip() == "tests/a.py \\\\"
    assert doubled_continuations(steps[1].script) == []
    if BASH is not None:
        assert bash_syntax_error(steps[1].script) is not None


def test_self_test_continuation_shapes() -> None:
    assert doubled_continuations("a \\\nb") == []
    assert doubled_continuations("a \\\\\nb") == ["a \\\\"]
    assert doubled_continuations("a \\\\\\\nb") == []  # escaped backslash + continuation
    assert doubled_continuations("echo 'x'\n") == []
