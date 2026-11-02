# Discovery Research — pre-review gate scope recovery (issue #6865)

Mission: `pre-review-gate-scope-recovery-01M6EJS2` · Issue: spec-kitty/spec-kitty#6865

## Problem statement (from the issue, restated precisely)

A `move-task --to for_review` on this repository either

1. runs the whole declared `make test-fast` and is refused with
   `Pre-review regression gate timed_out; transition not applied` at the 300 s
   default budget, or
2. is refused differently the moment the operator applies the recovery the gate
   itself advertises: a bounded `pre_review_test_scope` in the WP frontmatter
   makes the WP unreadable to `WPMetadata` (`extra="forbid"`), so the subtask-roster
   guard fails with `Cannot resolve subtask roster for WPxx: <file>.md is unreadable`.

So the gate's only usable path in this repository is `--skip-pre-review-gate`,
which is the exact outcome the gate exists to prevent.

## Evidence gathered on current `main` (`9aed3a8012`)

Reproduction (run in this clone, `uv run --frozen python /tmp/repro_6865.py`):

```
WPMetadata: REJECTED -> pre_review_test_scope
scope source: DeclaredCommandScopeSource
test_command: ['sh', '-c', 'export SPEC_KITTY_CMD_OUTPUT_FILE=/tmp/spec-kitty-declared-cmd-7lecr8rk/output.xml;
               PYTEST_ADDOPTS="--junitxml=${SPEC_KITTY_CMD_OUTPUT_FILE}" make test-fast']
file_to_scope('src/specify_cli/review/pre_review_gate.py'): ()
head argv with derived targets: ['sh', '-c', '<the whole make test-fast script>', 'tests/review']
```

Three distinct, independently verifiable facts fall out of that:

- **F1 — the derived scope is always empty for this repository's source.**
  `DeclaredCommandScopeSource.file_to_scope` returns `()` for every path by
  design (`src/specify_cli/review/scope_source.py`): the source is
  layout-agnostic and runs its declared command in full. The census-driven
  derivation that used to produce shard/composite targets was retired
  (mission `scopesource-gate-followup-01KY6S9P`, FR-001). So on this repo the
  gate's `ScopeResult.test_targets` is `()` on every ordinary `for_review` move.
- **F2 — even a non-empty target list would never narrow the run.**
  `pre_review_gate._evaluate_via_scope_source` builds the argv as
  `[*command, *scope.test_targets]`, and a `DeclaredCommandScopeSource` command
  is `["sh", "-c", "<script>"]`. Appending after the script string makes the
  targets `$0`, `$1`, … of the shell — passed to `make` never, consumed never.
  The surface that *does* honour a target list is the FR-004 override tier
  (`_mt_pre_review_gate_with_override_scope` → `evaluate_with_scope` with
  `scope_source=None` → `run_scoped_tests_at_head` → a real scoped `pytest`
  invocation), i.e. exactly the path that F3 blocks.
- **F3 — the documented recovery is unreadable to the WP model.**
  `specify_cli/status/wp_metadata.WPMetadata` sets `extra="forbid"` and has no
  `pre_review_test_scope` field, so
  `specify_cli/core/subtask_rows.authored_subtask_roster` — which validates the
  same frontmatter through `WPMetadata` and converts every exception into
  `"Cannot resolve subtask roster for WPxx: <file>.md is unreadable"` — refuses
  the WP. The key is documented in `docs/development/how-to/review-gates.md`,
  advertised in the gate's own refusal message and consumed at
  `tasks_move_task_gates._mt_pre_review_scope_override`, so the model, not the
  operator, is wrong.

Measured cost (this host, other agents running their own suites concurrently):
`make test-fast` was still running after 5 minutes in a clean clone, i.e. the
300 s default budget in `.kittify/config.yaml` (which declares no
`review.test_timeout_seconds`) cannot hold the command this repository declares.

## Decisions

