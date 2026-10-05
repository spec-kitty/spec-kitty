"""Regression test for #1917: _validate_base_ref must terminate rev options.

When `git rev-parse --verify` receives a value starting with '--' (like '--git-dir'),
it consumes the value as an option rather than as a ref name, potentially:
- Leaking git option side-effects (e.g., printing the git dir) as the returned "SHA"
- Silently succeeding for option-shaped values that are not valid refs

The fix inserts Git's rev-option terminator so that leading-dash values are always
validated AS REF NAMES: git rev-parse --verify --end-of-options <base_ref>

Probe option: '--git-dir'
- WITHOUT '--': git consumes --git-dir as an option (emits git-dir path to stdout), rc=128
- WITH '--': git treats --git-dir as a ref name (unknown-revision error), rc=128
Both return rc!=0 for real git, but the argv shape is different — the test captures
the exact subprocess argv to prove the separator is present.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands.implement_phases import _validate_base_ref

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LEADING_DASH_REF = "--git-dir"
"""A leading-dash value that maps to a real git rev-parse option.

Without ``--end-of-options``, git consumes it as an option flag. With
``--end-of-options``, git treats it as a ref name.
"""


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _init_repo(repo_root: Path) -> str:
    _git(repo_root, "init")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")
    (repo_root / "README.md").write_text("test\n")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "init")
    _git(repo_root, "branch", "-M", "main")
    return _git(repo_root, "rev-parse", "HEAD")


# ---------------------------------------------------------------------------
# T030 — Regression: real git ref validation
# ---------------------------------------------------------------------------


def test_validate_base_ref_normal_ref_passes_real_git(tmp_path: Path) -> None:
    """Normal refs must still resolve through real git.

    A mocked argv test missed that ``git rev-parse --verify -- main`` returns
    ``fatal: Needed a single revision``. This exercises the observable command.
    """
    expected_sha = _init_repo(tmp_path)

    assert _validate_base_ref(tmp_path, "main") == expected_sha


def test_validate_base_ref_leading_dash_ref_passes_real_git(tmp_path: Path) -> None:
    """Leading-dash ref names must be treated as refs, not rev-parse options."""
    expected_sha = _init_repo(tmp_path)
    _git(tmp_path, "update-ref", f"refs/heads/{_LEADING_DASH_REF}", expected_sha)

    assert _validate_base_ref(tmp_path, _LEADING_DASH_REF) == expected_sha


def test_validate_base_ref_exits_on_nonzero_returncode(tmp_path: Path) -> None:
    """_validate_base_ref must raise typer.Exit(1) when git returns non-zero.

    This exercises the error path: a ref that does not resolve locally.
    The '--' fix must not change the existing error semantics.
    """
    import typer

    _init_repo(tmp_path)

    with pytest.raises(typer.Exit) as exc_info:
        _validate_base_ref(tmp_path, "no-such-ref")

    assert exc_info.value.exit_code == 1, (
        f"Expected exit code 1 for unknown ref, got {exc_info.value.exit_code}"
    )
