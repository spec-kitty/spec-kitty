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
