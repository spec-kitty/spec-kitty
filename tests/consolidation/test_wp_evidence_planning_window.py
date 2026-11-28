"""#7860: a default Mission's planning evidence window runs on its Mission branch, one window per work package.

Before a default Mission (``topology_source: default``) lands, its planning lane writes to its
Mission branch (the coordination branch). The evidence axis judges each approved planning work
package on ``<commit introducing its window-opening status event>..<Mission branch>``
(:func:`~specify_cli.consolidation.wp_evidence.planning_evidence_window`, operator ruling
2026-11-25): Mission content authored before the claim never counts (FR-010), the window ends at
the Mission branch (FR-003/FR-004), an unprovable start refuses (NFR-002), and every other shape
keeps ``planning_commit..target`` (FR-006). A hollow work package whose owned change sits on the
target branch only is named with both remedies (FR-007).

Real git throughout: the Mission is built by hand on its Mission branch, every status event is
committed in its own commit, exactly as the coordination branch carries them.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation import wp_evidence
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.lanes.compute import PLANNING_LANE_ID, lane_created_branch
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.status import read_events
from tests._support.git_cli import git_out

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "fx-01M8A725"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_TARGET = "main"
_MISSION_DIR = f"kitty-specs/{_SLUG}"
_IMPLEMENTER = "claude:sonnet:implementer"
_REVIEWER = "codex:gpt:reviewer"
_OWNED = {
    "WP01": "src/m1/**",
    "WP02": f"{_MISSION_DIR}/research/notes.md",
    "WP03": f"{_MISSION_DIR}/research/other.md",
}


@dataclass
class _Fixture:
    repo: Path
    pin: str
    counter: list[int] = field(default_factory=lambda: [0])

    @property
    def feature_dir(self) -> Path:
        return self.repo / _MISSION_DIR

    def manifest(self) -> LanesManifest:
        manifest = read_lanes_json(self.feature_dir)
        assert manifest is not None
        return manifest

    def next_event_id(self) -> str:
        self.counter[0] += 1
        return f"01M8A7{self.counter[0]:020d}"


def _git(repo: Path, *args: str) -> str:
    return git_out(repo, *args).strip()


def _wp_file(wp_id: str) -> str:
    planning = "" if wp_id == "WP01" else "execution_mode: planning_artifact\n"
    return f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\ndependencies: []\n{planning}owned_files:\n  - {_OWNED[wp_id]}\n---\n# {wp_id}\n"


def _meta(**fields: object) -> dict[str, object]:
    meta: dict[str, object] = {
        "mission_slug": _SLUG,
        "mission_id": "01M8A725AAAAAAAAAAAAAAAAAA",
        "target_branch": _TARGET,
        "topology": "lanes_with_coord",
        "topology_source": "default",
        "mission_branch": _MISSION_BRANCH,
        "coordination_branch": _MISSION_BRANCH,
    }
    meta.update(fields)
    return meta


def _manifest(pin: str, planning_wps: Sequence[str], code_wps: Sequence[str]) -> LanesManifest:
    lanes = [ExecutionLane("lane-a", tuple(code_wps), (_OWNED["WP01"],), (), (), 0)] if code_wps else []
    lanes.append(ExecutionLane(PLANNING_LANE_ID, tuple(planning_wps), tuple(_OWNED[wp] for wp in planning_wps), (), (), 0))
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id="01M8A725AAAAAAAAAAAAAAAAAA",
        mission_branch=_MISSION_BRANCH,
        target_branch=_TARGET,
        lanes=lanes,
        computed_at="2026-11-26T00:00:00+00:00",
        computed_from="test",
        planning_artifact_wps=list(planning_wps),
        planning_commit_sha=pin,
    )


def _commit_file(repo: Path, relpath: str, text: str, message: str) -> str:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(repo, "add", "--", relpath)
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _event(fx: _Fixture, wp_id: str, from_lane: str, to_lane: str, actor: str) -> dict[str, Any]:
    return {
        "actor": actor,
        "at": f"2026-11-26T00:{fx.counter[0] // 60:02d}:{fx.counter[0] % 60:02d}+00:00",
        "event_id": fx.next_event_id(),
        "evidence": None,
        "execution_mode": "direct_repo",
        "mission_slug": _SLUG,
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }


def _append_events(fx: _Fixture, events: Iterable[dict[str, Any]], *, commit: str | None) -> None:
    log = fx.feature_dir / "status.events.jsonl"
    with log.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    if commit is not None:
        _git(fx.repo, "add", "--", str(log.relative_to(fx.repo)))
        _git(fx.repo, "commit", "-qm", commit)


def _claim(fx: _Fixture, wp_id: str, *, commit: bool = True) -> None:
    events = [_event(fx, wp_id, "planned", "claimed", _IMPLEMENTER), _event(fx, wp_id, "claimed", "in_progress", _IMPLEMENTER)]
    _append_events(fx, events, commit=f"chore: claim {wp_id}" if commit else None)


def _approve(fx: _Fixture, wp_id: str) -> None:
    events = [
        _event(fx, wp_id, "in_progress", "for_review", _IMPLEMENTER),
        _event(fx, wp_id, "for_review", "in_review", _REVIEWER),
        _event(fx, wp_id, "in_review", "approved", _REVIEWER),
    ]
    _append_events(fx, events, commit=f"chore: approve {wp_id}")


def _build(
    tmp_path: Path,
    *,
    planning_wps: Sequence[str] = ("WP02",),
    code_wps: Sequence[str] = (),
    meta: dict[str, object] | None = None,
    before_claim: Sequence[str] = (),
) -> _Fixture:
    """A Mission whose repository root checkout holds its Mission branch, cut from ``main``.

    *before_claim* owned paths are committed on the Mission branch during planning (FR-010).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _commit_file(repo, "README.md", "x\n", "init")
    pin = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "-qc", _MISSION_BRANCH)
    fx = _Fixture(repo, pin)
    fx.feature_dir.mkdir(parents=True)
    (fx.feature_dir / "meta.json").write_text(json.dumps(meta if meta is not None else _meta()), encoding="utf-8")
    (fx.feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (fx.feature_dir / "tasks").mkdir()
    for wp_id in (*code_wps, *planning_wps):
        (fx.feature_dir / "tasks" / f"{wp_id}-work.md").write_text(_wp_file(wp_id), encoding="utf-8")
    write_lanes_json(fx.feature_dir, _manifest(pin, planning_wps, code_wps))
    for relpath in before_claim:
        (repo / relpath).parent.mkdir(parents=True, exist_ok=True)
        (repo / relpath).write_text("planning-time draft\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "planning")
    return fx


def _evaluate(fx: _Fixture, approved: Sequence[str]) -> wp_evidence.EvidenceReport:
    events = read_events(fx.feature_dir)
    return wp_evidence.evaluate_evidence(
        fx.repo,
        fx.feature_dir,
        fx.manifest(),
        {wp_id: {"lane": "approved"} for wp_id in approved},
        events=lambda: events,
        is_single_branch=False,
    )


def _on_target(fx: _Fixture, relpath: str, text: str, message: str) -> str:
    _git(fx.repo, "switch", "-q", _TARGET)
    sha = _commit_file(fx.repo, relpath, text, message)
    _git(fx.repo, "switch", "-q", _MISSION_BRANCH)
    return sha


# ---------------------------------------------------------------- FR-003 / FR-004 / FR-010


def test_owned_work_committed_on_the_mission_branch_after_the_claim_counts(tmp_path: Path) -> None:
    fx = _build(tmp_path)
    _claim(fx, "WP02")
    _commit_file(fx.repo, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes")
    _approve(fx, "WP02")

    report = _evaluate(fx, ["WP02"])

    assert report.refusal is None, report.refusal


def test_a_hollow_planning_work_package_is_refused_with_a_window_ending_at_the_mission_branch(tmp_path: Path) -> None:
    fx = _build(tmp_path)
    _claim(fx, "WP02")
    claim_commit = _git(fx.repo, "rev-parse", "HEAD")
    _approve(fx, "WP02")

    report = _evaluate(fx, ["WP02"])

    assert report.verdicts == {"WP02": wp_evidence.IMPLEMENTATION_MISSING}
    assert report.refusal is not None
    assert f"{claim_commit}..{_MISSION_BRANCH} ({PLANNING_LANE_ID})" in report.refusal
    assert "the Mission branch (the coordination branch)" in report.refusal
    assert "found on the target branch only" not in report.refusal


def test_an_owned_file_authored_before_the_claim_is_not_evidence(tmp_path: Path) -> None:
    """FR-010: a planning-time draft of the owned file must not make a hollow work package pass."""
    fx = _build(tmp_path, before_claim=[_OWNED["WP02"]])
    _claim(fx, "WP02")
    _approve(fx, "WP02")

    report = _evaluate(fx, ["WP02"])

    assert report.verdicts == {"WP02": wp_evidence.IMPLEMENTATION_MISSING}


def test_each_planning_work_package_is_judged_on_its_own_window(tmp_path: Path) -> None:
    fx = _build(tmp_path, planning_wps=("WP02", "WP03"))
    _claim(fx, "WP02")
    _commit_file(fx.repo, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes")
    _claim(fx, "WP03")
    _approve(fx, "WP02")
    _approve(fx, "WP03")

    report = _evaluate(fx, ["WP02", "WP03"])

    assert report.verdicts == {"WP03": wp_evidence.IMPLEMENTATION_MISSING}


# ---------------------------------------------------------------- NFR-002


def test_a_claim_event_not_committed_on_the_mission_branch_refuses(tmp_path: Path) -> None:
    fx = _build(tmp_path)
    _claim(fx, "WP02", commit=False)
    _commit_file(fx.repo, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes")

    report = _evaluate(fx, ["WP02"])

    assert report.verdicts == {"WP02": wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE}
    assert report.refusal is not None
    assert "no_commit" in report.refusal


def test_a_planning_work_package_with_no_opener_refuses(tmp_path: Path) -> None:
    fx = _build(tmp_path)
    _commit_file(fx.repo, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes")

    report = _evaluate(fx, ["WP02"])

    assert report.verdicts == {"WP02": wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE}


def _unresolved(fx: _Fixture, wp_id: str) -> wp_evidence.PlanningWindowUnresolved:
    manifest = fx.manifest()
    (lane,) = [lane for lane in manifest.lanes if lane.lane_id == PLANNING_LANE_ID]
    events = read_events(fx.feature_dir)
    with pytest.raises(wp_evidence.PlanningWindowUnresolved) as raised:
        wp_evidence.planning_evidence_window(fx.repo, manifest, lane, wp_id, lambda: events)
    return raised.value


def test_the_unresolved_window_says_whether_an_opener_is_recorded(tmp_path: Path) -> None:
    """Review 7 item 4: no opener needs one reopen; an opener that cannot be proven needs two."""
    fx = _build(tmp_path)
    assert _unresolved(fx, "WP02").opener_recorded is False
    _claim(fx, "WP02", commit=False)
    assert _unresolved(fx, "WP02").opener_recorded is True


def test_an_unreadable_event_log_refuses(tmp_path: Path) -> None:
    fx = _build(tmp_path)
    _claim(fx, "WP02")
    _commit_file(fx.repo, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes")

    report = wp_evidence.evaluate_evidence(fx.repo, fx.feature_dir, fx.manifest(), {"WP02": {"lane": "approved"}}, events=lambda: None, is_single_branch=False)

    assert report.verdicts == {"WP02": wp_evidence.IMPLEMENTATION_UNREADABLE}


def test_an_unreadable_meta_json_refuses(tmp_path: Path) -> None:
    fx = _build(tmp_path)
    _claim(fx, "WP02")
    _commit_file(fx.repo, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes")
    _approve(fx, "WP02")
    (fx.feature_dir / "meta.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(wp_evidence.PlanningWindowUnresolved) as window_error:
        wp_evidence.planning_evidence_window(fx.repo, fx.manifest(), fx.manifest().lanes[-1], "WP02", lambda: read_events(fx.feature_dir))

    assert window_error.value.code == wp_evidence.IMPLEMENTATION_UNREADABLE


# ---------------------------------------------------------------- FR-006


def test_an_explicit_topology_keeps_the_target_window(tmp_path: Path) -> None:
    meta = _meta()
    del meta["topology_source"]
    fx = _build(tmp_path, meta=meta)
    _claim(fx, "WP02")
    _approve(fx, "WP02")
    _on_target(fx, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes on the target")
    lane = fx.manifest().lanes[-1]

    assert wp_evidence.planning_evidence_window(fx.repo, fx.manifest(), lane, "WP02", lambda: read_events(fx.feature_dir)) is None
    assert _evaluate(fx, ["WP02"]).refusal is None


def test_a_landed_default_mission_keeps_the_target_window(tmp_path: Path) -> None:
    fx = _build(tmp_path, meta=_meta(merged_at="2026-11-26T01:00:00+00:00", merged_into=_TARGET))
    _claim(fx, "WP02")
    _commit_file(fx.repo, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes on the Mission branch only")
    _approve(fx, "WP02")

    report = _evaluate(fx, ["WP02"])

    assert report.verdicts == {"WP02": wp_evidence.IMPLEMENTATION_MISSING}
    assert report.refusal is not None
    assert f"{fx.pin}..{_TARGET} ({PLANNING_LANE_ID})" in report.refusal


def test_a_code_lane_beside_the_planning_lane_keeps_its_lane_window(tmp_path: Path) -> None:
    fx = _build(tmp_path, code_wps=("WP01",))
    lane_branch = lane_created_branch(fx.manifest(), "lane-a")
    _claim(fx, "WP01")
    _claim(fx, "WP02")
    _commit_file(fx.repo, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes")
    _approve(fx, "WP01")
    _approve(fx, "WP02")
    _git(fx.repo, "branch", lane_branch, fx.pin)

    report = _evaluate(fx, ["WP01", "WP02"])

    assert report.verdicts == {"WP01": wp_evidence.IMPLEMENTATION_MISSING}
    assert report.refusal is not None
    assert f"{fx.pin}..{lane_branch} (lane-a)" in report.refusal


# ---------------------------------------------------------------- FR-007


def test_owned_work_found_only_on_the_target_is_named_with_both_remedies(tmp_path: Path) -> None:
    fx = _build(tmp_path)
    _claim(fx, "WP02")
    _approve(fx, "WP02")
    owned_sha = _on_target(fx, _OWNED["WP02"], "# notes\n", "feat(WP02): research notes on the target")
    unrelated_sha = _on_target(fx, "docs/unrelated.md", "x\n", "docs: unrelated later work")

    report = _evaluate(fx, ["WP02"])

    assert report.verdicts == {"WP02": wp_evidence.IMPLEMENTATION_MISSING}
    assert report.refusal is not None
    assert f"found on the target branch only: {owned_sha}" in report.refusal
    assert unrelated_sha not in report.refusal
    assert f"cherry-pick {owned_sha}" in report.refusal
    assert "If they are this work package's work" in report.refusal
    assert f"{wp_evidence.ATTEST_NO_IMPLEMENTATION_FLAG} WP02" in report.refusal


def test_the_probe_failure_keeps_the_refusal_and_says_why(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _build(tmp_path)
    _claim(fx, "WP02")
    _approve(fx, "WP02")

    def _broken(*_args: object, **_kwargs: object) -> str:
        raise GitProbeError("git merge-base exploded")

    monkeypatch.setattr(wp_evidence, "_merge_base", _broken)
    report = _evaluate(fx, ["WP02"])

    assert report.verdicts == {"WP02": wp_evidence.IMPLEMENTATION_MISSING}
    assert report.refusal is not None
    assert "could not check the target branch: git merge-base exploded" in report.refusal


def test_an_owned_commit_already_on_the_mission_branch_is_not_target_only(tmp_path: Path) -> None:
    """A target commit the Mission branch already carries (before the claim) is not "target only"."""
    fx = _build(tmp_path)
    owned_sha = _on_target(fx, _OWNED["WP02"], "# notes\n", "feat: notes on the target before the claim")
    _git(fx.repo, "merge", "-q", "--no-edit", _TARGET)
    _claim(fx, "WP02")
    _approve(fx, "WP02")

    report = _evaluate(fx, ["WP02"])

    assert report.verdicts == {"WP02": wp_evidence.IMPLEMENTATION_MISSING}
    assert report.refusal is not None
    assert owned_sha not in report.refusal


def test_the_recovery_text_names_the_mission_branch() -> None:
    recovery = wp_evidence._RECOVERY[wp_evidence.IMPLEMENTATION_MISSING]

    assert "the Mission branch before a default Mission lands" in recovery
    assert "on the target branch for a planning-artifact work package" not in recovery
    planning_remedy = wp_evidence.PLANNING_WINDOW_RECOVERY[wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE]
    assert planning_remedy in wp_evidence._RECOVERY[wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE]


# ---------------------------------------------------------------- planning_approval_end (#7860 review M1)


def _force_approve(fx: _Fixture, wp_id: str, *, attestation: bool = False) -> str:
    """Commit a forced move into ``approved`` (no review), or a no-implementation attestation of it; returns its commit."""
    event = _event(fx, wp_id, "in_progress", "approved", "operator")
    event["force"] = True
    if attestation:
        event["policy_metadata"] = {"attestation": wp_evidence.NO_IMPLEMENTATION}
    _append_events(fx, [event], commit=f"chore: forced approval of {wp_id}")
    return _git(fx.repo, "rev-parse", "HEAD")


@pytest.mark.parametrize("case", ["review_approval", "forced_move_skips_attestation", "no_approval", "not_on_mission_branch"])
def test_planning_approval_end_is_the_commit_that_introduced_the_approval(tmp_path: Path, case: str) -> None:
    """The window end is the commit introducing the newest approval; with no review approval, the newest forced move (never an attestation)."""
    fx = _build(tmp_path, meta=_meta(topology_source="explicit") if case == "not_on_mission_branch" else None)
    _claim(fx, "WP02")
    expected: str | None = None
    if case == "review_approval":
        _approve(fx, "WP02")
        expected = _git(fx.repo, "rev-parse", "HEAD")
    elif case == "forced_move_skips_attestation":
        expected = _force_approve(fx, "WP02")
        _force_approve(fx, "WP02", attestation=True)

    events = read_events(fx.feature_dir)
    if expected is not None:
        assert wp_evidence.planning_approval_end(fx.repo, fx.manifest(), "WP02", events) == expected
        return
    with pytest.raises(wp_evidence.PlanningWindowUnresolved) as raised:
        wp_evidence.planning_approval_end(fx.repo, fx.manifest(), "WP02", events)
    assert raised.value.code == wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE
    assert ("no approval is recorded for WP02" if case == "no_approval" else "does not write to the Mission branch") in raised.value.detail
