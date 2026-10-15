"""Unit tests for merge-time hollow review warnings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands.consolidate import (
    _collect_hollow_review_warnings,
    _warn_or_confirm_hollow_reviews,
)
from specify_cli.status.lifecycle_events import emit_reviewer_self_approval

pytestmark = pytest.mark.fast


def test_collect_hollow_review_warnings_reads_force_count_and_self_approval(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.json").write_text(
        json.dumps({"work_packages": {"WP01": {"force_count": 3}, "WP02": {"force_count": 0}}}),
        encoding="utf-8",
    )
    emit_reviewer_self_approval(
        feature_dir,
        mission_slug="034-test",
        wp_id="WP02",
        implementing_actor="codex",
        intended_reviewer="claude",
        failure_reason="exit 1",
    )

    warnings = _collect_hollow_review_warnings(feature_dir, ["WP01", "WP02", "WP03"])

    assert warnings["WP01"] == ["force_count=3"]
    assert warnings["WP02"] == ["ReviewerSelfApproval (claude failed: exit 1; codex self-reviewed)"]
    assert "WP03" not in warnings


def test_warn_or_confirm_hollow_reviews_assume_yes_does_not_prompt(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--yes`` skips the confirm prompt even at an interactive terminal.

    The terminal is forced interactive and the prompt would decline, so the
    merge proceeds only because ``assume_yes`` short-circuits the prompt (under
    pytest's non-TTY stdin the non-interactive arm alone would proceed).
    """
    monkeypatch.setenv("SPEC_KITTY_FORCE_INTERACTIVE", "1")
    prompts: list[str] = []

    def _declining_confirm(text: str, **_kwargs: object) -> bool:
        prompts.append(text)
        return False

    monkeypatch.setattr(typer, "confirm", _declining_confirm)
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.json").write_text(
        json.dumps({"work_packages": {"WP01": {"force_count": 2}}}),
        encoding="utf-8",
    )

    _warn_or_confirm_hollow_reviews(feature_dir=feature_dir, wp_ids=["WP01"], assume_yes=True)

    out = capsys.readouterr().out
    assert "Hollow reviews detected" in out
    assert "Proceeding without interactive confirmation" in out
    assert prompts == []


