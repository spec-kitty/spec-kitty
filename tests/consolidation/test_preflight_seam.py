"""Seam test for the relocated merge preflights (mission #2057, WP05).

Covers the hollow-review warning split (force_count + ReviewerSelfApproval),
both review-artifact-gate branches, target-branch validation, mission-branch
checks, and effective-push resolution. The re-export-identity and one-way-
import guards (FR-003, FR-005, FR-006, C-002, INV-2) live in the consolidated
``tests/merge/test_merge_compat_surface.py`` (WP04,
dev-assist-retire-path-hardening-01KXAVR0 / #2565) — this file keeps only the
functional coverage and the domain/publish-layer import-boundary guard below.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import typer

from specify_cli.consolidation import preflight
from specify_cli.consolidation._constants import HollowReviewWarnings
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.status import REVIEWER_SELF_APPROVAL
from specify_cli.status.lifecycle_events import emit_reviewer_self_approval

pytestmark = pytest.mark.fast


def test_domain_preflight_has_no_push_preflight_module_import() -> None:
    """Issue #1706 boundary: domain ``preflight`` must not import the publish layer at load.

    The push/target-sync preflight (which consumes ``check_push_safety``) now
    lives in ``push_preflight``, so ``preflight`` carries no push_preflight
    import outside ``TYPE_CHECKING`` — preserving the network-free domain layer.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(preflight))
    parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}

    def under_type_checking(node: ast.AST) -> bool:
        while node in parents:
            parent = parents[node]
            if (
                isinstance(parent, ast.If)
                and isinstance(parent.test, ast.Name)
                and parent.test.id == "TYPE_CHECKING"
            ):
                return True
            node = parent
        return False

    runtime = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom)
        and n.module == "specify_cli.consolidation.push_preflight"
        and not under_type_checking(n)
    ]
    assert runtime == []


# --- hollow-review split: force_count -------------------------------------


def test_collect_force_count_warnings_threshold(tmp_path: Path) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps({"work_packages": {
            "WP01": {"force_count": 2},
            "WP02": {"force_count": 1},
            "WP03": {"force_count": "bad"},
        }}),
        encoding="utf-8",
    )
    warnings: HollowReviewWarnings = {}
    preflight._collect_force_count_warnings(tmp_path, {"WP01", "WP02", "WP03"}, warnings)
    assert warnings == {"WP01": ["force_count=2"]}


def test_collect_force_count_warnings_no_status_file(tmp_path: Path) -> None:
    warnings: HollowReviewWarnings = {}
    preflight._collect_force_count_warnings(tmp_path, {"WP01"}, warnings)
    assert warnings == {}


def _write_transition(
    tmp_path: Path, *, wp_id: str, to_lane: str, actor: str, event_id: str, at: str
) -> None:
    with (tmp_path / "status.events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "event_id": event_id,
                    "wp_id": wp_id,
                    "to_lane": to_lane,
                    "from_lane": "planned",
                    "at": at,
                    "actor": actor,
                    "force": False,
                    "execution_mode": "worktree",
                }
            )
            + "\n"
        )


# --- hollow-review: item #9 reviewer-identity disambiguation --------------


def test_latest_actor_for_transition_picks_the_latest_by_timestamp(tmp_path: Path) -> None:
    _write_transition(
        tmp_path, wp_id="WP01", to_lane="in_progress", actor="implementer-a",
        event_id="01A", at="2026-07-21T00:00:00Z",
    )
    # Rework cycle: a second, later claim by a different implementer.
    _write_transition(
        tmp_path, wp_id="WP01", to_lane="in_progress", actor="implementer-b",
        event_id="01B", at="2026-07-21T01:00:00Z",
    )
    assert preflight._latest_actor_for_transition(tmp_path, "WP01", "in_progress") == "implementer-b"


def test_latest_actor_for_transition_no_events_file(tmp_path: Path) -> None:
    assert preflight._latest_actor_for_transition(tmp_path, "WP01", "approved") is None


def test_latest_actor_for_transition_no_matching_wp_or_lane(tmp_path: Path) -> None:
    _write_transition(
        tmp_path, wp_id="WP01", to_lane="in_progress", actor="implementer-a",
        event_id="01A", at="2026-07-21T00:00:00Z",
    )
    assert preflight._latest_actor_for_transition(tmp_path, "WP02", "in_progress") is None
    assert preflight._latest_actor_for_transition(tmp_path, "WP01", "approved") is None


