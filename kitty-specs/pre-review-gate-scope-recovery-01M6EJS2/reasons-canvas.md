# REASONS Canvas — Pre-review gate scope recovery

> Mission: pre-review-gate-scope-recovery-01M6EJS2
> Generated: 2026-11-02
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: software-engineer and automation-agent

## Requirements
- Problem: the pre-review regression gate cannot run in this repository. Its chosen scope is the whole declared command (`DeclaredCommandScopeSource.file_to_scope` returns `()` by design), so the 300 s scoped default bounds a whole-suite run and every `for_review` move is refused at the timeout; the recovery the gate itself advertises (`pre_review_test_scope` in the WP frontmatter) is rejected by `WPMetadata(extra="forbid")`, so applying it makes the WP unreadable to the subtask-roster guard ([research.md](research.md), F1/F2/F3).
- Acceptance: [spec.md](spec.md) FR-001 through FR-009 and SC-001 through SC-004 — the key parses, the roster guard reads it, the pinned targets run at head, a whole-declared-command run is bounded by a whole-command budget using one resolved number per transition, and both refusals name the shape they chose.
- Definition of done: failing-first tests through the production seams (`WPMetadata`/`authored_subtask_roster`, the resolved budget, the rendered verdict reason), the scoped fix, targeted green evidence plus the pre-existing gate suites, independent review, changelog fragment, draft PR flipped to ready. No gate weakened; no merge by the implementer.

## Entities
- Review budget: the one per-transition number bounding baseline capture, the receipt match and the candidate head run; resolved by `review/test_timeout.py`.
- Scope shape: *bounded target list* (explicit override, or a source that narrows per file) versus *whole declared command* (a source with no per-file narrowing). It is derived from the resolved `ScopeSource`, never from runtime timings.
- Pinned scope: the per-WP `pre_review_test_scope` frontmatter value — a whitespace-separated pytest target list, consumed by `tasks_move_task_gates._mt_pre_review_scope_override`.
- `WPMetadata` stays the single strict WP-frontmatter model; the new field is optional and inert for every other consumer.

## Approach
- Declare the field the gate already consumes on the model that validates every WP file, rather than loosening `extra="forbid"` or teaching the roster guard a second reader (single canonical authority).
- Keep one budget authority. The shape only selects the *default* when the project declares no `review.test_timeout_seconds`; the resolved number is then used by capture, the receipt match and the head run, so a shape mismatch can never discard a valid baseline.
- Diagnose, do not re-derive: the timeout reason names the shape, the command, the policy-metadata owner and the recovery. The retired census derivation is not resurrected (C-001), and no source-to-test naming heuristic is added.
- Budget the whole-command shape from source-controlled evidence, not runtime observations: this repository's CI bounds a whole per-PR lane at 20 minutes (`.github/workflows/ci-aggregate.yml`), which prices a whole-command default of 1,200 s.

## Structure
- Production: `src/specify_cli/status/wp_metadata.py` (one optional field), `src/specify_cli/review/test_timeout.py` (whole-command default + `whole_command` selector), `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py` (shape probe at the one budget-resolution seam), `src/specify_cli/review/pre_review_gate.py` (shape-aware refusal reason).
- Reused, not edited: `ScopeSource.exposes_scope_breakdown` as the narrowing-capability predicate; `gate_budget.assess_scope_budget` and its rules stay untouched; the FR-004 override tier keeps `run_scoped_tests_at_head` as its runner.
- Docs: `docs/development/how-to/review-gates.md`, `docs/configuration/review-test-budget.md`, `docs/api/configuration.md`.
- Tests: one focused module for the WP-model/roster seam, one for budget shape resolution, and the diagnostic assertions added where the reason is already rendered; the existing gate suites are the ratchet.

## Operations
1. Opening campsite check of the touched surfaces; record the no-enabler conclusion instead of broadening scope.
2. Failing-first: a WP file carrying `pre_review_test_scope` must be rejected by `WPMetadata`/the roster guard today, and the whole-command budget assertion must fail against the 300 s default today. Commit RED.
3. Implement the field, the shape selector and the shape-aware refusals in that order, one commit each.
4. Run the targeted suites (`tests/review/`, `tests/specify_cli/status/test_wp_metadata.py`, the move-task gate tests), the new tests, `ruff`, and the docs freshness check; record commands and results.
5. Wrap up: accept, issue verdict, independent review of the aggregate diff, consolidate/compact/rebase, changelog fragment, draft PR. The operator merges.

## Norms
- Canonical command surfaces and the resolved mission handle; targeted staging only.
- Python typing/lint standards; no broad suppressions; no new dependencies; no new configuration key.
- New-code coverage ≥90% on changed lines; the reviewer reads the real diff and live evidence, not a summary.
- Terminology: Mission (not feature); work package; lane; review budget; scope shape.

## Safeguards
- Do not weaken a gate: `TIMED_OUT`/`CANCELLED` stay terminal, the opt-in `NEW_FAILURES` block is unchanged, `--skip-pre-review-gate` stays an explicit opt-out, and the receipt-budget identity keeps invalidating stale receipts.
- Do not resurrect the census derivation or add a heuristic source-to-test mapping (C-001).
- Do not turn `pre_review_test_command` into a second scope surface; it stays a deprecated alias (C-002).
- Do not let the shape default mask an invalid `review.test_timeout_seconds` declaration.
- Do not scope the baseline capture leg in this mission; it is a named follow-up.
- No full heavy suite in-mission; no main push; no merge; no auto-merge.

## Deviations (append-only)
