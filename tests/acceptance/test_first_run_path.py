"""Public first-run tutorial contracts forward-ported from hotfix #4051.

Run real subprocesses in temporary Git repositories through init, mission
creation, substantive spec authoring, spec-commit and plan. Main deliberately
permits protected-branch creation with disclosed uncommitted artifacts; users
continue that same mission after switching branches. No stable version or
historical failure count is assumed here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TIMEOUT = 300


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _cli(cwd: Path, *args: str, python: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Invoke the CLI the way a user does — a separate process, real argv.

    ``python -m specify_cli`` rather than a ``spec-kitty`` from PATH: PATH may
    hold a different (often stale) install, which would silently test the wrong
    code. See the stale-install gotcha in CLAUDE.md.
    """
    env = dict(os.environ)
    if python is None:
        env["PYTHONPATH"] = str(_REPO_ROOT / "src")
    else:
        for key in ("PYTHONPATH", "SPEC_KITTY_TEMPLATE_ROOT", "SPEC_KITTY_TEST_MODE", "SPEC_KITTY_CLI_VERSION"):
            env.pop(key, None)
    # Assign, never setdefault: an inherited SPEC_KITTY_HOME would otherwise leak a
    # developer's real home into the test (home-pin gate, SKH-SETDEFAULT).
    env["SPEC_KITTY_HOME"] = str(cwd / ".spec-kitty-home")
    return subprocess.run(
        [str(python) if python is not None else sys.executable, "-m", "specify_cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=_TIMEOUT,
        env=env,
        stdin=subprocess.DEVNULL,
    )


def _missions(repo: Path) -> list[str]:
    specs = repo / "kitty-specs"
    return sorted(entry.name for entry in specs.iterdir() if entry.is_dir()) if specs.exists() else []


def _declared_coordination_branch(repo: Path, mission: str) -> str | None:
    meta = json.loads((repo / "kitty-specs" / mission / "meta.json").read_text(encoding="utf-8"))
    value = meta.get("coordination_branch")
    return str(value) if value else None


def _ref_exists(repo: Path, ref: str) -> bool:
    return subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=repo, capture_output=True, check=False).returncode == 0


def _unwrapped(result: subprocess.CompletedProcess[str]) -> str:
    """Combined stdout+stderr with wrapping collapsed.

    Rich hard-wraps console output at the terminal width, so a phrase like
    "protected branch" arrives split across a newline. Matching raw output makes
    a message assertion fail (or, worse, pass only at some widths).
    """
    return " ".join((result.stdout + " " + result.stderr).split())


def _porcelain(repo: Path) -> str:
    return subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """An initialized project with one commit, sitting on ``main``.

    Mirrors the corrected Getting Started steps 1-3. Step 4 (the working
    branch) is deliberately left to each test, because whether it happened is
    the thing several of these are about.
    """
    repo = tmp_path / "my-spec-project"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    init = _cli(repo, "init", ".", "--ai", "claude")
    assert init.returncode == 0, f"`spec-kitty init` failed:\n{init.stdout}\n{init.stderr}"
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "Initial commit")
    return repo


# ---------------------------------------------------------------------------
# #3988 — the documented first-run path must actually work
# ---------------------------------------------------------------------------


def test_documented_getting_started_path_succeeds(project: Path) -> None:
    """Getting Started, verbatim, produces one sound mission.

    "Sound" is the load-bearing word: a mission whose declared coordination
    branch does not exist is the #4033 defect, and it reported success.
    """
    _git(project, "checkout", "-b", "my-first-mission")

    result = _cli(project, "specify", "Build a tiny command-line task list app with add, complete, and delete actions.")

    assert result.returncode == 0, f"the documented path failed:\n{result.stdout}\n{result.stderr}"
    missions = _missions(project)
    assert len(missions) == 1, f"expected exactly one mission, got {missions}"

    branch = _declared_coordination_branch(project, missions[0])
    assert branch is not None
    assert _ref_exists(project, branch), f"meta.json declares {branch!r}, which does not exist in git"


