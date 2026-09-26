"""Scope: #2709 -- squash merge clobbers target-newer provenance.

Formerly a red-first ``@pytest.mark.regression`` reproduction (WP01 of
``merge-squash-provenance-and-rollback-coherence-01KXRRB7``, a TEST-ONLY
red-first ATDD reproduction, FR-001, US1-S1, US2-S1, SC-001); relocated here
and un-marked (landing fold: make ``@pytest.mark.regression`` mean exactly
one thing) once the fix landed and these tests started passing. #2709 is
fixed — this module is now a permanent guard, not a red-first pin.

It witnesses that the supported squash merge -- the real
``_run_lane_based_merge`` with strategy ``SQUASH`` (which runs ``git merge
--squash -X theirs <mission_branch>`` in ``lanes/merge.py::_merge_branch_into``)
-- used to overwrite target-newer ``meta.json`` acceptance/VCS provenance and
``traces/*.md`` sections with the older mission/coord-branch copy.

``meta.json`` has **no** registered merge driver, so ``-X theirs`` steers git's
built-in text driver to favor the mission/coord branch on every conflicting
hunk; target-side acceptance provenance is reverted to the older value.

RED-for-the-right-reason (SC-001): ``meta.json`` is modified on **both** the
coord branch (acceptance v1 @ T1) **and** the target branch ``main``
(acceptance v2 @ T2) vs the merge-base, so ``-X theirs`` genuinely fires
(without both-sides divergence git trivially keeps target and the test would be
green-on-base, proving nothing). The **first** failing assertion is a
provenance field (``accepted_at == T2``), not a fixture/setup error.

The real-git coord harness in
``tests/specify_cli/cli/commands/test_merge_coord_topology_1772.py`` is imported
**read-only**; the per-branch acceptance helpers below are local to this module
because WP02 also consumes that harness file (no in-place edits).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Import the status package before any coordination submodule -- mirrors the
# production import order and the 1772 harness's documented import-order guard.
import specify_cli.status  # noqa: F401  # import-order guard (see 1772 harness)
from specify_cli import mission_metadata
from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.merge.config import MergeStrategy

from tests.specify_cli.cli.commands.test_merge_coord_topology_1772 import (
    COORD_BRANCH,
    MISSION_SLUG,
    _bootstrap_coord_mission,
    _git,
    _init_git_repo,
    _materialize_coord_worktree,
    _real_merge_external_mocks,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.git_repo,
    pytest.mark.non_sandbox,
]

# Deterministic, strictly ordered acceptance timestamps: T1 (coord/older) < T2
# (target/newer). Monkeypatched into ``mission_metadata._now_iso`` per branch so
# ``record_acceptance`` stamps a known, divergent ``accepted_at``.
T1_COORD = "2026-01-01T00:00:00+00:00"
T2_TARGET = "2026-06-01T00:00:00+00:00"

TRACE_RELPATH = f"kitty-specs/{MISSION_SLUG}/traces/mission-trace.md"
TARGET_TRACE_MARKER = "section:target-newer"


def _make_meta_valid(feature_dir: Path) -> None:
    """Fill the required ``meta.json`` fields the 1772 fixture omits.

    The shared harness ``_write_meta`` writes a coord-topology ``meta.json`` that
    lacks ``slug``/``friendly_name``/``created_at`` (not needed by the 1772
    tests). ``record_acceptance``/``set_vcs_lock`` write through
    ``write_meta(validate=True)``, so the on-disk meta must be valid first. The
    same values are written on both branches so these keys do NOT contribute to
    the divergence -- only the acceptance/VCS fields diverge.
    """
    meta = mission_metadata.load_meta(feature_dir) or {}
    meta.setdefault("slug", MISSION_SLUG)
    meta.setdefault("friendly_name", "Coord Topology 1772")
    meta.setdefault("created_at", "2025-12-01T00:00:00+00:00")
    mission_metadata.write_meta(feature_dir, meta, validate=False)


def _seed_branch_provenance(
    repo: Path,
    feature_dir: Path,
    branch: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    now: str,
    accepted_by: str,
    mode: str,
    from_commit: str,
    accept_commit: str,
    vcs: str,
    trace_body: str,
) -> None:
    """Check out *branch* and record a full, divergent acceptance/VCS provenance.

    Records acceptance (via the canonical ``record_acceptance``), a VCS lock (via
    ``set_vcs_lock``), and a ``traces/*.md`` section, then commits them on
    *branch*. Called once per branch (coord = older @ T1, ``main`` = newer @ T2)
    so ``meta.json`` and the trace file diverge on both sides vs the merge-base.
    """
    _git(repo, "checkout", branch)
    _make_meta_valid(feature_dir)

    # Deterministic accepted_at / history timestamp for this branch.
    monkeypatch.setattr(mission_metadata, "_now_iso", lambda: now)
    mission_metadata.record_acceptance(
        feature_dir,
        accepted_by=accepted_by,
        mode=mode,
        from_commit=from_commit,
        accept_commit=accept_commit,
    )
    mission_metadata.set_vcs_lock(feature_dir, vcs_type=vcs, locked_at=now)

    traces_dir = feature_dir / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    (traces_dir / "mission-trace.md").write_text(trace_body, encoding="utf-8")

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({MISSION_SLUG}): provenance on {branch}")


def test_squash_merge_preserves_target_newer_meta_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#2709 / FR-001 / US1-S1 / US2-S1: the supported squash merge must NOT
    clobber target-newer ``meta.json`` acceptance/VCS provenance with the older
    coord-branch copy.

    Was RED before the fix: ``git merge --squash -X theirs`` reverted the
    target-newer acceptance/VCS fields to the coord branch's older values
    because ``meta.json`` carries no merge driver. #2709's field-level
    reconciler now preserves target-authoritative provenance, and this test
    is a permanent guard against the defect recurring.
    """
    _init_git_repo(tmp_path)
    feature_dir = _bootstrap_coord_mission(tmp_path)

    # Coord/mission branch: OLDER acceptance (v1 @ T1).
    _seed_branch_provenance(
        tmp_path,
        feature_dir,
        COORD_BRANCH,
        monkeypatch,
        now=T1_COORD,
        accepted_by="reviewer-coord-v1",
        mode="manual",
        from_commit="coordfromcommit1",
        accept_commit="coordacceptcommit1",
        vcs="svn",
        trace_body=(
            "# Mission Trace\n\n"
            "<!-- section:coord-older -->\n"
            "## Coord section (mission-branch, older)\n"
            "coord trace body @ T1\n"
        ),
    )

    # Target branch (``main``): NEWER accepted state (v2 @ T2).
    _seed_branch_provenance(
        tmp_path,
        feature_dir,
        "main",
        monkeypatch,
        now=T2_TARGET,
        accepted_by="reviewer-target-v2",
        mode="automatic",
        from_commit="targetfromcommit2",
        accept_commit="targetacceptcommit2",
        vcs="git",
        trace_body=(
            "# Mission Trace\n\n"
            f"<!-- {TARGET_TRACE_MARKER} -->\n"
            "## Target section (target-newer, target-only)\n"
            "target trace body @ T2\n"
        ),
    )

    # Preconditions (fixture health, asserted BEFORE the merge so a fixture
    # break surfaces as a precondition failure, never as a false contract RED).
    base_main_meta = json.loads(
        _git(tmp_path, "show", f"main:kitty-specs/{MISSION_SLUG}/meta.json").stdout
    )
    assert base_main_meta.get("accepted_at") == T2_TARGET, (
        "fixture precondition: target `main` must hold the NEWER acceptance "
        "(v2 @ T2) before the merge"
    )
    base_coord_meta = json.loads(
        _git(
            tmp_path, "show", f"{COORD_BRANCH}:kitty-specs/{MISSION_SLUG}/meta.json"
        ).stdout
    )
    assert base_coord_meta.get("accepted_at") == T1_COORD, (
        "fixture precondition: the coord branch must hold the OLDER acceptance "
        "(v1 @ T1) so `-X theirs` genuinely diverges from target"
    )

    # Run the supported squash merge through the real entry point.
    _git(tmp_path, "checkout", "main")
    # Materialize the coord worktree NOW (post-#4959 the STATUS_STATE read
    # needs it) — every direct COORD_BRANCH checkout in the main worktree
    # (the two `_seed_branch_provenance` calls above) is done, and the main
    # worktree is on `main`, not `COORD_BRANCH`, so the worktree add below
    # will not collide with an existing checkout.
    _materialize_coord_worktree(tmp_path)
    with _real_merge_external_mocks():
        _run_lane_based_merge(
            repo_root=tmp_path,
            mission_slug=MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )

    merged_meta = json.loads(
        _git(tmp_path, "show", f"main:kitty-specs/{MISSION_SLUG}/meta.json").stdout
    )

    # --- Contract assertions (RED on the mission base). The FIRST assertion is a
    #     provenance field, satisfying SC-001 (RED for the right reason). ---
    assert merged_meta.get("accepted_at") == T2_TARGET, (
        "#2709 regression: squash merge clobbered target-newer `accepted_at` "
        f"with the coord-branch value. Expected {T2_TARGET!r} (target v2), got "
        f"{merged_meta.get('accepted_at')!r} (coord v1). meta={merged_meta!r}"
    )
    assert merged_meta.get("accepted_by") == "reviewer-target-v2", (
        "#2709 regression: target-newer `accepted_by` was clobbered by the "
        f"coord copy. got={merged_meta.get('accepted_by')!r}"
    )
    assert merged_meta.get("accepted_from_commit") == "targetfromcommit2", (
        "#2709 regression: target-newer `accepted_from_commit` was clobbered. "
        f"got={merged_meta.get('accepted_from_commit')!r}"
    )
    assert merged_meta.get("acceptance_mode") == "automatic", (
        "#2709 regression: target-newer `acceptance_mode` was clobbered. "
        f"got={merged_meta.get('acceptance_mode')!r}"
    )
    assert merged_meta.get("accept_commit") == "targetacceptcommit2", (
        "#2709 regression: target-newer `accept_commit` was clobbered. "
        f"got={merged_meta.get('accept_commit')!r}"
    )
    assert len(merged_meta.get("acceptance_history", [])) == 2, (
        "#2709 regression: `acceptance_history` must union both sides (coord v1 "
        "+ target v2). `-X theirs` kept only the coord copy. "
        f"history={merged_meta.get('acceptance_history')!r}"
    )
    assert merged_meta.get("vcs") == "git", (
        "#2709 regression: target-newer `vcs` was clobbered by the coord copy. "
        f"got={merged_meta.get('vcs')!r}"
    )
    assert merged_meta.get("vcs_locked_at") == T2_TARGET, (
        "#2709 regression: target-newer `vcs_locked_at` was clobbered by the "
        f"coord copy. got={merged_meta.get('vcs_locked_at')!r}"
    )


def test_squash_merge_preserves_target_newer_trace_section(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#2709 / US2-S2: the squash merge must NOT drop a target-newer
    ``traces/*.md`` section.

    Was RED before the fix: append-only ``traces/*.md`` has no merge driver
    and no dedup key, so ``-X theirs`` took the coord copy and the
    target-newer section was dropped. #2709's markdown-union contract now
    preserves both sides' sections, and this test is a permanent guard
    against the defect recurring.
    """
    _init_git_repo(tmp_path)
    feature_dir = _bootstrap_coord_mission(tmp_path)

    _seed_branch_provenance(
        tmp_path,
        feature_dir,
        COORD_BRANCH,
        monkeypatch,
        now=T1_COORD,
        accepted_by="reviewer-coord-v1",
        mode="manual",
        from_commit="coordfromcommit1",
        accept_commit="coordacceptcommit1",
        vcs="svn",
        trace_body=(
            "# Mission Trace\n\n"
            "<!-- section:coord-older -->\n"
            "## Coord section (mission-branch, older)\n"
            "coord trace body @ T1\n"
        ),
    )
    _seed_branch_provenance(
        tmp_path,
        feature_dir,
        "main",
        monkeypatch,
        now=T2_TARGET,
        accepted_by="reviewer-target-v2",
        mode="automatic",
        from_commit="targetfromcommit2",
        accept_commit="targetacceptcommit2",
        vcs="git",
        trace_body=(
            "# Mission Trace\n\n"
            f"<!-- {TARGET_TRACE_MARKER} -->\n"
            "## Target section (target-newer, target-only)\n"
            "target trace body @ T2\n"
        ),
    )

    # Precondition: the target-newer trace section is on `main` before the merge.
    base_trace = _git(tmp_path, "show", f"main:{TRACE_RELPATH}").stdout
    assert TARGET_TRACE_MARKER in base_trace, (
        "fixture precondition: the target-newer trace section must be on `main` "
        "before the merge"
    )

    _git(tmp_path, "checkout", "main")
    # Materialize the coord worktree NOW (post-#4959 the STATUS_STATE read
    # needs it) — every direct COORD_BRANCH checkout in the main worktree
    # (the two `_seed_branch_provenance` calls above) is done, and the main
    # worktree is on `main`, not `COORD_BRANCH`, so the worktree add below
    # will not collide with an existing checkout.
    _materialize_coord_worktree(tmp_path)
    with _real_merge_external_mocks():
        _run_lane_based_merge(
            repo_root=tmp_path,
            mission_slug=MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )

    merged_trace = _git(tmp_path, "show", f"main:{TRACE_RELPATH}").stdout
    assert TARGET_TRACE_MARKER in merged_trace, (
        "#2709 regression: squash merge dropped the target-newer `traces/*.md` "
        "section -- `-X theirs` took the coord copy over the target-only "
        f"section. merged trace:\n{merged_trace}"
    )
