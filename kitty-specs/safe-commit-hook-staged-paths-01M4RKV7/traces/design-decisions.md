# Tracer: Design Decisions — safe-commit-hook-staged-paths-01M4RKV7

- **[2026-10-12][specify] New error class mirrors `SafeCommitIndexResidue`.**
  `SafeCommitUnrequestedPaths(SafeCommitRecoveryFailed)` with its own `error_code`
  (`SAFE_COMMIT_UNREQUESTED_PATHS`), carrying `commit_sha` + the extra paths. Rationale: the issue
  says the caller surfaces must report "DID land" the way `SAFE_COMMIT_INDEX_RESIDUE` already does;
  `SAFE_COMMIT_INDEX_RESIDUE` achieves that purely by being a `SafeCommitRecoveryFailed` subclass
  with `commit_sha` set. Reusing that shape keeps a single reporting pattern (no new caller logic).
- **[2026-10-12][specify] One shared post-landing helper, two call sites.** The `--only` route has
  no post-landing check today; the FR-022 route syncs only `requested+deletions`. A single helper
  `_assert_committed_paths_requested(...)` (diff-tree vs requested set, re-sync extras, raise) is
  called from both, satisfying "one post-landing check ... covering BOTH routes".
- **[2026-10-12][specify] Comparison basis = `git diff-tree --name-only -r <sha>` vs the requested
  set.** The requested set is `normalized_files` for `--only`, or `requested ∪ deletions` for
  FR-022. A committed path not in the requested set is "extra". A subset (partial no-op) is fine.
- **[2026-10-12][specify] Index re-sync reuses the `git reset -q HEAD -- <paths>` pattern** from
  `_sync_real_index_after_commit`, applied to the extra paths, so the operator's real index no
  longer stages a revert (`MM` cleared).
- **[2026-10-12][specify] Contract version bump to 1.15.0.** Consistent with the 1.13.0/1.14.0
  precedent for a new verb-reachable `SAFE_COMMIT_*` code; single canonical authority
  (`upstream_contract.json`) + its JSON-equal docs mirror + the envelope changelog, in one change.
- **[2026-10-12][specify] Expected-parent route left untouched (C-002).** It rebuilds the tree from
  requested paths only; it is the negative control and the one route #5903 confirms is correct.
- **[2026-10-12][review] POSIX-normalize both sides of the path comparison (adversarial fold).** The
  pre-PR adversarial squad found a Windows release-blocker: `git diff-tree` output is always
  forward-slashed, but `str(Path)` uses backslashes on Windows, so comparing the committed set
  against `normalized_files` directly would false-positive on every nested-path commit (even with no
  hook) and mutate the index. Both sides now route through `kernel.paths.to_posix` (the #2836
  separator seam). Added a nested-path no-hook regression test so `ci-windows.yml` exercises it; the
  single-component fixtures could not. Documented the individual-files precondition (Finding 2,
  latent). Finding 3 (re-sync drops a `git add -p` partial stage of a swept path) matches existing
  `_sync_real_index_after_commit` behaviour and is accepted.
