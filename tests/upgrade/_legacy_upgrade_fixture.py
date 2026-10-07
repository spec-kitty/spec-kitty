"""Hermetic real-git legacy (pre-schema-3) project fixture for the #5443 upgrade tests.

Every helper here exists so that an assertion about ``spec-kitty upgrade`` is an
assertion about the upgrade and never about the developer's machine:

* the child environment is an allowlist (isolated HOME/XDG, no inherited
  ``GIT_*`` / ``SPEC_KITTY_*``), plus ``PYTHONPATH=<this checkout>/src`` so the
  subprocess runs the code under test and not the main checkout's editable install;
* the repository is created with ``git init --template= -b work`` (no template
  hooks, and a branch that is not protected, so the protected-branch guard is
  never what a test observes);
* HOME state (cold / warm) is pinned explicitly.

The module name starts with an underscore: it is a support module, not collected.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import yaml

from tests.upgrade.preview_support.process import child_environment

__all__ = [
    "MARKED_COMMAND_FILE",
    "all_history_blob_text",
    "build_legacy",
    "commit_files",
    "flat",
    "git",
    "head",
    "install_pre_commit_hook",
    "make_legacy_project",
    "new_commit_files",
    "new_commits",
    "prepare_home",
    "run_upgrade",
    "staged",
    "status_z",
    "upgrade_env",
]

HomeState = Literal["cold", "warm"]

CHECKOUT = Path(__file__).resolve().parents[2]

#: A generated command file: the version marker in its first lines proves it is ours.
MARKED_COMMAND_FILE = "<!-- spec-kitty-command-version: 2.1.0 -->\n# spec-kitty.implement\n"

_EXPECTED_GIT_KEYS = frozenset({"GIT_OPTIONAL_LOCKS", "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL", "GIT_TERMINAL_PROMPT"})
_EXPECTED_SPEC_KITTY_KEYS = frozenset({"SPEC_KITTY_HOME", "SPEC_KITTY_NO_UPGRADE_CHECK", "SPEC_KITTY_ENABLE_SAAS_SYNC"})


def upgrade_env(sandbox: Path, checkout_src: Path | None = None) -> dict[str, str]:
    """Build the allowlisted child environment for one upgrade run.

    ``checkout_src`` is the ``src`` directory of the checkout under test; it defaults
    to this checkout (the lane worktree), never the editable install's main checkout.
    """
    src = checkout_src if checkout_src is not None else CHECKOUT / "src"
    assert (src.parent / "packs").is_dir(), f"{src.parent} has no packs/ beside src/ — the CLI would upgrade with missing packs"
    env = child_environment(sandbox, {"COLUMNS": "400"})
    env["SPEC_KITTY_NO_UPGRADE_CHECK"] = "1"
    env["PYTHONPATH"] = str(src)
    env["PATH"] = _path_with_git(env["PATH"])
    assert {k for k in env if k.startswith("GIT_")} == _EXPECTED_GIT_KEYS
    assert {k for k in env if k.startswith("SPEC_KITTY_")} == _EXPECTED_SPEC_KITTY_KEYS
    return env


def _path_with_git(path: str) -> str:
    git_exe = shutil.which("git", path=path) or shutil.which("git")
    assert git_exe is not None, "git is required"
    git_dir = str(Path(git_exe).parent)
    return path if git_dir in path.split(":") else f"{path}:{git_dir}"


def prepare_home(sandbox: Path, home_state: HomeState) -> Path:
    """Create the sandbox HOME in an explicit state.

    ``cold``: empty (no global runtime, no global agent commands).
    ``warm``: the global runtime and the exact global replacement the globalize
    migrations probe for (``~/.kittify/missions/<dir>/`` and
    ``~/.claude/commands/spec-kitty.implement.md``).
    """
    home = sandbox / "home"
    home.mkdir(parents=True, exist_ok=True)
    if home_state == "warm":
        (home / ".kittify" / "missions" / "software-dev").mkdir(parents=True, exist_ok=True)
        commands = home / ".claude" / "commands"
        commands.mkdir(parents=True, exist_ok=True)
        (commands / "spec-kitty.implement.md").write_text(MARKED_COMMAND_FILE, encoding="utf-8")
    return home


def git(project: Path, env: Mapping[str, str], *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run git in *project* with the hermetic environment."""
    result = subprocess.run(["git", *args], cwd=project, env=dict(env), capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed ({result.returncode}): {result.stderr}")
    return result


def make_legacy_project(
    root: Path,
    env: Mapping[str, str],
    *,
    agents: list[str],
    gitignore: str | None,
    extra_files: Mapping[str, str] | None = None,
) -> Path:
    """Create a committed legacy (schema-less, ``2.1.0``) project at *root*.

    ``extra_files`` are written and committed with explicit paths (never ``git add -A``).
    """
    root.mkdir(parents=True)
    files: dict[str, str] = {
        ".kittify/metadata.yaml": yaml.dump({"spec_kitty": {"version": "2.1.0", "initialized_at": "2026-01-01T00:00:00"}}),
        ".kittify/config.yaml": yaml.dump({"agents": {"available": agents}}),
        "kitty-specs/001-demo/meta.json": '{"mission_slug": "001-demo", "title": "Demo"}\n',
        "kitty-specs/001-demo/tasks/WP01-title.md": (
            "---\nwork_package_id: ''\nwp_code: 'WP01'\ntitle: WP01 Title\nlane: 'planned'\ndependencies: []\nsubtasks: []\n---\n\n# WP01\n"
        ),
        "src/app.py": "A = 1\n",
        "docs/old.md": "old\n",
    }
    if gitignore is not None:
        files[".gitignore"] = gitignore
    files.update(extra_files or {})

    git(root, env, "init", "--template=", "-b", "work", "-q")
    hooks_dir = root / ".git" / "hooks"
    leftovers = [p for p in hooks_dir.iterdir() if not p.name.endswith(".sample")] if hooks_dir.is_dir() else []
    assert leftovers == [], f"fixture repository must start hook-free, found {leftovers}"
    git(root, env, "config", "user.name", "Fixture")
    git(root, env, "config", "user.email", "fixture@example.com")
    git(root, env, "config", "commit.gpgsign", "false")
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    git(root, env, "add", "--", *sorted(files))
    git(root, env, "commit", "-q", "-m", "initial")
    return root


def build_legacy(
    sandbox: Path,
    *,
    agents: list[str],
    gitignore: str | None,
    home: HomeState = "cold",
    extra_files: Mapping[str, str] | None = None,
) -> tuple[Path, dict[str, str]]:
    """Create the sandbox HOME, the environment and the legacy project in one call."""
    prepare_home(sandbox, home)
    env = upgrade_env(sandbox)
    project = make_legacy_project(sandbox / "project", env, agents=agents, gitignore=gitignore, extra_files=extra_files)
    return project, env


def flat(text: str) -> str:
    """Collapse whitespace so assertions survive terminal wrapping."""
    return " ".join(text.split())


def run_upgrade(project: Path, env: Mapping[str, str], *extra: str) -> subprocess.CompletedProcess[str]:
    """Run ``spec-kitty upgrade --yes`` through the module entry point of this checkout."""
    return subprocess.run(
        [sys.executable, "-m", "specify_cli", "upgrade", "--yes", *extra],
        cwd=project,
        env=dict(env),
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )


def head(project: Path, env: Mapping[str, str]) -> str:
    return git(project, env, "rev-parse", "HEAD").stdout.strip()


def new_commits(project: Path, env: Mapping[str, str], since: str) -> list[str]:
    """Commits in ``since..HEAD``, oldest first."""
    out = git(project, env, "rev-list", "--reverse", f"{since}..HEAD").stdout
    return out.split()


def commit_files(project: Path, env: Mapping[str, str], rev: str) -> list[tuple[str, str]]:
    """``(status letter, path)`` pairs of one commit (NUL-split, so a deletion shows as ``D``)."""
    raw = git(project, env, "show", "--name-status", "--format=", "-z", rev).stdout
    tokens = [t for t in raw.split("\0") if t]
    pairs: list[tuple[str, str]] = []
    idx = 0
    while idx < len(tokens):
        status = tokens[idx]
        width = 2 if status[0] in {"R", "C"} else 1
        pairs.append((status[0], tokens[idx + width]))
        idx += 1 + width
    return pairs


def new_commit_files(project: Path, env: Mapping[str, str], since: str) -> list[tuple[str, str]]:
    """Every ``(status, path)`` of every commit in ``since..HEAD``."""
    pairs: list[tuple[str, str]] = []
    for rev in new_commits(project, env, since):
        pairs.extend(commit_files(project, env, rev))
    return pairs


def status_z(project: Path, env: Mapping[str, str]) -> list[tuple[str, str]]:
    """``(XY, path)`` pairs of ``git status --porcelain=v1 -z --untracked-files=all``."""
    raw = git(project, env, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    tokens = [t for t in raw.split("\0") if t]
    pairs: list[tuple[str, str]] = []
    idx = 0
    while idx < len(tokens):
        entry = tokens[idx]
        xy, path = entry[:2], entry[3:]
        pairs.append((xy, path))
        idx += 2 if "R" in xy or "C" in xy else 1
    return pairs


def staged(project: Path, env: Mapping[str, str]) -> list[str]:
    raw = git(project, env, "diff", "--cached", "--name-only", "-z").stdout
    return sorted(t for t in raw.split("\0") if t)


def all_history_blob_text(project: Path, env: Mapping[str, str]) -> str:
    """Every patch of every ref, for secret-leak greps (HEAD's file list is not enough)."""
    raw = subprocess.run(["git", "log", "--all", "-p", "--binary"], cwd=project, env=dict(env), capture_output=True, check=True).stdout
    return raw.decode("utf-8", errors="replace")


def install_pre_commit_hook(project: Path, sandbox: Path, *, reject: bool) -> Path:
    """Install a counting pre-commit hook; return the counter file (outside the work tree)."""
    counter = sandbox / "hook-calls"
    hook = project / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(
        f"#!{sys.executable}\nimport sys\nwith open({str(counter)!r}, 'a') as fh:\n    fh.write('x\\n')\nsys.exit({1 if reject else 0})\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    return counter
