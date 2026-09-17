# Phase 0 Research: Source-aware unblock refusal message

Grounding for this mission was performed by a three-lens squad (behavior-matrix,
adversarial regression-hole, blast-radius) against `main` at `ee8e7885ed`. This
file consolidates the decisions; the live-probe evidence is summarized inline.

## Decision 1 — Message-only, reachability-based partition (state machine untouched)

- **Decision**: Enrich the `_guard_planned_rollback` refusal by branching the
  message on `Lane.PLANNED in wp_state_for(resolve_lane_alias(old_lane)).allowed_targets()`.
  Do **not** change any allow/deny rule. Do **not** legalize `blocked → planned`.
- **Rationale**: F-51 is a *misleading message*, not a missing transition. The
  intended recovery from `blocked` is the one-hop `blocked → in_progress` (which
  is already legal: `BlockedState.allowed_targets == {in_progress, canceled}`).
  Rewinding to `planned` would discard the claim/progress. Operator confirmed
  this and declined expanding scope (decision `01M2Q4F897ANB84HA6EHA9DG98`).
- **Alternatives considered**:
  - *Purely additive message* (keep "requires review feedback" for all sources,
    append legal targets): rejected — leaves the misleading feedback demand on
    `blocked`, which is the exact complaint.
  - *Legalize `blocked → planned` in the state machine*: rejected by operator —
    larger change, alters allow/deny, needs its own resurrection-safety review,
    and the one-hop resume already exists.
  - *Blocked-only special case*: rejected in favor of reachability — `canceled`
    and `done` carry the same misleading feedback demand today; the reachability
    key fixes all three with no extra branching and no allow/deny duplication.

## Decision 2 — Keep the guard unconditional; read source lane only to shape text

- **Decision**: The four feedback-field checks (the allow/deny) are unchanged.
  The source lane is read *inside* the refusal construction, never to decide
  whether to refuse. Every branch of the missing-feedback path returns
  `RefuseExit1`.
- **Rationale (the load-bearing why)**: `_guard_planned_rollback` runs in the
  `_GUARDS` chain **before** `build_transition_plan`/the state machine
  (`decide_transition`). Its "cannot be bypassed with --force" promise holds
  only because it refuses first and never consults the source to decide. The
  prior attempt (WP02) turned it into a source-scoped early-return keyed on
  `is_run_affecting` (False for `genesis`/`blocked`/`done`/`canceled`); those
  fell through to the state machine, where `--force` overrides a non-existent
  edge — and for `done`, backward auto-force-promotion (FR-015) supplies the
  force flaglessly. Result: a merged `done` work package resurrected to
  `planned` with a `force=true` event and a synthesized reason. That is why the
  fix must never route a source into the state machine.
- **Alternatives considered**: restoring the cut `legal_targets_from()` /
  `_invalid_transition_diagnostic()` helpers — unnecessary; the legal-target set
  is one pure `allowed_targets()` lookup constructed inline, which is a smaller
  diff and fewer places for a control-flow slip to hide.

## Decision 3 — Non-vacuous, red-first regression battery

- **Decision**: Cover `{done, canceled, genesis, blocked, in_review}` ×
  `{none, --force}` (all refuse, lane unchanged), plus: the flagless
  `done → planned` case asserts **no** forced-rewind event is emitted; a
  positive control (`in_review` + valid non-empty feedback → `planned`, exit 0);
  and a fabricated non-empty feedback file on `blocked` still refused. Assertions
  are on observable outcome (resulting lane / emitted events), not message
  substring alone. Rows must be written RED against a deliberately-holed guard
  and proven to fail before the fix.
- **Rationale**: The prior 292-line test file passed `--force` nowhere and never
  used `done`/`canceled`/`genesis` as a source, so the resurrection hole survived
  two reviews. The matrix's `done`-flagless and `*-with-force` rows are the
  tripwires.

## Ground-truth evidence (current `main`)

- `_guard_planned_rollback` at `tasks_transition_core.py:561`, guard-chain
  index 6 of `_GUARDS` (`:675`), runs entirely before `build_transition_plan`
  (`:800`) and the state machine.
- Today the refusal text is **byte-identical across all six source lanes** and
  identical with/without `--force` — it reads neither `old_lane` nor `force`.
- `wp_state.py`: `planned ∉ allowed_targets` for `done` (empty), `canceled`
  (empty), `blocked` (`{in_progress, canceled}`); `planned ∈ allowed_targets`
  for `genesis`, `in_progress`, `in_review`, `approved`.
- FR-015 backward auto-force (`tasks_transition_core.py:325-349`,
  `_is_backward_transition`/`_FORWARD_ORDER` in
  `tasks_finalize_validation.py:44-67`): `done → planned` is backward *within*
  `_FORWARD_ORDER` → force auto-promoted flaglessly; `blocked`/`canceled` are
  outside `_FORWARD_ORDER` → need explicit `--force`.
- Blast radius: exactly one test file pins the changing text —
  `test_tasks_transition_core.py:473-474` (asserts "requires review feedback"
  and "cannot be bypassed with --force") — and it uses `old_lane="in_review"`
  (a reachable lane), so the reachability partition keeps it green. No
  golden/snapshot/terminology gate trips for an additive, forbidden-word-free
  enrichment.

## Adversarial evidence disposition

No security-impacting dependency decision (no dependency change), so the
supply-chain adversarial pass is N/A. The adversarial *regression-hole* pass
(reviewer lens) was run at grounding; its top risk — "any code path out of the
guard that returns something other than `RefuseExit1` for a `--to planned` move
without valid feedback" — is **accepted** and encoded as constraint C-001 and
the IC-4 matrix (status: `accepted`).