def test_plan_runs_on_the_mission_the_tutorial_creates(project: Path) -> None:
    """The next documented command also works — the mission is usable, not just present."""
    _git(project, "checkout", "-b", "my-first-mission")
    assert _cli(project, "specify", "Build a tiny command-line task list app.").returncode == 0

    mission = _missions(project)[0]
    # The agent's specify workflow authors and commits the specification after
    # CLI scaffold creation. Exercise that documented boundary with real Git.
    spec_file = project / "kitty-specs" / mission / "spec.md"
    spec_file.write_text(
        "# Task List Specification\n\n"
        "## Functional Requirements\n\n"
        "- **FR-001**: Users can add a task with a non-empty title.\n"
        "- **FR-002**: Users can mark an existing task complete.\n"
        "- **FR-003**: Users can delete an existing task by its identifier.\n\n"
        "## Acceptance Scenarios\n\n"
        "Adding a task preserves its title and assigns a stable identifier.\n"
        "Completing that identifier marks only that task complete.\n"
        "Deleting that identifier removes it from the task list.\n",
        encoding="utf-8",
    )
    committed = _cli(
        project,
        "spec-commit",
        "--mission",
        mission,
        "--message",
        "Add task list specification",
        str(spec_file),
        "--json",
    )
    assert committed.returncode == 0, _unwrapped(committed)
    tracked_spec = _git(project, "show", f"HEAD:{spec_file.relative_to(project).as_posix()}")
    assert tracked_spec.stdout == spec_file.read_text(encoding="utf-8")
    result = _cli(project, "plan", "--mission", mission, "--json")

    assert result.returncode == 0, f"`plan` failed on a freshly created mission:\n{result.stdout}\n{result.stderr}"
    assert json.loads(result.stdout)["result"] == "success", result.stdout
    assert (project / "kitty-specs" / mission / "plan.md").is_file()


def test_specify_on_main_discloses_uncommitted_scaffold(project: Path) -> None:
    """Main's supported protected-branch path succeeds and names pending files."""
    result = _cli(project, "specify", "task-list", "--json")
    assert result.returncode == 0, _unwrapped(result)
    payload = json.loads(result.stdout)
    missions = _missions(project)
    assert len(missions) == 1
    mission_dir = project / "kitty-specs" / missions[0]
    artifacts = {Path(item["path"]).name for item in payload["uncommitted_artifacts"]}
    assert {"spec.md", "meta.json"} <= artifacts
    assert (mission_dir / "meta.json").is_file()
    branch = _declared_coordination_branch(project, missions[0])
    assert branch is not None and _ref_exists(project, branch)
    assert _porcelain(project), "pending scaffold must remain visible to Git"


def test_specify_on_main_human_output_reports_meta_not_committed(project: Path) -> None:
    """#4608: the human path must not claim a commit the guard refused.

    ``--json`` discloses the uncommitted scaffold (test above); the plain
    human output used to unconditionally print "Meta committed to main"
    while no commit existed — the exact false report in the issue.
    """
    result = _cli(project, "specify", "task-list")
    assert result.returncode == 0, _unwrapped(result)
    output = _unwrapped(result)
    assert "Meta not committed" in output
    assert "untracked" in output
    assert "Meta committed to" not in output
    # What actually happened: no new commit, scaffold on disk, untracked.
    assert _git(project, "rev-list", "--count", "HEAD").stdout.strip() == "1"
    assert _porcelain(project)
    assert len(_missions(project)) == 1


def test_specify_on_feature_branch_human_output_reports_meta_committed(project: Path) -> None:
    """#4608 counterpart: on a non-protected branch the commit really lands,
    so the "Meta committed to" line stays and is true."""
    _git(project, "checkout", "-b", "my-first-mission")
    result = _cli(project, "specify", "task-list")
    assert result.returncode == 0, _unwrapped(result)
    output = _unwrapped(result)
    assert "Meta committed to my-first-mission" in output
    assert "Meta not committed" not in output
    # The scaffold commit landed: HEAD moved past the init commit.
    assert _git(project, "rev-list", "--count", "HEAD").stdout.strip() == "2"


# ---------------------------------------------------------------------------
# #4035 — the reporter's exact scenario
# ---------------------------------------------------------------------------


def test_protected_branch_continuation_keeps_exactly_one_mission(project: Path) -> None:
    """Switch branches and commit the existing scaffold without creating again."""
    result = _cli(project, "specify", "task-list", "--mission-type", "software-dev", "--json")
    assert result.returncode == 0, _unwrapped(result)
    before = _missions(project)
    assert len(before) == 1
    _git(project, "checkout", "-b", "my-first-mission")
    _git(project, "add", "-A")
    _git(project, "commit", "-m", "Commit existing mission scaffold")
    assert _missions(project) == before
    assert _porcelain(project) == ""


def test_protected_branch_notice_names_existing_artifacts(project: Path) -> None:
    result = _cli(project, "specify", "task-list", "--json")
    assert result.returncode == 0, _unwrapped(result)
    payload = json.loads(result.stdout)
    pending = payload["uncommitted_artifacts"]
    assert pending
    assert all(Path(item["path"]).exists() for item in pending)
    assert any("protected" in item["reason"] for item in pending)
    assert any("non-protected" in item["responsible_command"] for item in pending)


