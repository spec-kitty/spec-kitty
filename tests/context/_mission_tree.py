"""Shared ``kitty-specs/`` fixture tree for the mission resolver equivalence tests.

Used by ``test_mission_resolver_exact_directory`` (#6517) and
``test_walk_once_mission_resolver`` (#6788): the directories are chosen so an
exact directory name and a lower ladder priority can disagree, and ``HANDLES``
covers every ladder outcome (resolved, ambiguous, not found).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from specify_cli.context.mission_resolver import AmbiguousHandleError, MissionNotFoundError

ID_FOO = "01FOOAAAAAAAAAAAAAAAAAAAAB"
ID_X1 = "01XAAAAAAAAAAAAAAAAAAAAAAC"
ID_X2 = "01XBBBBBAAAAAAAAAAAAAAAAAD"
ID_DIGITS = "01DIGAAAAAAAAAAAAAAAAAAAAE"
ID_MID8_NAMED = "01MIDAAAAAAAAAAAAAAAAAAAAF"
ID_ULID_NAMED = "01ULIDAAAAAAAAAAAAAAAAAAAG"
ID_NUMERIC = 12345
ULID_SHAPED_NAME = "01ZZZZZZZZZZZZZZZZZZZZZZZZ"


def write_meta(directory: Path, payload: object) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "meta.json").write_text(json.dumps(payload), encoding="utf-8")


def build_mission_tree(tmp_path: Path) -> Path:
    """Directories chosen so that an exact name and a lower ladder priority can disagree."""
    specs = tmp_path / "kitty-specs"
    write_meta(specs / "001-foo", {"mission_id": ID_FOO})
    # A legacy directory named like 001-foo's human slug: its exact name must NOT short-circuit,
    # because the ladder resolves "foo" to 001-foo at priority 4.
    write_meta(specs / "foo", {"mission_slug": "foo"})
    write_meta(specs / "080-x", {"mission_id": ID_X1})
    write_meta(specs / "081-x", {"mission_id": ID_X2})
    write_meta(specs / "083", {"mission_id": ID_DIGITS})
    write_meta(specs / "MIDNAMED", {"mission_id": ID_MID8_NAMED})
    write_meta(specs / ULID_SHAPED_NAME, {"mission_id": ID_ULID_NAMED})
    write_meta(specs / "090-array", ["not", "an", "object"])
    write_meta(specs / "091-empty-id", {"mission_id": ""})
    (specs / "093-malformed").mkdir()
    (specs / "093-malformed" / "meta.json").write_text("{not json", encoding="utf-8")
    (specs / "094-no-meta").mkdir()
    (specs / "095-file").write_text("not a directory", encoding="utf-8")
    return tmp_path


HANDLES = [
    "001-foo",
    "foo",
    "x",
    "080-x",
    "081-x",
    "080",
    "083",
    "MIDNAMED",
    ULID_SHAPED_NAME,
    ID_FOO,
    ID_FOO[:8],
    "090-array",
    "091-empty-id",
    "093-malformed",
    "094-no-meta",
    "095-file",
    "array",
    "missing",
    "",
    ".",
    "..",
    "kitty-specs",
    "001-foo/",
    "../kitty-specs/001-foo",
]


def outcome(call: Callable[[], object]) -> tuple[object, ...]:
    """The comparable outcome of a resolution: the row, or the error type with its candidates."""
    try:
        resolved = call()
    except AmbiguousHandleError as error:
        return ("ambiguous", error.handle, tuple(c.mission_slug for c in error.candidates))
    except MissionNotFoundError as error:
        return ("not-found", error.handle)
    return ("resolved", resolved)
