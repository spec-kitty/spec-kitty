# Research — Verdict-matrix RMW preservation (#4858 + #4868)

All decisions grounded on baseline `skupstream/main == 45df0b61d5` (the acceptance path is
byte-identical to the #4858 grounding baseline `32cfc272ee`). Sources: `research/grounding-4858.md`,
`research/grounding-4868.md`, two post-spec adversarial squads (`tracer-squad-findings.md`).

## Decision A1 — #4858 fix locus: locked re-read + single-row splice at the command seam (Option A)

- **Decision**: In `acceptance_verdict.py`, run the slow `enforce_negative_invariants` check
  OUTSIDE the lock; then inside `feature_status_lock(repo_root, matrix_dir.name)` re-read the
  on-disk matrix, splice in only the owned entry (criterion id / invariant id), and write+commit.
  `matrix_dir` is resolved once and reused as both re-read base and write target.
- **Rationale**: Keeps the criterion-vs-invariant disambiguation where the caller already knows
  it; minimal blast radius; the slow check stays out of the critical section. The architecture
  lens confirmed the lock key is layout-invariant and composes cleanly with the write-seam.
- **Alternatives considered**:
  - *Option B — push the locked RMW into `write_and_commit_acceptance_matrix`*: one chokepoint
    for all writers, but must re-contract the function to disambiguate criterion vs invariant, and
    would serialize non-verdict writers we deliberately keep out of scope (C-010). Rejected as
    heavier for a P0.
  - *Option C — content hash CAS with retry*: more moving parts, still needs the per-row merge,
    and doesn't match the existing `status/locking.py` doctrine. Rejected.

## Decision A2 — #4858 atomic write via `kernel.atomic.atomic_write`

- **Decision**: Replace the bare `path.write_text` in `write_acceptance_matrix` (`matrix.py`)
  with `kernel.atomic.atomic_write` (tempfile + rename). Assert via a call-spy (US1 Scenario 6).
- **Rationale**: Prevents torn reads at the shared writer for ALL callers; sanctioned door
  (C-003). Confirmed `atomic_write` is a live symbol; `write_if_changed` is absent, so it is NOT
  activated (avoids the C-007 dead-symbol trap).
- **Alternatives**: activating `write_if_changed` — rejected (would need a real caller in-change
  or trip `test_no_dead_symbols.py`; unnecessary).

## Decision A3 — #4858 lock primitive: existing `feature_status_lock`

- **Decision**: Reuse `status/locking.py::feature_status_lock`, keyed on the git common dir +
  `matrix_dir.name`; no new primitive, no change to that module.
- **Rationale**: It already spans primary + coord worktrees (one lock file), is cross-process and
  bounded-timeout, and routes through `kernel.locks` (C-001/C-002 satisfied). The architecture
  lens verified both primary and coord roots collapse to the same common-dir lock path.

## Decision B1 — #4868 fix: coord-aware migration read source

- **Decision**: Add an optional keyword-only `read_dir: Path | None = None` to
  `migrate_issue_matrix_to_json`; read the legacy matrix from `read_dir or feature_dir`; keep
  `write_issue_matrix(feature_dir=feature_dir)` unchanged. Pass `read_dir=read_dir` from
  `_migrate_if_needed` (`issue_verdict.py:166`).
- **Rationale**: Minimal (2-line) fix at the true root — the migration read source — while the
  write stays on primary so the write-seam still materializes coord and cleans residue (C-011).
  Backward-compatible: the bulk caller `_migrate_one_mission` and unit callers pass keyword args
  after `feature_dir` (signature already `*`-separated), so nothing breaks (NFR-005).
- **Alternatives considered**:
  - *Make `_load_raw_rows` failover-read the coord `.md`*: would preserve rows but leave
    `migrated=False`, never write a canonical JSON, and re-trigger every call. Rejected — the
    `migrated is True` assertion in US4 exists specifically to reject this pseudo-fix.
  - *Pass `read_dir` as the write `feature_dir`*: gets both rows into coord JSON via the main
    write but breaks the write-seam residue-cleanup contract. Rejected and explicitly guarded by
    C-011 + the US4 primary-residue assertion.

## Decision B2 — #4868 malformed legacy coord `.md`: fail loudly

- **Decision**: After the fix, a malformed coord `.md` surfaces the validation error rather than
  being silently ignored (as on base). This is intended, safer behaviour; a guard test pins it.
- **Rationale**: Silent success that drops the authoritative matrix is the very defect class this
  mission closes; failing loudly on a corrupt authoritative matrix is the correct posture.

## Decision C1 — Test strategy: deterministic, no real threads/flake

- **#4858**: serialized `read1→run2→finish1` harness; patch the COMMAND-module binding
  `...acceptance_verdict.enforce_negative_invariants` (import-by-name), one-shot `nonlocal` guard;
  disk-reload assertions; lock spy + call-order spy + atomic-write spy; flat + coord (two worktree
  roots) + criterion-mode.
- **#4868**: integration test with the REAL write-seam (a fake seam won't materialize the coord
  JSON and would mask the fix); reuse `_build_coord_mission_for_matrix`; flat control cited.

