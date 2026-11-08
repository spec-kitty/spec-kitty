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

import os
from functools import partial
from pathlib import Path

import pytest

from specify_cli.context import mission_resolver
from specify_cli.context.mission_resolver import (
    MissionNotFoundError,
    resolve_mission,
)
from tests.context._mission_tree import (
    HANDLES,
    ID_NUMERIC,
    build_mission_tree,
    outcome,
    write_meta,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    """Directories chosen so that an exact name and a lower ladder priority can disagree."""
    return build_mission_tree(tmp_path)


@pytest.mark.parametrize("handle", HANDLES)
def test_resolve_gives_the_full_walk_answer(repo_root: Path, handle: str) -> None:
    walked = outcome(lambda: mission_resolver._resolve_from_index(handle, mission_resolver._build_index(repo_root)))
    assert outcome(lambda: resolve_mission(handle, repo_root)) == walked


def test_the_fixture_exercises_every_ladder_outcome(repo_root: Path) -> None:
    """Without each outcome kind among the handles, the equivalence above would prove less than it claims."""
    kinds = {outcome(partial(resolve_mission, handle, repo_root))[0] for handle in HANDLES}
    assert kinds == {"resolved", "ambiguous", "not-found"}


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


def test_a_non_string_mission_id_elsewhere_no_longer_breaks_an_exact_lookup(repo_root: Path) -> None:
    """The one deliberate difference from the walk: another directory's odd ``meta.json`` is not read.

    ``resolve_mid8`` raises ``TypeError`` on a non-string ``mission_id``, so the full walk fails
    for every handle while one such directory exists (unchanged, pinned below). An exact
    directory name reads only its own ``meta.json`` and now resolves; the odd directory itself
    still raises, as it always did.
    """
    write_meta(repo_root / "kitty-specs" / "092-numeric-id", {"mission_id": ID_NUMERIC})
    assert resolve_mission("001-foo", repo_root).mission_slug == "001-foo"
    with pytest.raises(TypeError):
        resolve_mission("092-numeric-id", repo_root)
    with pytest.raises(TypeError):
        resolve_mission("foo", repo_root)
