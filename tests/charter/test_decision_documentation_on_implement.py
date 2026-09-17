"""Tests for the FR-004 decision-documentation-on-implement gate (mission
governance-at-the-gate WP03).

Requirements: FR-004, US3, SC-004 (``research-outputs/governance-at-the-gate/spec.md``).

Covers:
- ``test_required_decision_documentation_directive_scoped_on_implement_fails``:
  SC-004 -- a seeded ``required`` decision-documentation directive delivered
  to ``implement`` fails the gate, naming the directive.
- ``test_required_non_decision_documentation_directive_is_not_flagged``: the
  class discrimination -- a `required` directive whose title does NOT carry
  "decision documentation" (DIRECTIVE_001) is not flagged, proving this is
  not a blanket "no required directives on implement" rule.
- ``test_shipped_corpus_passes_the_gate``: SC-004 -- the real bundled
  doctrine pack, post FR-005 (WP03 T2/T4), passes -- proving the gate is
  non-vacuous against genuine delivery (not merely a synthetic fixture),
  including the transitive-``requires``-chain leak WP03's own brownfield
  investigation found and closed (see
  ``tests/charter/test_directive_003_implement_to_review.py`` for the CLI
  -level combined assertion this gate backs at the structural level).
- ``test_fail_closed_on_scan_error``: a forced scan error lands in
  ``verification_errors``, folded into ``coherent=False``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import charter.activation._drg_helpers as drg_helpers
from charter.activation import consistency_check
from charter.activation.consistency_check import (
    run_consistency_check,
    scan_decision_documentation_scoped_on_implement,
)
from charter.drg import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.activation.invocation_context import ProjectContext

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Real built-in doctrine identifiers (packs/built-in/directives/*.yaml):
#   directive:DIRECTIVE_003 -- required, title "Decision Documentation
#     Requirement" (the decision-documentation class instance).
#   directive:DIRECTIVE_001 -- required, title "Architectural Integrity
#     Standard" (required, but NOT decision-documentation-titled).
# ---------------------------------------------------------------------------
_STEM_003 = "003-decision-documentation-requirement"
_STEM_001 = "001-architectural-integrity-standard"

_URN_003 = "directive:DIRECTIVE_003"
_URN_001 = "directive:DIRECTIVE_001"
_IMPLEMENT_URN = "action:software-dev/implement"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path, content: str) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")


def _ctx_with_config(tmp_path: Path, config_yaml: str) -> ProjectContext:
    """Build a fully-populated ProjectContext (real built-in pack) with *config_yaml*.

    Mirrors ``tests/charter/test_enforcement_lattice.py``'s helper of the
    same name -- ``mission_type_activations`` is a hard construction
    precondition for ``PackContext.from_config``, unrelated to this
    contract, so it is prepended ahead of every call site's own config.
    """
    _write_config(tmp_path, "mission_type_activations:\n  - software-dev\n" + config_yaml)
    return ProjectContext.from_repo(tmp_path)


def _make_graph(nodes: list[DRGNode], edges: list[DRGEdge]) -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="TEST",
        generated_by="test",
        nodes=nodes,
        edges=edges,
    )


# ---------------------------------------------------------------------------
# SC-004: seeded violation, naming the directive
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_required_decision_documentation_directive_scoped_on_implement_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A required decision-documentation directive delivered to implement fails.

    Uses the REAL, independently-loadable DIRECTIVE_003 (required, title
    "Decision Documentation Requirement") wired with a synthetic ``scope``
    edge -- no custom Directive fixture needed, and the enforcement/title
    come from the genuine on-disk YAML, not a mock.
    """
    graph = _make_graph(
        nodes=[
            DRGNode(urn=_IMPLEMENT_URN, kind=NodeKind.ACTION),
            DRGNode(urn=_URN_003, kind=NodeKind.DIRECTIVE),
        ],
        edges=[
            DRGEdge(source=_IMPLEMENT_URN, target=_URN_003, relation=Relation.SCOPE),
        ],
    )
    monkeypatch.setattr(drg_helpers, "load_validated_graph", lambda repo_root: graph)

    ctx = _ctx_with_config(
        tmp_path,
        f"activated_directives:\n  - {_STEM_003}\n",
    )

    violations = scan_decision_documentation_scoped_on_implement(ctx)

    assert len(violations) == 1
    assert _URN_003 in violations[0]
    assert "Decision Documentation Requirement" in violations[0]


