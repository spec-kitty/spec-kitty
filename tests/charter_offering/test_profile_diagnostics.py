"""WP05 — agent-profile load diagnostics + DRG-backed lineage.

Covers FR-002 (lineage via DRG), FR-005/006/007 (structured skip diagnostics),
NFR-002 (deterministic ordering), NFR-005 (zero diagnostics for valid built-ins),
and C-009 (the retired ``specializes-from`` field is no longer consulted).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.agent_profiles import SkippedProfile
from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]


# ── helpers ────────────────────────────────────────────────────────────────


def _profile_yaml(profile_id: str, *, primary_focus: str = "work", extra: str = "") -> str:
    """Return a minimal valid agent-profile YAML body (no retired fields)."""
    return (
        f"profile-id: {profile_id}\n"
        f"name: {profile_id.title()}\n"
        "roles:\n"
        "  - implementer\n"
        f"purpose: {profile_id} purpose\n"
        "specialization:\n"
        f"  primary-focus: {primary_focus}\n"
        f"{extra}"
    )


def _lineage_drg(*pairs: tuple[str, str]) -> DRGGraph:
    """Build a DRG carrying ``specializes_from`` lineage edges.

    Each ``(child, parent)`` pair becomes an
    ``agent_profile:<child> --specializes_from--> agent_profile:<parent>`` edge.
    Nodes are synthesized for every referenced profile id.
    """
    ids = {pid for pair in pairs for pid in pair}
    nodes = [
        DRGNode(urn=f"agent_profile:{pid}", kind=NodeKind.AGENT_PROFILE) for pid in sorted(ids)
    ]
    edges = [
        DRGEdge(
            source=f"agent_profile:{child}",
            target=f"agent_profile:{parent}",
            relation=Relation.SPECIALIZES_FROM,
        )
        for child, parent in pairs
    ]
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-06-02T00:00:00Z",
        generated_by="test_profile_diagnostics",
        nodes=nodes,
        edges=edges,
    )


def _empty_drg() -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-06-02T00:00:00Z",
        generated_by="test_profile_diagnostics",
        nodes=[],
        edges=[],
    )


# ── FR-005/006/007: structured diagnostics ──────────────────────────────────


class TestSkippedDiagnostics:
    def test_invalid_profile_recorded_with_all_fields(self, tmp_path: Path) -> None:
        """An unparseable profile is retained as a SkippedProfile with all fields."""
        built_in = tmp_path / "built-in"
        built_in.mkdir()
        bad = built_in / "broken.agent.yaml"
        bad.write_text("this: is: not: valid: yaml: {", encoding="utf-8")

        repo = AgentProfileRepository(built_in_dir=built_in, project_dir=None, drg=_empty_drg())

        skipped = repo.skipped_profiles()
        assert {(s.layer, s.path) for s in skipped} == {("builtin", str(bad))}
        record = skipped[0]
        assert isinstance(record, SkippedProfile)
        assert record.layer == "builtin"
        assert record.path == str(bad)
        assert record.error_summary  # non-empty
        # path/profile_id/error_summary all populated (profile_id may be None here)

    def test_missing_profile_id_recorded(self, tmp_path: Path) -> None:
        """A profile lacking profile-id is recorded, not silently dropped."""
        built_in = tmp_path / "built-in"
        built_in.mkdir()
        (built_in / "noid.agent.yaml").write_text(
            "name: No Id\nroles: [implementer]\npurpose: x\n", encoding="utf-8"
        )

        repo = AgentProfileRepository(built_in_dir=built_in, project_dir=None, drg=_empty_drg())

        skipped = repo.skipped_profiles()
        assert {s.profile_id for s in skipped} == {None}
        assert skipped[0].profile_id is None
        assert skipped[0].error_summary

    def test_skipped_profile_is_frozen(self) -> None:
        record = SkippedProfile(layer="org", path="/x.agent.yaml", profile_id="p", error_summary="e")
        with pytest.raises((AttributeError, TypeError)):
            record.layer = "project"  # type: ignore[misc]

    def test_list_all_is_valid_only(self, tmp_path: Path) -> None:
        """FR-006: list_all() returns only successfully loaded profiles."""
        built_in = tmp_path / "built-in"
        built_in.mkdir()
        (built_in / "good.agent.yaml").write_text(_profile_yaml("good"), encoding="utf-8")
        (built_in / "broken.agent.yaml").write_text("{{{ not yaml", encoding="utf-8")

        repo = AgentProfileRepository(built_in_dir=built_in, project_dir=None, drg=_empty_drg())

        ids = [p.profile_id for p in repo.list_all()]
        assert ids == ["good"]
        assert {s.layer for s in repo.skipped_profiles()} == {"builtin"}


# ── NFR-002: determinism ─────────────────────────────────────────────────────


class TestDeterminism:
    def test_records_sorted_and_stable_across_loads(self, tmp_path: Path) -> None:
        """Two loads of the same inputs produce identical sorted records (NFR-002)."""
        built_in = tmp_path / "built-in"
        built_in.mkdir()
        for name in ("zeta", "alpha", "mid"):
            (built_in / f"{name}.agent.yaml").write_text("{{{ broken", encoding="utf-8")

        repo1 = AgentProfileRepository(built_in_dir=built_in, project_dir=None, drg=_empty_drg())
        repo2 = AgentProfileRepository(built_in_dir=built_in, project_dir=None, drg=_empty_drg())

        first = repo1.skipped_profiles()
        second = repo2.skipped_profiles()

        # Identical ordering across independent loads.
        assert [s.path for s in first] == [s.path for s in second]
        # Sorted by path within the (single) layer.
        assert [s.path for s in first] == sorted(s.path for s in first)

    def test_layer_rank_orders_builtin_before_project(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        built_in.mkdir()
        project = tmp_path / "project"
        project.mkdir()
        (built_in / "zzz.agent.yaml").write_text("{{{ broken", encoding="utf-8")
        (project / "aaa.agent.yaml").write_text("{{{ broken", encoding="utf-8")

        repo = AgentProfileRepository(built_in_dir=built_in, project_dir=project, drg=_empty_drg())

        layers = [s.layer for s in repo.skipped_profiles()]
        # builtin record must precede project record regardless of path.
        assert layers == ["builtin", "project"]


# ── NFR-005: zero diagnostics for built-ins ──────────────────────────────────


def test_shipped_builtins_have_zero_diagnostics() -> None:
    """NFR-005: the real shipped built-in profiles load without any skips."""
    repo = AgentProfileRepository()
    assert repo.skipped_profiles() == []


# ── FR-007: diagnostics survive on CharterOfferingService ──────────────────────────


def test_service_preserves_diagnostics_without_rescan() -> None:
    """FR-007: accessing service.agent_profiles twice yields the same cached repo."""
    from charter.offering.service import CharterOfferingService

    service = CharterOfferingService()
    repo_a = service.agent_profiles
    repo_b = service.agent_profiles

    assert repo_a is repo_b  # cached: no re-scan
    assert repo_a.skipped_profiles() == repo_b.skipped_profiles()


# ── FR-002 / C-009: lineage via DRG ──────────────────────────────────────────


class TestLineageViaDRG:
    @pytest.fixture
    def repo(self, tmp_path: Path) -> AgentProfileRepository:
        built_in = tmp_path / "built-in"
        built_in.mkdir()
        for name in ("base", "child", "grandchild", "sibling"):
            (built_in / f"{name}.agent.yaml").write_text(
                _profile_yaml(name, primary_focus=f"{name} focus"), encoding="utf-8"
            )
        drg = _lineage_drg(("child", "base"), ("grandchild", "child"), ("sibling", "base"))
        return AgentProfileRepository(built_in_dir=built_in, project_dir=None, drg=drg)

    def test_parent_chain(self, repo: AgentProfileRepository) -> None:
        assert repo.get_ancestors("child") == ["base"]
        assert repo.get_ancestors("grandchild") == ["child", "base"]
        assert repo.get_ancestors("base") == []

    def test_children_via_drg(self, repo: AgentProfileRepository) -> None:
        kids = sorted(p.profile_id for p in repo.get_children("base"))
        assert kids == ["child", "sibling"]
        assert repo.get_children("grandchild") == []

    def test_hierarchy_tree_roots(self, repo: AgentProfileRepository) -> None:
        tree = repo.get_hierarchy_tree()
        assert "base" in tree
        assert "child" in tree["base"]["children"]
        assert "grandchild" in tree["base"]["children"]["child"]["children"]

    def test_resolve_profile_inherits_via_drg(self, repo: AgentProfileRepository) -> None:
        # grandchild overrides its own focus, but the chain resolves cleanly.
        resolved = repo.resolve_profile("grandchild")
        assert resolved.specialization.primary_focus == "grandchild focus"

    def test_retired_field_is_not_consulted(self, tmp_path: Path) -> None:
        """C-009: with no DRG edges, there is no lineage even for sibling ids."""
        built_in = tmp_path / "built-in"
        built_in.mkdir()
        (built_in / "base.agent.yaml").write_text(_profile_yaml("base"), encoding="utf-8")
        (built_in / "child.agent.yaml").write_text(_profile_yaml("child"), encoding="utf-8")

        repo = AgentProfileRepository(built_in_dir=built_in, project_dir=None, drg=_empty_drg())

        assert repo.get_ancestors("child") == []
        assert repo.get_children("base") == []

    def test_cycle_detected_in_resolve(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        built_in.mkdir()
        (built_in / "a.agent.yaml").write_text(_profile_yaml("a"), encoding="utf-8")
        (built_in / "b.agent.yaml").write_text(_profile_yaml("b"), encoding="utf-8")
        drg = _lineage_drg(("a", "b"), ("b", "a"))

        repo = AgentProfileRepository(built_in_dir=built_in, project_dir=None, drg=drg)

        with pytest.raises(ValueError, match="Cycle detected"):
            repo.resolve_profile("a")

    def test_cycle_detected_in_validate_hierarchy(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        built_in.mkdir()
        (built_in / "a.agent.yaml").write_text(_profile_yaml("a"), encoding="utf-8")
        (built_in / "b.agent.yaml").write_text(_profile_yaml("b"), encoding="utf-8")
        drg = _lineage_drg(("a", "b"), ("b", "a"))

        repo = AgentProfileRepository(built_in_dir=built_in, project_dir=None, drg=drg)

        errors = repo.validate_hierarchy()
        assert any("cycle" in e.lower() for e in errors)

    def test_orphaned_reference_detected(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        built_in.mkdir()
        (built_in / "child.agent.yaml").write_text(_profile_yaml("child"), encoding="utf-8")
        # Parent edge points at a profile that is not loaded.
        drg = _lineage_drg(("child", "ghost-parent"))

        repo = AgentProfileRepository(built_in_dir=built_in, project_dir=None, drg=drg)

        errors = repo.validate_hierarchy()
        assert any("ghost-parent" in e for e in errors)

    def test_missing_parent_resolve_raises_key_error(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        built_in.mkdir()
        (built_in / "child.agent.yaml").write_text(_profile_yaml("child"), encoding="utf-8")
        drg = _lineage_drg(("child", "ghost-parent"))

        repo = AgentProfileRepository(built_in_dir=built_in, project_dir=None, drg=drg)

        with pytest.raises(KeyError, match="ghost-parent"):
            repo.resolve_profile("child")


def test_shipped_python_pedro_lineage_via_drg() -> None:
    """Integration: the real shipped graph resolves python-pedro -> implementer-ivan."""
    repo = AgentProfileRepository()
    assert repo.get_ancestors("python-pedro") == ["implementer-ivan"]
    children = sorted(p.profile_id for p in repo.get_children("implementer-ivan"))
    assert "python-pedro" in children
    assert repo.validate_hierarchy() == []
