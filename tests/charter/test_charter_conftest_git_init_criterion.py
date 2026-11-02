"""Focused regressions for the charter conftest git-init consumer criterion.

The root autouse ``_isolate_global_encoding_provenance`` fixture requests
``tmp_path`` for every test, so membership in ``request.fixturenames`` is not
evidence that a test needs a repository-backed temp directory. These cases pin
the narrowed criterion: only an explicit repository consumer pays for
``git init``; the unrelated isolation request does not.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def test_unrelated_autouse_tmp_path_does_not_create_a_repository(
    request: pytest.FixtureRequest,
) -> None:
    """RED before narrowing: the autouse provenance fixture made ``tmp_path`` a repo.

    This test never declares ``tmp_path``; it only receives it through the
    root autouse isolation fixture. It must not pay for a git repository.
    """
    tmp_path: Path = request.getfixturevalue("tmp_path")
    assert not (tmp_path / ".git").exists(), (
        "tmp_path was git-initialized even though this test has no repository consumer; the root autouse provenance fixture alone must not trigger it"
    )


def test_explicit_tmp_path_consumer_still_gets_a_repository(tmp_path: Path) -> None:
    """A test that explicitly requests ``tmp_path`` keeps real repo semantics."""
    assert (tmp_path / ".git").exists(), "an explicit tmp_path consumer must still receive the canonical repository-backed temp directory"
    result = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert Path(result.stdout.strip()).resolve() == tmp_path.resolve()


@pytest.mark.git_repo
def test_git_repo_marker_is_an_explicit_opt_in(request: pytest.FixtureRequest) -> None:
    """The existing ``git_repo`` marker is a deliberate repository opt-in."""
    tmp_path: Path = request.getfixturevalue("tmp_path")
    assert (tmp_path / ".git").exists(), "a git_repo-marked test must receive the repository-backed tmp_path"


@pytest.fixture
def declared_repository_consumer(tmp_path: Path) -> Path:
    """A non-autouse fixture that explicitly requests ``tmp_path``."""
    return tmp_path


def test_fixture_declared_tmp_path_consumer_gets_a_repository(
    declared_repository_consumer: Path,
) -> None:
    """The criterion follows a test's declared fixture graph, not just its signature."""
    assert (declared_repository_consumer / ".git").exists()


class TestNonHarnessAutouseConsumer:
    """A test-local autouse fixture is a consumer; the root harness fixture is not."""

    @pytest.fixture(autouse=True)
    def _local_tmp_path_consumer(self, tmp_path: Path) -> Path:
        return tmp_path

    def test_non_harness_autouse_consumer_gets_a_repository(self, request: pytest.FixtureRequest) -> None:
        tmp_path: Path = request.getfixturevalue("tmp_path")
        assert (tmp_path / ".git").exists()
