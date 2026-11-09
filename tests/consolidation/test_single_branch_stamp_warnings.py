"""S8 warnings (#7283, FR-075): ``move-task`` and ``agent status emit`` warn for ``single_branch`` approvals.

ADR ``2026-10-04-5`` Amendment 2026-11-06: the existing unstamped-approval and forced-approval
warnings (``approved_bound.unstamped_approval_warning`` / ``forced_approval_warning``) print for a
``single_branch`` Mission with a minted Mission branch too, so a reviewer learns of a weak approval
before ``consolidate`` refuses it. A commit-to-target Mission is outside the bound (FR-078) and
gets neither warning.

The Mission is built once through the real CLI (``init``, ``agent mission create --topology
single_branch`` on protected ``main``, ``finalize-tasks``) and copied per test; the commands
under test run in-process so the unstamped case can break the best-effort stamp probe.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.status import app as status_app
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.status import lane_head
from tests._support.ansi import strip_ansi

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TARGET = "main"
_CLI = [sys.executable, "-m", "specify_cli"]
_UNSTAMPED = "no lane head could be recorded for {wp}'s approval"
_FORCED = "forced approval of {wp} is not a review approval"
_REVIEW = json.dumps({"reviewer": "bob", "verdict": "approved", "reference": "PR#1"})

runner = CliRunner()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        HOME=str(home / "home"),
        XDG_CONFIG_HOME=str(home / "xc"),
        XDG_CACHE_HOME=str(home / "xcache"),
        XDG_DATA_HOME=str(home / "xd"),
        SPEC_KITTY_NO_UPGRADE_CHECK="1",
    )
    # A protected-branch override would make create skip the Mission-branch mint.
    env.pop("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", None)
    for key in ("home", "xc", "xcache", "xd"):
        (home / key).mkdir(parents=True, exist_ok=True)
    return env


def _sk(repo: Path, env: dict[str, str], *args: str) -> str:
    proc = subprocess.run([*_CLI, *args], cwd=repo, env=env, capture_output=True, text=True, timeout=400)
    if proc.returncode != 0:
        raise AssertionError(f"spec-kitty {' '.join(args)} failed rc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc.stdout


def _wp_file(wp: str, module: str, subtask: str) -> str:
    return (
        f"---\nwork_package_id: {wp}\ntitle: {wp} {module}\ndependencies: []\nrequirement_refs: [FR-001]\n"
        f"authoritative_surface: src/{module}/\nowned_files:\n  - src/{module}/**\nsubtasks:\n  - {subtask}\n---\n"
        f"# {wp} {module}\n\n- [ ] {subtask} do {module}\n"
    )


def _build_template(base: Path, *, commit_to_target: bool) -> tuple[Path, str]:
    env = _env(base)
    repo = base / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    _sk(repo, env, "init", "--ai", "claude", "--non-interactive")
    (repo / "src").mkdir()
    (repo / "src" / "shared.py").write_text("A = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    extra = ("--commit-to-target",) if commit_to_target else ()
    created = _sk(
        repo,
        env,
        *("agent", "mission", "create", "fx", "--mission-type", "software-dev", "--topology", "single_branch", *extra),
        *("--branch-strategy", "already-confirmed", "--target-branch", _TARGET, "--friendly-name", "fx"),
        *("--purpose-tldr", "fx", "--purpose-context", "QA fixture.", "--json"),
    )
    slug = str(json.loads(created)["mission_slug"])
    fd = repo / "kitty-specs" / slug
    (fd / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: things work.\n", encoding="utf-8")
    (fd / "plan.md").write_text("# Plan\n\nModules.\n", encoding="utf-8")
    (fd / "tasks").mkdir(exist_ok=True)
    (fd / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01: m1\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] T1 do m1\n\n"
        "## Work Package WP02: m2\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] T2 do m2\n",
        encoding="utf-8",
    )
    (fd / "tasks" / "WP01-m1.md").write_text(_wp_file("WP01", "m1", "T1"), encoding="utf-8")
    (fd / "tasks" / "WP02-m2.md").write_text(_wp_file("WP02", "m2", "T2"), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "planning")
    _sk(repo, env, "agent", "mission", "finalize-tasks", "--mission", slug, "--json")
    return repo, slug


@pytest.fixture(scope="module")
def minted_template(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    repo, slug = _build_template(tmp_path_factory.mktemp("minted"), commit_to_target=False)
    meta = json.loads((repo / "kitty-specs" / slug / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("mission_branch") not in (None, _TARGET), "fixture: create must mint a Mission branch on protected main"
    return repo, slug


@pytest.fixture(scope="module")
def commit_to_target_template(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    return _build_template(tmp_path_factory.mktemp("ctt"), commit_to_target=True)


def _checkout(template: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    source, slug = template
    repo = tmp_path / "repo"
    shutil.copytree(source, repo, symlinks=True)
    monkeypatch.chdir(repo)
    return repo, slug


def _move(slug: str, wp: str, to: str, agent: str, *extra: str) -> tuple[int, str]:
    result = runner.invoke(tasks_app, ["move-task", wp, "--to", to, "--agent", agent, "--note", f"{to} by {agent}", "--mission", slug, *extra])
    return result.exit_code, strip_ansi(result.output + (result.stderr if result.stderr_bytes is not None else ""))


def _emit(slug: str, wp: str, to: str, actor: str, *extra: str) -> tuple[int, str]:
    result = runner.invoke(status_app, ["emit", wp, "--to", to, "--actor", actor, "--mission", slug, *extra])
    return result.exit_code, strip_ansi(result.output + (result.stderr if result.stderr_bytes is not None else ""))


def _implement(repo: Path, slug: str, wp: str, module: str, subtask: str) -> None:
    """alice claims *wp*, commits real work in its owned files and ticks its subtask."""
    code, out = _move(slug, wp, "in_progress", "alice")
    assert code == 0, out
    target = repo / "src" / module / "real.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"VALUE = {wp!r}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", f"feat({wp}): implement {module}")
    result = runner.invoke(tasks_app, ["mark-status", subtask, "--status", "done", "--mission", slug])
    assert result.exit_code == 0, result.output


def _to_claimed_review(slug: str, wp: str) -> None:
    """Hand *wp* to review: a forced ``for_review`` (the commit gate is not under test), then bob's unforced review claim."""
    code, out = _emit(slug, wp, "for_review", "alice", "--force", "--reason", "handed to review")
    assert code == 0, out
    code, out = _emit(slug, wp, "in_review", "bob")
    assert code == 0, out


