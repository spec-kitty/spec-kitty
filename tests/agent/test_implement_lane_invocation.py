"""``implement`` and the prompts carry the lane test invocation (mission lane-code-verification #7547, WP02).

FR-001 / SC-001: ``spec-kitty implement WP## --json`` returns ``lane_test_invocation`` (cwd, declared
command, environment changes, probe). Run with exactly that working directory and environment, a
Python started from the lane -- and every process it spawns -- loads the lane's code, while the
repository root checkout's activated venv with the inherited environment loads the root's code from
the same lane (#1907 / #7547). NFR-002: every pre-existing key keeps its meaning.

FR-005 / SC-003: the implement and review prompts state the same invocation, re-derived and
re-probed from the resolved workspace at render time.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import workflow, workflow_executor
from specify_cli.review.cycle import review_feedback_source_path
from specify_cli.review.lane_test_invocation import LANE_TEST_INVOCATION_HEADER
from specify_cli.task_utils import WorkPackage
from specify_cli.workspace.context import ResolvedWorkspace
from tests.agent.test_workflow_review_lane_gate import _prompt_path_from_output, _setup_implement_fixture, _setup_review_fixture
from tests.lane_test_utils import lane_worktree_path
from tests.specify_cli.cli.commands.test_implement_characterization import (
    ARGS,
    LANE_BRANCH,
    LANE_WORKTREE,
    MISSION_ID,
    SLUG,
    activate_repo,
    build_mission,
    git,
    implement_cli,
    init_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TEST_COMMAND = 'PYTEST_ADDOPTS="--junitxml={output_file}" python -m pytest -q'
_REDIRECT_KEYS = ("PYTHONPATH", "UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV")
# Prints the package value, then spawns a grandchild (inheriting this environment) that does the same.
_CHILD_SCRIPT = "import subprocess, sys\nimport pkg\nprint(pkg.V, flush=True)\nsubprocess.run([sys.executable, '-c', 'import pkg; print(pkg.V)'], check=True)\n"


def _bin_dir(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin")


def _root_venv(root: Path) -> Path:
    """A venv in the repository root checkout whose install points at ``root/src`` (an editable-style ``.pth``)."""
    venv = root / ".venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True, capture_output=True)
    python = shutil.which("python", path=str(_bin_dir(venv)))
    assert python is not None
    purelib = subprocess.run([python, "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"], check=True, capture_output=True, text=True).stdout.strip()
    Path(purelib, "root_src.pth").write_text(f"{root / 'src'}\n", encoding="utf-8")
    return venv


@pytest.fixture()
def planted_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A lanes Mission in a repository root checkout that ships ``src/pkg`` (``V = 1``) and an activated root venv."""
    root = init_repo(tmp_path / "repo")
    activate_repo(root, monkeypatch, tmp_path)
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text("V = 1\n", encoding="utf-8")
    (root / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    (root / ".kittify" / "config.yaml").write_text(f"review:\n  test_command: '{_TEST_COMMAND}'\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "project source")
    build_mission(root, SLUG, MISSION_ID)
    venv = _root_venv(root)
    for key in _REDIRECT_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("VIRTUAL_ENV", str(venv))
    monkeypatch.setenv("PATH", f"{_bin_dir(venv)}{os.pathsep}{os.environ['PATH']}")
    return root


def _invoke_json() -> dict[str, Any]:
    result = implement_cli(*ARGS, "--json")
    assert result.exit_code == 0, result.output
    payload: dict[str, Any] = json.loads(result.stdout)
    return payload


def _environ(invocation: dict[str, Any]) -> dict[str, str]:
    """``base env - env_unset + env_set``, ``path_prepend`` before ``PATH``, as the contract states."""
    env = {key: value for key, value in os.environ.items() if key not in invocation["env_unset"]}
    env.update(invocation["env_set"])
    env["PATH"] = os.pathsep.join([*invocation["path_prepend"], *([env["PATH"]] if env.get("PATH") else [])])
    return env


def _run_child(cwd: str, env: dict[str, str]) -> list[str]:
    python = shutil.which("python", path=env["PATH"])
    assert python is not None
    completed = subprocess.run([python, "-c", _CHILD_SCRIPT], cwd=cwd, env=env, capture_output=True, text=True, check=True)
    return completed.stdout.split()


# ---------------------------------------------------------------------------
# implement --json (FR-001, SC-001, NFR-002)
# ---------------------------------------------------------------------------


def test_implement_json_invocation_loads_the_planted_lane_change_in_child_and_grandchild(planted_repo: Path) -> None:
    """Planted break (proven red): drop the key, or leave ``PYTHONPATH=<lane>/src`` out of ``env_set``."""
    payload = _invoke_json()
    invocation = payload["lane_test_invocation"]
    lane = planted_repo / LANE_WORKTREE

    assert invocation["cwd"] == str(lane)
    assert invocation["command"] == _TEST_COMMAND
    assert invocation["probe"]["status"] == "verified"
    assert invocation["probe"]["origins"] == {"pkg": str(lane / "src" / "pkg" / "__init__.py")}

    (lane / "src" / "pkg" / "__init__.py").write_text("V = 2\n", encoding="utf-8")

    assert _run_child(invocation["cwd"], _environ(invocation)) == ["2", "2"]
    # The same fixture, the root venv's interpreter with the inherited environment, run from the lane:
    assert _run_child(invocation["cwd"], dict(os.environ)) == ["1", "1"]


def test_implement_json_keeps_every_pre_existing_key(planted_repo: Path) -> None:
    payload = _invoke_json()

    assert {key: value for key, value in payload.items() if key != "lane_test_invocation"} == {
        "workspace": LANE_WORKTREE,
        "workspace_path": LANE_WORKTREE,
        "branch": LANE_BRANCH,
        "mission_slug": SLUG,
        "mission_number": None,
        "mission_type": "software-dev",
        "wp_id": "WP01",
        "lane_id": "lane-a",
        "execution_mode": "code_change",
        "status": "created",
        "lane_test_env": {"SPEC_KITTY_TEST_DB_NAME": "test_demo_mission_lane_a"},
    }


def test_implement_banner_prints_the_lane_test_invocation(planted_repo: Path) -> None:
    result = implement_cli(*ARGS)

    assert result.exit_code == 0, result.output
    lane = planted_repo / LANE_WORKTREE
    assert LANE_TEST_INVOCATION_HEADER in result.output
    assert f"cd {lane}" in result.output
    assert "unset PYTHONPATH UV_PROJECT_ENVIRONMENT VIRTUAL_ENV" in result.output
    assert _TEST_COMMAND in result.output
    assert "probe: verified — pkg → src/pkg/__init__.py" in result.output


def test_implement_json_for_planning_artifact_work_has_a_null_invocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = init_repo(tmp_path / "repo")
    activate_repo(root, monkeypatch, tmp_path)
    build_mission(root, SLUG, MISSION_ID, topology="single_branch", wps={"WP01": ("planning_artifact", [])})

    payload = _invoke_json()

    assert payload["lane_test_invocation"] is None


def _raise_from_the_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("probe exploded")

    monkeypatch.setattr("specify_cli.cli.commands.implement.workspace_lane_test_invocation", boom)


def test_an_adapter_failure_never_fails_implement_after_the_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review cycle 1, item 2: fail-open like the prompts; the banner states the failure as an unverified probe."""
    root = init_repo(tmp_path / "repo")
    activate_repo(root, monkeypatch, tmp_path)
    build_mission(root, SLUG, MISSION_ID)
    _raise_from_the_adapter(monkeypatch)

    result = implement_cli(*ARGS)

    assert result.exit_code == 0, result.output
    assert "✓ Lane worktree ready" in result.output
    assert LANE_TEST_INVOCATION_HEADER in result.output
    assert "probe: unverified — could not build the lane test invocation: probe exploded" in result.output


def test_an_adapter_failure_yields_a_null_json_invocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = init_repo(tmp_path / "repo")
    activate_repo(root, monkeypatch, tmp_path)
    build_mission(root, SLUG, MISSION_ID)
    _raise_from_the_adapter(monkeypatch)

    payload = _invoke_json()

    assert payload["status"] == "created"
    assert payload["lane_test_invocation"] is None


def test_single_branch_code_work_gets_an_invocation_rooted_at_the_write_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = init_repo(tmp_path / "repo")
    activate_repo(root, monkeypatch, tmp_path)
    build_mission(root, SLUG, MISSION_ID, topology="single_branch")

    result = implement_cli(*ARGS)
    payload = _invoke_json()

    assert result.exit_code == 0, result.output
    assert LANE_TEST_INVOCATION_HEADER in result.output
    assert payload["lane_test_invocation"]["cwd"] == str(root)
    assert "SPEC_KITTY_TEST_DB_NAME" not in payload["lane_test_invocation"]["env_set"]


# ---------------------------------------------------------------------------
# build_review_prompt_lines (FR-005, SC-003)
# ---------------------------------------------------------------------------

_REVIEW_SLUG = "001-review-invocation"


def _review_wp(repo: Path) -> WorkPackage:
    path = repo / "kitty-specs" / _REVIEW_SLUG / "tasks" / "WP01-core.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nwork_package_id: WP01\n---\n\n# WP01\n", encoding="utf-8")
    return WorkPackage(
        feature=_REVIEW_SLUG,
        path=path,
        current_lane="for_review",
        relative_subpath=Path("tasks") / "WP01-core.md",
        frontmatter="---\nwork_package_id: WP01\n---\n",
        body="# WP01\n",
        padding="",
    )


def _review_workspace(
    worktree: Path, *, execution_mode: str = "code_change", lane_id: str = "lane-a", resolution_kind: str = "lane_workspace"
) -> ResolvedWorkspace:
    return ResolvedWorkspace(
        mission_slug=_REVIEW_SLUG,
        wp_id="WP01",
        execution_mode=execution_mode,
        mode_source="test",
        resolution_kind=resolution_kind,
        workspace_name=worktree.name,
        worktree_path=worktree,
        branch_name=f"kitty/mission-{_REVIEW_SLUG}-{lane_id}",
        lane_id=lane_id,
        lane_wp_ids=["WP01"],
    )


def _review_prompt(repo: Path, workspace: ResolvedWorkspace, monkeypatch: pytest.MonkeyPatch) -> str:
    """The real ``REVIEW`` body; only the lookups that need a populated Mission are stubbed."""
    monkeypatch.setattr(workflow_executor, "render_charter_context_text", lambda *_a, **_k: "")
    monkeypatch.setattr(workflow_executor, "_review_baseline_context_lines", lambda **_k: [])
    monkeypatch.setattr(workflow_executor, "resolve_review_completion_reviewer", lambda **_k: "reviewer")
    monkeypatch.setattr(workflow_executor, "shared_artifact_guidance", lambda *_a, **_k: [])
    wp = _review_wp(repo)
    lines = workflow_executor.build_review_prompt_lines(
        normalized_wp_id="WP01",
        wp=wp,
        workspace=workspace,
        workspace_path=workspace.worktree_path,
        review_agent_assignment=None,
        repo_root=repo,
        mission_slug=_REVIEW_SLUG,
        target_branch="main",
        dependents_warning=[],
        review_ctx={"base_branch": "unknown", "branch_name": "b", "commit_count": 0},
        main_repo_root=repo,
        review_feedback_path=review_feedback_source_path(wp.path.parent, 1),
    )
    return "\n".join(lines)


def test_review_prompt_states_the_lane_test_invocation_and_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    lane = repo / ".worktrees" / f"{_REVIEW_SLUG}-lane-a"
    (lane / "src" / "pkg").mkdir(parents=True)
    (lane / "src" / "pkg" / "__init__.py").write_text("V = 1\n", encoding="utf-8")
    git_init = ["git", "-C", str(lane)]
    subprocess.run([*git_init, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git_init, "add", "-A"], check=True)
    subprocess.run([*git_init, "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-q", "-m", "seed"], check=True)
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("review:\n  test_command: make test-fast\n", encoding="utf-8")

    text = _review_prompt(repo, _review_workspace(lane), monkeypatch)

    assert LANE_TEST_INVOCATION_HEADER in text
    assert f"   cd {lane}" in text
    assert "   make test-fast" in text
    assert "   probe: verified — pkg → src/pkg/__init__.py" in text


def test_review_prompt_for_planning_artifact_work_has_no_invocation_block(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    workspace = _review_workspace(repo, execution_mode="planning_artifact", lane_id="lane-planning", resolution_kind="repo_root")

    assert LANE_TEST_INVOCATION_HEADER not in _review_prompt(repo, workspace, monkeypatch)


# ---------------------------------------------------------------------------
# End to end: agent action implement + review write the block into their prompt files
# ---------------------------------------------------------------------------


@pytest.fixture()
def action_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The ``workflow.app`` harness of ``test_workflow_review_lane_gate`` (fake lane ``.git``, no real worktree)."""
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text(
        "vcs:\n  type: git\nproject:\n  uuid: test-project-uuid\n  slug: test-project\nreview:\n  test_command: make test-fast\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("specify_cli.cli.commands.agent.workflow._ensure_target_branch_checked_out", lambda repo_root, mission_slug: (repo_root, "main"))
    monkeypatch.setattr("specify_cli.cli.commands.agent.workflow.safe_commit", lambda **kwargs: True)
    return tmp_path


@pytest.mark.parametrize(("action", "setup", "agent"), [("implement", _setup_implement_fixture, "test-agent"), ("review", _setup_review_fixture, "test-reviewer")])
def test_action_prompt_file_carries_the_lane_test_invocation(action_repo: Path, action: str, setup: Any, agent: str) -> None:
    _wp_path, mission_slug = setup(action_repo)

    result = CliRunner().invoke(workflow.app, [action, "WP01", "--mission", mission_slug, "--agent", agent])

    assert result.exit_code == 0, result.stdout
    content = _prompt_path_from_output(result.stdout).read_text(encoding="utf-8")
    assert LANE_TEST_INVOCATION_HEADER in content
    assert f"   cd {lane_worktree_path(action_repo, mission_slug)}" in content
    assert "   make test-fast" in content
    # The harness fakes the lane's ``.git``, so nothing can be verified there; the probe still reports.
    assert "   probe: unverified — " in content
