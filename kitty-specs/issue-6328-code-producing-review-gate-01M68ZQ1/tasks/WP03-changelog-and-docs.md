---
work_package_id: WP03
title: Changelog and docs freshness
dependencies:
- WP01
- WP02
requirement_refs:
- FR-008
- SC-004
planning_base_branch: issue-6328-code-producing-review-gate
merge_target_branch: issue-6328-code-producing-review-gate
branch_strategy: Planning artifacts for this mission were generated on issue-6328-code-producing-review-gate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6328-code-producing-review-gate unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
phase: Phase 2 - Record
history:
- at: '2026-10-31T12:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: documentation
tracker_refs: []
---

# Work Package Prompt: WP03 – Changelog and docs freshness

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission issue-6328-code-producing-review-gate-01M68ZQ1`) and address every item before handing back.

## Objectives & Success Criteria

Record the user-facing change in one `[Unreleased]` changelog entry and verify the docs
surfaces this diff touches are fresh.

Done means:

- `docs/changelog/CHANGELOG.md` has one new `-` bullet under `[Unreleased]`, bold
  impact-first lead, ending with `(#6328)`, under 1,200 characters, with an explicit
  **before / after** and a **what to do** clause.
- The entry also credits `#6327` as the capability it lands, and states in one clause
  that the `#6715`/`#5939` evidence gates are untouched.
- `uv run python -m scripts.docs.check_docs_freshness --ci` reports `errors=0`.

## Context

**Spec**: `kitty-specs/issue-6328-code-producing-review-gate-01M68ZQ1/spec.md`.
**Plan**: plan.md § IC-03.

`docs/changelog/CHANGELOG.md` is the real file; the root `CHANGELOG.md` is a symlink
to it — never write through the symlink, and never edit both.

### House style, read before writing

Read the existing `[Unreleased]` section and, in particular, line ~185 (`#6315`,
"two capabilities on its resolved mission type"). Your entry is the direct sequel to
that one and should read as its continuation: same voice, same **Before:** /
**After:** / **What to do:** rhythm, same "behave as before" clause naming the four
built-ins.

Do not restate the `#6315` entry; reference the outcome, not its history.

## Detailed guidance per subtask

### T014 — The changelog entry

Shape (adapt the wording, keep the rhythm and the ordering of clauses):

```
- **A custom mission type that produces code can no longer reach review with nothing
  implemented** (#6328; with #6327). **Before:** …
  **After:** … **What to do:** …
```

Content the entry must carry:

1. What changed for a user/operator, first, in one sentence.
2. **Before:** the review-readiness prerequisite that asks for implementation commits
   ran only for the `software-dev` family, so an activated custom code-producing type
   passed review-readiness with an empty lane.
3. **After:** mission types carry a `code_producing` capability (`software-dev` true;
   `research`, `documentation`, `plan` false; an undeclared custom type false) and the
   prerequisite reads it, so a custom code-producing type is refused and names the
   missing commits; `research`, `documentation` and `plan` behave exactly as before.
4. **What to do:** a custom type that produces code declares `code_producing: true` in
   its mission-type descriptor; a custom type that produces no code declares nothing
   and keeps its current flow.
5. One clause making the negative claim explicit: the `#6715`/`#5939` evidence gates
   are unchanged.

Keep it under 1,200 characters (the repo's convention for these entries). Count it.

Do **not** touch any other `[Unreleased]` entry. If the file has other agents' entries
in your working tree, leave them exactly as they are (the brief's shared-machine rule
applies to the changelog too: append, never reorder).

### T015 — Docs freshness

```bash
uv run python -m scripts.docs.check_docs_freshness --ci
```

Expected `errors=0`. If it reports an error on a surface this diff changes, fix it.
If it reports an error on a surface this diff does **not** change, do not regenerate
the whole reference (the installed CLI's global asset cache is shared with other
agents running concurrently and a full rebuild is non-deterministic here): record the
error verbatim, name the surface, and put it in the hand-off so the PR body can cite
it under `## Deferred` with the reason.

Also run the terminology gate if you touched any user-facing prose:

```bash
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
```

## Out of scope — do not do these

- Do **not** edit `src/` or `tests/` — WP01 and WP02 own those.
- Do **not** add an ADR. This is a capability addition with an existing precedent
  (`#6315`), not a new architectural boundary.
- Do **not** hand-write `docs/api/cli-commands.md`. If it needs regenerating, use the
  script and verify with the freshness check; a partial, verifiable regeneration beats
  a churny full one.

## Definition of Done

- [ ] One `[Unreleased]` bullet exists, ends with `(#6328)`, and is under 1,200
      characters (state the count in the hand-off).
- [ ] The bullet names `#6327`, states before/after/what-to-do, and says the
      `#6715`/`#5939` gates are unchanged.
- [ ] No other `[Unreleased]` entry was reordered or reworded.
- [ ] `check_docs_freshness --ci` result captured verbatim in the hand-off.
- [ ] `tests/architectural/test_no_legacy_terminology.py` green (or the failure
      recorded with its reason).

## Risks & reviewer guidance

- **Character budget.** These entries are read in release notes; the house limit is
  1,200 characters. A reviewer should check the count, not the intent.
- **Symlink.** `CHANGELOG.md` at the repo root links to `docs/changelog/CHANGELOG.md`;
  editing the wrong one produces a commit nobody can review.
- **Shared-cache churn.** A full `docs/api/cli-commands.md` rebuild reads the installed
  CLI's global asset cache, which other agents rewrite concurrently. Prefer the
  freshness check over a rebuild, and report rather than chase a non-deterministic
  diff.