def test_independent_reviewer_confirmed_when_actors_differ(tmp_path: Path) -> None:
    _write_transition(
        tmp_path, wp_id="WP01", to_lane="in_progress", actor="implementer-ivan",
        event_id="01A", at="2026-07-21T00:00:00Z",
    )
    _write_transition(
        tmp_path, wp_id="WP01", to_lane="approved", actor="reviewer-renata",
        event_id="01B", at="2026-07-21T01:00:00Z",
    )
    assert preflight._independent_reviewer_confirmed(tmp_path, "WP01") is True


def test_independent_reviewer_not_confirmed_when_actors_match(tmp_path: Path) -> None:
    _write_transition(
        tmp_path, wp_id="WP01", to_lane="in_progress", actor="implementer-ivan",
        event_id="01A", at="2026-07-21T00:00:00Z",
    )
    _write_transition(
        tmp_path, wp_id="WP01", to_lane="approved", actor="implementer-ivan",
        event_id="01B", at="2026-07-21T01:00:00Z",
    )
    assert preflight._independent_reviewer_confirmed(tmp_path, "WP01") is False


def test_independent_reviewer_not_confirmed_when_actor_unknown(tmp_path: Path) -> None:
    # No in_progress transition at all -- absence of evidence must not
    # suppress the warning.
    _write_transition(
        tmp_path, wp_id="WP01", to_lane="approved", actor="reviewer-renata",
        event_id="01B", at="2026-07-21T01:00:00Z",
    )
    assert preflight._independent_reviewer_confirmed(tmp_path, "WP01") is False


def test_collect_force_count_warnings_suppressed_when_reviewer_differs(tmp_path: Path) -> None:
    """The field-reported false positive: force_count>=2 alone used to warn
    regardless of whether the review was genuinely independent."""
    (tmp_path / "status.json").write_text(
        json.dumps({"work_packages": {"WP01": {"force_count": 3}}}), encoding="utf-8"
    )
    _write_transition(
        tmp_path, wp_id="WP01", to_lane="in_progress", actor="implementer-ivan",
        event_id="01A", at="2026-07-21T00:00:00Z",
    )
    _write_transition(
        tmp_path, wp_id="WP01", to_lane="approved", actor="reviewer-renata",
        event_id="01B", at="2026-07-21T01:00:00Z",
    )
    warnings: HollowReviewWarnings = {}
    preflight._collect_force_count_warnings(tmp_path, {"WP01"}, warnings)
    assert warnings == {}


def test_collect_force_count_warnings_kept_when_same_actor(tmp_path: Path) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps({"work_packages": {"WP01": {"force_count": 3}}}), encoding="utf-8"
    )
    _write_transition(
        tmp_path, wp_id="WP01", to_lane="in_progress", actor="implementer-ivan",
        event_id="01A", at="2026-07-21T00:00:00Z",
    )
    _write_transition(
        tmp_path, wp_id="WP01", to_lane="approved", actor="implementer-ivan",
        event_id="01B", at="2026-07-21T01:00:00Z",
    )
    warnings: HollowReviewWarnings = {}
    preflight._collect_force_count_warnings(tmp_path, {"WP01"}, warnings)
    assert warnings == {"WP01": ["force_count=3"]}


def test_collect_force_count_warnings_kept_when_no_event_log(tmp_path: Path) -> None:
    """Fail-safe default: with no event log to check, keep warning as before."""
    (tmp_path / "status.json").write_text(
        json.dumps({"work_packages": {"WP01": {"force_count": 3}}}), encoding="utf-8"
    )
    warnings: HollowReviewWarnings = {}
    preflight._collect_force_count_warnings(tmp_path, {"WP01"}, warnings)
    assert warnings == {"WP01": ["force_count=3"]}


# --- hollow-review split: self-approval -----------------------------------


