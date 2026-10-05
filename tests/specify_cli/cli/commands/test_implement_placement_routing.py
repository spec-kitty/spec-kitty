"""WP03 (coord-primary-partition-lock) -- placement-seam routing for implement.py.

Red-first coverage (T010) for the two forbidden checkout-derived fallbacks
named by D11 / the seam contract (``kitty-specs/coord-primary-partition-lock-01KWZ46V/
contracts/seam-api.md``):

1. ``implement.py:886`` (symbol-anchored inside
   ``_ensure_planning_artifacts_committed_git``): the inline
   ``coord_branch if coord_branch else planning_branch`` grammar is a
   FORBIDDEN caller-side reconstruction of a placement decision the seam
   already resolved. When a ``placement_ref`` is threaded, the destination
   must be taken directly from it (``placement_ref.ref``), not rebuilt.

2. ``implement.py:1462`` (the WP status claim commit, inside ``implement()``):
   ``_get_current_branch(repo_root) or planning_branch`` derives the commit
   destination from whatever branch the operator happens to have checked
   out -- completely ignoring the already-resolved ``_placement_ref``. This
   is the literal D11 "None -> CommitTarget(ref=<checkout>)" grammar. T012
   fixes it fail-closed via the small, pure ``_resolve_claim_commit_target``
   extraction (Sonar-testable per the charter's "prefer testable
   extractions" guidance) instead of a broad end-to-end reproduction.

Each class below pins the FIXED (green) behavior; the docstrings record what
the pre-fix code did (the red baseline), consistent with this WP's git
history (T010 was authored and run red against the pre-fix source before
T011/T012 landed the fix in the same commit).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import CommitTarget

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# T012 / D11 -- _resolve_claim_commit_target fail-closed pure helper
# ---------------------------------------------------------------------------


class TestResolveClaimCommitTargetFailClosed:
    """Pre-fix, the WP status claim commit (``implement.py`` ~:1462) derived its
    destination via ``_get_current_branch(repo_root) or planning_branch`` --
    completely ignoring a failed (``None``) placement resolution and silently
    committing to whatever branch was checked out. Post-fix, a ``None``
    placement FAILS CLOSED with a structured, actionable error naming the
    remediation path; a resolved placement is used verbatim (no
    re-derivation, no checkout consultation at all).
    """

    def test_none_placement_ref_raises_structured_error(self) -> None:
        from specify_cli.cli.commands.implement import PlacementResolutionRequired
        from specify_cli.cli.commands.implement_cores import _resolve_claim_commit_target

        with pytest.raises(PlacementResolutionRequired) as excinfo:
            _resolve_claim_commit_target(None, mission_slug="demo-mission")

        # Structured (error_code) and actionable (names the remediation path).
        # #5113 / FR-014: names the REAL materializing command with the real
        # slug, never the retired `doctor workspaces --fix` (#2240) and never
        # a `<mission>` placeholder.
        assert excinfo.value.error_code == "PLACEMENT_RESOLUTION_REQUIRED"
        assert "doctor coordination --mission demo-mission --fix" in str(excinfo.value)

    def test_resolved_placement_ref_is_used_verbatim(self) -> None:
        """No re-derivation, no checkout consultation -- the resolved seam
        value is returned unchanged, even when it names a branch that is
        neither the current checkout nor `planning_branch` (proving the
        helper does not fall back to either)."""
        from specify_cli.cli.commands.implement_cores import _resolve_claim_commit_target

        target = CommitTarget(ref="kitty/mission-demo-AAAA1111")
        assert _resolve_claim_commit_target(target, mission_slug="demo-mission") is target

    def test_structured_error_is_not_swallowed_as_soft_warning(self) -> None:
        """D11: implement()'s WP-status-update try/except has a broad
        ``except Exception: console.print("[yellow]Warning:...")`` that
        historically downgraded ANY failure at this call site to a soft,
        non-fatal warning (production continues past it). A
        ``PlacementResolutionRequired`` must NOT be swallowed there -- it
        needs its own explicit ``except ...: raise`` clause (mirroring the
        pre-existing ``SafeCommitPathPolicyError`` pattern) so the refusal
        actually surfaces instead of being silently downgraded.
        """
        import inspect

        from specify_cli.cli.commands.implement import implement

        source = inspect.getsource(implement)
        raise_idx = source.index("except PlacementResolutionRequired:")
        # The dedicated clause must appear BEFORE the generic downgrade-to-warning
        # handler in source order (except clauses are evaluated in order). Match
        # the actual print statement (not any comment text referencing the same
        # warning message, which would give a false-positive ordering).
        warning_idx = source.index('console.print(f"[yellow]Warning:[/yellow] Could not update WP status')
        assert raise_idx < warning_idx
        # And it must actually re-raise, not swallow. The clause body sits
        # between the two markers found above; it must contain a bare
        # ``raise`` statement line (not just comment prose mentioning it).
        clause_body = source[raise_idx:warning_idx]
        assert any(line.strip() == "raise" for line in clause_body.splitlines())

    def test_head_mismatch_is_not_swallowed_as_soft_warning(self) -> None:
        """#610: the same broad ``except Exception`` downgrade also swallowed
        ``SafeCommitHeadMismatch`` -- a genuine branch-name mismatch on the
        WP-status claim commit -- leaving the worktree dirty (the status/lane
        files were already written to disk before the commit was attempted)
        for ``merge``'s dirty-worktree gate to trip on later. Mirrors
        ``test_structured_error_is_not_swallowed_as_soft_warning`` above:
        needs its own explicit ``except SafeCommitHeadMismatch: raise``
        clause, ordered before the generic downgrade-to-warning handler.
        """
        import inspect

        from specify_cli.cli.commands.implement import implement

        source = inspect.getsource(implement)
        raise_idx = source.index("except SafeCommitHeadMismatch:")
        warning_idx = source.index('console.print(f"[yellow]Warning:[/yellow] Could not update WP status')
        assert raise_idx < warning_idx
        clause_body = source[raise_idx:warning_idx]
        assert any(line.strip() == "raise" for line in clause_body.splitlines())


# ---------------------------------------------------------------------------
# T011 -- _ensure_planning_artifacts_committed_git routes via placement_ref
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "initial")


def _make_meta(feature_dir: Path, *, mission_id: str, mission_slug: str, coord_branch: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "mission_id": mission_id,
        "mission_slug": mission_slug,
        "mid8": mission_id[:8],
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-05-28T00:00:00+00:00",
        "friendly_name": "WP03 placement routing test",
        "coordination_branch": coord_branch,
    }
    (feature_dir / "meta.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


class TestEnsurePlanningArtifactsRoutesThroughPlacementRef:
    """Pre-fix, ``:886`` reconstructed the coord/primary choice with the
    forbidden ``coord_branch if coord_branch else planning_branch`` ternary
    -- an inline re-derivation of a decision the seam-resolved
    ``placement_ref`` already made (contracts/seam-api.md's explicitly
    forbidden caller grammar). The seam value is still consumed directly (no
    re-derivation), but write-path-integrity WP02 / T008 / FR-001 reverses the
    prior "whole batch to ``placement_ref.ref`` verbatim" contract (SANCTIONED
    C-004 reversal): the batch is now PARTITIONED, so the COORD-residue group
    lands on ``placement_ref.ref`` (the seam value, still verbatim for its
    partition) while the PRIMARY group lands on the mission's target branch. The
    rewritten test below (list-capture + mixed-kind batch) asserts BOTH refs
    receive their own partition -- the old last-write-wins single-``destination_ref``
    capture could not express the two-commit split.
    """

    def test_partitioned_batch_routes_each_group_to_its_own_ref(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """List-capture every ``acquire`` call's ``(destination_ref, paths)`` and
        prove the mixed-kind batch splits: the COORD-residue artifact
        (``issue-matrix.md``) lands on ``placement_ref.ref`` -- a SENTINEL value
        the meta-derived ``coord_branch`` could never itself produce, so a match
        proves the seam value drove the coord leg -- while the PRIMARY artifact
        (``tasks/WP01.md``) lands on the mission's target branch
        (``planning_branch``), never the coordination ref. Pre-WP02 the whole
        batch (including the PRIMARY WP file) was committed VERBATIM to
        ``placement_ref.ref``; this asserts the T008 partition instead.
        """
        from specify_cli.cli.commands.implement_planning_commit import _ensure_planning_artifacts_committed_git

        repo = tmp_path / "repo"
        _init_repo(repo)

        mission_slug = "wp03-route-demo"
        mission_id = "01J6XW9K00000000000000000P"
        meta_coord_branch = f"kitty/mission-{mission_slug}-{mission_id[:8]}"
        sentinel_seam_ref = "sentinel-seam-resolved-ref"

        feature_dir = repo / "kitty-specs" / mission_slug
        _make_meta(
            feature_dir,
            mission_id=mission_id,
            mission_slug=mission_slug,
            coord_branch=meta_coord_branch,
        )
        # PRIMARY-partition artifact: a WP task file.
        wp = feature_dir / "tasks" / "WP01.md"
        wp.parent.mkdir(parents=True, exist_ok=True)
        wp.write_text("lane: in_progress\n", encoding="utf-8")
        # COORD-residue artifact that SURVIVES staging: issue-matrix.md is a
        # coord-partition kind (ISSUE_MATRIX) but NOT the status log/snapshot,
        # so (unlike status.events.jsonl) it is not dropped by the status-state
        # staging filter -- it reaches files_to_commit and its own coord group.
        issue_matrix = feature_dir / "issue-matrix.md"
        issue_matrix.write_text("# Issue Matrix\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "seed feature dir")

        wp.write_text("lane: in_progress\nedited\n", encoding="utf-8")
        issue_matrix.write_text("# Issue Matrix\nedited\n", encoding="utf-8")

        calls: list[tuple[str, list[str]]] = []

        class _FakeTxn:
            def __init__(self, destination_ref: str) -> None:
                self._destination_ref = destination_ref
                self._paths: list[str] = []

            def __enter__(self) -> _FakeTxn:
                return self

            def __exit__(self, *exc: object) -> bool:
                calls.append((self._destination_ref, list(self._paths)))
                return False

            def write_artifact(self, repo_path: Path, _content: bytes) -> None:
                self._paths.append(repo_path.as_posix())

            def commit(self, _msg: str) -> None:
                return None

            def commit_idempotent(self, _msg: str) -> None:
                return None

        class _FakeBookkeepingTransaction:
            @classmethod
            def acquire(cls, **kwargs: object) -> _FakeTxn:
                return _FakeTxn(str(kwargs["destination_ref"]))

        monkeypatch.setattr(
            "specify_cli.coordination.transaction.BookkeepingTransaction",
            _FakeBookkeepingTransaction,
        )

        _ensure_planning_artifacts_committed_git(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP02",
            planning_branch="main",
            auto_commit=True,
            placement_ref=CommitTarget(ref=sentinel_seam_ref),
        )

        wp_rel = f"kitty-specs/{mission_slug}/tasks/WP01.md"
        matrix_rel = f"kitty-specs/{mission_slug}/issue-matrix.md"
        wp_dest = [ref for ref, paths in calls if wp_rel in paths]
        matrix_dest = [ref for ref, paths in calls if matrix_rel in paths]

        # COORD-residue group -> the seam-resolved sentinel ref (verbatim for
        # its partition).
        assert matrix_dest == [sentinel_seam_ref], (
            f"expected issue-matrix.md (COORD) on the seam ref {sentinel_seam_ref!r}; "
            f"got {matrix_dest!r} (all calls: {calls!r})"
        )
        # PRIMARY group -> the target branch, NEVER the coordination/sentinel ref
        # (the #3371 fix: PRIMARY artifacts never land on coord).
        assert wp_dest == ["main"], (
            f"expected WP01.md (PRIMARY) on the target branch 'main'; got "
            f"{wp_dest!r} (all calls: {calls!r})"
        )
        assert sentinel_seam_ref not in wp_dest

    def test_no_inline_forbidden_ternary_grammar_in_source(self) -> None:
        """Static guard: the exact forbidden grammar named in
        contracts/seam-api.md -- ``coord_branch if coord_branch else
        planning_branch`` (the pre-fix source wrapped the truthy arm in
        ``str(...)``: ``str(coord_branch) if coord_branch else
        planning_branch``) -- must not appear verbatim in implement.py,
        under either spelling."""
        import inspect

        from specify_cli.cli.commands import implement as implement_module
        from specify_cli.cli.commands import implement_planning_commit

        source = inspect.getsource(implement_module) + inspect.getsource(implement_planning_commit)
        assert "coord_branch if coord_branch else planning_branch" not in source
        assert "str(coord_branch) if coord_branch else planning_branch" not in source


class TestPrimarySurfaceStatusPaths:
    """#3784: ``_primary_surface_status_paths`` keeps the #2155 invariant that
    NO ``.worktrees/``-nested path enters a primary-root ``safe_commit`` bundle.

    The former inline filter dropped only the STATUS_STATE files
    (``is_status_state_path``) and let the coord-worktree ``tasks.md`` (a
    ``TASKS_INDEX`` kind) survive; the helper now excludes ANY
    ``is_under_worktrees_segment`` path on coord topology. On a flat/legacy
    mission every collected artifact is canonical on PRIMARY and stays.
    """

    def test_coord_drops_worktrees_nested_tasks_md_and_status_files(
        self, tmp_path: Path
    ) -> None:
        from specify_cli.cli.commands.implement import _primary_surface_status_paths

        wt = tmp_path / ".worktrees" / "slug-coord" / "kitty-specs" / "slug"
        wt.mkdir(parents=True)
        events = wt / "status.events.jsonl"
        status = wt / "status.json"
        tasks_md = wt / "tasks.md"
        for f in (events, status, tasks_md):
            f.write_text("x", encoding="utf-8")

        kept = _primary_surface_status_paths(
            [events, status, tasks_md], routes_through_coord=True
        )

        # Every coord-owned artifact is under .worktrees/ -> nothing survives.
        assert kept == []

    def test_flat_topology_keeps_all_collected_artifacts(
        self, tmp_path: Path
    ) -> None:
        from specify_cli.cli.commands.implement import _primary_surface_status_paths

        feature_dir = tmp_path / "kitty-specs" / "slug"
        feature_dir.mkdir(parents=True)
        events = feature_dir / "status.events.jsonl"
        status = feature_dir / "status.json"
        tasks_md = feature_dir / "tasks.md"
        for f in (events, status, tasks_md):
            f.write_text("x", encoding="utf-8")

        kept = _primary_surface_status_paths(
            [events, status, tasks_md], routes_through_coord=False
        )

        assert {p.resolve() for p in kept} == {
            events.resolve(),
            status.resolve(),
            tasks_md.resolve(),
        }
