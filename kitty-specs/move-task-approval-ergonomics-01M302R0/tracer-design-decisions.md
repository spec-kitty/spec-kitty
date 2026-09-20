# Tracer — Design Decisions

Mission: move-task / approval-gate ergonomics (#3469)

## Seed (planning)

- **Verdict value name = `not-applicable`** (Decision `DM-01M302SBM26BGHEX36GC8YFJME`, operator-
  confirmed). Chosen over `context-only`/`reference` as the truthful catch-all for any row where
  no mission work applies (context citation OR PR/commit reference).
- **Both levers + lightweight ADR** (operator-confirmed): narrow discovery classification AND add
  the verdict value. Rationale: classification stops most false gating rows at the source; the
  verdict value gives the residual/ambiguous/operator-recorded rows an honest value. The ADR
  records the new value, its non-gating semantics, the classification narrowing, and why it is
  backward-compatible (so a later maintainer does not "clean up" the new value).
- **Additive enum only** — no removal/rename of the four existing verdicts; existing
  `issue-matrix.json` validates without migration (C-003 / NFR-001).
- **Inert checkboxes = docs-only** — subtask completion is event-sourced (#2816); do not re-read
  `tasks.md` checkboxes (C-001).
- **Flag reconciliation** — `move-task` gets `--actor`/`--reason` aliases matching
  `issue-verdict`'s existing `--actor`; the two sibling commands present one vocabulary.

## Resolved by post-spec adversarial review (folded into spec FR-011..FR-015, NFR-006)

- **SSOT for "is this reference gating?"** = ONE shared function extending the discovery surface /
  `IssueReference` (FR-012), consumed identically by the approval blocker, `merge_gates`, and
  `status/doctor` — the gating computation is currently forked across all three.
- **Lever roles pinned** (FR-013): classification decides whether a row is REQUIRED; verdict
  decides whether an existing row is RESOLVED. `not-applicable` verdict makes a row non-gating
  regardless of classification; an implementation-target classification requires a row.
- **Fail-safe direction** (FR-011): default-gating; classification only DEMOTES on an explicit
  signal; ambiguity stays gating. Narrowing must not flip the gate fail-open.
- **`not-applicable` is terminal** (FR-014): passes `done`/merge unchanged, unlike `in-mission`.
- **Multi-occurrence** (FR-015): classify as an aggregate over all occurrences (today's
  first-occurrence dedupe would silently downgrade a dual-cited impl-target).
- **ADR supersedes prior WP09 `not_applicable` intent** (FR-010) documented but never implemented
  in `merge_gates.py`.

## Post-tasks squads (anti-laziness + brownfield scout) — folded into WP prompts

- **Single-source is a HELPER, not just a field** (both squads, top risk): WP01 must EXPORT
  `gating_issue_numbers`/`is_gating` from `tasks/`; WP02+WP03 import it — no per-site
  `classification == implementation_target` re-encode. Folded into WP01 T003/DoD, WP02 T009, WP03
  T012/T013, contract C2.1.
- **Red-first must hit the observable defect**: WP01 T001 now drives RED through `scaffold_issue_matrix`
  (not the classifier symbol); WP03 T011 now asserts end-state per-site non-gating (RED on main) + a
  fail-OPEN guard (bare `#N` still gates) — the "all three identical" framing was vacuously green.
- **Anchor drift corrected**: in-mission gating flip is `tasks_parsing_validation.py:271-272` (not the
  296-300 message block); move-task lives in `tasks.py:657` (Typer alias pattern at `init.py:787`);
  merge_gates `L393/395` + WP09 docstring `L375-378`; doctor `L433/439`.
- **FR-015 fights TWO dedupe layers** (discovery L114-118 + detect L171-178); NamedTuple append-defaults;
  deferred-import monkeypatch seam (discovery L107) preserved; 4th consumer `review/__init__.py:305`.
- **T004 keeps the audit row** (scaffold non-gating refs AS non-gating rows, never omit) — consumer-side
  filtering is the load-bearing change.
- **WP05 gained a WP04 dependency** (its docs mirror WP04's aliases). NFR-002 non-regression runs added
  to WP02 (#4330) and WP04 (#2816) test strategies.

## Appended during implement

_(to be filled per WP)_
