"""WP04 (#2217) — retrospect tracer ingestion + conditional data-model gap.

Drives the pre-existing ``spec-kitty retrospect create`` surface (C-006 red-first)
against a real on-disk mission and inspects the persisted record, asserting:

1. A mission with ``traces/tooling-friction.md`` content yields >= 1 tracer-sourced
   finding (FR-007).
2. A no-domain-entity (governance/wiring) mission with no ``data-model.md`` does NOT
   get a false "data-model.md absent" gap (FR-008, negative case).
3. A mission that DOES declare domain entities but ships no ``data-model.md`` STILL
   gets the gap (FR-008, positive case — pins conditional-on-entities, not
   always-off).
4. A malformed/empty tracer file does NOT crash the generator (best-effort ingest,
   #2217 edge case).

The findings/data-model assertions read the record the CLI wrote back through the
public reader, so the test exercises generator + writer end-to-end via the CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.retrospect import app as retrospect_app
from specify_cli.retrospective.generator import _parse_trace_entries
from specify_cli.retrospective.reader import read_gen_record

pytestmark = [pytest.mark.unit, pytest.mark.fast]

RUNNER = CliRunner()

# A real-format ULID mission_id (26 chars, Crockford base32).
_MISSION_ID = "01KW4V6CXTRACERINGEST0WP04Z"[:26]
_MISSION_ID_NOENT = "01KW4V6CXNOENTITYGOVWIRE0AA"[:26]
_MISSION_ID_ENT = "01KW4V6CXHASENTITYDATAMOD0B"[:26]
_MISSION_ID_BAD = "01KW4V6CXMALFORMEDTRACER0CC"[:26]
_TRACER_TEMPLATES = (
    Path(__file__).parents[3] / "src/charter/offering/templates/mission-tracer-files"
)


@pytest.mark.parametrize("name", ["tooling-friction", "approach", "design-decisions"])
def test_shipped_tracer_example_is_parseable_without_seeding_a_finding(name: str) -> None:
    """Each author-facing example can be copied into a tracer as one finding."""
    template = (_TRACER_TEMPLATES / f"{name}.md").read_text(encoding="utf-8")
    example = next(
        line.removeprefix("Example: `").removesuffix("`")
        for line in template.splitlines()
        if line.startswith("Example: `- ")
    )

    assert _parse_trace_entries(template) == []
    entries = _parse_trace_entries(example)
    assert len(entries) == 1
    assert entries[0][0].startswith("[2026-")


# ---------------------------------------------------------------------------
# Production-shaped fixture content
# ---------------------------------------------------------------------------

# A realistic tooling-friction tracer following the documented entry format:
#   N. **[phase] SYMPTOM ...** ... disposition (... OPEN/candidate gap/workaround/fixed)
_TOOLING_FRICTION_TRACE = """\
# Tooling-Friction Trace — tracer-ingest-mission

**Purpose:** a running log of spec-kitty tooling friction encountered while running
this mission. Seeded at spec -> plan; appended during the implement loop.

> Format per entry: `[phase] SYMPTOM — anchor — disposition (fixed/workaround/open)`

---

## Seeded during spec -> plan

1. **[implement/analyze gate] Every `mark-status` re-stales the analyze report.**
   Marking a WP's subtasks done edited `tasks.md`, so the recorded
   `analysis-report.md` went `stale_analysis_report` and the next claim refused
   until `/spec-kitty.analyze` was re-run. Disposition: **workaround = re-run
   analyze per WP**. Candidate gap: ignore checkbox-only diffs. **OPEN (candidate gap).**

2. **[implement/auto-commit-off] The claim writes `vcs_locked_at` into `meta.json`,
   then refuses because that write left the tree dirty.** Self-inflicted dirty-tree
   block. Disposition: **workaround = hand-commit the bookkeeping, then re-claim.**

3. **[plan] `plan` blocks until Technical Context is substantive.** Working as
   designed; authoring + re-run returned `success`. Disposition: **expected** — no gap.
