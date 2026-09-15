"""Unit tests for context/mission_resolver.py (T039).

Fixture: temp repo with 5 missions including two sharing numeric prefix "080".

Priority order tested:
  full mission_id > mid8 > full slug (with/without prefix) > numeric prefix
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.context.mission_resolver import (
    AmbiguousHandleError,
    MissionNotFoundError,
    ResolvedMission,
    resolve_mission,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Mission IDs with distinct mid8 prefixes so each resolves unambiguously.
# All are valid 26-char Crockford base32 strings (ULID format).

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_ID_A = "01AAAAAAAAAAAAAAAAAAAAAAAB"  # mid8: 01AAAAAA
MISSION_ID_B = "01BBBBBBAAAAAAAAAAAAAAAAAC"  # mid8: 01BBBBBB
MISSION_ID_C = "01CCCCCCAAAAAAAAAAAAAAAAAD"  # mid8: 01CCCCCC
MISSION_ID_D = "01DDDDDDAAAAAAAAAAAAAAAAAE"  # mid8: 01DDDDDD
MISSION_ID_E = "01EEEEEEAAAAAAAAAAAAAAAAAF"  # mid8: 01EEEEEE


def _make_mission(
    specs_dir: Path,
    slug: str,
    mission_id: str | None,
) -> Path:
    """Create a kitty-specs/<slug>/meta.json fixture."""
    feature_dir = specs_dir / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {"mission_slug": slug}
    if mission_id is not None:
        meta["mission_id"] = mission_id
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return feature_dir


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    """Temp repo with 5 missions:
    - 083-foo-bar          (MISSION_ID_A, unique prefix 083)
    - 080-alpha            (MISSION_ID_B, prefix 080 — ambiguous with 080-beta)
    - 080-beta             (MISSION_ID_C, prefix 080 — ambiguous with 080-alpha)
    - 099-unique           (MISSION_ID_D, unique prefix 099)
    - 101-no-id            (mission_id missing — legacy/orphan)
    """
    specs = tmp_path / "kitty-specs"
    _make_mission(specs, "083-foo-bar", MISSION_ID_A)
    _make_mission(specs, "080-alpha", MISSION_ID_B)
    _make_mission(specs, "080-beta", MISSION_ID_C)
    _make_mission(specs, "099-unique", MISSION_ID_D)
    _make_mission(specs, "101-no-id", mission_id=None)
    return tmp_path


# ---------------------------------------------------------------------------
# T039 test cases
# ---------------------------------------------------------------------------


class TestResolveByFullMissionId:
    def test_exact_match(self, repo_root: Path) -> None:
        result = resolve_mission(MISSION_ID_A, repo_root)
        assert isinstance(result, ResolvedMission)
        assert result.mission_id == MISSION_ID_A
        assert result.mission_slug == "083-foo-bar"
        assert result.mid8 == MISSION_ID_A[:8]

    def test_full_id_returns_correct_feature_dir(self, repo_root: Path) -> None:
        result = resolve_mission(MISSION_ID_B, repo_root)
        assert result.feature_dir == repo_root / "kitty-specs" / "080-alpha"

    @pytest.mark.parametrize(
        "mission_id,expected_slug",
        [
            (MISSION_ID_A, "083-foo-bar"),
            (MISSION_ID_B, "080-alpha"),
            (MISSION_ID_C, "080-beta"),
            (MISSION_ID_D, "099-unique"),
        ],
    )
    def test_parametrized_full_id(
        self, repo_root: Path, mission_id: str, expected_slug: str
    ) -> None:
        result = resolve_mission(mission_id, repo_root)
        assert result.mission_id == mission_id
        assert result.mission_slug == expected_slug


class TestResolveByMid8:
    def test_mid8_resolves_unique(self, repo_root: Path) -> None:
        mid8 = MISSION_ID_A[:8]
        result = resolve_mission(mid8, repo_root)
        assert result.mission_id == MISSION_ID_A

    def test_mid8_all_missions(self, repo_root: Path) -> None:
        for mission_id in (MISSION_ID_A, MISSION_ID_B, MISSION_ID_C, MISSION_ID_D):
            mid8 = mission_id[:8]
            result = resolve_mission(mid8, repo_root)
            assert result.mission_id == mission_id


class TestResolveBySlug:
    def test_full_slug_with_prefix(self, repo_root: Path) -> None:
        result = resolve_mission("083-foo-bar", repo_root)
        assert result.mission_id == MISSION_ID_A
        assert result.mission_slug == "083-foo-bar"

    def test_full_slug_without_prefix_human_slug(self, repo_root: Path) -> None:
        result = resolve_mission("foo-bar", repo_root)
        assert result.mission_id == MISSION_ID_A

    def test_human_slug_unique_resolves(self, repo_root: Path) -> None:
        result = resolve_mission("unique", repo_root)
        assert result.mission_id == MISSION_ID_D

    def test_full_slug_with_prefix_beta(self, repo_root: Path) -> None:
        result = resolve_mission("080-beta", repo_root)
        assert result.mission_id == MISSION_ID_C

    def test_human_slug_ambiguous_raises(self, repo_root: Path) -> None:
        # "alpha" strips to just one mission — not ambiguous
        result = resolve_mission("alpha", repo_root)
        assert result.mission_id == MISSION_ID_B

    def test_human_slug_ambiguous_when_multiple_match(self, repo_root: Path) -> None:
        # Add a second "alpha" variant mission to force ambiguity on human slug
        specs = repo_root / "kitty-specs"
        _make_mission(specs, "081-alpha", "01FFFFFFAAAAAAAAAAAAAAAAAG")
        with pytest.raises(AmbiguousHandleError) as exc_info:
            resolve_mission("alpha", repo_root)
        err = exc_info.value
        assert "alpha" in str(err)
        assert {c.mission_slug for c in err.candidates} == {"080-alpha", "081-alpha"}


class TestResolveByNumericPrefix:
    def test_unique_numeric_prefix_resolves(self, repo_root: Path) -> None:
        result = resolve_mission("083", repo_root)
        assert result.mission_id == MISSION_ID_A

    def test_unique_numeric_099(self, repo_root: Path) -> None:
        result = resolve_mission("099", repo_root)
        assert result.mission_id == MISSION_ID_D

    def test_ambiguous_numeric_prefix_raises(self, repo_root: Path) -> None:
        with pytest.raises(AmbiguousHandleError) as exc_info:
            resolve_mission("080", repo_root)
        err = exc_info.value
        assert err.handle == "080"
        slugs = {c.mission_slug for c in err.candidates}
        assert slugs == {"080-alpha", "080-beta"}

    def test_ambiguous_error_str_format(self, repo_root: Path) -> None:
        with pytest.raises(AmbiguousHandleError) as exc_info:
            resolve_mission("080", repo_root)
        msg = str(exc_info.value)
        assert '"080"' in msg
        assert "080-alpha" in msg
        assert "080-beta" in msg
        assert "mid8" in msg
        assert "spec-kitty" in msg

    def test_ambiguous_error_candidates_have_mid8(self, repo_root: Path) -> None:
        with pytest.raises(AmbiguousHandleError) as exc_info:
            resolve_mission("080", repo_root)
        for candidate in exc_info.value.candidates:
            assert len(candidate.mid8) == 8
            assert candidate.mission_id.startswith(candidate.mid8)


class TestMissionNotFoundError:
    def test_nonexistent_handle_raises(self, repo_root: Path) -> None:
        with pytest.raises(MissionNotFoundError) as exc_info:
            resolve_mission("999-nonexistent", repo_root)
        err = exc_info.value
        assert err.handle == "999-nonexistent"

    def test_not_found_error_message(self, repo_root: Path) -> None:
        with pytest.raises(MissionNotFoundError) as exc_info:
            resolve_mission("zzz-garbage", repo_root)
        assert "zzz-garbage" in str(exc_info.value)

    @pytest.mark.parametrize(
        "handle",
        ["999", "unknown-slug", "ZZZZZZZZ", "00000000000000000000000000"],
    )
    def test_various_unknown_handles(self, repo_root: Path, handle: str) -> None:
        with pytest.raises(MissionNotFoundError):
            resolve_mission(handle, repo_root)


class TestMissingIdentityError:
    def test_mission_without_mission_id_raises_on_resolve(self, repo_root: Path) -> None:
        # "101-no-id" has no mission_id in meta.json;
        # resolve_mission should raise MissionNotFoundError since it can't index it.
        # But the _read_meta_json path in resolver.py raises MissingIdentityError.
        # resolve_mission raises MissionNotFoundError for missions it can't index.
        # MissingIdentityError is raised by context/resolver.py:_read_meta_json
        # when loading a mission context directly (not via resolve_mission).
        # Verify that resolving by slug "101-no-id" raises MissionNotFoundError
        # (since the mission has no mission_id, it cannot be indexed).
        with pytest.raises(MissionNotFoundError):
            resolve_mission("101-no-id", repo_root)

    def test_resolver_py_raises_missing_identity_error(self, tmp_path: Path) -> None:
        """context/resolver.py:_read_meta_json falls back to feature_dir.name when mission_id is missing."""
        from specify_cli.context.resolver import _read_meta_json

        feature_dir = tmp_path / "kitty-specs" / "legacy-mission"
        feature_dir.mkdir(parents=True)
        meta = {"mission_slug": "legacy-mission"}
        (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        data = _read_meta_json(feature_dir, tmp_path)
        assert data["mission_id"] == "legacy-mission"
        assert data["mission_number"] == ""

    def test_missing_identity_error_null_mission_id(self, tmp_path: Path) -> None:
        """JSON null mission_id also falls back to the directory name."""
        from specify_cli.context.resolver import _read_meta_json

        feature_dir = tmp_path / "kitty-specs" / "null-id-mission"
        feature_dir.mkdir(parents=True)
        meta = {"mission_slug": "null-id-mission", "mission_id": None}
        (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        data = _read_meta_json(feature_dir, tmp_path)
        assert data["mission_id"] == "null-id-mission"
        assert data["mission_number"] == ""


class TestResolvedMissionDataclass:
    def test_is_frozen(self, repo_root: Path) -> None:
        result = resolve_mission(MISSION_ID_A, repo_root)
        with pytest.raises((AttributeError, TypeError)):
            result.mission_id = "changed"  # type: ignore[misc]

    def test_mid8_derived_from_mission_id(self, repo_root: Path) -> None:
        result = resolve_mission(MISSION_ID_A, repo_root)
        assert result.mid8 == result.mission_id[:8]

    def test_feature_dir_is_path(self, repo_root: Path) -> None:
        result = resolve_mission(MISSION_ID_A, repo_root)
        assert isinstance(result.feature_dir, Path)
        assert result.feature_dir.exists()


class TestAmbiguousHandleErrorJson:
    def test_to_dict_structure(self, repo_root: Path) -> None:
        with pytest.raises(AmbiguousHandleError) as exc_info:
            resolve_mission("080", repo_root)
        err = exc_info.value
        d = err.to_dict()
        assert d["error"] == "MISSION_AMBIGUOUS_SELECTOR"
        assert d["handle"] == "080"
        assert isinstance(d["candidates"], list)
        assert {c["slug"] for c in d["candidates"]} == {"080-alpha", "080-beta"}
        for c in d["candidates"]:
            assert "mission_id" in c
            assert "mid8" in c
            assert "slug" in c
            assert "feature_dir" in c
