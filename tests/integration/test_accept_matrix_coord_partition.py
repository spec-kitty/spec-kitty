"""#2404 coord-topology characterization: acceptance-matrix.json across ALL
three write paths, locked closed end to end (FR-009, SC-003).

WP01 (``117d86a68``, ``commit_router.py::_group_files_by_partition``) closed
the #2404 defect *shape* at the seam: a mixed-partition batch committed under
ONE nominal ``kind`` no longer resolves every file to that kind's partition —
each file is reclassified via ``kind_for_mission_file`` and split into its own
commit. WP02 (``bede15843``, ``accept.py``) routed the accept-gate's own
residual commit through the same seam. What neither WP proves END TO END is
that ``acceptance-matrix.json`` — a COORD-partition kind
(``MissionArtifactKind.ACCEPTANCE_MATRIX`` stays in
``mission_runtime.artifacts._PLACEMENT_ARTIFACT_KINDS``; the WP explicitly did
NOT flip it to a PRIMARY kind, see ``tracer-design-decisions.md``) — actually
lands on the coordination surface and is read back FRESH by accept's own read
seam (``resolve_feature_dir_for_mission`` + ``read_acceptance_matrix``, the
exact two calls ``acceptance/__init__.py::_check_lane_gates`` makes) via each
of the three real production write paths:

1. ``spec-commit`` (``spec_commit_cmd.py::spec_commit_command``, T011)
2. ``finalize-tasks``'s commit phase (the ``kind=TASKS_INDEX`` batch that
   ALSO includes ``acceptance-matrix.json``,
   ``mission_finalize.py::_commit_finalize_artifacts``, T012)
3. ``accept``'s own residual commit
   (``accept.py::_commit_residual_acceptance_artifacts``, WP02, T013)

Build ON #2462's landed ``tests/integration/test_placement_partition_golden_
path.py`` (``_init_git_repo`` / ``_create_mission`` / ``_commit`` /
``_materialize_coord_worktree``) — reused verbatim below, NOT duplicated —
plus ``tests/lane_test_utils.py`` for a production-shaped ``lanes.json``
keyed on a REAL minted ``mission_id``/``mid8`` (the #2462 CI-fixture lesson:
a meta-less/empty-mid8 fixture now hard-fails loudly,
``CoordinationWorkspaceIdentityUnresolved``, #2091 M-1 — never a silent
fallback).

NFR-001 (critical): every assertion below pins the resolved coord dir against
``CoordinationWorkspace.resolve(...)`` — the SAME canonical materialiser
WP01's router uses to write — never a hand-rolled ``-coord`` husk path. This
is the "kind-CORRECT post-fix surface", not the stale kind-blind husk
Directive-041 forbids re-pinning.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from mission_runtime import MissionArtifactKind, MissionTopology, placement_seam
from specify_cli.acceptance.gates_core import (
    AcceptanceCheckDiagnostic,
    _acceptance_matrix_read_dir,
    _evaluate_acceptance_matrix,
)
from specify_cli.acceptance.matrix import (
    AcceptanceMatrix,
    NegativeInvariant,
    read_acceptance_matrix,
    write_acceptance_matrix,
)
from specify_cli.cli.commands.accept import _commit_residual_acceptance_artifacts
from specify_cli.coordination import commit_router as commit_router_mod
from specify_cli.coordination.commit_router import CommitRouterResult, commit_for_mission
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.core.mission_creation import MissionCreationResult
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.missions._read_path_resolver import resolve_feature_dir_for_mission

# Reused verbatim from #2462's golden-path scaffolding (do NOT duplicate the
# git/mission-creation primitives — see module docstring).
from tests.integration.test_placement_partition_golden_path import (
    _commit,
    _create_mission,
    _init_git_repo,
    _materialize_coord_worktree,
)
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# A non-default working branch (#2404-lite / T012 note): ``main``/``master``
# are protected by default (``ProtectionPolicy._DEFAULT_PROTECTED_BRANCHES``).
# The finalize-path phase (T012) commits a MIXED batch — a PRIMARY-kind file
# (tasks.md) alongside the COORD-kind matrix — in ONE ``commit_for_mission``
# call; on a protected primary the PRIMARY-partition group would be refused
# (``no_op_wrong_surface``), which is an orthogonal concern (FR-008) this test
# does not exercise. A dedicated unprotected working branch keeps every phase
# exercising ONLY the partition-routing seam under test (mirrors the golden
# path's own SINGLE_BRANCH convention of avoiding ``main`` for this reason).
_WORK_BRANCH = "matrix-coord-partition-work"
_SLUG = "accept-matrix-coord-partition"


def _make_spec_commit_app() -> typer.Typer:
    """Expose ``spec_commit_command`` as a bare Typer app (T011 CLI driver).

    Mirrors ``tests/specify_cli/cli/commands/test_spec_commit_cmd.py``'s
    ``_make_app`` harness, but here NOTHING below ``spec_commit_command``
    is mocked — real ``commit_for_mission``, real git, real coordination
    worktree materialisation. Only the process CWD anchors ``_current_repo_
    root()`` (via ``monkeypatch.chdir``), matching how a real ``spec-kitty
    spec-commit`` invocation resolves its repo root from the operator's cwd.
    """
    from specify_cli.cli.commands.spec_commit_cmd import spec_commit_command

    app = typer.Typer()
    app.command()(spec_commit_command)
    return app


def _build_coord_mission_for_matrix(tmp_path: Path) -> tuple[MissionCreationResult, Path, Path]:
    """T010: a coord-topology mission with a valid MINTED mid8, golden-path-built.

    Reuses the golden-path module's low-level primitives (init repo -> create
    mission via the real ``create_mission_core`` -> commit a spec -> materialise
    the coord worktree) rather than re-implementing them (C-001 in spirit — one
    canonical fixture-construction sequence, not a parallel one). Seeds a
    production-shaped ``lanes.json`` via ``tests/lane_test_utils.py``, keyed on
    the REAL minted ``mission_id`` (never an empty/meta-less mid8 — #2462 CI
    lesson, #2091 M-1).

    Returns ``(result, coord_root, coord_feature_dir)``:
    - ``result.feature_dir`` is the PRIMARY mission dir.
    - ``coord_root`` is the coordination worktree's repo root.
    - ``coord_feature_dir`` is ``coord_root/kitty-specs/<slug>`` — the SAME
      path ``mission_runtime.placement_seam(...).read_dir(ACCEPTANCE_MATRIX)``
      and WP01's ``commit_router`` resolve to for a COORD-partition write.
    """
    _init_git_repo(tmp_path, branch=_WORK_BRANCH)
    result = _create_mission(tmp_path, _SLUG, MissionTopology.COORD)

    spec_file = result.feature_dir / "spec.md"
    spec_file.write_text("# Spec — accept-matrix-coord-partition\n", encoding="utf-8")
    _commit(tmp_path, str(spec_file.relative_to(tmp_path)), "feat: add spec")

    coord_root = _materialize_coord_worktree(tmp_path, result)
    coord_feature_dir = coord_root / "kitty-specs" / result.mission_slug

    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    mission_id = str(meta["mission_id"])
    assert len(mission_id) == 26, f"expected a full 26-char ULID, got {mission_id!r}"
    mid8 = mission_id[:8]
    assert mid8, "minted mid8 must be non-empty (#2091 M-1 CI lesson)"

    write_single_lane_manifest(
        result.feature_dir,
        mission_id=mission_id,
        target_branch=result.target_branch,
    )
    _commit(tmp_path, str((result.feature_dir / "lanes.json").relative_to(tmp_path)), "feat: seed lanes.json")

    # Coord-topology divergence assertion (WP prompt requirement): the fixture
    # genuinely has TWO distinct surfaces, computed via the SAME canonical
    # composer WP01's write side and this test's read-back assertions both use
    # — never a hand-rolled path. A collapsed (coord == primary) fixture would
    # make every "lands on coord" assertion below vacuous.
    expected_coord_root = CoordinationWorkspace.resolve(tmp_path, result.mission_slug, mid8)
    assert coord_root == expected_coord_root
    assert coord_feature_dir != result.feature_dir, (
        "fixture invariant violated: coord and primary must be genuinely divergent surfaces, or every coord-landing assertion is vacuous"
    )
    assert not coord_feature_dir.exists(), (
        "fixture invariant: the coord worktree must NOT carry kitty-specs/<slug>/ "
        "yet — it is materialised lazily by the first COORD-partition write "
        "(matches coord_topology_fixture.py's base-husk invariant)"
    )

    return result, coord_root, coord_feature_dir


def _matrix_with_marker(mission_slug: str, marker: str) -> AcceptanceMatrix:
    """Build a minimal, realistic acceptance matrix carrying *marker* in extras.

    One negative invariant with a pattern that can never match keeps
    ``overall_verdict`` computed as ``"pass"`` (real
    ``AcceptanceMatrix.overall_verdict`` logic, not hand-set) — mirrors
    ``test_accept_residual_partition.py``'s fixture shape (WP02).
    """
    return AcceptanceMatrix(
        mission_slug=mission_slug,
        criteria=[],
        negative_invariants=[
            NegativeInvariant(
                invariant_id="NI1",
                description="legacy symbol must be absent",
                verification_method="grep_absence",
                verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
                result="confirmed_absent",
            )
        ],
        extras={"marker": marker},
    )


def _clear_stray_primary_matrix_residue(primary_feature_dir: Path) -> None:
    """Delete a stray, untracked PRIMARY-side ``acceptance-matrix.json`` copy.

    Neither ``spec_commit_command`` (T011) nor this test's direct
    ``commit_for_mission`` call mirroring the finalize commit phase (T012)
    threads ``primary_paths_created_this_invocation`` for a COORD-kind file
    the way ``mission_finalize.py::_commit_finalize_artifacts`` does for
    artifacts it scaffolds itself — so committing a COORD-partition file
    (routed to the coord worktree) leaves the SOURCE copy sitting untracked
    on the PRIMARY checkout (the router only stages/copies, it never deletes
    the primary source unless that residue-cleanup set is threaded).

    That stray primary copy is orthogonal to THIS WP's seam (partition
    routing, not residue GC) but if left in place it silently poisons the
    NEXT phase: ``accept.py::_stage_artifacts_in_coord_worktree`` blindly
    re-copies FROM the primary-rooted path whenever it exists (M2's coord
    residual-commit staging, WP02), which would clobber a fresher COORD-side
    edit with the stale primary blob. Clearing it between phases mirrors the
    realistic steady state between distinct operator actions and keeps each
    phase's assertions scoped to the write-path/partition-routing claim under
    test (SC-003), not this separate residue-GC gap.
    """
    stray = primary_feature_dir / "acceptance-matrix.json"
    if stray.exists():
        stray.unlink()


def _read_back_via_accept_seam(repo_root: Path, mission_slug: str) -> tuple[Path, AcceptanceMatrix | None]:
    """Resolve + read exactly as ``accept.py::_check_lane_gates`` does.

    ``_check_lane_gates`` computes ``read_feature_dir =
    resolve_feature_dir_for_mission(repo_root, feature)`` (in
    ``collect_feature_summary``) and then ``read_acceptance_matrix(feature_dir)``
    where ``feature_dir`` is that SAME ``read_feature_dir`` — this helper is
    that exact two-call sequence, not a parallel resolver (C-001).
    """
    resolved = resolve_feature_dir_for_mission(repo_root, mission_slug)
    return resolved, read_acceptance_matrix(resolved)


# ===========================================================================
# T010 — fixture smoke test
# ===========================================================================


def test_fixture_mints_production_shaped_coord_topology_mission(tmp_path: Path) -> None:
    """T010: the shared fixture builds a real, non-vacuous coord-topology mission."""
    result, coord_root, coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)

    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["topology"] == "coord"
    assert meta.get("coordination_branch"), "coord-topology mission must record a coordination_branch"
    assert coord_root != tmp_path, "coord worktree must be a distinct checkout from the primary repo"
    assert coord_feature_dir.parent.parent == coord_root


# ===========================================================================
# T011 / T012 / T013 — the three write paths, driven sequentially against
# ONE mission so SC-003 ("no stale copy") is proven across the FULL lifecycle:
# each phase's accept-seam read must reflect the freshest write, never a
# leftover from an earlier phase or partition.
# ===========================================================================


def test_matrix_lands_on_coord_via_all_three_write_paths_no_stale_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result, coord_root, coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)
    slug = result.mission_slug

    # -----------------------------------------------------------------
    # T011 — spec-commit path
    # -----------------------------------------------------------------
    marker_1 = "T011_SPEC_COMMIT_MARKER"
    matrix_path = write_acceptance_matrix(result.feature_dir, _matrix_with_marker(slug, marker_1))

    app = _make_spec_commit_app()
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    cli_result = runner.invoke(
        app,
        [str(matrix_path), "--message", "T011: land matrix via spec-commit", "--mission", slug, "--json"],
        catch_exceptions=False,
    )
    assert cli_result.exit_code == 0, cli_result.output
    payload: dict[str, Any] = json.loads(cli_result.output)
    assert payload["success"] is True
    assert payload["committed"] is True

    resolved_1, acc_matrix_1 = _read_back_via_accept_seam(tmp_path, slug)
    assert resolved_1 == coord_feature_dir, (
        "T011 (#2404 / NFR-001): spec-commit must land acceptance-matrix.json "
        f"on the kind-CORRECT coord surface ({coord_feature_dir}), and accept's "
        f"own read seam must resolve that SAME dir, got {resolved_1}"
    )
    assert acc_matrix_1 is not None, "accept's read seam found no matrix after spec-commit"
    assert acc_matrix_1.extras.get("marker") == marker_1
    # The coord worktree's own tree is clean — a real commit landed, not a
    # dangling staged copy.
    coord_status = _porcelain(coord_root)
    assert coord_status == "", f"coord worktree dirty after spec-commit: {coord_status!r}"
    _clear_stray_primary_matrix_residue(result.feature_dir)

    # -----------------------------------------------------------------
    # T012 — finalize-tasks commit-phase path (mixed TASKS_INDEX batch)
    # -----------------------------------------------------------------
    marker_2 = "T012_FINALIZE_MARKER"
    tasks_md = result.feature_dir / "tasks.md"
    tasks_md.write_text("# Work Packages\n\n## WP01 - fixture\n- [ ] T001 do a thing\n", encoding="utf-8")
    tasks_dir = result.feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    wp_file = tasks_dir / "WP01.md"
    wp_file.write_text("---\nwork_package_id: WP01\ntitle: fixture WP\n---\n# WP01\n", encoding="utf-8")
    write_acceptance_matrix(result.feature_dir, _matrix_with_marker(slug, marker_2))

    # Mirrors mission_finalize.py::_commit_finalize_artifacts's EXACT call
    # shape (files = _collect_finalize_artifacts(...), kind=TASKS_INDEX) —
    # driven directly rather than through the full `finalize-tasks` CLI, which
    # also runs ownership/dependency/risk validation orthogonal to the
    # partition-routing seam under test here.
    finalize_files = (tasks_md, wp_file, result.feature_dir / "acceptance-matrix.json")
    finalize_policy = ProtectionPolicy.resolve(tmp_path)
    finalize_result: CommitRouterResult = commit_for_mission(
        repo_root=tmp_path,
        mission_slug=slug,
        files=finalize_files,
        message="T012: finalize-tasks commit phase",
        policy=finalize_policy,
        kind=MissionArtifactKind.TASKS_INDEX,
    )
    assert finalize_result.status == "committed", finalize_result

    resolved_2, acc_matrix_2 = _read_back_via_accept_seam(tmp_path, slug)
    assert resolved_2 == coord_feature_dir
    assert acc_matrix_2 is not None
    assert acc_matrix_2.extras.get("marker") == marker_2, (
        "T012 (#2404 mixed-batch class): a TASKS_INDEX-kind batch that ALSO "
        "carries acceptance-matrix.json must still land the matrix on COORD "
        "(split-and-commit, contracts/partition-aware-commit-seam.md) — a "
        "'per-batch kind' regression would land it on PRIMARY instead and "
        "accept would read the STALE T011 copy or nothing"
    )
    # The PRIMARY-kind files in the SAME batch land directly on the primary
    # branch (unaffected by the split) — proof the fast path for the
    # co-resident partition still works.
    primary_tasks_show = _git(tmp_path, "show", f"HEAD:kitty-specs/{slug}/tasks.md")
    assert "WP01" in primary_tasks_show.stdout
    _clear_stray_primary_matrix_residue(result.feature_dir)

    # -----------------------------------------------------------------
    # T013 — accept's own residual commit path (SC-003) + mixed-batch proof
    # -----------------------------------------------------------------
    marker_3 = "T013_ACCEPT_RESIDUAL_MARKER"
    # Simulate accept's own readiness-check mutation: `_check_lane_gates`
    # calls `write_acceptance_matrix(read_feature_dir, ...)` where
    # `read_feature_dir` is ALREADY the coord dir — write directly there.
    write_acceptance_matrix(coord_feature_dir, _matrix_with_marker(slug, marker_3))
    # AND dirty a PRIMARY-kind artifact in the SAME window, so the residual
    # commit call proves the mixed-partition-batch class stays closed (DoD):
    # a caller mixing primary + coord dirt cannot reintroduce a stale matrix
    # on either surface.
    spec_file = result.feature_dir / "spec.md"
    spec_file.write_text("# Spec — accept-matrix-coord-partition\nv2\n", encoding="utf-8")

    created = _commit_residual_acceptance_artifacts(tmp_path, slug)
    assert created is True

    resolved_3, acc_matrix_3 = _read_back_via_accept_seam(tmp_path, slug)
    assert resolved_3 == coord_feature_dir
    assert acc_matrix_3 is not None
    assert acc_matrix_3.extras.get("marker") == marker_3, (
        "T013 / SC-003: accept's residual commit must land the freshest "
        "matrix on coord and accept's own read seam must see it immediately "
        "— no stale copy from T011/T012 leaking through"
    )
    primary_spec_show = _git(tmp_path, "show", f"HEAD:kitty-specs/{slug}/spec.md")
    assert "v2" in primary_spec_show.stdout, (
        "mixed-batch primary residual (spec.md) must ALSO land on primary in "
        "the same residual-commit call — the wrong-kind-commit class stays "
        "closed for BOTH partitions simultaneously, not just the coord one"
    )
    # No TRACKED-modified residue remains on either surface (a real commit
    # landed both parts of the mixed batch). Untracked scaffolding noise
    # (``.kittify/``, ``.worktrees/``, an un-committed ``status.events.jsonl``
    # seeded by mission creation, etc.) is expected and orthogonal to this
    # WP's seam — ``_dirty_paths_with_prefix`` itself deliberately excludes
    # ``??`` entries for the same reason (accept.py docstring), so this
    # assertion mirrors that same tracked-vs-untracked distinction rather
    # than demanding a byte-for-byte pristine ``git status``.
    assert not _tracked_dirty_lines(tmp_path), f"primary checkout has tracked-but-uncommitted residue: {_porcelain(tmp_path)!r}"
    assert not _tracked_dirty_lines(coord_root), f"coord worktree has tracked-but-uncommitted residue: {_porcelain(coord_root)!r}"


# ===========================================================================
# Regression pin: prove the characterization above WOULD go RED if the seam
# regressed to per-batch kind (reviewer guidance / NFR-001).
# ===========================================================================


def test_per_batch_kind_regression_would_misroute_matrix_off_coord(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates a partition-classifier defect and shows the seam's guard is real.

    Post-#2650 (WP05) ``_group_files_by_partition`` decides membership via
    ``is_coord_residue_churn`` (WP12 retired the former ``mission_runtime``
    ``is_coordination_artifact_residue_path`` predicate onto this owner leg) —
    the retired ``kind_for_mission_file`` per-file classifier no longer drives
    the split (patching it is a no-op now). To keep this falsifiability check
    valid against the CURRENT classifier, monkeypatch the residue predicate to
    always return ``False`` — collapsing EVERY file (including the
    COORD-residue ``acceptance-matrix.json``) into the PRIMARY bucket. Committing the
    matrix with the SPEC-commit's nominal ``kind=SPEC`` under this patched router must then
    land it on the PRIMARY target branch instead of coord — proving that
    ``test_matrix_lands_on_coord_via_all_three_write_paths_no_stale_copy``'s
    ``resolved_1 == coord_feature_dir`` assertion is genuinely falsifiable, not a tautology.
    """
    result, coord_root, coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)
    slug = result.mission_slug

    monkeypatch.setattr(commit_router_mod, "is_coord_residue_churn", lambda *_a, **_kw: False)

    matrix_path = write_acceptance_matrix(result.feature_dir, _matrix_with_marker(slug, "REGRESSION_MARKER"))
    policy = ProtectionPolicy.resolve(tmp_path)
    regressed_result: CommitRouterResult = commit_for_mission(
        repo_root=tmp_path,
        mission_slug=slug,
        files=(matrix_path,),
        message="regression: per-batch-kind spec-commit",
        policy=policy,
        kind=MissionArtifactKind.SPEC,
    )

    # Under the regression the matrix is treated as a SPEC (primary) artifact:
    # it commits directly to the primary working branch, and the coord
    # worktree never receives it.
    assert regressed_result.status == "committed", regressed_result
    assert not coord_feature_dir.exists(), "regression check invalid: coord dir should NOT be materialised when the per-file classifier is disabled"
    resolved, acc_matrix = _read_back_via_accept_seam(tmp_path, slug)
    assert acc_matrix is None or acc_matrix.extras.get("marker") != "REGRESSION_MARKER" or resolved != coord_feature_dir, (
        "the per-batch-kind regression must NOT be indistinguishable from the "
        "fixed seam: accept's read seam must not find the regressed write "
        "sitting on the coord surface"
    )


