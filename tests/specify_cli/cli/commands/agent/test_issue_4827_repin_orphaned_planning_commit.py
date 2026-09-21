"""#4827 — finalize re-pins an ORPHANED ``planning_commit_sha`` after a
mid-mission rebase.

#4141 gave ``finalize-tasks`` an advance-only ``--refresh-planning-commit``:
refused whenever the recorded SHA is not an ancestor of the target-branch
tip, because a non-ancestor was assumed to mean "diverged/rewritten", never
"legitimately rebased". That assumption breaks for the mid-mission-rebase
shape: the recorded commit object is still present in the repository (it can
be inspected, diffed, merge-based against) but is no longer reachable from
the branch tip because the branch itself was rebased onto a newer base. A
plain (no-flag) re-finalize in that state silently PRESERVES the orphaned
pin (#3311 preserve, unaware of the distinction) and every subsequently
allocated lane keeps merging a dead base; bare ``--refresh-planning-commit``
refuses it with "not an ancestor", the same message a genuinely diverged
side-branch pin gets — no in-tool recovery exists for the rebase case.

The fix (#4827) wires the shared WP01 classifier
(:mod:`specify_cli.lanes.planning_commit_classify`) into the finalize
decision seam so it can tell ORPHANED (present, unreachable) apart from
FOREIGN (absent) and ADVANCED (the healthy state), and adds
``--allow-orphaned`` as the explicit operator assertion required to re-pin
an orphan. See ``research.md`` D3/D4/D7 and
``contracts/finalize-repin-contract.md`` for the full decision table.

These tests drive the REAL ``finalize_tasks`` entry point against a REAL git
repo — mirroring ``test_issue_4141_refresh_planning_commit.py``'s harness —
and produce the orphan via an ACTUAL ``git rebase`` (not a synthetic/fake
SHA), so ``_capture_target_branch_tip`` and the classifier's two git
predicates resolve real objects:

* ``test_plain_finalize_fails_closed_on_orphaned_pin`` — the default (no
  flag) run must FAIL CLOSED before any write: ``lanes.json`` untouched, the
  refusal names ``--refresh-planning-commit --allow-orphaned`` plus the
  recorded/tip SHAs.
* ``test_refresh_with_allow_orphaned_repins_to_new_tip`` — the crux:
  ``--refresh-planning-commit --allow-orphaned`` re-pins the recorded SHA to
  the post-rebase tip, reporting ``action: "repinned"`` with
  ``previous_sha`` equal to the orphaned SHA.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.coordination.surface_resolver import (
    resolve_status_surface_with_anchor,
)
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

from tests.specify_cli.cli.commands.agent.test_feature_finalize_bootstrap import (
    MODULE,
    _common_patches,
    _make_bootstrap_result,
    _setup_lane_based_feature,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

SEAM = "specify_cli.cli.commands.agent.mission_finalize"


def _run_finalize(
    mission_slug: str,
    patches: dict[str, object],
    *,
    refresh: bool = False,
    allow_orphaned: bool = False,
    json_output: bool = True,
) -> None:
    from specify_cli.cli.commands.agent.mission import finalize_tasks

    ctx_patches = {k: patch(k, v) for k, v in patches.items()}
    for p in ctx_patches.values():
        p.start()
    try:
        finalize_tasks(
            feature=mission_slug,
            json_output=json_output,
            validate_only=False,
            refresh_planning_commit=refresh,
            allow_orphaned=allow_orphaned,
        )
    except (typer.Exit, SystemExit):
        pass  # a refusal path deliberately exits non-zero.
    finally:
        for p in ctx_patches.values():
            p.stop()


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _git_init_with_first_commit(repo_root: Path) -> None:
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")


def _git_commit_marker(repo_root: Path, name: str, message: str) -> str:
    marker = repo_root / name
    marker.write_text(f"{name}\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", message)
    return _git(repo_root, "rev-parse", "--verify", "HEAD")


def _seed_execution_begun_event(repo_root: Path, mission_slug: str, wp_id: str) -> None:
    read_dir = resolve_status_surface_with_anchor(repo_root, mission_slug).read_dir
    append_event(
        read_dir,
        StatusEvent(
            event_id="01HXYZ4827EXECUTIONBEGUNEVT",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-09-21T00:00:00Z",
            actor="claude-sonnet",
            force=False,
            execution_mode="worktree",
        ),
    )


def _base_patches(tmp_path: Path, mission_slug: str, feature_dir: Path) -> dict[str, object]:
    patches = _common_patches(tmp_path, mission_slug)
    patches[f"{MODULE}._find_feature_directory"] = MagicMock(return_value=feature_dir)
    patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())
    return patches


@pytest.fixture(autouse=True)
def _disable_saas_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")


def _rebase_main_onto_diverged_upstream(repo_root: Path) -> str:
    """Simulate a mid-mission rebase via ``git rebase --onto`` against a
    diverged upstream base, rewriting ``main``'s tip commit(s) with brand-new
    SHAs -- exactly what a real mid-mission rebase does to every commit it
    replays.

    ``_common_patches`` mocks ``commit_for_mission`` (no real git I/O for
    finalize's own bookkeeping commit — see ``test_feature_finalize_
    bootstrap.py``), so at this point ``main`` is still exactly the single
    real ``"initial"`` commit from :func:`_git_init_with_first_commit`; the
    recorded ``planning_commit_sha`` captured by run 1 IS that commit. A
    plain ``git commit --amend`` cannot be used here (there is no parent to
    preserve identity against for a root commit), so this creates an
    unrelated diverged root, replays ``main`` onto it with ``rebase
    --onto``, and confirms the ORIGINAL commit becomes unreachable.

    ``main``'s pre-rebase tip becomes ORPHANED: the commit object stays
    present in the repository (reachable via ``ORIG_HEAD`` / reflog, not
    pruned within the test's lifetime) but is no longer an ancestor of
    ``main``'s new (rebased) tip.

    Returns the new ``main`` tip SHA after the rebase.
    """
    _git(repo_root, "checkout", "-q", "--orphan", "_upstream_base")
    _git(repo_root, "rm", "-rf", "-q", ".")
    _git_commit_marker(repo_root, "UPSTREAM_ADVANCE.txt", "upstream advanced independently")
    _git(repo_root, "checkout", "-q", "main")
    # ``--root`` replays EVERY commit on ``main`` (there may be just the one
    # real "initial" commit at this point) onto the diverged upstream base,
    # giving each a brand-new SHA.
    _git(repo_root, "rebase", "-q", "--onto", "_upstream_base", "--root", "main")
    return _git(repo_root, "rev-parse", "--verify", "main")


def test_plain_finalize_fails_closed_on_orphaned_pin(tmp_path: Path) -> None:
    mission_slug = "067-lane-feature"
    feature_dir = _setup_lane_based_feature(tmp_path, mission_slug)
    _git_init_with_first_commit(tmp_path)

    patches = _base_patches(tmp_path, mission_slug, feature_dir)

    # Run 1: materialize the established lanes; execution has NOT begun, so
    # the real main tip (this run's own finalize bookkeeping commit) is
    # captured as the recorded planning SHA.
    _run_finalize(mission_slug, patches)
    established = read_lanes_json(feature_dir)
    assert established is not None
    orphaned_sha = established.planning_commit_sha
    assert orphaned_sha is not None, "a real git repo must yield a real captured tip"

    # Execution begins, then the mission/target branch is REBASED — the
    # recorded SHA's commit object survives but main's tip moves onto a new,
    # unrelated base, orphaning it (present, not an ancestor).
    _seed_execution_begun_event(tmp_path, mission_slug, "WP01")
    new_tip = _rebase_main_onto_diverged_upstream(tmp_path)
    assert new_tip != orphaned_sha
    is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", orphaned_sha, new_tip],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert is_ancestor.returncode != 0, "sanity: the rebase must orphan the recorded SHA"
    object_present = subprocess.run(
        ["git", "cat-file", "-e", f"{orphaned_sha}^{{commit}}"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert object_present.returncode == 0, "sanity: the orphaned commit object must still be present"

    # Run 2: plain finalize, no flag — must fail closed BEFORE any write.
    emitted: list[dict[str, object]] = []
    capture_patches = {**patches, f"{SEAM}._emit_json": emitted.append}
    _run_finalize(mission_slug, capture_patches)

    after = read_lanes_json(feature_dir)
    assert after is not None
    assert after.planning_commit_sha == orphaned_sha, (
        f"a proven-orphaned pin must leave lanes.json untouched on a plain finalize; planning_commit_sha went {orphaned_sha!r} -> {after.planning_commit_sha!r}"
    )
    errors = [str(e.get("error", "")) for e in emitted if "error" in e]
    assert errors, f"a plain finalize on an orphaned pin must refuse; emitted: {emitted}"
    combined = " ".join(errors)
    assert "--refresh-planning-commit" in combined and "--allow-orphaned" in combined, (
        f"the refusal must name the --refresh-planning-commit --allow-orphaned recovery; got: {combined!r}"
    )
    assert orphaned_sha in combined and new_tip in combined, f"the refusal must name both the recorded and tip SHAs; got: {combined!r}"


def test_refresh_with_allow_orphaned_repins_to_new_tip(tmp_path: Path) -> None:
    mission_slug = "068-lane-feature"
    feature_dir = _setup_lane_based_feature(tmp_path, mission_slug)
    _git_init_with_first_commit(tmp_path)

    patches = _base_patches(tmp_path, mission_slug, feature_dir)

    _run_finalize(mission_slug, patches)
    established = read_lanes_json(feature_dir)
    assert established is not None
    orphaned_sha = established.planning_commit_sha
    assert orphaned_sha is not None

    _seed_execution_begun_event(tmp_path, mission_slug, "WP01")
    new_tip = _rebase_main_onto_diverged_upstream(tmp_path)
    assert new_tip != orphaned_sha

    # Run 2: the operator confirms the mid-mission rebase and re-pins.
    emitted: list[dict[str, object]] = []
    capture_patches = {**patches, f"{SEAM}._emit_json": emitted.append}
    _run_finalize(mission_slug, capture_patches, refresh=True, allow_orphaned=True)

    after = read_lanes_json(feature_dir)
    assert after is not None
    assert after.planning_commit_sha == new_tip, (
        "--refresh-planning-commit --allow-orphaned must re-pin planning_commit_sha to the "
        f"post-rebase tip; went {orphaned_sha!r} -> {after.planning_commit_sha!r} (expected {new_tip!r})"
    )

    success = next(e for e in emitted if e.get("result") == "success")
    planning_commit = success["planning_commit"]
    assert planning_commit["action"] == "repinned"
    assert planning_commit["sha"] == new_tip
    assert planning_commit["previous_sha"] == orphaned_sha
    assert planning_commit["branch_tip"] == new_tip
