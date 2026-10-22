"""WP05 (verdict-seam-write-unification-01KZ9Q35) reader-collapse tests.

Covers:

- **T021 (SC-008 / US6 scenario 2)**: the provenance interlock
  (``stranded_verdict_findings``, WP02-owned) reports a WP whose only
  rejection is a pre-event ``.md`` verdict, and clears once the backfill
  runs -- proving the safety interlock this WP's own reader deletion was
  gated on. Once clean, the collapsed reader (``resolve_review_verdict_facts``,
  via ``event_sourced_review_result``) correctly resolves the historical
  verdict from the event log alone.
- **T022 (US1)**: the single-authority anchor -- every repointed reader
  answers from the event-sourced snapshot, never ``review-cycle-N.md``
  frontmatter, when the two disagree in EITHER direction (approved-artifact
  vs. rejected-snapshot, and the inverse). Red-first against the pre-WP05
  frontmatter readers (see each test's docstring for why it fails before the
  repoint).
- **T029 (SC-004)**: a parametrized-by-consumer damaged-record proof over the
  distinct safety-gate reader shapes this WP repointed (the approval guard,
  the status display, the merge gate) -- each fails closed on a damaged
  ``review_result`` record: never a fabricated approval, never an uncaught
  crash.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.cli.commands.agent.tasks_parsing_validation import (
    _apply_review_status_flags,
)
from specify_cli.cli.commands.agent.tasks_verdict_persistence import (
    _wp_id_from_stem,
    resolve_review_verdict_facts,
)
from specify_cli.migration.verdict_provenance_backfill import (
    backfill_verdict_provenance,
    stranded_verdict_findings,
)
from specify_cli.post_merge.review_artifact_consistency import (
    find_rejected_review_artifact_conflicts,
)
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.status.models import Lane, ReviewResult, StatusEvent, StatusSnapshot
from specify_cli.status.reducer import ReviewResultLookup
from tests._support.status_seed import seed_status_event

pytestmark = pytest.mark.fast

MISSION_SLUG = "042-reader-collapse-demo"

#: The three-way outcome a genuinely corrupted event-log ``review_result``
#: slot produces (:class:`~specify_cli.status.reducer.ReviewResultLookup`'s
#: ``slot_present=True, result=None`` case) -- injected directly at each
#: consumer's own seam for T029's parametrized proof.
_DAMAGED = ReviewResultLookup(slot_present=True, result=None)


def _feature_dir(tmp_path: Path, slug: str = MISSION_SLUG) -> Path:
    feature_dir = tmp_path / slug
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": slug,
                "mission_id": "01JRDRCOLLAPSE0000000000",
                "mission_type": "software-dev",
            }
        ),
        encoding="utf-8",
    )
    return feature_dir


def _write_review_cycle(
    feature_dir: Path,
    wp_id: str,
    *,
    cycle_number: int,
    verdict: str,
    reviewed_at: str = "2026-01-01T00:00:00+00:00",
    wp_slug: str | None = None,
) -> Path:
    """Write a ``review-cycle-N.md`` artifact carrying a LEGACY ``verdict``
    frontmatter key (WP06, FR-003/SC-007): ``ReviewCycleArtifact`` no longer
    has a ``verdict`` field, but this module's whole point is exercising the
    provenance-recovery path (``migration.verdict_provenance_backfill``) over
    files written BEFORE that schema change -- so the legacy key is spliced
    into the frontmatter directly after the live-schema write, matching the
    real on-disk shape those historical files carry forever.
    """
    dir_name = wp_slug or wp_id
    sub_dir = feature_dir / "tasks" / dir_name
    artifact = ReviewCycleArtifact(
        cycle_number=cycle_number,
        wp_id=wp_id,
        mission_slug=feature_dir.name,
        reviewer_agent="reviewer-renata",
        reviewed_at=reviewed_at,
        body="# Review\n",
    )
    path = sub_dir / f"review-cycle-{cycle_number}.md"
    artifact.write(path)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"expected frontmatter delimiter in {path}"
    path.write_text(f"---\nverdict: {verdict}\n{text[4:]}", encoding="utf-8")
    return path


def _write_wp_file(feature_dir: Path, wp_id: str, wp_slug: str) -> Path:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    wp_file = tasks_dir / f"{wp_slug}.md"
    wp_file.write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Demo\n---\n# {wp_id}\n",
        encoding="utf-8",
    )
    return wp_file


def _append_review_result_event(
    feature_dir: Path,
    *,
    wp_id: str,
    to_lane: Lane,
    verdict: str,
    event_id: str,
    from_lane: Lane = Lane.IN_REVIEW,
    reference: str = "review-cycle://demo/WP01/review-cycle-1.md",
) -> None:
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=event_id,
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=from_lane,
            to_lane=to_lane,
            at="2026-02-01T00:00:00+00:00",
            actor="reviewer-renata",
            force=False,
            execution_mode="worktree",
            review_result=ReviewResult(reviewer="reviewer-renata", verdict=verdict, reference=reference),
        ),
    )


# ===========================================================================
# T021 (SC-008 / US6 scenario 2) -- the provenance interlock
# ===========================================================================


def test_provenance_interlock_reports_stranded_pre_event_rejection(tmp_path: Path) -> None:
    """A WP whose only rejection record is a pre-event ``.md`` (no
    ``review_result`` event slot at all) is reported by the interlock --
    this is the finding that blocks reader deletion (US6 scenario 2, first
    half; SC-008)."""
    feature_dir = _feature_dir(tmp_path)
    _write_review_cycle(feature_dir, "WP01", cycle_number=1, verdict="rejected")

    findings = stranded_verdict_findings(feature_dir)

    assert len(findings) == 1
    assert findings[0].wp_id == "WP01"
    assert findings[0].has_md_verdict is True
    assert findings[0].has_event_slot is False


def test_provenance_interlock_clears_after_backfill_and_reader_sees_correct_verdict(
    tmp_path: Path,
) -> None:
    """Running the WP02 backfill clears the interlock (US6 scenario 2,
    second half) AND the now-collapsed reader
    (``resolve_review_verdict_facts``, via ``event_sourced_review_result``)
    correctly resolves the historical rejection from the event log alone --
    proving the reader deletion this WP performed is safe only because the
    backfill ran first (SC-008)."""
    feature_dir = _feature_dir(tmp_path)
    wp_slug = "WP01-demo"
    wp_file = _write_wp_file(feature_dir, "WP01", wp_slug)
    _write_review_cycle(feature_dir, "WP01", cycle_number=1, verdict="rejected", wp_slug=wp_slug)

    assert len(stranded_verdict_findings(feature_dir)) == 1

    outcome = backfill_verdict_provenance(feature_dir)
    assert outcome.appended_count == 1
    assert stranded_verdict_findings(feature_dir) == []

    # Idempotent re-run adds nothing (G1).
    assert backfill_verdict_provenance(feature_dir).appended_count == 0

    review_verdict, _, _ = resolve_review_verdict_facts(wp_file)
    assert review_verdict == "rejected", (
        "post-backfill, the collapsed reader must resolve the historical "
        "rejection from the event log alone -- the SC-008 guarantee"
    )


# ===========================================================================
# T022 (US1) -- the single-authority anchor: snapshot wins, both directions
# ===========================================================================


def test_approval_guard_reads_snapshot_rejected_despite_approved_frontmatter(
    tmp_path: Path,
) -> None:
    """US1 scenario 1: the event-sourced snapshot says ``changes_requested``;
    the ``.md`` frontmatter (stale) says ``approved``. The approval guard's
    feed (``resolve_review_verdict_facts``) must report the SNAPSHOT verdict
    (``rejected``), never the stale ``.md`` -- this is exactly the disagreement
    shape that fails RED against the pre-WP05 frontmatter reader
    (``_get_latest_review_cycle_verdict`` would have returned ``"approved"``
    here)."""
    feature_dir = _feature_dir(tmp_path)
    wp_slug = "WP01-demo"
    wp_file = _write_wp_file(feature_dir, "WP01", wp_slug)
    _write_review_cycle(feature_dir, "WP01", cycle_number=1, verdict="approved", wp_slug=wp_slug)
    _append_review_result_event(
        feature_dir,
        wp_id="WP01",
        to_lane=Lane.IN_PROGRESS,
        verdict="changes_requested",
        event_id="01T022REJECTED0000000001",
        reference=f"review-cycle://{feature_dir.name}/{wp_slug}/review-cycle-1.md",
    )

    review_verdict, _, _ = resolve_review_verdict_facts(wp_file)

    assert review_verdict == "rejected", "the snapshot must win over the .md's stale 'approved'"


def test_approval_guard_reads_snapshot_approved_despite_rejected_frontmatter(
    tmp_path: Path,
) -> None:
    """The inverse disagreement: the snapshot says ``approved``, the ``.md``
    says ``rejected`` -- the guard must resolve the snapshot's ``approved``,
    never the stale rejection (the reverse-disagreement half of US1
    scenario 1)."""
    feature_dir = _feature_dir(tmp_path)
    wp_slug = "WP01-demo"
    wp_file = _write_wp_file(feature_dir, "WP01", wp_slug)
    _write_review_cycle(feature_dir, "WP01", cycle_number=1, verdict="rejected", wp_slug=wp_slug)
    _append_review_result_event(
        feature_dir,
        wp_id="WP01",
        to_lane=Lane.APPROVED,
        verdict="approved",
        event_id="01T022APPROVED0000000001",
    )

    review_verdict, _, _ = resolve_review_verdict_facts(wp_file)

    assert review_verdict == "approved"


def test_board_shows_snapshot_rejected_despite_approved_frontmatter(tmp_path: Path) -> None:
    """US1 scenario 2: the status display flags the WP stale from the
    event-sourced snapshot even though its ``.md`` frontmatter reads
    ``approved``."""
    feature_dir = _feature_dir(tmp_path)
    _write_review_cycle(feature_dir, "WP01", cycle_number=1, verdict="approved")
    _append_review_result_event(
        feature_dir,
        wp_id="WP01",
        to_lane=Lane.IN_PROGRESS,
        verdict="changes_requested",
        event_id="01T022BOARD0000000000001",
    )
    work_packages: list[dict[str, object]] = [{"id": "WP01", "lane": Lane.DONE}]

    stale, _ = _apply_review_status_flags(
        work_packages, feature_dir=feature_dir, events=[], stall_threshold_minutes=30
    )

    assert stale and stale[0]["wp_id"] == "WP01"
    assert work_packages[0]["_stale_verdict"] is True


def test_damaged_record_fails_closed_not_crash(tmp_path: Path) -> None:
    """US1 scenario 3: a damaged event-log ``review_result`` slot fails
    closed on the approval guard's feed -- never a crash, never a fabricated
    verdict."""
    feature_dir = _feature_dir(tmp_path)
    wp_slug = "WP01-demo"
    wp_file = _write_wp_file(feature_dir, "WP01", wp_slug)

    with patch(
        "specify_cli.cli.commands.agent.tasks_verdict_persistence.event_sourced_review_result",
        return_value=_DAMAGED,
    ):
        review_verdict, _artifact_path, review_artifact_name = resolve_review_verdict_facts(wp_file)

    assert review_verdict is None
    assert review_artifact_name is not None, (
        "damaged must still trip the caller's 'no parseable review verdict' "
        "refusal (a None review_artifact_name would short-circuit it instead)"
    )


def test_cleared_slot_resolves_as_no_verdict_on_record(tmp_path: Path) -> None:
    """#5446: a slot cleared by a verdict-less review exit is not damage."""
    feature_dir = _feature_dir(tmp_path)
    wp_file = _write_wp_file(feature_dir, "WP01", "WP01-demo")
    cleared = ReviewResultLookup(slot_present=True, result=None, cleared_without_verdict=True)

    with patch(
        "specify_cli.cli.commands.agent.tasks_verdict_persistence.event_sourced_review_result",
        return_value=cleared,
    ):
        facts = resolve_review_verdict_facts(wp_file)

    assert facts == (None, None, None)


