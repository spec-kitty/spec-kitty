"""Tests for the FR-002 enforcement-lattice gate (mission governance-at-the-gate WP01).

Requirements: FR-001, FR-002, FR-003, US3, SC-004, SC-005, SC-009
(``research-outputs/governance-at-the-gate/spec.md``).

Covers:
- ``test_advisory_reconciler_over_required_operand_fails_naming_the_edge``:
  SC-004 -- a seeded ``advisory`` reconciler over a ``required`` directive
  operand fails the gate, naming the offending edge.
- ``test_tactic_target_edge_is_skipped``: the documented skip rule -- a
  ``reconciles_tension`` edge whose target is a tactic (no ``enforcement``
  field) is never evaluated.
- ``test_reconciler_promoted_to_required_is_always_a_violation``: the FR-003
  bound -- a reconciler is never ``required``, even when the rank comparison
  alone would pass.
- ``test_inactive_reconciler_edge_is_not_evaluated``: only ACTIVE
  ``reconciles_tension`` edges are in scope (mirrors the tension scan's own
  activation gate, reused not reimplemented).
- ``test_shipped_corpus_passes_the_lattice_gate``: SC-004/SC-005 -- the real
  bundled doctrine pack, with the built-in reconciler active, passes the
  gate (proves FR-003's promotion, not merely a synthetic fixture).
- ``test_fail_closed_on_scan_error``: a forced scan error lands in
  ``verification_errors``, folded into ``coherent=False``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import charter.activation._drg_helpers as drg_helpers
from charter.activation import consistency_check
from charter.activation.consistency_check import (
    ConsistencyReport,
    run_consistency_check,
    scan_enforcement_lattice_violations,
)
from charter.drg import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.activation.invocation_context import ProjectContext

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Real built-in doctrine identifiers (packs/built-in/directives/*.yaml):
#   directive:DIRECTIVE_047, directive:DIRECTIVE_049 -- advisory
#   directive:DIRECTIVE_001                          -- required
#   directive:DIRECTIVE_024, directive:DIRECTIVE_025  -- lenient-adherence
#   directive:RECONCILE_CHANGE_SCOPE_TENSIONS         -- lenient-adherence
#     (post-WP01 T3 promotion; advisory before)
#   tactic:change-apply-smallest-viable-diff          -- no enforcement field
# ---------------------------------------------------------------------------
_STEM_ADVISORY = "047-audience-oriented-writing"
_STEM_REQUIRED = "001-architectural-integrity-standard"
_STEM_024 = "024-locality-of-change"
_STEM_025 = "025-boy-scout-rule"
_STEM_TACTIC = "change-apply-smallest-viable-diff"
_STEM_RECONCILER = "reconcile-change-scope-tensions"

_URN_ADVISORY = "directive:DIRECTIVE_047"
_URN_REQUIRED = "directive:DIRECTIVE_001"
_URN_024 = "directive:DIRECTIVE_024"
_URN_025 = "directive:DIRECTIVE_025"
_URN_TACTIC = "tactic:change-apply-smallest-viable-diff"
_URN_RECONCILER = "directive:RECONCILE_CHANGE_SCOPE_TENSIONS"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path, content: str) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")


def _ctx_with_config(tmp_path: Path, config_yaml: str) -> ProjectContext:
    """Build a fully-populated ProjectContext (real built-in pack) with *config_yaml*.

    Mirrors ``tests/charter/test_tension_unreconciled.py``'s helper of the
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
# SC-004: seeded rank violation, naming the edge
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_advisory_reconciler_over_required_operand_fails_naming_the_edge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An advisory reconciler over a required operand fails, naming the edge.

    Uses two REAL, independently-loadable directives (DIRECTIVE_047,
    advisory; DIRECTIVE_001, required) wired together with a synthetic
    ``reconciles_tension`` edge -- no custom Directive fixture needed, and
    the enforcement values come from the genuine on-disk YAML, not a mock.
    """
    graph = _make_graph(
        nodes=[
            DRGNode(urn=_URN_ADVISORY, kind=NodeKind.DIRECTIVE),
            DRGNode(urn=_URN_REQUIRED, kind=NodeKind.DIRECTIVE),
        ],
        edges=[
            DRGEdge(
                source=_URN_ADVISORY,
                target=_URN_REQUIRED,
                relation=Relation.RECONCILES_TENSION,
            ),
        ],
    )
    monkeypatch.setattr(drg_helpers, "load_validated_graph", lambda repo_root: graph)

    ctx = _ctx_with_config(
        tmp_path,
        f"activated_directives:\n  - {_STEM_ADVISORY}\n  - {_STEM_REQUIRED}\nactivated_tactics: []\n",
    )

    violations = scan_enforcement_lattice_violations(ctx)

    assert len(violations) == 1
    assert _URN_ADVISORY in violations[0]
    assert _URN_REQUIRED in violations[0]
    assert "advisory" in violations[0]
    assert "required" in violations[0]


# ---------------------------------------------------------------------------
# Documented skip rule: tactic target
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_tactic_target_edge_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A reconciles_tension edge targeting a tactic is skipped, never evaluated.

    The reconciler here is advisory (DIRECTIVE_047) -- if the tactic target
    were wrongly treated as an operand with some default rank, this would
    risk flagging a violation. The gate must instead skip it outright: a
    tactic carries no ``enforcement`` field to rank against.
    """
    graph = _make_graph(
        nodes=[
            DRGNode(urn=_URN_ADVISORY, kind=NodeKind.DIRECTIVE),
            DRGNode(urn=_URN_TACTIC, kind=NodeKind.TACTIC),
        ],
        edges=[
            DRGEdge(
                source=_URN_ADVISORY,
                target=_URN_TACTIC,
                relation=Relation.RECONCILES_TENSION,
            ),
        ],
    )
    monkeypatch.setattr(drg_helpers, "load_validated_graph", lambda repo_root: graph)

    ctx = _ctx_with_config(
        tmp_path,
        f"activated_directives:\n  - {_STEM_ADVISORY}\nactivated_tactics:\n  - {_STEM_TACTIC}\n",
    )

    violations = scan_enforcement_lattice_violations(ctx)

    assert violations == []


