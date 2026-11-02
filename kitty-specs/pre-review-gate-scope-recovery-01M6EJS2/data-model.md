# Data Model — Pre-review gate scope recovery

No new persisted entity is introduced. The mission formalizes three concepts that
already exist implicitly and pins the invariant that joins them.

## ReviewBudget

The single per-transition number that bounds every test leg of one
`in_progress → for_review` gate run.

| Field | Type | Source |
|---|---|---|
| `seconds` | positive `int` (1 … 86 400) | `review.test_timeout_seconds` when declared, else the shape default |
| `shape` | `ScopeShape` | derived from the resolved `ScopeSource` |

Resolution:

| Declaration | Scope shape | Resolved budget |
|---|---|---|
| `review.test_timeout_seconds: N` | any | `N` |
| absent | whole declared command (source has no per-file narrowing) | `WHOLE_COMMAND_TEST_TIMEOUT_SECONDS` = 1 200 |
| absent | bounded target list (explicit override, or a narrowing source) | `DEFAULT_TEST_TIMEOUT_SECONDS` = 300 |
| invalid (`true`, `0`, `"5m"`, 86 401) | any | refusal (`InvalidReviewTestTimeout`) — the shape default never masks it |

**Invariant B1 — one number per transition.** Baseline capture, the
baseline-receipt match and every head leg of the transition read the same
memoised value. A shape-triggered divergence would make
`BaselineTestResult.test_timeout_seconds` unequal to the resolved budget and
silently discard a valid receipt, degrading the gate to `UNVERIFIED_BASELINE`.

**Invariant B2 — a bounded run is narrower, never differently bounded.** A
pinned target list runs under the same resolved number; pinning changes *what*
runs, not the bound.

## ScopeShape

What the gate actually chose to execute.

| Value | Predicate | Runs |
|---|---|---|
| whole declared command | `not exposes_scope_breakdown(source)` | `review.test_command` in full |
| bounded target list | `exposes_scope_breakdown(source)` **or** the FR-004 frontmatter/config override tier | an explicit pytest target list |

The shape is derived from the `ScopeSource` capability predicate and the override
tier, never from changed-file names, timings or a second config key (C-001).

## PinnedScope (`pre_review_test_scope`)

Per-WP, optional, authored in the work package frontmatter.

| Property | Value |
|---|---|
| Storage | WP file frontmatter, `kitty-specs/<mission>/tasks/WP##-*.md` |
| Type | `str \| None` on `WPMetadata`; whitespace-separated pytest target list |
| Consumers | `tasks_move_task_gates._mt_pre_review_scope_override` (gate), `WPMetadata` (validation), `authored_subtask_roster` (readability) |
| Precedence | frontmatter `> ` config `review.pre_review_test_command` (deprecated) `>` auto-derived (empty for a non-narrowing source) |
| Empty value | treated as absent (falsy) — the gate keeps its auto-derived tier |

**Invariant P1 — readable means usable.** Any WP file that carries the key must
parse under the strict model *and* resolve its subtask roster; a documented,
gate-consumed field may not make a WP unreadable.

## Refusal evidence

The transition `policy_metadata["pre_review_gate"]` payload keeps its existing
keys and gains no schema change; only the human-readable `reason` text becomes
shape-aware. Constraints: single line, ≤ 800 characters, JSON-safe (NFR-002).

| Outcome | Reason must name |
|---|---|
| `timed_out` (whole command) | shape, declared command, resolved budget, policy-metadata location, both recoveries |
| `timed_out` (bounded) | shape, targets, resolved budget, recovery |
| `scope_oversized` | shape, targets, budget |

## State transitions (unchanged)

`in_progress → for_review`: gate runs → `NO_NEW_FAILURES` / `NEW_FAILURES`
(warn by default, opt-in block) / `NO_COVERAGE` / `UNVERIFIED_BASELINE` /
`SOURCE_MISMATCH` / `SKIPPED` proceed; `TIMED_OUT` / `CANCELLED` are terminal and
leave the lane unchanged. This mission changes none of these outcomes — only the
budget that produces `TIMED_OUT`, and the wording of the refusals.
