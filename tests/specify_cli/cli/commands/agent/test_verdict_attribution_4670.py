"""#4670 regression: reviewer verdict attribution.

The generated review-completion command (``spec-kitty agent tasks move-task
<wp> --to approved|planned ...``) omits ``--agent``, so an agent's verdict was
recorded with ``actor.tool: user`` (the configured git user) and null
model/profile instead of the claimed reviewer's identity (FR-004/FR-005).
A genuine human approval -- one where no agent ever claimed the review --
must keep recording the human (FR-006); the fix must never fabricate an
agent identity that was never asserted.

This suite drives the real ``move-task`` entry point through the full
``for_review -> in_review -> {approved, planned}`` loop (mirrors
``test_move_task_reject_fix_approve_cycle.py``) and asserts on the actual
persisted event-log actor plus the ``review_result.reviewer`` field
threaded through the review-cycle evidence artifact.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import tasks as tasks_module
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.status import Lane
from specify_cli.status.models import StatusEvent, actor_identity_str
from specify_cli.status.store import append_event, read_events
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_MISSION_SLUG = "001-verdict-attribution"
_CLAIMED_REVIEWER = "claude-reviewer"


def _wp_slug_dir(mission_slug: str) -> Path:
    return Path("kitty-specs") / mission_slug / "tasks" / "WP01-core"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _seed_hops(feature_dir: Path, mission_slug: str, hops: list[tuple], at_day: str, actor: str = "fixture") -> None:
    """Seed canonical lane transitions directly into the event log."""
    for idx, (frm, to) in enumerate(hops, start=1):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-{at_day}-{idx}",
                mission_slug=mission_slug,
                wp_id="WP01",
                from_lane=frm,
                to_lane=to,
                at=f"{at_day}T00:00:0{idx}+00:00",
                actor=actor,
                force=True,
                execution_mode="worktree",
            ),
        )


def _build_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mission_slug: str) -> tuple[Path, Path]:
    """Materialise a ``status_phase: 1`` lanes mission with WP01 at ``planned``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "4670@example.invalid")
    _git(repo, "config", "user.name", "Git User Fallback")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("auto_commit: false\nprotection:\n  protected_branches: []\n", encoding="utf-8")
    feature_dir = repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status_phase"] = "1"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n\n## WP01 - Core\n\n(no subtasks)\n", encoding="utf-8")
    (tasks_dir / "WP01-core.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Core\nagent: reviewer\nsubtasks: []\ntracker_refs: []\ndependencies: []\n---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"seed {mission_slug} fixture")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(tasks_module, "locate_project_root", lambda: repo)
    monkeypatch.setattr(tasks_module, "_validate_ready_for_review", lambda *_a, **_k: (True, []))
    monkeypatch.setattr(tasks_module, "get_mission_type", lambda *_a, **_k: "software-dev")
    return repo, feature_dir


def _move(args: list[str]):
    return CliRunner().invoke(tasks_app, ["move-task", *args])


def _latest_actor_for(feature_dir: Path, wp_id: str, to_lane: Lane) -> str:
    """The actor identity (projected to a bare string) of the most recent
    event moving ``wp_id`` to ``to_lane``."""
    events = read_events(feature_dir)
    for event in reversed(events):
        if event.wp_id == wp_id and event.to_lane == to_lane:
            return actor_identity_str(event.actor)
    raise AssertionError(f"No event moving {wp_id} to {to_lane} found")


def _review_result_reviewer(repo: Path, mission_slug: str, cycle_number: int) -> str:
    cycle_path = repo / _wp_slug_dir(mission_slug) / f"review-cycle-{cycle_number}.md"
    content = cycle_path.read_text(encoding="utf-8")
    frontmatter = content.split("---")[1]
    for line in frontmatter.splitlines():
        if line.strip().startswith("reviewer_agent:") or line.strip().startswith("reviewer:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    raise AssertionError(f"No reviewer field found in {cycle_path}:\n{content}")


# ---------------------------------------------------------------------------
# T006a -- approval: identity-omitting completion resolves the claimed
# reviewer (RED on base: verdict-actor-is-agent / resolver-fills-identity)
# ---------------------------------------------------------------------------


def test_approval_without_agent_attributes_claimed_reviewer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An agent claimed the review (`for_review -> in_review` carries its
    identity); the generated approval completion omits ``--agent``. The
    recorded verdict actor MUST be the claimed reviewer, not the git user."""
    mission_slug = f"{_MISSION_SLUG}-approve"
    repo, feature_dir = _build_mission(tmp_path, monkeypatch, mission_slug)

    _seed_hops(
        feature_dir,
        mission_slug,
        [
            (Lane.GENESIS, Lane.PLANNED),
            (Lane.PLANNED, Lane.CLAIMED),
            (Lane.CLAIMED, Lane.IN_PROGRESS),
            (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
        ],
        at_day="2026-01-01",
    )
    # The review claim: THIS is the identity that must survive into the
    # verdict, exactly as a real `spec-kitty agent action review --agent
    # claude-reviewer` claim would record it.
    _seed_hops(
        feature_dir,
        mission_slug,
        [(Lane.FOR_REVIEW, Lane.IN_REVIEW)],
        at_day="2026-01-02",
        actor=_CLAIMED_REVIEWER,
    )

    # The generated completion command as it is actually printed today --
    # NO --agent (#4670's bug).
    approved = _move(
        [
            "WP01",
            "--to",
            "approved",
            "--mission",
            mission_slug,
            "--note",
            "Review passed",
        ]
    )
    assert approved.exit_code == 0, approved.output

    actor = _latest_actor_for(feature_dir, "WP01", Lane.APPROVED)
    assert actor == _CLAIMED_REVIEWER, (
        f"Expected the verdict actor to be the claimed reviewer {_CLAIMED_REVIEWER!r}, got {actor!r} (likely the git-user/'user' fallback -- #4670)."
    )

    reviewer_field = _review_result_reviewer(repo, mission_slug, cycle_number=1)
    assert reviewer_field == _CLAIMED_REVIEWER, f"Expected review_result.reviewer == {_CLAIMED_REVIEWER!r}, got {reviewer_field!r}."


# ---------------------------------------------------------------------------
# T006b -- rejection: identity-omitting completion resolves the claimed
# reviewer too (the six-site gap: rejection uses --to planned, not --to
# rejected -- there is no such lane).
# ---------------------------------------------------------------------------


def test_rejection_without_agent_attributes_claimed_reviewer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A rejection (``--to planned --review-feedback-file``) with ``--agent``
    omitted must still attribute the claimed reviewer, not the git user."""
    mission_slug = f"{_MISSION_SLUG}-reject"
    repo, feature_dir = _build_mission(tmp_path, monkeypatch, mission_slug)

    _seed_hops(
        feature_dir,
        mission_slug,
        [
            (Lane.GENESIS, Lane.PLANNED),
            (Lane.PLANNED, Lane.CLAIMED),
            (Lane.CLAIMED, Lane.IN_PROGRESS),
            (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
        ],
        at_day="2026-01-01",
    )
    _seed_hops(
        feature_dir,
        mission_slug,
        [(Lane.FOR_REVIEW, Lane.IN_REVIEW)],
        at_day="2026-01-02",
        actor=_CLAIMED_REVIEWER,
    )

    feedback = repo / "review-feedback-1.md"
    feedback.write_text("## Issues\n\nFix this thing.\n", encoding="utf-8")

    rejected = _move(
        [
            "WP01",
            "--to",
            "planned",
            "--review-feedback-file",
            str(feedback),
            "--mission",
            mission_slug,
        ]
    )
    assert rejected.exit_code == 0, rejected.output

    actor = _latest_actor_for(feature_dir, "WP01", Lane.PLANNED)
    assert actor == _CLAIMED_REVIEWER, (
        f"Expected the rejection verdict actor to be the claimed reviewer {_CLAIMED_REVIEWER!r}, got {actor!r} (likely the git-user/'user' fallback -- #4670)."
    )

    reviewer_field = _review_result_reviewer(repo, mission_slug, cycle_number=1)
    assert reviewer_field == _CLAIMED_REVIEWER, f"Expected review_result.reviewer == {_CLAIMED_REVIEWER!r}, got {reviewer_field!r}."


# ---------------------------------------------------------------------------
# T006c -- resolver: an identity-omitting completion resolves via the event
# log, independent of the CLI render path (FR-005 -- survives even if the
# generated text is bypassed).
# ---------------------------------------------------------------------------


def test_resolver_fills_identity_directly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same as the approval case, but pins the behavior at the resolver seam
    itself (FR-005): the fix must be behavioral (event-log resolution), not
    merely a change to the printed/generated command text."""
    from specify_cli.cli.commands.agent.tasks_move_task import _mt_resolve_active_reviewer_identity, _MoveTaskState

    mission_slug = f"{_MISSION_SLUG}-resolver"
    repo, feature_dir = _build_mission(tmp_path, monkeypatch, mission_slug)

    _seed_hops(
        feature_dir,
        mission_slug,
        [
            (Lane.GENESIS, Lane.PLANNED),
            (Lane.PLANNED, Lane.CLAIMED),
            (Lane.CLAIMED, Lane.IN_PROGRESS),
            (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
        ],
        at_day="2026-01-01",
    )
    _seed_hops(
        feature_dir,
        mission_slug,
        [(Lane.FOR_REVIEW, Lane.IN_REVIEW)],
        at_day="2026-01-02",
        actor=_CLAIMED_REVIEWER,
    )

    st = _MoveTaskState(
        task_id="WP01",
        to="approved",
        mission=mission_slug,
        agent=None,
        assignee=None,
        shell_pid=None,
        note=None,
        review_feedback_file=None,
        approval_ref=None,
        reviewer=None,
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=False,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=None,
        json_output=False,
    )
    st.mission_slug = mission_slug
    st.feature_dir = feature_dir
    st.main_repo_root = repo
    st.repo_root = repo
    resolved = _mt_resolve_active_reviewer_identity(st)
    assert resolved == _CLAIMED_REVIEWER


# ---------------------------------------------------------------------------
# T006d -- genuine human approval (no agent claim) stays attributed to the
# human (FR-006). Green-on-base: the review claim itself was made by the
# git-user identity ("user"), so both the old and new resolution paths
# agree; this pins the behavior against a future regression that would
# fabricate an agent identity that was never asserted.
# ---------------------------------------------------------------------------


def test_genuine_human_approval_stays_human(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When the review claim itself carries no agent identity (a real human
    claimed and completed the review), the verdict actor must remain the
    human -- never a fabricated agent."""
    mission_slug = f"{_MISSION_SLUG}-human"
    repo, feature_dir = _build_mission(tmp_path, monkeypatch, mission_slug)

    _seed_hops(
        feature_dir,
        mission_slug,
        [
            (Lane.GENESIS, Lane.PLANNED),
            (Lane.PLANNED, Lane.CLAIMED),
            (Lane.CLAIMED, Lane.IN_PROGRESS),
            (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
        ],
        at_day="2026-01-01",
    )
    # The review claim itself is human -- no agent identity was ever
    # asserted for this WP's review.
    _seed_hops(
        feature_dir,
        mission_slug,
        [(Lane.FOR_REVIEW, Lane.IN_REVIEW)],
        at_day="2026-01-02",
        actor="user",
    )

    approved = _move(
        [
            "WP01",
            "--to",
            "approved",
            "--mission",
            mission_slug,
            "--note",
            "Review passed",
        ]
    )
    assert approved.exit_code == 0, approved.output

    actor = _latest_actor_for(feature_dir, "WP01", Lane.APPROVED)
    assert actor == "user", f"Expected the genuine human approval to stay attributed to 'user', got {actor!r}."


# ---------------------------------------------------------------------------
# T007 -- the completion-command RENDER seam (the printed/generated text,
# independent of T008's CLI-behavioral fix above). All three call sites in
# workflow_executor.py (build_review_prompt_lines's two banners,
# _review_print_finalize_summary's closing lines) route through ONE render
# helper, so every generated APPROVAL and REJECTION command carries
# --agent <resolved reviewer identity>.
# ---------------------------------------------------------------------------


def test_render_seam_resolves_claimed_reviewer_from_event_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``resolve_review_completion_reviewer`` reads the SAME for_review ->
    in_review claim the CLI-side resolver reads -- not the WP's frontmatter
    ``resolved_agent()`` (the implementer's assignment, not the reviewer's)."""
    from specify_cli.cli.commands.agent.workflow_executor import resolve_review_completion_reviewer

    mission_slug = f"{_MISSION_SLUG}-render"
    repo, feature_dir = _build_mission(tmp_path, monkeypatch, mission_slug)

    _seed_hops(
        feature_dir,
        mission_slug,
        [
            (Lane.GENESIS, Lane.PLANNED),
            (Lane.PLANNED, Lane.CLAIMED),
            (Lane.CLAIMED, Lane.IN_PROGRESS),
            (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
        ],
        at_day="2026-01-01",
    )
    _seed_hops(
        feature_dir,
        mission_slug,
        [(Lane.FOR_REVIEW, Lane.IN_REVIEW)],
        at_day="2026-01-02",
        actor=_CLAIMED_REVIEWER,
    )

    resolved = resolve_review_completion_reviewer(main_repo_root=repo, mission_slug=mission_slug, normalized_wp_id="WP01")
    assert resolved == _CLAIMED_REVIEWER


def test_render_seam_falls_back_to_user_with_no_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No review-claim event on record (an unclaimed WP) -- the render seam
    falls back to "user", the same default the CLI-side resolver uses, so a
    printed command never diverges from what move-task would resolve itself."""
    from specify_cli.cli.commands.agent.workflow_executor import resolve_review_completion_reviewer

    mission_slug = f"{_MISSION_SLUG}-render-noclaim"
    repo, feature_dir = _build_mission(tmp_path, monkeypatch, mission_slug)

    resolved = resolve_review_completion_reviewer(main_repo_root=repo, mission_slug=mission_slug, normalized_wp_id="WP01")
    assert resolved == "user"


def test_render_helper_bakes_agent_into_both_approve_and_reject() -> None:
    """``render_review_completion_commands`` is the single seam threading
    ``--agent`` into BOTH the approval (--to approved) and rejection
    (--to planned --review-feedback-file -- there is no --to rejected lane)
    completion commands."""
    from specify_cli.cli.commands.agent.workflow_executor import render_review_completion_commands

    approve_command, reject_command = render_review_completion_commands(
        normalized_wp_id="WP01",
        mission_slug="my-mission",
        review_feedback_path=Path("kitty-specs/my-mission/tasks/WP01-x/review-feedback-1.md"),
        reviewer_identity=_CLAIMED_REVIEWER,
        approve_note="Review passed",
    )
    assert "--to approved" in approve_command
    assert f"--agent {_CLAIMED_REVIEWER}" in approve_command
    assert "--to planned" in reject_command
    assert "--review-feedback-file" in reject_command
    assert f"--agent {_CLAIMED_REVIEWER}" in reject_command
    # There is no --to rejected lane in the 9-lane vocabulary.
    assert "--to rejected" not in reject_command


def test_all_six_completion_render_sites_route_through_the_single_helper() -> None:
    """Committed-grep regression (T007): every one of the six known
    completion-command literal sites named by #4670's brownfield scout
    (workflow_executor.py:1960/2003/2124 approvals,
    :1966/2014/2125 rejections, pre-fix line numbers) must be gone from the
    raw source -- replaced by calls into the single
    ``render_review_completion_commands``/``resolve_review_completion_reviewer``
    seam. A partial patch or a newly hand-rolled literal fails this grep."""
    import specify_cli.cli.commands.agent.workflow_executor as _we_module

    source = Path(_we_module.__file__).read_text(encoding="utf-8")

    # No raw move-task completion command literal may remain outside the
    # render helper's own body (the helper itself legitimately contains the
    # two f-string templates).
    literal_hits = [
        line
        for line in source.splitlines()
        if ("move-task {normalized_wp_id} --to approved" in line or "move-task {normalized_wp_id} --to planned" in line) and "spec-kitty agent tasks " in line
    ]
    # The only two surviving literals are inside render_review_completion_commands
    # itself (approve_command / reject_command template strings).
    assert len(literal_hits) == 2, f"Expected exactly the 2 template literals inside render_review_completion_commands, found {len(literal_hits)}:\n" + "\n".join(
        literal_hits
    )

    # Every one of the three call sites must route through the helpers.
    assert source.count("render_review_completion_commands(") >= 4  # def + 3 call sites
    assert source.count("resolve_review_completion_reviewer(") >= 3  # def + 2 call sites (banner fn + finalize summary)
