---
work_package_id: WP01
title: Reference classification seam (foundation)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-011
- FR-012
- FR-015
- NFR-003
- NFR-005
planning_base_branch: fix/move-task-approval-ergonomics
merge_target_branch: fix/move-task-approval-ergonomics
branch_strategy: Planning artifacts for this mission were generated on fix/move-task-approval-ergonomics. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/move-task-approval-ergonomics unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-move-task-approval-ergonomics-01M302R0
base_commit: dd29b6adae5092f36eaee7328d2fb019b62e89f2
created_at: '2026-09-20T19:38:25.765401+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Implementation
history:
- at: '2026-09-20T19:15:00Z'
  actor: system
  action: Prompt generated for move-task-approval-ergonomics mission
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tasks/
create_intent:
- tests/tasks/test_issue_reference_classification.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/tasks/issue_reference_discovery.py
- src/specify_cli/tasks/issue_matrix.py
- tests/tasks/test_issue_reference_classification.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '3469'
---

# Work Package Prompt: WP01 – Reference classification seam

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (role: implementer) via the profile-load skill
(`/ad-hoc-profile-load` or `spec-kitty charter context --action implement`) before reading anything
else. Then read `spec.md`, `plan.md`, `data-model.md`, and `contracts/classification-and-verdict-contract.md`
in this mission's feature dir (`kitty-specs/move-task-approval-ergonomics-01M302R0/`).

## Objective

Create ONE shared, pure classifier that labels every discovered `#NNNN` reference with a
**gating classification**: `implementation_target` (gating), `context_only` (non-gating), or
`pr_or_commit_ref` (non-gating). The classifier is the single source of truth WP02 and WP03 consume.
Two load-bearing rules:

1. **Default-gating fail-safe (FR-011)** — a reference is `implementation_target` unless a positive,
   explicit signal demotes it. Ambiguity stays gating. Narrowing must NOT flip the gate fail-open.
2. **Aggregate over all occurrences (FR-015)** — classify each issue number from ALL its occurrences,
   not the first only; any implementation-target occurrence forces gating (impl-target wins).

## Context (grounding — anchors VERIFIED by brownfield scout at current HEAD)

- `src/specify_cli/tasks/issue_reference_discovery.py` (124 lines) — `discover_issue_references(feature_dir) -> list[IssueReference]`
  at L73–121; scans `spec.md`, `plan.md`, `research.md`, `analysis-report.md`, `tasks/*.md`,
  `contracts/*.md`. **First-occurrence dedupe at L114–118** (`seen: dict[int, tuple[str,str]]`, keeps
  first (file,line) only). `detect_issue_references` is imported DEFERRED inside the function at L107
  so tests monkeypatch `issue_matrix.detect_issue_references` — **preserve that deferred-import seam**.
- `src/specify_cli/tasks/issue_matrix.py` (401 lines) — `detect_issue_references` body at **L151–179**
  (its own per-file `seen` dedupe at L171–178 — the SECOND dedupe layer); regex `_GH_ISSUE_PATTERN`
  L88–94; `_matched_issue_number` L111–130 (cross-repo URL → None L128–129; `/pull/` never matched,
  regex anchored to `/issues/`). **Keep that exclusion; do not regress it.** `IssueReference` is a
  **NamedTuple(number:int, first_line_context:str, source_file:str)** at L133–148, with positional
  constructors at issue_matrix.py L179 and discovery L120 — so **append new fields WITH DEFAULTS ONLY;
  do not reorder**. Scaffold `scaffold_issue_matrix` L317–401 (calls detect at L370, writes
  `verdict="unknown"` rows). Leave the `unknown` placeholder semantics alone.
- **FR-015 fights TWO dedupe layers** (discovery L114–118 AND detect L171–178): occurrences are
  discarded at both. Classify BEFORE/around both, or thread occurrences through `detect_issue_references`
  too. First-occurrence classification would silently downgrade a context-first/target-second citation.
- **All callers of `discover_issue_references`** (your signature-change blast radius — all must stay
  green): `status/doctor.py:391` [WP03], `cli/commands/review/__init__.py:305` (truthiness-only
  zero-ref path — **a 4th consumer no WP owns; verify it stays green**), `tasks_parsing_validation.py:135,234`
  [WP02], `policy/merge_gates.py:384` [WP03], plus tests. All src consumers read only `ref.number`.
- Existing tests: `tests/tasks/test_issue_reference_discovery.py`, `test_zero_reference_not_applicable.py`,
  `test_issue_ref_url_provenance.py`. Extend, do not duplicate.

## Subtasks

### T001 — Red-first regression test through the OBSERVABLE entry point (RED before any code)
Add `tests/tasks/test_issue_reference_classification.py` marked `@pytest.mark.regression` and pinned
to `#3469`. **Drive the RED through the pre-existing observable defect — `scaffold_issue_matrix`
(the discovery→scaffold path) — NOT through the new classifier symbol.** The anti-laziness review
flagged that a test pinned to `classify(...) == context_only` goes green the moment the symbol exists,
weakly coupled to the real gate outcome. Assert the OBSERVABLE outcome on a fixture spec/plan:
- a `PR #300` ref and a context-marked `#200` do **NOT** produce a **gating** row;
- a bare unmarked `#100` **DOES** produce a gating row (fail-safe still holds);
- `#400` cited once as context and once as an implementation target produces a gating row.
This is RED on current `main` (all refs scaffold gating rows today) and GREEN after the fix. Keep the
direct-classifier assertions in T005 as unit coverage, not as the red-first anchor.

