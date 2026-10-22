# Research: Event write hygiene

## R-1 Public "known event type" predicate upstream

- **Decision:** none is available. Core deletes its only caller of the private map instead (operator ruling).
- **Evidence:**
  - At 11.2.1, `spec_kitty_events.conformance.validators._EVENT_TYPE_TO_MODEL` is still private, and upstream's own `persistence.py:82` imports it.
  - The public `validate_event` raises `ValueError` for an unknown type.
  - In core, the only reader is `_validate_lifecycle_payload`. Its only caller is `build_saas_lifecycle_queue_event`, which has no `src/` caller.
  - `SignificanceEvaluated` is persisted through the run journal (`runtime/next/_internal_runtime/engine.py::_record_significance`), never through this validator.
- **Alternatives considered:**
  - The public `validate_event` with its `ValueError`: behaviour-identical, but it keeps a dead path alive.
  - A local explicit type set: duplicates about 92 names and freezes strictness.
- **Upstream proposal:** export `known_event_types() -> frozenset[str]` from `spec_kitty_events.conformance`, and use it in upstream's own `persistence.py`. A second ask: public equivalents for the `diary` helpers that core's library-sync gate tests read (`_apply_annotation_delta`, `_RUNTIME_SLOTS`, `_REPLACE_SLOTS`, `_wp_state_from_event`).

## R-2 Where the door bans live

- **Decision:** extend the existing gates. See plan.md, Engineering Alignment.
- **Rationale:** the charter's single canonical authority rule.
- **Alternatives considered:** a new door-absence scanner. Rejected because it would duplicate the existing gates.

## R-3 Atomic seeding semantics vs the deleted plain append

- **Decision:** the helper delegates to `store.append_events_atomic`.
- **Differences, documented:**
  - It adds a newline when the existing text lacks one; the old door concatenated.
  - It refuses a symlinked log.
  - It replaces the inode; the old door appended in place.
- **Handling:** tests that pinned those quirks are rewritten to state the intended setup explicitly. See the census in `traces/approach.md`.

## R-4 Seam rename blast radius

- **Decision:** rename the seam and its residue: `adapters.py` identifiers and log labels, the `emit._saas_fan_out*` helpers, the lifecycle `*_hosted` fan-out, the test sink plugin and path-keyed ledgers. Keep no aliases.
- **Rationale:** the operator ruling, and the fact that `spec-kitty/event-router` is dead.
- **Alternatives considered:** renaming only in `adapters.py`. Rejected because it satisfies SC-003 on paper only.

## Adversarial squad dispositions (post-spec)

| Finding | Disposition |
|---|---|
| New door gate duplicates existing gates | Accepted. The existing gates are extended (plan). |
| The private-import gate lives in `test_events_tracker_public_imports.py`, not `test_shared_package_boundary.py` | Accepted. That gate is widened, and G-18 is corrected. |
| A test allowlist is priced debt | Accepted. The gate is limited to `src/` with no allowlist, and an upstream ask is filed in the PR. |
| Rename scope too narrow | Accepted. It covers the residue listed in R-4. |
| `repo_root_for_lifecycle_log` goes dead | Accepted. It is deleted in IC-04. |
| `ALLOWED_CALLERS` does not shrink; FR-001 and FR-002 land together | Accepted. They share a single work package. |
| The "byte-identical" claim needs a qualifier; the helper should batch | Accepted (R-3). |
| ADR and doc factual updates; env var docs; breaking changelog entry | Accepted (IC-06). |
| `ops-index.jsonl` is an index, not an event log | Accepted. The wording is corrected in data-model.md. |
