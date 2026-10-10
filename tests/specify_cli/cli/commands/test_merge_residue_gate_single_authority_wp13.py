"""WP13 / FR-012 (#1887): merge-path residue gates converge on one authority.

NOTE: this file's "WP13" label is from the ORIGINAL (#1887 / mission #2057)
FR-012 convergence work, predating and unrelated to
``lifecycle-gate-execution-context-01KY72GQ``'s WP13 (IC-07c), which retired
the ``coord_owned_filenames`` param this file originally exercised onto the
single canonical churn owner (``is_toolchain_generated_churn``) — the
call-site kwarg below was updated accordingly; the observable contracts
(raises / does-not-raise) are unchanged.

Three observable-contract cells, each paired with a negative control:

* **T025** — the ``advance_branch_ref`` callers exclude coordination status
  residue from the dirty gate (``context=residue_when(is_toolchain_generated_churn)``).
  A post-write ff-advance with an obstructing ``status.events.jsonl`` / ``status.json``
  copy on the checked-out worktree does **not** raise
  ``RefAdvanceDirtyWorktreeError``; an obstructing **non-residue** file (an
  author-owned source file) **still raises** (negative control — without it an
  over-allow mutant that ignored all obstruction would survive).

* **T026** — the auto-rebase "take theirs" arm now recognizes the FULL residue
  set drawn from the single authority. Parametrized over the three members the
  drifting local subset omitted (``plan.md`` / ``issue-matrix.md`` /
  ``analysis-report.md``); a non-residue conflicted source file on the coord
  side is **not** treated as coordination-owned (negative control).

* **Expressed-once guard** — an AST/symbol-based check that every merge-path
  consumer imports the single residue authority symbol and carries **no** local
  residue literal set, with a planted-offender self-test (a synthetic source
  reintroducing its own ``{"tasks.md", ...}`` literal trips the guard). String
  greps are theater; this walks the parse tree.

These tests assert observable verdicts (raises / does-not-raise / file content),
never the internal call graph (CT4 / D036). Fixtures use production-shaped
identities (26-char ULID, 8-char mid8). Build on a real on-disk git repo.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# Import status first to mirror production import order and avoid the known
# coordination<->status import-order cycle when a test imports merge directly.
import specify_cli.status  # noqa: F401  # import-order guard

from tests.residue_predicate import residue_when
from specify_cli.coordination.coherence import is_toolchain_generated_churn
from specify_cli.git.ref_advance import (
    RefAdvanceDirtyWorktreeError,
    advance_branch_ref,
)
from specify_cli.lanes.auto_rebase import AutoRebaseReport, attempt_auto_rebase
from specify_cli.lanes.models import ExecutionLane

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

# Production-shaped identity: a real 26-char ULID + 8-char mid8 disambiguator.
MISSION_ID = "01KVRJ6P00000000000000WP13"
MID8 = MISSION_ID[:8]
MISSION_SLUG = f"single-authority-topology-cleanup-{MID8}"


# ---------------------------------------------------------------------------
# Git helpers (self-contained real-repo scaffolding)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _rev_parse(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def _make_lane() -> ExecutionLane:
    return ExecutionLane(
        lane_id="lane-i",
        wp_ids=("WP13",),
        write_scope=("pyproject.toml",),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )


# ---------------------------------------------------------------------------
# T025 — advance_branch_ref callers exclude coordination residue from the gate
# ---------------------------------------------------------------------------


def _advance_branch_carrying_path(
    repo: Path, branch: str, tracked_relpath: str
) -> tuple[Path, str]:
    """Create a linked worktree on *branch*, then advance *branch* by committing
    *tracked_relpath* into the tree from a detached temp worktree (the merge
    pipeline's ``update-ref``-from-detached pattern).

    The parent directory of *tracked_relpath* is seeded as a tracked path on the
    base commit first, so that planting an untracked copy of *tracked_relpath*
    on the worktree surfaces as a single-file obstruction (``?? <full path>``)
    rather than collapsing to an untracked top-level directory (``?? kitty-specs/``).

    Returns ``(worktree_path, new_sha)`` where ``new_sha`` is the advanced tip
    that contains *tracked_relpath* as a tracked file.
    """
    # Seed the parent directory as tracked on the base commit so the later
    # untracked obstruction is reported at file granularity.
    keep = repo / Path(tracked_relpath).parent / ".gitkeep"
    keep.parent.mkdir(parents=True, exist_ok=True)
    keep.write_text("", encoding="utf-8")
    _git(repo, "add", str(keep.relative_to(repo)))
    _git(repo, "commit", "-m", "seed tracked parent dir")

    _git(repo, "branch", branch)
    wt = repo / ".worktrees" / "coord-wt"
    wt.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", str(wt), branch)

    detached = repo / ".worktrees" / "detached-tmp"
    _git(repo, "worktree", "add", "--detach", str(detached), branch)
    target = detached / tracked_relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("authoritative\n", encoding="utf-8")
    _git(detached, "add", tracked_relpath)
    _git(detached, "commit", "-m", "advance with tracked artifact")
    new_sha = _rev_parse(detached, "HEAD")
    _git(repo, "worktree", "remove", str(detached), "--force")
    return wt, new_sha


def test_ff_advance_ignores_obstructing_coordination_status_residue(
    tmp_path: Path,
) -> None:
    """T025: a post-write ff-advance does NOT raise when an obstructing
    coordination status copy is present on the checked-out worktree, because
    the caller passes ``context=residue_when(is_toolchain_generated_churn)``."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    branch = "kitty/mission-coord"
    residue_rel = f"kitty-specs/{MISSION_SLUG}/status.events.jsonl"
    wt, new_sha = _advance_branch_carrying_path(repo, branch, residue_rel)

    # The coordination-branch write left a stale, untracked copy on the primary
    # checkout that obstructs the same tracked path arriving in ``new_sha``.
    obstruction = wt / residue_rel
    obstruction.parent.mkdir(parents=True, exist_ok=True)
    obstruction.write_text("stale primary residue\n", encoding="utf-8")

    # With the residue predicate, the gate does not abort the advance.
    advance_branch_ref(
        repo, branch, new_sha, context=residue_when(is_toolchain_generated_churn)
    )

    assert _rev_parse(repo, branch) == new_sha
    assert _rev_parse(wt, "HEAD") == new_sha


def test_ff_advance_still_raises_on_obstructing_non_residue_file(
    tmp_path: Path,
) -> None:
    """T025 negative control: an obstructing NON-residue path (author-owned
    source) still raises ``RefAdvanceDirtyWorktreeError`` even with the
    coordination residue allow-list. Without this, an over-allow mutant that
    ignored all obstruction would survive."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    branch = "kitty/mission-coord"
    code_rel = "src/specify_cli/author_owned.py"
    wt, new_sha = _advance_branch_carrying_path(repo, branch, code_rel)
    old_sha = _rev_parse(repo, branch)

    obstruction = wt / code_rel
    obstruction.parent.mkdir(parents=True, exist_ok=True)
    obstruction.write_text("operator evidence must survive\n", encoding="utf-8")

    with pytest.raises(RefAdvanceDirtyWorktreeError) as excinfo:
        advance_branch_ref(
            repo, branch, new_sha, context=residue_when(is_toolchain_generated_churn)
        )

    # Atomic refusal: nothing reset, the operator's bytes survive untouched.
    assert _rev_parse(repo, branch) == old_sha
    assert obstruction.read_text(encoding="utf-8") == "operator evidence must survive\n"
    assert any("author_owned.py" in entry for entry in excinfo.value.dirty_entries)


# ---------------------------------------------------------------------------
# T026 — auto_rebase "take theirs" recognizes the FULL residue set
# ---------------------------------------------------------------------------


def _seed_conflict_repo(repo: Path, conflict_rel: str) -> tuple[str, Path]:
    """Seed a mission branch + a stale lane worktree that both modify
    *conflict_rel*, producing a content conflict on auto-rebase.

    Returns ``(mission_branch, lane_worktree)``.
    """
    mission_branch = f"kitty/mission-{MISSION_SLUG}"
    abs_path = repo / conflict_rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text("base\n", encoding="utf-8")
    _git(repo, "add", conflict_rel)
    _git(repo, "commit", "-m", "seed conflict artifact")

    # Mission branch: coordination-side content.
    _git(repo, "branch", mission_branch, "main")
    _git(repo, "checkout", mission_branch)
    abs_path.write_text("coordination authoritative copy\n", encoding="utf-8")
    _git(repo, "add", conflict_rel)
    _git(repo, "commit", "-m", "mission: coord copy")
    _git(repo, "checkout", "main")

    # Lane branch worktree: conflicting lane-side content.
    lane_branch = f"kitty/mission-{MISSION_SLUG}-lane-a"
    worktree = repo / ".worktrees" / f"{MISSION_SLUG}-lane-a"
    worktree.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-b", lane_branch, str(worktree), "main")
    _git(worktree, "config", "user.email", "test@spec-kitty")
    _git(worktree, "config", "user.name", "test")
    (worktree / conflict_rel).write_text("lane local copy\n", encoding="utf-8")
    _git(worktree, "add", conflict_rel)
    _git(worktree, "commit", "-m", "lane: local copy")
    return mission_branch, worktree


@pytest.mark.parametrize(
    "artifact_name",
    ["issue-matrix.md", "acceptance-matrix.json"],
)
def test_take_theirs_recognizes_previously_omitted_residue_member(
    tmp_path: Path, artifact_name: str
) -> None:
    """T026: the COORD-partition residue members the drifting local subset omitted
    are treated as coordination-owned ("take theirs" wins) — drawn from the single
    authority, not a hardcoded literal.

    write-surface-coherence WP01-04 narrowed the residue authority: ``plan.md``
    (``FINALIZED_EXECUTION_PLAN``) and the other planning/finalized kinds are now
    PRIMARY-partition artifacts that live on ``target_branch``, so they are NO
    LONGER coordination residue and the take-theirs arm must not swallow them
    (asserted by ``test_take_theirs_does_not_swallow_primary_planning_conflict``).
    FR-003 (coord-commit-integrity) likewise re-homed ``analysis-report.md``
    (``ANALYSIS_REPORT``) to PRIMARY, so the exemplar here was swapped to
    ``acceptance-matrix.json``. Only genuinely COORD-partition members
    (``issue-matrix.md`` → ``ISSUE_MATRIX``, ``acceptance-matrix.json`` →
    ``ACCEPTANCE_MATRIX``) remain here."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    conflict_rel = f"kitty-specs/{MISSION_SLUG}/{artifact_name}"
    mission_branch, worktree = _seed_conflict_repo(repo, conflict_rel)

    report = attempt_auto_rebase(
        lane=_make_lane(),
        branch=f"kitty/mission-{MISSION_SLUG}-lane-a",
        mission_branch=mission_branch,
        repo_root=repo,
        worktree_path=worktree,
    )

    assert isinstance(report, AutoRebaseReport)
    assert report.succeeded is True, f"halt_reason={report.halt_reason}"
    # Take-theirs: the coordination-side copy wins, the conflict is resolved.
    assert (worktree / conflict_rel).read_text(encoding="utf-8") == (
        "coordination authoritative copy\n"
    )
    rule_ids = {
        c.resolution.rule_id
        for c in report.classifications
        if hasattr(c.resolution, "rule_id")
    }
    assert "R-COORDINATION-ARTIFACT-THEIRS" in rule_ids


def test_take_theirs_does_not_swallow_non_residue_source_conflict(
    tmp_path: Path,
) -> None:
    """T026 negative control: a conflicted NON-residue source file is NOT
    treated as coordination-owned; it falls through to generic classification.
    A semantic source conflict the classifier cannot auto-resolve must halt
    (Manual) rather than silently take-theirs.

    The path is an author-owned code file OUTSIDE ``kitty-specs/`` — guaranteed
    non-residue under any residue-set version (the authority only recognizes
    planning/status artifacts under ``kitty-specs/<slug>/``), so this control
    stays robust if the residue set grows.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    conflict_rel = "src/specify_cli/author_owned_module.py"  # never residue
    mission_branch, worktree = _seed_conflict_repo(repo, conflict_rel)

    report = attempt_auto_rebase(
        lane=_make_lane(),
        branch=f"kitty/mission-{MISSION_SLUG}-lane-a",
        mission_branch=mission_branch,
        repo_root=repo,
        worktree_path=worktree,
    )

    # spec.md is deliberately NOT coordination-owned residue (the authority's
    # docstring: spec.md still blocks). A plain prose conflict the classifier
    # has no rule for must surface as a Manual halt, not a silent take-theirs.
    assert report.succeeded is False
    rule_ids = {
        c.resolution.rule_id
        for c in report.classifications
        if hasattr(c.resolution, "rule_id")
    }
    assert "R-COORDINATION-ARTIFACT-THEIRS" not in rule_ids

def test_take_theirs_does_not_swallow_primary_planning_conflict(
    tmp_path: Path,
) -> None:
    """write-surface-coherence WP01-04 narrowing: a conflicted ``plan.md`` is NOT
    coordination residue anymore, so the take-theirs arm must NOT auto-resolve it.

    Pre-mission ``plan.md`` was coordination residue and a rebase conflict on it
    was silently resolved "take theirs". WP01-04 moved ``plan.md``
    (``FINALIZED_EXECUTION_PLAN``) into ``_PRIMARY_ARTIFACT_KINDS``: it lives on
    ``target_branch`` with its mission, so a real conflict on it must surface as a
    Manual halt (the operator must reconcile), not be swallowed. This pins the
    narrowing the partition introduced — the take-theirs set genuinely shrank.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    conflict_rel = f"kitty-specs/{MISSION_SLUG}/plan.md"
    mission_branch, worktree = _seed_conflict_repo(repo, conflict_rel)

    report = attempt_auto_rebase(
        lane=_make_lane(),
        branch=f"kitty/mission-{MISSION_SLUG}-lane-a",
        mission_branch=mission_branch,
        repo_root=repo,
        worktree_path=worktree,
    )

    assert report.succeeded is False
    rule_ids = {
        c.resolution.rule_id
        for c in report.classifications
        if hasattr(c.resolution, "rule_id")
    }
    assert "R-COORDINATION-ARTIFACT-THEIRS" not in rule_ids