"""

# A spec with NO domain entities (governance / wiring mission) — no Key Entities
# section at all.
_SPEC_NO_ENTITIES = """\
# Mission Spec — governance wiring

## User Scenarios

### User Story 1 — Route the resolver

As an operator, I want the resolver wired so reads resolve through one surface.

## Requirements

- **FR-001**: Route reads through the canonical surface resolver.

## Success Criteria

- **SC-001**: All read sites resolve through the resolver.
"""

# A spec WITH concrete domain entities (populated Key Entities section — not the
# template placeholder ``- **[Entity 1]**``).
_SPEC_WITH_ENTITIES = """\
# Mission Spec — merge state model

## User Scenarios

### User Story 1 — Persist merge progress

As an operator, I want merge progress saved so I can resume.

## Requirements

- **FR-001**: Persist merge progress to disk.

### Key Entities

- **ConsolidationState**: the resumable merge progress for a mission, with the ordered WP
  list, completed WPs, and the current WP.
- **WPStatus**: per-work-package preflight status with worktree path and cleanliness.

## Success Criteria

- **SC-001**: Interrupted merges resume from the persisted state.
"""

_STATUS_EVENTS_ALL_DONE = [
    {
        "event_id": "01KW4V6C00000000000000WP01",
        "at": "2026-06-20T10:00:00+00:00",
        "actor": "claude",
        "feature_slug": "PLACEHOLDER",
        "wp_id": "WP01",
        "from_lane": "planned",
        "to_lane": "done",
        "force": False,
        "reason": None,
        "review_ref": None,
        "evidence": None,
        "execution_mode": "main",
    }
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_mission(
    kitty_specs: Path,
    *,
    slug: str,
    mission_id: str,
    spec_text: str,
    trace_text: str | None = None,
    write_data_model: bool = False,
) -> Path:
    """Write a completed on-disk mission under ``kitty-specs/<slug>/``.

    Returns the feature_dir.
    """
    feature_dir = kitty_specs / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": slug,
                "slug": slug,
                "friendly_name": slug,
                "mission_type": "software-dev",
            }
        ),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text(spec_text, encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n\nImplementation plan.\n", encoding="utf-8")

    events = []
    for raw in _STATUS_EVENTS_ALL_DONE:
        ev = dict(raw)
        ev["feature_slug"] = slug
        events.append(ev)
    (feature_dir / "status.events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )

    if write_data_model:
        (feature_dir / "data-model.md").write_text("# Data Model\n\nEntities.\n", encoding="utf-8")

    if trace_text is not None:
        traces_dir = feature_dir / "traces"
        traces_dir.mkdir(parents=True, exist_ok=True)
        (traces_dir / "tooling-friction.md").write_text(trace_text, encoding="utf-8")

    return feature_dir


def _run_create(repo_root: Path, slug: str) -> dict[str, object]:
    """Invoke ``spec-kitty retrospect create --mission <slug> --json``; return JSON."""
    with patch(
        "specify_cli.cli.commands.retrospect.locate_project_root",
        return_value=repo_root,
    ):
        result = RUNNER.invoke(
            retrospect_app, ["create", "--mission", slug, "--json"]
        )
    assert result.exit_code == 0, f"create failed (exit {result.exit_code}):\n{result.output}"
    return json.loads(result.stdout)


def _all_findings(record: object) -> list[object]:
    return [*record.helped, *record.not_helpful, *record.gaps]  # type: ignore[attr-defined]


def _trace_evidence_ids(record: object) -> set[str]:
    return {
        ref.id  # type: ignore[attr-defined]
        for ref in record.evidence_refs  # type: ignore[attr-defined]
        if "/traces/" in ref.path  # type: ignore[attr-defined]
    }


# ---------------------------------------------------------------------------
# T011 — FR-007: tracer-sourced finding
# ---------------------------------------------------------------------------


def test_tracer_content_yields_sourced_finding(tmp_path: Path) -> None:
    """A mission with traces/tooling-friction.md yields >= 1 tracer-sourced finding."""
    kitty_specs = tmp_path / "kitty-specs"
    slug = "tracer-ingest-mission"
    _seed_mission(
        kitty_specs,
        slug=slug,
        mission_id=_MISSION_ID,
        spec_text=_SPEC_NO_ENTITIES,
        trace_text=_TOOLING_FRICTION_TRACE,
    )

    data = _run_create(tmp_path, slug)
    record = read_gen_record(Path(str(data["record_path"])))

    trace_ev_ids = _trace_evidence_ids(record)
    assert trace_ev_ids, (
        "expected at least one evidence_ref pointing at traces/*.md; "
        f"got {[r.path for r in record.evidence_refs]}"
    )

    sourced = [
        f
        for f in _all_findings(record)
        if set(f.evidence_refs) & trace_ev_ids  # type: ignore[attr-defined]
    ]
    assert sourced, "expected at least one finding sourced from the tracer file"
    # The friction entries should surface as tooling-category findings.
    assert any(f.category == "tooling" for f in sourced), (
        f"expected a tooling-category tracer finding; got {[f.category for f in sourced]}"
    )


# ---------------------------------------------------------------------------
# T011 — FR-008: data-model gap conditional on domain entities
# ---------------------------------------------------------------------------


def _has_data_model_gap(record: object) -> bool:
    return any(
        "data-model.md absent" in g.summary  # type: ignore[attr-defined]
        for g in record.gaps  # type: ignore[attr-defined]
    )


def test_no_entity_mission_has_no_false_data_model_gap(tmp_path: Path) -> None:
    """A governance/wiring mission (no entities, no data-model.md) gets no false gap."""
    kitty_specs = tmp_path / "kitty-specs"
    slug = "governance-wiring-mission"
    _seed_mission(
        kitty_specs,
        slug=slug,
        mission_id=_MISSION_ID_NOENT,
        spec_text=_SPEC_NO_ENTITIES,
    )

    data = _run_create(tmp_path, slug)
    record = read_gen_record(Path(str(data["record_path"])))

    assert not _has_data_model_gap(record), (
        "no-entity mission must NOT flag a missing data-model.md gap; "
        f"gaps={[g.summary for g in record.gaps]}"
    )


def test_entity_mission_keeps_data_model_gap(tmp_path: Path) -> None:
    """A mission that declares domain entities but ships no data-model.md STILL gaps.

    Paired with the negative case above, this pins the gap as conditional-on-entities
    rather than silently disabled.
    """
    kitty_specs = tmp_path / "kitty-specs"
    slug = "entity-bearing-mission"
    _seed_mission(
        kitty_specs,
        slug=slug,
        mission_id=_MISSION_ID_ENT,
        spec_text=_SPEC_WITH_ENTITIES,
    )

    data = _run_create(tmp_path, slug)
    record = read_gen_record(Path(str(data["record_path"])))

    assert _has_data_model_gap(record), (
        "entity-bearing mission with no data-model.md MUST still flag the gap; "
        f"gaps={[g.summary for g in record.gaps]}"
    )


# ---------------------------------------------------------------------------
# T011 — #2217 edge case: malformed/empty tracer must not crash
# ---------------------------------------------------------------------------


def test_malformed_tracer_does_not_crash(tmp_path: Path) -> None:
    """A malformed/empty tracer file is skipped best-effort; create still succeeds."""
    kitty_specs = tmp_path / "kitty-specs"
    slug = "malformed-tracer-mission"
    feature_dir = _seed_mission(
        kitty_specs,
        slug=slug,
        mission_id=_MISSION_ID_BAD,
        spec_text=_SPEC_NO_ENTITIES,
        trace_text="",  # empty tracer
    )
    # A second tracer with non-UTF-8 bytes — the read must not crash the generator.
    (feature_dir / "traces" / "garbage.md").write_bytes(b"\xff\xfe\x00\x01 not valid utf-8 \x80")

    data = _run_create(tmp_path, slug)
    # The create completed (exit 0 asserted in _run_create) and wrote a record.
    record = read_gen_record(Path(str(data["record_path"])))
    assert record.mission_slug == slug
