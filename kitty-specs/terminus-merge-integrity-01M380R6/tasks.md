# Tasks: Terminus / Merge-Coord Integrity (Epic #5001)

**Mission**: `terminus-merge-integrity-01M380R6`
**Branch**: `fix/terminus-merge-integrity` · **Topology**: `coord`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Contract**: [contracts/terminus-reconciliation.md](./contracts/terminus-reconciliation.md)
**Grounding**: [research.md](./research.md) · [../../work/epic-5001-research/DEBRIEF.md](../../work/epic-5001-research/DEBRIEF.md)

Make Epic #5001's invariant **executable and closed-by-construction**: no terminus command
(`merge` / `merge --resume` / `merge --abort` / `upgrade` / `agent issue-verdict` /
`doctor coordination --fix`) may exit 0 while the target tree diverges from the claimed WP set or
while committed work is destroyed. Ten work packages build one shared terminus transaction seam —
CAS ref-advance → full post-checkpoint projection → fail-closed reachability verifier → gated
teardown — backed by four single-authority consolidations (target, lock, residue-topology,
lane-identity) and a surface-authority write gate.

Every WP is ATDD **red-first**: the failing reproduction lands (or is confirmed red) BEFORE the fix
(DIRECTIVE_041/034, FR-014, NFR-001). Completion is event-sourced via
`spec-kitty agent tasks move-task <WPID> --to <lane>` — no checkboxes, no frontmatter lane.

