---
work_package_id: WP02
title: Document the kept reflog refs and the reachability rule
dependencies:
- WP01
requirement_refs:
- FR-006
- NFR-003
planning_base_branch: issue-7211-reflog-reachable-prune
merge_target_branch: issue-7211-reflog-reachable-prune
branch_strategy: Planning artifacts for this mission were generated on issue-7211-reflog-reachable-prune. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7211-reflog-reachable-prune unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
history: []
agent_profile: planner-priti
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/development/how-to/pr-landing.md
- docs/api/cli-commands.md
- docs/changelog/unreleased/**
role: planner
tags: []
tracker_refs: []
---

# WP02 — Document the kept reflog refs and the reachability rule

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `planner-priti`
- **Role**: `planner`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Document what the prune now guarantees, where the kept refs live, and how to restore from them — in the landing runbook, the `doctor workspaces` CLI reference, and a per-PR changelog fragment.

## Context

WP01 makes the prune record commits that only a reflog still reached. An operator who reads the runbook must know that a `refs/spec-kitty/discarded/reflog/<sha>` ref means "this commit was reachable only from a destroyed reflog, and was kept", and how to bring it back into a branch. The changelog is assembled from fragments: read `docs/changelog/unreleased/README.md` for the required shape and naming.

## Subtask T008: Runbook and CLI reference

**Purpose**: The two doc surfaces the prune already owns.

**Steps**:

1. `docs/development/how-to/pr-landing.md` — in the pruning section, add what the removal does to reflogs, the reachability rule in two sentences, the ref namespace, and the restore recipe (`git branch <name> refs/spec-kitty/discarded/reflog/<sha>`). State the patch-narrowing: a pre-rebase commit whose patch is already on the primary ref is not kept.
2. `docs/api/cli-commands.md` — in the existing `doctor workspaces --prune` description, add the new output line and the additive JSON key `kept_commits`. Regenerate only this section if the file is generated; verify with `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` and expect `errors=0`. Do not rebuild the whole reference: other agents share the machine's asset cache.
3. If a module docstring in `src/specify_cli/workspace/landed_worktrees.py` still describes only the tip guarantee, that edit belongs to WP01's ownership; note it in the review instead of editing outside `owned_files`.

**Files**: `docs/development/how-to/pr-landing.md` (+~15 lines), `docs/api/cli-commands.md` (+~2 lines).

**Validation**: `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` reports `errors=0`; `uv run --frozen python -m scripts.docs.check_spelling` is clean for the touched files.

## Subtask T009: Changelog fragment

**Purpose**: The user-facing entry, in the fragment shape this repository now uses.

**Steps**:

1. Add `docs/changelog/unreleased/<pr>.fixed.md` (rename from the issue-suffixed name to the real PR number once the PR exists).
2. One entry, impact first, with `(#7211)` and before/after, under 1,200 characters, for example:
   `- **\`doctor workspaces --prune\` keeps commits that only a destroyed reflog still reached** (#7211). \`git worktree remove\` deletes the worktree HEAD reflog and \`git branch -D\` deletes the branch reflog, so a commit made while detached, or dropped with \`reset --hard\`, was left for \`git gc\`. **Before:** it was dropped silently. **After:** it is kept under \`refs/spec-kitty/discarded/reflog/<sha>\` and named in the report.`
3. Do **not** edit `docs/changelog/CHANGELOG.md`.
4. Verify with `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.

**Files**: `docs/changelog/unreleased/<pr>.fixed.md` (new, 1 entry).

**Validation**: both checker commands exit 0.

## Definition of Done

- The runbook states the rule, the namespace, the patch narrowing and the restore recipe.
- The CLI reference names the new output line and `kept_commits`.
- The changelog fragment exists with the PR number in its filename, and both docs checkers are clean.
- `docs/changelog/CHANGELOG.md` is untouched.

## Risks

- `docs/api/cli-commands.md` is checked by a freshness gate; a hand edit that disagrees with the generator turns CI red. Regenerate only the affected surface and verify with the freshness checker.
- A fragment named with the issue number instead of the PR number fails the release assembly; rename it before the final push.

## Reviewer Guidance

- Does the runbook say what to do with a kept ref, not just that it exists?
- Is the patch narrowing stated honestly (a rebase landing keeps nothing; anything unproven is kept)?
- Is the changelog a fragment, with the real PR number, and is `CHANGELOG.md` untouched?
