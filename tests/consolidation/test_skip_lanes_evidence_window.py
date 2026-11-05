"""#7209 - the synthesized ``--skip-lanes`` manifest must carry an evidence-window base.

``spec-kitty consolidate --skip-lanes`` completes a direct-on-target Mission: a Mission whose
work packages were committed straight onto the target branch, with no lane branch and no
``lanes.json`` (the #2745 fallback). ``entry_preflight._synthesize_no_lane_manifest`` builds the
run's ``LanesManifest`` for that topology; before #7209 it recorded no ``planning_commit_sha``, so
``wp_evidence.lane_evidence_window`` returned ``None`` for every approved work package and the
#6715 evidence axis refused ``EVIDENCE_WINDOW_UNCOMPUTABLE`` on every Mission the flag exists to
serve.

This module pins the fix at the seam that owns it: the synthesized manifest resolves its base from
the target branch's own history (the target tip immediately before the first commit that
introduced ``kitty-specs/<slug>/``), the evidence window that base produces is a real tree diff,
and the evidence / independence verdicts stay exactly as strict through it. The passing row and
its negative controls share one fixture family so the axis is proven to discriminate, not to pass
everything.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from kernel.clock import now_utc_iso

import specify_cli.status  # noqa: F401  # import-order guard

from specify_cli.consolidation import wp_evidence
from specify_cli.consolidation.entry_preflight import _synthesize_no_lane_manifest
from specify_cli.lanes.compute import is_planning_lane
from specify_cli.lanes.models import LanesManifest
from specify_cli.status import materialize_snapshot, read_events

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

MISSION_SLUG = "terminus-skip-lanes-7209-01M6P3JR"

#: The mission's target branch. Deliberately NOT ``main``/``master``: those are protected by
#: :mod:`specify_cli.git.protection_policy`'s default set, and a real direct-on-target Mission
#: lands on a non-protected integration branch.
TARGET_BRANCH = "delivery"

IMPLEMENTER = "implementer-bot"
REVIEWER = "reviewer-renata"


# ---------------------------------------------------------------------------------------------
# Fixture: a direct-on-target Mission built from real commits on the target branch
# ---------------------------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> str:
    return _run(["git", "-C", str(repo), *args]).stdout.strip()


@dataclass(frozen=True)
class DirectOnTarget:
    """A direct-on-target Mission fixture: the repo, its mission dir, and the SHAs that matter."""

    repo: Path
    feature_dir: Path
    base_commit: str
    mission_commit: str
    implementation_commit: str


def _write_meta(feature_dir: Path) -> None:
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": "01M6P3JRZVRW3KKQ5V87KBQ41V",
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": TARGET_BRANCH,
        "purpose_tldr": "#7209 skip-lanes evidence window",
        "purpose_context": "direct-on-target fixture: no lane branch, no lanes.json",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_wp_file(feature_dir: Path, *, owned_files: tuple[str, ...]) -> None:
    owned = "".join(f"  - {path}\n" for path in owned_files)
    (feature_dir / "tasks" / "WP01-work.md").write_text(
        f"---\nwork_package_id: WP01\ntitle: WP01 work\nagent: implementer-bot\nowned_files:\n{owned}---\n# WP01\n",
        encoding="utf-8",
    )


def _event(event_id: str, *, from_lane: str, to_lane: str, actor: str) -> dict[str, object]:
    return {
        "actor": actor,
        "at": now_utc_iso(),
        "event_id": event_id,
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": "review-WP01" if to_lane == "approved" else None,
        "to_lane": to_lane,
        "wp_id": "WP01",
    }


def _write_status_log(feature_dir: Path, *, implementer: str, reviewer: str) -> None:
    """A reducer-valid chain claimed -> in_progress -> for_review -> in_review -> approved."""
    events = [
        _event("01HXYZ7209000000000000001", from_lane="claimed", to_lane="in_progress", actor=implementer),
        _event("01HXYZ7209000000000000002", from_lane="in_progress", to_lane="for_review", actor=implementer),
        _event("01HXYZ7209000000000000003", from_lane="for_review", to_lane="in_review", actor=reviewer),
        _event("01HXYZ7209000000000000004", from_lane="in_review", to_lane="approved", actor=reviewer),
    ]
    (feature_dir / "status.events.jsonl").write_text("\n".join(json.dumps(event, sort_keys=True) for event in events) + "\n", encoding="utf-8")


def _build_direct_on_target(
    tmp_path: Path,
    *,
    owned_files: tuple[str, ...] = ("src/impl.py",),
    implementer: str = IMPLEMENTER,
    reviewer: str = REVIEWER,
    commit_mission_dir: bool = True,
) -> DirectOnTarget:
    """A direct-on-target Mission: planning artifacts then implementation, both on the target.

    *commit_mission_dir* False models the unresolvable case: the Mission directory never reached
    the target branch's history, so no evidence-window base exists to resolve.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-qb", TARGET_BRANCH, str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "init")
    base_commit = _git(repo, "rev-parse", "HEAD")

    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    if commit_mission_dir:
        _write_meta(feature_dir)
        _write_wp_file(feature_dir, owned_files=owned_files)
        _write_status_log(feature_dir, implementer=implementer, reviewer=reviewer)
        _git(repo, "add", "kitty-specs")
        _git(repo, "commit", "-qm", f"docs({MISSION_SLUG}): planning artifacts")
    mission_commit = _git(repo, "rev-parse", "HEAD")

    implementation = repo / "src" / "impl.py"
    implementation.parent.mkdir(parents=True, exist_ok=True)
    implementation.write_text("def impl() -> int:\n    return 7209\n", encoding="utf-8")
    _git(repo, "add", "src")
    _git(repo, "commit", "-qm", f"feat({MISSION_SLUG}): WP01 committed directly on target")
    implementation_commit = _git(repo, "rev-parse", "HEAD")

    if not commit_mission_dir:
        # The Mission directory exists on disk (a status surface must) but is not in history.
        _write_meta(feature_dir)
        _write_wp_file(feature_dir, owned_files=owned_files)
        _write_status_log(feature_dir, implementer=implementer, reviewer=reviewer)

    return DirectOnTarget(
        repo=repo,
        feature_dir=feature_dir,
        base_commit=base_commit,
        mission_commit=mission_commit,
        implementation_commit=implementation_commit,
    )


