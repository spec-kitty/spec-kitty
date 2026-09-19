"""Seam test for ``specify_cli.merge.resolve`` (mission #2057, WP04).

Covers slug extraction, merge-state key-candidate ordering, state load/clear/
cleanup, and target-branch resolution. The re-export-identity and one-way-
import guards live in the consolidated
``tests/merge/test_merge_compat_surface.py`` (WP04,
dev-assist-retire-path-hardening-01KXAVR0 / #2565) — this file keeps only the
functional coverage. The state-key candidate ORDER (modern ULID before legacy
slug) is locked.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.merge import resolve
from specify_cli.merge.state import MergeState

pytestmark = pytest.mark.fast


# --- _extract_mission_slug --------------------------------------------------


def test_extract_mission_slug_legacy_nnn_and_lane() -> None:
    assert resolve._extract_mission_slug("017-smarter-feature-merge") == "017-smarter-feature-merge"
    assert resolve._extract_mission_slug("017-smarter-feature-merge-lane-a") == "017-smarter-feature-merge"
    assert resolve._extract_mission_slug("totally-unparseable!!") is None


# --- _merge_state_key_candidates (ORDER is locked) --------------------------


def test_key_candidates_empty_for_no_slug() -> None:
    assert resolve._merge_state_key_candidates(Path("/r"), None) == []


def test_key_candidates_ulid_before_slug(tmp_path: Path) -> None:
    """Modern ULID key precedes the legacy slug key; duplicates collapsed."""
    feature_dir = tmp_path / "kitty-specs" / "my-mission"
    feature_dir.mkdir(parents=True)

    class _Identity:
        mission_id = "01ABCDEF000000000000000000"

    # WP05 (read-side-placement-seam-migration) routed the merge-state-key
    # feature-dir lookup off `candidate_feature_dir_for_mission` onto
    # `placement_seam(...).read_dir(MissionArtifactKind.PRIMARY_METADATA)`
    # (resolve.py:105-106). Patch the seam entry point the module calls now.
    with (
        patch.object(
            resolve, "placement_seam", return_value=MagicMock(read_dir=MagicMock(return_value=feature_dir))
        ),
        patch.object(resolve, "get_main_repo_root", return_value=tmp_path),
        patch.object(resolve, "resolve_mission_identity", return_value=_Identity()),
    ):
        keys = resolve._merge_state_key_candidates(tmp_path, "my-mission")
    assert keys == ["01ABCDEF000000000000000000", "my-mission"]


def test_key_candidates_slug_only_when_no_identity(tmp_path: Path) -> None:
    with (
        patch.object(resolve, "placement_seam", side_effect=RuntimeError("boom")),
        patch.object(resolve, "get_main_repo_root", return_value=tmp_path),
    ):
        keys = resolve._merge_state_key_candidates(tmp_path, "my-mission")
    assert keys == ["my-mission"]


# --- _load_merge_state_entry_for_mission ------------------------------------


def _state(slug: str = "m", mid: str = "01ID") -> MergeState:
    return MergeState(mission_id=mid, mission_slug=slug, target_branch="main", wp_order=["WP01"])


def test_load_entry_no_slug_uses_default_state() -> None:
    st = _state()
    with patch.object(resolve, "load_state", return_value=st):
        assert resolve._load_merge_state_entry_for_mission(Path("/r"), None) == (None, st)
    with patch.object(resolve, "load_state", return_value=None):
        assert resolve._load_merge_state_entry_for_mission(Path("/r"), None) is None


def test_load_entry_returns_first_matching_key(tmp_path: Path) -> None:
    st = _state(mid="01ULID")
    with (
        patch.object(resolve, "_merge_state_key_candidates", return_value=["01ULID", "m"]),
        patch.object(resolve, "load_state", side_effect=lambda _r, k=None: st if k == "01ULID" else None),
    ):
        key, state = resolve._load_merge_state_entry_for_mission(tmp_path, "m")
    assert key == "01ULID"
    assert state is st


def test_load_state_for_mission_unwraps_entry() -> None:
    st = _state()
    with patch.object(resolve, "_load_merge_state_entry_for_mission", return_value=("k", st)):
        assert resolve._load_merge_state_for_mission(Path("/r"), "m") is st
    with patch.object(resolve, "_load_merge_state_entry_for_mission", return_value=None):
        assert resolve._load_merge_state_for_mission(Path("/r"), "m") is None


# --- _load_or_create_merge_state --------------------------------------------


def test_load_or_create_returns_existing_canonical() -> None:
    st = _state(mid="01CANON")
    with patch.object(resolve, "load_state", return_value=st):
        result, existed = resolve._load_or_create_merge_state(
            main_repo=Path("/r"), mission_slug="m", canonical_id="01CANON",
            target_branch="main", wp_order=["WP01"], push_requested=False,
        )
    assert result is st and existed is True


def test_load_or_create_creates_new_when_absent() -> None:
    saved: list[MergeState] = []
    with (
        patch.object(resolve, "load_state", return_value=None),
        patch.object(resolve, "_load_merge_state_entry_for_mission", return_value=None),
        patch.object(resolve, "save_state", side_effect=lambda s, _r: saved.append(s)),
    ):
        result, existed = resolve._load_or_create_merge_state(
            main_repo=Path("/r"), mission_slug="m", canonical_id="01NEW",
            target_branch="main", wp_order=["WP01"], push_requested=True,
        )
    assert existed is False
    assert result.mission_id == "01NEW"
    assert result.push_requested is True
    assert saved == [result]


def test_load_or_create_migrates_legacy_state() -> None:
    legacy = _state(mid="01LEGACY")
    cleared: list[str] = []
    with (
        patch.object(resolve, "load_state", return_value=None),
        patch.object(resolve, "_load_merge_state_entry_for_mission", return_value=("01LEGACY", legacy)),
        patch.object(resolve, "save_state", lambda *a, **k: None),
        patch.object(resolve, "clear_state", side_effect=lambda _r, k: cleared.append(k)),
    ):
        result, existed = resolve._load_or_create_merge_state(
            main_repo=Path("/r"), mission_slug="m", canonical_id="01CANON",
            target_branch="main", wp_order=["WP01"], push_requested=False,
        )
    assert existed is True
    assert result.mission_id == "01CANON"
    assert cleared == ["01LEGACY"]


# --- _clear_merge_state_for_mission -----------------------------------------


def test_clear_state_no_slug_clears_default() -> None:
    with patch.object(resolve, "clear_state", return_value=True) as m:
        assert resolve._clear_merge_state_for_mission(Path("/r"), None) is True
    m.assert_called_once_with(Path("/r"))


def test_clear_state_clears_all_candidate_keys(tmp_path: Path) -> None:
    cleared: list[str] = []

    def _clear(_r: Path, k: str) -> bool:
        cleared.append(k)
        return True

    with (
        patch.object(resolve, "_merge_state_key_candidates", return_value=["01ULID", "m"]),
        patch.object(resolve, "_iter_merge_states_for_slug", return_value=[]),
        patch.object(resolve, "clear_state", side_effect=_clear),
    ):
        result = resolve._clear_merge_state_for_mission(tmp_path, "m")
    assert result is True
    assert cleared == ["01ULID", "m"]


# --- _cleanup_merge_workspaces_for_state ------------------------------------


def test_cleanup_workspaces_dedups_keys(tmp_path: Path) -> None:
    cleaned: list[str] = []
    st = _state(slug="m", mid="01ULID")

    def _record(k: str, _r: Path) -> None:
        cleaned.append(k)

    with (
        patch.object(resolve, "_merge_state_key_candidates", return_value=["01ULID", "m"]),
        patch.object(resolve, "cleanup_merge_workspace", side_effect=_record),
    ):
        resolve._cleanup_merge_workspaces_for_state(
            tmp_path, mission_slug="m", state_entry=("01ULID", st)
        )
    # Deduped, falsy keys dropped, order preserved.
    assert cleaned == ["01ULID", "m"]


# --- _resolve_target_branch -------------------------------------------------


# --- _iter_merge_states_for_slug: cross-mission isolation (#2899) ----------


def test_iter_merge_states_skips_corrupt_sibling_and_finds_target(tmp_path: Path) -> None:
    """A sibling mission's corrupt ``state.json`` must not abort resolving
    ANOTHER mission's merge state.

    Pre-fix, ``_iter_merge_states_for_slug`` called ``load_state(repo_root,
    candidate.name)`` with an explicit mission_id for every runtime-merge
    directory — the fail-closed path that RAISES ``MergeStateReadError`` on a
    corrupt ``state.json`` (WP07/#4746). One mission's corrupt state
    therefore aborted the scan before the target mission (sorted after it)
    was ever reached, violating the same cross-mission isolation invariant
    ``state.py``'s own two scan-all loops (``load_state``'s no-mission_id
    scan and the ``pending_coord_reconcile`` enumeration generator) already
    preserve.
    """
    runtime_merge_dir = tmp_path / ".kittify" / "runtime" / "merge"

    # Sorts before "target-mission" — corrupt sibling is hit FIRST.
    corrupt_dir = runtime_merge_dir / "corrupt-mission"
    corrupt_dir.mkdir(parents=True)
    (corrupt_dir / "state.json").write_text("{not valid json", encoding="utf-8")

    target_dir = runtime_merge_dir / "target-mission"
    target_dir.mkdir(parents=True)
    target_state = MergeState(
        mission_id="target-mission",
        mission_slug="target-slug",
        target_branch="main",
        wp_order=["WP01"],
    )
    (target_dir / "state.json").write_text(json.dumps(target_state.to_dict()), encoding="utf-8")

    matches = resolve._iter_merge_states_for_slug(tmp_path, "target-slug")

    assert [key for key, _state in matches] == ["target-mission"], (
        "the corrupt sibling must be skipped, not raised, so the target "
        f"mission's merge state is still found; matches={matches}"
    )
    assert matches[0][1].mission_slug == "target-slug"


def test_resolve_target_branch_delegates() -> None:
    with patch(
        "specify_cli.core.paths.resolve_merge_target_branch",
        return_value=("prog/2057-merge", "meta"),
    ):
        assert resolve._resolve_target_branch(Path("/r"), "m", None) == ("prog/2057-merge", "meta")
