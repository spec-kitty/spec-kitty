# Research: Concurrency-safe cold startup asset assessment

Sources: the pre-spec grounding squad, made of an alignment lens (debugger-debbie, opus) and a scope lens (planner-priti, opus), and the post-spec squad, made of a design-soundness lens (architect-alphonso, opus) and a spec-quality lens (reviewer-renata, opus). Evidence comes from main `a862d471a9`.

## R-0: Is the defect still real? (alignment lens)

- **Shape 2 (fresh home, `ensure_runtime`) is REAL.** With Ivan's fresh-home reproducer, 16/16 processes passed in each of three N=16 runs. The three N=32 runs gave 32/32, 32/32 and 27 passed + **5 failed**. With N=16 pinned to 4 CPUs, one run in three had **1/16 fail**. Every failure is `main_callback → ensure_runtime → RuntimeError: Asset changed during preparation: ~/.kittify/cache/runtime_bootstrap-assets.json`.
- **Shape 1 ("Global asset input changed" at `ensure_global_agent_commands`) is SUPERSEDED** for same-version peers by PR #4174's `apply_with_reassess`. It did not reproduce: 0 failures and 0 torn builds.
- **Traced mechanism.** One loser tore three times on successive stages of the *same* peer apply (dirs → content → inventory). `retry_torn_read` re-runs immediately, so it re-races rather than waiting. The traces also show the winner already held the cold sentinel **before** the losers tore, so blocking on it waits the write out.
- **Supersession.** No merged or open PR fixes shape 2.

## D-1: Escalate to the serialization point on an unlocked torn read

- **Decision.** The first destination-role torn read on the unlocked pass makes the owner take its serialization point and rebuild once under it.
- **Rationale.** Every writer runs under that serialization point, so once it is granted the peer has finished. The waiting is deterministic, not probabilistic.
- **Alternatives rejected.**
  - (B) More attempts or backoff. This is still probabilistic and only shifts the window, which amounts to "retry-to-green" and violates DIRECTIVE_034.
  - (C) Cache the unlocked assessment, or skip it on a cold home. That is a larger change that touches warm-path performance (#4516 territory).

## D-2: One serialization authority, extracted from `recheck_assets`

- **Decision.** Extract lines ~516-533 of `recheck_assets` verbatim into `_serialize_owner(lock_paths, anchor)`. It takes the sentinel if any lock path is absent, locks every existing lock path, then sets `_HELD_LOCKS`. Both `recheck_assets` and `build_serialized` use it.
- **Rationale.** Any other lock choice is a second authority. The escalation must take *exactly* what the locked recheck takes, otherwise the sentinel/owner-lock handoff could let a loser lock a different file than the one the writer holds.
- **Alternative rejected.** Deriving the lock from the owner name (`cache/<owner>.lock`) creates a parallel authority that can drift.

## D-3: Carry the lock identity on a typed exception

- **Decision.** `observe()` raises `TornReadError(ValueError)` with `path`, `role`, `lock_paths=(self.lock_path,)` and `anchor=self.root.path`. These are the same values `finish()` puts into `PreparedAssets`.
- **Rationale.** `incomplete()` drops the `AssetPreparation`, so without this the lock identity is unrecoverable at the failure site. Subclassing `ValueError` keeps every existing handler, and the message text is unchanged.
- **Alternative rejected.** Keeping `_TORN_READ_MESSAGE_PREFIX` string matching routes on prose, which the charter rules out (single canonical authority, no message-parsing).

## D-4: Release the serialization point after the locked build (do not hold it through apply)

- **Decision.** `build_serialized` releases the point after the locked rebuild. If effects remain, the existing `apply_with_reassess` re-acquires it, re-checks and rebuilds, which already closes the TOCTOU window.
- **Rationale.** Holding the point across apply would mean restructuring all three `ensure_*`, the tool-surface provider and the installer, for no correctness gain.
- **Cost.** A crashed-peer remainder costs at most 2 extra assessments (NFR-003).

## D-5: Retire the unlocked retry loop

- **Decision.** There is one unlocked attempt, then escalation. `retry_torn_read` and `_TORN_READ_RETRY_ATTEMPTS` are removed, and the dead-symbol gate is honoured.
- **Rationale.** An unlocked retry can only re-race a writer that runs under a lock. Removing the loop is also what NFR-003 "no busy-retry" means.

## D-6: Source-role torn read is terminal source drift

- **Decision.** A torn read whose effective role is `source_read` is refused without escalation.
- **Rationale.** Source drift is never tolerated (C-001). Peers only write destinations. Ancestor directories shared by source and destination trees cannot false-positive, because directory observations drop mtime and compare identity by `(dev, ino)` (`_observation`, `asset_preparation.py:158-162`). A dedicated test pins this.

## D-7: Reuse the CLI error-presentation seam for FR-005

- **Decision.** Add `StartupAssetError(GuardedReadError, RuntimeError)`, raised by the three `ensure_*` entry points in place of bare `RuntimeError`. `_run_app_with_error_hook` (`src/specify_cli/__init__.py:451`) renders it at exit 1, as one stderr line or a JSON envelope under `--json`.
- **Rationale.** This is the single existing authority (C-010). D3 multiple inheritance keeps `except RuntimeError` callers (`init.py`, `migrate_cmd.py`, existing tests) matching.
- **Alternative rejected.** A new renderer or a new exit-code convention.

## D-8: No ADR

- The lock-free warm-path invariant and the lock order are unchanged. The fix reuses `recheck_assets`' set as-is.
- "An assessment may now block after a torn read" (R-4 in plan.md) is plan-level and is documented in the `build_serialized` docstring. #4885 (the fate of the reassess gate) gets a cross-reference comment only.

## Contested findings disposition

| Finding (squad) | Disposition |
|---|---|
| Serialization point must equal the `recheck_assets` lock set (arch HIGH) | accepted: D-2, C-008 |
| Lock identity lost at `incomplete()` (arch/renata HIGH) | accepted: D-3, FR-003 |
| Source-role torn read is today retried; "as today" ill-defined (renata HIGH) | accepted: D-6, spec US3.2 rewritten |
| `next` does not run startup preparation; other `assess_*` callers bypass `ensure_*` (renata HIGH) | accepted: spec corrected; fix placed at the assessment layer (R-4) |
| Pass-count NFRs vacuous without a spy harness (renata MED-HIGH) | accepted: NFR-002/003 rewritten, spy test planned |
| Red-first must inject at leaf I/O (renata MED) | accepted: FR-006, test design |
| NFR-001/SC-001 flaky as a gate (renata MED) | accepted: evidence only; SC-002 is the gate |
| FR-005 reuse `GuardedReadError` hook (both MED) | accepted: D-7, C-010 |
| Hold the lock through apply? (arch MED) | rejected: D-4 (no correctness gain, large restructure) |
| Retire the unlocked retry (arch LOW) | accepted: D-5 |
| Create-then-lock window in the installer's apply (arch LOW) | deferred with rationale: benign atomic canonical writes; recorded as R-1 |
| Operator signal when waiting (renata LOW) | accepted: FR-008 |
| Windows lock-read safety (renata LOW) | accepted: C-009 |
