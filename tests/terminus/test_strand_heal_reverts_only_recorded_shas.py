"""Repro #5572 — ``doctor coordination --fix`` must not revert a reviewer's later reopen.

The rc5 fix for #4973 (``repair_coord_strand`` reverting only commits that touched the status
log) was verified with a third-party commit that does NOT touch the log
(``test_repro_4973.py``). A reviewer's reopen is a *status* commit, so it is in the strand
enumeration (``captured_sha..HEAD -- status.events.jsonl``) and ``doctor coordination --fix``
reverts it together with the stranded ``done`` — erasing the reopen and printing "Healed".

Expected behaviour (spec FR-007/FR-008): the marker records the strand's own commit SHAs when it
is written; the heal reverts only those. If the status log in ``captured_sha..HEAD`` holds any
other commit, or the marker predates the recorded SHAs, the heal REFUSES: no revert, no
"Healed", non-zero exit, manual-reconcile advice naming the foreign commits, marker kept.

Driven through ``doctor coordination --fix`` (CliRunner) against a real coordination worktree.
The stranded ``done`` and the reviewer reopen are REAL status commits made through the
production coordination status shell (``emit_status_transition_transactional``); the marker is
the public ``ConsolidationState`` / ``save_state`` API — fixture setup, not a mock.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app as doctor_app
from specify_cli.consolidation.state import ConsolidationState, load_state, marker_strand_shas, save_state
from specify_cli.coordination.status_transition import emit_status_transition_transactional
from specify_cli.status.models import TransitionRequest
from tests.terminus.conftest import CoordMission, build_coord_mission
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import _git_out as git_out
from tests.terminus.mixed_lane_support import transition

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WPS = ("WP01", "WP02", "WP03")
_STRANDED_WP = "WP02"
_MERGE_ACTOR = "spec-kitty-merge"
_REVIEWER = "reviewer-renata"
_HEALED = "Healed"


def _coord_worktree(mission: CoordMission) -> Path:
    return mission.repo / ".worktrees" / f"{mission.slug}-coord"


def _events_at(mission: CoordMission, ref: str) -> list[dict[str, object]]:
    rel = f"kitty-specs/{mission.slug}/status.events.jsonl"
    raw = git_out(mission.repo, "show", f"{ref}:{rel}")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def _strand_commit(mission: CoordMission) -> tuple[str, str]:
    """Strand WP02's ``done`` as a real status commit; return ``(captured_sha, strand_sha)``."""
    captured_sha = mission.rev(mission.coord_branch)
    request = TransitionRequest(
        feature_dir=mission.feature_dir,
        mission_slug=mission.slug,
        wp_id=_STRANDED_WP,
        to_lane="done",
        actor=_MERGE_ACTOR,
        repo_root=mission.repo,
        evidence={"review": {"reviewer": _REVIEWER, "verdict": "approved", "reference": "review-approve-5572"}},
    )
    emit_status_transition_transactional(request)
    strand_sha = mission.rev(mission.coord_branch)
    assert strand_sha != captured_sha, "fixture precondition: the stranded done must be a new coord commit"
    return captured_sha, strand_sha


def _save_marker(mission: CoordMission, captured_sha: str, *, strand_shas: list[str] | None) -> None:
    """Persist the marker a failed consolidation leaves (``strand_shas=None`` = legacy marker)."""
    state = ConsolidationState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch=mission.target_branch,
        wp_order=list(_WPS),
    )
    marker: dict[str, object] = {
        "coord_ref": mission.coord_branch,
        "captured_sha": captured_sha,
        "coord_worktree": str(_coord_worktree(mission)),
        "stranded_wp_ids": [_STRANDED_WP],
        "revert_error": None,
        "detected_at": "2026-10-03T12:00:00+00:00",
    }
    if strand_shas is not None:
        marker["strand_shas"] = strand_shas
    state.pending_coord_reconcile = marker
    save_state(state, mission.repo)


