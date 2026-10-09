"""Tests for the canonical ``builtin_mission_type_ids`` / ``_id_set`` accessors.

Covers (per WP01 / contracts/canonical-accessor.md, IC-1a):
- SC-001: a synthetic mission-type YAML injected via a monkeypatched
  ``MissionTypeRepository.default`` root is picked up after
  ``builtin_mission_type_ids.cache_clear()`` — without ever touching the
  real ``packs/built-in/missions/mission_types/`` tree (C-010 cache-vs-test
  seam).
- Un-monkeypatched behavior matches the four shipped built-in ids, sorted.
- ``builtin_mission_type_id_set()`` is a frozenset projection of the same ids.
- Loud-fail transitivity: a ``MissionTypeRepository`` construction error
  (id/filename-stem mismatch) propagates through the accessor rather than
  being swallowed.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from charter.offering.missions.mission_type_repository import (
    MissionTypeRepository,
    builtin_mission_type_id_set,
    builtin_mission_type_ids,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_SHIPPED_MISSION_TYPES_DIR = (
    Path(__file__).parent.parent.parent.parent / "packs" / "built-in" / "missions" / "mission_types"
)
_SHIPPED_IDS = ("documentation", "plan", "research", "software-dev")

_SYNTHETIC_ANALYSIS_YAML = (
    "schema_version: 1\n"
    "id: analysis\n"
    'display_name: "Analysis"\n'
    "action_sequence:\n"
    "  - specify\n"
    "  - plan\n"
)

_MISMATCHED_ID_YAML = (
    "schema_version: 1\n"
    "id: totally-different-id\n"
    'display_name: "Broken"\n'
    "action_sequence:\n"
    "  - specify\n"
)


@pytest.fixture(autouse=True)
def _clear_builtin_mission_type_ids_cache() -> Iterator[None]:
    """Ensure no test leaks a monkeypatched cache value into another test.

    ``builtin_mission_type_ids`` is process-cached via ``functools.cache``.
    Tests that monkeypatch ``MissionTypeRepository.default`` MUST clear the
    cache before asserting, and this fixture guarantees the cache is also
    reset after the test so later tests (including in other modules, under
    ``-n auto``) observe only the real bundled roster.
    """
    builtin_mission_type_ids.cache_clear()
    yield
    builtin_mission_type_ids.cache_clear()


def _patch_default_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Monkeypatch ``MissionTypeRepository.default`` to load from *root*."""

    def _fake_default(cls: type[MissionTypeRepository]) -> MissionTypeRepository:
        return cls(root)

    monkeypatch.setattr(MissionTypeRepository, "default", classmethod(_fake_default))


class TestSyntheticTypePickup:
    """SC-001: a synthetic mission-type YAML is picked up universally."""

    def test_synthetic_analysis_type_is_included(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for shipped_yaml in _SHIPPED_MISSION_TYPES_DIR.glob("*.yaml"):
            shutil.copy(shipped_yaml, tmp_path / shipped_yaml.name)
        (tmp_path / "analysis.yaml").write_text(_SYNTHETIC_ANALYSIS_YAML, encoding="utf-8")

        _patch_default_root(monkeypatch, tmp_path)
        builtin_mission_type_ids.cache_clear()

        result = builtin_mission_type_ids()

        assert "analysis" in result
        assert result == tuple(sorted(result))
        assert set(result) == {*_SHIPPED_IDS, "analysis"}

    def test_synthetic_type_test_does_not_mutate_real_mission_types_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        before = sorted(p.name for p in _SHIPPED_MISSION_TYPES_DIR.glob("*.yaml"))

        (tmp_path / "analysis.yaml").write_text(_SYNTHETIC_ANALYSIS_YAML, encoding="utf-8")
        _patch_default_root(monkeypatch, tmp_path)
        builtin_mission_type_ids.cache_clear()
        builtin_mission_type_ids()

        after = sorted(p.name for p in _SHIPPED_MISSION_TYPES_DIR.glob("*.yaml"))
        assert after == before
        assert "analysis.yaml" not in after


class TestUnpatchedBuiltinAccessors:
    """Un-monkeypatched behavior: exactly the four shipped ids."""

    def test_builtin_mission_type_ids_matches_shipped_yaml_stems(self) -> None:
        assert builtin_mission_type_ids() == tuple(sorted(_SHIPPED_IDS))

    def test_builtin_mission_type_ids_is_sorted(self) -> None:
        result = builtin_mission_type_ids()
        assert result == tuple(sorted(result))

    def test_builtin_mission_type_ids_derives_from_repository_default(self) -> None:
        assert builtin_mission_type_ids() == tuple(MissionTypeRepository.default().ids())

    def test_builtin_mission_type_id_set_is_frozenset_of_ids(self) -> None:
        id_set = builtin_mission_type_id_set()
        assert isinstance(id_set, frozenset)
        assert id_set == frozenset(_SHIPPED_IDS)
        assert id_set == frozenset(builtin_mission_type_ids())

    def test_repeated_calls_return_cached_equal_result(self) -> None:
        first = builtin_mission_type_ids()
        second = builtin_mission_type_ids()
        assert first == second


class TestLoudFailTransitivity:
    """A MissionTypeRepository construction error propagates through the accessor."""

    def test_id_stem_mismatch_raises_through_accessor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "correct-name.yaml").write_text(_MISMATCHED_ID_YAML, encoding="utf-8")

        _patch_default_root(monkeypatch, tmp_path)
        builtin_mission_type_ids.cache_clear()

        with pytest.raises(ValueError, match="does not match filename stem"):
            builtin_mission_type_ids()
