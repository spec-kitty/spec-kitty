# REASONS Canvas — Model-built payloads for the three post-mission lifecycle events

> Mission: issue-6438-build-lifecycle-payloads-from-models-01M68ZPD
> Generated: 2026-10-31
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: software-engineer and automation-agent

## Requirements
- Problem: three lifecycle emitters write a hand-built `dict`, so a payload the published `spec-kitty-events` contract rejects reaches `status.events.jsonl` and is only detected later, by a consumer ([research.md](research.md), [spec.md](spec.md)).
- Acceptance: [spec.md](spec.md), FR-001 through FR-005 and SC-001 through SC-004 — each emitter constructs its model, a model-rejected field fails before the append, and a valid emit persists the model's own dump.
- Definition of done: a failing-first test module committed red, a scoped production change, targeted green evidence with an unchanged write path, independent review, changelog entry, PR only. No merge by an agent.
- Out of scope, stated so it is not read as an omission: retiring `build_saas_lifecycle_queue_event` / `_canonical_lifecycle_payload_for_saas` (done in #6607) and CLI rendering of a `ValidationError`.

## Entities
- `MissionReopenedPayload`, `FollowUpRecordedPayload` (`spec_kitty_events.lifecycle`) and `ReviewerSelfApprovalPayload` (`spec_kitty_events.project_lifecycle`) are the published contract entities; no new entity, model or field is introduced.
- The persisted lifecycle envelope (`_build_envelope`) and the event-type registry are unchanged entities: this mission changes only how a `payload` mapping is produced.
- Existing domain meanings are kept: Mission, work package, status event log. Existing lines are historical facts and are never rewritten.

## Approach
- One construction idiom for the whole file: `Model(**fields).model_dump(mode="json", exclude_none=False)`, matching `emit_wp_created_local` and `emit_artifact_phase_local`. No second factory, no wrapper, no schema duplication.
- `pydantic.ValidationError` propagates rather than being wrapped: the sibling emitters already raise it, it is a `ValueError`, and wrapping would add a second failure surface for one defect class.
- Emitter guards stay ahead of construction so an existing named error (`MissionNotCompletedError`, the `follow_up_type` `ValueError`) keeps winning for the cases it already covers.
- Tradeoff rejected: tightening `emit_follow_up_recorded`'s parameter to `Literal["commit","pr"]` would change a public signature for typing alone; the runtime guard stays the contract and the narrowing is local to the call.

## Structure
- Production: `src/specify_cli/status/lifecycle_events.py`, three function bodies plus their docstrings. `_build_envelope`, `append_lifecycle_event`, `persist_lifecycle_event_local`, `store.append_raw_rows_atomic`, the constants and `__all__` are untouched.
- Tests: new `tests/specify_cli/status/test_model_built_payloads_6438.py`; one pre-existing fixture in `tests/specify_cli/status/test_post_mission_lifecycle_events.py` reseeded directly because the emitter can no longer produce an empty-reason row (assertions unchanged).
- Docs: `docs/changelog/CHANGELOG.md` `[Unreleased]/Fixed`. Planning artifacts under `kitty-specs/issue-6438-build-lifecycle-payloads-from-models-01M68ZPD/`.
- No dependency, packaging, schema or migration surface is touched.

## Operations
1. Opening campsite check of the three emitters: no separate tidy step was taken, so the diff stays a payload-construction change.
2. Write the contract tests first and commit them red (`DID NOT RAISE` on the four negative cases), then change the emitters.
3. Apply the three constructions; re-run the new module green plus the owning subsystem.
4. Run the blast radius: `tests/specify_cli/status/`, the events public-import architectural gate, the reopen CLI tests, ruff and mypy; record commands and counts.
5. Author the changelog entry, run the docs freshness check, then hand the branch to the operator for a draft PR. No merge, no auto-merge, no push to `main`.

## Norms
- Canonical sources only: the published models, the repo's own emitters as the idiom, the resolved mission artifacts rather than an older mission's structure.
- Python typing/lint standards with no suppressions; no `type: ignore`; no new dependency or version number.
- Refusal and absence assertions are paired with a same-fixture positive control, per `acceptance-criteria-non-vacuity`.
- Independent reviewer checks the diff and the live evidence, not a summary.

## Safeguards
- Only public `spec_kitty_events` modules are imported, function-locally; `tests/architectural/test_events_tracker_public_imports.py` must stay green.
- `reason`, `recorded_by` and `failure_reason` are non-empty by contract; an empty one must write nothing at all — no partial line, no repaired row.
- No historical `status.events.jsonl` line is rewritten, and a valid emit's payload keeps every field and every `null` optional it has today.
- No gate may be skipped, xfailed or loosened to make this land.
