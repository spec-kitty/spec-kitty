# WP01 Review — Finalized-board routing (the wedge + advance first-contact parity)

**Reviewer:** reviewer-renata (independent QA, tool identity `codex`; implementer was `claude`)
**Cycle:** 1
**Verdict:** **APPROVE**
**Date:** 2026-10-05
**Base:** `2acbe38eab686d6ba48152e3f4d93685d679e2b6` → HEAD (single_branch, repo-root checkout)

---

## Scope reviewed

Two defects in `src/runtime/next/runtime_bridge.py`, both claimed red-first:
- **Defect 1 (#5669, the wedge):** `_finalized_task_board_override_step` must report `review`
  (not `implement`) when the only `planned` WPs are dependency-walled and a `for_review` WP exists.
- **#5310 (advance first-contact parity):** a finalized board with no persisted run must resolve
  the board step on advance, agreeing with query mode, not boot a fresh `discovery` run.

(US3 / FR-006 / FR-007 / SC-004 — the `mission-events.jsonl` dirty-survivor — is WP02, out of scope.)

## Commit sequence — verified present and matching

| sha | role | present |
|-----|------|---------|
| `e05f2638ac` | red D1 (wedge regression + `_scaffold` `dependencies` kwarg) | ✓ |
| `ddbb0f20c2` | fix D1 (`_has_claimable_planned_wp` gates planned arm) | ✓ |
| `328967284d` | red #5310 (advance first-contact regression) | ✓ |
| `4c4a88d0fc` | fix #5310 (`_dn_finalized_board_override` front phase) | ✓ |
| `4302f1e2f7` | docs (activity log + approach/design traces D5) | ✓ |

## §1 — Red→green, both defects, witnessed empirically

Worktrees checked out at the red commits; worktree source forced to win via
`PYTHONPATH=<wt>/src:<wt>` over the repo-root editable `.venv` (verified: red-D1 import of
`runtime_bridge` has no `_has_claimable_planned_wp`; red-#5310 has no `_dn_finalized_board_override`).

- **Defect 1 RED** @ `e05f2638ac` (`tests/next/test_next_dependency_wedge_5669.py`): **3 failed, 3 passed.**
  The 3 defect-pinning assertions fail — override/dispatch/query each report `implement` instead of
  `review` (`assert 'implement' == 'review'`). The 3 passing are the #4860 guard, the claimable-planned
  positive control, and the state-to-action preemption test (correctly green both sides).
- **Defect 1 GREEN** @ HEAD: all 6 pass.
- **#5310 RED** @ `328967284d` (`tests/next/test_next_advance_first_contact_5310.py`): **3 failed, 2 passed.**
  Advance boots the DAG (`assert 'research' == 'review'`; `assert step == blocked`) while query selects
  the board step. Controls (no-board→discovery, all-approved decline) green both sides.
- **#5310 GREEN** @ HEAD: all pass.

Both files carry `pytestmark = [pytest.mark.git_repo, pytest.mark.regression]` and are issue-pinned
(5669 / 5310) in filename, module docstring, and test names. ✓

## §2 — The `_run_is_untouched` narrowing (CRITICAL) — CORRECT scope, not accommodation

The front phase `_dn_finalized_board_override` fires only for `ctx.result == "success"` on an
**untouched** run (no completed steps, no pending decisions, no decisions — query mode's own
initial-step predicate). Judgement: **this is the correct scope for #5310 (first-contact =
never-advanced run), not a fix shrunk to pass tests.** Evidence:

- A walked run that later reaches a WP-iteration step **still consults the fixed board authority**:
  `_dn_dependency_gate` (when WPs remain / guards fail) → `_build_wp_iteration_decision` →
  `_wp_iteration_action_and_state` → `_resolve_wp_board_action` → `_finalized_task_board_override_step`.
  The wedge fix lives in `_finalized_task_board_override_step`, consulted on BOTH the first-contact
  path (new front phase) and the walked-run path (dependency gate). **The narrowing leaves no gap in
  the wedge fix.** `test_advance_of_an_already_walked_run_keeps_dag_progression` proves a walked run
  advances `implement` with the persisted run state moving in lock-step (not left behind).
- The rejected first draft (fire on any non-WP current step) pre-empted a legitimately mid-DAG run
  (e.g. at `tasks`), so the issued decision outran persisted run state — a real divergence, caught by
  `tests/integration/test_owned_next_runtime.py`. The narrowing removes that divergence; it does not
  hide it. `test_owned_next_runtime.py` is **green at HEAD** (re-run below).
- `_run_is_untouched` reads the snapshot in `try/except Exception: return False` — an unreadable/
  malformed snapshot is treated as **touched**, so the phase declines and the pre-existing path is
  kept. Fail-safe direction confirmed (`test_run_is_untouched_treats_an_unreadable_snapshot_as_touched`).

## §3 — decision.py untouched + preemption

`git diff base..HEAD -- src/runtime/next/decision.py` is **empty**. The preemption is proven by
`test_board_authority_preempts_state_to_action_fallback_for_walled_board`: `_wp_iteration_action_and_state`
returns the board's named `blocked_reason` (with the `spec-kitty agent tasks status --mission <slug>`
recovery string) and `action=None` for a walled board, short-circuiting before `_state_to_action`'s
live `for_review` fallback is consulted. ✓

