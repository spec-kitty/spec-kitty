"""``spec-kitty retrospect create`` must not sweep the operator's staged index onto protected ``main``.

Regression guard for #5479 (item 4, folded in from #5442). PR #5495 fixed the
defect; both tests were written red-first and failed on the pre-fix code
(``795b2acf10^``). They pin what #5495's own tests leave open: unrelated work the
operator had staged, and the protected-``main`` refusal on a ``lanes`` mission
(#5495 covers that refusal on a ``coord`` mission only).

The fixture follows the #5442 reproduction: a real ``spec-kitty init`` project on
``main`` (the protected primary branch), a real ``lanes`` mission created and
finalized through the CLI, its only WP canceled through ``agent status emit``.
The operator then stages unrelated work (``src/wip.py``) and runs
``spec-kitty retrospect create`` as a subprocess, with
``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` unset. Nothing is patched.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

RunCli = Callable[..., subprocess.CompletedProcess[str]]

_HATCH = "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"
_WIP_REL = "src/wip.py"
_WP01 = """---
work_package_id: WP01
title: one
dependencies: []
requirement_refs: [FR-001]
authoritative_surface: src/one/
owned_files:
  - src/one/**
subtasks:
  - T001
---
# WP01

- [ ] T001 do it
"""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _ok(result: subprocess.CompletedProcess[str], step: str) -> subprocess.CompletedProcess[str]:
    assert result.returncode == 0, f"fixture step {step!r} failed (exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
    return result


def _protected_main_with_completed_mission(tmp_path: Path, run_cli: RunCli, isolated_env: dict[str, str]) -> tuple[Path, str]:
    """A ``spec-kitty init`` project on ``main`` with one finalized ``lanes`` mission whose only WP is canceled."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "qa")
    _git(repo, "config", "user.email", "qa@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    _ok(run_cli(repo, "init", "--ai", "claude", "--non-interactive"), "init")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("A = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    # Mission creation and planning commits need the operator hatch on main (by design).
    isolated_env[_HATCH] = "1"
    created = _ok(
        run_cli(
            repo,
            "agent",
            "mission",
            "create",
            "demo",
            "--mission-type",
            "software-dev",
            "--topology",
            "lanes",
            "--branch-strategy",
            "already-confirmed",
            "--target-branch",
            "main",
            "--friendly-name",
            "Demo",
            "--purpose-tldr",
            "demo",
            "--purpose-context",
            "P0 reproduction fixture",
            "--json",
        ),
        "agent mission create",
    )
    slug = str(json.loads(created.stdout)["mission_slug"])
    mission_dir = repo / "kitty-specs" / slug
    (mission_dir / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: works.\n", encoding="utf-8")
    (mission_dir / "plan.md").write_text("# Plan\n\nOne module.\n", encoding="utf-8")
    (mission_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01: one\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n",
        encoding="utf-8",
    )
    (mission_dir / "tasks").mkdir(exist_ok=True)
    (mission_dir / "tasks" / "WP01-one.md").write_text(_WP01, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning")
    _ok(run_cli(repo, "agent", "mission", "finalize-tasks", "--mission", slug, "--json"), "finalize-tasks")
    _ok(
        run_cli(repo, "agent", "status", "emit", "WP01", "--to", "canceled", "--actor", "qa", "--mission", slug, "--reason", "descoped"),
        "status emit canceled",
    )
    _git(repo, "add", "-A")
    if _git(repo, "status", "--porcelain"):
        _git(repo, "commit", "-q", "-m", "fixture residue")

    # From here on the operator is on protected main without the hatch.
    isolated_env.pop(_HATCH, None)
    assert _git(repo, "branch", "--show-current") == "main"
    assert _git(repo, "status", "--porcelain") == "", "fixture must leave a clean checkout"
    return repo, slug


def _stage_unrelated_work(repo: Path) -> None:
    """The operator has unrelated work staged (half-reviewed) when the retrospective is written."""
    (repo / _WIP_REL).write_text('SECRET_WIP = "not ready"\n', encoding="utf-8")
    _git(repo, "add", "--", _WIP_REL)


@pytest.mark.regression
def test_retrospect_create_leaves_the_operators_staged_work_out_of_its_commit(tmp_path: Path, run_cli: RunCli, isolated_env: dict[str, str]) -> None:
    """Regression guard for #5479 / #5442.

    Invariant: whatever the operator had staged for
    unrelated work is not part of any commit ``retrospect create`` makes, and is
    still staged (and uncommitted) after the command returns.
    """
    repo, slug = _protected_main_with_completed_mission(tmp_path, run_cli, isolated_env)
    _stage_unrelated_work(repo)
    head_before = _git(repo, "rev-parse", "HEAD")

    result = run_cli(repo, "retrospect", "create", "--mission", slug, "--json")

    assert result.returncode == 0, result.stderr
    swept = [sha for sha in _git(repo, "rev-list", f"{head_before}..HEAD").split() if _WIP_REL in _git(repo, "show", "--name-only", "--format=", sha).splitlines()]
    assert not swept, (
        f"retrospect create swept the operator's staged {_WIP_REL} into "
        f"{_git(repo, 'log', '-1', '--format=%h %s', swept[0])!r} on branch {_git(repo, 'branch', '--show-current')!r}"
    )
    assert _git(repo, "diff", "--cached", "--name-only", "--", _WIP_REL) == _WIP_REL, f"{_WIP_REL} must still be staged"


@pytest.mark.regression
def test_retrospect_create_does_not_commit_onto_protected_main_without_the_hatch(tmp_path: Path, run_cli: RunCli, isolated_env: dict[str, str]) -> None:
    """Regression guard for #5479 / #5442.

    Invariant: on protected ``main`` without
    ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS``, ``retrospect create`` makes no
    commit on ``main``; it warns or refuses, exactly as ``spec-commit`` does
    (asserted first as the control).
    """
    repo, slug = _protected_main_with_completed_mission(tmp_path, run_cli, isolated_env)
    _stage_unrelated_work(repo)
    main_before = _git(repo, "rev-parse", "main")

    # Control: the bookkeeping writer that honours the contract refuses here.
    spec = repo / "kitty-specs" / slug / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "more\n", encoding="utf-8")
    control = run_cli(repo, "spec-commit", f"kitty-specs/{slug}/spec.md", "-m", "spec edit", "--json")
    assert control.returncode != 0, f"control: spec-commit must refuse on protected main:\n{control.stdout}\n{control.stderr}"
    assert _git(repo, "rev-parse", "main") == main_before, "control: spec-commit must not move main"
    _git(repo, "checkout", "-q", "--", f"kitty-specs/{slug}/spec.md")

    result = run_cli(repo, "retrospect", "create", "--mission", slug, "--json")

    landed = _git(repo, "log", "--format=%h %s", f"{main_before}..main")
    assert landed == "", f"retrospect create committed onto protected 'main' that spec-commit refused (no {_HATCH}):\n{landed}\nexit={result.returncode}"
