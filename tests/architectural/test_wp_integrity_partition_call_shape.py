"""Static call-shape gate: no un-partitioned coord planning commit (FR-011 / SC-006).

write-path-integrity WP04 / T019. The #3371 P0 was a single call shape in
``_commit_planning_artifacts_transaction``: the ``placement_ref is not None`` arm
committed the WHOLE ``files_to_commit`` batch VERBATIM to ``placement_ref.ref``
(the coordination branch under coord topology), so a PRIMARY ``lanes.json`` landed
on coord and add/add-conflicted at lane allocation. WP02 fixed it by partitioning
the batch (``_partition_files_for_commit``) and committing each group to its own
partition ref.

This gate makes that class hard to silently reintroduce. It is **static** (AST
over the module source) — it asserts a *call shape*, not a runtime file-set (the
"no ``lanes.json`` on a coord ref" runtime property is owned by the SC-002
real-git scan, NOT this gate, per plan IC-05 / FR-011).

The invariant (structural, no line-number whitelist):

    Every ``_run_planning_artifact_commit`` call that receives the RAW,
    un-partitioned ``files_to_commit`` batch (an ``ast.Name`` whose id is
    ``files_to_commit``) MUST target the mission's PRIMARY target ref —
    ``destination_ref=_commit_target_ref_for(...)``. Passing the raw batch to
    any OTHER destination (``placement_ref.ref``, ``coord_branch``, an unknown
    ref) is the #3371 shape and is forbidden.

Why the destination-ref classification rather than an ``implement.py:909``
line-number carve-out (OD-3): the legitimate flat/legacy arm commits the raw
batch VERBATIM **to the primary target ref** by design (FR-011 explicitly carves
it out — "no coord partition exists on a flat mission"). Keying the carve-out on
the *destination* (raw batch is legal only to the primary target ref, never to a
coord ref) captures exactly the flat-arm exemption FR-011 sanctions, survives
refactoring that moves line numbers, and does not condemn any legitimate shape.
The coord-topology arms all commit a PARTITION output (``primary_files`` /
``coord_files``), never the raw batch, so they are unaffected.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
# implement-degod WP05: the planning-commit adapter (and its partition-split arms) moved out of implement.py.
_IMPLEMENT = _REPO_ROOT / "src" / "specify_cli" / "cli" / "commands" / "implement_planning_commit.py"

_COMMIT_FN = "_run_planning_artifact_commit"
_RAW_BATCH_NAME = "files_to_commit"
_PRIMARY_TARGET_HELPER = "_commit_target_ref_for"


@dataclass(frozen=True)
class Violation:
    """A ``_run_planning_artifact_commit`` call that commits the raw batch off-primary."""

    lineno: int
    files_repr: str
    destination_repr: str


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_raw_batch(node: ast.expr | None) -> bool:
    """The ``files=`` argument is the raw, un-partitioned ``files_to_commit`` name."""
    return isinstance(node, ast.Name) and node.id == _RAW_BATCH_NAME


def _is_primary_target_ref(node: ast.expr | None) -> bool:
    """The ``destination_ref=`` argument resolves the mission's PRIMARY target ref.

    That is ``_commit_target_ref_for(...)`` — the only destination a raw,
    un-partitioned batch may legally reach (the flat/legacy arm; FR-011 carve-out).
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _PRIMARY_TARGET_HELPER
    )


