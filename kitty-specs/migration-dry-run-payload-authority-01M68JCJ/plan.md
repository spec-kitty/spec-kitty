# Implementation Plan: Migration dry-run payload authority

**Branch**: `issue-6449-migration-dry-run-payload-authority` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/migration-dry-run-payload-authority-01M68JCJ/spec.md`

## Summary

`specify_cli/migration/mission_state.py::_status_event_to_teamspace_envelope`
currently assembles the dry-run `WPStatusChanged` payload as a plain dict. This
mission replaces that literal with one canonical CORE builder,
`specify_cli.status.build_status_event_payload`, which maps a `StatusEvent` onto
`spec_kitty_events.status.StatusTransitionPayload`, lets the model validate the
result, and shapes it with the existing shared
`apply_keep_none_fields` primitive. The dry-run then calls only that builder, so
there is a single authority for the payload shape; the `canonical-producer-exempt`
marker at the call site is retired. Parity with a real transition (the durable
`status.events.jsonl` row) is pinned by a red-first test that emits a transition
through the public status API and compares bytes.

## Technical Context

**Language/Version**: Python 3.11 (repo `.python-version`), `uv`-managed env.
**Primary Dependencies**: `spec-kitty-events>=11.3.0,<12` (installed 11.3.0) for `StatusTransitionPayload`; `pydantic` v2 (already a dependency).
**Storage**: JSONL event logs on disk (`kitty-specs/<mission>/status.events.jsonl`); the dry-run reads them and writes nothing.
**Testing**: pytest with layered markers; targeted modules under `tests/migration/`, `tests/status/`, `tests/architectural/` (no full heavy suite in-mission).
**Target Platform**: CLI, Linux/macOS.
**Project Type**: single Python package (`src/specify_cli`).
**Performance Goals**: no measurable change — one extra pydantic construction per dry-run event row (the row is already validated once by `validate_event`).
**Constraints**: CORE layer only (`specify_cli.status`); no INTEGRATION imports; reachable from `migration/` only through the `status` facade (`SR-2`); no new dependency.
**Scale/Scope**: one new CORE module (~70 lines), one call-site rewrite (~20 lines), one test module (~4 tests), one changelog entry.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter gate | Verdict |
| --- | --- |
| **Single canonical authority / canonical-producer (C-007, #1198)** | **Pass** — this mission removes a second authority and routes construction through the package model. The `#1198`-tracked `canonical-producer-exempt` marker at this site is retired, not renewed. |
| **ATDD-First Discipline (C-011)** | **Pass** — a failing-first parity test lands before the implementation commit; reviewer verifies red on the planning base and green on the final commit. |
| **Locality of change (`DIRECTIVE_024`) / smallest viable diff** | **Pass** — one new module, one call site, tests and changelog; no fan-out or transport-seam change. |
| **`__all__` Declaration Convention (C-007)** | **Pass** — the new symbol is promoted onto `specify_cli.status.__all__` and has a `src/` caller (`migration/mission_state.py`), satisfying the symbol-level dead-code gate. |
| **90%+ coverage for new code** | **Pass** — the builder's valid path, override validation and failure path are each covered; diff-cover target is 100% of the new lines. |
| **Pre-existing Failure Reporting Rule** | **N/A here** — no gate is known red for this diff; any CI red outside this diff is cited in the PR. |
| **Documentation standards** | **Pass** — a changelog `[Unreleased]` entry plus the payload contract doc under the mission's `contracts/`; no user-facing docs page describes the dry-run payload shape today, so no page edit is required (verified by `docs/` grep in the PR's Discovery). |

No violations: the Complexity Tracking table is not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/migration-dry-run-payload-authority-01M68JCJ/
├── plan.md              # This file
├── research.md          # Phase 0 output (discovery decisions, extended in plan)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── wp-status-changed-payload.md
├── tasks.md             # Phase 2 output (/spec-kitty.tasks)
└── traces/              # approach, design-decisions, tooling-friction
```

### Source Code (repository root)

```
src/specify_cli/status/
├── __init__.py          # facade: add build_status_event_payload to __all__
└── wire_payload.py      # NEW: the canonical WPStatusChanged payload builder

src/specify_cli/migration/
└── mission_state.py     # call site: build through the builder; report model rejection

tests/migration/
├── test_mission_state_teamspace_payload_authority.py   # NEW (red-first parity tests)
└── test_mission_state_repair.py                        # existing regression suite

