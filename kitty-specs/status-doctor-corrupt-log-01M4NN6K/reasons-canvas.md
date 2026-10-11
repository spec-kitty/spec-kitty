# REASONS Canvas — Status Doctor Corrupt Log

> Mission: status-doctor-corrupt-log-01M4NN6K
> Generated: 2026-10-11
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: software-engineer and automation-agent

## Requirements
- Problem: unreadable authoritative history currently yields false health without a snapshot or a crash with one ([research.md](research.md), E1).
- Acceptance: [spec.md](spec.md), FR-001 through FR-006 and SC-001 through SC-004; five failure classes, both snapshot states, visible CLI failure and truthful location.
- Definition of done: failing-first test commit, scoped production fix, full targeted green evidence, byte-preservation and healthy controls, independent thorough review, PR only. No merger performed by an implementation agent.

## Entities
- Mission, status event log, status snapshot and Finding have the existing status-domain meanings; [spec.md](spec.md#key-entities-include-if-the-mission-involves-data).
- Event log remains authority; snapshot is derived evidence, never an alternate health authority. Use Mission, not legacy product terminology. No new entity/model is needed.

## Approach
- Consume the existing canonical reader's success/failure as the diagnosis boundary independently of snapshot availability; do not create a second parser.
- Failure is not empty history: do not run misleading history-dependent reconciliation/drift/backfill paths after a failed read.
- Tradeoff: local status-doctor fix over speculative cross-doctor unification. See #5304 for context only; D1–D6 in [research.md](research.md) record the bounded decision. Planner records supplied constraints, not new product architecture.

## Structure
- Candidate production surface: `src/specify_cli/status/doctor.py`; tests `tests/status/test_doctor.py`, optional focused status test file.
- Existing reader: `src/specify_cli/status/store.py`; touch only add AttributeError to existing annotation from_dict catch tuple for witnessed malformed delta/subtasks, preserving canonical physical-line StoreError; add tests/status/test_store.py regressions. Existing CLI renderer is an acceptance surface, not a planned production change.
- One WP01; implementer owns product/tests, reviewer is independent, planner owns this reasoning and sequencing only. No external-package, reducer or decision-domain change.

## Operations
1. Opening campsite check of touched surfaces; record no-enabler conclusion or distinct behavior-preserving tidy step, never broaden scope.
2. Write failing-first tests through real `run_doctor` and CLI; run and commit RED before production edits. Use transitional `regression` markers only when required, remove on fix.
3. Apply bounded failure translation, preserving reader authority and evidence bytes. Verify each snapshot half and location/recovery semantics.
4. Run targeted status/CLI checks, same-fixture valid controls, scoped quality checks and independent review. Record commands/counts and red→green commits.
5. Parent operator prepares PR to main; no merge/consolidation or main push.

## Norms
- Canonical source packs/CLI rc7; explicit mission handle; targeted staging only.
- Python typing/lint/format standards, no broad suppressions; no new dependencies or version numbers.
- New-code coverage ≥90%; independent reviewer verifies actual diff and live targeted evidence, not a summary alone. Do not claim planning evidence as implementation tests.

## Safeguards
- Preserve every existing log/snapshot byte and missing-file state. No automatic writes, destructive cleanup or blind log deletion advice.
- Path/reason always; physical 1-based record line only when truthful. No invented I/O line or doctor-local parser. Doctor catches exactly StoreError/OSError/UnicodeError, not broad Exception; store normalization is only the annotation-decoder tuple addition. Skip all log-dependent checks including reviewer-self-approval, retain independent issue-matrix/sparse/frontmatter checks after failure.
- Keep supported lifecycle/status/annotation acceptance and missing/empty/blank behavior, real drift and WP reconciliation.
- No credentials in diagnostics; no full local architectural/e2e/performance/test-full sweep.
- All writes on issue-5924-status-doctor-corrupt-log; unrelated kitty-ops/evidence stay out of commits; no main mutations.

## Deviations (append-only)

2026-10-11 — WP01 — Initially no store adjustment needed — parent verified canonical annotation-aware parser and physical-line diagnostics.
- 2026-10-11 — WP01 — Approved minimal annotation error normalization — parent then witnessed delta=[] AttributeError; add AttributeError only to existing annotation decoder catch tuple with direct store/doctor regressions. Note overlap with PR #5953; no general parser/model refactor.
