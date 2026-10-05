# Data model: the three glossary terms

Each term is one `GlossaryTerm` (pack) and one `GlossarySeedTerm` (seed) with
identical values. Fields: `surface`, `definition`, `confidence: 0.9`,
`status: active`, optional `synonyms_to_avoid`.

Invariant: the definition string is byte-identical in pack and seed, and its
meaning matches the `docs/context/` entry it points to.

## tool-surface drift

- **Source**: `docs/context/execution.md` → `### Tool-surface drift`
- **synonyms_to_avoid**: `[drift]`
- **definition**: The state of a generated tool surface file that Spec Kitty still tracks as managed but whose content no longer matches anything Spec Kitty wrote, so Spec Kitty will not overwrite it without consent. In practice someone edited a generated slash-command file, command skill, managed skill, agent profile or plugin-bundle component. `spec-kitty upgrade` keeps such a file, names it (`Not updated, your local edit was kept: <path>`) and exits non-zero (whether it should is still open) with the outcome `drift_unresolved` and the failure reason `surface_drift` (ADR 2026-10-04-3); `spec-kitty doctor tool-surfaces` reports the same file as drifted. Not tool-surface drift: a missing file (upgrade recreates it); a file that matches an older generated version (stale; upgrade rewrites it); a file Spec Kitty never generated (user-owned, left untouched); a difference between two branches' copies of `.kittify/metadata.yaml`. A known defect can misclassify an unedited generated file as drifted; that is the defect, not this term. Never write bare 'drift' in operator-facing text; say which file was kept and why. See the Tool-surface drift entry in docs/context/execution.md.

## integrating worktree

- **Source**: `docs/context/execution.md` → `### integrating worktree`
- **synonyms_to_avoid**: none
- **definition**: A linked git worktree whose checked-out branch is a mission, lane or coordination branch (a `kitty/mission-` branch, as recognized by the branch-naming authority), or whose branch cannot be read (a detached HEAD counts, to fail safe). Its branch will later be integrated into another branch of the same Mission. `spec-kitty upgrade`, run from the repository root checkout, skips integrating worktrees: it writes, stamps and commits nothing in them (ADR 2026-10-04-4), which is why a lane can still show a pre-upgrade `.kittify/metadata.yaml`. Not an integrating worktree: a worktree on an ordinary branch, such as a topic or landing branch, where upgrade still upgrades and commits; the repository root checkout, which never is one. For a per-work-package execution checkout in general, say lane worktree. See the integrating worktree entry in docs/context/execution.md.

Wording note: the source says "an ordinary branch (a feature or landing
branch)"; the pack says "a topic or landing branch" to keep the prohibited
product word out of shipped text. Same meaning (any non-mission git branch).

## target-owned bookkeeping

- **Source**: `docs/context/orchestration.md` → `### Target-owned bookkeeping`
- **synonyms_to_avoid**: `[primary-owned bookkeeping]`
- **definition**: A tracked file at the project root that Spec Kitty fully generates, marks 'do not edit', and that no work package authors, declared target-owned in the state contract; today only `.kittify/metadata.yaml`. Its authoritative copy is the one on the merge target branch. When two branches of one Mission carry different copies, each integration site (consolidate, review start, implement resume, lane sync) resolves the conflict to a fixed side without asking: the copy closer to the merge target branch wins, and between two lanes the receiving lane keeps its own until consolidation (per-site table in ADR 2026-10-04-4). The code identifiers `target_owned`, `is_target_owned_path` and the rule id `R-TARGET-OWNED-BOOKKEEPING` carry this sense. Not target-owned: an operator-editable file (`.gitattributes`, `.gitignore`, `.kittify/config.yaml`), whose conflicts still refuse. For where a Mission artifact is stored, say PRIMARY partition; `.kittify/metadata.yaml` is not a Mission artifact and has no partition. No site computes 'the repository root checkout's copy'. Do not call it 'primary-owned': that earlier name suggested the PRIMARY partition or the primary branch, and the merge target branch need not be the primary branch. See the Target-owned bookkeeping entry in docs/context/orchestration.md.
