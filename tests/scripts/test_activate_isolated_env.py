"""Behavior of the sourced Shadow Clone helper."""

from pathlib import Path
import subprocess


HELPER = Path(__file__).resolve().parents[2] / "scripts/dev/activate-isolated-env.sh"


def _run(shell: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", shell], cwd=cwd, text=True, capture_output=True, check=False
    )


def test_sourced_helper_binds_current_worktree(tmp_path: Path) -> None:
    root = tmp_path / "clone"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "--allow-empty", "-m", "base"], check=True)
    worktree = tmp_path / "old-branch"
    subprocess.run(["git", "-C", str(root), "worktree", "add", "-q", "-b", "old-branch", str(worktree)], check=True)
    cli = worktree / ".venv/bin/spec-kitty"
    cli.parent.mkdir(parents=True)
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)

    result = _run(f'source "{HELPER}" && printf "ROOT=%s\\nCLI=%s\\n" "$SPEC_KITTY_HOME" "$(command -v spec-kitty)"', worktree)

    assert result.returncode == 0, result.stderr
    assert f"ROOT={worktree}/.spec-kitty-home" in result.stdout
    assert f"CLI={cli}" in result.stdout
    assert not (root / ".spec-kitty-home").exists()


def test_missing_local_cli_refuses_without_changing_shell(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".venv/bin").mkdir(parents=True)

    result = _run(f'old_path=$PATH; source "{HELPER}"; status=$?; printf "STATUS=%s HOME=%s PATH_SAME=%s\\n" "$status" "${{SPEC_KITTY_HOME-unset}}" "$([ "$PATH" = "$old_path" ] && echo yes || echo no)"', tmp_path)

    assert "STATUS=1 HOME=unset PATH_SAME=yes" in result.stdout
    assert "spec-kitty" in result.stderr
    assert not (tmp_path / ".spec-kitty-home").exists()