def _reviewer_reopen(mission: CoordMission, wp_id: str) -> str:
    """A reviewer's forced reopen as a real status commit; return the new coord tip."""
    transition(
        mission,
        wp_id,
        "in_progress",
        actor=_REVIEWER,
        force=True,
        reason="reviewer reopen after rejection",
        review_ref="review-reopen-5572",
    )
    return mission.rev(mission.coord_branch)


def _doctor_fix(mission: CoordMission, monkeypatch: pytest.MonkeyPatch) -> Result:
    monkeypatch.chdir(mission.repo)
    return CliRunner().invoke(doctor_app, ["coordination", "--fix"], catch_exceptions=False)


def _flat(text: str) -> str:
    return " ".join(text.split())


@pytest.mark.parametrize("reopened_wp", ["WP03", "WP01"], ids=["sibling-wp-reopen", "wp01-reopen"])
def test_5572_doctor_fix_must_not_revert_a_reviewers_later_reopen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reopened_wp: str) -> None:
    mission = build_coord_mission(tmp_path, wps=_WPS, mid8="01M5572A")
    captured_sha, strand_sha = _strand_commit(mission)
    _save_marker(mission, captured_sha, strand_shas=[strand_sha])
    reopen_tip = _reviewer_reopen(mission, reopened_wp)

    result = _doctor_fix(mission, monkeypatch)
    out = _flat(result.output)

    # The reviewer's reopen is still the newest status event of its WP on the coord branch.
    reopen_events = [e for e in _events_at(mission, mission.coord_branch) if e["wp_id"] == reopened_wp]
    assert reopen_events[-1]["to_lane"] == "in_progress", f"doctor --fix erased the reviewer's reopen of {reopened_wp} (#5572):\n{out}"
    assert _HEALED not in out, f"doctor --fix printed a success claim over a refused heal:\n{out}"
    assert result.exit_code != 0, f"a refused heal must exit non-zero (got {result.exit_code}):\n{out}"
    assert reopen_tip[:12] in out, f"the refusal must name the foreign commit it would have erased:\n{out}"
    assert "manually" in out, f"the refusal must carry manual-reconcile advice:\n{out}"
    assert mission.rev(mission.coord_branch) == reopen_tip, "the refused heal must not add a revert commit"
    state = load_state(mission.repo, mission.mission_id)
    assert state is not None and state.pending_coord_reconcile is not None, "the marker must be kept on a refusal"


def test_5572_positive_control_strand_only_range_still_heals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = build_coord_mission(tmp_path, wps=_WPS, mid8="01M5572B")
    captured_sha, strand_sha = _strand_commit(mission)
    _save_marker(mission, captured_sha, strand_shas=[strand_sha])

    result = _doctor_fix(mission, monkeypatch)
    out = _flat(result.output)

    assert result.exit_code == 0, out
    assert _HEALED in out
    wp02 = [e for e in _events_at(mission, mission.coord_branch) if e["wp_id"] == _STRANDED_WP]
    assert wp02[-1]["to_lane"] != "done", "the strand's own done must be reverted"
    state = load_state(mission.repo, mission.mission_id)
    assert state is not None and state.pending_coord_reconcile is None
    # The revert appended a commit; the stranded done stays in history (append-only log).
    git(mission.repo, "merge-base", "--is-ancestor", strand_sha, mission.coord_branch)


def test_5572_marker_writer_records_the_strands_own_commit_shas(tmp_path: Path) -> None:
    """T015: the production marker writer persists ``strand_shas`` — exactly this run's strand."""
    from types import SimpleNamespace

    from specify_cli.consolidation import executor as ex

    mission = build_coord_mission(tmp_path, wps=_WPS, mid8="01M5572C")
    captured_sha, strand_sha = _strand_commit(mission)
    coord_worktree = _coord_worktree(mission)
    state = ConsolidationState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch=mission.target_branch,
        wp_order=list(_WPS),
    )
    run: Any = SimpleNamespace(
        main_repo=mission.repo,
        mission_slug=mission.slug,
        state=state,
        pre_target_coord_ref=mission.coord_branch,
        pre_target_coord_sha=captured_sha,
        pre_target_done_write_set=[_STRANDED_WP],
        canonical_events_path=coord_worktree / "kitty-specs" / mission.slug / "status.events.jsonl",
    )

    ex._persist_coord_reconcile_marker(run, None)

    persisted = load_state(mission.repo, mission.mission_id)
    assert persisted is not None and persisted.pending_coord_reconcile is not None
    assert persisted.pending_coord_reconcile["strand_shas"] == [strand_sha]
    assert persisted.pending_coord_reconcile["stranded_wp_ids"] == [_STRANDED_WP]
    assert marker_strand_shas(persisted.pending_coord_reconcile) == [strand_sha]


