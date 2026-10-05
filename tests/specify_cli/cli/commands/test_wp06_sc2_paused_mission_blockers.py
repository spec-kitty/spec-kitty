"""WP06 / T022 — SC-2 reproduction: the paused 01KTNWFC blockers do not reproduce.

The doctrine-glossary-architecture-consolidation mission (01KTNWFC) was paused by
two structural deadlocks (``work/MISSION_01KTNWFC_PAUSED.md``):

* **#1814** — ``record-analysis`` deadlocked on *coord residue*: the primary
  checkout of a coordination-topology mission legitimately carries stale copies
  of the coord-owned status log/snapshot, and the dirty-tree preflight counted
  that residue as an unsafe dirty working tree, so ``record-analysis`` could
  never run from the primary checkout.
* **#1816** — implement-claim blocked on a *planning-artifact branch-split*: the
  placement decision was derived independently from meta.json, so a flattened
  mission was mis-treated as a primary↔coord split.

WP06 resolves both by routing the placement decision through the context's
single :class:`CommitTarget` (the ``ArtifactPlacementFragment.placement_ref`` ==
``BranchRefFragment.destination_ref``, C-PLACE-1). These tests reproduce the two
blockers at the precise sites that deadlocked and assert they no longer do — the
checks are genuine (real ``git status`` residue / real porcelain entries), not
mocked away.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer
from click.testing import Result

from mission_runtime import CommitTarget, MissionTopology

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# WP13 (IC-07c) retired ``COORD_OWNED_STATUS_FILES``; this fixture module needs
# the two canonical status-artifact basenames as test-local seed data, not a
# churn-classifier verdict.
_STATUS_STATE_BASENAMES: frozenset[str] = frozenset({"status.events.jsonl", "status.json"})


def _patch_mission_topology(
    monkeypatch: pytest.MonkeyPatch, *, coord: bool
) -> None:
    """Stub the record-analysis seam's stored-topology read (FR-001b routing reads topology).

    #2056 WP04 relocated record-analysis + its dirty-tree preflight into
    ``mission_record_analysis``; the preflight reads ``resolve_topology`` from
    that seam's namespace, so the patch targets the seam (not the ``mission``
    shim, which no longer carries this name).
    """
    from specify_cli.cli.commands.agent import mission_record_analysis as _record_seam

    topology = MissionTopology.COORD if coord else MissionTopology.SINGLE_BRANCH
    monkeypatch.setattr(_record_seam, "resolve_topology", lambda _root, _slug: topology)


def _patch_implement_topology(
    monkeypatch: pytest.MonkeyPatch, *, coord: bool
) -> None:
    """Stub the implement module's stored-topology read (FR-001b routing reads topology).

    #5232 moved ``placement_coord_filter`` into the placement seam
    (``coordination/planning_commit``) -- that module holds its own
    ``resolve_topology`` import and is the one a directly-invoked
    ``placement_coord_filter`` actually reads at call time.
    ``implement.py`` still calls ``resolve_topology`` inline too (e.g. the WP
    claim-status commit), so both module namespaces are patched to keep every
    call path -- direct-core and through-implement -- stubbed consistently.
    """
    from specify_cli.cli.commands import implement as _implement_mod
    from specify_cli.coordination import planning_commit as _planning_commit_mod

    topology = MissionTopology.COORD if coord else MissionTopology.SINGLE_BRANCH
    monkeypatch.setattr(
        _implement_mod, "resolve_topology", lambda _root, _slug: topology
    )
    monkeypatch.setattr(
        _planning_commit_mod, "resolve_topology", lambda _root, _slug: topology
    )


# ---------------------------------------------------------------------------
# #1814 — record-analysis must not deadlock on coord residue
# ---------------------------------------------------------------------------
class TestRecordAnalysisCoordResidueNoDeadlock:
    """The dirty-tree preflight is context-aware (C-PLACE-1): under coordination
    topology the coord-owned status residue in the primary checkout is NOT a
    blocking dirty working tree."""

    def _repo_with_coord_residue(self, tmp_path: Path) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args: str) -> None:
            subprocess.run(
                ["git", *args], cwd=repo, check=True, capture_output=True, text=True
            )

        git("init", "-b", "kitty/mission-residue-lane-a")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "Test")
        mission_dir = repo / "kitty-specs" / "residue-01ABCDEF"
        mission_dir.mkdir(parents=True)
        # write-surface-coherence WP01-04 narrowed the residue authority: planning
        # + finalized + identity kinds (``plan.md`` / ``tasks.md`` / ``tasks/WP*.md``
        # / ``lanes.json``) are now PRIMARY-partition artifacts that live on
        # ``target_branch`` — a stale primary copy is REAL dirt, not droppable
        # residue. Only the COORD-partition artifacts (the status log/snapshot plus
        # the coordination-owned matrices ``acceptance-matrix.json`` / ``issue-matrix.md``)
        # remain residue whose stale primary copy the preflight must ignore.
        # Seed + commit coord-owned finalized artifacts so they are *tracked*; a
        # later edit makes them show up as worktree-modified residue.
        for name in sorted(_STATUS_STATE_BASENAMES):
            (mission_dir / name).write_text("{}\n", encoding="utf-8")
        for rel_path in (
            "acceptance-matrix.json",
            "issue-matrix.md",
        ):
            path = mission_dir / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("seed\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-m", "seed coord-owned artifacts")
        # The coord branch is now the canonical owner; the primary checkout edit
        # below is exactly the COORD-partition residue that deadlocked #1814/#1998.
        for name in sorted(_STATUS_STATE_BASENAMES):
            (mission_dir / name).write_text('{"stale": true}\n', encoding="utf-8")
        for rel_path in (
            "acceptance-matrix.json",
            "issue-matrix.md",
        ):
            (mission_dir / rel_path).write_text("stale primary residue\n", encoding="utf-8")
        return repo

    def test_coord_residue_does_not_block_record_analysis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.cli.commands.agent.mission import (
            _enforce_analysis_report_write_preflight,
        )

        repo = self._repo_with_coord_residue(tmp_path)
        monkeypatch.chdir(repo)
        _patch_mission_topology(monkeypatch, coord=True)

        coord_placement = CommitTarget(ref="kitty/mission-residue-01ABCDEF")

        # WP06 fix: coord-owned residue is filtered out — no DIRTY_WORKTREE deadlock.
        # The coord-vs-primary decision reads the STORED topology (FR-001b).
        _enforce_analysis_report_write_preflight(
            repo,
            json_output=True,
            placement_ref=coord_placement,
            mission_slug="residue-01ABCDEF",
        )

    def test_untracked_coord_residue_does_not_block_record_analysis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An UNTRACKED COORD-partition residue file does not block record-analysis.

        write-surface-coherence WP01-04 narrowing: the original fixture used an
        untracked ``tasks/`` dir, but ``WORK_PACKAGE_TASK`` is now a PRIMARY kind
        (a real dirty blocker). The coord-residue ignore path is exercised with an
        untracked COORD-partition artifact (``acceptance-matrix.json`` →
        ``ACCEPTANCE_MATRIX``), which stays coordination-owned under coord topology
        — its stale primary copy must still be ignored by the dirty-tree preflight.
        """
        from specify_cli.cli.commands.agent.mission import (
            _enforce_analysis_report_write_preflight,
        )

        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", *args],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout

        git("init", "-b", "kitty/mission-residue-lane-a")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "Test")
        mission_dir = repo / "kitty-specs" / "residue-01ABCDEF"
        mission_dir.mkdir(parents=True)
        (mission_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-m", "seed mission")
        (mission_dir / "acceptance-matrix.json").write_text("{}\n", encoding="utf-8")
        assert (
            "?? kitty-specs/residue-01ABCDEF/acceptance-matrix.json"
            in git("status", "--porcelain")
        )
        monkeypatch.chdir(repo)
        _patch_mission_topology(monkeypatch, coord=True)

        _enforce_analysis_report_write_preflight(
            repo,
            json_output=True,
            placement_ref=CommitTarget(ref="kitty/mission-residue-01ABCDEF"),
            mission_slug="residue-01ABCDEF",
        )

    def test_regression_guard_without_context_still_blocks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without the context placement ref (legacy call), the coord residue is
        still treated as dirty — proving the test exercises a *real* dirty tree
        and the fix is the context-awareness, not a weakened check."""
        from specify_cli.cli.commands.agent.mission import (
            _enforce_analysis_report_write_preflight,
        )

        repo = self._repo_with_coord_residue(tmp_path)
        monkeypatch.chdir(repo)

        with pytest.raises(typer.Exit):
            _enforce_analysis_report_write_preflight(repo, json_output=True)

    def test_genuine_uncommitted_edit_still_blocks_under_coord(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A *genuine* uncommitted non-status edit must still block even under
        coordination topology — the fix only ignores coord-owned residue, never
        real planning-artifact churn (no over-broad escape hatch)."""
        from specify_cli.cli.commands.agent.mission import (
            _enforce_analysis_report_write_preflight,
        )

        repo = self._repo_with_coord_residue(tmp_path)
        (repo / "kitty-specs" / "residue-01ABCDEF" / "src_real_edit.py").write_text(
            "dirty source edit\n", encoding="utf-8"
        )
        monkeypatch.chdir(repo)
        _patch_mission_topology(monkeypatch, coord=True)

        coord_placement = CommitTarget(ref="kitty/mission-residue-01ABCDEF")
        with pytest.raises(typer.Exit):
            _enforce_analysis_report_write_preflight(
                repo,
                json_output=True,
                placement_ref=coord_placement,
                mission_slug="residue-01ABCDEF",
            )


# ---------------------------------------------------------------------------
# #1816 — implement-claim must not block on a planning-artifact branch-split
# ---------------------------------------------------------------------------
class TestImplementClaimNoPlanningArtifactSplit:
    """The planning-artifact placement decision comes from the context's single
    :class:`CommitTarget` (C-PLACE-1), so a flattened mission is never mis-routed
    as a primary↔coord split."""

    def _entries(self) -> list[object]:
        from specify_cli.cli.commands.implement_cores import _PorcelainEntry

        return [
            _PorcelainEntry(
                xy=" M", path="kitty-specs/m/status.events.jsonl", is_structural=False
            ),
            _PorcelainEntry(
                xy=" M", path="kitty-specs/m/status.json", is_structural=False
            ),
            _PorcelainEntry(xy=" M", path="kitty-specs/m/tasks.md", is_structural=False),
        ]

    def test_flattened_placement_has_no_coord_split(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.cli.commands.implement_cores import _status_paths_for_commit
        from specify_cli.coordination.planning_commit import placement_coord_filter

        # FR-001b: the coord-vs-primary decision reads the STORED topology, not a
        # per-ref enum. A coord-less (flattened) topology → no coord split.
        _patch_implement_topology(monkeypatch, coord=False)
        flattened = CommitTarget(ref="fixups/code-engine-stabilization")
        # Flattened topology → no coord branch to reconcile (C-PLACE-1).
        coord_filter = placement_coord_filter(tmp_path, "m", flattened)
        assert coord_filter is None

        # Consequently the status files are committed on the single flattened ref
        # (not excluded as coord-owned) — there is no primary↔coord split.
        paths = _status_paths_for_commit(self._entries(), coord_filter)
        assert "kitty-specs/m/status.events.jsonl" in paths
        assert "kitty-specs/m/status.json" in paths
        assert "kitty-specs/m/tasks.md" in paths

    def test_coordination_placement_routes_to_coord_ref(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.cli.commands.implement_cores import _status_paths_for_commit
        from specify_cli.coordination.planning_commit import placement_coord_filter

        _patch_implement_topology(monkeypatch, coord=True)
        coord = CommitTarget(ref="kitty/mission-m-01ABCDEF")
        # Coordination topology → the coord ref owns the status files; the primary
        # checkout's copies are excluded so they don't clobber the seeded state.
        coord_filter = placement_coord_filter(tmp_path, "m", coord)
        assert coord_filter == "kitty/mission-m-01ABCDEF"
        paths = _status_paths_for_commit(self._entries(), coord_filter)
        assert "kitty-specs/m/status.events.jsonl" not in paths
        assert "kitty-specs/m/status.json" not in paths
        assert "kitty-specs/m/tasks.md" in paths

    def test_primary_placement_commits_status_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.cli.commands.implement_cores import _status_paths_for_commit
        from specify_cli.coordination.planning_commit import placement_coord_filter

        _patch_implement_topology(monkeypatch, coord=False)
        primary = CommitTarget(ref="main")
        # Primary/legacy topology → no coord owner; the primary status files are
        # canonical and must be committed.
        coord_filter = placement_coord_filter(tmp_path, "m", primary)
        assert coord_filter is None
        paths = _status_paths_for_commit(self._entries(), coord_filter)
        assert "kitty-specs/m/status.events.jsonl" in paths
        assert "kitty-specs/m/status.json" in paths


# ---------------------------------------------------------------------------
# WP02 / FR-006 / A-r1 (#1814 residual) — finalize leaves no primary residue
# ---------------------------------------------------------------------------
#
# Mission coordination-merge-stabilization-01KTXRVR, AC-A1: a REAL
# coordination-topology finalize-tasks run must leave `git status --porcelain`
# on the primary checkout free of planning-artifact residue created by the
# stager (lanes.json / matrices), so a subsequent record-analysis is not
# refused with DIRTY_WORKTREE. Cleanup is scoped to paths finalize itself
# materialized this invocation (research R6): an operator-authored untracked
# file planted pre-finalize SURVIVES. Constraint C-003: the fix never widens
# the status-log/snapshot exclusion set (formerly ``COORD_OWNED_STATUS_FILES``,
# retired onto the owner in WP13; now the ``STATUS_STATE`` kind, still exactly
# ``status.events.jsonl`` / ``status.json``).

_RESIDUE_MISSION_ID = "01T009RESIDUEFREE000000001"
_RESIDUE_MID8 = _RESIDUE_MISSION_ID[:8]
# write-surface-coherence WP01-04: planning artifacts (spec/plan/tasks/WP*) are
# PRIMARY-partition kinds that commit to ``target_branch`` for every topology.
# Under coord topology with a PROTECTED ``target_branch`` (``main``) the finalize
# planning commit is REFUSED (FR-008). To exercise the residue-free finalize
# (the #1814 class) the mission's ``target_branch`` must be a NON-protected
# feature branch that is checked out, so the planning commit lands cleanly there
# while status stays on the coordination branch.
_RESIDUE_TARGET_BRANCH = "feat/residue-work"


def _scaffold_residue_mission(repo: Path) -> str:
    """SC6-shaped coordination-topology mission on a NON-protected feature branch.

    write-surface-coherence WP01-04: ``target_branch`` is a non-protected feature
    branch (not ``main``) so the planning artifacts (now PRIMARY-partition kinds)
    commit to it instead of tripping the FR-008 protected-branch refusal, while
    the ``coordination_branch`` keeps the mission coordination-topology for status.
    """
    mission_dirname = f"residue-mission-{_RESIDUE_MID8}"
    feature_dir = repo / "kitty-specs" / mission_dirname
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    meta = {
        "mission_slug": mission_dirname,
        "mission_id": _RESIDUE_MISSION_ID,
        "mid8": _RESIDUE_MID8,
        "target_branch": _RESIDUE_TARGET_BRANCH,
        "coordination_branch": f"kitty/mission-residue-mission-{_RESIDUE_MID8}",
    }
    import json as _json

    (feature_dir / "meta.json").write_text(_json.dumps(meta) + "\n", encoding="utf-8")
    # Real spec-kitty projects gitignore the worktree root and local sync
    # state; without this, fixture-environment noise (not stager residue)
    # would pollute the porcelain assertions.
    (repo / ".gitignore").write_text(
        ".worktrees/\n.kittify/sync-state.json\n", encoding="utf-8"
    )
    # The WP frontmatter is pre-enriched with the fields finalize-tasks
    # records on first run (WP07 branch recording et al.) so the finalize
    # under test performs no frontmatter write — the porcelain check then
    # isolates exactly the stager-residue class (#1814 / FR-006).
    branch_strategy = (
        f"Planning artifacts for this mission were generated on "
        f"{_RESIDUE_TARGET_BRANCH}. During /spec-kitty.implement this WP may "
        f"branch from a dependency-specific base, but completed changes must "
        f"merge back into {_RESIDUE_TARGET_BRANCH} unless the human explicitly "
        f"redirects the landing branch."
    )
    (tasks_dir / "WP01-task.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Test WP01\n"
        "dependencies: []\n"
        "requirement_refs:\n"
        "- FR-001\n"
        "tracker_refs: []\n"
        f"planning_base_branch: {_RESIDUE_TARGET_BRANCH}\n"
        f"merge_target_branch: {_RESIDUE_TARGET_BRANCH}\n"
        f"branch_strategy: {branch_strategy}\n"
        "subtasks: []\n"
        "history: []\n"
        "authoritative_surface: src/module_wp01/\n"
        "execution_mode: code_change\n"
        "owned_files:\n"
        "- src/module_wp01/**\n"
        "tags: []\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n"
        "## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | Test requirement | Test passes. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n",
        encoding="utf-8",
    )

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)

    # Check out the non-protected feature branch BEFORE committing the mission so
    # the planning artifacts land on a branch whose HEAD safe_commit accepts.
    git("checkout", "-q", "-b", _RESIDUE_TARGET_BRANCH)
    git("add", ".")
    git("commit", "-q", "-m", "seed mission")
    git("branch", f"kitty/mission-residue-mission-{_RESIDUE_MID8}")
    return mission_dirname


def _run_real_finalize(repo: Path, mission_slug: str) -> Result:
    from unittest.mock import patch

    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent.mission import app

    with (
        patch(
            "specify_cli.cli.commands.agent.mission.locate_project_root",
            return_value=repo,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission.run_git_preflight",
            return_value=type("P", (), {"passed": True})(),
        ),
    ):
        return CliRunner().invoke(
            app,
            ["finalize-tasks", "--mission", mission_slug, "--json"],
            catch_exceptions=False,
        )


def _porcelain_lines(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


@pytest.mark.integration
class TestFinalizeLeavesNoPrimaryResidue:
    """AC-A1: residue-free finalize on coordination topology (#1814)."""

    @pytest.fixture(autouse=True)
    def _disable_saas_fanout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.status.emit as emit_module

        monkeypatch.setattr(emit_module, "_saas_fan_out", lambda *a, **k: None)
        # Disable hosted sync at its canonical source module: late
        # `from specify_cli.core.saas_sync_config import is_saas_sync_enabled`
        # imports (readiness coordinator, mission_type) must also see it disabled,
        # or environment-dependent writes leak into the porcelain assertions.

    def test_finalize_leaves_porcelain_free_of_stager_residue(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tests.git.protected_target_fixtures import build_protected_target_repo

        repo = build_protected_target_repo(tmp_path).repo_root
        mission_slug = _scaffold_residue_mission(repo)

        result = _run_real_finalize(repo, mission_slug)
        assert result.exit_code == 0, f"finalize failed:\n{result.output}"

        # The stager's own outputs must not remain as primary residue. The
        # coord-owned status log/snapshot are the emitter's (placement-aware
        # gate already excludes them, WP06); everything else under the mission
        # tree must be clean — in particular the AC-A1 trio: lanes.json,
        # tasks/*, and the scaffolded matrices.
        porcelain = _porcelain_lines(repo)
        residue = [
            line
            for line in porcelain
            if "kitty-specs/" in line
            and line.split("/")[-1] not in _STATUS_STATE_BASENAMES
        ]
        assert residue == [], (
            "finalize left planning-artifact residue on the primary checkout "
            f"(#1814 regression): {residue}"
        )
        for marker in ("lanes.json", "acceptance-matrix.json", "issue-matrix.md"):
            assert not any(marker in line for line in porcelain), (
                f"stager residue {marker!r} present in porcelain: {porcelain}"
            )

    def test_record_analysis_not_blocked_after_finalize(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mission_runtime import (
            MissionArtifactKind,
            resolve_placement_only,
            resolve_topology,
            routes_through_coordination,
        )

        from specify_cli.cli.commands.agent.mission import (
            _enforce_analysis_report_write_preflight,
        )
        from tests.git.protected_target_fixtures import build_protected_target_repo

        repo = build_protected_target_repo(tmp_path).repo_root
        mission_slug = _scaffold_residue_mission(repo)

        result = _run_real_finalize(repo, mission_slug)
        assert result.exit_code == 0, f"finalize failed:\n{result.output}"

        # write-surface-coherence WP01: ``kind`` is REQUIRED. record-analysis
        # writes ``ANALYSIS_REPORT``, which coord-commit-integrity FR-003
        # re-homed COORD->PRIMARY -- its placement resolves to the primary ref
        # even though this mission's topology routes other kinds through
        # coordination (checked separately below).
        placement = resolve_placement_only(
            repo, mission_slug, kind=MissionArtifactKind.ANALYSIS_REPORT
        )
        # FR-001b: the coordination-topology mission routes through coordination —
        # read from the STORED topology, not a per-ref enum.
        assert routes_through_coordination(resolve_topology(repo, mission_slug)) is True
        assert placement.ref

        # Absorb fixture-environment noise OUTSIDE the mission tree (identity
        # regeneration may rewrite .kittify/config.yaml in this hermetic
        # fixture). This is unrelated to the stager-residue class under test —
        # the kitty-specs/ tree is deliberately NOT committed here, so any
        # stager residue still trips the preflight below.
        subprocess.run(
            ["git", "add", ".kittify"], cwd=repo, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-q", "--allow-empty", "-m", "fixture: env noise"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        # record-analysis runs from a (non-protected) working branch; the
        # dirty-tree preflight must not be tripped by stager residue.
        subprocess.run(
            ["git", "checkout", "-q", "-b", "analysis-work"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        monkeypatch.chdir(repo)
        # FR-001b: the coord-residue filter reads the STORED topology, so the
        # mission_slug must be threaded for the coord-vs-primary decision.
        _enforce_analysis_report_write_preflight(
            repo, json_output=True, placement_ref=placement, mission_slug=mission_slug
        )

    def test_operator_authored_untracked_file_survives(
        self, tmp_path: Path
    ) -> None:
        """Negative control (R6 scoping): a pre-finalize operator file in the
        staged set is NEVER deleted by the residue cleanup."""
        from tests.git.protected_target_fixtures import build_protected_target_repo

        repo = build_protected_target_repo(tmp_path).repo_root
        mission_slug = _scaffold_residue_mission(repo)

        operator_file = (
            repo / "kitty-specs" / mission_slug / "tasks" / "operator-scratch.md"
        )
        operator_content = "# operator notes — do not delete\n"
        operator_file.write_text(operator_content, encoding="utf-8")

        result = _run_real_finalize(repo, mission_slug)
        assert result.exit_code == 0, f"finalize failed:\n{result.output}"

        assert operator_file.exists(), (
            "R6 scoping violated: finalize residue cleanup deleted an "
            "operator-authored pre-existing file"
        )
        assert operator_file.read_text(encoding="utf-8") == operator_content

    def test_coord_owned_status_files_not_widened(self) -> None:
        """C-003: the residue fix is cleanup-at-source; the coord-owned
        exclusion set keeps exactly its two members.

        WP13 (IC-07c) retired ``COORD_OWNED_STATUS_FILES`` onto the canonical
        file->kind classifier; this pins the same invariant against the new
        owner (``MissionArtifactKind.STATUS_STATE``) instead of the retired
        frozenset.
        """
        from mission_runtime import MissionArtifactKind, kind_for_mission_file

        candidates = (
            "status.events.jsonl",
            "status.json",
            "tasks.md",
            "lanes.json",
            "acceptance-matrix.json",
            "issue-matrix.md",
        )
        classified_status_state = {
            name
            for name in candidates
            if kind_for_mission_file(f"kitty-specs/m/{name}") is MissionArtifactKind.STATUS_STATE
        }
        assert classified_status_state == {"status.events.jsonl", "status.json"}


class TestStagerResidueCleanupScoping:
    """Unit pins for the stager's R6 defensive checks (WP02 / T008)."""

    def test_created_path_is_removed_after_staging(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent.mission import (
            _stage_finalize_artifacts_in_coord_worktree,
        )

        repo = tmp_path / "repo"
        coord = tmp_path / "coord"
        src = repo / "kitty-specs" / "m" / "lanes.json"
        src.parent.mkdir(parents=True)
        src.write_text('{"lanes": []}\n', encoding="utf-8")

        coord_files = _stage_finalize_artifacts_in_coord_worktree(
            [src],
            coord,
            repo,
            primary_paths_created_this_invocation=frozenset({src}),
        )

        assert coord_files == [coord / "kitty-specs" / "m" / "lanes.json"]
        assert coord_files[0].read_text(encoding="utf-8") == '{"lanes": []}\n'
        assert not src.exists(), "created-this-invocation residue must be removed"

    def test_preexisting_path_is_never_removed(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent.mission import (
            _stage_finalize_artifacts_in_coord_worktree,
        )

        repo = tmp_path / "repo"
        coord = tmp_path / "coord"
        src = repo / "kitty-specs" / "m" / "tasks" / "WP01-task.md"
        src.parent.mkdir(parents=True)
        src.write_text("# WP01\n", encoding="utf-8")

        _stage_finalize_artifacts_in_coord_worktree(
            [src],
            coord,
            repo,
            primary_paths_created_this_invocation=frozenset(),
        )

        assert src.exists(), "R6: a pre-existing path must never be deleted"

    def test_diverged_primary_copy_is_skipped_with_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the primary bytes do not match the staged coord copy (e.g. a
        racing writer), cleanup skips the file instead of deleting it.

        #2056 WP08: the stager relocated from mission.py into commit_router (the
        former mission.py ``_stage_finalize_artifacts_in_coord_worktree``
        reconciled into the router's canonical ``_stage_artifacts_in_coord_worktree``),
        so the ``shutil.copy2`` patch + call target the router namespace.
        """
        import specify_cli.coordination.commit_router as commit_router_module

        repo = tmp_path / "repo"
        coord = tmp_path / "coord"
        src = repo / "kitty-specs" / "m" / "lanes.json"
        src.parent.mkdir(parents=True)
        src.write_text("original\n", encoding="utf-8")

        def _copy_then_mutate_src(s: object, d: object) -> None:
            Path(str(d)).write_text("original\n", encoding="utf-8")
            Path(str(s)).write_text("mutated-after-staging\n", encoding="utf-8")

        monkeypatch.setattr(commit_router_module.shutil, "copy2", _copy_then_mutate_src)

        commit_router_module._stage_finalize_artifacts_in_coord_worktree(
            [src],
            coord,
            repo,
            primary_paths_created_this_invocation=frozenset({src}),
        )

        assert src.exists(), "diverged primary copy must be skipped, not deleted"
        assert src.read_text(encoding="utf-8") == "mutated-after-staging\n"
