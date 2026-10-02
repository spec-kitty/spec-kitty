"""Value-object tests for the write-location accessor (mission coord-artifact-single-home-01M3V4BE, WP03 T012).

``WriteLocation`` / ``Establishment`` / ``SeedReport`` are imported from the
``mission_runtime`` package root only (MR-1/MR-2).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from mission_runtime import Establishment, SeedReport, TopologySurface, WriteLocation


class TestEstablishment:
    def test_members(self) -> None:
        assert {member.value for member in Establishment} == {
            "none",
            "worktree_materialized",
            "seeded",
            "restored_from_branch",
        }

    def test_does_not_collide_with_coord_state_materialized_by_name(self) -> None:
        """Binding correction: avoid the ``Establishment.MATERIALIZED`` vs
        ``CoordState.MATERIALIZED`` name collision."""
        assert not hasattr(Establishment, "MATERIALIZED")
        assert Establishment.WORKTREE_MATERIALIZED.value == "worktree_materialized"


class TestSeedReport:
    def test_frozen(self) -> None:
        report = SeedReport()
        with pytest.raises(dataclasses.FrozenInstanceError):
            report.carried = ("x",)  # type: ignore[misc]

    def test_defaults(self) -> None:
        report = SeedReport()
        assert report.carried == ()
        assert report.restored_root == ()
        assert report.restored_from_branch == ()
        assert report.coord_commit is None
        assert report.warnings == ()

    def test_kw_only_construction(self) -> None:
        report = SeedReport(carried=("a",), coord_commit="deadbeef")
        assert report.carried == ("a",)
        assert report.coord_commit == "deadbeef"


class TestWriteLocation:
    def test_frozen(self) -> None:
        location = WriteLocation(
            path=Path("/tmp/a"),
            checkout_root=Path("/tmp"),
            surface=TopologySurface.PRIMARY,
            coord_state_before=None,
            establishment=Establishment.NONE,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            location.path = Path("/tmp/b")  # type: ignore[misc]

    def test_defaults_seed_none(self) -> None:
        location = WriteLocation(
            path=Path("/tmp/a"),
            checkout_root=Path("/tmp"),
            surface=TopologySurface.PRIMARY,
            coord_state_before=None,
            establishment=Establishment.NONE,
        )
        assert location.seed is None

    def test_checkout_root_field_exists_and_is_kw_only(self) -> None:
        """Post-tasks squad P-M3: ``checkout_root`` is a real field, added after a
        defaulted ``seed`` field -- ``kw_only=True`` keeps that legal."""
        fields = {f.name for f in dataclasses.fields(WriteLocation)}
        assert "checkout_root" in fields
        location = WriteLocation(
            path=Path("/worktrees/demo-coord/kitty-specs/demo-01ABCDEF"),
            checkout_root=Path("/worktrees/demo-coord"),
            surface=TopologySurface.COORD,
            coord_state_before=None,
            establishment=Establishment.SEEDED,
            seed=SeedReport(carried=("status.events.jsonl",)),
        )
        assert location.checkout_root == Path("/worktrees/demo-coord")
        assert location.seed is not None
        assert location.seed.carried == ("status.events.jsonl",)

    def test_surface_is_the_topology_surface_enum_not_a_literal_string(self) -> None:
        """Binding correction: prefer ``TopologySurface`` over ``Literal`` strings."""
        location = WriteLocation(
            path=Path("/tmp/a"),
            checkout_root=Path("/tmp"),
            surface=TopologySurface.COORD,
            coord_state_before=None,
            establishment=Establishment.NONE,
        )
        assert isinstance(location.surface, TopologySurface)
        assert location.surface is TopologySurface.COORD
