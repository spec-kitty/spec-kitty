# Research — Nightly Suites Green (run 38021225055)

Phase 0 research for this mission is root-cause classification, not technology selection. The findings below come from local reproduction plus a two-lens profile-loaded grounding squad (architecture-boundary lens + classification/reproduction lens). No new dependency is added, so the supply-chain security controls (DIRECTIVE_051) are **not applicable** to this plan.

## Decision 1 — #5988 integration cluster is a REAL product regression (fix code)

- **Decision**: Fix in code at TWO targeted seams; do NOT relax the owned-lifecycle acceptance pins, and do NOT fix the lock root to `P`.
- **Rationale (refined by the brownfield scout)**: The pins guard a genuine ownership boundary. Introduced by `f815fc9b66` (#5883) collapsing path resolution onto `resolve_canonical_root`→`R`. Two distinct, independently-fixable seams on `root_resolver`:
  - **A (lock-root convergence)** — single site `core/mission_creation_meta.py:199`: the birth write drops `write_root` and locks on `R` while sibling create writers use `P`. Thread `write_root` through `_write_create_meta`.
  - **B (write-target redirect, the real `next→analyze` cause)** — single seam `canonicalize_feature_dir` (`workspace/root_resolver.py:83`): owned-unaware, redirects an owned checkout's status writes to `R`'s stale copy. Make it owned-aware (mirror the coord-worktree guard at `:114-130`); covers all 8 write sites with zero threading.
  - **CORRECTION (verified at implement)**: sub-cluster B was NOT a `canonicalize_feature_dir` redirect; it was acceptance-test staleness vs the #5885 `analyze` DAG step. Only Seam A (birth-write lock) is a code fix. The grounding-squad seam-B hypothesis (attributed, not line-traced) was disproven by instrumentation.
  - **Crucial**: the lock mutex landing under `R` is *tolerated* by the tests (`tolerate_status_mutex_for`); B is about the status *write target*, not the lock root. Keep the two concerns separate (R1) — fixing the lock root to `P` would de-converge the mutex.
- **Alternatives considered**: (a) updating the tests to tolerate the `R` read — rejected, blesses the breach; (b) per-caller threading of the owned root through the ~8/~38 writer sites — rejected as the many-call-sites anti-pattern; the `canonicalize_feature_dir` seam fix subsumes it. **Deferred (out of scope)**: splitting `root_resolver`'s lock-root vs surface-root concerns into two named resolvers — follow-up, not this release fix.

## Decision 2 — #5989 context-errors (4) and #5990 corpus (2) are CI/corpus artifacts (fix test/oracle)

- **Decision**: Harden the test/oracle to match correct production/resolver behavior; do NOT weaken expected codes or prune remotes.
- **Rationale (context-errors)**: `not_in_project` only holds when the cwd has no enclosing project ancestor. The CLI project walk-up is deliberately unbounded (no `stop=`); when pytest basetemp sits inside the repo checkout (the nightly's layout), detection succeeds and the per-command codes (`no_worktree`/`context_not_found`/`context_resolution_failed`) surface. Production resolution is correct; not 3.13-specific (reproduced on local 3.11 by moving basetemp into the repo).
- **Rationale (corpus)**: The resolver's `_coord_branch_exists` has a live `ls-remote` arm (fail-closed-to-present, the #2614 data-loss guard); the independent oracle mirrors only local heads + `refs/remotes/`, not the live arm. On the online nightly, three coordination branches still live on origin → resolver says present, oracle says deleted-fallback → mismatch. The resolver is correct and deliberate; the oracle has a blind spot.
- **Alternatives considered**: CI basetemp-outside-repo config (valid but narrower; the test hardening is the durable fix); pruning stale origin coord branches (fragile, contradicts the online RESOLVER_CASES design).

## Decision 3 — #5987, #5989-template, #5989-pinning, #5990-terminology are drift/derived/doc

- **#5987 git-redaction**: the production clone path runs through the kernel `clone_repository` (`git_source.py:270`), not the monkeypatched `_run_git`, so the test hits real git (modern git strips credentials from the auth-failure line). The redaction code is correct; drive token-bearing stderr through the real clone seam.
- **#5989 template-dir**: the implement command-template lost the `src/specify_cli/missions/*/command-templates/` verification reference; restore at the SOURCE template (or realign the test), edit SOURCE not agent copies.
- **#5989 pinning**: a new `retiring-step` rule exists in-tree but the inventory was not re-derived; re-run `derive_pinning_inventory.py` and disposition the new rule (never regenerate-away).
- **#5990 terminology**: `docs/archive/` is in FORBIDDEN_SCAN_ROOTS but undocumented in the policy doc; add coverage for every `docs/` exempt root.

## Decision 4 — #5991 perf is a real import regression + an operator-owned calibration

- **Decision**: Shave the eager imports at root first; the final budget limit is an operator/CI decision measured on the nightly runner (not a local series).
- **Rationale**: `next_cmd.py:57-59` module-scope imports pull `charter.activation.*` (~70ms, doctrine-to-charter rework), `runtime.next._internal_runtime.schema` (~143ms, next rework), and `status.dup_key_repair` (~19ms) onto the `--help` path, which activates nothing. Deferring them into command bodies restores headroom. FR-011 (budget pass) is no-op passable by a bare limit bump, so FR-010's import-absence assertion is its positive control.
- **Alternatives considered**: bumping `STARTUP_RATIO_LIMIT` alone — rejected as green-washing without the shave.

## Supersession check

`git log --all --grep` for 5987/5989/5990/5991 → none; no changelog/ADR mentions. `STARTUP_RATIO_LIMIT = 2.90` is live. None of the five issues is superseded. #5883 is a context-only reference (the introducing rework), not a work-owing issue.

## Adversarial findings disposition

The grounding squad's findings are all **adopted** (encoded as FR-001…FR-011 and C-001…C-006).

**Post-tasks adversarial review (reviewer-renata) + brownfield scout (paula-patterns) — folded:**
- **F1 (coverage)**: the count is **25**, not 28 (issue bodies: 1+14+6+3+1); WP coverage (14+1+4+2+1+1+1+1) = 25, complete. Corrected across artifacts; WP01 embeds the 14 exact `#5988` test IDs so coverage is verified, not asserted.
- **F2/F3 (seam-vs-threading, guard shape)**: resolved by the scout — two single-seam edits (A `_write_create_meta`; B `canonicalize_feature_dir` owned-aware), NOT per-caller threading; WP01 `owned_files` reshaped to the three real files; FR-003 guards are behavioral over both seams with self-mutation controls. R1/R2 recorded in plan IC-01.
- **F4 (WP03 mis-classification risk)**: before hardening the context test, confirm the per-command error codes (`no_worktree`/`context_not_found`/`context_resolution_failed`) match the pre-#5883 merge-base, so hardening cannot green-wash a rework-introduced guard-ordering regression. Added as a WP03 subtask.
- **F5 (WP07)**: the test's `docs/development/terminology-exemptions.md` assertion is satisfied by the test file's own source literal — do NOT create a second doc; cover all docs/ exempt roots (`docs/migrations/`, `docs/adr/`, `docs/archive/`, `docs/plans/engineering-notes/`, `docs/plans/initiatives/`, `docs/reports/`) in the existing `.../reference/...` doc. Noted in WP07.
- **F6/F7 (WP04)**: oracle must re-derive remote presence from the live primitive independently (not delegate to the resolver), and the regression pin must encode the remote-live/local-absent asymmetry. Reinforced in WP04.
- **F8 (NFR-004)**: drift/CI/derived/doc WPs legitimately reuse the pre-existing failing nightly test as the red-first pin (no new `@regression` marker); only WP01/WP02/WP08 create new repros. Clarified in NFR-004.

No contested finding was dropped.
