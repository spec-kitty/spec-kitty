"""WP06 (T025) — scoped move-task writer-cut hash regression.

Proves the ``move-task`` god-write cut (FR-006/FR-007/FR-008, AC-5): every
runtime-state change driven through the real ``move-task`` entry point fires as
an event (proof-of-drive) while the WP file (``tasks/WP##.md``) and the
``tasks.md`` surface stay **byte-identical** across those move-task-owned writes
when the phase-1 flag is ON (event-only).

Scope note (deliberate): this is the **move-task writer-cut** regression only —
it does NOT claim the full-lifecycle SC-001/SC-005 acceptance. The
``implement``/``orchestrator`` writers are cut in WP07/WP08 (not WP06 deps), so
a full-lifecycle acceptance cannot be claimed here; WP10/T038 is the sole
SC-001/SC-005 acceptance. Three arms live here:

* **hash stability + proof-of-drive** — claim / note / tracker-ref driven through
  ``move-task`` leave ``tasks/WP01.md`` and ``tasks.md`` byte-stable, and each
  action persists an event.
* **SC-008 (#2647)** — an off-axis emit driven from a cwd *different* from the
  mission root lands at the stored-topology target, never a ``Path.cwd()``
  location.
* **SC-007** — the two ``in_review -> *`` edges WP06 owns
  (``in_review -> planned`` and ``in_review -> in_progress``) persist a
  ``StatusEvent`` whose ``force`` is falsy (a threaded ``review_result`` replaces
  the raw force flag).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.hasher import hash_content
from specify_cli.cli.commands.agent import tasks as tasks_module
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.status import Lane
from specify_cli.status.models import StatusEvent
from specify_cli.status.store import append_event, read_event_stream, read_events
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "001-writer-cut-hash"
_SEED_ACTOR = "fixture"

_FORWARD_SEQUENCE = [
    Lane.PLANNED,
    Lane.CLAIMED,
    Lane.IN_PROGRESS,
    Lane.FOR_REVIEW,
    Lane.IN_REVIEW,
]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _content_hash(path: Path) -> str:
    """Canonical content hash (NOT mtime — mtime is informational, not gated).

    Routes through the sanctioned ``charter.hasher.hash_content`` (TID251) rather
    than reimplementing the digest. A move-task write that leaked back into the
    file would change its text and therefore its hash.
    """
    return hash_content(path.read_text(encoding="utf-8"))


def _seed_events(feature_dir: Path, *, up_to: Lane) -> None:
    """Seed genesis -> ... -> *up_to* canonical transitions for WP01."""
    prev = Lane.GENESIS
    for idx, lane in enumerate(_FORWARD_SEQUENCE, start=1):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-{idx}",
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                from_lane=prev,
                to_lane=lane,
                at=f"2026-01-01T00:00:0{idx}+00:00",
                actor=_SEED_ACTOR,
                force=True,
                execution_mode="worktree",
            ),
        )
        prev = lane
        if lane == up_to:
            return


def _build_mission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    seed_up_to: Lane,
    wp_agent: str = "claude",
) -> tuple[Path, Path]:
    """Materialise a flag-ON lanes mission with WP01 seeded to *seed_up_to*.

    Returns ``(repo, feature_dir)``. ``status_phase: "1"`` puts the mission on the
    event-only (flag ON) write path — the WP file must stay byte-stable.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "wp06@example.invalid")
    _git(repo, "config", "user.name", "WP06 Hash Regression")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    # Cycle 2 fix (review-verdict-write-integrity-01KZ1CGF WP01): the
    # rejection-write path now threads a REAL ``commit_artifact`` call and
    # raises on a non-"committed" result. ``ProtectionPolicy.resolve`` treats
    # "main" as protected by default, so this real-git fixture needs the
    # override to let the review-cycle artifact's commit genuinely succeed --
    # mirrors ``tests/review/test_cycle.py``'s ``_unprotect_main`` idiom.
    (repo / ".kittify" / "config.yaml").write_text(
        "auto_commit: false\nprotection:\n  protected_branches: []\n", encoding="utf-8"
    )

    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))

    # Flag ON: event-only writes; WP file byte-stable across move-task actions.
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status_phase"] = "1"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    # No subtasks -> the forward review gate is trivially satisfied; this test
    # exercises the writer cut, not the subtask gate (WP04's surface).
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01 - Core\n\n(no subtasks)\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP01-core.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Core\n"
        f"agent: {wp_agent}\n"
        "shell_pid: ''\n"
        "subtasks: []\n"
        "tracker_refs: []\n"
        "dependencies: []\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed writer-cut hash fixture")
    _seed_events(feature_dir, up_to=seed_up_to)

    monkeypatch.chdir(repo)
    monkeypatch.setattr(tasks_module, "locate_project_root", lambda: repo)
    monkeypatch.setattr(
        tasks_module, "_validate_ready_for_review", lambda *_a, **_k: (True, [])
    )
    monkeypatch.setattr(tasks_module, "get_mission_type", lambda *_a, **_k: "software-dev")
    return repo, feature_dir