# ===========================================================================
# Accept-gate READ-PARTITION regression (folded into coord-commit-integrity):
# ``gates_core._evaluate_acceptance_matrix`` must read the acceptance-matrix
# from the COORD surface (where write_acceptance_matrix lands it under coord
# topology), not the PRIMARY feature_dir threaded through the gate pipeline
# (the ``PRIMARY_METADATA`` read dir). Reading the PRIMARY dir mis-reports a
# false "acceptance-matrix.json ... was not found" and blocks accept on a
# mission whose matrix is correctly on coord.
# ===========================================================================


def test_acceptance_matrix_read_dir_resolves_coord_surface(tmp_path: Path) -> None:
    """``_acceptance_matrix_read_dir`` resolves the COORD dir under coord topology.

    The matrix is written ONLY to the coord ``feature_dir`` (mirroring the three
    real write paths) and NOT to the primary dir; the read-dir resolver must
    hand back that coord surface — pinned against the same canonical
    ``placement_seam(...).read_dir(ACCEPTANCE_MATRIX)`` the write side lands on,
    never a hand-rolled ``-coord`` husk (NFR-001 / Directive-044).
    """
    result, _coord_root, coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)
    slug = result.mission_slug

    # The real write paths (spec-commit / finalize / accept-residual) materialise
    # this subdir via the commit router; write directly for a focused test.
    coord_feature_dir.mkdir(parents=True, exist_ok=True)
    write_acceptance_matrix(coord_feature_dir, _matrix_with_marker(slug, "COORD_ONLY"))
    assert coord_feature_dir.exists()
    assert not (result.feature_dir / "acceptance-matrix.json").exists(), (
        "fixture invariant: matrix must be COORD-only to exercise the read-partition bug (a stray primary copy would mask it)"
    )

    resolved = _acceptance_matrix_read_dir(tmp_path, result.feature_dir)
    assert resolved == coord_feature_dir, f"coord-topology acceptance-matrix read must resolve the coord surface ({coord_feature_dir}), got {resolved}"
    assert read_acceptance_matrix(resolved) is not None