def test_collect_self_approval_warnings_from_events(tmp_path: Path) -> None:
    # Canonical producer: the self-approval event is written through the
    # lifecycle emitter, not a hand-rolled {event_type, payload} envelope (#1248).
    emit_reviewer_self_approval(
        tmp_path,
        mission_slug="034-test",
        wp_id="WP01",
        implementing_actor="claude",
        intended_reviewer="reviewer-renata",
        failure_reason="timeout",
    )
    # A non-self-approval line proves the collector skips foreign event types.
    # No ``payload`` key -> not an event envelope the canonical-producer rule
    # governs; it is inert noise for this scan.
    with (tmp_path / "status.events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event_type": "other", "wp_id": "WP01"}) + "\n")

    warnings: HollowReviewWarnings = {}
    preflight._collect_self_approval_warnings(tmp_path, {"WP01"}, warnings)
    assert "WP01" in warnings
    assert "ReviewerSelfApproval" in warnings["WP01"][0]
    assert "reviewer-renata failed: timeout" in warnings["WP01"][0]


def test_collect_hollow_review_warnings_merges_both_sources(tmp_path: Path) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps({"work_packages": {"WP01": {"force_count": 3}}}), encoding="utf-8"
    )
    emit_reviewer_self_approval(
        tmp_path,
        mission_slug="034-test",
        wp_id="WP01",
        implementing_actor="claude",
        intended_reviewer="reviewer-renata",
        failure_reason="timeout",
    )
    result = preflight._collect_hollow_review_warnings(tmp_path, ["WP01"])
    assert result["WP01"][0] == "force_count=3"
    assert "ReviewerSelfApproval" in result["WP01"][1]


# --- review-artifact gate: both branches -----------------------------------


def test_enforce_review_artifact_consistency_passes(tmp_path: Path) -> None:
    class _Result:
        passed = True
        findings: list[object] = []

    with patch.object(preflight, "run_review_artifact_consistency_preflight", return_value=_Result()):
        # No exception means the gate passed.
        preflight._enforce_review_artifact_consistency(
            repo_root=tmp_path, feature_dir=tmp_path, mission_slug="m", wp_ids=["WP01"]
        )


def test_enforce_review_artifact_consistency_blocks(tmp_path: Path) -> None:
    class _Result:
        passed = False
        findings = ["finding"]

    diag = {
        "diagnostic_code": "REJECTED_REVIEW_ARTIFACT_CONFLICT",
        "branch_or_work_package": "WP01",
        "violated_invariant": "x",
        "latest_review_cycle_path": "p",
        "remediation": ["fix it"],
    }
    with (
        patch.object(preflight, "run_review_artifact_consistency_preflight", return_value=_Result()),
        patch.object(preflight, "review_artifact_finding_diagnostic", return_value=diag),
        patch.object(preflight, "format_review_artifact_finding", return_value="bad"),
        pytest.raises(typer.Exit) as exc,
    ):
        preflight._enforce_review_artifact_consistency(
            repo_root=tmp_path, feature_dir=tmp_path, mission_slug="m", wp_ids=["WP01"]
        )
    assert exc.value.exit_code == 1


# --- target-branch validation ----------------------------------------------


def test_validate_target_branch_passes_when_local_exists(tmp_path: Path) -> None:
    with patch.object(preflight, "run_command", return_value=(0, "", "")):
        preflight._validate_target_branch(tmp_path, "m", "main", "cli", json_output=False)


def test_validate_target_branch_raises_when_missing(tmp_path: Path) -> None:
    with (
        patch.object(preflight, "run_command", return_value=(1, "", "")),
        pytest.raises(typer.Exit) as exc,
    ):
        preflight._validate_target_branch(tmp_path, "m", "main", "meta.json", json_output=True)
    assert exc.value.exit_code == 1


# --- mission-branch check ---------------------------------------------------


def test_check_mission_branch_present_and_missing(tmp_path: Path) -> None:
    with patch.object(preflight, "_has_branch_ref", return_value=True):
        ready, blocker = preflight._check_mission_branch("m", tmp_path, expected_branch="kitty/mission-m")
    assert ready is True and blocker is None

    with (
        patch.object(preflight, "_has_branch_ref", return_value=False),
        patch.object(preflight, "run_command", return_value=(0, "abc123def456789", "")),
    ):
        ready, blocker = preflight._check_mission_branch("m", tmp_path, expected_branch="kitty/mission-m")
    assert ready is False
    assert blocker is not None
    assert blocker["blocker"] == "missing_mission_branch"
    assert blocker["expected_branch"] == "kitty/mission-m"


# --- effective push intent --------------------------------------------------


