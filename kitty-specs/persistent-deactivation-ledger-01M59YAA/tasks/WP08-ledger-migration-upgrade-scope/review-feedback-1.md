# WP08 review — cycle 1 (reviewer-renata, claude) — REJECT

Most of the WP is sound and verified (see "Verified" below). One behavioural defect blocks approval.

## Findings

1. **[MEDIUM] src/charter/activation/activation_ledger.py:800 (`restamp_pending`), :690 (`noop`), m_4_0_0rc8_activation_ledger.py `detect()` — the crash-recovery re-stamp has no evidence that the migration caused the lag, so rc8 and `migrate activation-ledger` restamp ANY lagging `bundle_content_hash`.**
   - `restamp_pending` is True for any project with a ledger, no legacy key and a manifest stamp that differs from `charter.yaml`. A lag also comes from an ordinary hand-edit of `charter.yaml` after synthesis. `compute_freshness` reads that lag as `synthesized_drg: stale` with the remedy "run charter synthesize". The restamp marks the DRG fresh without any resynthesis, which hides the stale state.
   - The effect is permanent on every project that has no migration ledger, this repository included. `not_recorded` leaves rc8 selected by ledger-diff forever, so every later `spec-kitty upgrade` applies rc8 whenever the stamp lags. Before WP08 the binding behaviour (carry-forward M1, data-model §11, T051.2) was: "rc8 selected, detect() False, not needed, nothing moves, runner records skipped".
   - It also breaks FR-021 ("a re-run reports nothing to do and writes nothing"). Reproduced on a clone of this branch at 9a52f13d by appending a comment line to `.kittify/charter/charter.yaml`:
     - `migrate activation-ledger --dry-run --json` returns `{"result":"dry_run","moves":[]}`;
     - the real run then prints "Moved the activation keys into .kittify/charter/activation.yaml", although nothing moved, and rewrites `synthesis-manifest.yaml`;
     - `get_applicable` still selects rc8.
   - **Required fix:** recover the crash window without the lag heuristic. Option (a): stamp the manifest from the stripped bytes before the authority strip. Compute the hash the stripped `charter.yaml` will have (prepare the strip, hash its `desired_bytes` with the `compute_bundle_content_hash` recipe), re-stamp to that value, then apply the strip. A crash between the two steps leaves legacy keys, so `detect()` stays True and the re-run strips them. Option (b): any other design whose recovery trigger is evidence the migration wrote itself. With either option:
     - `plan.noop` must be True on a ledger project with no legacy key and a lagging stamp, and the run must change zero bytes. Add a test for this next to `test_second_run_changes_zero_bytes`.
     - Keep the `after-config-strip` crash test green.
     - The command must never print "Moved" when `moves` is empty.

2. **[LOW] tests/specify_cli/upgrade/test_init_reseed_keeps_rc8_pending.py:7-8 — the module docstring says "the re-run exits 0", but the test asserts exit 1.** Exit 1 is acceptable as the in-Mission strict-mode pin, and the carry-forward already tells WP14 to flip it. The test does not check why the run exited 1, so an unrelated `SystemExit(1)` would also pass. Required fix: correct the docstring, and assert that the output names the unmigrated refusal (`spec-kitty upgrade` / the key).

3. **[LOW] src/specify_cli/upgrade/migrations/base.py:56 `_canonical_root` lru_cache — a `None` cached for a directory that is not yet a repository stays cached after `git init` in the same process.** This is harmless for the CLI (one process per run). Required fix: state the limit in the docstring, or key the cache on the presence of `.git`. Optional.

## Verified (no action)
- **C-001:** `git diff be770dd1..HEAD -- src/specify_cli/upgrade/migrations/` touches only `base.py`, the new `m_4_0_0rc8_activation_ledger.py` and `order_manifest.txt`. `compute_content_hash` gives the same value at base and head for all 125 shipped migrations; the only new id is rc8.
- **Wrapper:**
  - every wrapped method across all subclasses is a standard `detect`/`can_apply`/`apply`/rc6 method with a path-typed first parameter;
  - abstract methods are preserved (an intermediate abstract subclass still refuses to instantiate);
  - `__wrapped__`/signature are kept; the wrapper is re-entrant and covers the canonical root;
  - `SupersededMigration` is unaffected.
- **Red-first:** at 1454ba6d, 18 tests failed, 15 passed and 2 test files failed to collect. That matches the implementer's report.
- **Dogfood (9a52f13d):**
  - `activation.yaml` equals the 8 keys removed from `charter.yaml`, and the `mission_type_activations` copy in `config.yaml` was equal to the authority;
  - every other key is unchanged and no comment lines were removed;
  - `charter context --action implement` is byte-identical between fresh clones at 54ca630f and 9a52f13d, apart from the clone path.
- **Scope of changes:** the empty-write no-op in `charter_yaml_io.py` and the `_legacy_activation_scope` rename are minimal and recorded in the traces. ruff, format and C901 are clean; the 2 mypy errors predate this WP (fa9c2f50).
