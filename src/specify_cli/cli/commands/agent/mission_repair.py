"""``agent mission repair`` — Gap-2 cure for pre-existing cross-partition content
split-brain (WP08, coord-write-placement-closure-01KYCF83, FR-005/NFR-005).

**Distinct from BOTH existing repair surfaces** (adjudicated in
``kitty-specs/coord-write-placement-closure-01KYCF83/tracers/design-decisions.md``,
T037):

* ``doctor coordination --fix`` (Gap-1, ``_coordination_doctor.py``) stays
  MINIMIZED (C-002/C-003) to ONE direction (coord branch behind
  ``target_branch``) and operates repo-wide across every mission in one pass.
  This command is per-mission, bidirectional (either partition may be the
  stale one), and scopes its diff to the mission's own content.
* ``doctor mission-state --fix`` -> ``repair_repo`` (``_mission_state_doctor.py``,
  ``migration/mission_state.py:518``) canonicalizes historical JSON *shape*
  (ids, schema drift) within a SINGLE checkout/root. It never compares two
  branches' copies of the same mission's bookkeeping content, so it cannot
  express a cross-partition cure at all.

**Reuse, not reimplementation (per WP08 T039)**: the ancestor/fast-forward
classification reuses ``_coordination_doctor``'s ``_is_ff_candidate`` (via
``_fast_forward_finding``), ``_rev_parse``, ``_coordination_identity``,
``_coord_vs_target_shas``, and ``_resolve_coord_short`` verbatim — this module
adds ONLY the bidirectional state classification, the mission-scoped diff, and
the worktree-agnostic forward action.

**State machine (data-model.md "Repair operation")**: ``clean`` (SHAs equal) ->
no-op; ``ff-candidate`` (one partition's tip is a STRICT ancestor of the
other's, and the behind side's worktree is clean) -> forward (fast-forward,
zero data loss); ``divergent`` (neither is an ancestor) -> refuse, emit a
unified diff scoped to the mission's own directory, exit non-zero, mutate
NOTHING (NFR-005).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer

from kernel.git import GitCommandError, status_entries

from specify_cli.cli.commands._coordination_doctor import (
    _coord_vs_target_shas,
    _fast_forward_finding,
    _is_ff_candidate,
)
from specify_cli.cli.console import console
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import locate_project_root
from specify_cli.mission_metadata import load_meta

#: Sentinel error codes for the two FF directions, mirroring the naming
#: convention `_coordination_doctor.py` uses for its own staleness findings —
#: kept local (not exported) since this module owns its own repair vocabulary.
_COORD_BEHIND_CODE = "REPAIR_COORD_BEHIND_PRIMARY"
_PRIMARY_BEHIND_CODE = "REPAIR_PRIMARY_BEHIND_COORD"


def _mission_dir(repo_root: Path, mission: str) -> Path:
    # Explicit ``Path`` annotation: under the project's ``follow_imports = "skip"``
    # mypy config the cross-module ``KITTY_SPECS_DIR`` constant is seen as ``Any``
    # when this file is type-checked in isolation; the annotation re-narrows the
    # join back to ``Path`` (it IS a ``str``) rather than suppressing the check —
    # matching the sibling ``mission_feature_resolution.py`` pattern.
    mission_dir: Path = repo_root / KITTY_SPECS_DIR / mission
    return mission_dir


def _classify_repair_state(
    repo_root: Path, coord_branch: str, target_branch: str, coord_sha: str, target_sha: str,
) -> tuple[str, str | None, str | None, str | None, str | None]:
    """Classify the repair state and, for ``ff_candidate``, the direction to forward.

    Returns ``(state, behind_branch, ahead_branch, behind_sha, ahead_sha)``.
    ``state`` is one of ``"clean"``, ``"ff_candidate"``, or ``"divergent"``;
    the remaining fields are ``None`` unless ``state == "ff_candidate"``.

    Reuses :func:`_fast_forward_finding` (which itself reuses
    ``_is_ff_candidate``) in BOTH directions rather than reimplementing the
    ancestor check — a non-``None`` result in exactly one direction is what
    distinguishes ``ff_candidate`` from ``divergent`` (both directions
    returning ``None`` while the SHAs differ IS the divergent case).
    """
    if coord_sha == target_sha:
        return "clean", None, None, None, None

    coord_behind = _fast_forward_finding(
        subject_sha=coord_sha, tip_sha=target_sha, repo_root=repo_root,
        message=(
            f"Coordination partition {coord_branch!r} is behind primary "
            f"partition {target_branch!r}."
        ),
        next_step="", error_code=_COORD_BEHIND_CODE,
    )
    if coord_behind is not None:
        return "ff_candidate", coord_branch, target_branch, coord_sha, target_sha

    primary_behind = _fast_forward_finding(
        subject_sha=target_sha, tip_sha=coord_sha, repo_root=repo_root,
        message=(
            f"Primary partition {target_branch!r} is behind coordination "
            f"partition {coord_branch!r}."
        ),
        next_step="", error_code=_PRIMARY_BEHIND_CODE,
    )
    if primary_behind is not None:
        return "ff_candidate", target_branch, coord_branch, target_sha, coord_sha

    return "divergent", None, None, None, None


def _worktree_for_branch(repo_root: Path, branch: str) -> Path | None:
    """Return an existing worktree currently checked out to *branch*, or ``None``.

    Scans ``git worktree list --porcelain`` (the repo_root checkout itself is
    always one entry) so the forward can be applied wherever the branch
    actually lives, without assuming a dedicated worktree exists for it — a
    plain coordination branch has its own ``.worktrees/<slug>-coord`` entry,
    while ``target_branch`` is commonly just the repo_root's own checkout.
    """
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
            text=True, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    current_path: Path | None = None
    expected_ref = f"refs/heads/{branch}"
    for line in out.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree ").strip())
        elif (
            line.startswith("branch ")
            and current_path is not None
            and line.removeprefix("branch ").strip() == expected_ref
        ):
            return current_path
    return None


def _is_worktree_dirty(worktree: Path) -> bool:
    try:
        return bool(status_entries(worktree, untracked=None))
    except GitCommandError:
        return True  # unreadable -> treat as unsafe (C-005 warn-first)


def _forward_ref(
    repo_root: Path, *, behind_branch: str, ahead_branch: str, behind_sha: str, ahead_sha: str,
) -> tuple[bool, str]:
    """Attempt to fast-forward *behind_branch* onto *ahead_branch*.

    Returns ``(forwarded, reason)``. Mutates nothing when it returns
    ``(False, ...)`` (NFR-005): every precondition — a fresh
    :func:`_is_ff_candidate` re-check (TOCTOU guard: the branches may have
    moved between classification and this call), a worktree existing for the
    behind branch, and that worktree being clean — is checked BEFORE any git
    write.
    """
    if not _is_ff_candidate(repo_root, behind_sha, ahead_sha):
        return False, (
            f"{behind_branch!r} is no longer a strict ancestor of {ahead_branch!r} "
            "(it moved between classification and repair)"
        )
    worktree = _worktree_for_branch(repo_root, behind_branch)
    if worktree is None:
        return False, (
            f"no worktree is checked out to {behind_branch!r}; cannot safely "
            "fast-forward it without one"
        )
    if _is_worktree_dirty(worktree):
        return False, f"the worktree for {behind_branch!r} ({worktree}) has uncommitted changes"

    subprocess.run(
        ["git", "-C", str(worktree), "merge", "--ff-only", ahead_branch],
        check=True, capture_output=True, text=True,
    )
    return True, ""


def _mission_diff(repo_root: Path, mission: str, ref_a: str, ref_b: str) -> str:
    """Return ``git diff ref_a ref_b`` scoped to this mission's own directory.

    Scoping to ``kitty-specs/<mission>/`` (rather than the whole-branch diff
    ``_coordination_doctor._unified_diff`` prints for Gap-1) is the
    "content"-specificity NFR-005 calls for: the two branches may carry
    unrelated commits outside this mission entirely, and a repair operator
    should see only the diverged bookkeeping content, not repo-wide noise.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "diff", ref_a, ref_b, "--",
             f"{KITTY_SPECS_DIR}/{mission}/"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return ""
    return result.stdout