# ---------------------------------------------------------------------------
# #4033 — unborn HEAD
# ---------------------------------------------------------------------------


def test_unborn_head_refuses_before_writing_anything(tmp_path: Path) -> None:
    """A repo with no commits cannot host a mission, and is told so.

    Before the fix this exited 0 and produced a mission declaring a
    coordination branch that could never have been created.
    """
    repo = tmp_path / "unborn"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    assert _cli(repo, "init", ".", "--ai", "claude").returncode == 0
    heads = list((repo / ".git" / "refs" / "heads").glob("*")) if (repo / ".git" / "refs" / "heads").exists() else []
    assert heads == [], f"fixture invalid: the repo already has a branch ({heads})"

    result = _cli(repo, "specify", "task-list")

    assert result.returncode != 0, "expected a non-zero exit on an unborn HEAD"
    combined = _unwrapped(result)
    assert "no commits yet" in combined, f"expected the no-commits refusal, got:\n{combined}"
    assert _missions(repo) == [], "the refusal still wrote a scaffold"


def test_unborn_head_error_names_a_remedy_that_works(tmp_path: Path) -> None:
    """A guard that blocks without a working recovery is worse than the bug.

    Runs the exact command the error prescribes and asserts the next attempt
    gets somewhere — specifically, past the unborn-HEAD refusal.
    """
    repo = tmp_path / "unborn-recover"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    assert _cli(repo, "init", ".", "--ai", "claude").returncode == 0

    blocked = _cli(repo, "specify", "task-list")
    assert "git commit --allow-empty -m 'Initial commit'" in _unwrapped(blocked)

    _git(repo, "commit", "--allow-empty", "-m", "Initial commit")
    _git(repo, "checkout", "-b", "my-first-mission")
    retried = _cli(repo, "specify", "task-list")

    assert retried.returncode == 0, f"the prescribed remedy did not unblock the user:\n{retried.stdout}\n{retried.stderr}"
    assert len(_missions(repo)) == 1


# ---------------------------------------------------------------------------
# Release metadata
# ---------------------------------------------------------------------------


def test_version_matches_current_main_metadata(project: Path) -> None:
    expected = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())["project"]["version"]
    result = _cli(project, "--version")
    assert result.returncode == 0
    assert expected in _unwrapped(result)


def test_no_retired_org_in_user_facing_urls() -> None:
    """Active main package and issue URLs use the canonical organization.

    Package metadata plus the runtime constant that builds issue URLs — the two
    places a user actually lands on. Docstring references are out of scope on
    this line and are deliberately not asserted.
    """
    pyproject = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    urls_block = pyproject.split("[project.urls]", 1)[1].split("\n[", 1)[0]
    assert "Priivacy-ai" not in urls_block, f"[project.urls] still names the retired org:\n{urls_block}"

    issue_matrix = (_REPO_ROOT / "src" / "specify_cli" / "tasks" / "issue_matrix.py").read_text(encoding="utf-8")
    assert '_CANONICAL_REPO_SLUG = "spec-kitty/spec-kitty"' in issue_matrix