def _synthesized_manifest(fixture: DirectOnTarget) -> LanesManifest:
    """Build the run's manifest through the production synthesis seam."""
    return _synthesize_no_lane_manifest(
        main_repo=fixture.repo,
        mission_slug=MISSION_SLUG,
        status_feature_dir=fixture.feature_dir,
        primary_meta_dir=fixture.feature_dir,
        target_override=None,
    )


def _evaluate(repo: Path, feature_dir: Path, manifest: LanesManifest) -> wp_evidence.EvidenceReport:
    snapshot = materialize_snapshot(feature_dir)
    return wp_evidence.evaluate_evidence(
        repo,
        feature_dir,
        manifest,
        snapshot.work_packages or {},
        events=lambda: read_events(feature_dir),
    )


# ---------------------------------------------------------------------------------------------
# The base, and the window it produces
# ---------------------------------------------------------------------------------------------


def test_synthesized_manifest_records_the_mission_start_boundary(tmp_path: Path) -> None:
    """The base is the target tip immediately before this Mission's planning artifacts appeared.

    Using the introducing commit's *parent* keeps the window non-empty even when a Mission's first
    commit carries both artifacts and work-package code (this fixture commits them separately, so
    the value is also visibly the commit before the planning commit).
    """
    fixture = _build_direct_on_target(tmp_path)

    manifest = _synthesized_manifest(fixture)

    assert manifest.planning_commit_sha == fixture.base_commit
    assert manifest.mission_branch == TARGET_BRANCH
    assert manifest.target_branch == TARGET_BRANCH
    planning_lane = manifest.lanes[0]
    assert is_planning_lane(planning_lane)
    assert wp_evidence.lane_evidence_window(manifest, planning_lane) == (fixture.base_commit, TARGET_BRANCH)

    window = wp_evidence.lane_evidence_window(manifest, planning_lane)
    assert window is not None
    paths = wp_evidence.evidence_paths(fixture.repo, window, MISSION_SLUG)
    assert "src/impl.py" in paths  # the positive control: the probe sees real implementation


