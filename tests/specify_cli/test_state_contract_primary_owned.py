"""Primary-owned declaration on the state contract (#5457, FR-004, NFR-004)."""

import os
from pathlib import PurePosixPath

import pytest

from specify_cli.state.contract import (
    STATE_SURFACES,
    GitClass,
    StateRoot,
    is_primary_owned_path,
    primary_owned_paths,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

METADATA = ".kittify/metadata.yaml"


@pytest.mark.parametrize(
    "path",
    [METADATA, "./" + METADATA, ".kittify\\metadata.yaml", ".\\.kittify\\metadata.yaml", PurePosixPath(METADATA)],
)
def test_metadata_forms_are_primary_owned(path: str | os.PathLike[str]) -> None:
    assert is_primary_owned_path(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "metadata.yaml",
        "sub/.kittify/metadata.yaml",
        "kitty-specs/x/.kittify/metadata.yaml",
        ".kittify/metadata.yml",
        ".kittify/config.yaml",
        ".gitattributes",
        ".gitignore",
        ".kittify/charter/charter.md",
        "/repo/.kittify/metadata.yaml",
        "C:/repo/.kittify/metadata.yaml",
        "",
    ],
)
def test_other_paths_are_not_primary_owned(path: str) -> None:
    # Positive control on the same predicate and surface.
    assert is_primary_owned_path(METADATA) is True
    assert is_primary_owned_path(path) is False


def test_primary_owned_surfaces_are_tracked_project_literals() -> None:
    owned = [s for s in STATE_SURFACES if s.primary_owned]
    assert owned
    for surface in owned:
        assert surface.git_class == GitClass.TRACKED
        assert surface.root == StateRoot.PROJECT
        assert not any(ch in surface.path_pattern for ch in "<*?")


def test_primary_owned_set_is_pinned() -> None:
    # Deliberate pin: adding a primary-owned surface must be a reviewed decision.
    assert primary_owned_paths() == frozenset({METADATA})


def test_declared_paths_are_accepted_unchanged_by_the_predicate() -> None:
    for declared in primary_owned_paths():
        assert is_primary_owned_path(declared)