@pytest.mark.distribution
@pytest.mark.slow
def test_installed_wheel_tutorial_reaches_plan(
    installed_wheel_venv: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical wheel fixture runs the public tutorial without source imports."""
    python = installed_wheel_venv["python"]
    venv = installed_wheel_venv["venv_dir"].resolve()
    repo = tmp_path / "wheel-project"
    repo.mkdir()
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "PYTHONPATH",
            "SPEC_KITTY_TEMPLATE_ROOT",
            "SPEC_KITTY_TEST_MODE",
            "SPEC_KITTY_CLI_VERSION",
        }
    }
    probe = subprocess.run(
        [str(python), "-c", "import specify_cli; print(specify_cli.__file__)"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    module = Path(probe.stdout.strip()).resolve()
    assert module.is_relative_to(venv)
    assert not module.is_relative_to(_REPO_ROOT.resolve())
    original = _cli

    def installed_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return original(cwd, *args, python=python)

    monkeypatch.setattr(sys.modules[__name__], "_cli", installed_cli)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    initialized = _cli(repo, "init", ".", "--ai", "claude")
    assert initialized.returncode == 0, _unwrapped(initialized)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "Initial commit")
    test_plan_runs_on_the_mission_the_tutorial_creates(repo)


# ---------------------------------------------------------------------------
# #4166 — first init must not import a removed private installer function
# ---------------------------------------------------------------------------


def _isolate_fresh_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    """Point HOME and every XDG state var at a never-before-used home."""
    home.mkdir(parents=True, exist_ok=True)
    for var in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(var, str(home))
    for var, subdir in {
        "XDG_CONFIG_HOME": ".config",
        "XDG_DATA_HOME": ".local/share",
        "XDG_STATE_HOME": ".local/state",
        "XDG_CACHE_HOME": ".cache",
    }.items():
        (home / subdir).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(home / subdir))


def _assert_clean_first_init_skill_installation(result: subprocess.CompletedProcess[str], home: Path, repo: Path) -> None:
    """The #4166 contract: clean warning surface plus real skill evidence."""
    assert result.returncode == 0, f"`spec-kitty init` failed:\n{result.stdout}\n{result.stderr}"
    unwrapped = _unwrapped(result)
    assert "Skill installation incomplete" not in unwrapped, unwrapped
    assert "_sync_global_skill" not in unwrapped, unwrapped
    assert "cannot import name" not in unwrapped, unwrapped
    # Global canonical skills for the selected shared root, installed by the
    # retained global owner the CLI root callback dispatches.
    global_skill_docs = sorted((home / ".agents" / "skills").glob("*/SKILL.md"))
    assert global_skill_docs, f"no global canonical skills under the fresh HOME: {home}"
    # Project command skills for the selected agent, with delivery complete
    # (no pending record left behind claiming otherwise).
    project_skill_docs = sorted((repo / ".agents" / "skills").glob("spec-kitty.*/SKILL.md"))
    assert project_skill_docs, f"no command skills installed into the project: {repo}"
    assert (repo / ".kittify" / "command-skills-manifest.json").is_file()
    assert not (repo / ".kittify" / "init-command-skills.pending.json").exists()


def test_first_init_codex_non_interactive_reports_clean_skill_installation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#4166: `init --ai codex --non-interactive` on a fresh HOME.

    The former standalone global-skill phase imported the removed private
    ``_sync_global_skill`` writer and warned about an incomplete installation
    while later phases masked the failure. The entrypoint must instead show a
    clean warning surface AND leave the required selected-agent global/project
    skill evidence, without touching an unrelated skill owner under the HOME.
    """
    home = tmp_path / "fresh-home"
    _isolate_fresh_home(monkeypatch, home)
    unrelated_skill = home / ".agents" / "skills" / "my-personal-skill" / "SKILL.md"
    unrelated_skill.parent.mkdir(parents=True, exist_ok=True)
    unrelated_content = "---\nname: my-personal-skill\n---\nHands off.\n"
    unrelated_skill.write_text(unrelated_content, encoding="utf-8")

    repo = tmp_path / "codex-project"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")

    result = _cli(repo, "init", ".", "--ai", "codex", "--non-interactive")

    _assert_clean_first_init_skill_installation(result, home, repo)
    # Unrelated skill owners under the HOME are preserved, never replaced.
    assert unrelated_skill.read_text(encoding="utf-8") == unrelated_content


@pytest.mark.distribution
@pytest.mark.slow
def test_installed_wheel_first_init_codex_non_interactive_clean(
    installed_wheel_venv: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#4166: the installed-wheel build of the same entrypoint, fresh HOME.

    The original report reproduced against an installed wheel (3.2.7rc1), so
    the regression runs the wheel install too, not just the source tree.
    """
    python = installed_wheel_venv["python"]
    venv = installed_wheel_venv["venv_dir"].resolve()
    home = tmp_path / "wheel-fresh-home"
    _isolate_fresh_home(monkeypatch, home)
    repo = tmp_path / "wheel-codex-project"
    repo.mkdir()
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "PYTHONPATH",
            "SPEC_KITTY_TEMPLATE_ROOT",
            "SPEC_KITTY_TEST_MODE",
            "SPEC_KITTY_CLI_VERSION",
        }
    }
    probe = subprocess.run(
        [str(python), "-c", "import specify_cli; print(specify_cli.__file__)"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    module = Path(probe.stdout.strip()).resolve()
    assert module.is_relative_to(venv)
    assert not module.is_relative_to(_REPO_ROOT.resolve())
    original = _cli

    def installed_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return original(cwd, *args, python=python)

    monkeypatch.setattr(sys.modules[__name__], "_cli", installed_cli)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")

    result = _cli(repo, "init", ".", "--ai", "codex", "--non-interactive")

    _assert_clean_first_init_skill_installation(result, home, repo)
