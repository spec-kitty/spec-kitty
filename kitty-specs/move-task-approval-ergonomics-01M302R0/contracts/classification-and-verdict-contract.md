# Behavior Contract: reference classification + verdict vocabulary

This is the executable-intent contract WP02/WP03 consume from WP01. Each clause maps to an FR and is
covered by an ATDD test (red-first, NFR-005).

## C1 — Classification (FR-001, FR-011, FR-015)

- **C1.1** Given a bare unmarked `#N` in ordinary prose, the classifier returns `implementation_target`
  (gating). *(fail-safe default)*
- **C1.2** Given `#N` whose every occurrence line carries a context marker (`Follow-up:`,
  `baseline-red`, `see #`, `parent`, `epic`), the classifier returns `context_only` (non-gating).
- **C1.3** Given `PR #N` (hash form) or a `/pull/N` URL, the classifier returns `pr_or_commit_ref`
  (non-gating).
- **C1.4** Given `#N` cited once as context and once as an implementation target, the classifier
  returns `implementation_target` (aggregate; impl-target wins).
- **C1.5** The classifier is pure and deterministic (no I/O, stable across runs).

## C2 — Single-source consumption (FR-012, NFR-006)

- **C2.1** WP01 exports ONE shared gating helper (`gating_issue_numbers(feature_dir) -> set[str]` and/or
  `is_gating(ref) -> bool`) from `tasks/issue_reference_discovery.py`. The approval blocker,
  `merge_gates`, and `status/doctor` all **import and consume that helper** — none re-encodes the
  `classification == implementation_target` predicate locally (no per-site fork).
- **C2.2** A reference non-gating at the `approved` transition is non-gating at merge and reports
  clean in doctor (0 divergence), and a bare unmarked `#N` STILL gates at all three (no fail-open).

## C3 — Verdict vocabulary (FR-003, FR-004, FR-014)

- **C3.1** `IssueMatrixVerdict` accepts `not-applicable` in addition to the four legacy values.
- **C3.2** The four legacy values validate unchanged; an existing `issue-matrix.json` needs no
  migration.
- **C3.3** A row with verdict `not-applicable` does not block the `approved` transition.
- **C3.4** A row with verdict `not-applicable` passes the `done`/merge completeness gate unchanged
  (terminal) — contrast `in-mission`, which is rejected at `done`.

## C4 — Lever SSOT (FR-013)

- **C4.1** Classification decides row-requirement; verdict decides row-resolution.
- **C4.2** An operator may record any verdict on any row.
- **C4.3** An `implementation_target` classification requires a row even if none was scaffolded.

## C5 — CLI ergonomics (FR-005, FR-006, FR-009)

- **C5.1** `move-task WP## --to <lane> --actor X --reason Y` succeeds and applies the same values as
  `--agent X --note Y`.
- **C5.2** `issue-verdict --help` lists `not-applicable` and documents the `deferred-with-followup`
  evidence-token rule (`#NNN` or `Follow-up:`) pre-flight.
- **C5.3** `move-task --help` `--assignee` text describes its actual any-lane behavior (no "when
  moving to doing").

## C6 — Early warning (FR-007)

- **C6.1** The specify/plan/tasks/analyze mission-step prompts carry a non-gating note that approvals
  require an issue-matrix verdict for referenced issues.

## C7 — Non-regression (C-001, C-002, NFR-002)

- **C7.1** No code path re-reads `tasks.md` checkboxes for subtask completion.
- **C7.2** The #4330 behaviors (JSON-first error string, batched missing-row surfacing) are unchanged.
