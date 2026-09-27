"""Behavioural contract for WP06 — post-consolidation verification seam.

Pins contract ``negative-invariant-provenance.md`` C6/C7, spec FR-004/FR-005, and
the data-model Result state machine's ``deferred_to_consolidation ->
confirmed_absent | still_present`` transition (``verified_surface_kind =
CONSOLIDATED``).

These are filesystem/``grep`` tests: a consolidated mission tree is materialised in
a temp dir, the acceptance matrix is written alongside it, and the deferred
invariant is re-judged against that tree. No git is shelled — the consolidation
commit is supplied as a ref string, exactly as a dispatched op would pass it — so
the suite carries only the ``integration`` marker (real subprocess ``grep`` +
filesystem), mirroring the WP04 provenance/deferral suite.

Fixtures use production-shaped identifiers (a real mission slug with its ULID
suffix, 40-hex refs, real ``TopologySurface`` values) so a shape assumption that
would break on real data breaks here.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from mission_runtime import TopologySurface
from specify_cli.acceptance import post_consolidation as pc_module
from specify_cli.acceptance.matrix import (
    DEFERRED_TO_CONSOLIDATION,
    POST_CONSOLIDATION_PHASE_NAME,
    PROVENANCE_RECORDED,
    AcceptanceMatrix,
    NegativeInvariant,
    read_acceptance_matrix,
    write_acceptance_matrix,
)
from specify_cli.acceptance.post_consolidation import (
    PostConsolidationResult,
    PostConsolidationViolation,
    verify_deferred_invariants,
)

pytestmark = pytest.mark.integration

MISSION_SLUG = "lifecycle-gate-execution-context-01KY72GQ"
CONSOLIDATION_REF = "1a2b3c4d5e6f7081920a3b4c5d6e7f8091a2b3c4"
ALT_REF = "9f2c1a7e4b3d0a6f8c2e1d5b7a9040f3e6c8b1d2"
SCOPED_DIR = "src/specify_cli/newpkg"
OLD_PATTERN = "LegacyDefectMarker"
DEFERRED_ID = "NI-newpkg-no-legacy-marker"


def _deferred_invariant() -> NegativeInvariant:
    """A ``deferred_to_consolidation`` grep_absence invariant scoped to a mission-owned dir."""
    return NegativeInvariant(
        invariant_id=DEFERRED_ID,
        description="the mission's new package carries no LegacyDefectMarker",
        verification_method="grep_absence",
        verification_command=OLD_PATTERN,
        result=DEFERRED_TO_CONSOLIDATION,
        scope=SCOPED_DIR,
        evidence="scoped subject absent pre-consolidation; deferred.",
        deferred_reason="scoped path absent on primary pre-consolidation (FR-003).",
        deferred_to_phase=POST_CONSOLIDATION_PHASE_NAME,
    )


def _consolidated_tree(tmp_path: Path, *, marker_present: bool) -> Path:
    """Materialise a consolidated mission tree where the scoped dir now exists.

    Writes a sentinel ``consolidated.txt`` at the tree root standing in for "the
    consolidation has already completed" — the C7 tests assert it is untouched. The
    scoped package exists (it does post-consolidation) and either does or does not
    contain the forbidden pattern.
    """
    tree = tmp_path / "consolidated-tree"
    pkg = tree / SCOPED_DIR
    pkg.mkdir(parents=True)
    (tree / "consolidated.txt").write_text("consolidation completed\n", encoding="utf-8")
    body = f"# {OLD_PATTERN} still here\n" if marker_present else "# clean module\n"
    (pkg / "mod.py").write_text(body, encoding="utf-8")
    return tree


def _write_matrix(tree: Path, invariants: list[NegativeInvariant]) -> Path:
    """Write ``acceptance-matrix.json`` into the consolidated tree's feature dir."""
    feature_dir = tree / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    matrix = AcceptanceMatrix(mission_slug=MISSION_SLUG, negative_invariants=invariants)
    write_acceptance_matrix(feature_dir, matrix)
    return feature_dir


def _reload(feature_dir: Path) -> AcceptanceMatrix:
    """Read back the persisted matrix, asserting it exists (keeps mypy narrow)."""
    persisted = read_acceptance_matrix(feature_dir)
    assert persisted is not None
    return persisted


