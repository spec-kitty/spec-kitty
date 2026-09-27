"""Shared fixtures for ``tests/docs``.

The leakage-check CLI resolves markdown link targets and inventory paths
against the current working directory. The fixtures here stage a fresh
``docs/`` tree (plus an inventory YAML) inside ``tmp_path`` and yield
that staging directory so tests can run the script with ``cwd=staging``.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

# ``scripts.docs`` is importable without any sys.path bootstrap: pytest's own
# rootdir-prepend (triggered by ``tests/__init__.py``) already puts the repo
# root on ``sys.path`` before this conftest is collected.
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PAGES_DIR = FIXTURES_DIR / "sample_pages"


@pytest.fixture()
def clean_workspace(tmp_path: Path) -> Iterator[Path]:
    """Stage the clean sample tree + inventory in ``tmp_path``."""
    workspace = tmp_path / "clean"
    shutil.copytree(SAMPLE_PAGES_DIR / "clean", workspace)
    shutil.copy(FIXTURES_DIR / "clean_inventory.yaml", workspace / "inventory.yaml")
    yield workspace


@pytest.fixture()
def dirty_workspace(tmp_path: Path) -> Iterator[Path]:
    """Stage the dirty sample tree + inventory in ``tmp_path``."""
    workspace = tmp_path / "dirty"
    shutil.copytree(SAMPLE_PAGES_DIR / "dirty", workspace)
    shutil.copy(FIXTURES_DIR / "dirty_inventory.yaml", workspace / "inventory.yaml")
    yield workspace


@pytest.fixture()
def missing_workspace(tmp_path: Path) -> Iterator[Path]:
    """Stage a minimal docs tree + malformed inventory in ``tmp_path``."""
    workspace = tmp_path / "missing"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    shutil.copy(FIXTURES_DIR / "missing_inventory.yaml", workspace / "inventory.yaml")
    yield workspace


# --------------------------------------------------------------------------- #
# Diff-scope test git helpers (#3147, B-WP02).
#
# Shared by test_guards.py, test_relative_link_fixer.py, test_related_validator.py,
# and test_rulers_blocking.py: each exercises a ``--changed-from BASE_REF`` /
# :func:`scripts.docs._guards.resolve_changed_files` diff-scope path, which needs
# a real (throwaway, tmp_path-scoped) git repo with a distinguishable "base"
# commit and a later "head" state to diff against. Centralised here so the
# four call sites don't drift on the git-init incantation.
# --------------------------------------------------------------------------- #


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )


def init_git_repo_with_base(root: Path) -> str:
    """Init a git repo at *root* and commit the current on-disk state as "base".

    Returns the base commit's SHA. Callers stage further changes under *root*
    and pass them to :func:`commit_all_changes` to produce a "head" commit; the
    diff-scope code under test is then invoked with ``--changed-from <base
    sha>`` (or :func:`scripts.docs._guards.resolve_changed_files` directly) to
    diff the two.
    """
    _run_git(root, "init", "-q")
    _run_git(root, "config", "user.email", "spec-kitty-tests@example.com")
    _run_git(root, "config", "user.name", "Spec Kitty Tests")
    _run_git(root, "add", "-A")
    _run_git(root, "commit", "-q", "-m", "base", "--allow-empty")
    return _run_git(root, "rev-parse", "HEAD").stdout.strip()


def commit_all_changes(root: Path, message: str) -> None:
    """Stage and commit every current change under *root* (the diff's "head")."""
    _run_git(root, "add", "-A")
    _run_git(root, "commit", "-q", "-m", message, "--allow-empty")