# ---------------------------------------------------------------------------
# FR-003 bound: reconciler never `required`
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_reconciler_promoted_to_required_is_always_a_violation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A `required` reconciler is a violation even though rank(R) >= rank(X) holds.

    Uses two real `required` directives (DIRECTIVE_001 as reconciler,
    DIRECTIVE_003 as operand) so the plain rank comparison alone would
    PASS (required >= required) -- proving the "never required" bound is a
    genuinely separate assertion, not derivable from the rank check.
    """
    urn_operand = "directive:DIRECTIVE_003"
    graph = _make_graph(
        nodes=[
            DRGNode(urn=_URN_REQUIRED, kind=NodeKind.DIRECTIVE),
            DRGNode(urn=urn_operand, kind=NodeKind.DIRECTIVE),
        ],
        edges=[
            DRGEdge(
                source=_URN_REQUIRED,
                target=urn_operand,
                relation=Relation.RECONCILES_TENSION,
            ),
        ],
    )
    monkeypatch.setattr(drg_helpers, "load_validated_graph", lambda repo_root: graph)

    ctx = _ctx_with_config(
        tmp_path,
        f"activated_directives:\n  - {_STEM_REQUIRED}\n  - 003-decision-documentation-requirement\nactivated_tactics: []\n",
    )

    violations = scan_enforcement_lattice_violations(ctx)

    assert len(violations) == 1
    assert _URN_REQUIRED in violations[0]
    assert "required" in violations[0].lower()


# ---------------------------------------------------------------------------
# Activation gate: only active edges are evaluated
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_inactive_reconciler_edge_is_not_evaluated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A reconciles_tension edge whose source is NOT active is out of scope.

    Same violating pair as the first test (advisory over required), but the
    reconciler stem is left out of ``activated_directives`` -- the edge
    never becomes an active ``reconciles_tension`` edge, so the gate must
    not flag it (mirrors the tension scan's own activation semantics).
    """
    graph = _make_graph(
        nodes=[
            DRGNode(urn=_URN_ADVISORY, kind=NodeKind.DIRECTIVE),
            DRGNode(urn=_URN_REQUIRED, kind=NodeKind.DIRECTIVE),
        ],
        edges=[
            DRGEdge(
                source=_URN_ADVISORY,
                target=_URN_REQUIRED,
                relation=Relation.RECONCILES_TENSION,
            ),
        ],
    )
    monkeypatch.setattr(drg_helpers, "load_validated_graph", lambda repo_root: graph)

    ctx = _ctx_with_config(
        tmp_path,
        f"activated_directives:\n  - {_STEM_REQUIRED}\nactivated_tactics: []\n",
    )

    violations = scan_enforcement_lattice_violations(ctx)

    assert violations == []