- **D1 — `WPMetadata` accepts the documented, gate-consumed key.** Add
  `pre_review_test_scope: str | None` to the review-metadata block of
  `WPMetadata`. It is a real, documented, gate-consumed frontmatter field; the
  "if a key appears in the wild, add it to the model" rule in the module
  docstring is exactly this case. Nothing else about the model changes: the
  field is optional, additive, and inert for every other consumer.
- **D2 — the gate names the scope it chose, and why.** The timeout
  diagnostic today says `normalized targets: (empty); … This is a classification
  candidate for a reviewed metadata update` and never says *which* scope ran.
  It must name (a) the scope shape it actually executed — the whole declared
  command versus a bounded target list, (b) the declared command that ran, and
  (c) the concrete recovery for that shape. The `scope_oversized` message must
  name its shape the same way. This is the diagnosability half of the issue's
  first paragraph and the whole of its third "Done when" bullet.
- **D3 — the budget matches the scope the gate actually chose.** A
  whole-declared-command run is not a bounded run, so the 300 s *scoped* default
  is the wrong bound for it. The declared-command shape resolves a
  whole-command budget — `review.test_timeout_seconds` when the project declares
  one, otherwise a documented whole-command default that reflects a
  multi-minute declared suite — while a bounded target list keeps the scoped
  default. This is the issue's stated alternative to re-deriving targets, it
  invents no timing policy from runtime observations, and it keeps one knob.
- **D4 — this repository declares its own budget.** `.kittify/config.yaml` gains
  an explicit `review.test_timeout_seconds` measured against this repo's own
  `make test-fast`, so an ordinary `for_review` move completes here without
  `--skip-pre-review-gate`. The declared value is a repo-local operational
  statement about a repo-local command, not a product default change.
- **D5 — the ticket-spirit guard: no gate is weakened.** Nothing disables,
  skips or xfails a gate. `TIMED_OUT` stays terminal, the opt-in
  `NEW_FAILURES` block is untouched, `--skip-pre-review-gate` stays an explicit
  per-invocation opt-out, and the baseline-receipt budget identity still
  invalidates a stale receipt.
- **D6 — small, honest scope.** The retired census is *not* resurrected: no
  heuristic `src/` → `tests/` path namer, no new scope-map config. The issue
  offers budget-scaling as an equal alternative and that is the branch taken.

## Invariants to preserve (found by reading the current call sites)

- `_mt_review_test_timeout` is the single budget authority for baseline capture,
  the receipt match (`baseline.test_timeout_seconds != resolved` discards the
  baseline) and the head run. Whatever D3 does, a capture and a head run for the
  same WP must resolve the *same* number, or every gate silently degrades to
  `UNVERIFIED_BASELINE` and can never block.
- `review.test_command` remains the single test-command authority
  (`ScopeSource`, FR-011); `review.pre_review_test_command` stays a deprecated
  alias, not a second scope surface.
- The FR-004 override tier is the only path that yields a genuinely bounded run
  today; D1 is what makes it reachable.
- `docs/configuration/review-test-budget.md` and
  `docs/development/how-to/review-gates.md` already document the budget and the
  recovery surfaces; both need the shape distinction added, and the changelog
  needs a per-PR fragment (`docs/changelog/unreleased/<pr>.fixed.md`).

## Open questions (resolved during plan/tasks)

- Q1 — Where does the shape decision live so capture and the head run cannot
  disagree? (Resolved: the shape is a property of the *resolved* scope and the
  budget stays one number per transition; capture always runs the declared
  command, so it uses the declared-command budget, and the head run's bounded
  tier keeps the same resolved number rather than a second one.)
- Q2 — Does the whole-command default need a new config key? (No: one knob,
  `review.test_timeout_seconds`, with a shape-dependent *default*.)
- Q3 — Should the timeout diagnostic carry the full declared command? (Truncate
  to a bounded, single-line form; the command can be long and the reason is
  emitted into `--json` transition evidence as well as console output.)