## §4 — #4860 guard intact

`test_walled_planned_wp_alone_is_never_dispatched_for_implement_4860`: a walled `planned` WP (its
dependency `blocked`) yields `result.action != "implement"` and `wp_id != "WP02"` — the implement
resolver fails closed via `preview_claimable_wp` → blocked floor. Green. ✓

## §5 — NFR-002 no regression (targeted suites, at HEAD)

```
tests/next/test_next_dependency_wedge_5669.py
tests/next/test_next_advance_first_contact_5310.py
tests/next/test_finalized_task_routing.py
tests/runtime/test_next_board_authority.py
tests/integration/test_next_preview_primary_routing.py
tests/integration/test_owned_next_runtime.py          → 86 passed
```
Wider next surface:
```
tests/next  tests/runtime/next  tests/specify_cli/orchestrator_api  tests/specify_cli/next
                                                       → 1115 passed, 4 skipped
```
done/accept/review_in_progress/no_actionable_wp, claimed/in_progress→implement, and
claimable-planned→implement all unchanged. ✓

## §6 — Single authority / no whack-a-field

- Planned arm reuses `discovery.preview_claimable_wp` via the thin `_has_claimable_planned_wp`
  (no new claimability predicate) — same authority `_resolve_wp_board_implement_action` already uses (C-001). ✓
- The #5310 front phase routes through the shared `_resolve_wp_board_action` and materializes via
  `_build_wp_iteration_decision` / a named `blocked` Decision — no advance-only claimability re-derivation. ✓
- **T005:** `orchestrator_api/decision_verbs.py::answer_decision` calls `decide_next` →
  `decide_next_via_runtime` (the same seam, now carrying the front phase). No parallel override. ✓

## §7 — Logged caveats (D5) — acceptable out-of-scope residuals

- **(a)** `_dn_bootstrap` persists a fresh discovery-phase run before the front phase short-circuits
  it idempotently (mirrors query's ephemeral run). Cosmetic write; no correctness impact. **Accept.**
- **(b)** An all-approved/all-done finalized board on **first-contact** advance resolves to the DAG
  first step (`research`) rather than accept/done, while query previews accept/done — a query↔advance
  mismatch for terminal boards. Judgement: **acceptable, does NOT break anything the mission claims to
  fix.** SC-001..SC-003 are all about implement/review dispatch; the accept/done first-contact case is
  not in the SC set. Leaving it on the pre-existing path is what makes NFR-002 ("accept/done unchanged,
  byte-identical") hold — the front phase declines when `board.action is None`. It is a *pre-existing*
  mismatch (pre-WP01, every first-contact advance booted discovery), narrowed but not fully closed; it
  self-heals on the next advance. The only tension is NFR-001's full-generality wording vs the delivered
  scope. **Accept**, provided both caveats are stated in the PR body as known residuals.

## §8 — Quality

- `ruff check` (runtime_bridge.py + 2 new test files): **All checks passed.**
- `ruff format --check --force-exclude` (same 3 files): **3 files already formatted.**
- No new `# noqa` / `# type: ignore` in the changed lines.
- `mypy`: the two **new** test files and `runtime_bridge.py` are **clean (zero errors)**. Complexity
  under ceiling (ruff C901 ≤ 15 passed).
- **Pre-existing-mypy verdict (test_finalized_task_routing.py:243):** **GENUINELY PRE-EXISTING.** The
  line (`_finalized_task_board_override_step(feature_dir, progress)` with `progress: dict[str, int]`,
  dict-invariance arg-type error) is **byte-identical at the merge-base `2acbe38`**. The `_scaffold`
  diff hunks are at lines 25-26 and 38-47 only — nowhere near line 243. **Not introduced** by the
  `_scaffold` extension. (The sibling `tests/lane_test_utils.py:85` error is in an untouched file.)

## §9 — Acceptance

FR-001 ✓ · FR-002/#4860 ✓ · FR-003 (honest blocked floor) ✓ · FR-004 (resume arms) ✓ ·
FR-005/SC-003 ✓ · SC-001 ✓ · SC-002 ✓ · NFR-002 ✓ · NFR-003 (bounded idempotent FS read, Medium,
anticipated by design) ✓ · NFR-001 ✓ with the documented accept/done first-contact residual (§7b).

---

**APPROVE.** Both defects are red-first witnessed (3+3 red D1; 3 red #5310) and green at HEAD; the
untouched-run narrowing is principled (walked runs still consult the fixed authority — no wedge gap);
`decision.py` untouched; #4860 intact; single claimability authority; quality gates clean; the one
flagged mypy error is pre-existing. Record the two D5 caveats in the PR body as known residuals.
