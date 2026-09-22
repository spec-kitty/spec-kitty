# Tracer — Adversarial Squad Findings (#4858)

## Post-spec point-cut (2026-09-21)

Three independent, profile-loaded, read-only lenses. All grounding line refs re-verified
against HEAD. Convergent verdict: **Option-A fix contract is structurally sound; spec test
contract needed hardening.** All findings below were FOLDED into `spec.md`.

### architect-alphonso (structure/seams/topology) — "spec needs minor changes"
- ✅ Lock key/topology CORRECT: `feature_status_lock_path` keys under `_git_common_dir`; primary
  and coord roots collapse to the same common dir, and `lock_key = matrix_dir.name` is
  layout-invariant → one lock file coordinates both. Validates Assumption #2.
- ✅ Re-read placement (slow check outside lock; re-read+merge+write inside) leaves no residual
  gap; `matrix_dir` resolved once and reused → folded as FR-003 invariant.
- ✅ kernel.atomic composes cleanly with write_seam → commit_for_mission; no double-serialize.
- ⚠️ MEDIUM: lock protects verdict-vs-verdict only, NOT verdict-vs-(finalize/accept/gate); make
  the boundary explicit → folded as **C-010** + Scope Boundaries section.
- ⚠️ LOW: NFR-004 over-promised (coord `shutil.copy2` in frozen commit_router is non-atomic) →
  NFR-004 scoped to the atomic-write door the fix owns.
- Withdrew an initial coord read-surface-skew suspicion (matrix must pre-exist on coord).

