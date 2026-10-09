# Tracer: tooling friction — green-reds-coord-review-repin

## Pre-review regression gate: whole-suite fallback for a test-only WP
- `move-task --to for_review` runs the pre-review regression gate
  (`src/specify_cli/review/pre_review_gate.py`). For a WP whose `owned_files`
  is a **test file**, the scope source derives **empty** test targets (it maps
  `src/` → tests; a test file maps to nothing). A non-narrowing
  `DeclaredCommandScopeSource` then runs its **whole declared suite**, which
  exceeds the 300s budget → `TIMED_OUT` (BudgetClassification UNKNOWN), blocking
  the transition. Observed twice (once aggravated by concurrent `make test-fast`
  CPU contention).
- Impact: a pure test-remediation WP cannot pass the gate on the happy path even
  though the change is verified green independently.

## Frontmatter override `pre_review_test_scope` is incompatible with WPMetadata
- FR-004 lets a WP scope the gate via the `pre_review_test_scope` frontmatter key
  (`tasks_move_task_gates._mt_pre_review_scope_override`, read with raw
  `extract_scalar`). But the subtask-roster resolver
  (`core/subtask_rows.authored_subtask_roster`) validates the SAME frontmatter
  with `WPMetadata(extra="forbid")`, and `pre_review_test_scope` is NOT a
  `WPMetadata` field — so authoring it makes the WP file "unreadable" and blocks
  the move entirely. Two readers of one frontmatter disagree on strictness.
- This is a genuine upstream gap (candidate issue). Out of scope for #5928/#5948;
  recorded here rather than worked around by fixing WPMetadata.

## Decision (DIRECTIVE_003)
- Reverted the frontmatter override. Used the documented opt-out
  `SPEC_KITTY_SKIP_PRE_REVIEW_GATE` / `--skip-pre-review-gate` (CLAUDE.md
  "baseline-red gotcha" category 2) to move WP01 to for_review. Justified: the
  gate timed out on an unbounded whole-suite fallback and surfaced NO failures;
  the change is test-only (zero `src/` lines) so the gate's purpose (catch a WP
  breaking a consumer outside its owned set) is inapplicable; and the change is
  independently verified green — the full file `test_trio_json_envelope.py`
  (8 passed) and `make test-fast` (2500 passed, 8 skipped).