def test_coord_matrix_gate_reads_from_coord_not_primary(tmp_path: Path) -> None:
    """RED-first: the accept gate must NOT report a coord-only matrix as missing.

    Drives ``_evaluate_acceptance_matrix`` with EXACTLY the ``feature_dir``
    production threads into ``_check_lane_gates`` — the ``PRIMARY_METADATA``
    read dir (``collect_feature_summary``). Pre-fix the gate read that PRIMARY
    dir, found no matrix, and appended an ``acceptance_matrix`` blocked check
    ("... was not found"); post-fix it resolves the coord surface and passes.
    This test references NO new symbol, so it fails RED cleanly (an assertion,
    not an ImportError) against the pre-fix gate.
    """
    result, _coord_root, coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)
    slug = result.mission_slug

    # Matrix lands ONLY on the coord surface (verdict computes to "pass").
    coord_feature_dir.mkdir(parents=True, exist_ok=True)
    write_acceptance_matrix(coord_feature_dir, _matrix_with_marker(slug, "COORD_ONLY"))
    assert not (result.feature_dir / "acceptance-matrix.json").exists()

    # The exact feature_dir collect_feature_summary passes to _check_lane_gates.
    read_feature_dir = placement_seam(tmp_path, slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)

    activity_issues: list[str] = []
    skipped_checks: list[AcceptanceCheckDiagnostic] = []
    blocked_checks: list[AcceptanceCheckDiagnostic] = []
    _evaluate_acceptance_matrix(
        tmp_path,
        read_feature_dir,
        activity_issues,
        skipped_checks,
        blocked_checks,
        mutate_matrix=False,
    )

    assert not any(c.check == "acceptance_matrix" for c in blocked_checks), (
        f"false 'acceptance-matrix not found' on a coord-only matrix — the gate read the PRIMARY dir instead of coord: {[c.to_dict() for c in blocked_checks]}"
    )
    assert not any("was not found" in issue for issue in activity_issues), activity_issues
    # overall_verdict == "pass" → no fail/pending verdict issue appended.
    assert not any("verdict is" in issue for issue in activity_issues), activity_issues