def _move(mission_args: list[str]) -> object:
    """Drive ``move-task`` through the real Typer app."""
    return CliRunner().invoke(tasks_app, ["move-task", *mission_args])


# ---------------------------------------------------------------------------
# Arm 1: hash stability + proof-of-drive across the move-task writer cut
# ---------------------------------------------------------------------------


def test_move_task_writer_cut_leaves_wp_file_and_tasks_md_byte_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, feature_dir = _build_mission(tmp_path, monkeypatch, seed_up_to=Lane.PLANNED)
    wp_file = feature_dir / "tasks" / "WP01-core.md"
    tasks_md = feature_dir / "tasks.md"

    wp_hash_0 = _content_hash(wp_file)
    tasks_hash_0 = _content_hash(tasks_md)
    transitions_before = len(read_events(feature_dir))
    annotations_before = len(read_event_stream(feature_dir).annotations)

    # Action A — claim: the triple rides the transition policy_metadata.
    claim = _move(
        [
            "WP01", "--to", "claimed", "--mission", _MISSION_SLUG,
            "--shell-pid", "424242", "--agent", "claude",
            "--note", "claiming for work", "--no-auto-commit", "--json",
        ]
    )
    assert claim.exit_code == 0, claim.output
    assert _content_hash(wp_file) == wp_hash_0, "claim rewrote tasks/WP01.md bytes"
    assert _content_hash(tasks_md) == tasks_hash_0, "claim rewrote tasks.md bytes"

    # Action B — note + tracker-ref union delta (off-axis InnerStateChanged).
    work = _move(
        [
            "WP01", "--to", "in_progress", "--mission", _MISSION_SLUG,
            "--agent", "claude", "--note", "starting the work",
            "--tracker-ref", "TR-123", "--no-auto-commit", "--json",
        ]
    )
    assert work.exit_code == 0, work.output
    assert _content_hash(wp_file) == wp_hash_0, "note/tracker rewrote tasks/WP01.md bytes"
    assert _content_hash(tasks_md) == tasks_hash_0, "note/tracker rewrote tasks.md bytes"

    # Proof-of-drive: BOTH transitions fired AND off-axis annotations landed.
    stream = read_event_stream(feature_dir)
    assert len(stream.transitions) == transitions_before + 2, "transitions did not fire"
    assert len(stream.annotations) > annotations_before, "no off-axis annotation persisted"

    # The claim triple rode the transition's policy_metadata (not the WP file).
    claimed_events = [
        e for e in stream.transitions if e.to_lane == Lane.CLAIMED and e.policy_metadata
    ]
    assert claimed_events, "claim triple did not ride the transition policy_metadata"
    assert claimed_events[-1].policy_metadata.get("shell_pid") == 424242
    assert claimed_events[-1].policy_metadata.get("agent") == "claude"

    # The tracker-ref union delta was recorded off-axis.
    tracker_annotations = [
        a for a in stream.annotations if a.delta.tracker_refs
    ]
    assert tracker_annotations, "tracker-ref union delta not emitted"
    assert "TR-123" in tracker_annotations[-1].delta.tracker_refs


# ---------------------------------------------------------------------------
# Arm 2: SC-008 (#2647) — off-axis emit resolves stored topology, not cwd
# ---------------------------------------------------------------------------