def _run(tree: Path, feature_dir: Path, *, ref: str = CONSOLIDATION_REF) -> PostConsolidationResult:
    return verify_deferred_invariants(
        tree, feature_dir, consolidation_ref=ref, mission_slug=MISSION_SLUG
    )


# ---------------------------------------------------------------------------
# C6 — a deferred invariant is judged against the consolidated tree
# ---------------------------------------------------------------------------


def test_c6_deferred_confirmed_absent_judged_on_consolidated_tree(tmp_path: Path) -> None:
    """C6/FR-004: a clean deferred invariant clears against the consolidated tree.

    The outcome is stamped ``verified_surface_kind = CONSOLIDATED`` with the
    consolidation commit as ``verified_ref``.
    """
    tree = _consolidated_tree(tmp_path, marker_present=False)
    feature_dir = _write_matrix(tree, [_deferred_invariant()])

    result = _run(tree, feature_dir)

    assert result.passed is True
    assert result.verified == [DEFERRED_ID]
    assert not result.violations

    judged = _reload(feature_dir).negative_invariants[0]
    assert judged.result == "confirmed_absent"
    assert judged.verified_surface_kind == TopologySurface.CONSOLIDATED.value
    assert judged.verified_ref == CONSOLIDATION_REF
    assert judged.provenance_origin == PROVENANCE_RECORDED
    # No longer deferred — the scheduling fields are cleared.
    assert judged.deferred_reason is None
    assert judged.deferred_to_phase is None


def test_c6_verified_ref_is_consolidation_commit(tmp_path: Path) -> None:
    """C6: the recorded ``verified_ref`` is exactly the consolidation commit passed in."""
    tree = _consolidated_tree(tmp_path, marker_present=False)
    feature_dir = _write_matrix(tree, [_deferred_invariant()])

    _run(tree, feature_dir, ref=ALT_REF)

    judged = _reload(feature_dir).negative_invariants[0]
    assert judged.verified_ref == ALT_REF


# ---------------------------------------------------------------------------
# C7 / FR-005 — a violated deferred invariant fails the OP, not the consolidation
# ---------------------------------------------------------------------------


def test_c7_still_present_fails_op_and_names_invariant(tmp_path: Path) -> None:
    """C7/FR-005: a deferred invariant that proves still_present fails the op, named."""
    tree = _consolidated_tree(tmp_path, marker_present=True)
    feature_dir = _write_matrix(tree, [_deferred_invariant()])

    result = _run(tree, feature_dir)

    assert result.passed is False
    assert [v.invariant_id for v in result.violations] == [DEFERRED_ID]
    assert result.violations[0].result == "still_present"
    # The op names the specific invariant in its failure message (FR-005).
    assert DEFERRED_ID in result.failure_message()

    judged = _reload(feature_dir).negative_invariants[0]
    assert judged.result == "still_present"
    assert judged.verified_surface_kind == TopologySurface.CONSOLIDATED.value


def test_c7_raise_for_violations_fails_the_op(tmp_path: Path) -> None:
    """C7: the fail-loud path raises, naming the invariant, for a dispatched op to fail on."""
    tree = _consolidated_tree(tmp_path, marker_present=True)
    feature_dir = _write_matrix(tree, [_deferred_invariant()])

    result = _run(tree, feature_dir)

    with pytest.raises(PostConsolidationViolation) as excinfo:
        result.raise_for_violations()
    assert excinfo.value.error_code == "POST_CONSOLIDATION_INVARIANT_VIOLATED"
    assert DEFERRED_ID in str(excinfo.value)


def test_c7_consolidation_left_untouched_on_violation(tmp_path: Path) -> None:
    """C7: a violation fails the op but does NOT roll back / touch the consolidation.

    The sentinel standing in for the completed consolidation is byte-identical
    afterwards, and the offending source is unchanged — nothing about the
    consolidated tree is reverted.
    """
    tree = _consolidated_tree(tmp_path, marker_present=True)
    feature_dir = _write_matrix(tree, [_deferred_invariant()])
    sentinel = tree / "consolidated.txt"
    module = tree / SCOPED_DIR / "mod.py"
    sentinel_before = sentinel.read_text(encoding="utf-8")
    module_before = module.read_text(encoding="utf-8")

    result = _run(tree, feature_dir)

    assert result.passed is False
    assert sentinel.read_text(encoding="utf-8") == sentinel_before
    assert module.read_text(encoding="utf-8") == module_before