@pytest.fixture
def broken_stamp(monkeypatch: pytest.MonkeyPatch) -> None:
    """The best-effort stamp probe finds nothing (a git error, a missing branch): every transition is persisted unstamped."""
    monkeypatch.setattr(lane_head, "_read_lane_head", lambda **_kwargs: lane_head.LaneHeadReading.not_applicable())


def test_unstamped_single_branch_approval_warns(minted_template: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, broken_stamp: None) -> None:
    """FR-075: an approval persisted with no stamp warns on both surfaces, ``agent status emit`` and ``move-task``."""
    repo, slug = _checkout(minted_template, tmp_path, monkeypatch)

    _implement(repo, slug, "WP01", "m1", "T1")
    _to_claimed_review(slug, "WP01")
    code, out = _emit(slug, "WP01", "approved", "bob", "--review-result-json", _REVIEW)
    assert code == 0, out
    assert _UNSTAMPED.format(wp="WP01") in out

    _implement(repo, slug, "WP02", "m2", "T2")
    _to_claimed_review(slug, "WP02")
    # A reviewer's forced verdict on a claimed review is a review approval, so it is judged on its stamp.
    code, out = _move(slug, "WP02", "approved", "bob", "--force")
    assert code == 0, out
    assert _UNSTAMPED.format(wp="WP02") in out
    assert _FORCED.format(wp="WP02") not in out


def test_stamped_single_branch_approval_does_not_warn(minted_template: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: with the stamp probe working, the same review approval is stamped and prints no warning."""
    repo, slug = _checkout(minted_template, tmp_path, monkeypatch)

    _implement(repo, slug, "WP01", "m1", "T1")
    _to_claimed_review(slug, "WP01")
    code, out = _emit(slug, "WP01", "approved", "bob", "--review-result-json", _REVIEW)

    assert code == 0, out
    assert "Warning:" not in out


def test_forced_single_branch_approval_warns(minted_template: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-075: a forced approval that records no review warns on ``move-task`` and on ``agent status emit``."""
    repo, slug = _checkout(minted_template, tmp_path, monkeypatch)

    _implement(repo, slug, "WP01", "m1", "T1")
    code, out = _move(slug, "WP01", "approved", "bob", "--force")
    assert code == 0, out
    assert _FORCED.format(wp="WP01") in out

    _implement(repo, slug, "WP02", "m2", "T2")
    code, out = _emit(slug, "WP02", "approved", "bob", "--force", "--reason", "operator restamp")
    assert code == 0, out
    assert _FORCED.format(wp="WP02") in out


def test_commit_to_target_single_branch_approval_does_not_warn(
    commit_to_target_template: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, broken_stamp: None
) -> None:
    """FR-078: a commit-to-target Mission is outside the bound, so neither warning prints for it."""
    repo, slug = _checkout(commit_to_target_template, tmp_path, monkeypatch)

    _implement(repo, slug, "WP01", "m1", "T1")
    code, out = _move(slug, "WP01", "approved", "bob", "--force")

    assert code == 0, out
    assert _FORCED.format(wp="WP01") not in out
    assert "Warning: no lane head" not in out