def test_effective_push_requested_prefers_persisted_state(tmp_path: Path) -> None:
    st = ConsolidationState(mission_id="01ID", mission_slug="m", target_branch="main", wp_order=[], push_requested=True)
    with patch.object(preflight, "load_state", return_value=st):
        assert preflight._effective_push_requested(tmp_path, "01ID", False) is True
    with patch.object(preflight, "load_state", return_value=None):
        assert preflight._effective_push_requested(tmp_path, "01ID", True) is True
        assert preflight._effective_push_requested(tmp_path, "01ID", False) is False


# --- target_branch_sync_remediation (behind / diverged / ahead) -------------


def _sync_status(
    state: str, ahead: int, behind: int, tracking: str | None = "origin/main"
) -> SimpleNamespace:
    return SimpleNamespace(
        target_branch="main",
        state=state,
        ahead_count=ahead,
        behind_count=behind,
        tracking_branch=tracking,
    )


def test_remediation_behind_recommends_update_not_push() -> None:
    lines = preflight.target_branch_sync_remediation(
        _sync_status("behind", 0, 3),
        mission_slug="m",
        mission_branch="kitty/mission-m-deadbeef",
    )
    joined = "\n".join(lines)
    assert "update local 'main'" in joined
    # Focused PR path emitted because mission_slug is provided.
    assert any("git switch -c" in ln for ln in lines)


def test_remediation_diverged_recommends_focused_pr() -> None:
    lines = preflight.target_branch_sync_remediation(
        _sync_status("diverged", 2, 2), mission_slug="m",
        mission_branch="kitty/mission-m-deadbeef",
    )
    joined = "\n".join(lines)
    assert "focused PR path" in joined
    assert "kitty/mission-m-deadbeef" in joined


def test_remediation_without_slug_emits_generic_hint() -> None:
    lines = preflight.target_branch_sync_remediation(
        _sync_status("ahead", 1, 0, tracking=None), mission_slug=None,
    )
    joined = "\n".join(lines)
    assert "preserve them on a new PR branch" in joined
    # Falls back to origin/<target> when tracking_branch is absent.
    assert "origin/main" in joined


# --- _enforce_planning_artifact_target_branch -------------------------------


def test_enforce_planning_artifact_on_target_branch_passes(tmp_path: Path) -> None:
    with patch.object(preflight, "run_command", return_value=(0, "main", "")):
        preflight._enforce_planning_artifact_target_branch(tmp_path, "main")


def test_enforce_planning_artifact_wrong_branch_exits(tmp_path: Path) -> None:
    with (
        patch.object(preflight, "run_command", return_value=(0, "feature-x", "")),
        pytest.raises(typer.Exit) as exc,
    ):
        preflight._enforce_planning_artifact_target_branch(tmp_path, "main")
    assert exc.value.exit_code == 1


def test_enforce_planning_artifact_detached_head_exits(tmp_path: Path) -> None:
    # rev-parse fails -> current_branch empty -> "detached HEAD" label.
    with (
        patch.object(preflight, "run_command", return_value=(1, "", "fatal")),
        pytest.raises(typer.Exit) as exc,
    ):
        preflight._enforce_planning_artifact_target_branch(tmp_path, "main")
    assert exc.value.exit_code == 1


# --- _enforce_git_preflight -------------------------------------------------


def test_enforce_git_preflight_skips_without_dotgit(tmp_path: Path) -> None:
    # No .git dir -> early return, never runs preflight.
    with patch.object(preflight, "run_git_preflight") as pf_mock:
        preflight._enforce_git_preflight(tmp_path, json_output=False)
    pf_mock.assert_not_called()


