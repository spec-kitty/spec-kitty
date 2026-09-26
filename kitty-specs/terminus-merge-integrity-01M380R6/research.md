# Research — Terminus / Merge-Coord Integrity

Phase 0 output. Design decisions that resolve the spec's open questions, each with rationale +
alternatives, grounded in `work/epic-5001-research/DEBRIEF.md` and the four per-lens deliverables.

## D1 — Seam shape: one `SurfaceAuthority` object, two entry points

- **Decision**: introduce a single `SurfaceAuthority` with `resolve_for_read()` (keeps today's
  loud-primary-fallback, which is correct for reads) and `resolve_for_write()` (fail-closed: refuse
  when the authoritative coord worktree/branch is unresolved/unmaterialized). Not two separate
  classes.
- **Rationale**: the split-brain lens showed the read side (`coordination/surface_resolver.py`) is
  already correct; only writes lack a gate. One object with two entry points keeps the authority
  decision in one place (DIRECTIVE_044) while letting reads and writes differ in failure posture.
- **Alternatives**: (a) two classes (write-fence + read-resolver) — rejected: duplicates the
  resolution logic, reintroduces drift risk; (b) gate at each call site — rejected: that is exactly
  the per-site open-coding that caused the class.

## D2 — CAS on the forward ref advance

- **Decision**: `advance_branch_ref` uses `git update-ref <ref> <new> <old>` (3-arg CAS) with the
  `<old>` read at the start of the transaction; on mismatch, fail closed (raise), never retry-write.
  The rollback path already uses 3-arg CAS — bring the advance to the same discipline.
