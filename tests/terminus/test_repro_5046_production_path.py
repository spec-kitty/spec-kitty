"""SC-006: the mixed-lane-authorship-soundness fix proven end to end through
the REAL production capture path (mixed-lane-authorship-soundness-01M3M7Y0,
WP06, T028).

Every other #5046 repro (``test_repro_5046.py``) drives WP02's lifecycle
through WP01's fixture builder's own hand-written events -- a legitimate
"this is what the real workflow would have recorded" stand-in, but never the
production status shell itself. SC-006 closes that gap: this file builds the
fixture with ``canceled_lifecycle="none"`` (WP02 left ``planned``, zero
events, zero commits -- the builder's own doc says this mode exists FOR
WP06) and then drives WP02's ENTIRE lifecycle (and, for the superseded twin,
WP01's rework) through ``specify_cli.coordination.status_transition.
emit_status_transition_transactional`` -- the coord-topology transactional
shell (contract C1) that injects WP03's real ``probe_lane_head`` -- never a
hand-written ``policy_metadata={"lane_head": ...}`` stamp. Consolidation then
runs through the REAL ``spec-kitty consolidate`` CLI
(:func:`tests.terminus.conftest.run_terminus`).

This proves SC-006's own wording: "driven through the real CLI transitions
... with no hand-written attribution consolidates to FAIL; its twin with a
superseding survivor rework consolidates to PASS."

**Time-boxing note (WP prompt Context & Constraints):** driving the FULL
``spec-kitty implement`` / ``agent tasks move-task`` CLI end to end in this
fixture repo was evaluated and found to need the complete mission scaffold
(worktrees, lane checkouts, agent profile resolution) this synthetic fixture
does not carry. The documented fallback -- driving transitions through the
production status shell directly, in-process, against the SAME real
on-disk repo and coordination worktree the CLI's own consolidate command
reads -- was used instead; it is still the production capture seam (never a
hand-written stamp), and IS what actually ran end-to-end below via
``run_terminus`` for the ``consolidate`` step itself. No tooling-friction
note was needed since this path worked on the first attempt (see the
WP06 handoff report for the full account).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

import specify_cli.status.lane_head as lane_head_module
from specify_cli.coordination.status_transition import emit_status_transition_transactional
from specify_cli.status.models import ReviewResult, StatusEvent, TransitionRequest
from tests.terminus.conftest import CoordMission, build_coord_mission_mixed_lane_canceled, run_terminus

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_LEAKED_PATH = "src/pkg/wp02_new.py"
_LANE_NAME = "lane-a"
_FAIL_HEADER = "Reconciliation FAILED"
_FAIL_WHO = "canceled WP02"
_REFUSE_HEADER = "Reconciliation refused (fail-closed)"
_REFUSE_NO_ATTRIBUTION = "no commit attribution"
_SRC_DIR = Path(__file__).resolve().parents[2] / "src"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _rev(repo: Path, ref: str) -> str:
    return subprocess.run(["git", "rev-parse", ref], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _collapse(text: str) -> str:
    """Same normalisation as ``test_repro_5046.py``'s own helper (whitespace
    collapse + backtick strip), duplicated locally -- this file owns no
    shared fixture with WP02's module (owned_files: this file only)."""
    return " ".join(text.replace("`", "").split())


def _transition(
    mission: CoordMission,
    wp_id: str,
    to_lane: str,
    *,
    reason_source: str | None = None,
    review_ref: str | None = None,
    subtasks_complete: bool | None = None,
    review_result: ReviewResult | None = None,
) -> StatusEvent:
    """Drive ONE transition through the production transactional shell
    (``specify_cli.coordination.status_transition.
    emit_status_transition_transactional`` -- the coord-topology door,
    contract C1) -- never a hand-written ``policy_metadata`` stamp. Returns
    the persisted :class:`StatusEvent`, whose ``policy_metadata`` is WP03's
    real ``probe_lane_head`` result, read at persist time.
    """
    request = TransitionRequest(
        feature_dir=mission.feature_dir,
        mission_slug=mission.slug,
        wp_id=wp_id,
        to_lane=to_lane,
        actor="wp06-production-path-test",
        repo_root=mission.repo,
        reason_source=reason_source,
        review_ref=review_ref,
        subtasks_complete=subtasks_complete,
        review_result=review_result,
    )
    return emit_status_transition_transactional(request)


