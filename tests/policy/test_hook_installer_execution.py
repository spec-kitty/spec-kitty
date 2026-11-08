"""Tests for pre-commit hook actual execution behavior (T036, T037, T039).

T039: POSIX smoke test — hook executes without 126/127 errors.
T036: Windows execution test — marked windows_ci.
T037: Windows execution with space in interpreter path — marked windows_ci.

Return codes 126 and 127 are the regression signatures:
  126 = permission denied / not executable (mode or shebang broken)
  127 = command not found (PATH lookup failed)
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.policy.hook_installer import install


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

def _init_git(repo: Path) -> None:
    """Initialize a bare git repo with user config for committing."""
    subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX smoke test")
def test_hook_executes_on_posix(tmp_path: Path) -> None:
    """Confirm the hook is executable on POSIX — not 126 or 127 (T039)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo)
    install(repo)

    (repo / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
    proc = subprocess.run(
        ["git", "commit", "-m", "posix-smoke"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert proc.returncode not in (126, 127), (
        f"Hook invocation failed on POSIX. rc={proc.returncode}\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )


@pytest.mark.windows_ci
def test_hook_executes_on_windows(tmp_path: Path) -> None:
    """Confirm the hook is executable on Git for Windows (T036).

    126 = non-executable (mode/shebang broken).
    127 = not-found (PATH lookup broken).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo)
    install(repo)

    (repo / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)

    proc = subprocess.run(
        ["git", "commit", "-m", "test"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert proc.returncode not in (126, 127), (
        f"Hook invocation failed at shell level. rc={proc.returncode}\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )


@pytest.mark.windows_ci
def test_hook_executes_with_spaces_in_interpreter_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hook works when the interpreter path contains a space (T037).

    This is the most common real-world Windows failure mode: paths like
    C:\\Program Files\\Python311\\python.exe must survive the exec line.
    """
    # Copy the interpreter into a path with a space in the directory name.
    spaced = tmp_path / "My Programs" / "Python"
    spaced.mkdir(parents=True)
    fake_interp = spaced / Path(sys.executable).name
    shutil.copy2(sys.executable, fake_interp)

    monkeypatch.setattr(sys, "executable", str(fake_interp))

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo)
    install(repo)

    (repo / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
    proc = subprocess.run(
        ["git", "commit", "-m", "test-spaces"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert proc.returncode not in (126, 127), (
        f"Hook invocation failed with interpreter at a path containing a space. "
        f"rc={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
