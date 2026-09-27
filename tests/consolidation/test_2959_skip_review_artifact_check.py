"""#2959 (WP01 / FR-002): merge review-artifact gate escape hatch.

``spec-kitty merge`` had no way to proceed past a review-artifact rejection even
when an operator legitimately wants to override it — the coord deadlock had no
release valve. This adds ``--skip-review-artifact-check`` (with a mandatory
``--note``) that bypasses the gate WITHOUT silently swallowing it: the skip is
recorded as durable ``ReviewOverride`` evidence in the append-only status log,
so the override is auditable exactly like an ordinary review override.

These tests drive the gate seam (``_enforce_review_artifact_consistency``)
directly — the tightest surface that proves both halves (bypass + recorded
evidence) — plus a CLI-boundary guard test proving ``--skip-review-artifact-check``
without ``--note`` is refused (never a silent bypass).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from specify_cli.consolidation.preflight import _enforce_review_artifact_consistency
from specify_cli.status import materialize
from specify_cli.status.models import Lane, ReviewOverride, ReviewResult, StatusEvent
from specify_cli.status.store import append_event

# These are fast unit/CLI tests (tmp_path + status store + CliRunner; no real
# git worktree), so they run in ``fast-tests-merge`` (-m "fast and not
# windows_ci"). Without a marker the file is orphaned — selected by no
# push-to-main job (test_ci_collection_completeness / test_same_tier_uniqueness).
pytestmark = pytest.mark.fast

_MISSION_SLUG = "skip-review-artifact-2959"
_MISSION_ID = "01KZSKIP2959000000000000AA"
_WP_ID = "WP01"
_NOTE = "Operator override: gate false-positive on a stale rejection (#2959)."


def _feature_dir_with_blocking_rejection(root: Path) -> Path:
    """Build a feature_dir whose event log carries a CURRENT rejection verdict.

    The pure-event review-artifact gate blocks on a WP whose reduced
    ``review_result`` slot records ``changes_requested`` — so seed exactly that.
    """
    feature_dir = root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": _MISSION_SLUG}),
        encoding="utf-8",
    )
    event = StatusEvent(
        event_id="01KZSKIP2959EVENT0000000001",
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id=_WP_ID,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        at="2026-08-15T12:00:00Z",
        actor="operator",
        force=False,
        execution_mode="worktree",
        reason="approved for merge",
        review_result=ReviewResult(
            reviewer="reviewer-renata", verdict="changes_requested", reference="x"
        ),
    )
    append_event(feature_dir, event)
    return feature_dir


def test_gate_blocks_without_skip(tmp_path: Path) -> None:
    """Control: a current rejection blocks the merge when the gate is not skipped."""
    feature_dir = _feature_dir_with_blocking_rejection(tmp_path)
    with pytest.raises(typer.Exit):
        _enforce_review_artifact_consistency(
            repo_root=tmp_path,
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            wp_ids=[_WP_ID],
        )
    # The skip did not run, so no override evidence was recorded.
    review_slot = materialize(feature_dir).work_packages[_WP_ID].get("review")
    assert review_slot is None


def test_skip_bypasses_gate_and_records_evidence(tmp_path: Path) -> None:
    """``--skip-review-artifact-check --note`` clears the gate AND records evidence.

    RED (pre-WP01): the gate has no skip parameter — the call raises regardless.
    GREEN (post-WP01): with ``skip_review_artifact_check=True`` the gate does not
    raise, and it records a complete ``ReviewOverride`` carrying the operator note
    as durable evidence in the status log.
    """
    feature_dir = _feature_dir_with_blocking_rejection(tmp_path)

    # Bypass: must NOT raise.
    _enforce_review_artifact_consistency(
        repo_root=tmp_path,
        feature_dir=feature_dir,
        mission_slug=_MISSION_SLUG,
        wp_ids=[_WP_ID],
        skip_review_artifact_check=True,
        skip_note=_NOTE,
    )

    # Evidence: a complete override carrying the note is now in the status log.
    review_slot = materialize(feature_dir).work_packages[_WP_ID].get("review")
    assert review_slot is not None, (
        "the skip must record durable override evidence, not silently bypass"
    )
    override = ReviewOverride.from_dict(review_slot)
    assert override.complete
    assert override.reason == _NOTE
    assert override.wp_id == _WP_ID


def test_cli_skip_requires_note(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ``merge`` CLI refuses ``--skip-review-artifact-check`` without ``--note``.

    A skip is never silent: withholding the note is refused at the CLI boundary
    with a non-zero exit, before any merge work runs.
    """
    from typer.testing import CliRunner

    import specify_cli.cli.commands.consolidate as merge_mod

    app = typer.Typer()
    app.command()(merge_mod.consolidate)

    # Keep the guard the only thing that can fire: point the command at a repo
    # root and stub the real merge so a green path would otherwise proceed.
    monkeypatch.setattr(merge_mod, "find_repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        merge_mod, "_run_real_merge", lambda *a, **k: None
    )

    result = CliRunner().invoke(app, ["--skip-review-artifact-check"])
    assert result.exit_code != 0
    assert "note" in result.output.lower()