# ===========================================================================
# T029 (SC-004) -- parametrized damaged-record proof over the distinct
# safety-gate reader shapes this WP repointed.
# ===========================================================================


def test_status_display_fails_closed_on_damaged_record(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    work_packages: list[dict[str, object]] = [{"id": "WP01", "lane": Lane.DONE}]

    with patch(
        "specify_cli.cli.commands.agent.tasks_parsing_validation.event_sourced_review_result",
        return_value=_DAMAGED,
    ):
        stale, _ = _apply_review_status_flags(
            work_packages, feature_dir=feature_dir, events=[], stall_threshold_minutes=30
        )

    assert stale and stale[0]["damaged"] is True
    assert work_packages[0]["_damaged_verdict"] is True


def test_status_display_does_not_flag_a_cleared_slot(tmp_path: Path) -> None:
    """#5446: a slot cleared by a verdict-less review exit is not "damaged"."""
    feature_dir = _feature_dir(tmp_path)
    work_packages: list[dict[str, object]] = [{"id": "WP01", "lane": Lane.DONE}]
    cleared = ReviewResultLookup(slot_present=True, result=None, cleared_without_verdict=True)

    with patch(
        "specify_cli.cli.commands.agent.tasks_parsing_validation.event_sourced_review_result",
        return_value=cleared,
    ):
        stale, _ = _apply_review_status_flags(work_packages, feature_dir=feature_dir, events=[], stall_threshold_minutes=30)

    assert not stale
    assert "_damaged_verdict" not in work_packages[0]


def test_merge_gate_fails_closed_on_damaged_record_never_blocks(tmp_path: Path) -> None:
    """The merge gate's damaged-record polarity (G2): a safety-gate checking
    for an EXISTING rejection must not fabricate one from a damaged record
    either -- it defers (no finding), the same as an absent slot. Exercises
    the REAL ``_event_sourced_gate_verdict`` malformed-dict catch (a
    ``Mapping`` present but missing required ``ReviewResult`` fields) rather
    than mocking it away."""
    feature_dir = _feature_dir(tmp_path)
    damaged_snapshot = StatusSnapshot(
        mission_slug=feature_dir.name,
        materialized_at="2026-02-01T00:00:00+00:00",
        event_count=1,
        last_event_id="01T029MERGEGATE00000001",
        work_packages={
            "WP01": {
                "lane": "approved",
                # Present (a Mapping) but missing required ReviewResult
                # fields (reviewer/verdict/reference) -- the genuine
                # "damaged" shape, not merely absent.
                "review_result": {"reviewer": "reviewer-renata"},
            }
        },
        summary={},
    )

    with patch(
        "specify_cli.post_merge.review_artifact_consistency.materialize_snapshot",
        return_value=damaged_snapshot,
    ):
        findings = find_rejected_review_artifact_conflicts(feature_dir)

    assert findings == [], (
        "a damaged review_result record must not be fabricated into a "
        "blocking merge-gate finding (G2 fail-closed, never a crash either)"
    )


# ===========================================================================
# Reviewer cycle-1 finding: ``_wp_id_from_stem``'s non-hyphen separator
# branches were untested. A wrong wp_id key -> event_sourced_review_result
# reads the WRONG slot -> slot_present=False -> (None, None, None) -> the
# approval guard does NOT refuse -- a FAIL-OPEN on the safety gate this WP
# exists to close. Parametrized over all three T057-accepted separators
# (hyphen kept as the already-covered control) so the ``.``/``_`` branches
# -- the exact case ``_wp_id_from_stem`` was added to fix -- are proven both
# at the pure-function level AND through the real caller
# (``resolve_review_verdict_facts``) that the approval guard depends on.
# ===========================================================================


@pytest.mark.parametrize(
    "wp_slug",
    ["WP05-foo", "WP05.foo", "WP05_foo"],
    ids=["hyphen", "dot", "underscore"],
)
def test_wp_id_from_stem_resolves_bare_id_for_every_accepted_separator(
    wp_slug: str,
) -> None:
    """``_wp_id_from_stem`` must reduce every T057-accepted separator
    (``-``, ``.``, ``_``) to the bare ``WP05`` id -- not merely the hyphen
    case the old ``stem.split("-")[0]`` naive cut happened to get right.

    This is the RED-FIRST proof against the pre-fix regex: reverting
    ``_wp_id_from_stem`` to ``stem.split("-")[0]`` fails this test on the
    ``dot``/``underscore`` parametrizations (returning ``"WP05.foo"``/
    ``"WP05_foo"`` unchanged) while still passing on ``hyphen`` --
    demonstrating the non-hyphen branches were the exact untested gap.
    """
    assert _wp_id_from_stem(wp_slug) == "WP05"


@pytest.mark.parametrize(
    "wp_slug",
    ["WP05-foo", "WP05.foo", "WP05_foo"],
    ids=["hyphen", "dot", "underscore"],
)
def test_approval_guard_resolves_rejection_for_every_accepted_separator(
    tmp_path: Path, wp_slug: str
) -> None:
    """End-to-end proof, through the REAL caller the safety gate depends on:
    a WP whose task file uses a non-hyphen separator (``WP05.foo.md``,
    ``WP05_foo.md``) still resolves its genuine ``changes_requested`` event
    via ``resolve_review_verdict_facts`` -- ``slot_present`` must be
    ``True`` with the rejection surfaced, never ``(None, None, None)``
    (the silent fail-open this WP's own safety mandate forbids).

    Before ``_wp_id_from_stem``, the naive ``stem.split("-")[0]`` wp_id
    extraction returned the WHOLE stem unchanged for ``.``/``_`` stems (e.g.
    ``"WP05_foo"``, never reduced to ``"WP05"``), so
    ``event_sourced_review_result`` looked up an event under a wp_id that
    never matches any real event -- ``slot_present=False`` -- and the
    approval guard's caller (``_mt_gather_review_facts``) would have treated
    a genuinely rejected WP as having no verdict on record at all, silently
    NOT refusing the approval. This test fails RED against that naive cut
    for the ``dot``/``underscore`` parametrizations.
    """
    feature_dir = _feature_dir(tmp_path)
    wp_file = _write_wp_file(feature_dir, "WP05", wp_slug)
    _append_review_result_event(
        feature_dir,
        wp_id="WP05",
        to_lane=Lane.IN_PROGRESS,
        verdict="changes_requested",
        event_id=f"01TSEP{wp_slug.replace('.', 'D').replace('_', 'U')}0001",
        reference=f"review-cycle://{feature_dir.name}/{wp_slug}/review-cycle-1.md",
    )

    review_verdict, _artifact_path, review_artifact_name = resolve_review_verdict_facts(
        wp_file
    )

    assert review_verdict == "rejected", (
        f"wp_slug={wp_slug!r}: the guard must resolve the genuine rejection "
        "recorded under wp_id WP05 -- a fail-open here means the WRONG "
        "wp_id key was looked up"
    )
    assert review_artifact_name is not None, (
        f"wp_slug={wp_slug!r}: slot_present must be True (a real rejection "
        "recorded) -- (None, None, None) is the fail-open shape this test "
        "guards against"
    )