# ---------------------------------------------------------------------------
# SC-004/SC-005: shipped corpus (real, not synthetic)
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_shipped_corpus_passes_the_lattice_gate(tmp_path: Path) -> None:
    """The real bundled doctrine pack, reconciler active, passes the gate.

    This is the mission's headline SC-004/SC-005 acceptance criterion,
    exercised against the REAL bundled doctrine pack (024, 025,
    change-apply-smallest-viable-diff, reconcile-change-scope-tensions) --
    never a synthetic fixture. Before FR-003's promotion (reconciler
    ``advisory``, both operands ``lenient-adherence``) this legitimately
    fails: ``rank(advisory) < rank(lenient-adherence)``.
    """
    ctx = _ctx_with_config(
        tmp_path,
        f"activated_directives:\n  - {_STEM_024}\n  - {_STEM_025}\n  - {_STEM_RECONCILER}\nactivated_tactics:\n  - {_STEM_TACTIC}\n",
    )

    violations = scan_enforcement_lattice_violations(ctx)

    assert violations == []

    report = run_consistency_check(ctx)
    assert report.enforcement_lattice_violations == []
    assert report.coherent is True


# ---------------------------------------------------------------------------
# DRG<->doctrine-repository disagreement
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_reconciler_or_operand_unresolvable_in_directive_repository_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A DRG/doctrine-repository disagreement raises, not a silent skip.

    ``active_urns`` already gates edge membership via the DRG (both
    endpoints here are DRG nodes marked active), so a miss in the directive
    repository is a genuine "could not verify" condition -- the two
    subsystems disagree on what exists -- never a legitimate "nothing to
    rank" skip. Forces that disagreement directly by stubbing
    ``_resolve_directives`` to an empty repository, independent of DRG
    activation resolution.
    """
    graph = _make_graph(
        nodes=[
            DRGNode(urn=_URN_ADVISORY, kind=NodeKind.DIRECTIVE),
            DRGNode(urn=_URN_REQUIRED, kind=NodeKind.DIRECTIVE),
        ],
        edges=[
            DRGEdge(
                source=_URN_ADVISORY,
                target=_URN_REQUIRED,
                relation=Relation.RECONCILES_TENSION,
            ),
        ],
    )
    monkeypatch.setattr(drg_helpers, "load_validated_graph", lambda repo_root: graph)
    monkeypatch.setattr(consistency_check, "_resolve_directives", lambda repo_root, pack_context: {})

    ctx = _ctx_with_config(
        tmp_path,
        f"activated_directives:\n  - {_STEM_ADVISORY}\n  - {_STEM_REQUIRED}\nactivated_tactics: []\n",
    )

    with pytest.raises(RuntimeError, match="cannot resolve"):
        scan_enforcement_lattice_violations(ctx)


# ---------------------------------------------------------------------------
# Fail-closed
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_fail_closed_on_scan_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A forced scan error lands in verification_errors, folded into coherent=False."""
    ctx = _ctx_with_config(
        tmp_path,
        f"activated_directives:\n  - {_STEM_024}\n  - {_STEM_025}\nactivated_tactics: []\n",
    )

    def _boom(_ctx: ProjectContext) -> list[str]:
        raise RuntimeError("simulated lattice-scan failure")

    monkeypatch.setattr(consistency_check, "scan_enforcement_lattice_violations", _boom)

    report = run_consistency_check(ctx)

    assert report.enforcement_lattice_violations == []
    assert any("enforcement lattice" in err for err in report.verification_errors), (
        f"Expected a lattice-scan failure in verification_errors, got: {report.verification_errors}"
    )
    assert report.coherent is False


def test_to_json_includes_enforcement_lattice_violations_key() -> None:
    """``ConsistencyReport.to_json()`` renders the new field (additive-safe)."""
    report = ConsistencyReport(
        coherent=False,
        enforcement_lattice_violations=["reconciles_tension X -> Y: ..."],
    )

    payload = report.to_json()

    assert '"enforcement_lattice_violations"' in payload
    assert "reconciles_tension X -> Y" in payload
