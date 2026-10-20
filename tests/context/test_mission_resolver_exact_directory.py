"""The exact-directory lookup of ``FsMissionResolver.resolve`` gives the full walk's answer (#6517).

``FsMissionResolver.resolve`` answers a handle that names an indexed ``kitty-specs/``
directory exactly by reading that one ``meta.json`` instead of walking every Mission.
These tests pin that the answer, the error type and the ambiguity candidates are the
ones the priority ladder over a full ``_build_index`` walk gives, for every handle form
and for the inputs where the lookup must decline (legacy, malformed or non-object
``meta.json``, a file, a mid8- or ULID-shaped directory name, a path that is not a single
segment), and that a run of exact-name lookups never walks the tree.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from specify_cli.context import mission_resolver
from specify_cli.context.mission_resolver import (
    AmbiguousHandleError,
    FsMissionResolver,
    MissionNotFoundError,
    resolve_mission,
)
from specify_cli.mission_metadata import OnMalformed, load_meta

pytestmark = [pytest.mark.unit, pytest.mark.fast]

ID_FOO = "01FOOAAAAAAAAAAAAAAAAAAAAB"
ID_X1 = "01XAAAAAAAAAAAAAAAAAAAAAAC"
ID_X2 = "01XBBBBBAAAAAAAAAAAAAAAAAD"
ID_DIGITS = "01DIGAAAAAAAAAAAAAAAAAAAAE"
ID_MID8_NAMED = "01MIDAAAAAAAAAAAAAAAAAAAAF"
ID_ULID_NAMED = "01ULIDAAAAAAAAAAAAAAAAAAAG"
ID_NUMERIC = 12345
ULID_SHAPED_NAME = "01ZZZZZZZZZZZZZZZZZZZZZZZZ"


def _write_meta(directory: Path, payload: object) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "meta.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    """Directories chosen so that an exact name and a lower ladder priority can disagree."""
    specs = tmp_path / "kitty-specs"
    _write_meta(specs / "001-foo", {"mission_id": ID_FOO})
    # A legacy directory named like 001-foo's human slug: its exact name must NOT short-circuit,
    # because the ladder resolves "foo" to 001-foo at priority 4.
    _write_meta(specs / "foo", {"mission_slug": "foo"})
    _write_meta(specs / "080-x", {"mission_id": ID_X1})
    _write_meta(specs / "081-x", {"mission_id": ID_X2})
    _write_meta(specs / "083", {"mission_id": ID_DIGITS})
    _write_meta(specs / "MIDNAMED", {"mission_id": ID_MID8_NAMED})
    _write_meta(specs / ULID_SHAPED_NAME, {"mission_id": ID_ULID_NAMED})
    _write_meta(specs / "090-array", ["not", "an", "object"])
    _write_meta(specs / "091-empty-id", {"mission_id": ""})
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


def _outcome(call: object) -> tuple[object, ...]:
    """The comparable outcome of a resolution: the row, or the error type with its candidates."""
    try:
        resolved = call()  # type: ignore[operator]
    except AmbiguousHandleError as error:
        return ("ambiguous", error.handle, tuple(c.mission_slug for c in error.candidates))
    except MissionNotFoundError as error:
        return ("not-found", error.handle)
    return ("resolved", resolved)


@pytest.mark.parametrize("handle", HANDLES)
def test_resolve_gives_the_full_walk_answer(repo_root: Path, handle: str) -> None:
    walked = _outcome(lambda: mission_resolver._resolve_from_index(handle, mission_resolver._build_index(repo_root)))
    assert _outcome(lambda: resolve_mission(handle, repo_root)) == walked


def test_the_fixture_exercises_every_ladder_outcome(repo_root: Path) -> None:
    """Without each outcome kind among the handles, the equivalence above would prove less than it claims."""
    kinds = {_outcome(lambda h=handle: resolve_mission(h, repo_root))[0] for handle in HANDLES}
    assert kinds == {"resolved", "ambiguous", "not-found"}


@pytest.mark.parametrize(
    ("handle", "expected_slug"),
    [("001-foo", "001-foo"), ("080-x", "080-x"), ("083", "083")],
)
def test_an_exact_indexed_name_never_walks(repo_root: Path, monkeypatch: pytest.MonkeyPatch, handle: str, expected_slug: str) -> None:
    def no_walk(_root: Path) -> list[mission_resolver.ResolvedMission]:
        raise AssertionError("the full kitty-specs/ walk ran for an exact indexed directory name")

    monkeypatch.setattr(mission_resolver, "_build_index", no_walk)
    resolved = FsMissionResolver(repo_root).resolve(handle)
    assert resolved.mission_slug == expected_slug
    assert resolved.feature_dir == repo_root / "kitty-specs" / expected_slug


@pytest.mark.parametrize(
    "handle",
    ["foo", "090-array", "091-empty-id", "093-malformed", "094-no-meta", "095-file", "MIDNAMED", ULID_SHAPED_NAME, "..", "x"],
)
def test_the_lookup_declines_what_it_cannot_decide(repo_root: Path, handle: str) -> None:
    """Unindexed directories, files, mid8- or ULID-shaped names and non-entries fall through to the walk."""
    assert mission_resolver._resolve_exact_directory(repo_root, handle) is None


def test_membership_is_the_exact_listing_name_not_existence(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A case-insensitive filesystem answers ``exists()`` for ``001-FOO``; only the listing tells the real name.

    Simulated by a listing that spells the directory differently from the handle: the
    lookup must decline although the path exists, as the walk would not match it either.
    """
    real_listdir = os.listdir
    monkeypatch.setattr(os, "listdir", lambda path: [name.upper() for name in real_listdir(path)])
    assert (repo_root / "kitty-specs" / "001-foo").is_dir()
    assert mission_resolver._index_entry_named(repo_root, "001-foo") is None