def _ensure_wp01_subtasks_roster(mission: CoordMission) -> None:
    """WP01's fixture task file (WP01's own builder) carries no ``subtasks:``
    frontmatter key -- fine for the builder's OWN hand-written approve
    chain, but the production ``in_progress -> for_review`` guard
    (``authored_subtask_roster``) requires the key to exist before it will
    infer completeness for a LIVE transition. Writing an empty roster here
    is fixture setup local to this file, not an edit to WP01's or WP03's
    owned sources (``conftest.py`` is untouched)."""
    wp01_file = mission.feature_dir / "tasks" / "WP01-work.md"
    wp01_file.write_text(
        "---\nwork_package_id: WP01\ntitle: WP01 work\nagent: implementer-ivan\nsubtasks: []\n---\n# WP01\n",
        encoding="utf-8",
    )
    _git(mission.repo, "add", str(wp01_file.relative_to(mission.repo)))
    _git(mission.repo, "commit", "-qm", "wp01: add empty subtasks roster for the live rework gate")


def _drive_wp02_live(mission: CoordMission, lane_branch: str) -> tuple[str, str]:
    """WP02's ENTIRE lifecycle, live, through the production shell:
    genesis -> planned -> claimed -> in_progress -> [real commit] ->
    canceled. Returns ``(lane_head_before_first_commit,
    lane_head_after_last_commit)`` -- the two SHAs the in_progress/canceled
    events' stamps must equal exactly (WP prompt T028, "not merely 'a stamp
    exists'").
    """
    _transition(mission, "WP02", "planned")  # genesis -> planned
    _transition(mission, "WP02", "claimed")

    lane_head_before_first_commit = _rev(mission.repo, lane_branch)
    in_progress_event = _transition(mission, "WP02", "in_progress")
    assert in_progress_event.policy_metadata is not None
    assert in_progress_event.policy_metadata["lane_head"] == lane_head_before_first_commit, (
        "WP02's in_progress stamp must equal the lane's rev-parse taken just before its first commit"
    )

    _git(mission.repo, "checkout", "-q", lane_branch)
    leaked = mission.repo / _LEAKED_PATH
    leaked.parent.mkdir(parents=True, exist_ok=True)
    leaked.write_text("def wp02_new():\n    return 'wp02 leaked'\n", encoding="utf-8")
    _git(mission.repo, "add", _LEAKED_PATH)
    _git(mission.repo, "commit", "-qm", "wp02 commits real content, live")
    lane_head_after_last_commit = _rev(mission.repo, lane_branch)
    _git(mission.repo, "checkout", "-q", mission.target_branch)

    cancel_event = _transition(mission, "WP02", "canceled", reason_source="operator")
    assert cancel_event.policy_metadata is not None
    assert cancel_event.policy_metadata["lane_head"] == lane_head_after_last_commit, (
        "WP02's canceled stamp must equal the lane's rev-parse taken just after its last commit"
    )
    return lane_head_before_first_commit, lane_head_after_last_commit


def _drive_wp01_superseding_rework(mission: CoordMission, lane_branch: str) -> None:
    """WP01's REWORK, live, through the production shell: approved ->
    in_progress -> [real commit fully rewriting WP02's leaked path] ->
    for_review -> in_review -> approved. Every path ``canceled_changes``
    touched must be rewritten for the mixed-lane axis to treat it as
    superseded (``wp_attribution._canceled_content_walk``'s R7 rule: the
    newest toucher of the path must be a non-canceled commit)."""
    _transition(mission, "WP01", "in_progress", review_ref="review-wp01-rework")

    _git(mission.repo, "checkout", "-q", lane_branch)
    leaked = mission.repo / _LEAKED_PATH
    leaked.write_text("def wp02_new():\n    return 'wp01 rewrote this entirely'\n", encoding="utf-8")
    _git(mission.repo, "add", _LEAKED_PATH)
    _git(mission.repo, "commit", "-qm", "wp01 rework supersedes wp02's content")
    _git(mission.repo, "checkout", "-q", mission.target_branch)

    _transition(mission, "WP01", "for_review", subtasks_complete=True)
    _transition(mission, "WP01", "in_review")
    _transition(
        mission,
        "WP01",
        "approved",
        review_result=ReviewResult(reviewer="wp06-production-path-test", verdict="approved", reference="review-wp01-rework"),
    )