def test_5572_marker_strand_shas_reader_is_tolerant_of_legacy_and_malformed_markers() -> None:
    """T015: ``strand_shas`` is optional — absent or malformed reads as ``None`` (legacy), never raises."""
    assert marker_strand_shas(None) is None
    assert marker_strand_shas({"coord_ref": "c"}) is None  # legacy marker: predates the field
    assert marker_strand_shas({"strand_shas": "abc123"}) is None  # not a list
    assert marker_strand_shas({"strand_shas": ["abc123", 7]}) is None  # not list[str]
    assert marker_strand_shas({"strand_shas": []}) == []  # recorded, but empty
    assert marker_strand_shas({"strand_shas": ["abc123", "def456"]}) == ["abc123", "def456"]


def test_5572_legacy_marker_without_recorded_shas_is_refused_not_guessed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A marker that predates ``strand_shas`` is refused even over a strand-only range."""
    mission = build_coord_mission(tmp_path, wps=_WPS, mid8="01M5572D")
    captured_sha, _ = _strand_commit(mission)
    _save_marker(mission, captured_sha, strand_shas=None)
    tip_before = mission.rev(mission.coord_branch)

    result = _doctor_fix(mission, monkeypatch)
    out = _flat(result.output)

    assert result.exit_code != 0, out
    assert _HEALED not in out, out
    assert "predates recorded strand commits" in out, out
    assert mission.rev(mission.coord_branch) == tip_before, "a legacy marker must not be healed by guessing the range"
    state = load_state(mission.repo, mission.mission_id)
    assert state is not None and state.pending_coord_reconcile is not None


def _resume(mission: CoordMission) -> str:
    from tests.terminus.conftest import run_terminus

    result = run_terminus(mission, ["consolidate", "--resume", "--mission", mission.slug, "--yes"])
    return _flat(result.stdout + result.stderr)


def test_5572_resume_explains_a_refused_heal_for_a_legacy_marker(tmp_path: Path) -> None:
    """The resume-start heal says WHY it refused a marker that predates recorded strand commits."""
    mission = build_coord_mission(tmp_path, wps=_WPS, mid8="01M5572E")
    captured_sha, _ = _strand_commit(mission)
    _save_marker(mission, captured_sha, strand_shas=None)

    out = _resume(mission)

    assert "NOT reverted" in out, out
    assert "the reconcile marker predates recorded strand commits" in out, out
    assert "none named" not in out, out


@pytest.mark.parametrize(
    ("foreign", "expected"),
    [
        (["abcdef0123456789"], "the status log holds commits the marker did not record (foreign: abcdef0123), e.g. a later reopen"),
        ([], "the status log no longer matches the commits the marker recorded"),
    ],
    ids=["names-the-foreign-commits", "no-foreign-commit-named"],
)
def test_5572_resume_heal_refusal_text_for_a_strand_mismatch(capsys: pytest.CaptureFixture[str], foreign: list[str], expected: str) -> None:
    """A mismatch that names no foreign commit must not print 'none named' — it says what disagrees."""
    from specify_cli.consolidation import executor as ex
    from specify_cli.coordination.coherence import CoordRepairOutcome

    ex.console.width = 400
    ex._report_refused_strand_heal(CoordRepairOutcome(healed=False, strand_mismatch=True, foreign_status_commits=foreign))

    out = _flat(capsys.readouterr().out)
    assert expected in out, out
    assert "none named" not in out, out
    assert "The reconcile marker is kept." in out, out
    assert "spec-kitty doctor coordination" in out, out
