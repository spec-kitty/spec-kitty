"""NFR-001 benchmark: per-WP attribution overhead on a mixed lane (WP06 T031).

Spec NFR-001: "Per-WP attribution adds no more than 1 second to the
reconciliation gate on a mixed lane of 5 WPs and 50 first-parent commits,
measured by a dedicated benchmark test built on the new mixed-lane builder."

Git-backed (no mocking): builds a real 5-WP lane with 50 first-parent commits
on a real repo, once with the 5th WP CANCELED (with real commit-attribution
stamps -- the code path the canceled-content axis + ``wp_attribution.
resolve_canceled_wp`` actually walk) and once with the SAME lane's 5th WP
APPROVED instead (baseline: attribution runs, but there is no canceled WP for
the mixed-lane axis to resolve). Times ``build_approved_wp_set`` +
``MergeOutcomeVerifier.verify`` for both and asserts the delta is <= 1.0s.

``@pytest.mark.performance``: skipped unless ``SPEC_KITTY_RUN_PERFORMANCE=1``
(``tests/conftest.py``'s performance chokepoint) -- a single-shot wall-clock
budget test is cold-start/shared-runner bound, so it never blocks a normal
PR run. Never ``timing`` (that marker runs per-PR under coverage, which this
budget is not calibrated against).
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import pytest

from specify_cli.consolidation.reconciliation import MergeOutcomeVerifier, VerifyStatus, build_approved_wp_set
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json

pytestmark = [pytest.mark.performance, pytest.mark.git_repo]

_TARGET = "main"
_WP_IDS: tuple[str, ...] = ("WP01", "WP02", "WP03", "WP04", "WP05")
_COMMITS_PER_WP = 10  # 5 WPs * 10 = 50 first-parent commits (NFR-001)
_BUDGET_SECONDS = 1.0
_TIMED_RUNS = 3  # min of N timed runs after a warm-up (review cycle 1, Issue 4)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _rev(repo: Path, ref: str = "HEAD") -> str:
    return subprocess.run(["git", "rev-parse", ref], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _event(seq: int, wp: str, frm: str, to: str, *, slug: str, at: str, stamp: str | None) -> dict[str, object]:
    ev: dict[str, object] = {
        "actor": "implementer-ivan",
        "at": at,
        "event_id": f"01BENCH{seq:016d}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": slug,
        "force": False,
        "from_lane": frm,
        "reason": None,
        "review_ref": None,
        "to_lane": to,
        "wp_id": wp,
    }
    if stamp is not None:
        ev["policy_metadata"] = {"lane_head": stamp}
    return ev


def _build_five_wp_mixed_lane(tmp_path: Path, *, slug: str, wp05_canceled: bool) -> tuple[Path, Path, LanesManifest, str, str]:
    """5 WPs sharing one lane, 10 first-parent commits each (50 total).

    WP01-WP04 always run their full approve chain with one commit apiece.
    WP05 either cancels after its 10 commits (``wp05_canceled=True``, the
    mixed-lane shape this benchmark measures) or completes its own approve
    chain (``wp05_canceled=False``, the baseline with NO canceled WP for the
    mixed-lane axis to resolve -- same commit/event volume either way, so
    the timing delta isolates the canceled-content axis's own cost).
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    mission_id = ("01BENCH" + slug.upper().replace("-", ""))[:26].ljust(26, "0")
    feature_dir = repo / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": slug, "mission_id": mission_id, "mission_type": "software-dev", "target_branch": _TARGET}),
        encoding="utf-8",
    )
    lane = ExecutionLane(
        lane_id="lane-a",
        wp_ids=_WP_IDS,
        write_scope=("src/pkg",),
        predicted_surfaces=("code",),
        depends_on_lanes=(),
        parallel_group=0,
    )
    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission_id,
        mission_branch=f"kitty/mission-{slug}",
        target_branch=_TARGET,
        lanes=[lane],
        computed_at="2026-09-28T00:00:00+00:00",
        computed_from="wp06-nfr001-benchmark",
    )
    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "bootstrap")
    coord_base = _rev(repo)

    lane_branch = lane_branch_name(slug, "lane-a", planning_base_branch=_TARGET)
    _git(repo, "branch", lane_branch, coord_base)
    _git(repo, "checkout", "-q", lane_branch)

    events: list[dict[str, object]] = []
    seq = 0
    for wp_index, wp_id in enumerate(_WP_IDS):
        is_last = wp_index == len(_WP_IDS) - 1
        cancel_this_one = is_last and wp05_canceled

        seq += 1
        events.append(_event(seq, wp_id, "planned", "claimed", slug=slug, at=f"2026-01-0{wp_index + 1}T00:00:00+00:00", stamp=_rev(repo)))
        seq += 1
        events.append(_event(seq, wp_id, "claimed", "in_progress", slug=slug, at=f"2026-01-0{wp_index + 1}T00:01:00+00:00", stamp=_rev(repo)))

        for commit_index in range(_COMMITS_PER_WP):
            path = f"src/pkg/{wp_id.lower()}_{commit_index}.py"
            (repo / path).parent.mkdir(parents=True, exist_ok=True)
            (repo / path).write_text(f"{wp_id}_{commit_index} = {commit_index}\n", encoding="utf-8")
            _git(repo, "add", path)
            _git(repo, "commit", "-qm", f"{wp_id} commit #{commit_index}")

        seq += 1
        if cancel_this_one:
            events.append(_event(seq, wp_id, "in_progress", "canceled", slug=slug, at=f"2026-01-0{wp_index + 1}T00:02:00+00:00", stamp=_rev(repo)))
        else:
            events.append(_event(seq, wp_id, "in_progress", "for_review", slug=slug, at=f"2026-01-0{wp_index + 1}T00:02:00+00:00", stamp=_rev(repo)))
            seq += 1
            events.append(_event(seq, wp_id, "for_review", "in_review", slug=slug, at=f"2026-01-0{wp_index + 1}T00:03:00+00:00", stamp=None))
            seq += 1
            events.append(_event(seq, wp_id, "in_review", "approved", slug=slug, at=f"2026-01-0{wp_index + 1}T00:04:00+00:00", stamp=_rev(repo)))

    _git(repo, "checkout", "-q", _TARGET)
    events_path = feature_dir / "status.events.jsonl"
    events_path.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events), encoding="utf-8")
    _git(repo, "add", str(events_path.relative_to(repo)))
    _git(repo, "commit", "-qm", "record events")

    return repo, feature_dir, manifest, coord_base, lane_branch