### debugger-debbie (live-evidence / test efficacy) — "needs strengthening"
- ⚠️ HIGH: deterministic read1→run2→finish1 harness CANNOT gate the lock (B commits before A's
  section; A's re-read sees B regardless of lock) → added **FR-009** lock-acquisition spy
  (key == matrix_dir.name, path under common dir) + **FR-011** call-order (check before lock).
- ⚠️ HIGH: coord scenario as written can't falsify a per-checkout key (one process, one root) →
  US2 now drives A via primary root + B via coord root (or a lock-key-equality unit test).
- ⚠️ HIGH: monkeypatch the COMMAND-module binding
  `...acceptance_verdict.enforce_negative_invariants`, not the matrix module (import-by-name);
  one-shot `nonlocal` reentrancy guard → folded into US1 Independent Test.
- ⚠️ MEDIUM: Scenario "reports committed" is true on base (decoy); the load-bearing assertions
  reload from disk + check overall_verdict == fail → US1 Scenario 1 pinned as FR-004-bearing.
- ⚠️ MEDIUM: mid-point "B truly persisted" checkpoint guards against proving #2482 not #4858 →
  US1 Scenario 2.
- ⚠️ MEDIUM: criterion mode has NO slow-check seam → US3 names `_resolve_criterion_update` /
  write step as its seam.
- Concessions: did not judge Option A/B/C best; single-thread harness cannot observe torn file.

### reviewer-renata (anti-laziness / scope) — "needs spec-level hardening; scope sound"
- ✅ Scope correctly bounded to #4858; #2482 note-not-fold correct; terminology clean in spec.
- ⚠️ MAJOR: FR-006 both-modes untested → US3 criterion-mode scenario added.
- ⚠️ MAJOR: NFR-002 unfalsifiable → FR-011 call-order assertion.
- ⚠️ MINOR: same-entry-id / coord-path-distinct / brief gates 4 & 8 traceability → edge cases +
  C-008 + C-009 added; coord-path-distinct assertion in US2.
- ⚠️ MINOR: checklist "Feature" term is template-inherited → fixed local instance to "Mission",
  logged upstream template gap in checklist note.

## Upstream gaps to file (canonical-source doctrine)
- Shipped specify checklist template in `packs/built-in` still emits prohibited `Feature` term
  ("**Feature**:", "## Feature Readiness"). Non-blocking; file against the template, not by
  hand-editing consumer artifacts.

## Post-spec point-cut — #4868 half + fold coherence (2026-09-21)

Two profile-loaded, read-only lenses on the folded mission. Both grounded against current code.

### debugger-debbie (test efficacy, #4868) — APPROVE-WITH-CHANGES
- ✅ Bug reconfirmed: `_migrate_if_needed:166` passes primary `feature_dir`; `_load_raw_rows`
  reads only JSON; migration is the only route #A reaches the final JSON → #A lost on coord.
- ✅ Integration-with-real-seam is genuinely necessary (fake write_artifact won't materialize
  coord JSON → fix would appear broken); `_build_coord_mission_for_matrix` is a faithful repro.
- ✅ Assertion set non-fakeable + double-RED on base (rows AND `migrated is True`); `migrated is
  True` is LOAD-BEARING (rejects a `.md`-failover pseudo-fix). Fix trace → GREEN; NFR-005 compat OK.
- ⚠️ MEDIUM: C-011 not falsified — a wrong fix passing `read_dir` as the WRITE `feature_dir` still
  lands both rows via the untouched main write → **added US4 Scenario 2 primary-residue assertion.**
- ⚠️ LOW: malformed coord `.md` behaviour changes base→fix → **added edge case + decision (fail
  loudly) + guard test.**
- ⚠️ LOW: coord-json-short-circuit only fake-seam unit tested → cite explicitly in tasks.

### reviewer-renata (fold coherence / scope) — CONDITIONAL PASS
- ✅ Fold coherent + scope-disciplined; all 8+ gates present; terminology clean; #2482 note-not-
  fold confirmed; ATDD sequencing sound (disjoint files → separable red→green commits).
- ⚠️ MEDIUM: atomic-write (FR-009/C-003) not test-gated like the lock was → **added US1 Scenario 6
  atomic-write spy + FR-009 wording + SC-005.**
- ⚠️ LOW: record conscious deferral of atomic door on issue writer → **added Scope Boundaries line.**
- ⚠️ PROCESS: stale tracer "Open items" → **refreshed.**
- Fold is "thin" (shared failure signature + fixtures, not shared code) — honestly disclosed; note
  for reviewer expectations, not a defect.

## Post-plan point-cut (2026-09-21) — 3 lenses, all folded

Concurrency-focused per the brief (lock scope, re-read placement, coord-vs-flat key, interleavings
the happy path misses). Verdicts: architect "sound—needs changes", debugger "two HIGH gaps",
pedro "feasible as planned". Highlights (full dispositions in research.md):
- **HIGH** fail-closed-on-lock-timeout (else fail-open re-introduces the P0) → FR-015/C-012 + test.
- **HIGH** re-read-inside-lock not pinned (mutant survives serial harness) → strict ordering assert.
- **MED** reported overall_verdict from stale snapshot → emit from re-read (FR-016).
- **MED** criterion index + NI splice must derive from re-read (not pre-check; not `_register_*`).
- **MED** read-surface==commit-surface; materialize worktree before lock (FR-017/C-013).
- **MED** #4868 C-011 guard didn't kill the wrong fix → spy `feature_dir==primary`, mutation-tested.
- **MED** #4868 malformed `.md` → structured `IssueVerdictError` (FR-018); 2nd-call idempotency.

## Post-tasks point-cut (2026-09-21) — 2 lenses, all folded

reviewer-renata (anti-laziness) + planner-priti (decomposition/hygiene). Both CONDITIONAL PASS.
- **HIGH (renata)**: US1 Scenario 3 (reverse role: B passes / A fails) was labeled covered but not
  instantiated (S3-vs-US3 shorthand collision) → added explicit reverse-role bullet to WP01 T002,
  fixed the T001 label. Catches a splice that drops a PASSING sibling row.
- **HIGH (priti)**: no issue-matrix.md → would block `move-task --to approved` → scaffolded rows
  (#4858→in-mission/WP01, #4868→in-mission/WP02) on the coord surface; resolved auto-discovered
  #2482 → not-applicable (C-005). #3347/#4792 correctly classified context-only (not added).
- **MED (renata)**: no `make test-fast` baseline in T005/T010 → added. Self-attested counts →
  added "paste terminal output; reviewer RE-RUNS" to both.
- **MED (priti)**: CHANGELOG close-out honor-system → converted to a tracked close-out checklist.
- **LOW (renata)**: mypy command not spelled out → added explicit `uv run --frozen mypy ...`;
  T003 density + materialize-before-lock is review-verified (backstopped by T002 spies) → reviewer note.
- **OK**: ownership disjoint, lanes parallel-safe, sequencing correct, 18/18 FR coverage, no drift.
