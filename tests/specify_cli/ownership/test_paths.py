"""The one ``owned_files`` normaliser and ``kitty-specs/`` test, shared by finalize's two readers."""

from __future__ import annotations

import pytest

from specify_cli.cli.commands.agent import mission_parsing
from specify_cli.ownership import kind_normalisation
from specify_cli.ownership.paths import is_kitty_specs_path, normalize_owned_path

pytestmark = [pytest.mark.fast, pytest.mark.unit]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("docs/a.md", "docs/a.md"),
        ("  ./docs/a.md  ", "docs/a.md"),
        ("././kitty-specs/m/spec.md", "kitty-specs/m/spec.md"),
        ("kitty-specs\\m\\spec.md", "kitty-specs/m/spec.md"),
        (".\\docs\\a.md", "docs/a.md"),
    ],
)
def test_normalize_owned_path(raw: str, expected: str) -> None:
    assert normalize_owned_path(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("kitty-specs", True),
        ("kitty-specs/m/**", True),
        ("./kitty-specs/m/spec.md", True),
        ("kitty-specs\\m\\spec.md", True),
        ("kitty-specs-other/a.md", False),
        ("docs/kitty-specs/a.md", False),
        ("src/a.py", False),
    ],
)
def test_is_kitty_specs_path(raw: str, expected: bool) -> None:
    assert is_kitty_specs_path(raw) is expected


def test_both_finalize_readers_use_the_one_predicate() -> None:
    """The kitty-specs ban and the kind normalisation cannot drift apart again (MED-4)."""
    assert mission_parsing._is_mission_specs_owned_file is is_kitty_specs_path
    assert mission_parsing._normalize_owned_file_path is normalize_owned_path
    assert kind_normalisation.is_kitty_specs_path is is_kitty_specs_path
