"""Repro #5296 -- a planning-lane claim must never merge code lanes onto the target.

Claiming a ``planning_artifact`` WP (``lane-planning``) that depends on an
approved code WP runs the dependency self-heal, which merges every approved code
dependency lane into the planning lane's workspace -- the REPOSITORY ROOT
checkout, sitting on the mission's target branch -- so code lands on the target
before ``spec-kitty consolidate`` (bypassing its attribution window). On a
protected target the same self-heal dies with ``ProtectedBranchCommitError``.

Operator decision (DM 01M3PJWGGKTRT9W03MJHFV44Q2): skip the merge and waive
code-lane ancestry for exactly that placement; code reaches the target only
through ``consolidate``. Driven through the REAL CLI (no mocking).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, blob_present_at, git_rev, run_terminus
from tests.terminus.conftest import _event  # noqa: PLC2701 -- shared harness event shape (fixture adapter)
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import _git_out as git_out
from tests.terminus.lanes_fixture import build_lanes_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_CODE_FILE = "src/pkg/wp01.py"
_NOTICE = "through `spec-kitty consolidate`"
_PLANNING_WP = "WP02"
_CARRIER_READY = (
    "---\nschema: analysis-findings/v1\nfindings: []\ncounts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n---\n\n"
    "# Specification Analysis Report\n\nNo blocking findings.\n"
)


def _wire_planning_dependency(m: CoordMission) -> None:
    """Declare WP02's dependency on WP01 in frontmatter and commit it on the target."""
    wp_file = m.feature_dir / "tasks" / f"{_PLANNING_WP}-work.md"
    wp_file.write_text(
        f"---\nwork_package_id: {_PLANNING_WP}\ntitle: {_PLANNING_WP} work\ndependencies:\n- WP01\nexecution_mode: planning_artifact\n---\n# {_PLANNING_WP}\n"
    )
    # Canonical bootstrap seed (what finalize-tasks writes): the planning WP starts `planned`.
    with (m.feature_dir / "status.events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_event(m, _PLANNING_WP, "planned", "planned"), sort_keys=True) + "\n")
    for name, text in (("spec.md", "# Spec\n\nFR-001.\n"), ("plan.md", "# Plan\n"), ("tasks.md", "# Tasks\n")):
        (m.feature_dir / name).write_text(text)
    git(m.repo, "add", "kitty-specs")
    git(m.repo, "commit", "-qm", "chore: planning WP depends on WP01")
    # The implement gate requires a fresh persisted analysis report: record it through the real CLI.
    findings = m.home / "analysis-input.md"
    findings.write_text(_CARRIER_READY, encoding="utf-8")
    recorded = run_terminus(m, ["agent", "mission", "record-analysis", "--mission", m.slug, "--input-file", str(findings)])
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    git(m.repo, "add", "kitty-specs")
    git(m.repo, "commit", "-qm", "chore: record analysis", "--allow-empty")


def _claim(m: CoordMission) -> tuple[int, str]:
    result = run_terminus(m, ["agent", "action", "implement", _PLANNING_WP, "--agent", "claude", "--mission", m.slug])
    return result.returncode, result.stdout + result.stderr


def _assert_only_status_bookkeeping_landed(m: CoordMission, since: str) -> None:
    landed = set(git_out(m.repo, "diff", "--name-only", f"{since}..{m.target_branch}").split())
    allowed = {f"kitty-specs/{m.slug}/status.events.jsonl", f"kitty-specs/{m.slug}/status.json"}
    assert landed <= allowed, f"claim landed non-bookkeeping paths on the target: {sorted(landed - allowed)}"
    merges = git_out(m.repo, "rev-list", "--merges", f"{since}..{m.target_branch}").split()
    assert not merges, f"claim created merge commit(s) on the target: {merges}"


def _root_files(m: CoordMission) -> set[str]:
    return set(git_out(m.repo, "ls-files").split())


def test_5296_planning_claim_does_not_merge_code_lanes_onto_target(tmp_path: Path) -> None:
    m = build_lanes_mission(tmp_path, with_planning_lane_wp=True, planning_depends_on_code=True, approve_planning_wp=False)
    _wire_planning_dependency(m)
    target_before = git_rev(m.repo, m.target_branch)
    assert git_out(m.repo, "symbolic-ref", "--short", "HEAD") == m.target_branch

    rc, out = _claim(m)

    assert rc == 0, out
    # The claim's own status-transition bookkeeping legitimately lands on the target (status events
    # only); what must NEVER land is code -- no merge of lane-a, no non-bookkeeping path.
    _assert_only_status_bookkeeping_landed(m, target_before)
    assert _CODE_FILE not in _root_files(m), "lane-a code merged into the repository root checkout"
    assert not (m.repo / _CODE_FILE).exists()
    assert _NOTICE in out, out

    # A planning WP's own work: a planning commit on the target under kitty-specs/<slug>/.
    (m.feature_dir / "research.md").write_text("planning output\n")
    git(m.repo, "add", str(m.feature_dir / "research.md"))
    git(m.repo, "commit", "-qm", "docs: planning output")
    # Approve WP02 (claim already recorded planned -> claimed -> in_progress).
    events = m.feature_dir / "status.events.jsonl"
    with events.open("a", encoding="utf-8") as fh:
        for frm, to in (("in_progress", "for_review"), ("for_review", "in_review"), ("in_review", "approved")):
            fh.write(json.dumps(_event(m, _PLANNING_WP, frm, to), sort_keys=True) + "\n")
    git(m.repo, "add", "kitty-specs")
    git(m.repo, "commit", "-qm", "chore: approve planning WP")

    result = run_terminus(m, ["consolidate", "--mission", m.slug, "--yes"])

    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert blob_present_at(m.repo, m.target_branch, _CODE_FILE), out


def test_5296_protected_target_claim_does_not_raise_or_commit(tmp_path: Path) -> None:
    m = build_lanes_mission(tmp_path, mid8="01M5296P", target_branch="main", with_planning_lane_wp=True, planning_depends_on_code=True, approve_planning_wp=False)
    _wire_planning_dependency(m)
    target_before = git_rev(m.repo, "main")

    _rc, out = _claim(m)

    # Contract of THIS fix: the claim never commits on the protected target and never lands the
    # code lane there; the load-bearing assertions are the unchanged `main` SHA and the absent code
    # file. (The exit code is deliberately not asserted: a LANES mission's claim status bookkeeping
    # onto a protected `main` is refused separately -- the #5385 protected-target trap, outside
    # #5296 -- and that refusal happens before any commit lands.) This fixture carries no
    # `.kittify/config.yaml`, so `assert_not_protected_branch` does not run here and the
    # `ProtectedBranchCommitError` check below is only a smoke check; the raise itself is pinned by
    # tests/lanes/test_planning_claim_self_heal.py::test_planning_claim_on_protected_target_checkout_does_not_raise.
    assert "ProtectedBranchCommitError" not in out, out
    assert _NOTICE in out, out
    assert git_rev(m.repo, "main") == target_before, "claim committed on the protected target"
    assert not (m.repo / _CODE_FILE).exists()