def test_production_path_unsuperseded_canceled_content_fails(tmp_path: Path) -> None:
    """SC-006 (unsuperseded twin): WP02's entire lifecycle is driven live
    through the production status shell (no hand-written attribution
    anywhere in this test), and its real commit is never superseded.
    Consolidation must FAIL, naming WP02, and restore the target.
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=(),  # ignored: canceled_lifecycle="none" drives WP02 live instead
        stamp_attribution=True,
        canceled_lifecycle="none",
        mid8="01M5046P",
    )
    _ensure_wp01_subtasks_roster(mission)
    lane_branch = mission.lane_branches["WP02"]

    _drive_wp02_live(mission, lane_branch)

    pre_sha = mission.rev(mission.target_branch)
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    flat = _collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, f"unsuperseded canceled WP02 content driven through the production shell must be refused, got exit 0:\n{flat}"
    assert _FAIL_HEADER in flat, f"expected the FAIL verdict header in output:\n{flat}"
    assert _FAIL_WHO in flat, f"expected the FAIL verdict to name '{_FAIL_WHO}':\n{flat}"
    assert _LANE_NAME in flat, f"expected the FAIL verdict to name the lane '{_LANE_NAME}':\n{flat}"
    assert f"'{_LEAKED_PATH}'" in flat, f"expected the FAIL verdict to name the offending path '{_LEAKED_PATH}':\n{flat}"
    assert mission.rev(mission.target_branch) == pre_sha, "target must be restored to its pre-consolidation SHA on FAIL"


def test_production_path_superseded_twin_passes(tmp_path: Path) -> None:
    """SC-006 (superseded twin): the SAME production-path drive as above,
    plus a live WP01 rework (also through the production shell) that fully
    rewrites WP02's leaked path. Consolidation must exit 0.
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=(),
        stamp_attribution=True,
        canceled_lifecycle="none",
        mid8="01M5046Q",
    )
    _ensure_wp01_subtasks_roster(mission)
    lane_branch = mission.lane_branches["WP02"]

    _drive_wp02_live(mission, lane_branch)
    _drive_wp01_superseding_rework(mission, lane_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    flat = _collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode == 0, f"a superseding WP01 rework driven through the production shell must consolidate cleanly, got:\n{flat}"


# --------------------------------------------------------------------------- #
# T029 -- half-by-half non-vacuity proof (WP prompt: "run_terminus spawns the
# CLI as a subprocess, so monkeypatch does not reach it"). Both halves below
# use the CLI half described as PREFERRED in the WP prompt; no in-process
# fallback was needed (see the WP06 handoff report).
# --------------------------------------------------------------------------- #


def _plant_wp02_commit(mission: CoordMission, lane_branch: str) -> None:
    _git(mission.repo, "checkout", "-q", lane_branch)
    leaked = mission.repo / _LEAKED_PATH
    leaked.parent.mkdir(parents=True, exist_ok=True)
    leaked.write_text("def wp02_new():\n    return 'wp02 leaked'\n", encoding="utf-8")
    _git(mission.repo, "add", _LEAKED_PATH)
    _git(mission.repo, "commit", "-qm", "wp02 commits real content")
    _git(mission.repo, "checkout", "-q", mission.target_branch)


def test_half_by_half_capture_disabled_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Capture-off half: WP03's ``probe_lane_head`` is disabled (monkeypatched
    to always return ``None``) WHILE DRIVING WP02's transitions, in-process
    (capture happens at transition-persist time, in this same process --
    ``run_terminus`` spawns the CLI as a SEPARATE process only for the final
    ``consolidate`` step, which ``monkeypatch`` cannot reach, per the WP
    prompt). No lane_head stamp is ever recorded anywhere on WP02's events.

    Expected: REFUSE (``no commit attribution``), never PASS and never the
    ordinary FAIL -- proving the FAIL this mission adds genuinely depends on
    WP03's capture, not on some other, pre-existing mechanism.
    """
    monkeypatch.setattr(lane_head_module, "probe_lane_head", lambda **_kwargs: None)

    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=(),
        stamp_attribution=True,
        canceled_lifecycle="none",
        mid8="01M5046R",
    )
    _ensure_wp01_subtasks_roster(mission)
    lane_branch = mission.lane_branches["WP02"]

    _transition(mission, "WP02", "planned")
    _transition(mission, "WP02", "claimed")
    in_progress_event = _transition(mission, "WP02", "in_progress")
    assert in_progress_event.policy_metadata is None, "capture-off half: in_progress must carry no stamp"

    _plant_wp02_commit(mission, lane_branch)

    cancel_event = _transition(mission, "WP02", "canceled", reason_source="operator")
    assert cancel_event.policy_metadata is None, "capture-off half: canceled must carry no stamp"

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    flat = _collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, f"capture-off half must REFUSE, not PASS:\n{flat}"
    assert _REFUSE_HEADER in flat, f"expected the REFUSE header with capture disabled:\n{flat}"
    assert _REFUSE_NO_ATTRIBUTION in flat, f"expected '{_REFUSE_NO_ATTRIBUTION}' with capture disabled:\n{flat}"
    assert _FAIL_HEADER not in flat, f"capture-off half must not produce the ordinary FAIL verdict:\n{flat}"


def test_half_by_half_axis_disabled_passes(tmp_path: Path) -> None:
    """Axis-off half: WP02's lifecycle is driven live and stamped NORMALLY
    (the real production capture path, unpatched), but the CLI subprocess
    that runs ``consolidate`` is given a ``sitecustomize.py`` (prepended to
    ``PYTHONPATH`` via ``run_terminus(..., env=...)``, WP01's addition) that
    neuters ``MergeOutcomeVerifier._canceled_content_divergence`` to always
    report no findings -- simulating WP05's axis never having been wired in.

    Expected: exit 0 -- proving the FAIL this mission adds genuinely depends
    on WP05's axis, not on some other, pre-existing mechanism (the squash
    blob-attribution axis alone does not catch a mixed lane's canceled
    content, which is the whole #5046 defect this mission fixes).

    Non-vacuity (review cycle 1, Issue 3): the patched ``_axis_off`` writes a
    SENTINEL file the moment it actually runs (not merely at
    ``sitecustomize`` module load) -- proving both that the CLI subprocess
    really saw the injected ``PYTHONPATH`` AND that the patched method was
    genuinely invoked during this consolidation, not skipped by some other
    code path. A silently dropped ``PYTHONPATH`` or a renamed method fails
    loudly here instead of the exit-0 assertion alone possibly passing for
    the wrong reason.
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=(),
        stamp_attribution=True,
        canceled_lifecycle="none",
        mid8="01M5046S",
    )
    _ensure_wp01_subtasks_roster(mission)
    lane_branch = mission.lane_branches["WP02"]

    _drive_wp02_live(mission, lane_branch)

    sitecustomize_dir = tmp_path / "sitecustomize_dir"
    sitecustomize_dir.mkdir()
    sentinel = tmp_path / "axis_off_sentinel.txt"
    (sitecustomize_dir / "sitecustomize.py").write_text(
        "from pathlib import Path\n"
        "\n"
        "from specify_cli.consolidation.reconciliation import MergeOutcomeVerifier\n"
        "\n"
        f"_SENTINEL = Path({str(sentinel)!r})\n"
        "\n"
        "def _axis_off(self, target_ref, claim):\n"
        "    _SENTINEL.write_text('_canceled_content_divergence was called\\n', encoding='utf-8')\n"
        "    return [], None\n"
        "\n"
        "MergeOutcomeVerifier._canceled_content_divergence = _axis_off\n",
        encoding="utf-8",
    )
    env = {"PYTHONPATH": f"{sitecustomize_dir}{os.pathsep}{_SRC_DIR}"}

    assert not sentinel.exists(), "sentinel must not pre-exist before the patched consolidate run"
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"], env=env)

    flat = _collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode == 0, f"axis-off half must PASS (exit 0), got:\n{flat}"
    assert sentinel.exists(), f"the axis-off patch never ran -- the sitecustomize.py injection was not observed (dropped PYTHONPATH or renamed method):\n{flat}"
    assert sentinel.read_text(encoding="utf-8") == "_canceled_content_divergence was called\n"
