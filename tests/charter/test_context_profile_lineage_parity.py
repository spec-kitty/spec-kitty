"""Dispatch-capsule ↔ ``profiles show`` ``specializes_from`` parity (#4917).

The dispatch capsule / governance-context funnel
(``charter.activation.profile_resolution._resolve_agent_profile_record`` →
``_load_agent_profile``) must render the same profile-cited directive/tactic
sections that ``profiles show`` and the runtime bridge do. Those surfaces read
the ungated ``AgentProfileRepository.resolve_profile``, which unions a profile's
``directive-references`` / ``tactic-references`` up its ``specializes_from``
ancestor chain. The capsule funnel previously returned the raw, un-composed
record via ``AgentProfileRepository.get``, so a leaf profile that
``specializes_from`` a base citing directives/tactics only on the base dropped
those sections from the capsule while ``profiles show`` kept them.

These tests pin the parity on both funnel paths — the built-in fast path
(``repo_root is None`` / no org packs) and the activation-aware org path — and
assert the design decision that lineage composition is *below the activation
grain*: a de-activated ancestor still contributes its cited sections to an
activated leaf, while a de-activated leaf is still omitted entirely.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.fast]


def _lineage_drg(*pairs: tuple[str, str]) -> DRGGraph:
    """Build a DRG with ``specializes_from`` edges for ``(child, parent)`` pairs."""
    ids = {pid for pair in pairs for pid in pair}
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-06-02T00:00:00Z",
        generated_by="test_context_profile_lineage_parity",
        nodes=[DRGNode(urn=f"agent_profile:{pid}", kind=NodeKind.AGENT_PROFILE) for pid in sorted(ids)],
        edges=[
            DRGEdge(
                source=f"agent_profile:{child}",
                target=f"agent_profile:{parent}",
                relation=Relation.SPECIALIZES_FROM,
            )
            for child, parent in pairs
        ],
    )


@pytest.fixture
def lineage_repo(tmp_path: Path) -> AgentProfileRepository:
    """A base that cites a directive + tactic, and a child that cites neither."""
    shipped = tmp_path / "built-in"
    shipped.mkdir()

    (shipped / "base-analyst.agent.yaml").write_text(
        """profile-id: base-analyst
name: Base Analyst
roles:
  - analyst
purpose: Abstract base
specialization:
  primary-focus: analysis
directive-references:
  - code: DIRECTIVE_024
    name: Locality of Change
    rationale: keep edits local
tactic-references:
  - id: change-apply-smallest-viable-diff
    rationale: minimize the diff
initialization-declaration: hello
""",
        encoding="utf-8",
    )
    (shipped / "project-annie.agent.yaml").write_text(
        """profile-id: project-annie
name: Project Annie
roles:
  - analyst
purpose: Concrete specialist citing nothing of its own
specialization:
  primary-focus: project analysis
""",
        encoding="utf-8",
    )

    drg = _lineage_drg(("project-annie", "base-analyst"))
    return AgentProfileRepository(built_in_dir=shipped, project_dir=None, drg=drg)


def test_builtin_path_capsule_composes_lineage_like_resolve_profile(lineage_repo: AgentProfileRepository, monkeypatch: pytest.MonkeyPatch) -> None:
    """The built-in fast path funnel matches ``resolve_profile`` composition (#4917)."""
    from charter.activation import context as ctx_mod
    from charter.activation import profile_resolution as pr

    # profiles show / runtime bridge accessor (ungated, composed):
    composed = lineage_repo.resolve_profile("project-annie")
    assert {r.code for r in composed.directive_references} == {"DIRECTIVE_024"}
    assert {r.id for r in composed.tactic_references} == {"change-apply-smallest-viable-diff"}

    # Dispatch-capsule funnel, built-in fast path (repo_root is None):
    monkeypatch.setattr(ctx_mod, "_default_agent_profile_repository", lambda: lineage_repo)
    pr._reset_agent_profile_cache()

    capsule = pr._resolve_agent_profile_record("project-annie", repo_root=None)
    assert capsule is not None
    assert {r.code for r in capsule.directive_references} == {r.code for r in composed.directive_references}
    assert {r.id for r in capsule.tactic_references} == {r.id for r in composed.tactic_references}


def test_activation_aware_map_composes_lineage_and_gates_only_the_leaf(lineage_repo: AgentProfileRepository, monkeypatch: pytest.MonkeyPatch) -> None:
    """Org path: gate the leaf id, but compose lineage across a de-activated ancestor (#4917)."""
    from charter.activation import context as ctx_mod
    from charter.activation import profile_resolution as pr

    class _FakeService:
        """Mimics the activation wrapper: a gated leaf dict + the raw repository."""

        def __init__(self, repo: AgentProfileRepository, activated: set[str]) -> None:
            self._repo = repo
            self._activated = activated

        @property
        def agent_profiles(self) -> dict[str, object]:
            # Only the leaf is activated; the base ancestor is gated out.
            return {pid: self._repo.get(pid) for pid in self._activated}

        @property
        def agent_profile_repository(self) -> AgentProfileRepository:
            return self._repo

    monkeypatch.setattr(
        ctx_mod,
        "_build_activation_aware_doctrine_service",
        lambda repo_root, org_roots: _FakeService(lineage_repo, {"project-annie"}),
    )
    pr._reset_agent_profile_cache()

    mapped = pr._activation_aware_profile_map(Path("/repo"), [Path("/repo/.org")])

    # Leaf-only activation gate: the de-activated base is not itself a map entry.
    assert set(mapped) == {"project-annie"}
    annie = mapped["project-annie"]
    # Below-the-activation-grain lineage: the de-activated base still contributes
    # its cited directive/tactic sections to the activated leaf.
    assert {r.code for r in annie.directive_references} == {"DIRECTIVE_024"}
    assert {r.id for r in annie.tactic_references} == {"change-apply-smallest-viable-diff"}
