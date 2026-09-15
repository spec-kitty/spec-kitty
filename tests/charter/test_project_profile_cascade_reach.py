"""T001 (ATDD/C-004): a hand-authored project-tier agent_profile is cascade-reachable.

The defect (M6 / #3038): authoring
``.kittify/doctrine/agent_profiles/<name>.agent.yaml`` loads and validates as a
profile today, but never becomes an ``agent_profile:<id>`` DRG node in the
project overlay ``graph.yaml`` the charter cascade reads. This test drives the
project-overlay emission path end-to-end and asserts the node lands in
``.kittify/doctrine/graph.yaml`` and is reachable via
``load_validated_graph(project_root)``.

RED on the pre-fix tree: ``emit_project_layer`` neither accepts ``project_root``
nor walks the authored profiles, so the node is absent (0). GREEN after the fix:
the node is present (1) — the measured 0->1 of SC-001.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation._drg_helpers import load_validated_graph
from charter.activation.synthesizer.path_guard import PathGuard
from charter.activation.synthesizer.project_drg import emit_project_layer, persist
from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.models import NodeKind

pytestmark = [pytest.mark.unit]

_PROFILE_URN = "agent_profile:reviewer-rhonda"


def _author_project_profile(root: Path) -> None:
    profiles_dir = root / ".kittify" / "doctrine" / "agent_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / "reviewer-rhonda.agent.yaml").write_text(
        "profile-id: reviewer-rhonda\nname: Reviewer Rhonda\n",
        encoding="utf-8",
    )


def test_hand_authored_project_profile_is_cascade_reachable(tmp_path: Path) -> None:
    """SC-001: the authored profile yields exactly one cascade-reachable node."""
    _author_project_profile(tmp_path)
    built_in = load_built_in_graph()

    # Drive the emission path (no synthesis interview answer): the walk half is
    # engaged solely by ``project_root``.
    overlay = emit_project_layer(
        [],
        "0.0.0-test",
        built_in,
        project_root=tmp_path,
    )
    profile_nodes = [n for n in overlay.nodes if n.urn == _PROFILE_URN]
    assert len(profile_nodes) == 1, "expected exactly one project agent_profile node"
    assert profile_nodes[0].kind is NodeKind.AGENT_PROFILE

    # Persist into the live project doctrine tree so cascade can read it. The
    # persist writes ``<staging>/doctrine/graph.yaml``; anchoring staging at
    # ``<root>/.kittify`` lands it at ``<root>/.kittify/doctrine/graph.yaml``.
    guard = PathGuard(repo_root=tmp_path)
    persist(overlay, tmp_path / ".kittify", guard)
    graph_path = tmp_path / ".kittify" / "doctrine" / "graph.yaml"
    assert graph_path.exists()
    assert _PROFILE_URN in graph_path.read_text(encoding="utf-8")

    # Cascade reads through ``load_validated_graph``.
    merged = load_validated_graph(tmp_path)
    node = merged.get_node(_PROFILE_URN)
    assert node is not None
    assert node.kind is NodeKind.AGENT_PROFILE
