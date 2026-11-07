# Doctrine scan: lanes and worktrees in spec-kitty-open-packs

Source: `spec-kitty/spec-kitty-open-packs` at `23686fb`. Paths are relative to that repository's root. The command skills (`spk-*`, `spec-kitty-*`) are not in the packs; they live in core under `src/charter/offering/skills/`. The fetched copy under core `packs/` had drifted from that HEAD in about 20 files at scan time.

## Inventory

- `packs/built-in/paradigms/execution-lanes.paradigm.yaml:1-10`: one isolated lane worktree per WP is the default.
- `packs/built-in/missions/built_in_step_contracts/implement.step-contract.yaml:10-21`. Line 20 calls lanes "the default and only supported git worktree paradigm", yet lists other paradigms as candidates.
- `packs/built-in/missions/software-dev/steps/implement.prompt.md:39-58`: working-directory rules. Line 46 is the only WRITE_CHECKOUT_* mention (OCCUPIED). Line 45 allows "a lane worktree, or a harness-isolated worktree".
- `.../implement.guidelines.md:7-24`: "Working Directory Discipline"; line 11 says "NEVER write deliverable files to the repository root checkout".
- `.../review.prompt.md:16-27`: review from your own checkout.
- `.../accept.prompt.md:16-25`: a `cd` recipe to get back to the root checkout.
- `.../analyze.prompt.md:205-215`: DIRTY_WORKTREE recovery (write the report outside the checkout).
- `.../tasks-finalize.prompt.md:66-85`: WPs on a shared surface "share a single worktree".
- `packs/built-in/procedures/mission-wrap-up-sequence.procedure.yaml:23-31`: "Resolve any stale-lane conflicts on shared files".
- `packs/built-in/procedures/post-merge-arch-gate-adjudication.procedure.yaml:22-26`. Line 22 has `git stash  # or use a worktree`, which contradicts `git-worktree-pr-workflow.guide.md:17-21`. Line 26 adds a `/tmp` worktree with no cleanup step.
- `packs/built-in/tactics/pr-agent-worktree-isolation.tactic.yaml`: harness `isolation: "worktree"`. This is a second worktree concept, unrelated to lanes.
- `packs/built-in/toolguides/git-worktree-pr-workflow.guide.md`: 23 of 110 lines mention worktrees.
- `packs/built-in/toolguides/efficient-local-tooling.guide.md:108-114`. Line 112 says a bare `pytest` "can silently import the wrong checkout's source tree".
- `packs/internal/procedures/landing-contributor-prs.procedure.yaml:22-26`: a third worktree kind (`.worktrees/pr-<N>-landing`). Line 26: "If a worktree is stale or points at a missing gitdir, create a fresh standalone checkout rather than reusing the broken one."
- `packs/internal/glossary_packs/spk-internal-glossary.glossary-pack.yaml:90-113`: the coord/primary partition, and a cutover guard that "Reads the primary checkout, which is a footgun in shared worktrees".
- `packs/internal/directives/no-full-heavy-suites-in-mission.directive.yaml:10-11,49-51`: parallel lanes contend for the machine.

## Findings

1. **No cleanup doctrine.** There is none for lane or coordination worktrees. DESTROYED_LANE and LANE_WORK_TIP_UNKNOWN appear nowhere in the packs or skills.
2. **No status-surface rule.** No pack doctrine tells an agent which checkout to read status from. Agents are told to work only inside the lane worktree, while the internal glossary routes status writes to coord or primary.
3. **"lane" means two things.** It is a WP lifecycle state in the glossary (`spec-kitty-core.glossary-pack.yaml:260-265`) and an execution workspace in the paradigm.
4. **Three worktree concepts:** spec-kitty lane worktrees, harness-isolated agent worktrees, and manual PR-landing worktrees.
5. **Root checkout rules conflict.** "Never write to the root checkout" (implement.guidelines.md:11) contradicts "single_branch WPs run in the root checkout" (implement.prompt.md:42).
6. **Stale command names.** The skills still say `spec-kitty merge`; the packs say `consolidate`.
7. **Workaround text that signals friction.** In core skills:
   - The implement-review skill (about lines 844-860) has a manual stale-lane refresh: `git merge kitty/mission-<slug>` inside the lane worktree.
   - spec-kitty-git-workflow (162-171) has "Refreshing a Stale Lane Workspace".
