# Tracer: Tooling Friction

Append friction encountered while driving this mission (feeds the next mission's setup).

## Planning
- `spec-kitty agent mission create` sets `target_branch` to the *current* branch when `--target-branch` is omitted; this is correct for the lane→feature-branch→PR flow but is easy to misread as "targets main". Named explicitly in the branch contract to avoid the `primary`/`merge` footgun.
- Shell cwd silently follows `cd` into the mission dir across Bash calls; switched to absolute paths to avoid path drift.

## Implementation
- `spec-kitty implement WP##` stamps `base_commit`/`base_branch` into the WP frontmatter, leaving it dirty; the NEXT `implement` (or any state move) refuses until you commit that stamp. Commit the frontmatter stamp immediately after each `implement`.
- Transient `ensure_global_agent_commands` `RuntimeError` on CLI startup (agent-command health rebuild) intermittently aborted a command mid-run (e.g. one `issue-verdict` in a batch silently didn't record). Re-run the single command; verify the effect (read the matrix), don't trust the batch.
- **Multi-dependency lane base is NOT auto-consolidated.** `implement WP02` (deps [WP01, WP03]) created lane-b at the mission base (638e27d2fe), NOT a merge of the two dep lanes. Because WP01/WP03 touch disjoint files, stacked them linearly by hand: `git -C <lane-b> reset --hard <WP01-tip>` then `git cherry-pick <WP03 commits>`. A single-dep WP would just `git rebase <dep-lane>` (the approval message hints this). Worth a resolver improvement upstream.
- Tests must run with `PYTHONPATH=<worktree>/src` and in-process invocation (CliRunner/direct calls) — the global `.venv/bin/spec-kitty` resolves the MAIN checkout's src, not the lane worktree's edits, so a shelled CLI test would validate the wrong code.

## Review / consolidation
- Issue-matrix approval gate (`move-task WP## --to approved`) is MISSION-level: it refuses until EVERY cited `#NNNN` (incl. context/precedent/out-of-scope refs the artifacts merely mention) carries a non-`unknown` verdict. Resolve excluded siblings + precedent refs as `not-applicable`, in-flight WP issues as `in-mission` (flip to `fixed` as each WP approves). Per-WP approval is effectively serialized behind the whole matrix.
- `move-task --to approved` also refuses while mission bookkeeping (status.events.jsonl, review-cycle artifacts) is uncommitted — commit the mission dir first.
- zsh/bash word-splitting: a `M="--mission <slug>"` var used unquoted as `$M` was consumed as a single option token (`No such option: --mission <slug>`). Run `issue-verdict`/`move-task` with literal flags, no variable expansion (cf. cli-caveats skill).