## Supply-chain

N/A — no dependency add/upgrade/remove. Nothing to vet under DIRECTIVE_051.

## Adversarial evidence (dispositions — no contested finding dropped)

Per `contracts/adversarial-evidence-contract.md`. Two post-spec squads; every finding folded:

| Finding (lens) | Disposition |
|----------------|-------------|
| Deterministic harness can't gate the lock (debugger, #4858) | **changed** — added lock-acquisition spy (FR-007) + call-order (FR-008) |
| Monkeypatch must target command-module binding + one-shot reentrancy (debugger, #4858) | **changed** — pinned in US1 Independent Test |
| Scenario "reports committed" is a decoy; use disk-reload + fail→pass (debugger, #4858) | **changed** — US1 Scenario 1 pinned |
| Mid-point "B persisted" provenance checkpoint (debugger, #4858) | **changed** — US1 Scenario 2 |
| Coord must drive two worktree roots (debugger+architect, #4858) | **changed** — US2 Independent Test |
| Criterion-mode has its own seam (debugger+reviewer, #4858) | **changed** — US3 |
| Lock scope is verdict-vs-verdict only; state it (architect, #4858) | **changed** — C-010 + Scope Boundaries |
| NFR-004 over-promised (coord copy non-atomic) (architect, #4858) | **changed** — NFR-004 scoped to the door |
| Atomic-write door not test-gated (reviewer, fold) | **changed** — US1 Scenario 6 spy + FR-009 |
| C-011 not falsified by the test (debugger, #4868) | **changed** — US4 Scenario 2 primary-residue assertion |
| Malformed coord `.md` behaviour change (debugger, #4868) | **accepted** — decision: fail loudly + guard test |
| Defer atomic door on issue writer — record it (reviewer, fold) | **accepted** — Scope Boundaries line |
| Fold is "thin" (shared signature+fixtures, not code) (reviewer, fold) | **accepted** — disclosed honestly; not a defect |

## Adversarial evidence — POST-PLAN squad (2026-09-21)

Three lenses (architect-alphonso, debugger-debbie, python-pedro). All findings folded into
spec/plan/contract; none dropped. Verdicts: architect "sound — needs changes"; debugger "sound,
two HIGH structural gaps"; pedro "feasible as planned".

| Finding (lens) | Disposition |
|----------------|-------------|
| Lock-timeout unspecified; fail-open would re-introduce P0 (debugger HIGH, architect Q2) | **changed** — FR-015/C-012 fail-closed + US1 Scenario 8 |
| FR-003 re-read-inside-lock not pinned; "re-read outside lock" mutant survives serial harness (debugger HIGH) | **changed** — US1 Scenario 7 strict ordering + C-4858-reread-in-lock |
| Reported `overall_verdict` from stale in-memory matrix (debugger MED, pedro MED) | **changed** — FR-016 + US1 Scenario 9 |
| Criterion index/`_resolve_criterion_update` must run on re-read (pedro HIGH, debugger MED) | **changed** — US3 note + C-4858-modes + plan step |
| NI splice must not reuse `_register_negative_invariant` (resets to pending) (pedro MED) | **changed** — US3 note + C-4858-modes (replace-or-append-judged helper) |
| Read surface vs commit surface can diverge; materialize worktree before lock (architect Q1/Q2) | **changed** — FR-017/C-013 + edge case |
| #4868 C-011 guard doesn't kill the wrong fix; residue-only check insufficient (architect Q4) | **changed** — US4 Scenario 2 now spies `feature_dir==primary`, mutation-tested |
| #4868 malformed `.md` may raise raw traceback (architect Q4) | **changed** — FR-018 structured `IssueVerdictError` |
| #4868 unmaterialized-coord degradation (architect Q4) | **accepted** — precondition documented (edge case) |
| #4868 no 2nd-call idempotency coverage (debugger MED) | **changed** — US4 Scenario 3 |
| atomic tempfile in matrix_dir, no residue (architect LOW, debugger LOW) | **accepted** — noted in plan/contract |
| lock re-entrancy vs commit path — safe, no deadlock (architect Q2, pedro LOW) | **accepted** — confirmed no finding |
| shared fixture `_build_coord_mission_for_matrix` cross-lane coupling (architect Q5) | **accepted** — freeze return contract; site A's coord test in the file already importing it |
| same-entry-id race — no sibling loss, no delete path (debugger Q2) | **accepted** — no finding |
