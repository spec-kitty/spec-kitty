"""#4120: lane-worktree merges had the *attribute-mapping* half of the merge
driver activation missing.

``test_worktree_allocator_merge_driver_selfheal.py`` (FIX-M2-01) covered the
git-CONFIG half: a committed ``.gitattributes`` mapping whose matching
``merge.<key>.driver`` git-config entries were never registered. This module
covers the other half of the same gap: a lane worktree whose checked-out tree
carries NO committed ``.gitattributes`` mapping at all.

That is not an exotic state — it is the structural norm for exactly the
mission shape #4120 reported. The lane branch is cut from
``coordination_branch``/``mission_branch``, which is minted BEFORE the
mission's planning commits exist (that is why
``_merge_recorded_planning_commit`` runs at all, FR-009). A project whose
``.gitattributes`` mapping landed with the planning commits — or was never
committed (initialized before the mapping existed) — therefore checks out a
lane base with no mapping, and the add/add divergence this merge is EXPECTED
to produce on the append-only ``status.events.jsonl`` (a lone finalize-tasks
bootstrap event on the lane side against the full specify/plan history on the
planning side, both added after a merge-base that predates the file) falls
back to a plain 3-way merge and conflicts, surfacing a raw git conflict the
operator must splice by hand (#4120's bug 1).

The fix activates the driver attribute mappings ephemerally for exactly these
merges — the same ``_ephemeral_merge_driver_activation`` the squash
mission→target merge uses — so the union drivers fire regardless of what the
branch committed. This module reproduces the divergence against a repo with
NO committed ``.gitattributes`` (asserted as an explicit precondition), drives
the real production entry points, and additionally pins the #2709/#2711
invariant: the seeded ``info/attributes`` activation must NOT outlive the
merge (a persistent seeding would pre-empt a later ``auto_rebase``'s in-process
``R-STATUS-EVENTS-JSONL-UNION`` classifier).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.lanes.branch_naming import code_lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import (
    _merge_dependency_lane_tips,
    allocate_lane_worktree,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_SLUG = "issue-4120-stale-lane-base"
# Crockford-base32 ULID shape (26 chars, no I/L/O/U) -- reuses the known-good
# literal tests/lanes/test_issue_2993_lane_planning_ancestry.py already
# verified resolve_mid8 accepts; only used for isolated tmp_path repos here.
MISSION_ID = "01KYHQ9FTN3W7C5J4K2M6R8QDS"
WP_ID = "WP01"

_EXPECTED_DRIVER_COMMAND = "spec-kitty merge-driver-event-log %O %A %B"
_DRIVER_ATTRIBUTE_LINE = "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    """A fresh repo with NO committed ``.gitattributes`` (#4120's precondition).

    Distinct from ``test_worktree_allocator_merge_driver_selfheal``'s init
    shape (mapping committed, git-config unregistered): here the mapping is
    absent from every branch, so only an EPHEMERAL activation can make the
    union driver fire.
    """
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed (no .gitattributes — pre-mapping project)")


def _assert_no_committed_gitattributes(repo: Path) -> None:
    """Pin the precondition: no branch carries a ``.gitattributes`` mapping."""
    result = subprocess.run(
        ["git", "-C", str(repo), "show", "main:.gitattributes"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, (
        "test setup invariant violated: this module's defect needs a repo "
        "with NO committed .gitattributes, or it cannot distinguish the "
        "ephemeral-activation fix from the committed-mapping path"
    )


def _assert_no_persistent_attribute_activation(repo: Path) -> None:
    """Pin the #2709/#2711 invariant: ``info/attributes`` did not survive.

    The ephemeral activation seeds the driver patterns into
    ``$GIT_COMMON_DIR/info/attributes`` before the merge and must remove
    exactly its own lines afterwards. A persistent seeding would pre-activate
    the git driver for a later ``auto_rebase`` in the same repo and silently
    pre-empt its in-process union classifier.
    """
    common_dir_raw = _git(repo, "rev-parse", "--git-common-dir")
    common_dir = Path(common_dir_raw)
    if not common_dir.is_absolute():
        common_dir = repo / common_dir
    attributes_path = common_dir / "info" / "attributes"
    if not attributes_path.exists():
        return
    lines = attributes_path.read_text(encoding="utf-8").splitlines()
    assert _DRIVER_ATTRIBUTE_LINE not in lines, (
        f"ephemeral merge-driver attribute activation leaked into {attributes_path}: the seeding must be torn down after the merge (#2709/#2711 regression)"
    )


def _write_status_event(feature_dir: Path, *, event_id: str, at: str) -> None:
    """Append one event line to the feature dir's event log (append, not
    overwrite — the planning side accumulates a multi-event history)."""
    events_path = feature_dir / "status.events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"event_id": event_id, "at": at, "kind": "wp_status_transition"}
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _use_this_venvs_spec_kitty_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prepend THIS interpreter's venv bin to PATH for the test process.

    The drivers are invoked bare as ``spec-kitty ...`` per the real
    ``_MERGE_DRIVERS`` registry, so they must resolve to the SAME spec-kitty
    under test rather than any other ``spec-kitty`` a developer machine
    happens to have on PATH — mirrors ``lanes/merge.py::_make_merge_env``'s
    identical concern.
    """
    venv_bin = str(Path(sys.executable).parent)
    monkeypatch.setenv("PATH", venv_bin + os.pathsep + os.environ.get("PATH", ""))


