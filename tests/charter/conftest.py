"""Conftest for charter tests."""

import subprocess
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).parent


def _find_repo_root() -> Path:
    """Walk up from this file until a directory containing ``pyproject.toml`` is found."""
    candidate = Path(__file__).resolve().parent
    while candidate != candidate.parent:
        if (candidate / "pyproject.toml").exists():
            return candidate
        candidate = candidate.parent
    raise RuntimeError("Could not find repo root (no pyproject.toml found in any parent directory)")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the repository root as a :class:`~pathlib.Path`.

    Works correctly whether tests run from the main checkout or from a
    worktree, because resolution walks up from this conftest file rather
    than relying on ``Path.cwd()``.
    """
    return _find_repo_root()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark all tests in this directory as fast."""
    for item in items:
        if _THIS_DIR in Path(item.fspath).parents:
            item.add_marker(pytest.mark.fast)


@pytest.fixture(autouse=True)
def _git_init_tmp_path(request: pytest.FixtureRequest) -> None:
    """Initialize a git repo in ``tmp_path`` whenever a charter test uses it.

    WP02 introduced ``resolve_canonical_repo_root`` in
    ``ensure_charter_bundle_fresh``, which raises
    ``NotInsideRepositoryError`` for paths outside any git repository. The
    pre-WP02 charter tests pass raw ``tmp_path`` directories that are not
    git-tracked. Initializing an empty repo is the minimal-touch fix and
    matches how real users invoke the chokepoint.

    The resolver also caches its results, so we reset its LRU after each
    test to keep tests independent on shared fixtures.
    """
    if "tmp_path" in request.fixturenames:
        tmp_path: Path = request.getfixturevalue("tmp_path")
        # Run git init quietly; ignore failure (some tests may not need git
        # but the fixture activates whenever tmp_path is requested).
        try:
            subprocess.run(
                ["git", "init", "--quiet", str(tmp_path)],
                check=False,
                capture_output=True,
            )
        except (FileNotFoundError, OSError):
            pass
    yield
    # Drop the cache so paths from previous tests don't shadow this one.
    try:
        from charter.resolution import resolve_canonical_repo_root

        resolve_canonical_repo_root.cache_clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _reset_catalog_miss_emission_latch() -> None:
    """Reset the once-per-process catalog-miss emission latch around each case.

    #4572: ``emit_catalog_miss_warning`` surfaces each distinct
    ``(selector_kind, artifact_id)`` miss at most once per process; a test
    process is one long command run, so without this fixture the first
    miss-emitting test would consume every later test's emission of the same
    key. Mirrors the ``retrospective.deprecation`` and charter-preflight
    ``ambient_warning`` reset patterns (#3971).
    """
    from charter.activation._catalog_miss import _reset_emitted_for_testing

    _reset_emitted_for_testing()
