# Research: move-task / approval-gate ergonomics (#3469)

No `[NEEDS CLARIFICATION]` markers and no new/changed dependencies — this is a brownfield change to
existing CLI/library code. Research consolidates the design decisions grounded by the alignment +
scope grounding squads and the post-spec adversarial review.

## Decision 1 — Single-source gating classification

- **Decision**: Attach a *gating classification* to each discovered reference in ONE shared function
  (extend `discover_issue_references` / the `IssueReference` model in
  `tasks/issue_reference_discovery.py` + `tasks/issue_matrix.py`), consumed read-only by all three
  sites that compute "referenced-but-missing": the approval blocker
  (`tasks_parsing_validation.py`), `merge_gates._evaluate_issue_matrix_completeness_gate`, and
  `status/doctor.py`.
- **Rationale**: Grounding + review found the gating computation (`referenced_issues -
  matrix_issues`) forked across three sites. Narrowing in one place without the others would let a
  reference be non-gating at `approved` but re-block at merge or report dirty in doctor (a
  parallel-authority defect). One classifier closes the defect class by construction (DIRECTIVE_043).
- **Alternatives considered**: (a) narrow only the approval blocker — rejected: leaves merge/doctor
  divergent (NFR-006 violation). (b) A second scanner — rejected: violates single-canonical-authority.

## Decision 2 — Default-gating fail-safe

- **Decision**: A discovered reference is gating by default; classification only *demotes* to
  non-gating on a positive, explicit signal (leading `PR `/`pull` token → PR/commit ref; context
  markers `Follow-up:`, `baseline-red`, `see #`, `parent`, `epic` on the citation line →
  context-only; cross-repo URL → already excluded). Ambiguity stays gating.
- **Rationale**: The current gate is fail-closed (every ref gates). Narrowing must not flip it
  fail-open — a real implementation target misclassified as context-only would silently escape the
  completeness control on a governance artifact.
- **Alternatives considered**: default-non-gating with an explicit "gating" marker — rejected:
  inverts the safe direction and would require re-marking every real target.

## Decision 3 — Aggregate-over-occurrences classification

- **Decision**: Classify each issue number as an aggregate over ALL its occurrences; any
  implementation-target occurrence forces gating (impl-target wins).
- **Rationale**: `detect_issue_references` today dedupes by issue number keeping the first
  occurrence's line only. If a context citation appears before the impl-target citation, a
  first-occurrence classifier would silently downgrade the target — the exact edge case the spec
  forbids (FR-015, edge case).
- **Alternatives considered**: first-occurrence classification — rejected (silent downgrade).

## Decision 4 — `not-applicable` verdict: additive + terminal + non-gating

- **Decision**: Append `not-applicable` to `IssueMatrixVerdict` (StrEnum). It is non-gating at
  `approved` AND terminal — it passes the `done`/merge completeness gate unchanged (unlike
  `in-mission`, which is accepted at `approved` but rejected at `done`).
- **Rationale**: Verified additive-safe — `IssueMatrixVerdict(value)` parsing leaves the four legacy
  values validating unchanged (no migration, NFR-001). Terminal semantics avoid a `not-applicable`
  row re-blocking at merge.
- **Alternatives considered**: `context-only` / `reference` names — rejected by operator decision
  (`DM-01M302SBM26BGHEX36GC8YFJME`): `not-applicable` is the truthful catch-all. Non-terminal
  (in-mission-style) — rejected: would re-block a context row at merge.

## Decision 5 — Lever SSOT (classification vs verdict)

- **Decision**: classification decides whether a row is REQUIRED (gating); verdict decides whether an
  existing row is RESOLVED. When they disagree: an operator may record any verdict on any row; a
  `not-applicable` verdict makes a row non-gating regardless of classification; an
  implementation-target classification requires a row even if none was scaffolded.
- **Rationale**: Removes the ambiguity between the two levers (FR-013). The classifier is the
  authority for "must a row exist?"; the verdict is the authority for "is the existing row resolved?".

## Decision 6 — ADR supersedes stale WP09 `not_applicable` intent

- **Decision**: The ADR (FR-010) cites and supersedes the never-implemented WP09 `not_applicable`
  Gate-4 intent documented in `merge_gates.py`, so two definitions do not diverge.
- **Rationale**: Review found a docstring claiming a prior owner for a `not_applicable` verdict that
  was never implemented; the ADR must absorb it, not create a second authority.

## Decision 7 — Inert checkboxes are docs-only (#2816)

- **Decision**: Do not re-read `tasks.md` checkboxes for subtask completion; add guidance pointing at
  `mark-status` and stating checkboxes are not the source of truth.
- **Rationale**: Subtask completion is event-sourced by design (#2816, IC-10). Re-reading checkboxes
  would regress it (C-001).

## Supply-Chain Security (Planning)

Not applicable — this mission adds/upgrades/removes **no** dependencies. No registry, lifecycle-script,
or freshness decision is introduced. Recorded per the planning supply-chain section: silence here is a
true N/A, not an unexamined default.

## Adversarial Evidence Dispositions (post-spec squad)

Per `contracts/adversarial-evidence-contract.md`, every contested finding's disposition is recorded.
The post-spec adversarial review raised 3 BLOCKERs + 3 MAJORs + 2 MINORs; all **accepted** and folded
into the spec before planning:

| Finding | Severity | Disposition | Spec landing |
|---------|----------|-------------|--------------|
| No operational discriminator for gating vs context-only | BLOCKER | accepted | FR-001 + FR-011 |
| Narrowing inverts gate fail-safe direction | BLOCKER | accepted | FR-011 + SC-007 + US1.2 |
| Parallel authority: gating decided at 4 sites | BLOCKER | accepted | FR-012 + NFR-006 + US1.7 |
| Two levers not disambiguated (SSOT) | MAJOR | accepted | FR-013 |
| `not-applicable` lifecycle at done/merge unspecified | MAJOR | accepted | FR-014 + edge case |
| First-occurrence dedupe downgrades dual-cited target | MAJOR | accepted | FR-015 + US1.6 |
| Undisclosed prior WP09 `not_applicable` claim | MINOR | accepted | FR-010 |
| FR-005 alias reconciliation asymmetry | MINOR | accepted | FR-005 + US3.2 reworded |

No contested finding was dropped.