def _squash_target(repo: Path, base: str, lane_branch: str) -> str:
    _git(repo, "checkout", "-q", "-b", "target-squash", base)
    _git(repo, "merge", "--squash", "-q", lane_branch)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True)
    if status.stdout.strip():
        _git(repo, "commit", "-qm", f"squash {lane_branch}")
    return "target-squash"


def _timed_claim_and_verify(
    repo: Path,
    feature_dir: Path,
    manifest: LanesManifest,
    coord_base: str,
    target_ref: str,
    excluded_wp_ids: frozenset[str],
) -> tuple[float, VerifyStatus]:
    start = time.perf_counter()
    claim = build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=excluded_wp_ids,
        excluded_window_base=coord_base,
    )
    result = MergeOutcomeVerifier(repo).verify(target_ref, replace(claim, verify_reachability=False))
    elapsed = time.perf_counter() - start
    return elapsed, result.status


def _min_of_n_timed_runs(
    repo: Path,
    feature_dir: Path,
    manifest: LanesManifest,
    coord_base: str,
    target_ref: str,
    excluded_wp_ids: frozenset[str],
    *,
    n: int = _TIMED_RUNS,
) -> tuple[float, VerifyStatus]:
    """Discard one warm-up call (cold-start cost: git subprocess spawn,
    module import inside ``build_approved_wp_set``), then take the MIN of
    *n* timed runs -- less exposed to a single scheduling hiccup than one
    timed sample (review cycle 1, Issue 4). Every run's verdict must agree;
    a status that flips between runs would itself be a correctness bug this
    benchmark should surface, not paper over by only keeping the fastest
    run's status.
    """
    _timed_claim_and_verify(repo, feature_dir, manifest, coord_base, target_ref, excluded_wp_ids)  # warm-up, discarded
    samples = [_timed_claim_and_verify(repo, feature_dir, manifest, coord_base, target_ref, excluded_wp_ids) for _ in range(n)]
    statuses = {status for _elapsed, status in samples}
    assert len(statuses) == 1, f"verdict must be stable across {n} timed runs, got {statuses}"
    best_elapsed = min(elapsed for elapsed, _status in samples)
    return best_elapsed, statuses.pop()


def test_canceled_content_axis_overhead_within_budget(tmp_path: Path) -> None:
    """NFR-001: build_approved_wp_set + verify on a 5-WP/50-commit mixed lane
    (one canceled WP with real attribution stamps) is no more than 1.0s
    slower than the same-shaped lane with NO canceled WP (baseline).

    Also asserts the VerifyResult each side actually produces (review cycle
    1, Issue 4): the mixed lane's unsuperseded canceled WP05 content must
    FAIL (so an early REFUSE or a vacuous short-circuit cannot produce a
    trivially fast "within budget" timing), and the baseline (no canceled
    WP at all) must PASS.
    """
    mixed_repo, mixed_feature_dir, mixed_manifest, mixed_coord_base, mixed_lane_branch = _build_five_wp_mixed_lane(
        tmp_path / "mixed", slug="bench-mixed", wp05_canceled=True
    )
    mixed_target = _squash_target(mixed_repo, _TARGET, mixed_lane_branch)
    mixed_elapsed, mixed_status = _min_of_n_timed_runs(mixed_repo, mixed_feature_dir, mixed_manifest, mixed_coord_base, mixed_target, frozenset({"WP05"}))
    assert mixed_status == VerifyStatus.FAIL, (
        f"the mixed lane's unsuperseded canceled WP05 content must FAIL, got {mixed_status} (an early REFUSE/short-circuit would make the timing meaningless)"
    )

    baseline_repo, baseline_feature_dir, baseline_manifest, baseline_coord_base, baseline_lane_branch = _build_five_wp_mixed_lane(
        tmp_path / "baseline", slug="bench-baseline", wp05_canceled=False
    )
    baseline_target = _squash_target(baseline_repo, _TARGET, baseline_lane_branch)
    baseline_elapsed, baseline_status = _min_of_n_timed_runs(
        baseline_repo, baseline_feature_dir, baseline_manifest, baseline_coord_base, baseline_target, frozenset()
    )
    assert baseline_status == VerifyStatus.PASS, f"the no-canceled-WP baseline must PASS, got {baseline_status}"

    delta = mixed_elapsed - baseline_elapsed
    print(f"\nNFR-001 benchmark (min of {_TIMED_RUNS} runs): mixed={mixed_elapsed:.4f}s baseline={baseline_elapsed:.4f}s delta={delta:.4f}s")
    assert delta <= _BUDGET_SECONDS, f"canceled-content axis overhead {delta:.4f}s exceeds the NFR-001 budget of {_BUDGET_SECONDS}s"