def test_sc008_off_axis_emit_lands_at_stored_topology_from_foreign_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, feature_dir = _build_mission(tmp_path, monkeypatch, seed_up_to=Lane.PLANNED)
    annotations_before = len(read_event_stream(feature_dir).annotations)

    # Stand somewhere that is NOT the mission root before emitting.
    foreign = tmp_path / "somewhere-else"
    foreign.mkdir()
    monkeypatch.chdir(foreign)

    result = _move(
        [
            "WP01", "--to", "claimed", "--mission", _MISSION_SLUG,
            "--shell-pid", "515151", "--agent", "claude",
            "--note", "off-axis from a foreign cwd", "--no-auto-commit", "--json",
        ]
    )
    assert result.exit_code == 0, result.output

    # The write landed at the stored-topology feature_dir...
    assert len(read_event_stream(feature_dir).annotations) > annotations_before
    # ...and NOT at any Path.cwd()-derived location.
    assert not (foreign / "kitty-specs").exists(), (
        "#2647 regression: an emit target was assembled from Path.cwd()"
    )


# ---------------------------------------------------------------------------
# Arm 3: SC-007 — the in_review -> * rewind edges.
#
# #3307 re-point: `in_review -> planned` is a member of the shared
# `spec-kitty-events` review-rejection family (`* -> planned`), which the wire
# contract the SaaS ingestion endpoint enforces declares `force=True`-required
# regardless of local evidence. FR-015/SC-007 formerly asserted it force-free
# from the CLI-local FSM; emitting `force=False` produced contract-invalid events
# hosted sync silently dropped, so the emit path now gates on both validators and
# persists `force=True` (the structured rewind rationale still travels on the
# wire). `in_review -> in_progress` is NOT in the mandatory-force family and stays
# force-free (below).
# ---------------------------------------------------------------------------


def test_sc007_in_review_to_planned_is_force_promoted_by_wire_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, feature_dir = _build_mission(
        tmp_path, monkeypatch, seed_up_to=Lane.IN_REVIEW, wp_agent="reviewer"
    )
    feedback = repo / "feedback.md"
    feedback.write_text("**Issue**: changes requested.\n", encoding="utf-8")

    result = _move(
        [
            "WP01", "--to", "planned", "--mission", _MISSION_SLUG,
            "--review-feedback-file", str(feedback), "--agent", "reviewer",
            "--no-auto-commit", "--json",
        ]
    )
    assert result.exit_code == 0, result.output

    last = read_events(feature_dir)[-1]
    assert last.from_lane == Lane.IN_REVIEW
    assert last.to_lane == Lane.PLANNED
    # #3307: review-rejection family edge — force=True per the shared wire contract.
    assert last.force, "in_review -> planned must persist force=True (#3307 wire contract)"


def test_sc007_in_review_to_in_progress_is_force_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, feature_dir = _build_mission(
        tmp_path, monkeypatch, seed_up_to=Lane.IN_REVIEW, wp_agent="reviewer"
    )
    # #4899 (operator verdict on #5044: stale test, contract stands):
    # in_review -> in_progress is a review-rejection edge and durably requires
    # reviewer feedback. SC-007's invariant -- the persisted ``force`` stays
    # falsy on this evidence-gated edge -- is unchanged.
    feedback = tmp_path / "review-feedback.md"
    feedback.write_text("**Issue**: rework requested.\n", encoding="utf-8")

    result = _move(
        [
            "WP01", "--to", "in_progress", "--mission", _MISSION_SLUG,
            "--agent", "reviewer", "--note", "reviewer sends it back",
            "--review-feedback-file", str(feedback),
            "--no-auto-commit", "--json",
        ]
    )
    assert result.exit_code == 0, result.output

    last = read_events(feature_dir)[-1]
    assert last.from_lane == Lane.IN_REVIEW
    assert last.to_lane == Lane.IN_PROGRESS
    assert not last.force, "in_review -> in_progress persisted force=True (SC-007 violated)"
    assert last.review_ref, "the rejection edge must record a pointer to the reviewer feedback"