def _report_clean(mission: str, coord_branch: str, target_branch: str, sha: str) -> None:
    console.print(
        f"[green]Clean:[/green] mission {mission!r}'s coordination partition "
        f"({coord_branch!r}) and primary partition ({target_branch!r}) already "
        f"match ({sha[:8]}). Nothing to repair."
    )


def _report_divergent(repo_root: Path, mission: str, coord_branch: str, target_branch: str,
                       coord_sha: str, target_sha: str) -> None:
    console.print(
        f"[red]Refusing to repair:[/red] mission {mission!r}'s coordination "
        f"partition ({coord_branch!r}, {coord_sha[:8]}) and primary partition "
        f"({target_branch!r}, {target_sha[:8]}) have diverged (neither is an "
        "ancestor of the other) — repair mutates nothing. Reconcile manually "
        "using the diff below."
    )
    diff_text = _mission_diff(repo_root, mission, coord_sha, target_sha)
    if diff_text:
        console.print(diff_text)
    else:
        console.print(
            "(no content diff detected under this mission's own directory — "
            "the divergence lies elsewhere in the two branches' history)"
        )
    raise typer.Exit(1)


def _apply_forward(
    mission: str, repo_root: Path, behind_branch: str, ahead_branch: str,
    behind_sha: str, ahead_sha: str,
) -> None:
    forwarded, reason = _forward_ref(
        repo_root, behind_branch=behind_branch, ahead_branch=ahead_branch,
        behind_sha=behind_sha, ahead_sha=ahead_sha,
    )
    if not forwarded:
        console.print(
            f"[red]Refusing to repair:[/red] mission {mission!r} is a "
            f"fast-forward candidate ({behind_branch!r} -> {ahead_branch!r}) but "
            f"the forward is not safe right now: {reason}. Repair mutates nothing."
        )
        raise typer.Exit(1)
    console.print(
        f"[green]Repaired:[/green] fast-forwarded {behind_branch!r} onto "
        f"{ahead_branch!r} for mission {mission!r} (zero data loss)."
    )