### T002 — `GatingClass` + pure classifier
Add a `GatingClass` enum/value object and a pure classification function (no I/O, deterministic) in
the discovery module. Signals (all case-insensitive, matched on the occurrence's line/preceding
token):
- **PR/commit**: a leading `PR `/`PR#`/`pull` token adjacent to the `#N`, or a `/pull/<n>` URL.
- **context-only**: an explicit context marker on the line (`Follow-up:`, `baseline-red`, `see #`,
  `parent`, `epic`; extend the list judiciously and document it).
- **default**: `implementation_target`.
Classification of an issue number = aggregate over all its occurrences: if ANY occurrence is
`implementation_target`, the number is `implementation_target`; else if all are the same non-gating
class, use it; if mixed non-gating, prefer `pr_or_commit_ref` only when every occurrence is a PR ref,
otherwise `context_only`. Keep the rule readable (complexity ≤15) — extract helpers if needed.

### T003 — Retain occurrences, attach classification, AND export the shared gating helper
Extend `IssueReference` to carry all occurrences and the derived `classification` (append fields WITH
DEFAULTS — it is a NamedTuple with positional constructors). Update `discover_issue_references` to stop
discarding non-first occurrences before classification (handle BOTH dedupe layers). Preserve the
deferred-import monkeypatch seam at discovery L107.

**CRITICAL single-source deliverable (FR-012 — both squads flagged this as the top risk):** export ONE
shared gating helper from `tasks/issue_reference_discovery.py` — `gating_issue_numbers(feature_dir) -> set[str]`
(returns the gating-only referenced-issue strings, e.g. `{"#100"}`) and/or `is_gating(ref) -> bool`.
This helper is the SINGLE authority for "is this reference gating?". WP02 (approval blocker) and WP03
(merge_gates, doctor) **consume this helper by import** — they must NOT re-encode
`ref.classification == implementation_target` locally (that would recreate the parallel-authority
defect this mission exists to kill). Make the helper an explicit, tested export.

### T004 — Scaffold records non-gating classes as non-gating ROWS (keep the audit trail)
Update the scaffold in `issue_matrix.py` so `context_only` / `pr_or_commit_ref` references are written
as **non-gating rows** (a non-gating marker the gate honors) — **do NOT omit them**. US1.4/SC-002 need
the row to exist so an operator can record `not-applicable` on it and the audit stays honest; omitting
the row also risks a "referenced with no row" gate-worsening if a consumer forgets to filter. The
load-bearing change is **consumer-side filtering of `referenced_issues` by the shared helper** (T003);
T004 is subordinate to it. `implementation_target` references still scaffold gating rows exactly as
today; leave the `unknown` placeholder semantics alone.

### T005 — Unit tests for signal coverage
Beyond T001's regression, add focused unit tests: each marker form; PR hash vs URL; cross-repo URL
still excluded; multi-occurrence impl-target-wins; ambiguous/empty → gating. Execute the classifier
directly (Sonar new-code coverage).

## Branch Strategy

Planning base: `fix/move-task-approval-ergonomics`. Final merge target: `fix/move-task-approval-ergonomics`
(then upstream `main` via PR). Execution worktrees are allocated per computed lane from `lanes.json`
(this WP is the spine root). Do not hardcode branch names.

## Test Strategy (ATDD / red-first — required)

T001 lands RED first, through the pre-existing discovery entry point, pinned to `#3469`. After the
fix it is GREEN. Targeted run: `PWHEADLESS=1 .venv/bin/python -m pytest tests/tasks/ -q`. Do not run
a bare `uv run`.

## Definition of Done

- Classifier is pure, deterministic, aggregate-over-occurrences (both dedupe layers), default-gating.
- **A single shared gating helper (`gating_issue_numbers` / `is_gating`) is exported from `tasks/`
  and unit-tested** — this is the FR-012 single-source authority WP02/WP03 import.
- `context_only`/`pr_or_commit_ref` scaffold as NON-gating rows (audit trail kept), not gating rows,
  not omitted; `implementation_target` still scaffolds gating rows.
- Cross-repo exclusion preserved; NamedTuple append-with-defaults; deferred-import seam intact; the 4
  `discover_issue_references` consumers (incl. `review/__init__.py:305`) stay green.
- T001 RED→GREEN through `scaffold_issue_matrix`; unit tests cover every signal; ruff + mypy --strict
  clean; complexity ≤15.

## Reviewer Guidance

Verify the fail-safe direction: an unmarked bare `#N` MUST gate. Confirm the multi-occurrence
aggregate (a context-first, target-second citation gates). Confirm no cross-repo regression. Confirm
existing discovery callers still work (grep + run their tests).
