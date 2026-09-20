# Tracer: Tooling Friction — charter-catalog-coherence (#4785)

Append friction encountered while running the mission. Feeds the next mission.

## Planning

- (2026-09-19) Grounding required isolated `git clone` copies for any write-reproduction:
  charter write commands mutate tracked files (`charter.yaml`, activation lists), and this
  clone is the operator's live charter store. Worktrees do NOT isolate charter writes
  (that is literally Finding 3), so a worktree could not be used for repro either.
- (2026-09-19) `activate --resynthesize` transiently crashed on the unrelated `#2627`
  "Global asset input changed" global-asset-cache race during grounding; self-heals on retry.
  Watch for this on the recompile hot path during implement.

## Implement

- Folding the analysis + brownfield findings AFTER `finalize-tasks` left `lanes.json`'s
  `planning_commit_sha` stale → first `spec-kitty implement` failed "cannot auto-merge the
  recorded planning commit". Recovery: re-pin `planning_commit_sha` to current planning HEAD,
  re-run implement. (Fold squad findings BEFORE finalize, or expect the re-pin.)
- The `#2627` "Global asset input changed" global-asset-cache race fires on non-`next` verbs
  (move-task, merge) intermittently; a short retry-loop self-heals it.
- Dependent-lane consolidation: `spec-kitty merge` auto-merges dependency lanes, but a lane
  that never saw a sibling's content goes STALE ("overlapping files"); recovery = merge the
  mission branch into the stale lane, resolve the shared allowlist/baseline conflicts
  (both lanes made the identical edit), commit, `merge --resume`.
- `move-task --to approved` gates: needs all subtasks `mark-status done` + a verdict for
  EVERY `#NNN` in spec.md/prompts (incl. cross-refs); `deferred-with-followup` requires a
  `#NNN`/`Follow-up:` handle in the evidence; commit the review-cycle bookkeeping between WPs.

## Review / Close

- **The full integration suite on the MERGED tree caught 3 real regressions invisible to the
  subset per-WP reviews AND the pre-PR diff review** (green on base, red on branch): a dead-symbol
  gate (WP01 deletion + WP02/WP03 refactor orphaned 3 `__all__` symbols), a glossary-deactivate
  clobber (WP03 recompile-on-first-activate of a config-only project minted a charter.yaml pointer
  → activation split-brain), and synthesize remediation-effectiveness (WP04 fresh-gate too broad).
  Lesson: the integration gate on the consolidated tree is the first moment cross-lane/whole-tree
  defects exist — always run it, and classify each red against the merge base.
- Two integration reds were NOT the diff: `test_org_cascade_chain` (pre-existing org-pack cascade,
  red on base) and `test_lifted_root_no_checklist_surface` (gitignored generated agent-command
  files present in the working clone but not the PR — green on a fresh CI checkout).