def _make_manifest(coordination_branch: str, *, planning_commit_sha: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        mission_branch=coordination_branch,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=(WP_ID,),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-09T10:00:00Z",
        computed_from="test",
        planning_commit_sha=planning_commit_sha,
    )


class TestPlanningCommitMergeWithoutCommittedAttributes:
    def test_stale_lane_base_add_add_conflict_union_merges(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """#4120 bug 1: stale lane base + no committed mapping → still merges.

        The lane branch is cut from a base that predates the mission's
        planning commits, both sides independently ADD
        ``status.events.jsonl`` after that merge-base (the lone
        finalize-tasks bootstrap event on the lane side, the full
        specify/plan event history on the planning side), and no
        ``.gitattributes`` mapping exists anywhere. Pre-fix this raises
        ``PlanningCommitMergeConflictError``; post-fix the ephemeral driver
        activation makes the union driver reconcile both sides.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        _assert_no_committed_gitattributes(repo)

        coord_branch = f"kitty/mission-{MISSION_SLUG}"
        _git(repo, "branch", coord_branch)

        feature_dir = repo / "kitty-specs" / MISSION_SLUG

        # Coordination branch (the lane's parent) independently ADDS the lone
        # finalize-tasks bootstrap event — the exact lane-side content #4120
        # observed in the wild.
        _git(repo, "checkout", "-q", coord_branch)
        _write_status_event(feature_dir, event_id="evt-finalize-bootstrap", at="2026-09-09T09:00:00Z")
        _git(repo, "add", "kitty-specs")
        _git(repo, "commit", "-q", "-m", "status: finalize-tasks bootstrap")

        # Target/primary branch independently ADDS the SAME path with the
        # full specify/plan event history -- the add/add divergence.
        _git(repo, "checkout", "-q", "main")
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "spec.md").write_text("# Issue 4120\n", encoding="utf-8")
        (feature_dir / "tasks.md").write_text("## WP01\n- [ ] T001\n", encoding="utf-8")
        _write_status_event(feature_dir, event_id="evt-specify", at="2026-09-09T08:00:00Z")
        _write_status_event(feature_dir, event_id="evt-plan", at="2026-09-09T08:30:00Z")
        _git(repo, "add", "kitty-specs")
        _git(repo, "commit", "-q", "-m", "docs: spec+tasks+planning event history")
        planning_commit_sha = _git(repo, "rev-parse", "HEAD")

        manifest = _make_manifest(coord_branch, planning_commit_sha=planning_commit_sha)
        _use_this_venvs_spec_kitty_on_path(monkeypatch)

        # Regression assertion: pre-fix this raises
        # PlanningCommitMergeConflictError on the add/add divergence.
        _worktree_path, lane_branch = allocate_lane_worktree(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            lanes_manifest=manifest,
        )

        # The union driver actually FIRED (not just "no exception"): both
        # sides' events survive in the merged lane branch. Read via git
        # plumbing, not the worktree filesystem, mirroring the selfheal
        # module's read discipline.
        merged_text = _git(repo, "show", f"{lane_branch}:kitty-specs/{MISSION_SLUG}/status.events.jsonl")
        assert "evt-finalize-bootstrap" in merged_text, f"lane-side bootstrap event lost from the merged log: {merged_text!r}"
        assert "evt-specify" in merged_text, f"planning-side event lost from the merged log: {merged_text!r}"
        assert "evt-plan" in merged_text, f"planning-side event lost from the merged log: {merged_text!r}"

        # The driver git-config definitions persist (intended, inert without
        # a mapping) -- same post-condition as the selfheal module.
        assert _git(repo, "config", "--get", "merge.spec-kitty-event-log.driver") == _EXPECTED_DRIVER_COMMAND
        # ... but the info/attributes activation does NOT (#2709/#2711).
        _assert_no_persistent_attribute_activation(repo)


class TestDependencyLaneTipsMergeWithoutCommittedAttributes:
    """Same defect, second call site: ``_merge_dependency_lane_tips``."""

    def test_dependency_tip_merge_union_merges_without_committed_mapping(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        _assert_no_committed_gitattributes(repo)

        feature_dir = repo / "kitty-specs" / MISSION_SLUG
        dep_branch = code_lane_branch_name(MISSION_SLUG, "lane-dep")

        # Dependency lane independently ADDS status.events.jsonl.
        _git(repo, "branch", dep_branch)
        _git(repo, "checkout", "-q", dep_branch)
        _write_status_event(feature_dir, event_id="evt-dep-lane", at="2026-09-09T09:00:00Z")
        _git(repo, "add", "kitty-specs")
        _git(repo, "commit", "-q", "-m", "status: dep lane event")
        _git(repo, "checkout", "-q", "main")

        # The dependent lane's own worktree independently ADDS the SAME path
        # with DIFFERENT content before the dep-tip merge runs.
        dependent_branch = code_lane_branch_name(MISSION_SLUG, "lane-c")
        dependent_wt = repo / ".worktrees" / f"{MISSION_SLUG}-lane-c"
        dependent_wt.parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "worktree", "add", "-b", dependent_branch, str(dependent_wt), "main")
        _write_status_event(
            dependent_wt / "kitty-specs" / MISSION_SLUG,
            event_id="evt-dependent-lane",
            at="2026-09-09T08:00:00Z",
        )
        _git(dependent_wt, "add", "kitty-specs")
        _git(dependent_wt, "commit", "-q", "-m", "status: dependent lane event")

        dep_lane = ExecutionLane(
            lane_id="lane-dep",
            wp_ids=("WP02",),
            write_scope=("src/**",),
            predicted_surfaces=("core",),
            depends_on_lanes=(),
            parallel_group=0,
        )
        dependent_lane = ExecutionLane(
            lane_id="lane-c",
            wp_ids=(WP_ID,),
            write_scope=("src/**",),
            predicted_surfaces=("core",),
            depends_on_lanes=("lane-dep",),
            parallel_group=1,
        )
        manifest = LanesManifest(
            version=1,
            mission_slug=MISSION_SLUG,
            mission_id=MISSION_ID,
            mission_branch=f"kitty/mission-{MISSION_SLUG}",
            target_branch="main",
            lanes=[dep_lane, dependent_lane],
            computed_at="2026-09-09T10:00:00Z",
            computed_from="test",
        )
        _use_this_venvs_spec_kitty_on_path(monkeypatch)

        # Regression assertion: pre-fix this raises
        # DependencyLaneMergeConflictError on the add/add divergence.
        _merge_dependency_lane_tips(repo, dependent_wt, MISSION_SLUG, dependent_lane, manifest)

        merged_text = (dependent_wt / "kitty-specs" / MISSION_SLUG / "status.events.jsonl").read_text(encoding="utf-8")
        assert "evt-dep-lane" in merged_text, f"dep-lane event lost: {merged_text!r}"
        assert "evt-dependent-lane" in merged_text, f"dependent-lane event lost: {merged_text!r}"

        assert _git(repo, "config", "--get", "merge.spec-kitty-event-log.driver") == _EXPECTED_DRIVER_COMMAND
        _assert_no_persistent_attribute_activation(repo)