def test_flat_mission_matrix_read_dir_stays_primary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fallback preserved: a non-coord mission reads the matrix from PRIMARY.

    ``routes_through_coordination`` is False for ``SINGLE_BRANCH``, so the
    resolver must return the raw ``feature_dir`` unchanged — flat / lane
    missions read exactly where they do today (regression guard for the
    non-coord path the folded fix must not disturb).

    Approach (a) — pin the guard DIRECTLY (renata MEDIUM): a bare
    ``resolved == feature_dir`` assertion cannot distinguish guarded from
    unguarded, because for a SINGLE_BRANCH mission
    ``placement_seam(...).read_dir(ACCEPTANCE_MATRIX)`` collapses to the SAME
    primary ``feature_dir`` — the test would pass even if the
    ``routes_through_coordination`` short-circuit were deleted. Instead spy on
    ``mission_runtime.placement_seam`` (the helper resolves it via
    ``from mission_runtime import placement_seam`` at call time, so patching the
    package attribute is visible) and assert it is NEVER consulted: the guard
    must return before the seam. Drop the ``if not routes_through_coordination``
    line and this test reds on ``seam_calls == []``.
    """
    import mission_runtime

    _init_git_repo(tmp_path, branch=_WORK_BRANCH)
    result = _create_mission(tmp_path, "flat-accept-matrix", MissionTopology.SINGLE_BRANCH)
    slug = result.mission_slug

    write_acceptance_matrix(result.feature_dir, _matrix_with_marker(slug, "PRIMARY"))

    seam_calls: list[str] = []
    real_seam = mission_runtime.placement_seam

    def _spy_seam(repo_root: Path, mission_slug: str) -> mission_runtime.PlacementSeam:
        seam_calls.append(mission_slug)
        return real_seam(repo_root, mission_slug)

    monkeypatch.setattr(mission_runtime, "placement_seam", _spy_seam)

    resolved = _acceptance_matrix_read_dir(tmp_path, result.feature_dir)

    assert seam_calls == [], (
        f"non-coord mission must short-circuit on routes_through_coordination BEFORE consulting placement_seam (guard pin); seam was called: {seam_calls}"
    )
    assert resolved == result.feature_dir, f"non-coord mission must read the matrix from the primary feature_dir ({result.feature_dir}), got {resolved}"
    assert read_acceptance_matrix(resolved) is not None


# ---------------------------------------------------------------------------
# Small git porcelain helpers (mirrors test_accept_residual_partition.py's
# local ``_git``/``_porcelain`` — not imported cross-module since they are
# one-line subprocess wrappers, not scaffolding logic).
# ---------------------------------------------------------------------------


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=True)


def _porcelain(repo_root: Path) -> str:
    return _git(repo_root, "status", "--porcelain").stdout


def _tracked_dirty_lines(repo_root: Path) -> list[str]:
    """Return ``git status --porcelain`` lines for TRACKED-but-uncommitted paths.

    Excludes ``??`` (untracked) entries — the same distinction
    ``accept.py::_dirty_paths_with_prefix`` applies — so scaffolding noise
    (``.kittify/``, ``.worktrees/``, an un-committed ``status.events.jsonl``)
    does not fail an assertion this WP's seam has no bearing on.
    """
    return [line for line in _porcelain(repo_root).splitlines() if not line.startswith("??")]


# ===========================================================================
# WP03 (T010/T011, #4966) — decision-ledger / accept-gate PRIMARY-partition
# agreement on a MATERIALIZED status-only coord husk.
#
# This module's filename was already claimed by the #2404 acceptance-matrix
# coord-partition characterization above (an unrelated, earlier mission); the
# WP03 tasks file names this exact path in ``create_intent``, expecting a new
# file. Appending here (rather than a colliding second file) keeps ONE test
# per path while adding the WP03-owned coverage the WP prompt asks for.
#
# History: T010's first pass (commit ``15971a5ef6``) routed ONLY the
# ``meta.json`` identity read through ``PRIMARY_METADATA``
# (``decisions/service.py::_resolve_mission_id``), leaving the decisions
# LEDGER's own directory (``decisions/index.json`` / ``DM-<id>.md``) on the
# COORD partition -- a residual split-brain characterized by AC-D2 below as
# an ``xfail``. The operator approved widening WP03's owned-files scope to
# close that residual: ``decisions/service.py``'s ``_ledger_dir`` (new) now
# resolves the ledger directory through the SAME ``PRIMARY_METADATA`` kind as
# ``_resolve_mission_id``, and ``cli/commands/_decisions_doctor.py`` gained
# its own parallel ``_ledger_dir`` resolving to the identical PRIMARY dir, so
# the reconciler's repair target and sidecar lock stay in lockstep with the
# forward write path. ``status.events.jsonl`` (COORD/``STATUS_STATE``) is
# unaffected -- only the ledger identity/content dir moved. AC-D2 below is
# now a plain (non-xfail) assertion.
# ===========================================================================


from unittest.mock import patch

from specify_cli.acceptance import _check_needs_clarification
from specify_cli.decisions.models import OriginFlow
from specify_cli.decisions.service import defer_decision, open_decision, resolve_decision

_DECISION_WORK_BRANCH = "decision-ledger-accept-work"
_DECISION_HUSK_SLUG = "decision-ledger-accept-husk"


def _build_husk_coord_mission_for_decisions(tmp_path: Path) -> tuple[MissionCreationResult, Path]:
    """A coord-topology mission whose coord worktree is a MATERIALIZED
    status-only husk: ``kitty-specs/<slug>/`` exists on coord (real
    ``CoordinationWorkspace.resolve``-backed git worktree) and carries ONLY
    ``status.events.jsonl`` -- never ``meta.json``, never ``decisions/`` --
    the #4966 locus (``coordination/coherence.py:168``, "and nothing else").
    """
    _init_git_repo(tmp_path, branch=_DECISION_WORK_BRANCH)
    result = _create_mission(tmp_path, _DECISION_HUSK_SLUG, MissionTopology.COORD)
    coord_root = _materialize_coord_worktree(tmp_path, result)
    coord_mission_dir = coord_root / "kitty-specs" / result.mission_slug
    coord_mission_dir.mkdir(parents=True, exist_ok=True)
    (coord_mission_dir / "status.events.jsonl").write_text("", encoding="utf-8")

    assert not (coord_mission_dir / "meta.json").exists()
    assert not (coord_mission_dir / "decisions").exists()
    assert (result.feature_dir / "meta.json").exists()
    return result, coord_mission_dir


def test_decision_open_resolves_via_primary_on_materialized_status_only_husk(
    tmp_path: Path,
) -> None:
    """AC-D1 (#4966): the real service API resolves ``meta.json`` via PRIMARY
    on a materialised status-only husk -- no ``MISSION_NOT_FOUND``. Mirrors
    ``test_decision_single_authority.py``'s CLI-level pin at the service-API
    level (T010's actual owned surface)."""
    result, _coord_mission_dir = _build_husk_coord_mission_for_decisions(tmp_path)

    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1):
        resp = open_decision(
            tmp_path,
            result.mission_slug,
            origin_flow=OriginFlow.PLAN,
            step_id="plan.degrader-policy",
            input_key="degrader_policy",
            question="Which degrader policy?",
            options=("fail-closed", "fail-open"),
            actor="tester",
        )

    assert resp.decision_id != "DRY_RUN"
    assert resp.mission_id == result.meta["mission_id"]


def test_accept_gate_reads_resolved_decision_from_same_primary_ledger_as_service(
    tmp_path: Path,
) -> None:
    """AC-D2 (#4966): a deferred->resolved decision, opened against a
    MATERIALIZED status-only husk through the real service API, reaches the
    SAME PRIMARY ledger ``acceptance/__init__.py::_has_blocking_clarification_marker``
    reads (``load_index(file_path.parent)`` where ``file_path`` is a PRIMARY
    planning artifact) -- so a resolved clarification marker stops blocking
    ``accept``.

    Previously pinned as an ``xfail`` characterization: see the module-level
    scope note above for the residual split T010's first pass left open and
    the WP03-scope-expansion fix (``_ledger_dir`` in both
    ``decisions/service.py`` and ``cli/commands/_decisions_doctor.py``) that
    closes it. ``test_open_resolves_meta_via_primary_on_materialized_status_only_husk``
    (T009) and ``test_decision_open_resolves_via_primary_on_materialized_status_only_husk``
    above cover the meta.json-identity part of #4966 T010 already closed.
    """
    result, _coord_mission_dir = _build_husk_coord_mission_for_decisions(tmp_path)
    slug = result.mission_slug

    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1), patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=2):
        opened = open_decision(
            tmp_path,
            slug,
            origin_flow=OriginFlow.PLAN,
            step_id="plan.degrader-policy",
            input_key="degrader_policy",
            question="Which degrader policy?",
            options=("fail-closed", "fail-open"),
            actor="tester",
        )
        defer_decision(
            tmp_path,
            slug,
            opened.decision_id,
            rationale="revisit after research spike",
            actor="tester",
        )
        resolve_decision(
            tmp_path,
            slug,
            opened.decision_id,
            final_answer="fail-closed",
            actor="tester",
        )

    spec_path = result.feature_dir / "spec.md"
    spec_path.write_text(
        f"The degrader policy must be chosen. [NEEDS CLARIFICATION: which degrader policy] <!-- decision_id: {opened.decision_id} -->\n",
        encoding="utf-8",
    )

    blocking = _check_needs_clarification([spec_path])

    assert blocking == [], (
        "AC-D2 (#4966): accept's PRIMARY-anchored clarification-marker check "
        f"still reports {spec_path} as blocking after decision "
        f"{opened.decision_id!r} was resolved via the real service API on a "
        "materialised status-only husk -- the decisions LEDGER content "
        "(as opposed to the meta.json identity read T010 fixes) has not "
        "reached the SAME PRIMARY partition accept reads. See the "
        "module-level scope note above."
    )