def run_mission_repair(mission: str) -> None:
    """Entry point for ``agent mission repair --mission <handle>``.

    Exits 0 on ``clean`` (nothing to do), on a mission with no coordination
    partition (legacy/non-coordinated — no cross-partition content to
    reconcile), and on a successful forward. Exits 1 on ``divergent`` (with a
    diff) and on an ``ff_candidate`` whose forward precondition is unsafe
    (dirty or missing worktree) — either way, NOTHING is ever mutated on a
    non-zero exit (NFR-005).
    """
    try:
        repo_root = locate_project_root()
    except Exception as exc:
        console.print("[red]Error:[/red] Not in a spec-kitty project")
        raise typer.Exit(1) from exc
    if repo_root is None:
        console.print("[red]Error:[/red] Not in a spec-kitty project")
        raise typer.Exit(1)

    mission_dir = _mission_dir(repo_root, mission)
    meta = load_meta(mission_dir, on_malformed="none")
    if meta is None:
        if not mission_dir.exists():
            console.print(f"[red]Error:[/red] Mission not found: {mission!r}")
        else:
            console.print(
                f"[red]Error:[/red] Could not read meta.json for mission "
                f"{mission!r} (missing or malformed)."
            )
        raise typer.Exit(1)

    shas = _coord_vs_target_shas(repo_root, meta)
    if shas is None:
        console.print(
            f"[green]Nothing to repair:[/green] mission {mission!r} has no "
            "coordination partition (or incomplete branch identity) — there is "
            "no cross-partition content to reconcile."
        )
        return

    coord_branch, target_branch, coord_sha, target_sha = shas
    state, behind_branch, ahead_branch, behind_sha, ahead_sha = _classify_repair_state(
        repo_root, coord_branch, target_branch, coord_sha, target_sha,
    )

    if state == "clean":
        _report_clean(mission, coord_branch, target_branch, coord_sha)
        return
    if state == "divergent":
        _report_divergent(repo_root, mission, coord_branch, target_branch, coord_sha, target_sha)
        return  # pragma: no cover - _report_divergent always raises typer.Exit

    # ff_candidate invariant: every field below is non-None together.
    assert behind_branch is not None and ahead_branch is not None
    assert behind_sha is not None and ahead_sha is not None
    _apply_forward(mission, repo_root, behind_branch, ahead_branch, behind_sha, ahead_sha)


def repair(
    mission: Annotated[str, typer.Option("--mission", help="Mission slug/handle to repair")],
) -> None:
    """Detect and forward-only repair a pre-existing cross-partition content
    split-brain for one mission (FR-005, NFR-005).

    Fast-forwards under strict-ancestor + clean worktree, zero data loss.
    Refuses with a unified diff (scoped to the mission's own content) and
    mutates NOTHING on genuine (non-ancestor) divergence.

    Examples:
        spec-kitty agent mission repair --mission 020-my-mission
    """
    run_mission_repair(mission)