## Subtask Index (reference only — not a tracking surface)

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | `tests/terminus/` harness: real-CLI-entry fixtures, coord mission builder, lane-tip approved-SHA helper, planted-canceled-commit helper (`conftest.py`) | WP01 | [P] |
| T002 | Tier-0 property test: exit-0 terminus ⇒ every approved WP commit reachable, no excluded commit reachable | WP01 | [P] |
| T003 | Per-child red repros — reconciliation/CAS family (#4945 #4977 #4981 #4991 #4996) | WP01 | [P] |
| T004 | Per-child red repros — surface/resume/behind-HEAD family (#4969 #4970 #4973 #4978 #4982 #4985 #4997) | WP01 | [P] |
| T005 | Confirm RED on base; non-vacuous excluded-check (planted canceled commit fires) | WP01 | [P] |
| T006 | Red unit: `advance_branch_ref` argv is 3-arg CAS, fails closed on mismatch | WP02 | [P] |
| T007 | Fix: `advance_branch_ref` 2-arg → 3-arg CAS (`update-ref ref new old`), fail closed | WP02 | [P] |
| T008 | Fix: correct the module + `advance_branch_ref` docstring (drop lock-dependence claim) | WP02 | [P] |
| T009 | Verify red→green + ruff/mypy gates | WP02 | [P] |
| T010 | Red: unmaterialized-coord terminus WRITE refuses (does not degrade to primary) | WP03 | [P] |
| T011 | Fix: fail-closed WRITE gate at `resolve_write_target_or_degrade` (real degrade point) | WP03 | [P] |
| T012 | Fix: `surface_resolver.resolve_for_write` thin helper the write chain calls | WP03 | [P] |
| T013 | Fix: wire write chain — `write_seam.write_artifact`, `issue_matrix`, `issue_verdict` | WP03 | [P] |
| T014 | Fix: `implement._validate_base_ref` consults `origin/<lane>` (#4969) | WP03 | [P] |
| T015 | Verify red→green + ruff/mypy gates | WP03 | [P] |
| T016 | Red: lane id stable across WP-removal re-finalize; base consults `origin/<lane>` | WP04 | [P] |
| T017 | Fix: mint stable `lane_id` once at creation (`compute.py`) | WP04 | [P] |
| T018 | Fix: read back the bound id on finalize — never re-letter over a bound id | WP04 | [P] |
| T019 | Fix: `workspace/context.py` origin-aware base resolution | WP04 | [P] |
| T020 | Verify red→green + ruff/mypy gates | WP04 | [P] |
| T021 | Red: behind-own-HEAD checkout distinguished from real local changes | WP05 | [P] |
| T022 | Fix: `preflight.py` behind-HEAD classifier (behind-own-HEAD ≠ dirty) | WP05 | [P] |
| T023 | Fix: never advise the merge-reverting "Commit" remedy (#4982/#4997) | WP05 | [P] |
| T024 | Verify red→green + ruff/mypy gates | WP05 | [P] |
| T025 | Red: `MergeOutcomeVerifier.verify` reachability + fail-closed claim (`test_reconciliation.py`) | WP06 | |
| T026 | Scaffold: all new `_MergeRunState` fields + linear phase slot + `reconciliation.py` stub (ONE change) | WP06 | |
| T027 | Verifier claim integrity: fail-closed + Lamport-sourced membership + tree-tip approved SHAs | WP06 | |
| T028 | Verifier reachability: excluded-by-patch-id; `git_probes` ancestry→tree-equality | WP06 | |
| T029 | Wire gate into executor between `_phase_commit_and_assert` and cleanup; inline manifest reseed-from-state | WP06 | |
| T030 | FR-012 legacy refuse + NFR-005 non-vacuous call-site gate over all 6 terminus entry points + self-mutation test | WP06 | |
| T031 | Verify red→green (property + repros) + ruff/mypy gates | WP06 | |
| T032 | Red: post-checkpoint concurrent coord commit survives; changed coord tip aborts teardown (`test_projection_teardown.py`) | WP07 | |
| T033 | Fix: project ALL post-checkpoint coord commits onto target (not just status files) | WP07 | |
| T034 | Fix: teardown gated on reachability + coord-ref CAS (`teardown.py`) | WP07 | |
| T035 | Verify red→green + ruff/mypy gates | WP07 | |
| T036 | Red: strand heal reverts only recorded SHAs; residue classified by stored topology (`test_coherence_integrity.py`) | WP08 | |
| T037 | Fix: SHA-scoped strand heal (revert only recorded SHAs, never a range) (#4973) | WP08 | |
| T038 | Fix: `is_coord_residue_churn` threads stored mission topology (#4978) | WP08 | |
| T039 | Verify red→green + ruff/mypy gates | WP08 | |
| T040 | Red: `--target` > persisted > meta precedence across crash; abort frees only own lock (`test_merge_state_authority.py`) | WP09 | |
| T041 | Fix: single persisted merge target (`core/paths.py` + `resolve.py` + `state.py` + `merge.py`) | WP09 | |
| T042 | Fix: `owner_token = merge-state-id`; abort frees only own lock | WP09 | |
| T043 | Verify red→green + ruff/mypy gates | WP09 | |
| T044 | Correct CLAUDE.md false CAS-advance + sole-authority-reducer claims | WP10 | |
| T045 | Correct ADR `2026-02-09-3` + `status-model.md`; keep #4990 named-open | WP10 | |
| T046 | Final green: full blast-radius suite per quickstart.md (12 repros + property + gates) | WP10 | |

## Work Packages

### WP01 — Red-first terminus test harness (FR-014, NFR-001)
- **Goal**: land the Tier-0 property test + 12 per-child reproductions RED against pre-fix behavior,
  each driving the **real CLI entry point** (no `_run_git`/subprocess mocking), approved SHAs from
  lane-branch git tips, non-vacuous excluded-check (planted canceled commit).
- **Owns**: `tests/terminus/**`. **Profile**: `debugger-debbie`. **Deps**: none (parallel fan head).
- **Subtasks**: T001–T005. **Prompt**: [tasks/WP01-red-first-terminus-harness.md](./tasks/WP01-red-first-terminus-harness.md) (~330 lines)
- **Risks**: a repro that mocks `_run_git` is vacuous (does not exercise `ref_advance` CAS); an
  excluded-check that no-ops when the canceled set is empty.

### WP02 — Compare-and-swap ref advance (S-A, FR-003)
- **Goal**: `advance_branch_ref` uses 3-arg CAS `update-ref ref new old`, fails closed on mismatch;
  drop the docstring's lock-dependence admission. Traces #4996 #4982 #4997.
- **Owns**: `src/specify_cli/git/ref_advance.py`. **Profile**: `python-pedro`. **Deps**: none.
- **Subtasks**: T006–T009. **Prompt**: [tasks/WP02-cas-ref-advance.md](./tasks/WP02-cas-ref-advance.md) (~250 lines)
- **Risks**: a silent 2-arg fallback on CAS failure reopens #4996; retry-on-mismatch masks the race.

### WP03 — Surface-authority WRITE gate (S-C, FR-006)
- **Goal**: a terminus WRITE fails closed at the real degrade point when the authoritative coord
  worktree/branch is unresolved/unmaterialized; `implement._validate_base_ref` consults
  `origin/<lane>`. Traces #4970 #4969.
- **Owns**: `coordination/write_seam.py`, `mission_runtime/write_target_degrade.py`,
  `tasks/issue_matrix.py`, `cli/commands/agent/issue_verdict.py`, `cli/commands/implement.py`,
  `coordination/surface_resolver.py`. **Profile**: `python-pedro`. **Deps**: none.
- **Subtasks**: T010–T015. **Prompt**: [tasks/WP03-surface-write-gate.md](./tasks/WP03-surface-write-gate.md) (~340 lines)
- **Risks**: gating the READ path (breaks correct loud-primary-fallback); gating a helper the real
  write chain never calls (redundant guard, RN-F1).

### WP04 — Stable, origin-aware lane identity (C-4, FR-010)
- **Goal**: mint a stable `lane_id` once at creation; read it back on finalize (never re-letter over
  a bound id); base resolution consults `origin/<lane>`. Traces #4945 #4969.
- **Owns**: `src/specify_cli/lanes/compute.py`, `src/specify_cli/workspace/context.py`.
  **Profile**: `python-pedro`. **Deps**: none.
- **Subtasks**: T016–T020. **Prompt**: [tasks/WP04-stable-lane-identity.md](./tasks/WP04-stable-lane-identity.md) (~280 lines)
- **Risks**: PP-F5 — confirm finalize READS BACK the minted id rather than also-minting positionally.

### WP05 — Behind-HEAD recovery remedy (FR-011)
- **Goal**: distinguish a checkout merely behind its own HEAD from real local changes; never advise
  the merge-reverting "Commit". Traces #4982 #4997.
- **Owns**: `src/specify_cli/merge/preflight.py` (reads `merge/git_probes.py`, does not edit it).
  **Profile**: `python-pedro`. **Deps**: none.
- **Subtasks**: T021–T024. **Prompt**: [tasks/WP05-behind-head-remedy.md](./tasks/WP05-behind-head-remedy.md) (~250 lines)
- **Risks**: a remedy that stages the lane's own already-merged files reverts the merge.

### WP06 — Reconciliation gate scaffold + verifier (S-D, FR-001/FR-002/FR-012)
- **Goal**: SCAFFOLD (all new `_MergeRunState` fields + phase slot + `reconciliation.py` stub in ONE
  change) then the fail-closed verifier: reachability (approved SHAs from tree tips) + excluded-by-
  patch-id + Lamport-sourced claim, wired between `_phase_commit_and_assert` and cleanup, with the
  manifest reseed-from-state inlined; FR-012 legacy refuse; NFR-005 non-vacuous call-site gate over
  all 6 terminus entry points.
- **Owns**: `src/specify_cli/merge/executor.py`, `src/specify_cli/merge/reconciliation.py` (NEW),
  `src/specify_cli/merge/git_probes.py`. **Profile**: `python-pedro`. **Deps**: WP01, WP02.
- **Subtasks**: T025–T031. **Prompt**: [tasks/WP06-reconciliation-gate-scaffold.md](./tasks/WP06-reconciliation-gate-scaffold.md) (~460 lines)
- **Risks**: a claim sourced through the READ resolver degrades to empty primary → gate passes
  **vacuously** (PP-F3); membership through LWW `reduce_parsed` (#4990) green-washes a rejection;
  a 7th unrouted terminus path bypasses the gate.

### WP07 — Projection + gated teardown (S-B, FR-004)
- **Goal**: project ALL post-checkpoint coord commits onto the target (not only status files);
  gate teardown on reachability + coord-ref CAS. Traces #4981 #4970 #4973. Change **callee internals
  only** — the executor call sites are already wired by WP06.
- **Owns**: `src/specify_cli/merge/bookkeeping_projection.py`, `src/specify_cli/coordination/teardown.py`.
  **Profile**: `python-pedro`. **Deps**: WP06.
- **Subtasks**: T032–T035. **Prompt**: [tasks/WP07-projection-gated-teardown.md](./tasks/WP07-projection-gated-teardown.md) (~280 lines)
- **Risks**: projecting only `status.events.jsonl`/`status.json` (today's bug) still drops concurrent
  verdict/emit commits; teardown that proceeds when the coord tip moved since checkpoint.

### WP08 — Coherence integrity: SHA-scoped heal + topology residue (S-B heal + C-3, FR-005/FR-009)
- **Goal**: strand heal reverts only explicitly recorded SHAs (never a range revert erasing a third
  party's later event); `is_coord_residue_churn` threads the stored mission topology. Traces #4973 #4978.
- **Owns**: `src/specify_cli/coordination/coherence.py`. **Profile**: `python-pedro`. **Deps**: WP07.
- **Subtasks**: T036–T039. **Prompt**: [tasks/WP08-coherence-integrity.md](./tasks/WP08-coherence-integrity.md) (~270 lines)
- **Risks**: a `git revert captured..HEAD` range under a shape-only guard erases a reopen event; a
  topology-blind classifier `reset --hard`s lanes/single_branch planning artifacts.

### WP09 — MergeState authority: single target + owned lock (C-1/C-2, FR-007/FR-008)
- **Goal**: resolve+persist the landing target once (precedence `--target` > persisted > meta) as
  the sole authority for all phases and `--resume`; `owner_token = merge-state-id`; `--abort` frees
  only its own lock. Traces #4985 #4991 #4996.
- **Owns**: `src/specify_cli/core/paths.py`, `src/specify_cli/merge/resolve.py`,
  `src/specify_cli/merge/state.py`, `src/specify_cli/cli/commands/merge.py`. **Profile**: `python-pedro`. **Deps**: WP08.
- **Subtasks**: T040–T043. **Prompt**: [tasks/WP09-mergestate-authority.md](./tasks/WP09-mergestate-authority.md) (~300 lines)
- **Note**: one documented out-of-map edit to `executor.py`'s lock-acquire call site is permitted
  (serial after WP06, no collision) — record the rationale in the WP + PR.
- **Risks**: `owner_token = pid` cannot survive the crash the lock protects (`--resume` = new pid, PP-F2).

### WP10 — Doc/doctrine correction + final green (FR-013)
- **Goal**: correct CLAUDE.md's false compare-and-swap-advance + "sole-authority deterministic
  reducer" claims, the ADR reconciliation note, and `status-model.md`; keep #4990 named-open;
  run the full blast-radius suite green.
- **Owns**: `CLAUDE.md`, `docs/adr/2.x/2026-02-09-3-event-log-merge-semantics.md`,
  `docs/architecture/status-model.md`. **Profile**: `curator-carla`. **Deps**: WP03, WP04, WP05, WP09.
- **Subtasks**: T044–T046. **Prompt**: [tasks/WP10-doc-doctrine-final-green.md](./tasks/WP10-doc-doctrine-final-green.md) (~230 lines)
- **Risks**: over-claiming verdict-integrity a green Tier-0 does not provide while #4990 is open.

## Parallelization

```
Parallel fan (file-isolated, start immediately):
  WP01  tests/terminus/**                      (red-first harness)
  WP02  git/ref_advance.py                      (S-A CAS)
  WP03  write_seam/write_target_degrade/…       (S-C write gate)
  WP04  lanes/compute.py + workspace/context.py (C-4 lane identity)
  WP05  merge/preflight.py                       (FR-011 behind-HEAD)

Serialized executor lane (one owner; _MergeRunState kept coherent):
  WP06  scaffold + verifier + gate wiring   ← WP01, WP02
  WP07  projection + gated teardown         ← WP06
  WP08  coherence heal + residue topology   ← WP07
  WP09  single target + owned lock          ← WP08

Integration:
  WP10  docs + final green                  ← WP03, WP04, WP05, WP09
```

The only multi-writer files — `merge/executor.py` and `coordination/coherence.py` — are confined to
the single serial lane; no parallel-fan WP touches them. WP02 (CAS) is in the fan but MUST land
before WP06 starts (S-D pairs with atomic advance). WP01's Tier-0 property test is the shared gate:
red before, green after the serial lane + companions land.

## MVP scope

**WP06 (S-D reconciliation gate) + WP02 (S-A CAS)** are the MVP: together they make the epic
invariant executable and atomic, converting ~9–10 of the 12 defects from "exit 0 + destroyed work"
into honest fail-closed outcomes (US1). Everything else is defence-in-depth around them.

## Close-out checklist (not a WP — tracked here so it is not honor-system)

Per the mission brief, after `spec-kitty merge` consolidates lanes into **local** `main`:
- [ ] **CHANGELOG.md** entry for the Epic #5001 terminus-integrity fix (owed even without an
      `__init__.py` bump).
- [ ] Set issue-matrix verdicts #4945 #4969 #4970 #4973 #4977 #4978 #4981 #4982 #4985 #4991 #4996
      #4997 `in-mission → fixed` via `spec-kitty agent issue-verdict` before `move-task --to approved`.
      (#4990 and #4972 stay named-open as spun-out siblings.)
- [ ] Pre-merge review squad over the final aggregate diff; fold all findings.
- [ ] Clean branch history (coherent commits, `#`-referenced, attribution footer).
- [ ] Open the draft PR targeting `main`; the operator merges.
