"""#7209 - ``EVIDENCE_WINDOW_UNCOMPUTABLE`` names a remedy that works in a no-lanes Mission.

The code is unchanged and stays unliftable: an evidence window that cannot be computed refuses.
What changes is the advice. The only recovery this refusal used to print was
``run `spec-kitty agent mission finalize-tasks` to record the planning commit``, which addresses a
``lanes.json`` a ``--skip-lanes`` direct-on-target Mission does not have. A refusal whose remedy
cannot be performed is a dead end, so the recovery now names both shapes: ``finalize-tasks`` for a
recorded but unpinned ``lanes.json`` (#7210), and committing the Mission's planning artifacts on the
target branch for a Mission with no ``lanes.json`` at all.

The refusal line no longer claims "lanes.json records no planning commit" either: on this topology
there need be no ``lanes.json``, so it says no planning commit is recorded or resolvable.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from kernel.clock import now_utc_iso

import specify_cli.status  # noqa: F401  # import-order guard

from specify_cli.consolidation import wp_evidence
from specify_cli.consolidation.entry_preflight import _synthesize_no_lane_manifest
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.status import materialize_snapshot, read_events

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

MISSION_SLUG = "terminus-skip-lanes-refusal-7209-01M6P3JR"
TARGET_BRANCH = "delivery"
IMPLEMENTER = "implementer-bot"
REVIEWER = "reviewer-renata"


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> str:
    return _run(["git", "-C", str(repo), *args]).stdout.strip()


def _write_meta(feature_dir: Path) -> None:
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": "01M6P3JRZVRW3KKQ5V87KBQ41V",
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": TARGET_BRANCH,
        "purpose_tldr": "#7209 refusal text",
        "purpose_context": "direct-on-target fixture: no lanes.json",
    }
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_wp_file(feature_dir: Path, owned_files: tuple[str, ...] = ("src/impl.py",)) -> None:
    owned = "".join(f"  - {path}\n" for path in owned_files)
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (feature_dir / "tasks" / "WP01-work.md").write_text(
        f"---\nwork_package_id: WP01\ntitle: WP01 work\nagent: {IMPLEMENTER}\nowned_files:\n{owned}---\n# WP01\n",
        encoding="utf-8",
    )


def _write_status_log(feature_dir: Path) -> None:
    def event(event_id: str, *, from_lane: str, to_lane: str, actor: str) -> dict[str, object]:
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

    events = [
        event("01HXYZ7209000000000000011", from_lane="claimed", to_lane="in_progress", actor=IMPLEMENTER),
        event("01HXYZ7209000000000000012", from_lane="in_progress", to_lane="for_review", actor=IMPLEMENTER),
        event("01HXYZ7209000000000000013", from_lane="for_review", to_lane="in_review", actor=REVIEWER),
        event("01HXYZ7209000000000000014", from_lane="in_review", to_lane="approved", actor=REVIEWER),
    ]
    (feature_dir / "status.events.jsonl").write_text("\n".join(json.dumps(item, sort_keys=True) for item in events) + "\n", encoding="utf-8")


def _build_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    """A repo with two commits on the target; the Mission dir is on disk but not in history."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-qb", TARGET_BRANCH, str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "init")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "src").mkdir()
    (repo / "src" / "impl.py").write_text("def impl() -> int:\n    return 7209\n", encoding="utf-8")
    _git(repo, "add", "src")
    _git(repo, "commit", "-qm", "feat: implementation")
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    _write_meta(feature_dir)
    _write_wp_file(feature_dir)
    _write_status_log(feature_dir)
    return repo, feature_dir, base


def _manifest(planning_commit_sha: str | None) -> LanesManifest:
    """The direct-on-target synthetic manifest: one planning lane whose tip is the target branch."""
    return LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id="01M6P3JRZVRW3KKQ5V87KBQ41V",
        mission_branch=TARGET_BRANCH,
        target_branch=TARGET_BRANCH,
        lanes=[ExecutionLane(lane_id=PLANNING_LANE_ID, wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)],
        computed_at=now_utc_iso(),
        computed_from="skip-lanes direct-on-target synthesis (T021, FR-012)",
        planning_commit_sha=planning_commit_sha,
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


def test_uncomputable_window_leads_with_the_code_and_names_both_remedies(tmp_path: Path) -> None:
    """The refusal keeps its code and offers the remedy each shape can actually perform."""
    repo, feature_dir, _base = _build_repo(tmp_path)

    report = _evaluate(repo, feature_dir, _manifest(planning_commit_sha=None))

    assert report.refusal is not None
    # The one authority for the code is unchanged: it still leads the line.
    assert wp_evidence._refusal_codes(report.refusal) == [wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE]
    assert "EVIDENCE_WINDOW_UNCOMPUTABLE: WP01" in report.refusal
    # The recorded-but-unpinned remedy survives (#7210) ...
    assert "finalize-tasks" in report.refusal
    # ... and the no-`lanes.json` remedy names the shape an operator can perform.
    assert "no `lanes.json`" in report.refusal
    assert "commit the Mission's planning artifacts" in report.refusal
    assert "kitty-specs/<slug>/" in report.refusal
    assert "on the target branch" in report.refusal


def test_the_finalize_remedy_names_the_route_that_works(tmp_path: Path) -> None:
    """#7210: plain finalize-tasks derives a missing pin; --refresh-planning-commit records an empty window."""
    repo, feature_dir, _base = _build_repo(tmp_path)

    report = _evaluate(repo, feature_dir, _manifest(planning_commit_sha=None))

    assert report.refusal is not None
    assert "run plain `spec-kitty agent mission finalize-tasks` (no flags)" in report.refusal
    assert "derives one from git" in report.refusal
    assert "Do not use `--refresh-planning-commit` for this" in report.refusal
    assert "escalate to the operator" in report.refusal


def test_the_line_no_longer_claims_a_lanes_json_that_need_not_exist(tmp_path: Path) -> None:
    """The line says the commit is not recorded *or resolvable*: this topology has no lanes.json."""
    repo, feature_dir, _base = _build_repo(tmp_path)

    report = _evaluate(repo, feature_dir, _manifest(planning_commit_sha=None))

    assert report.refusal is not None
    assert "lanes.json records no planning commit" not in report.refusal
    assert "no planning commit is recorded or resolvable" in report.refusal


def test_positive_control_a_resolved_base_produces_no_refusal(tmp_path: Path) -> None:
    """Same fixture, a recorded base: the window computes, so the probe is not always a refusal."""
    repo, feature_dir, base = _build_repo(tmp_path)

    report = _evaluate(repo, feature_dir, _manifest(planning_commit_sha=base))

    assert report.refusal is None, report.refusal


def test_synthesized_manifest_without_history_hits_the_same_remedy(tmp_path: Path) -> None:
    """Through the production synthesis seam: no committed Mission dir -> no base -> the same text."""
    repo, feature_dir, _base = _build_repo(tmp_path)

    manifest = _synthesize_no_lane_manifest(
        main_repo=repo,
        mission_slug=MISSION_SLUG,
        status_feature_dir=feature_dir,
        primary_meta_dir=feature_dir,
        target_override=None,
    )
    report = _evaluate(repo, feature_dir, manifest)

    assert manifest.planning_commit_sha is None
    assert report.refusal is not None
    assert wp_evidence._refusal_codes(report.refusal) == [wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE]
    assert "commit the Mission's planning artifacts" in report.refusal