docs/changelog/CHANGELOG.md                            # [Unreleased] entry
```

**Structure Decision**: single Python package. The builder lives beside
`status/emit.py` and `status/models.py` because the payload is a CORE status
concept; the migration module keeps only the historical-replay facts
(`for_review` alias, approval/done evidence synthesis) and passes them to the
builder as field overrides.

## Design decisions

1. **Builder shape** (mirrors `core/mission_payload.py::build_mission_created_payload`):

   ```python
   # status/wire_payload.py
   _KEEP_NONE_FIELDS = ("reason", "review_ref", "evidence")
   _PRODUCER_SUPPLIED_FIELDS = frozenset({"summary"})
   _EVENT_FIELD_ATTRS: dict[str, str] = { ... }   # model field -> StatusEvent attribute

   def build_wp_status_changed_payload(**fields: Any) -> dict[str, Any]:
       model = StatusTransitionPayload(**fields)
       return apply_keep_none_fields(model, keep_none_fields=_KEEP_NONE_FIELDS)

   def build_status_event_payload(
       event: StatusEvent, *, overrides: Mapping[str, Any] | None = None
   ) -> dict[str, Any]:
       ...
   ```

2. **Coverage ratchet instead of silent drift**: `_EVENT_FIELD_ATTRS` plus
   `_PRODUCER_SUPPLIED_FIELDS` must equal `set(StatusTransitionPayload.model_fields)`;
   a test asserts that. A future model field therefore fails a test instead of
   being silently dropped — the exact defect that dropped `mission_id`.

3. **Null policy**: keep `reason`, `review_ref`, `evidence` as explicit nulls
   (3.0.0 transport fixture and real rows both carry them); every other unset
   optional is absent, so `mission_id` appears exactly when the event has one and
   `summary` never appears.

4. **Model rejection stays a report**: `_status_event_to_teamspace_envelope`
   raises `pydantic.ValidationError`; `teamspace_dry_run` catches it, appends the
   existing `PAYLOAD_INVALID` record (mapped `field`/`message`/`violation_type`)
   and continues. A row that cannot be represented yields the error and no
   `row_mappings` entry (previously the mapping survived an invalid payload; no
   test or consumer depends on that, and the error carries the `event_id`).

5. **`validate_event` stays**: the model validates shape and the model's own
   business rules; `validate_event` still adds JSON-schema conformance and the
   semantic (`validate_transition`) checks on the already-model-valid payload.

## Complexity Tracking

Not required — the Charter Check reports no violation.

## Implementation Concern Map

### IC-01 — Canonical payload builder

- **Purpose**: give the dry-run one contract-backed constructor for the `WPStatusChanged` payload and make model-field coverage a test-enforced ratchet.
- **Relevant requirements**: FR-001, FR-002, FR-003, C-001, C-002, C-003.
- **Affected surfaces**: `src/specify_cli/status/wire_payload.py` (new), `src/specify_cli/status/__init__.py` (facade export).
- **Sequencing/depends-on**: none.
- **Risks**: the facade export must satisfy both the SR-2 boundary and the dead-symbol gate; the null policy must match the 3.0.0 fixture or the dry-run's wire shape changes.

### IC-02 — Dry-run call site and non-raising rejection

- **Purpose**: route `_status_event_to_teamspace_envelope` through the builder, keep the historical rewrites, and keep per-row model failures reported rather than raised.
- **Relevant requirements**: FR-002, FR-004, FR-006, C-004.
- **Affected surfaces**: `src/specify_cli/migration/mission_state.py`.
- **Sequencing/depends-on**: IC-01.
- **Risks**: error-shape fidelity (`PAYLOAD_INVALID` fields), and not disturbing the `row_mappings`/`envelope_sha256` contract for valid rows beyond the intentional `mission_id` addition.

### IC-03 — Parity pins, changelog and review

- **Purpose**: prove byte parity against a real transition and the construction authority, record the user-facing change, and complete the review.
- **Relevant requirements**: FR-005, FR-001, NFR-001, NFR-003.
- **Affected surfaces**: `tests/migration/test_mission_state_teamspace_payload_authority.py` (new), `docs/changelog/CHANGELOG.md`.
- **Sequencing/depends-on**: IC-01, IC-02 (the tests must be able to fail first, so they are authored before the call-site rewrite).
- **Risks**: a test that only compares the builder to itself would be tautological — the parity oracle must be the real emitted row.
