"""Issue #4474 (distinct from #4764): topology-aware mission_number bake (FR-011).

Defect
-------
``_write_mission_number_to_branch`` (``src/specify_cli/merge/ordering.py``)
composes the ``meta.json`` path *inside the detached mission-branch worktree*
(``compose_meta_json_path(mission_tmp_path, mission_slug)``). On a coord-topology
mission (the "083+ layout", where ``lanes_manifest.mission_branch ==
coordination_branch`` — see ``consolidation/executor.py``'s
``_CoordCheckpoint`` docstring), that coordination branch
carries only lifecycle surfaces (status/notes/trace) — the mission's
``meta.json`` is a PRIMARY-partition artifact that instead lives on the
PRIMARY checkout (``main_repo``'s own on-disk working tree; see
``mission_runtime.resolution.read_dir_for``'s "repo_root: Absolute repository
root (primary checkout)"). Pre-fix, when the coordination-branch worktree
lacks ``meta.json`` the write FAIL-OPENS: it logs a warning and
``return False`` — the number is silently lost forever and ``doctor``
(``needs_number_assignment``) stays stuck reporting the mission as pending.

This is the OPPOSITE failure mode from #4764 (WP02), which refuses baking a
mission that is NOT yet merge-ready. #4474 is a genuinely merge-ready mission
LOSING its number.

Fix (FR-011)
------------
The write-back becomes topology-aware: when the coordination-branch worktree
lacks ``meta.json``, fall back to composing the SAME path directly against
``main_repo`` (the primary checkout) and, if that copy exists, persist the
number there (write + narrow ``git add``/``git commit`` directly on
``main_repo`` — never inside ``.worktrees/``, preserving the pre-existing
``path_is_under_worktrees`` guard). Only when the primary tree is ALSO
unreachable does the function surface the unbaked field (merge-summary line +
elevated logger) instead of a silent ``return False``.

Two cases (FOLD 4 — surfacing-only is INSUFFICIENT when the primary tree is
reachable):

1. ``test_coord_topology_bake_persists_to_primary_tree_when_reachable`` —
   PREFERRED-outcome case: the mission-branch (coordination) worktree lacks
   ``meta.json``, but ``main_repo``'s own checkout HAS it. Asserts the number
   is PERSISTED to the primary-tree ``meta.json`` and the
   ``needs_number_assignment`` doctor-proxy predicate flips
   ``True`` (pending) -> ``False`` (assigned).

2. ``test_unreachable_primary_returns_decided_number_unbaked_and_surfaces_it``
   — separately constructed: NEITHER the mission-branch worktree NOR
   ``main_repo``'s own checkout carries ``meta.json`` for this mission.
   Asserts the seam returns the decided number (never discards it),
   leaves ``mission_number_baked`` False, AND that a merge-summary line is
   printed (never a silent skip). The refusal half of the #4900 contract
   (the executor refusing rather than fabricating a null on the target) is
   covered separately by
   ``test_mission_number_truthful_4900.py::test_absent_target_meta_refuses_instead_of_fabricating``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.git_repo, pytest.mark.non_sandbox]


# ---------------------------------------------------------------------------
# Minimal real-git-repo fixture helpers (mirrors tests/merge/test_mission_number_idempotency.py)
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}:\nstdout: {result.stdout}\nstderr: {result.stderr}")
    return result


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial commit")


def _write_meta_file(feature_dir: Path, *, mission_slug: str, mission_number: int | None, coordination_branch: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "mission_id": "01HXBAKE4474MISSIONIDXXXX",
        "mission_number": mission_number,
        "mission_slug": mission_slug,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": coordination_branch,
        "created_at": "2026-09-19T00:00:00+00:00",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_bake(
    repo: Path,
    mission_slug: str,
    mission_branch: str,
    target_branch: str = "main",
    *,
    merge_state=None,  # noqa: ANN001 — imported lazily below, matches other tests/merge/ modules
):
    from specify_cli.consolidation.ordering import _bake_mission_number_into_mission_branch

    return _bake_mission_number_into_mission_branch(
        main_repo=repo,
        mission_slug=mission_slug,
        mission_branch=mission_branch,
        target_branch=target_branch,
        dry_run=False,
        merge_state=merge_state,
    )


# ---------------------------------------------------------------------------
# Case 1 (PREFERRED, mandatory persist): coordination branch lacks meta.json,
# but main_repo's own checkout (the primary tree) has it.
# ---------------------------------------------------------------------------


def test_coord_topology_bake_persists_to_primary_tree_when_reachable(tmp_path: Path) -> None:
    """#4474 / FR-011: the merge-ready coord-topology bake must PERSIST, not
    just surface, the number when the primary tree is reachable."""
    from specify_cli.consolidation.state import ConsolidationState, needs_number_assignment

    repo = tmp_path / "repo"
    _init_repo(repo)

    mission_slug = "coord-bake-4474"
    coord_branch = f"kitty/mission-{mission_slug}"

    # meta.json exists ONLY on main_repo's own current checkout ("main") —
    # simulating the PRIMARY partition (primary checkout, per
    # mission_runtime.resolution.read_dir_for's "repo_root: Absolute
    # repository root (primary checkout)" contract).
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta_file(feature_dir, mission_slug=mission_slug, mission_number=None, coordination_branch=coord_branch)
    _git(repo, "add", str(feature_dir / "meta.json"))
    _git(repo, "commit", "-m", f"add {mission_slug} meta.json (primary tree)")

    # The coordination/mission branch is created from an EARLIER commit —
    # before meta.json existed — so its tree genuinely lacks kitty-specs/<slug>/
    # (the real #4474 shape: coord = lifecycle surfaces only).
    initial_sha = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True).stdout.strip()
    _git(repo, "branch", coord_branch, initial_sha)

    # Doctor-proxy: pending BEFORE the bake.
    assert needs_number_assignment(feature_dir) is True

    state = ConsolidationState(
        mission_id="01HXBAKE4474MISSIONIDXXXX",
        mission_slug=mission_slug,
        target_branch="main",
        wp_order=["WP01"],
        mission_number_baked=False,
    )

    result = _run_bake(repo, mission_slug, coord_branch, merge_state=state)

    # PREFERRED outcome: the number is genuinely assigned and PERSISTED — not
    # merely surfaced. Surfacing-only would leave meta.json's mission_number
    # at None and needs_number_assignment would still report True.
    assert result == 1, "the coordination bake must return the assigned integer, not None"

    persisted = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert persisted["mission_number"] == 1, "mission_number must be PERSISTED to the primary-tree meta.json"

    # Doctor-proxy: pending -> assigned AFTER the bake.
    assert needs_number_assignment(feature_dir) is False, "doctor-equivalent predicate must flip pending -> assigned"

    # #4900: this write lands directly on target_branch, but the seam
    # itself never marks mission_number_baked -- only the executor does,
    # after ``assert_mission_number_on_target`` verifies it there.
    assert state.mission_number_baked is False


# ---------------------------------------------------------------------------
# Case 2 (fallback, separately constructed): NEITHER tree carries meta.json —
# genuinely unreachable. Must surface, never silently return False.
# ---------------------------------------------------------------------------


def test_unreachable_primary_returns_decided_number_unbaked_and_surfaces_it(tmp_path: Path) -> None:
    """#4474 / FR-011 fallback: when the primary tree is ALSO unreachable, the
    seam's own contract is to RETURN the decided ``mission_number`` (never
    discard it), leave ``mission_number_baked`` False, and print an observable
    merge-summary line -- never a silent skip (``return None``/``False``).

    The refusal half of the #4900 contract -- the executor refusing (``Error:``
    + exit 1) instead of fabricating a ``null`` mission_number when the target
    tree's own ``meta.json`` is absent -- is NOT exercised here; it is covered
    by ``tests/consolidation/test_mission_number_truthful_4900.py::
    test_absent_target_meta_refuses_instead_of_fabricating``.
    """
    from specify_cli.consolidation import ordering
    from specify_cli.consolidation.state import ConsolidationState

    repo = tmp_path / "repo"
    _init_repo(repo)

    mission_slug = "coord-bake-4474-unreachable"
    coord_branch = f"kitty/mission-{mission_slug}"
    other_branch = "operator-was-elsewhere"

    # A DIFFERENT mission's meta.json exists on "main" (the target branch) so
    # `assign_next_mission_number`'s scan has something to walk, but nothing
    # named after `mission_slug` exists ANYWHERE — the target branch itself
    # never carries this mission's meta.json pre-merge (only a successful bake
    # would create it there).
    other_feature_dir = repo / "kitty-specs" / "unrelated-mission"
    _write_meta_file(other_feature_dir, mission_slug="unrelated-mission", mission_number=None, coordination_branch="kitty/mission-unrelated")
    _git(repo, "add", str(other_feature_dir / "meta.json"))
    _git(repo, "commit", "-m", "add unrelated mission meta.json")

    # Coordination branch: lifecycle-only, no kitty-specs/<slug>/ at all.
    _git(repo, "branch", coord_branch)

    # main_repo's OWN checkout is moved to a THIRD branch that also never had
    # this mission's meta.json — the genuinely-unreachable primary tree.
    _git(repo, "checkout", "-b", other_branch)

    state = ConsolidationState(
        mission_id="01HXBAKE4474UNREACHABLEID",
        mission_slug=mission_slug,
        target_branch="main",
        wp_order=["WP01"],
        mission_number_baked=False,
    )

    printed: list[str] = []
    from unittest.mock import patch

    with patch.object(ordering.console, "print", side_effect=lambda *a, **k: printed.append(" ".join(str(x) for x in a))):
        result = ordering._bake_mission_number_into_mission_branch(
            main_repo=repo,
            mission_slug=mission_slug,
            mission_branch=coord_branch,
            target_branch="main",
            dry_run=False,
            merge_state=state,
        )

    # #4900: the decided number is still RETURNED (never discarded),
    # so the executor's unconditional target-tree write + read-back decides
    # the outcome: that write refuses (``Error:`` + exit 1) when the target
    # meta.json is absent, rather than the historical silent ``null`` + exit 0.
    # Nothing was committed on the mission branch or the primary tree here.
    assert result == 1, "the computed mission_number must reach the executor's target-tree write, not be discarded"
    assert state.mission_number_baked is False, "the baked flag must not be set when nothing was actually persisted"

    # The failure must be OBSERVABLE (a merge-summary line), never a silent skip.
    joined = "\n".join(printed)
    assert mission_slug in joined, "the merge-summary surfacing must name the affected mission"
    assert "mission_number" in joined.lower() or "not" in joined.lower() or "unreachable" in joined.lower() or "warning" in joined.lower(), (
        f"expected an observable unbaked-mission_number notice in the merge summary, got: {printed!r}"
    )
