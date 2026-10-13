"""Behavior of the sourced Shadow Clone helper."""

from pathlib import Path
import shutil
import subprocess

import pytest


HELPER = Path(__file__).resolve().parents[2] / "scripts/dev/activate-isolated-env.sh"


def _run(shell: str, cwd: Path, *, exe: str = "bash") -> subprocess.CompletedProcess[str]:
    return subprocess.run([exe, "-c", shell], cwd=cwd, text=True, capture_output=True, check=False)


def _parse(stdout: str) -> dict[str, str]:
    """Collect ``KEY=VALUE`` lines the probes print into a dict."""
    values: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            values[key] = value
    return values


def _fake_clone(base: Path) -> Path:
    """A non-git clone tree: a byte-identical copy of the helper under
    ``scripts/dev/`` plus an executable ``.venv/bin/spec-kitty``, so the helper's
    script-location fallback (``dirname/../..``) resolves back to *base*."""
    helper_dir = base / "scripts/dev"
    helper_dir.mkdir(parents=True)
    shutil.copy2(HELPER, helper_dir / HELPER.name)
    cli = base / ".venv/bin/spec-kitty"
    cli.parent.mkdir(parents=True)
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)
    return base


def test_sourced_helper_binds_current_worktree(tmp_path: Path) -> None:
    root = tmp_path / "clone"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "--allow-empty", "-m", "base"],
        check=True,
    )
    worktree = tmp_path / "old-branch"
    subprocess.run(
        ["git", "-C", str(root), "worktree", "add", "-q", "-b", "old-branch", str(worktree)],
        check=True,
    )
    cli = worktree / ".venv/bin/spec-kitty"
    cli.parent.mkdir(parents=True)
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)

    result = _run(
        f'source "{HELPER}" && printf "ROOT=%s\\nCLI=%s\\n" "$SPEC_KITTY_HOME" "$(command -v spec-kitty)"',
        worktree,
    )

    # Resolve both sides: ``git rev-parse --show-toplevel`` returns the real
    # path, so on macOS a ``/var`` tmp dir comes back as ``/private/var``. A
    # string-equality assertion against the unresolved path would fail there
    # while passing on Linux CI (#5957 review).
    wt = worktree.resolve()
    assert result.returncode == 0, result.stderr
    assert f"ROOT={wt}/.spec-kitty-home" in result.stdout
    assert f"CLI={wt}/.venv/bin/spec-kitty" in result.stdout
    assert not (root.resolve() / ".spec-kitty-home").exists()


def test_non_git_fallback_binds_script_location(tmp_path: Path) -> None:
    # Outside any git repo, ``git rev-parse --show-toplevel`` fails and the
    # helper falls back to its own location (``dirname/../..``). The ceiling
    # bounds the walk-up so an ambient repository above the temp tree cannot be
    # discovered and flip this branch.
    base = _fake_clone(tmp_path / "notgit")
    helper = base / "scripts/dev" / HELPER.name

    result = _run(
        f'export GIT_CEILING_DIRECTORIES="{tmp_path}"; source "{helper}" && printf "ROOT=%s\\nCLI=%s\\n" "$SPEC_KITTY_HOME" "$(command -v spec-kitty)"',
        base,
    )

    assert result.returncode == 0, result.stderr
    values = _parse(result.stdout)
    assert Path(values["ROOT"]).resolve() == (base / ".spec-kitty-home").resolve()
    assert Path(values["CLI"]).resolve() == (base / ".venv/bin/spec-kitty").resolve()


def test_missing_local_cli_refuses_without_changing_shell(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".venv/bin").mkdir(parents=True)

    result = _run(
        f'old_path=$PATH; source "{HELPER}"; status=$?; '
        'printf "STATUS=%s HOME=%s PATH_SAME=%s\\n" '
        '"$status" "${SPEC_KITTY_HOME-unset}" '
        '"$([ "$PATH" = "$old_path" ] && echo yes || echo no)"',
        tmp_path,
    )

    assert "STATUS=1 HOME=unset PATH_SAME=yes" in result.stdout
    assert "spec-kitty" in result.stderr
    assert not (tmp_path / ".spec-kitty-home").exists()


def test_non_executable_cli_refuses_without_changing_shell(tmp_path: Path) -> None:
    # Present but non-executable CLI exercises the ``-x`` arm of the guard
    # (``[ ! -f ] || [ ! -x ]``): the file exists, so the refusal comes from the
    # executable test, not the existence test the sibling case covers.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    cli = tmp_path / ".venv/bin/spec-kitty"
    cli.parent.mkdir(parents=True)
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o644)

    result = _run(
        f'old_path=$PATH; source "{HELPER}"; status=$?; '
        'printf "STATUS=%s HOME=%s PATH_SAME=%s\\n" '
        '"$status" "${SPEC_KITTY_HOME-unset}" '
        '"$([ "$PATH" = "$old_path" ] && echo yes || echo no)"',
        tmp_path,
    )

    assert "STATUS=1 HOME=unset PATH_SAME=yes" in result.stdout
    assert "no executable spec-kitty CLI" in result.stderr
    assert not (tmp_path / ".spec-kitty-home").exists()


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh is not installed")
def test_zsh_sourcing_resolves_script_location(tmp_path: Path) -> None:
    # Under zsh, ``BASH_SOURCE`` is unset and the helper resolves its own path
    # through ``${(%):-%N}``. Pair it with the non-git fallback so that branch
    # is the one that binds the root, proving the zsh path works end to end.
    base = _fake_clone(tmp_path / "notgit-zsh")
    helper = base / "scripts/dev" / HELPER.name

    result = _run(
        f'export GIT_CEILING_DIRECTORIES="{tmp_path}"; source "{helper}" && printf "ROOT=%s\\n" "$SPEC_KITTY_HOME"',
        base,
        exe="zsh",
    )

    assert result.returncode == 0, result.stderr
    values = _parse(result.stdout)
    assert Path(values["ROOT"]).resolve() == (base / ".spec-kitty-home").resolve()