def test_an_absent_kitty_specs_declines(tmp_path: Path) -> None:
    assert mission_resolver._index_entry_named(tmp_path, "001-foo") is None
    with pytest.raises(MissionNotFoundError):
        resolve_mission("001-foo", tmp_path)


def test_exact_name_lookups_read_one_meta_each(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolving every Mission by its directory name reads N ``meta.json`` files, not N squared."""
    specs = tmp_path / "kitty-specs"
    names = [f"{index:03d}-mission" for index in range(40)]
    for index, name in enumerate(names):
        _write_meta(specs / name, {"mission_id": f"01{index:024d}"})
    reads: list[Path] = []

    def counted(path: Path, *, on_malformed: OnMalformed = "raise") -> dict[str, Any] | None:
        reads.append(Path(path))
        meta: dict[str, Any] | None = load_meta(path, on_malformed=on_malformed)
        return meta

    monkeypatch.setattr("specify_cli.context.mission_resolver.load_meta", counted)
    resolver = FsMissionResolver(tmp_path)
    assert [resolver.resolve(name).mission_slug for name in names] == names
    assert len(reads) == len(names)


def test_a_non_string_mission_id_elsewhere_no_longer_breaks_an_exact_lookup(repo_root: Path) -> None:
    """The one deliberate difference from the walk: another directory's odd ``meta.json`` is not read.

    ``resolve_mid8`` raises ``TypeError`` on a non-string ``mission_id``, so the full walk fails
    for every handle while one such directory exists (unchanged, pinned below). An exact
    directory name reads only its own ``meta.json`` and now resolves; the odd directory itself
    still raises, as it always did.
    """
    _write_meta(repo_root / "kitty-specs" / "092-numeric-id", {"mission_id": ID_NUMERIC})
    assert resolve_mission("001-foo", repo_root).mission_slug == "001-foo"
    with pytest.raises(TypeError):
        resolve_mission("092-numeric-id", repo_root)
    with pytest.raises(TypeError):
        resolve_mission("foo", repo_root)
