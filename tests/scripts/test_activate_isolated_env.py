"""Behavior of the sourced Shadow Clone helper."""

from pathlib import Path
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.fast

HELPER = Path(__file__).resolve().parents[2] / "scripts/dev/activate-isolated-env.sh"


def _run(shell: str, cwd: Path, *, exe: str = "bash") -> subprocess.CompletedProcess[str]:
    return subprocess.run([exe, "-c", shell], cwd=cwd, text=True, capture_output=True, check=False)


def _git(*args: str) -> None:
    subprocess.run(["git", *args], check=True)


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


def _install_cli(root: Path) -> None:
    cli = root / ".venv/bin/spec-kitty"
    cli.parent.mkdir(parents=True)
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)


def _git_repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A repository at ``clone/`` with a linked worktree at ``old-branch/``."""
    root = tmp_path / "clone"
    root.mkdir()
    _git("init", "-q", str(root))
    _git("-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "--allow-empty", "-m", "base")
    worktree = tmp_path / "old-branch"
    _git("-C", str(root), "worktree", "add", "-q", "-b", "old-branch", str(worktree))
    return root, worktree


@pytest.mark.parametrize("subdir", ["", "nested/deeper"])
def test_sourced_helper_binds_current_worktree(tmp_path: Path, subdir: str) -> None:
    root, worktree = _git_repo_with_worktree(tmp_path)
    _install_cli(worktree)
    cwd = worktree / subdir
    cwd.mkdir(parents=True, exist_ok=True)

    result = _run(
        f'source "{HELPER}" && printf "ROOT=%s\\nCLI=%s\\n" "$SPEC_KITTY_HOME" "$(command -v spec-kitty)"',
        cwd,
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
    if subdir:
        assert not (cwd / ".spec-kitty-home").exists()


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


_REFUSAL_PROBE = (
    'old_path=$PATH; source "{helper}"; status=$?; '
    'printf "STATUS=%s HOME=%s PATH_SAME=%s\\n" '
    '"$status" "${{SPEC_KITTY_HOME-unset}}" '
    '"$([ "$PATH" = "$old_path" ] && echo yes || echo no)"'
)


def _venv_without_cli(root: Path) -> None:
    """A git checkout whose ``.venv`` exists but holds no ``spec-kitty`` CLI, so
    the refusal comes from the CLI guard rather than the missing-venv guard."""
    _git("init", "-q", str(root))
    (root / ".venv/bin").mkdir(parents=True)


def test_missing_local_cli_refuses_without_changing_shell(tmp_path: Path) -> None:
    _venv_without_cli(tmp_path)

    result = _run(_REFUSAL_PROBE.format(helper=HELPER), tmp_path)

    assert "STATUS=1 HOME=unset PATH_SAME=yes" in result.stdout
    assert "no executable spec-kitty CLI" in result.stderr
    assert "no .venv found" not in result.stderr
    assert not (tmp_path / ".spec-kitty-home").exists()


def test_caller_environment_does_not_leak_into_probes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Running this suite inside an activated Shadow Clone (or a git hook) must
    # not change its verdicts: the probes see a scrubbed environment, never the
    # caller's SPEC_KITTY_HOME / SPEC_KITTY_ISOLATED_ENV / VIRTUAL_ENV / GIT_*.
    decoy = tmp_path / "decoy"
    _git("init", "-q", str(decoy))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "foreign-home"))
    monkeypatch.setenv("SPEC_KITTY_ISOLATED_ENV", str(tmp_path / "foreign-clone"))
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "foreign-venv"))
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    checkout = tmp_path / "checkout"
    _venv_without_cli(checkout)

    result = _run(_REFUSAL_PROBE.format(helper=HELPER), checkout)

    assert "STATUS=1 HOME=unset PATH_SAME=yes" in result.stdout
    assert "no executable spec-kitty CLI" in result.stderr
    # The fixture's own ``git init`` must land in *checkout*, not in GIT_DIR.
    assert (checkout / ".git").is_dir()


def test_sourcing_under_set_e_outside_git_keeps_caller_alive(tmp_path: Path) -> None:
    # ``git rev-parse`` fails outside a repository; under ``set -e`` an
    # unguarded command substitution would kill the sourcing shell before the
    # script-location fallback runs.
    base = _fake_clone(tmp_path / "notgit")
    helper = base / "scripts/dev" / HELPER.name

    result = _run(
        f'set -e; export GIT_CEILING_DIRECTORIES="{tmp_path}"; source "{helper}"; echo survived',
        base,
    )

    assert result.returncode == 0, result.stderr
    assert "survived" in result.stdout


def test_switching_clones_then_deactivating_restores_original_shell(tmp_path: Path) -> None:
    # Activate in clone A, then source in clone B: B must become active, and a
    # single deactivate must restore the shell as it was before A, not A's
    # activated PATH / SPEC_KITTY_HOME.
    clone_a = tmp_path / "clone-a"
    clone_b = tmp_path / "clone-b"
    for clone in (clone_a, clone_b):
        _git("init", "-q", str(clone))
        _install_cli(clone)

    result = _run(
        "orig_path=$PATH; "
        f'cd "{clone_a}" && source "{HELPER}" && '
        f'cd "{clone_b}" && source "{HELPER}" && '
        'printf "ACTIVE_HOME=%s\\nACTIVE_CLI=%s\\n" "$SPEC_KITTY_HOME" "$(command -v spec-kitty)" && '
        "deactivate_spec_kitty && "
        'printf "HOME=%s\\nVENV=%s\\nMARKER=%s\\nPATH_SAME=%s\\n" '
        '"${SPEC_KITTY_HOME-unset}" "${VIRTUAL_ENV-unset}" "${SPEC_KITTY_ISOLATED_ENV-unset}" '
        '"$([ "$PATH" = "$orig_path" ] && echo yes || echo no)"',
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    values = _parse(result.stdout)
    assert Path(values["ACTIVE_HOME"]).resolve() == (clone_b / ".spec-kitty-home").resolve()
    assert Path(values["ACTIVE_CLI"]).resolve() == (clone_b / ".venv/bin/spec-kitty").resolve()
    assert values["HOME"] == "unset"
    assert values["VENV"] == "unset"
    assert values["MARKER"] == "unset"
    assert values["PATH_SAME"] == "yes"


def test_non_executable_cli_refuses_without_changing_shell(tmp_path: Path) -> None:
    # Present but non-executable CLI exercises the ``-x`` arm of the guard
    # (``[ ! -f ] || [ ! -x ]``): the file exists, so the refusal comes from the
    # executable test, not the existence test the sibling case covers.
    _git("init", "-q", str(tmp_path))
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
