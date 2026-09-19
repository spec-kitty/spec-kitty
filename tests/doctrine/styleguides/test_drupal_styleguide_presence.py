"""WP01/T006 — failing verification for the shipped Drupal doctrine inventory.

Mission ``drupal-dries-profile-01M28X69``. RED half of red-first
discipline: none of the four new artifacts exist yet, so the presence and
``suggests``-edge assertions below must fail for *absence*, never for an
import or collection error.

Covers contract C-P5 (node inventory rises by exactly four: 1 agent_profile,
2 styleguide, 1 toolguide) and the ``suggests`` edges of C-S7
(``data-model.md`` E7): each new styleguide suggests the profile, and
``drupal-conventions`` additionally suggests the toolguide.

Anti-tautology count property (per the WP01 prompt and
``tests/doctrine/_builtin_inventory.py``'s own docstring): expectations are
derived by **globbing the shipped source files**, independently of the graph
under test, never a frozen literal. ``_builtin_inventory.py`` already exposes
this for ``agent_profile`` (``builtin_profile_ids``); this module mirrors the
same idiom for the two kinds it does not expose an id-set helper for
(``styleguide``, ``toolguide``), reusing its ``PACK_ROOT`` /
``FILE_BACKED_NODE_GLOBS`` constants rather than inventing a second inventory
surface.
"""

from __future__ import annotations

import pytest
from ruamel.yaml import YAML

from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.models import DRGGraph, Relation
from charter.offering.styleguides.repository import StyleguideRepository
from charter.offering.toolguides.repository import ToolguideRepository
from tests.doctrine._builtin_inventory import FILE_BACKED_NODE_GLOBS, PACK_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_YAML = YAML(typ="safe")

_PROFILE_URN = "agent_profile:drupal-dries"
_CONVENTIONS_URN = "styleguide:drupal-conventions"
_SECURITY_URN = "styleguide:drupal-security-performance"
_TOOLGUIDE_URN = "toolguide:drupal-review-checks"

_EXPECTED_NEW_URNS = (_PROFILE_URN, _CONVENTIONS_URN, _SECURITY_URN, _TOOLGUIDE_URN)


def _shipped_ids(kind: str, id_field: str) -> set[str]:
    """Glob-derive shipped ids for *kind* from the source files on disk.

    Independent of the DRG loader/extractor under test -- mirrors
    ``tests/doctrine/_builtin_inventory.builtin_profile_ids`` for the
    ``styleguide``/``toolguide`` kinds that module does not itself expose an
    id-set helper for. A loader that drops a shipped file diverges from this
    set; this function never reads the graph, so it cannot be vacuously
    tautological with it.
    """
    ids: set[str] = set()
    for path in PACK_ROOT.glob(FILE_BACKED_NODE_GLOBS[kind]):
        data = _YAML.load(path.read_text(encoding="utf-8"))
        ids.add(data[id_field])
    return ids


@pytest.fixture(scope="module")
def graph() -> DRGGraph:
    """The shipped built-in DRG -- same seam as the sibling doctrine suites."""
    return load_built_in_graph()


class TestFourNewArtifactsPresentAndLoad:
    """C-P5 positive clause: the four new artifacts exist and load."""

    def test_four_new_urns_present_in_graph(self, graph: DRGGraph) -> None:
        # Arrange / Act
        node_urns = graph.node_urns()
        # Assert
        missing = [urn for urn in _EXPECTED_NEW_URNS if urn not in node_urns]
        assert missing == [], f"expected new nodes not present in built-in DRG: {missing}"

    def test_drupal_conventions_styleguide_loads(self) -> None:
        # Arrange
        repo = StyleguideRepository()
        # Act / Assert
        assert repo.get("drupal-conventions") is not None

    def test_drupal_security_performance_styleguide_loads(self) -> None:
        # Arrange
        repo = StyleguideRepository()
        # Act / Assert
        assert repo.get("drupal-security-performance") is not None

    def test_drupal_review_checks_toolguide_loads(self) -> None:
        # Arrange
        repo = ToolguideRepository()
        # Act / Assert
        assert repo.get("drupal-review-checks") is not None