def test_passing_op_raise_is_a_noop(tmp_path: Path) -> None:
    """raise_for_violations is a no-op when the op passed."""
    tree = _consolidated_tree(tmp_path, marker_present=False)
    feature_dir = _write_matrix(tree, [_deferred_invariant()])

    result = _run(tree, feature_dir)

    result.raise_for_violations()  # must not raise
    assert "cleared" in result.failure_message()


# ---------------------------------------------------------------------------
# C3 preservation — only deferred rows are re-judged
# ---------------------------------------------------------------------------


def test_terminal_invariant_preserved_verbatim(tmp_path: Path) -> None:
    """C3/NI-2: a recorded terminal invariant is NOT re-judged by the op."""
    tree = _consolidated_tree(tmp_path, marker_present=True)
    # A recorded terminal ``confirmed_absent`` for the SAME pattern that is now
    # present on the tree — if the op wrongly re-judged it, it would flip to
    # still_present. It must be preserved verbatim instead.
    terminal = NegativeInvariant(
        invariant_id="NI-already-recorded",
        description="recorded absent on primary, must not be re-judged",
        verification_method="grep_absence",
        verification_command=OLD_PATTERN,
        result="confirmed_absent",
        scope=SCOPED_DIR,
        evidence="grep found zero matches",
        verified_ref=ALT_REF,
        verified_surface_kind=TopologySurface.PRIMARY.value,
        provenance_origin=PROVENANCE_RECORDED,
    )
    feature_dir = _write_matrix(tree, [terminal, _deferred_invariant()])

    result = _run(tree, feature_dir)

    persisted = _reload(feature_dir)
    kept = next(
        ni for ni in persisted.negative_invariants if ni.invariant_id == "NI-already-recorded"
    )
    assert kept.result == "confirmed_absent"
    assert kept.verified_surface_kind == TopologySurface.PRIMARY.value
    assert kept.verified_ref == ALT_REF
    # Only the deferred one is verified this run.
    assert result.verified == [DEFERRED_ID]


def test_unjudgeable_deferred_left_intact(tmp_path: Path) -> None:
    """An unknown method that cannot resolve stays deferred rather than demoting to pending."""
    tree = _consolidated_tree(tmp_path, marker_present=False)
    unjudgeable = replace(
        _deferred_invariant(), verification_method="unknown_method", verification_command=None
    )
    feature_dir = _write_matrix(tree, [unjudgeable])

    result = _run(tree, feature_dir)

    assert result.verified == []
    assert result.passed is True
    kept = _reload(feature_dir).negative_invariants[0]
    assert kept.result == DEFERRED_TO_CONSOLIDATION
    assert kept.deferred_to_phase == POST_CONSOLIDATION_PHASE_NAME


def test_no_matrix_is_a_pass(tmp_path: Path) -> None:
    """No acceptance matrix on the consolidated tree -> nothing deferred -> passes."""
    tree = _consolidated_tree(tmp_path, marker_present=True)
    feature_dir = tree / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)

    result = _run(tree, feature_dir)

    assert isinstance(result, PostConsolidationResult)
    assert result.passed is True
    assert result.verified == []
    assert result.matrix_path is None


# ---------------------------------------------------------------------------
# T034 — decoupling from merge/ and the rollback machinery (by construction)
# ---------------------------------------------------------------------------


def test_module_has_zero_merge_or_rollback_coupling() -> None:
    """T034/WP06: the module imports nothing from ``merge/`` or the rollback seam.

    Enforced by a static AST scan of the module source, so a future edit that adds a
    ``from specify_cli.consolidation`` / rollback import is caught here rather than at
    review. Keeping the module file-disjoint from the consolidation transaction is
    the load-bearing decoupling (C7).
    """
    source = Path(pc_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    # Scan the dotted module paths only (a substring scan of the source would
    # false-positive on the docstring, which deliberately explains WHY there is no
    # call-in from merge/executor.py). No imported module may reach the
    # consolidation transaction or its rollback machinery.
    forbidden = [
        name
        for name in imported
        for part in name.split(".")
        if part in {"merge", "executor", "rollback"}
    ]
    assert forbidden == [], (
        f"post_consolidation must stay file-disjoint from the consolidation "
        f"transaction — offending imports: {forbidden}"
    )
