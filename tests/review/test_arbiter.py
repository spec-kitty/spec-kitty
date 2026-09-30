"""Tests for the arbiter checklist and rationale model.

Covers all 14 required test cases for T035.

WP12 (review-cycle-verdict-seam-rebuild-01KZ2W7W, FR-009/FR-010/FR-011,
arbiter-override-retirement, DM-01KZ6X4Y7A3XPK5AJ96AA49XJ9): `_find_review_
cycle_artifact`, `_persist_in_artifact`, and `_persist_standalone_json` were
deleted -- the arbiter's two non-durable, never-committed override
representations (a frontmatter `arbiter_override` block and a standalone
`arbiter-override-N.json` sidecar) are retired into the single, already-
durable, event-sourced `ReviewOverride` on the reduced `review` snapshot
slot. Tests that exercised ONLY those three functions' internals are
deleted below (the behaviour they tested no longer exists anywhere); tests
whose BEHAVIOUR survived -- `persist_arbiter_decision` still resolves the
artifact location and still persists a decision; `get_arbiter_overrides_for_
wp` still returns override data for display -- are rewritten against the
new event-sourced shape, not dropped. Each deletion/rewrite is annotated at
its site.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.review.arbiter import (
    ArbiterCategory,
    ArbiterChecklist,
    ArbiterDecision,
    _derive_category,
    _is_arbiter_override,
    create_arbiter_decision,
    get_arbiter_overrides_for_wp,
    parse_category_from_note,
    persist_arbiter_decision,
)
from specify_cli.status import ReviewOverride, WPInnerStateDelta, emit_inner_state_changed
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    *,
    wp_id: str = "WP01",
    from_lane: Lane,
    to_lane: Lane,
    review_ref: str | None = None,
    force: bool = False,
    mission_slug: str = "066-test",
) -> StatusEvent:
    return StatusEvent(
        event_id="01TESTARBITER000000000000",
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at="2026-04-06T12:00:00+00:00",
        actor="test",
        force=force,
        execution_mode="worktree",
        review_ref=review_ref,
    )


def _write_event(feature_dir: Path, event: StatusEvent) -> None:
    append_event(feature_dir, event)


def _make_checklist(
    *,
    is_pre_existing: bool = False,
    is_correct_context: bool = True,
    is_in_scope: bool = True,
    is_environmental: bool = False,
    should_follow_on: bool = False,
) -> ArbiterChecklist:
    return ArbiterChecklist(
        is_pre_existing=is_pre_existing,
        is_correct_context=is_correct_context,
        is_in_scope=is_in_scope,
        is_environmental=is_environmental,
        should_follow_on=should_follow_on,
    )


# ---------------------------------------------------------------------------
# T1: ArbiterCategory enum values
# ---------------------------------------------------------------------------


def test_arbiter_category_enum_values() -> None:
    """All 5 categories have correct string values."""
    assert ArbiterCategory.PRE_EXISTING_FAILURE == "pre_existing_failure"
    assert ArbiterCategory.WRONG_CONTEXT == "wrong_context"
    assert ArbiterCategory.CROSS_SCOPE == "cross_scope"
    assert ArbiterCategory.INFRA_ENVIRONMENTAL == "infra_environmental"
    assert ArbiterCategory.CUSTOM == "custom"


# ---------------------------------------------------------------------------
# T2: ArbiterChecklist round-trip
# ---------------------------------------------------------------------------


def test_checklist_to_dict_round_trip() -> None:
    """Create, to_dict, from_dict, compare."""
    original = _make_checklist(is_pre_existing=True, should_follow_on=True)
    d = original.to_dict()
    restored = ArbiterChecklist.from_dict(d)
    assert restored == original
    assert d["is_pre_existing"] is True
    assert d["should_follow_on"] is True


# ---------------------------------------------------------------------------
# T3: ArbiterDecision round-trip
# ---------------------------------------------------------------------------


def test_decision_to_dict_round_trip() -> None:
    """Full decision round-trip via to_dict / from_dict."""
    checklist = _make_checklist(is_pre_existing=True)
    decision = ArbiterDecision(
        arbiter="robert",
        category=ArbiterCategory.PRE_EXISTING_FAILURE,
        explanation="Test was already failing since commit abc123",
        checklist=checklist,
        decided_at="2026-04-06T14:00:00+00:00",
    )
    d = decision.to_dict()
    restored = ArbiterDecision.from_dict(d)
    assert restored == decision
    assert d["category"] == "pre_existing_failure"
    assert d["arbiter"] == "robert"


# ---------------------------------------------------------------------------
# T4-T8: Category derivation
# ---------------------------------------------------------------------------


def test_derive_category_pre_existing() -> None:
    """is_pre_existing=True → PRE_EXISTING_FAILURE."""
    cl = _make_checklist(is_pre_existing=True)
    assert _derive_category(cl) == ArbiterCategory.PRE_EXISTING_FAILURE


def test_derive_category_wrong_context() -> None:
    """is_correct_context=False → WRONG_CONTEXT."""
    cl = _make_checklist(is_correct_context=False)
    assert _derive_category(cl) == ArbiterCategory.WRONG_CONTEXT


def test_derive_category_cross_scope() -> None:
    """is_in_scope=False → CROSS_SCOPE."""
    cl = _make_checklist(is_in_scope=False)
    assert _derive_category(cl) == ArbiterCategory.CROSS_SCOPE


def test_derive_category_environmental() -> None:
    """is_environmental=True → INFRA_ENVIRONMENTAL."""
    cl = _make_checklist(is_environmental=True)
    assert _derive_category(cl) == ArbiterCategory.INFRA_ENVIRONMENTAL


def test_derive_category_custom() -> None:
    """All normal answers fall through to CUSTOM."""
    cl = _make_checklist()  # all defaults: no flags set
    assert _derive_category(cl) == ArbiterCategory.CUSTOM


# ---------------------------------------------------------------------------
# T9-T11: Override detection
# ---------------------------------------------------------------------------


def test_is_arbiter_override_after_rejection(tmp_path: Path) -> None:
    """Rejection event + forced rework to for_review → False (#5196: rework is not an override)."""
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    feature_dir.mkdir(parents=True)

    # Simulate: WP01 claimed -> for_review -> planned (rejection with review_ref)
    _write_event(
        feature_dir,
        _make_event(from_lane=Lane.CLAIMED, to_lane=Lane.FOR_REVIEW),
    )
    _write_event(
        feature_dir,
        _make_event(
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.PLANNED,
            review_ref="feedback://066-test/WP01/20260406T120000Z-abc123.md",
        ),
    )

    result = _is_arbiter_override(
        feature_dir=feature_dir,
        wp_id="WP01",
        old_lane="planned",
        target_lane="for_review",
        force=True,
    )
    assert result is False  # re-pinned (#5196): was True


def test_is_arbiter_override_after_rejection_forced_approve(tmp_path: Path) -> None:
    """Rejection event + forced approve → True (#5196: decision target)."""
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    feature_dir.mkdir(parents=True)
    _write_event(
        feature_dir,
        _make_event(
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.PLANNED,
            review_ref="feedback://066-test/WP01/20260406T120000Z-abc123.md",
        ),
    )

    result = _is_arbiter_override(
        feature_dir=feature_dir,
        wp_id="WP01",
        old_lane="planned",
        target_lane="approved",
        force=True,
    )
    assert result is True


def test_is_arbiter_override_normal_claim(tmp_path: Path) -> None:
    """No rejection event in history + force → False (normal claim, not override)."""
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    feature_dir.mkdir(parents=True)

    # Only a planned -> claimed event, no rejection
    _write_event(
        feature_dir,
        _make_event(from_lane=Lane.PLANNED, to_lane=Lane.CLAIMED),
    )

    result = _is_arbiter_override(
        feature_dir=feature_dir,
        wp_id="WP01",
        old_lane="planned",
        target_lane="approved",
        force=True,
    )
    assert result is False


def test_is_arbiter_override_no_force(tmp_path: Path) -> None:
    """Rejection event present but force=False → False (not an override)."""
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    feature_dir.mkdir(parents=True)

    _write_event(
        feature_dir,
        _make_event(
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.PLANNED,
            review_ref="feedback://066-test/WP01/20260406T120000Z-abc123.md",
        ),
    )

    result = _is_arbiter_override(
        feature_dir=feature_dir,
        wp_id="WP01",
        old_lane="planned",
        target_lane="approved",
        force=False,  # no force!
    )
    assert result is False


# ---------------------------------------------------------------------------
# T12: Persist decision -- event-sourced ReviewOverride (WP12 REWRITE)
#
# The two old T12/T13 tests below pinned the retired frontmatter-stamp
# ("arbiter_override" block written into review-cycle-N.md) and JSON-sidecar
# ("arbiter-override-N.json") representations, INCLUDING the branch that
# chose between them based on whether an artifact happened to exist. WP12
# retires both into the single event-sourced ``ReviewOverride`` -- there is
# no branch left to test; both scenarios ("artifact exists" / "no artifact
# at all") now take the exact same path and are asserted the same way.
# ---------------------------------------------------------------------------


def _make_wp_with_slug(feature_dir: Path, wp_id: str, slug: str) -> None:
    """Register a WP task file so ``_resolve_wp_slug`` resolves *slug* for
    *wp_id* -- the slug-aware resolution ``persist_arbiter_decision`` now
    uses (T053), never the bare ``wp_id``."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{slug}.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Fixture\n---\n\n# {wp_id}\n",
        encoding="utf-8",
    )


def test_persist_decision_resolves_via_slug_and_emits_override(tmp_path: Path) -> None:
    """``persist_arbiter_decision`` resolves the review-cycle artifact through
    the slug-aware directory (not a bare ``tasks/WP01/``) and persists the
    decision as a durable ``ReviewOverride`` on the reduced ``review``
    snapshot slot -- the successor of the old frontmatter-stamp assertion.
    """
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    _make_wp_with_slug(feature_dir, "WP01", "WP01-real-slug")
    wp_subdir = feature_dir / "tasks" / "WP01-real-slug"
    wp_subdir.mkdir(parents=True, exist_ok=True)
    artifact = wp_subdir / "review-cycle-1.md"
    artifact.write_text(
        "---\n"
        "cycle_number: 1\n"
        "mission_slug: 066-test\n"
        "reviewed_at: '2026-04-06T12:00:00Z'\n"
        "reviewer_agent: reviewer-renata\n"
        "verdict: rejected\n"
        "wp_id: WP01\n"
        "---\n\n# Review\n\nSome feedback.\n",
        encoding="utf-8",
    )
    assert not (feature_dir / "tasks" / "WP01").exists(), "bare wp_id dir must not exist for this fixture"

    checklist = _make_checklist(is_pre_existing=True)
    decision = ArbiterDecision(
        arbiter="robert",
        category=ArbiterCategory.PRE_EXISTING_FAILURE,
        explanation="Test was pre-existing",
        checklist=checklist,
        decided_at="2026-04-06T14:00:00+00:00",
    )

    result_path = persist_arbiter_decision(
        feature_dir=feature_dir,
        wp_id="WP01",
        review_ref="review-cycle://066-test/WP01/001",
        decision=decision,
        repo_root=tmp_path,
    )

    assert result_path.parent == wp_subdir, "must resolve under the SLUG directory, not a bare wp_id one"

    from specify_cli.status import materialize

    override = materialize(feature_dir).work_packages.get("WP01", {}).get("review") or {}
    assert override.get("actor") == "robert"
    assert override.get("wp_id") == "WP01"
    assert "pre_existing_failure" in override.get("reason", "")
    assert "Test was pre-existing" in override.get("reason", "")


def test_persist_decision_emits_override_without_a_pre_existing_artifact(tmp_path: Path) -> None:
    """No review-cycle artifact (and no ``tasks/<wp_id>*`` directory at all)
    existed on disk before this call -- the retired code branched to a JSON
    sidecar here; the successor has no branch at all and still durably
    records the override.
    """
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    # Deliberately do NOT create any tasks/ entry for WP01 at all.

    checklist = _make_checklist(is_environmental=True)
    decision = create_arbiter_decision(
        arbiter_name="operator",
        category=ArbiterCategory.INFRA_ENVIRONMENTAL,
        explanation="CI server was down",
        checklist=checklist,
    )

    persist_arbiter_decision(
        feature_dir=feature_dir,
        wp_id="WP01",
        review_ref=None,
        decision=decision,
        repo_root=tmp_path,
    )

    from specify_cli.status import materialize

    override = materialize(feature_dir).work_packages.get("WP01", {}).get("review") or {}
    assert override.get("actor") == "operator"
    assert "infra_environmental" in override.get("reason", "")
    assert "CI server was down" in override.get("reason", "")


def test_persist_decision_survives_conflict_marked_review_cycle_artifact(
    tmp_path: Path,
) -> None:
    """T015 (#3244, RED-FIRST): a prior fail-open merge-driver downgrade can
    leave a ``review-cycle-N.md`` body starting with unresolved git conflict
    markers and no valid YAML frontmatter at all. ``persist_arbiter_decision``
    must not crash resolving the cycle number for such a WP -- it only needs
    the FILENAME to derive ``cycle_number`` (T016's ``latest_cycle_number``),
    never the damaged body. Mirrors
    ``test_persist_decision_resolves_via_slug_and_emits_override`` above, but
    the on-disk artifact is unparseable.

    Before the fix, ``ReviewCycleArtifact.latest()`` (which fully parses the
    body via ``from_file``) blows up with:
        ValueError: Review artifact file has no YAML frontmatter: ...
    """
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    _make_wp_with_slug(feature_dir, "WP01", "WP01-real-slug")
    wp_subdir = feature_dir / "tasks" / "WP01-real-slug"
    wp_subdir.mkdir(parents=True, exist_ok=True)
    artifact = wp_subdir / "review-cycle-1.md"
    artifact.write_text(
        "<<<<<<< ours\ncycle_number: 1\nmission_slug: 066-test\n=======\ncycle_number: 1\nmission_slug: 066-test-renamed\n>>>>>>> theirs\n",
        encoding="utf-8",
    )

    checklist = _make_checklist(is_pre_existing=True)
    decision = ArbiterDecision(
        arbiter="robert",
        category=ArbiterCategory.PRE_EXISTING_FAILURE,
        explanation="Test was pre-existing",
        checklist=checklist,
        decided_at="2026-04-06T14:00:00+00:00",
    )

    result_path = persist_arbiter_decision(
        feature_dir=feature_dir,
        wp_id="WP01",
        review_ref="review-cycle://066-test/WP01/001",
        decision=decision,
        repo_root=tmp_path,
    )

    assert result_path.parent == wp_subdir

    from specify_cli.status import materialize

    override = materialize(feature_dir).work_packages.get("WP01", {}).get("review") or {}
    assert override.get("actor") == "robert"
    assert override.get("wp_id") == "WP01"
    assert "pre_existing_failure" in override.get("reason", "")
    assert "Test was pre-existing" in override.get("reason", "")


# ---------------------------------------------------------------------------
# T14: parse_category_from_note
# ---------------------------------------------------------------------------


def test_parse_category_from_note() -> None:
    """``"[pre_existing_failure] explanation"`` parsed correctly."""
    cat, expl = parse_category_from_note("[pre_existing_failure] Test was already failing")
    assert cat == ArbiterCategory.PRE_EXISTING_FAILURE
    assert expl == "Test was already failing"


def test_parse_category_from_note_wrong_context() -> None:
    """``"[wrong_context]"`` parsed correctly."""
    cat, expl = parse_category_from_note("[wrong_context] Reviewer confused WP06 with WP07")
    assert cat == ArbiterCategory.WRONG_CONTEXT
    assert "confused" in expl


def test_parse_category_from_note_freeform() -> None:
    """Freeform note without bracket → CUSTOM category."""
    cat, expl = parse_category_from_note("No bracket here at all")
    assert cat == ArbiterCategory.CUSTOM
    assert expl == "No bracket here at all"


def test_parse_category_from_note_none() -> None:
    """None note → CUSTOM with generic explanation."""
    cat, expl = parse_category_from_note(None)
    assert cat == ArbiterCategory.CUSTOM
    assert expl  # must be non-empty


def test_parse_category_from_note_unknown_bracket() -> None:
    """Unknown category in brackets → CUSTOM, full note as explanation."""
    cat, expl = parse_category_from_note("[unknown_category] some explanation")
    assert cat == ArbiterCategory.CUSTOM


# ---------------------------------------------------------------------------
# Additional: create_arbiter_decision non-interactive factory
# ---------------------------------------------------------------------------


def test_create_arbiter_decision_string_category() -> None:
    """String category is coerced to ArbiterCategory."""
    decision = create_arbiter_decision(
        arbiter_name="claude",
        category="cross_scope",
        explanation="Finding is outside WP scope",
    )
    assert decision.category == ArbiterCategory.CROSS_SCOPE
    assert decision.arbiter == "claude"
    assert decision.checklist is not None
    # Synthetic checklist should be consistent with CROSS_SCOPE
    assert decision.checklist.is_in_scope is False


def test_create_arbiter_decision_invalid_category_falls_back() -> None:
    """Invalid category string falls back to CUSTOM."""
    decision = create_arbiter_decision(
        arbiter_name="operator",
        category="totally_invalid",
        explanation="Some explanation",
    )
    assert decision.category == ArbiterCategory.CUSTOM


def test_create_arbiter_decision_empty_explanation_uses_default() -> None:
    """Empty explanation is filled with category default."""
    decision = create_arbiter_decision(
        arbiter_name="operator",
        category=ArbiterCategory.PRE_EXISTING_FAILURE,
        explanation="",
    )
    assert decision.explanation  # must be non-empty
    assert "pre-existing" in decision.explanation.lower() or "base branch" in decision.explanation.lower()


# ---------------------------------------------------------------------------
# WP12 DELETION: _find_review_cycle_artifact is gone (T053 -- its resolution
# is now inlined in persist_arbiter_decision via the SAME slug-aware/numeric-
# highest-cycle resolvers the writer uses). The four tests that lived here
# exercised ONLY that deleted function's own branches (no-tasks-dir, bare
# wp_id subdir, tasks-level fallback scan, no-match) -- none of that branching
# survives; the slug-vs-bare-id behaviour it defended is now covered by
# test_persist_decision_resolves_via_slug_and_emits_override above (which
# proves persist_arbiter_decision resolves through the slug directory when a
# bare wp_id directory does not exist) and by the double-digit-cycle-number
# regression test in tests/specify_cli/cli/commands/agent/
# test_tasks_cli_contract_coord.py (T053, numerically- not lexicographically-
# highest cycle). No behaviour lost.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# WP12 DELETION: _persist_in_artifact is gone (T051 -- the frontmatter
# arbiter_override stamp it wrote is retired into the event-sourced
# ReviewOverride). Its no-frontmatter-prepend branch has no successor to
# test: persist_arbiter_decision no longer writes frontmatter into any
# review-cycle artifact at all, present or absent. Covered instead by
# test_persist_decision_resolves_via_slug_and_emits_override above.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# get_arbiter_overrides_for_wp -- WP12 REWRITE against the event-sourced
# ``review`` snapshot slot (FR-009). The two old "empty" tests below are
# kept (the concept "nothing recorded -> []" survives) but rewritten against
# an event log rather than an on-disk tasks/ layout, since the function no
# longer scans directories at all. The two old "reads decisions from X"
# tests (standalone JSON, review-cycle frontmatter) are CONSOLIDATED into
# one rewritten test: there is only one representation left to read from,
# so there is only one "finds an override" scenario to assert, not two.
# ---------------------------------------------------------------------------


def test_get_arbiter_overrides_empty_when_no_event_log(tmp_path: Path) -> None:
    """Returns empty list when the feature has no status event log at all."""
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    feature_dir.mkdir(parents=True)
    result = get_arbiter_overrides_for_wp(feature_dir, "WP01")
    assert result == []


def test_get_arbiter_overrides_empty_when_no_override_recorded(tmp_path: Path) -> None:
    """Returns empty list when the WP has ordinary lifecycle events but no
    arbiter override was ever recorded against it."""
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    feature_dir.mkdir(parents=True)
    _write_event(feature_dir, _make_event(from_lane=Lane.PLANNED, to_lane=Lane.CLAIMED))
    result = get_arbiter_overrides_for_wp(feature_dir, "WP01")
    assert result == []


def test_get_arbiter_overrides_reads_the_event_sourced_override(tmp_path: Path) -> None:
    """Reads the durable override back from the reduced ``review`` snapshot
    slot -- the single successor of the retired standalone-JSON and
    review-cycle-frontmatter representations. Exercises the real
    persist_arbiter_decision -> get_arbiter_overrides_for_wp round trip.
    """
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    checklist = _make_checklist(is_pre_existing=True)
    decision = ArbiterDecision(
        arbiter="robert",
        category=ArbiterCategory.PRE_EXISTING_FAILURE,
        explanation="Already broken on main",
        checklist=checklist,
        decided_at="2026-04-06T14:00:00+00:00",
    )

    persist_arbiter_decision(
        feature_dir=feature_dir,
        wp_id="WP01",
        review_ref=None,
        decision=decision,
        repo_root=tmp_path,
    )

    result = get_arbiter_overrides_for_wp(feature_dir, "WP01")
    assert len(result) == 1
    assert result[0]["category"] == "pre_existing_failure"
    assert "Already broken on main" in result[0]["explanation"]
    assert result[0]["arbiter"] == "robert"


# ---------------------------------------------------------------------------
# _is_arbiter_override — additional branches (lines 355, 357, 365)
# ---------------------------------------------------------------------------


def test_is_arbiter_override_wrong_old_lane(tmp_path: Path) -> None:
    """old_lane != 'planned' returns False even with force and rejection event."""
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    feature_dir.mkdir(parents=True)

    result = _is_arbiter_override(
        feature_dir=feature_dir,
        wp_id="WP01",
        old_lane="in_progress",  # not 'planned'
        target_lane="approved",
        force=True,
    )
    assert result is False


def test_is_arbiter_override_non_forward_target_lane(tmp_path: Path) -> None:
    """target_lane not in (approved, done) returns False."""
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    feature_dir.mkdir(parents=True)

    result = _is_arbiter_override(
        feature_dir=feature_dir,
        wp_id="WP01",
        old_lane="planned",
        target_lane="blocked",  # not a forward lane
        force=True,
    )
    assert result is False


def test_is_arbiter_override_no_events_for_wp(tmp_path: Path) -> None:
    """No events for this WP returns False."""
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    feature_dir.mkdir(parents=True)
    # Write an event for a *different* WP
    _write_event(
        feature_dir,
        _make_event(wp_id="WP02", from_lane=Lane.FOR_REVIEW, to_lane=Lane.PLANNED, review_ref="feedback://066-test/WP02/20260406T120000Z-abc123.md"),
    )

    result = _is_arbiter_override(
        feature_dir=feature_dir,
        wp_id="WP01",
        old_lane="planned",
        target_lane="approved",
        force=True,
    )
    assert result is False


# ---------------------------------------------------------------------------
# parse_category_from_note — empty-explanation branch (line 177)
# ---------------------------------------------------------------------------


def test_parse_category_from_note_bracket_no_explanation() -> None:
    """'[pre_existing_failure]' with no trailing explanation uses category default."""
    cat, expl = parse_category_from_note("[pre_existing_failure]")
    assert cat == ArbiterCategory.PRE_EXISTING_FAILURE
    assert expl  # must be non-empty (filled from _CATEGORY_DEFAULTS)
    assert "pre" in expl.lower() or "base" in expl.lower()


# ---------------------------------------------------------------------------
# create_arbiter_decision — enum-category branch (line 212) and CUSTOM
# fallback explanation (line 215 "or" branch)
# ---------------------------------------------------------------------------


def test_create_arbiter_decision_enum_category_branch() -> None:
    """Passing an ArbiterCategory enum (not a string) exercises the else branch."""
    decision = create_arbiter_decision(
        arbiter_name="operator",
        category=ArbiterCategory.WRONG_CONTEXT,  # enum, not string
        explanation="Reviewer was confused",
    )
    assert decision.category == ArbiterCategory.WRONG_CONTEXT
    assert decision.explanation == "Reviewer was confused"


def test_create_arbiter_decision_custom_empty_explanation_uses_fallback() -> None:
    """CUSTOM with empty explanation hits the 'or f"Override: {cat}"' branch."""
    decision = create_arbiter_decision(
        arbiter_name="operator",
        category=ArbiterCategory.CUSTOM,  # default is empty string → or-branch
        explanation="",
    )
    assert decision.explanation  # must be non-empty
    assert "Override" in decision.explanation or "custom" in decision.explanation.lower()


# ---------------------------------------------------------------------------
# WP12 DELETION: _persist_in_artifact is gone (same function as the T51
# deletion above) -- its empty-YAML-frontmatter branch has no successor
# (there is no frontmatter write left at all). Already covered by the
# deletion note earlier in this file.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# get_arbiter_overrides_for_wp — WP12 REWRITE: malformed data is silently
# skipped (FR-009). The retired representation's "malformed JSON" failure
# mode has no direct successor (there is no JSON file to corrupt anymore),
# but the underlying safety property survives in a new shape: an INCOMPLETE
# event-sourced override (missing a required field -- here, an empty
# ``reason``) must never be surfaced as if it were a real, actionable
# override, mirroring ``ReviewOverride.complete``'s predicate everywhere
# else it is honoured. Not a duplicate of test_get_arbiter_overrides_empty_
# when_no_override_recorded above: this asserts a *present-but-incomplete*
# slot degrades the same as an *absent* one, not merely that absence is
# handled.
# ---------------------------------------------------------------------------


def test_get_arbiter_overrides_skips_an_incomplete_override(tmp_path: Path) -> None:
    """An incomplete ``ReviewOverride`` (an empty ``reason``) is silently
    skipped, never surfaced as a usable override entry."""
    feature_dir = tmp_path / "kitty-specs" / "066-test"
    incomplete = ReviewOverride(at="2026-04-06T14:00:00+00:00", actor="operator", wp_id="WP01", reason="")
    emit_inner_state_changed(
        feature_dir,
        "WP01",
        WPInnerStateDelta(review=incomplete),
        actor="operator",
        mission_slug="066-test",
        repo_root=tmp_path,
    )

    result = get_arbiter_overrides_for_wp(feature_dir, "WP01")
    assert result == []


# ---------------------------------------------------------------------------
# WP12 DELETION: _persist_standalone_json is gone (T052 -- the JSON-sidecar
# representation it wrote is retired). This class's whole reason for
# existing was its `wp_subdir.mkdir(parents=True, exist_ok=True)` call on a
# raw `tasks_dir / wp_id` join -- the specific mkdir-on-untrusted-segment
# risk `assert_safe_path_segment` guarded there no longer exists anywhere:
# the successor path (persist_arbiter_decision -> _resolve_wp_slug /
# _review_cycle_wp_dir -> _persist_review_artifact_override) never calls
# `.mkdir()`/`.write()` on a `wp_id`-or-`wp_slug`-joined path itself; the
# actual write is `emit_inner_state_changed`'s own `canonicalize_feature_dir`
# gate on a feature_dir derived from a caller-resolved artifact path. This
# is not an unverified assumption: tests/architectural/
# test_untrusted_path_containment.py's full suite (the repo-wide untrusted-
# segment sink audit) was re-run after this WP's changes and stayed green --
# no new AST-discovered path-join sink appeared in review/arbiter.py, and
# that module was removed from the audit's own KNOWN_CANDIDATE_FILES tripwire
# list (see tests/architectural/untrusted_path_audit/audit.py's comment at
# the removed entry) because it now contains none. Nothing to rewrite here:
# the guarded call site is gone, not merely relocated.
# ---------------------------------------------------------------------------