- **Rationale**: eliminates the TOCTOU between the `merge-base --is-ancestor` precheck and the write
  (the mechanism behind #4996's rewind and the abort-frees-live-lock amplification). Removes the
  docstring's admission that safety rests on the global lock.
- **Alternatives**: keep lock-based safety — rejected: the lock is itself unsound (#4996) and CAS is
  the git-native atomic primitive already in the file.

## D3 — Reconciliation gate: reachability, not envelope

- **Decision**: `MergeOutcomeVerifier.verify(target, approved_wp_commit_set)` asserts (a) every
  approved WP's approved commits are reachable from `target`, and (b) no excluded (canceled/removed)
  WP commit is reachable. It runs **before** any teardown; failure ⇒ refuse + non-zero + guidance,
  no teardown, no mutation.
- **Rationale**: today's asserts check derived rows/meta the same run wrote (circular). Tree
  reachability is the only authority that cannot be faked by the bookkeeping that is itself wrong.
  Reuses `ref_advance` ancestry helpers + `_durable_done_wps_on_coordination_ref`.
- **Alternatives**: strengthen the row asserts — rejected: still trusts a self-written envelope;
  full tree diff of every file — rejected: O(repo) and unnecessary (commit-set reachability suffices
  and is O(#approved commits), satisfying NFR-003).

## D4 — Projection before teardown (all commits, not just status files)

- **Decision**: capture the coord tip at a bookkeeping checkpoint; before teardown, project **every**
  commit added to the coord ref after the checkpoint onto the target (not only
  `status.events.jsonl`/`status.json`), then gate teardown on the reachability check. Coord-ref
  advance is CAS (tip unchanged since checkpoint) or teardown aborts.
- **Rationale**: closes #4981/#4970/#4973 — concurrent status-emit/verdict commits currently die in
  teardown. Content-scoped strand heal (revert only recorded SHAs) replaces the range revert that
  erased third-party events.
- **Alternatives**: hold a merge writer-fence lock over the whole window — considered as a
  complement (reduces the race window) but not a replacement; projection + coord-CAS is the
  correctness guarantee, the fence is an optimization deferred unless tests show contention.

## D5 — Single persisted merge target (authority order)

- **Decision**: resolve the landing branch once (precedence: explicit `--target` > persisted
  MergeState target > meta.json), persist it into MergeState, and make **that** the sole read
  authority for all phases and every `--resume`. `--resume` never re-derives from meta.
- **Rationale**: closes #4985/#4991 — four copies today; executor reads the manifest, MergeState's
  target is write-only. One persisted authority ends the split-brain.
- **Alternatives**: pass `--target` again on resume — rejected: operators don't, and the crash path
  is exactly when they can't.

## D6 — Forward-only legacy handling (operator decision)

- **Decision**: pre-fix in-flight MergeState/coord state is detected (schema/marker absent) and the
  terminus command refuses with a recovery instruction; the new guarantees are not retro-applied to
  auto-heal it.
- **Rationale**: operator-confirmed. Auto-healing pre-fix corrupted state is the exact risky
  auto-mutation this epic condemns; refuse-and-guide is honest and safe.
- **Alternatives**: retroactive recovery — rejected by operator (higher blast radius over corrupted
  state).

## D7 — Owned merge lock

- **Decision**: key the merge lock with an owner token (pid + start time / merge-state id); `--abort`
  releases only a lock whose owner matches the aborting invocation. A stale/dead-owner lock is
  reclaimable via an explicit liveness check, never by blanket unlink.
- **Rationale**: closes #4996 second half — today `--abort` unlinks the single global lock of any
  running merge.

## D8 — Topology-parameterized residue classifier

- **Decision**: thread the mission's stored topology into `is_coord_residue_churn`; the merge dirty
  gate classifies using actual topology, so lanes/single_branch planning artifacts are never treated
  as coord residue and `reset --hard`ed.
- **Rationale**: closes #4978; the classifier's own docstring already says it is only valid under
  COORD.

## D9 — Stable, origin-aware lane identity

- **Decision**: bind a lane's identity to its git branch at creation (stable id, not positional
  letter recomputed on WP removal); lane base resolution consults `origin/<lane>` before cutting a
  fresh branch from local main.
- **Rationale**: closes #4945 (re-lettering) and #4969 (origin shadowing).

## Adversarial evidence (planning)

No dependency/security-impacting decision was made (no install-surface change), so the supply-chain
adversarial pass is **not applicable** in v1 terms. The design-level adversarial challenge is the
**post-plan brownfield squad** run at this pointcut; its contested findings and dispositions
(`accepted` / `changed` / `deferred_with_rationale`) are appended below after that squad reports.

### Post-plan squad dispositions (3 lenses: paula split-brain-closure, renata coverage-honesty, priti decomposition)

Per `contracts/adversarial-evidence-contract.md`, every contested finding gets a disposition:
`accepted` (design changed), `deferred_with_rationale`, or `rejected`. Full lens reports:
`work/epic-5001-research/postplan-{paula,renata,priti}.md`.

| # | Finding | Disposition | Change |
|---|---|---|---|
| PP-F3 / RN-Q4 | Verifier claim sourced via `resolve_for_read` degrades to empty primary → gate passes **vacuously**; and membership flows through LWW `reduce_parsed` (#4990) | **ACCEPTED** | D3+ below: claim sourced **fail-closed** (refuse on empty/degraded, cross-check against manifest `all_wp_ids`) AND through the **Lamport wrapper** (`status/reducer.py:371` `materialize`/`reduce_shared_state`), never `reduce_parsed`. In-`specify_cli` routing only — does NOT modify `spec_kitty_events`, does NOT cross C-002, does NOT fix #4990's reducer itself. |
| RN-F1 | #4970 real write-degrade is `coordination/write_seam.write_artifact` → `mission_runtime.write_target_degrade.resolve_write_target_or_degrade`; chain `cli/commands/agent/issue_verdict.py:129` → `tasks/issue_matrix.py:328` → write_seam — NOT `surface_resolver.py` | **ACCEPTED** | S-C write gate moves to `write_seam` / `resolve_write_target_or_degrade`; `surface_resolver.resolve_for_write` becomes a thin helper the real write chain calls, not a redundant guard. |
| RN-F3 / PP-F1 | C-1 real authority is `core/paths.py resolve_merge_target_branch` (via `merge/resolve.py:284`); executor reads `run.lanes_manifest.target_branch` (28 sites) seeded from meta at `executor.py:2536-2538` BEFORE state load (`:2280-2288`) and never reconciled to `state.target_branch` (the live #4991 mechanism) | **ACCEPTED** | C-1 adds `core/paths.py` + a single **manifest-reseed-from-state** point right after `_load_or_create_merge_state`, so the 28 read-sites see the persisted target. |
| RN-F3 | Plan's C-004 locality `{merge,coordination,git,lanes}` cannot even wire the fix — real sites include `core/paths.py`, `tasks/issue_matrix.py`, `cli/commands/agent/issue_verdict.py`, `src/mission_runtime/…write_target_degrade`, `status/reducer.py` (routing), `CLAUDE.md` | **ACCEPTED** | C-004 widened to the true seam set (below). Layer note: `mission_runtime` is a deeper layer; edits there respect the enforced chain `…{mission_runtime}<-specify_cli`. |
| PP-F2 | Lock `owner_token` = "pid OR state-id" re-splits durable/ephemeral identity — a pid can't survive the crash the lock protects (`--resume` = new pid) | **ACCEPTED** | Pin `owner_token = merge-state-id` (stable across resume). `acquire_merge_lock` (`state.py:370`) already writes a body — clean change. |
| RN-F4 | S-D "no excluded commit reachable" uses WP-IDs/SHAs; misses cherry-picked/rebased/re-lettered canceled code (`lanes/compute.py:536` positional) | **ACCEPTED** | Excluded-commit detection uses **patch-id equivalence** (not just SHA) so cherry-picked/re-lettered copies of canceled code are caught; canceled set sourced from `acceptably_canceled_wp_ids` mapped to lane tips. |
| RN-Q3 | Fakeable DoD: nothing forbids deriving approved SHAs from status rows (the vacuous `_assert_merged_wps_done_on_target` pattern) or mocking `_run_git` in repros | **ACCEPTED** | Contract pins: approved SHAs come from **lane-branch git tips** (not status rows); per-child repros drive the **real CLI entry point**, no `_run_git`/subprocess mocking; excluded-check is non-vacuous even when canceled set is empty (planted-canceled-commit assertion). |
| RN-F5 / PP | NFR-005 non-vacuous gate must enumerate **all 6 terminus entry points** incl. `upgrade` | **ACCEPTED** | Gate allowlist enumerates merge/resume/abort/upgrade/issue-verdict/doctor-coordination-fix; self-mutation test proves a 7th unrouted path fails. |
| PR-priti | "Parallel companions" mislabeled — S-D/S-B/C-1/C-2 all mutate `executor.py` `_MergeRunState` (2663 lines, already function-decomposed into ~50 `_phase_*`) | **ACCEPTED** | Add a **scaffold WP** (all new dataclass fields + linear-caller phase slot + `reconciliation.py` stub in ONE change), then a **single serialized executor lane** {scaffold→S-D→S-B→C-1→C-2→C-3}. NO god-module decomposition (out-of-domain, DIRECTIVE_024). |
| PR-priti | `coherence.py` double-owned (S-B heal ∧ C-3 classifier); `git_probes.py` unassigned; S-C base = `implement.py:_validate_base_ref` not `workspace/context.py` | **ACCEPTED** | `coherence.py` → one owner in the serial lane; `git_probes.py` → S-D lane; S-C corrected to `implement.py:_validate_base_ref`. |
| PP-F4 / RN-Q4 | Green Tier-0 could imply verdict-integrity it doesn't provide while #4990 open | **ACCEPTED** | Gate success message scoped to "approved-WP commit reachability"; #4990 stays named-open in FR-013 docs. |
| PP-F5 | `lanes/compute.py:515-537` re-runs positional lettering every finalize — confirm it READS BACK the minted id, not also-mints | **ACCEPTED** | C-4 mints stable id once at creation and reads it back on finalize; positional lettering never overwrites a bound id. |

**No finding rejected or silently dropped.** The spine (S-A/S-D/S-B insertion points) was confirmed
correct by all three lenses; the changes above are localization + claim-integrity + sequencing
corrections, not a re-architecture.

### D3+ (amended) — verifier claim integrity
The verifier's `approved_wp_set` is sourced (a) **fail-closed** — refuse when the coord surface is
unresolved/unmaterialized or the derived claim is empty while the manifest lists WPs; (b) through
the **Lamport** reduction wrapper, so a wall-clock-later approval cannot override a committed
rejection in the claim the gate trusts; (c) approved commit SHAs come from **lane-branch git tips**,
never status rows. This makes the gate non-vacuous on both axes (tree AND claim).
