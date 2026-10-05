"""Shared helpers for the real-CLI mixed-lane canceled-content suites.

Output normalisation and verdict-block extraction for ``spec-kitty
consolidate`` runs, the gate's verdict wording, and the in-process driver for
the production coord-topology transactional status shell
(``emit_status_transition_transactional``) that the production-capture and
fail-recovery suites both use. Fixture builders stay in
:mod:`tests.terminus.conftest`.
"""

from __future__ import annotations

from specify_cli.coordination.status_transition import emit_status_transition_transactional
from specify_cli.status.models import ReviewResult, StatusEvent, TransitionRequest
from tests.terminus.conftest import CoordMission
from tests.terminus.conftest import _git as git

FAIL_HEADER = "Reconciliation FAILED"
REFUSE_HEADER = "Reconciliation refused (fail-closed)"
FAIL_WHO = "canceled WP02"
LANE_NAME = "lane-a"
ATTEST_FLAG = "--attest-canceled-superseded"


def collapse(text: str) -> str:
    """Collapse whitespace to single spaces AND strip backticks.

    A rich-console line wrap or a Markdown-styled recovery step
    ("re-run `spec-kitty consolidate`") then still matches a plain substring.
    Case is preserved: the verdict assertions pin exact-case text
    (``Reconciliation FAILED``), which the lowercasing
    :func:`tests.terminus.conftest.output_names_content_fail` would not.
    """
    return " ".join(text.replace("`", "").split())


def verdict_block(flat: str, header: str) -> str:
    """The suffix of *flat* starting at *header* -- the operator-facing verdict.

    ``"lane-a"`` / ``"WP02"`` appear in ANY run's output, so an assertion that
    only checks "appears somewhere" is vacuous; binding it to the verdict
    block checks that the VERDICT names the lane/WP.
    """
    idx = flat.find(header)
    assert idx != -1, f"expected the verdict text '{header}' in output:\n{flat}"
    return flat[idx:]


def clause_for_path(block: str, path: str) -> str:
    """The semicolon-delimited clause of *block* that names ``'<path>'``.

    The FAIL template renders one ``situation; recovery`` pair per divergence,
    so binding a path's expected wording to the SAME clause the path appears
    in proves the gate attached the right wording to the right path.
    """
    needle = f"'{path}'"
    for clause in block.split(";"):
        if needle in clause:
            return clause
    raise AssertionError(f"no clause in the verdict block names '{path}':\n{block}")


def transition(
    mission: CoordMission,
    wp_id: str,
    to_lane: str,
    *,
    actor: str = "mixed-lane-test",
    force: bool = False,
    reason: str | None = None,
    reason_source: str | None = None,
    review_ref: str | None = None,
    subtasks_complete: bool | None = None,
    review_result: ReviewResult | None = None,
) -> StatusEvent:
    """Drive ONE transition through the production coord-topology transactional shell.

    Never a hand-written ``policy_metadata`` stamp: the returned, persisted
    :class:`StatusEvent` carries whatever ``probe_lane_head`` read at persist time.
    """
    request = TransitionRequest(
        feature_dir=mission.feature_dir,
        mission_slug=mission.slug,
        wp_id=wp_id,
        to_lane=to_lane,
        actor=actor,
        repo_root=mission.repo,
        force=force,
        reason=reason,
        reason_source=reason_source,
        review_ref=review_ref,
        subtasks_complete=subtasks_complete,
        review_result=review_result,
    )
    return emit_status_transition_transactional(request)


def reapprove_wp01(mission: CoordMission, *, actor: str) -> None:
    """Send WP01 back for review and approve it again at the current lane tip (the production shell stamps it).

    Any content commit on the lane after WP01's approval refuses with
    ``LANE_MOVED_AFTER_APPROVAL`` until this is done, a canceled work package's own
    commit included (#5720). The caller gives WP01 its subtasks roster first
    (:func:`ensure_wp01_subtasks_roster`).
    """
    transition(mission, "WP01", "in_progress", actor=actor, review_ref="review-wp01-rework")
    transition(mission, "WP01", "for_review", actor=actor, subtasks_complete=True)
    transition(mission, "WP01", "in_review", actor=actor)
    transition(
        mission,
        "WP01",
        "approved",
        actor=actor,
        review_result=ReviewResult(reviewer=actor, verdict="approved", reference="review-wp01-rework"),
    )


def ensure_wp01_subtasks_roster(mission: CoordMission) -> None:
    """Give WP01's fixture task file an empty ``subtasks:`` roster.

    The builder's task file carries no ``subtasks:`` key, which is fine for its
    own hand-written approve chain, but the live ``in_progress -> for_review``
    guard (``authored_subtask_roster``) requires the key before it infers
    completeness for a real transition.
    """
    wp01_file = mission.feature_dir / "tasks" / "WP01-work.md"
    wp01_file.write_text(
        "---\nwork_package_id: WP01\ntitle: WP01 work\nagent: implementer-ivan\nsubtasks: []\n---\n# WP01\n",
        encoding="utf-8",
    )
    git(mission.repo, "add", str(wp01_file.relative_to(mission.repo)))
    git(mission.repo, "commit", "-qm", "wp01: add empty subtasks roster for the live rework gate")
