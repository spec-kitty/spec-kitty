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


#: Root-conftest autouse fixtures that request ``tmp_path`` for isolation only.
#: ``_isolate_global_encoding_provenance`` gives every test a ``tmp_path``, so
#: membership in ``request.fixturenames`` is NOT evidence that the test needs a
#: repository. Keep this list explicit: a new harness-only autouse fixture
#: added here avoids needless ``git init``; a new consumer must NOT be added.
_UNRELATED_TMP_PATH_AUTOUSE = frozenset({"_isolate_global_encoding_provenance"})

#: Existing explicit repository opt-in marker (a real ``git init`` is created).
_GIT_REPO_MARKER = "git_repo"


def _consumer_requests_tmp_path(request: pytest.FixtureRequest) -> bool:
    """Return whether this test's own fixture graph explicitly requests ``tmp_path``.

    The search starts from the test's declared arguments plus its autouse
    fixtures, but does not follow pytest's harness-only isolation fixtures
    (:data:`_UNRELATED_TMP_PATH_AUTOUSE`). A repository consumer always requests
    ``tmp_path`` directly, through a fixture it declares, or through a
    non-harness autouse fixture — all three are followed. If pytest's fixture
    metadata is unavailable we fail safe and keep the historical init.
    """
    info = getattr(request.node, "_fixtureinfo", None)
    if info is None:
        return "tmp_path" in request.fixturenames

    pending = [name for name in info.initialnames if name not in _UNRELATED_TMP_PATH_AUTOUSE]
    seen: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        if name == "tmp_path":
            return True
        if name in _UNRELATED_TMP_PATH_AUTOUSE:
            continue
        for fixture_def in info.name2fixturedefs.get(name, ()):
            pending.extend(fixture_def.argnames)
    return False


def _needs_repository_tmp_path(request: pytest.FixtureRequest) -> bool:
    """Whether this test should pay for a repository-backed ``tmp_path``."""
    if request.node.get_closest_marker(_GIT_REPO_MARKER) is not None:
        return True
    return _consumer_requests_tmp_path(request)


def _git_init(path: Path) -> None:
    """Initialize ``path`` as a quiet git work tree; ignore environment failure."""
    try:
        subprocess.run(
            ["git", "init", "--quiet", str(path)],
            check=False,
            capture_output=True,
        )
    except (FileNotFoundError, OSError):
        pass


@pytest.fixture(autouse=True)
def _git_init_tmp_path(request: pytest.FixtureRequest) -> None:
    """Initialize a git repo in ``tmp_path`` only for real repository consumers.

    WP02 introduced ``resolve_canonical_repo_root`` in
    ``ensure_charter_bundle_fresh``, which raises
    ``NotInsideRepositoryError`` for paths outside any git repository. The
    pre-WP02 charter tests pass raw ``tmp_path`` directories that are not
    git-tracked. Initializing an empty repo is the minimal-touch fix and
    matches how real users invoke the chokepoint.

    **Consumer criterion (CI speed hardening).** The root autouse
    ``_isolate_global_encoding_provenance`` fixture requests ``tmp_path`` for
    every test, which previously made this fixture effectively universal. A
    test now gets a repository only when it explicitly requests ``tmp_path``
    through its own fixture graph, or carries the ``git_repo`` marker. Tests
    that merely inherit the isolation ``tmp_path`` keep a plain temporary
    directory. Dynamic ``request.getfixturevalue('tmp_path')`` or
    ``tmp_path_factory`` consumers needing a repository must opt in with
    ``@pytest.mark.git_repo``; the fixture does not infer dependencies from
    a test body.

    The resolver also caches its results, so we reset its LRU after each
    test to keep tests independent on shared fixtures — whether or not this
    fixture initialized a repository.
    """
    if _needs_repository_tmp_path(request):
        _git_init(request.getfixturevalue("tmp_path"))
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
