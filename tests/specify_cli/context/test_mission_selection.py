"""Unit tests for the shared mission-selection seam (WP01, FR-006/FR-012).

These cover the three building blocks WP02-WP06 reuse:

* :func:`list_missions_for_selection` -- the population helper that lists a
  ``kitty-specs/`` directory only when a ``meta.json`` exists on disk **and**
  ``is_mission_dir`` accepts it (#5875, the same rule the agent-layer
  ``_list_feature_spec_candidates`` uses), so ``next`` and plan/tasks never
  disagree on the count. A spec.md-only folder is residue, not a Mission. A
  legacy ``meta.json`` without a ``mission_id`` is still listed when git tracks
  it, or on a non-git root (existence fallback) -- missions
  ``FsMissionResolver.all_missions()`` silently drops.
* :func:`sole_mission_for_selection` -- the FR-004 sole-mission convention
  (the slug when exactly one mission exists, else ``None``).
* :data:`MISSION_NOT_FOUND_MESSAGE` / :func:`mission_not_found_message` -- the
  single canonical capital-M not-found template the fixed commands adopt.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.context import mission_resolver
from specify_cli.context.mission_resolver import (
    MISSION_NOT_FOUND_MESSAGE,
    MissionListing,
    list_missions_for_selection,
    mission_not_found_message,
    sole_mission_for_selection,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# 26-char ULID-shaped identities ([0-9A-Z]); mid8 is the first 8 chars.
_MISSION_ID_ALPHA = "01J8ALPHA000000000000000AA"
_MISSION_ID_BETA = "01J8BETA000000000000000BBB"


def _write_meta(mission_dir: Path, meta: dict[str, object]) -> None:
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _normal_meta(mission_slug: str, mission_id: str, friendly_name: str) -> dict[str, object]:
    return {
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "friendly_name": friendly_name,
        "mission_id": mission_id,
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-09-18T00:00:00+00:00",
    }


def _stage_three_missions(root: Path) -> None:
    """Two normal missions (with ``mission_id``) + one spec.md-only folder.

    Also seeds noise the population rule must ignore: the spec.md-only folder
    (residue by operator ruling, #5875), a directory bearing neither
    ``spec.md`` nor ``meta.json``, and a stray top-level file.
    """
    specs = root / "kitty-specs"
    _write_meta(specs / "001-alpha", _normal_meta("001-alpha", _MISSION_ID_ALPHA, "Alpha Mission"))
    _write_meta(specs / "002-beta", _normal_meta("002-beta", _MISSION_ID_BETA, "Beta Mission"))

    # Only spec.md, no meta.json at all: residue, not a Mission (#5875).
    legacy = specs / "003-legacy"
    legacy.mkdir(parents=True)
    (legacy / "spec.md").write_text("# Legacy mission\n", encoding="utf-8")

    # Noise that must NOT be counted.
    (specs / "not-a-mission").mkdir()
    (specs / "README.md").write_text("index\n", encoding="utf-8")


def test_ulid_fixtures_are_well_formed() -> None:
    """Guard the fixtures: mid8 assertions below depend on 26-char ULIDs."""
    assert len(_MISSION_ID_ALPHA) == 26
    assert len(_MISSION_ID_BETA) == 26


def test_lists_missions_in_slug_order_excluding_spec_only(tmp_path: Path) -> None:
    _stage_three_missions(tmp_path)

    listings = list_missions_for_selection(tmp_path)

    assert [entry.mission_slug for entry in listings] == ["001-alpha", "002-beta"]
    assert all(isinstance(entry, MissionListing) for entry in listings)


def test_normal_missions_expose_mid8_and_friendly_name(tmp_path: Path) -> None:
    _stage_three_missions(tmp_path)

    by_slug = {entry.mission_slug: entry for entry in list_missions_for_selection(tmp_path)}

    assert by_slug["001-alpha"].mid8 == _MISSION_ID_ALPHA[:8]
    assert by_slug["001-alpha"].friendly_name == "Alpha Mission"
    assert by_slug["002-beta"].mid8 == _MISSION_ID_BETA[:8]
    assert by_slug["002-beta"].friendly_name == "Beta Mission"


def test_spec_only_folder_is_not_listed(tmp_path: Path) -> None:
    """A folder holding only ``spec.md`` is residue, not a Mission (#5875, D1)."""
    _stage_three_missions(tmp_path)

    slugs = {entry.mission_slug for entry in list_missions_for_selection(tmp_path)}

    assert "003-legacy" not in slugs


def test_meta_without_name_falls_back_to_slug(tmp_path: Path) -> None:
    """``friendly_name`` falls back to the slug so listings never blank."""
    specs = tmp_path / "kitty-specs"
    _write_meta(specs / "006-nameless", {"mission_id": _MISSION_ID_ALPHA})

    (listing,) = list_missions_for_selection(tmp_path)

    assert listing.mid8 == _MISSION_ID_ALPHA[:8]
    assert listing.friendly_name == "006-nameless"


def test_meta_without_mission_id_is_counted_with_none_mid8(tmp_path: Path) -> None:
    """A ``meta.json`` lacking ``mission_id`` still counts on a non-git root (existence fallback)."""
    specs = tmp_path / "kitty-specs"
    _write_meta(
        specs / "004-unbackfilled",
        {
            "slug": "004-unbackfilled",
            "mission_slug": "004-unbackfilled",
            "friendly_name": "Unbackfilled Mission",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-09-18T00:00:00+00:00",
        },
    )

    listings = list_missions_for_selection(tmp_path)

    assert len(listings) == 1
    assert listings[0].mission_slug == "004-unbackfilled"
    assert listings[0].mid8 is None
    # friendly_name still read from meta when present.
    assert listings[0].friendly_name == "Unbackfilled Mission"


def test_non_string_mission_id_does_not_crash_discovery(tmp_path: Path) -> None:
    """A valid meta.json whose ``mission_id`` is not a string must not crash
    discovery (guards ``resolve_mid8``'s ``len()`` against a JSON number so one
    odd file cannot break selection for the whole repo)."""
    specs = tmp_path / "kitty-specs"
    _write_meta(
        specs / "005-bad-id",
        {
            "slug": "005-bad-id",
            "mission_slug": "005-bad-id",
            "mission_id": 12345678,  # non-string (JSON number) — must be tolerated
            "friendly_name": "Bad Id Mission",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-09-18T00:00:00+00:00",
        },
    )

    listings = list_missions_for_selection(tmp_path)

    assert len(listings) == 1
    assert listings[0].mission_slug == "005-bad-id"
    # Non-string mission_id is dropped -> treated as legacy (no mid8).
    assert listings[0].mid8 is None
    assert listings[0].friendly_name == "Bad Id Mission"


def test_excludes_dirs_without_spec_or_meta_and_stray_files(tmp_path: Path) -> None:
    _stage_three_missions(tmp_path)

    slugs = {entry.mission_slug for entry in list_missions_for_selection(tmp_path)}

    assert "not-a-mission" not in slugs
    assert "README.md" not in slugs


def test_missing_kitty_specs_returns_empty(tmp_path: Path) -> None:
    assert list_missions_for_selection(tmp_path) == []


def test_count_agrees_with_len(tmp_path: Path) -> None:
    _stage_three_missions(tmp_path)

    listings = list_missions_for_selection(tmp_path)

    # The population count is exposed via the listing length (T003): no second
    # scan, no divergent counter.
    assert len(listings) == 2


def test_sole_mission_returns_slug_for_exactly_one(tmp_path: Path) -> None:
    specs = tmp_path / "kitty-specs"
    _write_meta(specs / "001-only", _normal_meta("001-only", _MISSION_ID_ALPHA, "Only Mission"))

    assert sole_mission_for_selection(tmp_path) == "001-only"


def test_sole_mission_returns_none_for_zero(tmp_path: Path) -> None:
    (tmp_path / "kitty-specs").mkdir()

    assert sole_mission_for_selection(tmp_path) is None


def test_sole_mission_returns_none_for_multiple(tmp_path: Path) -> None:
    _stage_three_missions(tmp_path)

    assert sole_mission_for_selection(tmp_path) is None


def test_sole_mission_ignores_spec_only_folder(tmp_path: Path) -> None:
    """A spec.md-only sibling never blocks (or wins) the sole-Mission auto-select."""
    specs = tmp_path / "kitty-specs"
    _write_meta(specs / "001-only", _normal_meta("001-only", _MISSION_ID_ALPHA, "Only Mission"))
    (specs / "002-residue").mkdir()
    (specs / "002-residue" / "spec.md").write_text("# s\n", encoding="utf-8")

    assert sole_mission_for_selection(tmp_path) == "001-only"


def test_sole_mission_none_when_only_spec_only_folder(tmp_path: Path) -> None:
    specs = tmp_path / "kitty-specs"
    (specs / "001-residue").mkdir(parents=True)
    (specs / "001-residue" / "spec.md").write_text("# s\n", encoding="utf-8")

    assert sole_mission_for_selection(tmp_path) is None


def test_canonical_not_found_message_is_capital_m_form() -> None:
    assert MISSION_NOT_FOUND_MESSAGE == "Mission not found: {handle}"
    assert MISSION_NOT_FOUND_MESSAGE.format(handle="zznope") == "Mission not found: zznope"
    assert mission_not_found_message("zznope") == "Mission not found: zznope"


# ---------------------------------------------------------------------------
# Git-aware selection rule (#5875): meta.json on disk AND is_mission_dir
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "kitty-specs").mkdir()
    (tmp_path / "README.md").write_text("root\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
    return tmp_path


def _commit_all(repo: Path) -> None:
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c")


def _spec_only(repo: Path, slug: str) -> None:
    path = repo / "kitty-specs" / slug
    path.mkdir(parents=True)
    (path / "spec.md").write_text("# s\n", encoding="utf-8")


def _meta_without_id(repo: Path, slug: str) -> None:
    _write_meta(repo / "kitty-specs" / slug, {"mission_slug": slug, "friendly_name": slug})


def _slugs(repo: Path) -> list[str]:
    return [entry.mission_slug for entry in list_missions_for_selection(repo)]


@pytest.mark.git_repo
def test_git_untracked_spec_only_is_excluded(git_repo: Path) -> None:
    _spec_only(git_repo, "001-residue")
    assert _slugs(git_repo) == []
    assert sole_mission_for_selection(git_repo) is None


@pytest.mark.git_repo
def test_git_tracked_spec_only_is_excluded(git_repo: Path) -> None:
    """Tracking a spec.md does not make a folder selectable: a meta.json must exist on disk (D2)."""
    _spec_only(git_repo, "001-residue")
    _commit_all(git_repo)
    assert _slugs(git_repo) == []


@pytest.mark.git_repo
def test_git_untracked_meta_with_id_is_included(git_repo: Path) -> None:
    _write_meta(git_repo / "kitty-specs" / "001-fresh", _normal_meta("001-fresh", _MISSION_ID_ALPHA, "Fresh"))
    assert _slugs(git_repo) == ["001-fresh"]
    assert sole_mission_for_selection(git_repo) == "001-fresh"


@pytest.mark.git_repo
def test_git_untracked_meta_without_id_is_excluded(git_repo: Path) -> None:
    _meta_without_id(git_repo, "001-noid")
    # A committed sibling keeps git aware of kitty-specs/ (the probe returns a non-empty set).
    _write_meta(git_repo / "kitty-specs" / "002-real", _normal_meta("002-real", _MISSION_ID_BETA, "Real"))
    _git(git_repo, "add", "kitty-specs/002-real")
    _git(git_repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "real")
    assert _slugs(git_repo) == ["002-real"]


@pytest.mark.git_repo
def test_git_tracked_meta_without_id_is_included(git_repo: Path) -> None:
    _meta_without_id(git_repo, "001-legacy")
    _commit_all(git_repo)
    (listing,) = list_missions_for_selection(git_repo)
    assert listing.mission_slug == "001-legacy"
    assert listing.mid8 is None


@pytest.mark.git_repo
def test_git_tracked_spec_with_deleted_meta_is_excluded(git_repo: Path) -> None:
    """A Mission whose meta.json was deleted on disk is not selectable, even if git tracks it."""
    _write_meta(git_repo / "kitty-specs" / "001-gone", {"mission_slug": "001-gone"})
    (git_repo / "kitty-specs" / "001-gone" / "spec.md").write_text("# s\n", encoding="utf-8")
    _commit_all(git_repo)
    (git_repo / "kitty-specs" / "001-gone" / "meta.json").unlink()
    assert _slugs(git_repo) == []


# ---------------------------------------------------------------------------
# NFR-001: no git call when every child has an identity; at most one probe per walk
# ---------------------------------------------------------------------------


def _count_probes(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    calls: list[Path] = []

    def _probe(repo_root: Path) -> frozenset[str] | None:
        calls.append(repo_root)
        return None

    monkeypatch.setattr(mission_resolver, "probe_tracked_mission_paths", _probe)
    monkeypatch.setattr(mission_resolver, "tracked_mission_paths", _probe)
    return calls


def test_no_probe_when_every_child_carries_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stage_three_missions(tmp_path)
    calls = _count_probes(monkeypatch)

    assert [e.mission_slug for e in list_missions_for_selection(tmp_path)] == ["001-alpha", "002-beta"]
    assert calls == []


def test_no_git_subprocess_when_every_child_carries_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001, asserted at the git boundary: identity-bearing children never reach git."""
    _stage_three_missions(tmp_path)

    def _no_git(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("selection ran git although every listed child carries a mission_id")

    for name in ("run_git", "is_tracked", "tracked_paths"):
        monkeypatch.setattr(mission_resolver, name, _no_git)

    assert [e.mission_slug for e in list_missions_for_selection(tmp_path)] == ["001-alpha", "002-beta"]


def test_at_most_one_probe_for_several_idless_children(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for slug in ("001-a", "002-b", "003-c"):
        _meta_without_id(tmp_path, slug)
    calls = _count_probes(monkeypatch)

    assert [e.mission_slug for e in list_missions_for_selection(tmp_path)] == ["001-a", "002-b", "003-c"]
    assert len(calls) == 1