def test_flat_mission_decision_accept_agreement_unchanged(tmp_path: Path) -> None:
    """AC-D3 regression: a non-coord (``SINGLE_BRANCH``) mission's decision
    open/resolve -> accept-marker agreement is unaffected by T010's fix --
    ``STATUS_STATE`` and ``PRIMARY_METADATA`` already coincide with the
    primary dir for a coord-less topology, so this path was never split."""
    _init_git_repo(tmp_path, branch=_DECISION_WORK_BRANCH)
    result = _create_mission(tmp_path, "flat-decision-accept", MissionTopology.SINGLE_BRANCH)
    slug = result.mission_slug

    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1), patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=2):
        opened = open_decision(
            tmp_path,
            slug,
            origin_flow=OriginFlow.PLAN,
            step_id="plan.degrader-policy",
            input_key="degrader_policy",
            question="Which degrader policy?",
            options=("fail-closed", "fail-open"),
            actor="tester",
        )
        resolve_decision(
            tmp_path,
            slug,
            opened.decision_id,
            final_answer="fail-closed",
            actor="tester",
        )

    spec_path = result.feature_dir / "spec.md"
    spec_path.write_text(
        f"The degrader policy must be chosen. [NEEDS CLARIFICATION: which degrader policy] <!-- decision_id: {opened.decision_id} -->\n",
        encoding="utf-8",
    )

    assert _check_needs_clarification([spec_path]) == []
