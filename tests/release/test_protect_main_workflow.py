"""Regression tests for the protect-main merge compliance shell logic."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "protect-main.yml"


def _protect_main_script() -> str:
    lines = WORKFLOW_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    script_lines: list[str] = []
    in_script = False

    for line in lines:
        if line == "        run: |\n":
            in_script = True
            continue
        if not in_script:
            continue
        if line.startswith("          "):
            script_lines.append(line[10:])
        elif line.strip() == "":
            script_lines.append("\n")
        else:
            break

    assert script_lines, "protect-main workflow run block was not found"
    return (
        "".join(script_lines)
        .replace("${{ github.event.before }}", "1111111111111111111111111111111111111111")
        .replace("${{ github.repository }}", "spec-kitty/spec-kitty")
    )


def _run_protect_main(
    tmp_path: Path,
    message: str,
    committer: str = "A Contributor",
    merged_pr: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "HEAD_COMMIT_MESSAGE": message,
            "HEAD_COMMITTER_NAME": committer,
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        }
    )
    # The workflow resolves MERGED_PR_FOR_HEAD from the commits->pulls API when
    # unset; injecting it directly exercises the rebase-merge decision without a
    # live API call (HEAD_SHA is left unset, so the API branch is never entered).
    if merged_pr is not None:
        env["MERGED_PR_FOR_HEAD"] = merged_pr
    return subprocess.run(
        ["bash"],
        input=f"set -euo pipefail\n{_protect_main_script()}",
        text=True,
        capture_output=True,
        env=env,
        cwd=REPO_ROOT,
        check=False,
    )


@pytest.mark.parametrize(
    "message",
    [
        "feat: release fix (#123)",
        "feat: release fix (#123)\n\nBody copied from the pull request.",
        "Merge pull request #123 from Priivacy-ai/example\n\nfeat: release fix",
    ],
)
def test_protect_main_accepts_pr_merge_subjects(tmp_path: Path, message: str) -> None:
    result = _run_protect_main(tmp_path, message)

    assert result.returncode == 0, result.stderr + result.stdout


@pytest.mark.parametrize(
    "message",
    [
        "feat: rework foo (see #123 for context)",
        "feat: rework foo (#123) in prose",
        "feat: direct push without PR suffix\n\nRefs (#123)",
    ],
)
def test_protect_main_rejects_issue_references_outside_subject_suffix(tmp_path: Path, message: str) -> None:
    result = _run_protect_main(tmp_path, message)

    assert result.returncode == 1
    assert "Direct push to main branch detected" in result.stderr + result.stdout


@pytest.mark.parametrize(
    "message",
    [
        "fix(landing): raise a typed error when the pre-image restore fails",
        "feat: a rebase-merged commit keeps its original subject\n\nNo PR suffix here.",
    ],
)
def test_protect_main_accepts_rebase_merge_when_commit_belongs_to_merged_pr(tmp_path: Path, message: str) -> None:
    # Rebase-and-merge replays the PR's commits verbatim (no "(#PR)" suffix,
    # author is the committer). The workflow accepts them via the commit's PR
    # association, injected here as MERGED_PR_FOR_HEAD.
    result = _run_protect_main(tmp_path, message, merged_pr="3791")

    assert result.returncode == 0, result.stderr + result.stdout
    assert "rebase merge" in result.stdout


def test_protect_main_rejects_rebase_shaped_subject_with_no_merged_pr(tmp_path: Path) -> None:
    # The same rebase-shaped subject with NO PR association is a genuine direct
    # push and must still be rejected -- content alone never grants acceptance.
    result = _run_protect_main(
        tmp_path,
        "fix(landing): raise a typed error when the pre-image restore fails",
        merged_pr="",
    )

    assert result.returncode == 1
    assert "Direct push to main branch detected" in result.stderr + result.stdout
