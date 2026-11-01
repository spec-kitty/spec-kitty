"""Resolver behaviour for :mod:`specify_cli.core.paths`.

These tests pin the #1965 fix: ``SPECIFY_REPO_ROOT`` is authoritative whenever
the path it names is an existing directory, even if that directory has no
``.kittify/``. The determinism the doctor-skills error-schema test relies on
must flow from this resolver, not from test-local ``monkeypatch`` isolation.

C-003 regression guard: a real ``.kittify/`` project resolves to the *same*
canonical root whether or not ``SPECIFY_REPO_ROOT`` is set, so honouring the
env var changes nothing for already-correct projects.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.constants import KITTIFY_DIR, LINT_REPORT_FILENAME
from specify_cli.core.paths import lint_report_path, locate_project_root


def test_lint_report_path_is_canonical(tmp_path: Path) -> None:
    """#2628 SSOT: the accessor composes the one canonical report location so
    the engine (writer), dashboard, and dossier stager cannot drift."""
    repo_root = tmp_path / "repo"
    result = lint_report_path(repo_root)
    assert result == repo_root / KITTIFY_DIR / LINT_REPORT_FILENAME
    assert result.name == "lint-report.json"
    assert result.parent.name == ".kittify"

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _init_git_repo(root: Path) -> None:
    """Create a minimal main-repo ``.git`` directory so worktree-pointer
    detection treats ``root`` as a regular checkout (not a worktree)."""
    (root / ".git").mkdir(parents=True, exist_ok=True)


def test_env_root_authoritative_without_kittify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1965: an existing ``SPECIFY_REPO_ROOT`` with no ``.kittify/`` is honoured.

    Determinism here comes from the resolver: even when the *current* checkout
    has a ``.kittify/`` (the ambient repo), pointing the env var at a
    ``.kittify``-less existing directory must win — the resolver must NOT fall
    through to a Tier-2 walk-up that leaks the ambient checkout.
    """
    # An ambient checkout that *does* have .kittify, used as the search start.
    ambient = tmp_path / "ambient-checkout"
    (ambient / ".kittify").mkdir(parents=True)
    _init_git_repo(ambient)

    # The env-named root: it exists but deliberately has NO .kittify/.
    env_root = tmp_path / "explicit-root"
    env_root.mkdir()

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(env_root))

    # Even starting the walk-up inside the ambient .kittify checkout, the env
    # var must take precedence and return the explicit (kittify-less) root.
    resolved = locate_project_root(start=ambient)

    assert resolved == env_root.resolve()
    assert resolved != ambient.resolve()


def test_env_root_ignored_when_path_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-existent ``SPECIFY_REPO_ROOT`` still falls through."""
    ambient = tmp_path / "ambient-checkout"
    (ambient / ".kittify").mkdir(parents=True)
    _init_git_repo(ambient)

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path / "does-not-exist"))

    resolved = locate_project_root(start=ambient)

    # The env var named a non-existent path → ignored → walk-up finds ambient.
    assert resolved == ambient.resolve()


def test_env_root_ignored_when_path_is_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file-valued ``SPECIFY_REPO_ROOT`` is not accepted as a project root."""
    ambient = tmp_path / "ambient-checkout"
    (ambient / ".kittify").mkdir(parents=True)
    _init_git_repo(ambient)
    marker_file = tmp_path / "not-a-directory"
    marker_file.write_text("not a repo root\n", encoding="utf-8")

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(marker_file))

    resolved = locate_project_root(start=ambient)

    assert resolved == ambient.resolve()


def test_c003_real_kittify_resolves_same_with_and_without_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-003: a real ``.kittify/`` project resolves identically with/without env.

    Honouring ``SPECIFY_REPO_ROOT`` must not change resolution for projects that
    were already correct: both paths flow through ``get_main_repo_root`` on the
    same directory, so the canonical root is identical.
    """
    project = tmp_path / "real-project"
    (project / ".kittify").mkdir(parents=True)
    _init_git_repo(project)

    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    without_env = locate_project_root(start=project)

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(project))
    with_env = locate_project_root(start=project)

    assert without_env == with_env == project.resolve()


# ---------------------------------------------------------------------------
# GIT_CEILING_DIRECTORIES (#7022): the project walk stops where git's does
# ---------------------------------------------------------------------------


def _ambient_repo_with_sandbox(tmp_path: Path) -> tuple[Path, Path, Path]:
    """An ambient git checkout with a ceiling dir and a bare sandbox below it."""
    ambient = tmp_path / "ambient"
    _init_git_repo(ambient)
    # A real ``HEAD``: the walk treats an empty ``.git`` dir as no checkout at all.
    (ambient / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    ceiling = ambient / "tmp"
    sandbox = ceiling / "sandbox" / "outside-project"
    sandbox.mkdir(parents=True)
    return ambient, ceiling, sandbox


def test_walk_does_not_climb_above_a_git_ceiling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#7022: a dir below a ceiling is not inside the checkout above it.

    ``resolve_canonical_root`` already honors ``GIT_CEILING_DIRECTORIES``; the
    project walk must agree, or a bare directory below a ceiling reads as a
    project that git itself says does not exist.
    """
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    ambient, ceiling, sandbox = _ambient_repo_with_sandbox(tmp_path)

    # Non-vacuity: without the ceiling the walk finds the ambient checkout.
    monkeypatch.delenv("GIT_CEILING_DIRECTORIES", raising=False)
    assert locate_project_root(start=sandbox) == ambient.resolve()

    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(ceiling))
    assert locate_project_root(start=sandbox) is None


def test_a_project_below_the_ceiling_is_still_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ceiling bounds the walk; it does not hide a project inside it."""
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    _ambient, ceiling, sandbox = _ambient_repo_with_sandbox(tmp_path)
    (sandbox / KITTIFY_DIR).mkdir()
    deep = sandbox / "kitty-specs" / "demo"
    deep.mkdir(parents=True)

    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(ceiling))
    assert locate_project_root(start=deep) == sandbox.resolve()


def test_a_project_at_the_ceiling_itself_is_still_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same ceiling semantics as ``resolve_canonical_root``: the listed dir is eligible."""
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    _ambient, ceiling, sandbox = _ambient_repo_with_sandbox(tmp_path)
    (ceiling / KITTIFY_DIR).mkdir()

    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(ceiling))
    assert locate_project_root(start=sandbox) == ceiling.resolve()