def test_enforce_git_preflight_passes(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    with patch.object(preflight, "run_git_preflight", return_value=SimpleNamespace(passed=True)):
        preflight._enforce_git_preflight(tmp_path, json_output=False)


def test_enforce_git_preflight_fails_human_channel(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    payload = {"error": "dirty tree", "remediation": ["git stash"]}
    with (
        patch.object(preflight, "run_git_preflight", return_value=SimpleNamespace(passed=False)),
        patch.object(preflight, "build_git_preflight_failure_payload", return_value=payload),
        pytest.raises(typer.Exit) as exc,
    ):
        preflight._enforce_git_preflight(tmp_path, json_output=False)
    assert exc.value.exit_code == 1


def test_enforce_git_preflight_fails_json_channel(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / ".git").mkdir()
    payload = {"error": "dirty tree", "remediation": ["git stash"]}
    with (
        patch.object(preflight, "run_git_preflight", return_value=SimpleNamespace(passed=False)),
        patch.object(preflight, "build_git_preflight_failure_payload", return_value=payload),
        pytest.raises(typer.Exit),
    ):
        preflight._enforce_git_preflight(tmp_path, json_output=True)
    out = capsys.readouterr().out
    assert "spec_kitty_version" in out


# --- _validate_target_branch: remote-exists + source-message branches -------


def test_validate_target_branch_passes_when_remote_exists(tmp_path: Path) -> None:
    # local missing (ret 1), remote present (ret 0) -> passes.
    rets = iter([(1, "", ""), (0, "", "")])
    with patch.object(preflight, "run_command", side_effect=lambda *a, **k: next(rets)):
        preflight._validate_target_branch(tmp_path, "m", "main", "cli", json_output=False)


def test_validate_target_branch_primary_branch_source_message(tmp_path: Path) -> None:
    rets = iter([(1, "", ""), (1, "", "")])
    with (
        patch.object(preflight, "run_command", side_effect=lambda *a, **k: next(rets)),
        pytest.raises(typer.Exit) as exc,
    ):
        preflight._validate_target_branch(tmp_path, "m", "main", "primary_branch", json_output=False)
    assert exc.value.exit_code == 1


def test_validate_target_branch_generic_message_without_slug(tmp_path: Path) -> None:
    rets = iter([(1, "", ""), (1, "", "")])
    with (
        patch.object(preflight, "run_command", side_effect=lambda *a, **k: next(rets)),
        pytest.raises(typer.Exit) as exc,
    ):
        preflight._validate_target_branch(tmp_path, None, "main", None, json_output=False)
    assert exc.value.exit_code == 1


# --- _print_remediation_lines -----------------------------------------------


def test_print_remediation_lines_list_and_scalar(capsys: pytest.CaptureFixture[str]) -> None:
    preflight._print_remediation_lines(["one", "two"])
    preflight._print_remediation_lines("single")
    out = capsys.readouterr().out
    assert "one" in out and "two" in out and "single" in out


# --- _enforce_canonical_status_history --------------------------------------


def test_canonical_status_history_noop_without_wps(tmp_path: Path) -> None:
    # Empty wp_ids -> early return regardless of log presence.
    preflight._enforce_canonical_status_history(
        feature_dir=tmp_path, mission_slug="m", wp_ids=[]
    )


def test_canonical_status_history_noop_without_log(tmp_path: Path) -> None:
    # Log file absent -> early return.
    preflight._enforce_canonical_status_history(
        feature_dir=tmp_path, mission_slug="m", wp_ids=["WP01"]
    )


def test_canonical_status_history_bootstrap_only_exits(tmp_path: Path) -> None:
    (tmp_path / "status.events.jsonl").write_text("{}\n", encoding="utf-8")
    with (
        patch("specify_cli.status.has_non_bootstrap_status_history", return_value=False),
        pytest.raises(typer.Exit) as exc,
    ):
        preflight._enforce_canonical_status_history(
            feature_dir=tmp_path, mission_slug="m", wp_ids=["WP01"]
        )
    assert exc.value.exit_code == 1


def test_canonical_status_history_passes_with_real_history(tmp_path: Path) -> None:
    (tmp_path / "status.events.jsonl").write_text("{}\n", encoding="utf-8")
    with patch("specify_cli.status.has_non_bootstrap_status_history", return_value=True):
        preflight._enforce_canonical_status_history(
            feature_dir=tmp_path, mission_slug="m", wp_ids=["WP01"]
        )


# --- review-artifact gate: schema_error + verdict diagnostic keys -----------


def test_enforce_review_artifact_blocks_with_optional_keys(tmp_path: Path) -> None:
    class _Result:
        passed = False
        findings = ["finding"]

    diag = {
        "diagnostic_code": "REVIEW_ARTIFACT_SCHEMA_INVALID",
        "branch_or_work_package": "WP01",
        "violated_invariant": "x",
        "latest_review_cycle_path": "p",
        "latest_review_cycle_verdict": "rejected",
        "schema_error": "bad frontmatter",
        "remediation": "fix it",  # scalar -> normalized to list
    }
    with (
        patch.object(preflight, "run_review_artifact_consistency_preflight", return_value=_Result()),
        patch.object(preflight, "review_artifact_finding_diagnostic", return_value=diag),
        patch.object(preflight, "format_review_artifact_finding", return_value="bad"),
        pytest.raises(typer.Exit) as exc,
    ):
        preflight._enforce_review_artifact_consistency(
            repo_root=tmp_path, feature_dir=tmp_path, mission_slug="m", wp_ids=["WP01"]
        )
    assert exc.value.exit_code == 1


# --- hollow-review confirm flow ---------------------------------------------


def test_warn_or_confirm_noop_without_warnings(tmp_path: Path) -> None:
    with patch.object(preflight, "_collect_hollow_review_warnings", return_value={}):
        preflight._warn_or_confirm_hollow_reviews(
            feature_dir=tmp_path, wp_ids=["WP01"], assume_yes=False
        )


def test_warn_or_confirm_proceeds_with_assume_yes(tmp_path: Path) -> None:
    with patch.object(preflight, "_collect_hollow_review_warnings", return_value={"WP01": ["force_count=2"]}):
        # assume_yes short-circuits the interactive confirm without raising.
        preflight._warn_or_confirm_hollow_reviews(
            feature_dir=tmp_path, wp_ids=["WP01"], assume_yes=True
        )


def test_warn_or_confirm_aborts_when_user_declines(tmp_path: Path) -> None:
    with (
        patch.object(preflight, "_collect_hollow_review_warnings", return_value={"WP01": ["force_count=2"]}),
        # #2912: the gate now routes through is_interactive(); force the
        # interactive confirm path via the documented escape hatch.
        patch.dict("os.environ", {"SPEC_KITTY_FORCE_INTERACTIVE": "1"}),
        patch.object(preflight.typer, "confirm", return_value=False),
        pytest.raises(typer.Exit) as exc,
    ):
        preflight._warn_or_confirm_hollow_reviews(
            feature_dir=tmp_path, wp_ids=["WP01"], assume_yes=False
        )
    assert exc.value.exit_code == 1


# --- self-approval collector: non-dict payload / wp filter / OSError --------


def test_collect_self_approval_skips_non_matching_and_malformed(tmp_path: Path) -> None:
    # A real (canonical-emitted) self-approval for a WP outside the target set:
    # exercises the wp-not-in-set skip branch without a hand-rolled envelope.
    emit_reviewer_self_approval(
        tmp_path,
        mission_slug="034-test",
        wp_id="WP99",
        implementing_actor="claude",
        intended_reviewer="reviewer-renata",
        failure_reason="timeout",
    )
    # A self-approval envelope whose payload is a scalar exercises the defensive
    # "payload not dict" branch. The canonical emitter cannot represent this
    # shape (that's the point of the test), so the envelope is assembled key by
    # key -- no single literal carries both ``event_type`` and ``payload``.
    scalar_envelope: dict[str, object] = {"event_type": REVIEWER_SELF_APPROVAL}
    scalar_envelope["payload"] = "scalar"
    with (tmp_path / "status.events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write("{not json\n")  # JSONDecodeError -> skipped
        fh.write(json.dumps(["not", "a", "dict"]) + "\n")  # not a dict -> skipped
        fh.write(json.dumps(scalar_envelope) + "\n")  # payload not dict -> skipped

    warnings: HollowReviewWarnings = {}
    preflight._collect_self_approval_warnings(tmp_path, {"WP01"}, warnings)
    assert warnings == {}


def test_collect_self_approval_no_events_file(tmp_path: Path) -> None:
    warnings: HollowReviewWarnings = {}
    preflight._collect_self_approval_warnings(tmp_path, {"WP01"}, warnings)
    assert warnings == {}


def test_collect_force_count_warnings_non_dict_work_packages(tmp_path: Path) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps({"work_packages": ["not", "a", "dict"]}), encoding="utf-8"
    )
    warnings: HollowReviewWarnings = {}
    preflight._collect_force_count_warnings(tmp_path, {"WP01"}, warnings)
    assert warnings == {}


def test_collect_force_count_warnings_corrupt_json(tmp_path: Path) -> None:
    (tmp_path / "status.json").write_text("{not valid", encoding="utf-8")
    warnings: HollowReviewWarnings = {}
    preflight._collect_force_count_warnings(tmp_path, {"WP01"}, warnings)
    assert warnings == {}