def test_warn_or_confirm_hollow_reviews_non_interactive_env_does_not_prompt(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#2912: with SPEC_KITTY_NON_INTERACTIVE set the hollow-review gate
    auto-proceeds without a confirm prompt even without --yes. Before routing
    through is_interactive(), the bare ``sys.stdin.isatty()`` check would prompt
    (and could hang an agent) whenever stdin merely looked like a TTY."""
    monkeypatch.setenv("SPEC_KITTY_NON_INTERACTIVE", "1")
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.json").write_text(
        json.dumps({"work_packages": {"WP01": {"force_count": 2}}}),
        encoding="utf-8",
    )

    _warn_or_confirm_hollow_reviews(feature_dir=feature_dir, wp_ids=["WP01"], assume_yes=False)

    out = capsys.readouterr().out
    assert "Hollow reviews detected" in out
    assert "Proceeding without interactive confirmation" in out


def _write_force_history(feature_dir: Path, wp_id: str, review_refs: list[str | None], *, force_count: int) -> None:
    """status.json reporting ``force_count`` plus the forced rewinds behind it.

    Implementer and approver are the same actor, so the independent-reviewer
    suppression does not apply and only the force signal decides.
    """
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.json").write_text(
        json.dumps({"work_packages": {wp_id: {"force_count": force_count}}}),
        encoding="utf-8",
    )
    events = [{"event_id": "e00", "wp_id": wp_id, "actor": "claude", "from_lane": "planned", "to_lane": "in_progress"}]
    for n, ref in enumerate(review_refs, 1):
        events += [
            {"event_id": f"f{n:02d}", "wp_id": wp_id, "actor": "claude", "force": True, "from_lane": "for_review", "to_lane": "planned", "review_ref": ref},
            {"event_id": f"p{n:02d}", "wp_id": wp_id, "actor": "claude", "from_lane": "planned", "to_lane": "in_progress"},
        ]
    events.append({"event_id": "a00", "wp_id": wp_id, "actor": "claude", "from_lane": "in_review", "to_lane": "approved"})
    (feature_dir / "status.events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def test_documented_rejections_do_not_count_as_hollow_review(tmp_path: Path) -> None:
    """#2267: the --force a documented rejection requires is not hollow-review evidence."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    refs = ["review-cycle://034-test/WP01/review-cycle-1.md", "review-cycle://034-test/WP01/review-cycle-2.md"]
    _write_force_history(feature_dir, "WP01", refs, force_count=2)

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {}


def test_undocumented_forcing_still_warns(tmp_path: Path) -> None:
    """Non-vacuity: forced rewinds with only the force-override sentinel still warn."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_force_history(feature_dir, "WP01", ["force-override", None], force_count=2)

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=2"]}


def test_an_attested_approval_does_not_confirm_an_independent_review(tmp_path: Path) -> None:
    """#5668: ``--attest-approved-reviewed`` records an operator's forced ``approved -> approved``; it is not a review, so the warning stays."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_force_history(feature_dir, "WP01", ["force-override", None], force_count=2)
    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=2"]}
    attestation = {
        "event_id": "z99",
        "wp_id": "WP01",
        "actor": "operator",
        "force": True,
        "from_lane": "approved",
        "to_lane": "approved",
        "policy_metadata": {"attestation": "approved_reviewed"},
    }
    with (feature_dir / "status.events.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(attestation) + "\n")

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=2"]}


def test_mixed_forcing_reports_the_undocumented_count(tmp_path: Path) -> None:
    """Only the undocumented forced transitions count towards the threshold."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    refs = ["review-cycle://034-test/WP01/review-cycle-1.md", None, None]
    _write_force_history(feature_dir, "WP01", refs, force_count=3)

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=2"]}


def test_duplicate_rejection_lines_are_discounted_once(tmp_path: Path) -> None:
    """A merged log may repeat an event line; the reducer dedupes by event_id."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    refs = ["review-cycle://034-test/WP01/review-cycle-1.md", None, None]
    _write_force_history(feature_dir, "WP01", refs, force_count=3)
    events_path = feature_dir / "status.events.jsonl"
    first_rejection = events_path.read_text(encoding="utf-8").splitlines()[1]
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(first_rejection + "\n")

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=2"]}


def test_missing_event_log_keeps_the_raw_force_count(tmp_path: Path) -> None:
    """No event log to correlate with: fail toward the warning."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_force_history(feature_dir, "WP01", ["review-cycle://034-test/WP01/review-cycle-1.md"] * 2, force_count=2)
    (feature_dir / "status.events.jsonl").unlink()

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=2"]}


def test_review_claims_do_not_count_as_hollow_review(tmp_path: Path) -> None:
    """#2267: forced review claims (for_review -> in_progress) are the review path."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_force_history(feature_dir, "WP01", [], force_count=2)
    claims = [
        {"event_id": f"c{n}", "wp_id": "WP01", "actor": "claude", "force": True, "from_lane": "for_review", "to_lane": "in_progress", "review_ref": marker}
        for n, marker in enumerate(("action-review-claim", "workflow-review-claim"))
    ]
    with (feature_dir / "status.events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps(c) for c in claims) + "\n")

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {}


def test_malformed_event_lines_are_skipped(tmp_path: Path) -> None:
    """Garbage and non-object lines neither crash nor discount."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_force_history(feature_dir, "WP01", ["review-cycle://034-test/WP01/review-cycle-1.md", None, None], force_count=3)
    with (feature_dir / "status.events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("not json\n[1, 2]\n\n")

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=2"]}


def _loop_event(event_id: str, actor: str, from_lane: str, to_lane: str, *, review_ref: str | None = None) -> dict[str, object]:
    event: dict[str, object] = {"event_id": event_id, "wp_id": "WP01", "actor": actor, "from_lane": from_lane, "to_lane": to_lane}
    if review_ref:
        event.update({"force": True, "review_ref": review_ref})
    return event


def _write_loop(feature_dir: Path, steps: list[tuple[str, str, str]], *, force_count: int = 4) -> None:
    """status.json plus an event log of ``(actor, from, to)`` steps; the third arg may carry ``@ref``."""
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.json").write_text(
        json.dumps({"work_packages": {"WP01": {"force_count": force_count}}}), encoding="utf-8"
    )
    events = []
    for n, (actor, src, dst) in enumerate(steps):
        to_lane, _, ref = dst.partition("@")
        events.append(_loop_event(f"e{n:02d}", actor, src, to_lane, review_ref=ref or None))
    (feature_dir / "status.events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _loop_steps(implementer: str, reviewer: str) -> list[tuple[str, str, str]]:
    return [
        (implementer, "planned", "claimed"),
        (implementer, "claimed", "in_progress"),
        (implementer, "in_progress", "for_review"),
        (reviewer, "for_review", "in_review"),
        (reviewer, "in_review", "in_progress@review-cycle-1.md"),
        (implementer, "in_progress", "for_review"),
        (reviewer, "for_review", "in_review"),
        (reviewer, "in_review", "approved"),
    ]


@pytest.mark.regression
def test_rework_loop_with_independent_reviewer_does_not_warn(tmp_path: Path) -> None:
    """#5340: the reviewer's rework verdict (``in_review -> in_progress``) is not an implementation claim.

    Read as one, the reviewer became "the implementer" and approving made them
    look like a self-reviewer, so an honest reject -> rework -> approve loop
    raised a false hollow-review warning.
    """
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_loop(feature_dir, _loop_steps("claude", "codex"))

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {}


def test_rework_loop_where_the_implementer_approves_still_warns(tmp_path: Path) -> None:
    """Non-vacuity: the implementer approving its own work still warns."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_loop(feature_dir, _loop_steps("claude", "claude"))

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=3"]}


def test_same_tool_different_profile_pair_does_not_newly_warn(tmp_path: Path) -> None:
    """Full-identity comparison is kept: one tool with two profiles is not a self-review (H3)."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_loop(
        feature_dir,
        _loop_steps("claude:opus:implementer-ivan:implementer", "claude:opus:reviewer-renata:reviewer"),
    )

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {}


def _dict_actor(tool: str, *, profile: str | None = None, role: str | None = None) -> dict[str, str | None]:
    return {"model": None, "profile": profile, "role": role, "tool": tool}


def _write_dict_loop(feature_dir: Path, implementer: object, reviewer: object) -> None:
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.json").write_text(json.dumps({"work_packages": {"WP01": {"force_count": 3}}}), encoding="utf-8")
    lanes = [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review"), ("for_review", "in_review")]
    events = [
        {"event_id": f"e{n}", "wp_id": "WP01", "actor": implementer, "from_lane": a, "to_lane": b}
        for n, (a, b) in enumerate(lanes)
    ]
    events.append({"event_id": "e9", "wp_id": "WP01", "actor": reviewer, "from_lane": "in_review", "to_lane": "approved"})
    (feature_dir / "status.events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def test_dict_actor_self_approval_still_warns(tmp_path: Path) -> None:
    """The same structured actor implementing and approving is a self-review (#5340)."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    actor = _dict_actor("claude", role="implementer")
    _write_dict_loop(feature_dir, actor, actor)

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=3"]}


def test_same_tool_dict_actors_with_different_profiles_do_not_warn(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_dict_loop(
        feature_dir,
        _dict_actor("claude", profile="implementer-ivan", role="implementer"),
        _dict_actor("claude", profile="reviewer-renata", role="reviewer"),
    )

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {}


@pytest.mark.regression
@pytest.mark.parametrize(
    ("implementer", "reviewer"),
    [
        pytest.param(_dict_actor("claude", role="implementer"), _dict_actor("claude", role="reviewer"), id="dict-roles"),
        pytest.param("claude", _dict_actor("claude", role="reviewer"), id="compact-and-dict"),
        pytest.param("claude:opus:ivan:implementer", {"tool": "claude", "model": "opus", "profile": "ivan", "role": "reviewer"}, id="full-compact-and-dict"),
    ],
)
def test_the_same_tool_model_and_profile_is_a_self_review_whatever_the_role(tmp_path: Path, implementer: object, reviewer: object) -> None:
    """#5340: the claim stamps role implementer and the approval role reviewer; the role never makes two actors different."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_dict_loop(feature_dir, implementer, reviewer)

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=3"]}


@pytest.mark.regression
def test_the_approving_reviewer_is_the_latest_appended_approval_whatever_the_clock_says(tmp_path: Path) -> None:
    """A skewed wall clock must not let an earlier-appended approval outrank a later one.

    ADR 2026-02-09-3 orders events causally, not by timestamp: the second approval is
    appended after the first, so its reviewer is the approving one even though its ``at`` is earlier.
    """
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.json").write_text(json.dumps({"work_packages": {"WP01": {"force_count": 3}}}), encoding="utf-8")
    steps = [
        ("e0", "claude", "planned", "claimed", "2026-10-07T10:00:00+00:00"),
        ("e1", "claude", "claimed", "in_progress", "2026-10-07T10:01:00+00:00"),
        ("e2", "claude", "in_progress", "for_review", "2026-10-07T10:02:00+00:00"),
        ("e3", "claude", "in_review", "approved", "2026-10-07T12:00:00+00:00"),  # self-approval, clock ahead
        ("e4", "codex", "in_review", "approved", "2026-10-07T11:00:00+00:00"),  # appended later, clock behind
    ]
    events = [{"event_id": i, "wp_id": "WP01", "actor": a, "from_lane": f, "to_lane": t, "at": at} for i, a, f, t, at in steps]
    (feature_dir / "status.events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {}


_BACKFILL_SEED = "migration:backfill_runtime_state"
_VERDICT_SEED = "migration:verdict_provenance_backfill"
_CLAIM_SEED = (_BACKFILL_SEED, "planned", "claimed")
_APPROVAL_SEED = (_VERDICT_SEED, "in_review", "approved")


@pytest.mark.regression
def test_an_appended_claim_seed_does_not_make_a_self_review_look_independent(tmp_path: Path) -> None:
    """#6257: a backfill claim seed appended last is not the implementer, so a self-review still warns."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_loop(feature_dir, [*_loop_steps("claude", "claude"), _CLAIM_SEED])

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=3"]}


@pytest.mark.regression
def test_an_appended_approval_seed_is_not_the_approving_reviewer(tmp_path: Path) -> None:
    """#6257 / FR-009: a ``verdict_provenance_backfill`` seed into ``approved`` restates a verdict; it is not a review."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_loop(feature_dir, [*_loop_steps("claude", "claude"), _APPROVAL_SEED])

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=3"]}


def test_an_independent_review_with_both_seeds_still_does_not_warn(tmp_path: Path) -> None:
    """#6257 positive control: the same seeds around a genuinely independent loop leave no warning."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_loop(feature_dir, [*_loop_steps("claude", "codex"), _CLAIM_SEED, _APPROVAL_SEED])

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {}


@pytest.mark.regression
def test_a_seeds_only_implementer_leaves_independence_unconfirmed(tmp_path: Path) -> None:
    """#6257: with no real implementer on record (generic ``user`` plus a seed), independence is not confirmed, so the force signal warns."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    _write_loop(feature_dir, [*_loop_steps("user", "codex"), _CLAIM_SEED])

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=3"]}


@pytest.mark.regression
def test_a_verdict_seed_alone_never_confirms_an_independent_review(tmp_path: Path) -> None:
    """#6257 / FR-009: a WP whose ONLY approval is a verdict seed has no real approver, so independence is unconfirmed and the force signal warns."""
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    without_real_approval = _loop_steps("claude", "claude")[:-1]
    _write_loop(feature_dir, [*without_real_approval, _APPROVAL_SEED])

    assert _collect_hollow_review_warnings(feature_dir, ["WP01"]) == {"WP01": ["force_count=3"]}
