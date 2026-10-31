"""#6462 — profile lineage is built on first use, not in the constructor.

The read-only `agent tasks status` board builds an ``AgentProfileRepository`` to answer
``profile.sentinel`` for its 👤 marker. Before this change the constructor parsed the 13
shipped ``*.graph.yaml`` fragments, so a status read paid the whole lineage graph to read
one boolean.

These guards count the work (graph parses, documents parsed), never wall clock: this host
is shared with concurrent agents and absolute seconds are not a signal (same rule as
#6858). The 👤 marker itself is asserted for parity — a guard that passed by losing the
marker would be a regression, not a fix.
"""

from __future__ import annotations

from typing import Any

import pytest

from charter.offering.agent_profiles.repository import AgentProfileRepository
from tests.charter._render_census import census

pytestmark = [pytest.mark.integration]

#: A profile the shipped pack marks ``sentinel: true`` (human-run). The board's 👤
#: marker is exactly `profile.sentinel`.
_SENTINEL_PROFILE = "human-in-charge"


def _repo() -> AgentProfileRepository:
    return AgentProfileRepository()


class TestProfileMapReadsNoGraph:
    """A profile-map read must not build the lineage graph."""

    def test_construction_parses_no_graph_fragment(self) -> None:
        with census() as state:
            repo = _repo()

        assert repo.list_all(), "the profile catalog must still load"
        assert state.for_kinds(("graph",)) == 0, f"constructing the repository parsed lineage fragments: {state.describe()}"

    def test_sentinel_read_parses_no_graph_fragment(self) -> None:
        """The board's marker read: `get(id).sentinel` -- map only, never lineage."""
        repo = _repo()

        with census() as state:
            profile = repo.get(_SENTINEL_PROFILE)

        assert profile is not None, f"{_SENTINEL_PROFILE} must be in the shipped pack"
        assert profile.sentinel is True
        assert state.for_kinds(("graph",)) == 0, f"reading `sentinel` parsed lineage fragments: {state.describe()}"

    def test_provenance_read_parses_no_graph_fragment(self) -> None:
        repo = _repo()

        with census() as state:
            repo.get_provenance(_SENTINEL_PROFILE)

        assert state.for_kinds(("graph",)) == 0, f"reading provenance parsed lineage fragments: {state.describe()}"


class TestLineageReadsBuildTheGraphOnce:
    """Lineage accessors still work, and build the graph exactly once."""

    def test_children_build_the_graph_once_and_stay_cached(self) -> None:
        repo = _repo()

        with census() as graph_census:
            repo.get_children("python-pedro")
            first = graph_census.for_kinds(("graph",))

        with census() as second_census:
            repo.get_children("python-pedro")

        assert first > 0, "a lineage read must build the shipped graph"
        assert second_census.for_kinds(("graph",)) == 0, "the built graph must be reused, not rebuilt per call"

    def test_explicit_drg_bypasses_the_lazy_build(self) -> None:
        """An explicit graph is authoritative: no shipped fragment is parsed at all."""
        from charter.offering.drg.models import DRGGraph

        empty = DRGGraph(
            schema_version="1.0",
            generated_at="1970-01-01T00:00:00Z",
            generated_by="tests",
            nodes=[],
            edges=[],
        )

        with census() as state:
            repo = AgentProfileRepository(drg=empty)
            assert repo.drg is empty
            assert repo.get_ancestors("python-pedro") == []

        assert state.for_kinds(("graph",)) == 0, f"an explicit drg must not parse shipped fragments: {state.describe()}"

    def test_unloadable_graph_still_degrades_to_empty_lineage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The documented degradation moves to first use; it does not disappear."""
        from charter.offering.agent_profiles import repository as repository_module
        from charter.offering.drg.loader import DRGLoadError

        def _boom() -> Any:
            raise DRGLoadError("shipped graph unreadable")

        # Patch the seam the degradation wraps (``_default_drg`` catches this), not
        # ``_default_drg`` itself: the contract under test is that an unreadable
        # shipped graph degrades to an empty graph, never that callers catch it.
        monkeypatch.setattr(repository_module, "load_built_in_graph", _boom)

        repo = _repo()
        assert repo.list_all(), "a profile-map read must not raise on an unloadable graph"
        assert repo.get_ancestors("python-pedro") == [], "lineage must degrade to empty, not propagate"

    def test_profile_list_unchanged_across_a_lineage_read(self) -> None:
        repo = _repo()
        before = sorted(profile.profile_id for profile in repo.list_all())

        repo.get_children("python-pedro")

        assert sorted(profile.profile_id for profile in repo.list_all()) == before