# ---------------------------------------------------------------------------
# Class discrimination: required but not decision-documentation is not flagged
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_required_non_decision_documentation_directive_is_not_flagged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A `required` directive whose title is NOT decision-documentation passes.

    Proves the gate is class-scoped (decision-documentation directives
    only), not a blanket "no required directive on implement" rule --
    DIRECTIVE_001 (required, "Architectural Integrity Standard") is
    legitimately delivered to implement and must not be flagged.
    """
    graph = _make_graph(
        nodes=[
            DRGNode(urn=_IMPLEMENT_URN, kind=NodeKind.ACTION),
            DRGNode(urn=_URN_001, kind=NodeKind.DIRECTIVE),
        ],
        edges=[
            DRGEdge(source=_IMPLEMENT_URN, target=_URN_001, relation=Relation.SCOPE),
        ],
    )
    monkeypatch.setattr(drg_helpers, "load_validated_graph", lambda repo_root: graph)

    ctx = _ctx_with_config(
        tmp_path,
        f"activated_directives:\n  - {_STEM_001}\n",
    )

    violations = scan_decision_documentation_scoped_on_implement(ctx)

    assert violations == []


# ---------------------------------------------------------------------------
# SC-004: shipped corpus (real, not synthetic)
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_shipped_corpus_passes_the_gate(tmp_path: Path) -> None:
    """The real bundled doctrine pack, post FR-005, passes the gate.

    This is the mission's headline SC-004 acceptance criterion for FR-004,
    exercised against the REAL bundled doctrine pack -- never a synthetic
    fixture. It is also the structural-level twin of
    ``test_directive_003_implement_to_review.py``'s CLI-level combined
    assertion: both must hold post WP03 (FR-005's index.yaml edit alone
    was NOT sufficient -- see that module's docstring and this mission's
    brownfield note on the transitive procedure ``requires`` chain WP03
    closed in ``packs/built-in/procedures/legacy-codebase-triage.procedure.yaml``
    and ``.../situational-assessment.procedure.yaml``).
    """
    ctx = _ctx_with_config(tmp_path, "")

    violations = scan_decision_documentation_scoped_on_implement(ctx)

    assert violations == []

    report = run_consistency_check(ctx)
    assert report.decision_documentation_on_implement_violations == []
    assert report.coherent is True


# ---------------------------------------------------------------------------
# DRG<->doctrine-repository disagreement
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_directive_unresolvable_in_directive_repository_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A DRG/doctrine-repository disagreement raises, not a silent skip.

    ``implement``'s resolved bundle already gated membership via the DRG
    (the directive URN here is a real ``scope`` edge target resolvable by
    the graph), so a miss in the directive repository is a genuine "could
    not verify" condition -- the two subsystems disagree on what exists --
    never a legitimate "nothing to check" skip. Forces that disagreement
    directly by stubbing ``_resolve_directives`` to an empty repository,
    independent of DRG resolution.
    """
    graph = _make_graph(
        nodes=[
            DRGNode(urn=_IMPLEMENT_URN, kind=NodeKind.ACTION),
            DRGNode(urn=_URN_003, kind=NodeKind.DIRECTIVE),
        ],
        edges=[
            DRGEdge(source=_IMPLEMENT_URN, target=_URN_003, relation=Relation.SCOPE),
        ],
    )
    monkeypatch.setattr(drg_helpers, "load_validated_graph", lambda repo_root: graph)
    monkeypatch.setattr(consistency_check, "_resolve_directives", lambda repo_root, pack_context: {})

    ctx = _ctx_with_config(
        tmp_path,
        f"activated_directives:\n  - {_STEM_003}\n",
    )

    with pytest.raises(RuntimeError, match="cannot resolve"):
        scan_decision_documentation_scoped_on_implement(ctx)


# ---------------------------------------------------------------------------
# Fail-closed
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_fail_closed_on_scan_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A forced scan error lands in verification_errors, folded into coherent=False."""

    def _boom(ctx: ProjectContext) -> list[str]:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        consistency_check,
        "scan_decision_documentation_scoped_on_implement",
        _boom,
    )

    ctx = _ctx_with_config(tmp_path, "")

    report = run_consistency_check(ctx)

    assert report.decision_documentation_on_implement_violations == []
    assert any("decision-documentation-on-implement" in e for e in report.verification_errors)
    assert report.coherent is False


def test_to_json_includes_decision_documentation_on_implement_violations_key() -> None:
    """``ConsistencyReport.to_json()`` renders the new field (additive-safe)."""
    from charter.activation.consistency_check import ConsistencyReport

    report = ConsistencyReport(
        coherent=False,
        decision_documentation_on_implement_violations=[
            f"{_IMPLEMENT_URN} delivers {_URN_003} ('Decision Documentation "
            f"Requirement'), a required decision-documentation directive; "
            f"decision documentation must not be delivered to implement."
        ],
    )

    payload = report.to_json()

    assert '"decision_documentation_on_implement_violations"' in payload
    assert _URN_003 in payload