def test_synthesized_manifest_base_survives_a_single_commit_mission(tmp_path: Path) -> None:
    """A Mission whose artifacts and code share one commit still gets a non-empty window.

    This is the collapsed shape of the existing #2745 fixture: the resolver takes the introducing
    commit's parent, not the introducing commit, so the window is not empty by construction.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-qb", TARGET_BRANCH, str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "init")
    base_commit = _git(repo, "rev-parse", "HEAD")
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _write_meta(feature_dir)
    _write_wp_file(feature_dir, owned_files=("src/impl.py",))
    _write_status_log(feature_dir, implementer=IMPLEMENTER, reviewer=REVIEWER)
    (repo / "src").mkdir()
    (repo / "src" / "impl.py").write_text("def impl() -> int:\n    return 7209\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", f"feat({MISSION_SLUG}): WP01 and its planning artifacts")

    manifest = _synthesize_no_lane_manifest(
        main_repo=repo,
        mission_slug=MISSION_SLUG,
        status_feature_dir=feature_dir,
        primary_meta_dir=feature_dir,
        target_override=None,
    )

    assert manifest.planning_commit_sha == base_commit
    window = wp_evidence.lane_evidence_window(manifest, manifest.lanes[0])
    assert window is not None
    assert "src/impl.py" in wp_evidence.evidence_paths(repo, window, MISSION_SLUG)


def test_resolved_base_is_deterministic(tmp_path: Path) -> None:
    """Two builds on one repository state resolve the same commit (no timestamp, no tip)."""
    fixture = _build_direct_on_target(tmp_path)

    first = _synthesized_manifest(fixture)
    second = _synthesized_manifest(fixture)

    assert first.planning_commit_sha == second.planning_commit_sha
    assert first.planning_commit_sha != fixture.implementation_commit


# ---------------------------------------------------------------------------------------------
# The evidence axis through that window: admits the owned change, refuses everything else
# ---------------------------------------------------------------------------------------------


def test_synthesized_window_admits_a_work_package_that_owns_the_change(tmp_path: Path) -> None:
    """The paired passing row: an approved WP whose owned_files the window changed is admitted."""
    fixture = _build_direct_on_target(tmp_path)

    report = _evaluate(fixture.repo, fixture.feature_dir, _synthesized_manifest(fixture))

    assert report.refusal is None, report.refusal
    assert report.verdicts == {}


def test_synthesized_window_still_refuses_a_work_package_with_no_owned_change(tmp_path: Path) -> None:
    """Same fixture, the WP owns a path the window never changed: IMPLEMENTATION_MISSING stands."""
    fixture = _build_direct_on_target(tmp_path, owned_files=("src/other.py",))

    report = _evaluate(fixture.repo, fixture.feature_dir, _synthesized_manifest(fixture))

    assert report.refusal is not None
    assert wp_evidence._refusal_codes(report.refusal) == [wp_evidence.IMPLEMENTATION_MISSING]
    assert "IMPLEMENTATION_MISSING: WP01" in report.refusal


def test_synthesized_window_still_refuses_a_self_reviewed_work_package(tmp_path: Path) -> None:
    """Same fixture, the implementer recorded its own approval: REVIEW_NOT_INDEPENDENT stands."""
    fixture = _build_direct_on_target(tmp_path, reviewer=IMPLEMENTER)

    report = _evaluate(fixture.repo, fixture.feature_dir, _synthesized_manifest(fixture))

    assert report.refusal is not None
    assert wp_evidence._refusal_codes(report.refusal) == [wp_evidence.REVIEW_NOT_INDEPENDENT]
    assert "REVIEW_NOT_INDEPENDENT: WP01" in report.refusal


# ---------------------------------------------------------------------------------------------
# Fail closed: no base, no window, no silence
# ---------------------------------------------------------------------------------------------


def test_unresolvable_base_keeps_the_window_refusal(tmp_path: Path) -> None:
    """A Mission directory absent from target history resolves no base and keeps refusing."""
    fixture = _build_direct_on_target(tmp_path, commit_mission_dir=False)

    manifest = _synthesized_manifest(fixture)

    assert manifest.planning_commit_sha is None
    assert wp_evidence.lane_evidence_window(manifest, manifest.lanes[0]) is None
    report = _evaluate(fixture.repo, fixture.feature_dir, manifest)
    assert report.refusal is not None
    assert wp_evidence._refusal_codes(report.refusal) == [wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE]
    assert "EVIDENCE_WINDOW_UNCOMPUTABLE: WP01" in report.refusal


def test_merged_planning_does_not_widen_the_window_past_unrelated_work(tmp_path: Path) -> None:
    """A planning branch merged in later must not pull pre-Mission target work into the window.

    Topology (the review finding of #7209): the planning artifacts are authored on a side branch
    cut from an early tip, unrelated implementation lands on the target *after* that fork, and the
    planning branch is merged into the target afterwards. A plain ``git log`` walk would pick the
    side-branch planning commit and take its parent as the base, so the window would include the
    unrelated implementation and falsely admit a work package that owns it. The first-parent line
    picks the merge commit, whose parent is the target tip that already had that work.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-qb", TARGET_BRANCH, str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "init")
    fork_point = _git(repo, "rev-parse", "HEAD")

    # Unrelated work lands on the target AFTER the planning branch's fork point.
    (repo / "src").mkdir()
    (repo / "src" / "impl.py").write_text("def impl() -> int:\n    return 0\n", encoding="utf-8")
    _git(repo, "add", "src")
    _git(repo, "commit", "-qm", "feat: unrelated implementation")
    unrelated_commit = _git(repo, "rev-parse", "HEAD")

    # The Mission's planning artifacts are authored on a side branch cut from the fork point.
    _git(repo, "checkout", "-q", "-b", "planning", fork_point)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _write_meta(feature_dir)
    _write_wp_file(feature_dir, owned_files=("src/impl.py",))
    _write_status_log(feature_dir, implementer=IMPLEMENTER, reviewer=REVIEWER)
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-qm", f"docs({MISSION_SLUG}): planning artifacts")
    _git(repo, "checkout", "-q", TARGET_BRANCH)
    _git(repo, "merge", "-q", "--no-ff", "planning", "-m", f"merge {MISSION_SLUG} planning")

    manifest = _synthesize_no_lane_manifest(
        main_repo=repo,
        mission_slug=MISSION_SLUG,
        status_feature_dir=feature_dir,
        primary_meta_dir=feature_dir,
        target_override=None,
    )

    # The base is the merge's first parent (the target tip that already held the unrelated work),
    # not the side-branch planning commit's parent (the fork point).
    assert manifest.planning_commit_sha == unrelated_commit
    assert manifest.planning_commit_sha != fork_point
    window = wp_evidence.lane_evidence_window(manifest, manifest.lanes[0])
    assert window is not None
    assert "src/impl.py" not in wp_evidence.evidence_paths(repo, window, MISSION_SLUG)
    report = _evaluate(repo, feature_dir, manifest)
    assert report.refusal is not None
    assert wp_evidence._refusal_codes(report.refusal) == [wp_evidence.IMPLEMENTATION_MISSING]


def test_unreadable_parent_probe_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An execution error while reading the introducing commit's parent is ``None``, not a raise."""
    from specify_cli.lanes import planning_base

    fixture = _build_direct_on_target(tmp_path)

    def _explode(*_args: object, **_kwargs: object) -> list[str]:
        raise OSError("git could not be executed")

    monkeypatch.setattr(planning_base, "commit_parents", _explode)

    manifest = _synthesized_manifest(fixture)

    assert manifest.planning_commit_sha is None
    report = _evaluate(fixture.repo, fixture.feature_dir, manifest)
    assert report.refusal is not None
    assert wp_evidence._refusal_codes(report.refusal) == [wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE]