def _iter_commit_calls(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        target = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if target == _COMMIT_FN:
            calls.append(node)
    return calls


def find_unpartitioned_coord_commits(source: str) -> list[Violation]:
    """Return every ``_run_planning_artifact_commit`` call that commits the raw
    ``files_to_commit`` batch to a non-primary (coord/unknown) destination ref.

    Extracted as a pure ``str -> list[Violation]`` detector so the gate can prove
    it BITES a reverted P0 shape against a synthetic snippet, without touching the
    production source (see the ``TestDetectorBite`` cases below).
    """
    tree = ast.parse(source)
    violations: list[Violation] = []
    for call in _iter_commit_calls(tree):
        files = _keyword(call, "files")
        destination = _keyword(call, "destination_ref")
        if _is_raw_batch(files) and not _is_primary_target_ref(destination):
            violations.append(
                Violation(
                    lineno=call.lineno,
                    files_repr=ast.unparse(files) if files is not None else "<missing>",
                    destination_repr=(
                        ast.unparse(destination) if destination is not None else "<missing>"
                    ),
                )
            )
    return violations


# ---------------------------------------------------------------------------
# The gate: the production tree must be clean.
# ---------------------------------------------------------------------------


def test_no_unpartitioned_coord_planning_commit() -> None:
    """FR-011 / SC-006: no coord-topology planning commit routes the raw batch.

    RED against the pre-WP02 tree (the ``placement_ref`` arm committed
    ``files=files_to_commit`` to ``destination_ref=placement_ref.ref``); GREEN on
    the fixed tree where every coord arm commits a partition output.
    """
    source = _IMPLEMENT.read_text(encoding="utf-8")
    violations = find_unpartitioned_coord_commits(source)
    assert not violations, (
        f"{_IMPLEMENT} commits the raw un-partitioned `files_to_commit` batch to a "
        f"non-primary destination ref — the #3371 P0 call shape (FR-011/SC-006). "
        f"Each coord-topology `_run_planning_artifact_commit` must receive a "
        f"partition output (`primary_files`/`coord_files`), and the raw batch may "
        f"only target `_commit_target_ref_for(...)` (the flat/legacy arm). "
        f"Violations: {violations}"
    )


def test_gate_is_non_vacuous() -> None:
    """Guard the gate itself: the production source must actually contain the
    commit calls the invariant ranges over, so a rename/refactor that makes the
    detector find zero calls cannot silently pass the gate above.
    """
    source = _IMPLEMENT.read_text(encoding="utf-8")
    calls = _iter_commit_calls(ast.parse(source))
    assert len(calls) >= 3, (
        f"Expected >=3 `{_COMMIT_FN}` calls in {_IMPLEMENT} (the partition-split "
        f"arms); found {len(calls)}. The static gate cannot be trusted if the "
        f"calls it inspects have moved or been renamed."
    )


# ---------------------------------------------------------------------------
# Proof the gate BITES: a deliberately-reverted P0 shape must be flagged, and
# the legitimate flat/legacy arm must NOT be a false positive.
# ---------------------------------------------------------------------------

_REVERTED_P0_SNIPPET = """
def _commit_planning_artifacts_transaction(placement_ref, files_to_commit):
    if placement_ref is not None:
        _run_planning_artifact_commit(
            repo_root=repo_root,
            destination_ref=placement_ref.ref,
            files=files_to_commit,
            commit_msg=commit_msg,
        )
"""

_FLAT_ARM_SNIPPET = """
def _commit_planning_artifacts_transaction(files_to_commit):
    _run_planning_artifact_commit(
        repo_root=repo_root,
        destination_ref=_commit_target_ref_for(planning_branch),
        files=files_to_commit,
        commit_msg=commit_msg,
    )
"""

_PARTITIONED_COORD_SNIPPET = """
def _commit_planning_artifacts_transaction(placement_ref, files_to_commit):
    primary_files, coord_files = _partition_files_for_commit(files_to_commit)
    if primary_files:
        _run_planning_artifact_commit(
            destination_ref=_commit_target_ref_for(planning_branch),
            files=primary_files,
        )
    if coord_files:
        _run_planning_artifact_commit(
            destination_ref=placement_ref.ref,
            files=coord_files,
        )
"""


class TestDetectorBite:
    def test_reverted_p0_shape_is_flagged(self) -> None:
        """The exact #3371 revert (raw batch -> coord ref) must be caught."""
        violations = find_unpartitioned_coord_commits(_REVERTED_P0_SNIPPET)
        assert len(violations) == 1, violations
        assert violations[0].files_repr == _RAW_BATCH_NAME
        assert violations[0].destination_repr == "placement_ref.ref"

    def test_flat_arm_verbatim_is_not_a_false_positive(self) -> None:
        """The legitimate flat/legacy arm (raw batch -> PRIMARY target ref) is
        allowed by design (FR-011 carve-out) and must not be condemned."""
        assert find_unpartitioned_coord_commits(_FLAT_ARM_SNIPPET) == []

    def test_partitioned_coord_commit_is_not_a_false_positive(self) -> None:
        """Coord arms committing a partition output (`coord_files`) are clean even
        though they target a coord ref — only the RAW batch is forbidden there."""
        assert find_unpartitioned_coord_commits(_PARTITIONED_COORD_SNIPPET) == []