class TestAntiPatternsFiledInDedicatedField:
    """The fourteen community anti-patterns must load as ``Styleguide.anti_patterns``
    (the schema's dedicated field), not sit under ``patterns``."""

    @pytest.mark.parametrize(
        ("styleguide_id", "expected"),
        [("drupal-conventions", 9), ("drupal-security-performance", 5)],
    )
    def test_anti_patterns_load_through_the_model(self, styleguide_id: str, expected: int) -> None:
        # Arrange
        repo = StyleguideRepository()
        # Act
        styleguide = repo.get(styleguide_id)
        # Assert
        assert styleguide is not None
        assert len(styleguide.anti_patterns) == expected
        assert styleguide.patterns, "positive patterns must remain in `patterns`"


class TestFilesystemDerivedInventoryAgrees:
    """C-P5 / NFR-007 anti-tautology guard: filesystem and graph agree, and
    the new ids are exactly the four this mission sanctioned -- not a
    hardcoded literal, but derived from the shipped source tree.
    """

    def test_new_profile_id_is_shipped_on_disk(self) -> None:
        # Act
        profile_ids = _shipped_ids("agent_profile", "profile-id")
        # Assert
        assert "drupal-dries" in profile_ids

    def test_new_styleguide_ids_are_shipped_on_disk(self) -> None:
        # Act
        styleguide_ids = _shipped_ids("styleguide", "id")
        # Assert
        missing = {"drupal-conventions", "drupal-security-performance"} - styleguide_ids
        assert missing == set(), f"missing shipped styleguide id(s): {missing}"

    def test_new_toolguide_id_is_shipped_on_disk(self) -> None:
        # Act
        toolguide_ids = _shipped_ids("toolguide", "id")
        # Assert
        assert "drupal-review-checks" in toolguide_ids

    def test_graph_agrees_with_filesystem_for_touched_kinds(self, graph: DRGGraph) -> None:
        """No node was silently dropped, and no unsanctioned extra node of
        these kinds appears: the glob-derived id set and the loaded graph's
        id set for each touched kind must match exactly.
        """
        # Arrange
        kind_to_id_field = {
            "agent_profile": "profile-id",
            "styleguide": "id",
            "toolguide": "id",
        }
        node_urns = graph.node_urns()
        # Act / Assert
        for kind, id_field in kind_to_id_field.items():
            shipped_ids = _shipped_ids(kind, id_field)
            graph_ids = {urn.split(":", 1)[1] for urn in node_urns if urn.split(":", 1)[0] == kind}
            assert shipped_ids == graph_ids, f"{kind}: filesystem ids {sorted(shipped_ids)} != graph ids {sorted(graph_ids)}"


class TestSuggestsEdges:
    """C-S7 (data-model.md E7): each styleguide suggests the profile;
    drupal-conventions also suggests the review-checks toolguide.
    """

    def test_drupal_conventions_suggests_the_profile(self, graph: DRGGraph) -> None:
        # Act
        targets = {edge.target for edge in graph.edges_from(_CONVENTIONS_URN, Relation.SUGGESTS)}
        # Assert
        assert _PROFILE_URN in targets

    def test_drupal_conventions_suggests_the_toolguide(self, graph: DRGGraph) -> None:
        # Act
        targets = {edge.target for edge in graph.edges_from(_CONVENTIONS_URN, Relation.SUGGESTS)}
        # Assert
        assert _TOOLGUIDE_URN in targets

    def test_drupal_security_performance_suggests_the_profile(self, graph: DRGGraph) -> None:
        # Act
        targets = {edge.target for edge in graph.edges_from(_SECURITY_URN, Relation.SUGGESTS)}
        # Assert
        assert _PROFILE_URN in targets
