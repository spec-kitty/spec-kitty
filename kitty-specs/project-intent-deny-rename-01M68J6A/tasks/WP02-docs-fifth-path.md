---
work_package_id: WP02
title: Document the fifth deny-list path
dependencies:
- WP01
requirement_refs:
- FR-006
planning_base_branch: kitty/mission-project-intent-deny-rename-01M68J6A
merge_target_branch: kitty/mission-project-intent-deny-rename-01M68J6A
branch_strategy: Planning artifacts for this mission were generated on kitty/mission-project-intent-deny-rename-01M68J6A. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/mission-project-intent-deny-rename-01M68J6A unless the human explicitly redirects the landing branch.
created_at: '2026-10-31T08:50:00+00:00'
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Contract docs
history:
- at: '2026-10-31T08:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md
- docs/api/charter-commands.md
- docs/changelog/CHANGELOG.md
- AGENTS.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6565'
---

# Work Package Prompt: WP02 – Document the fifth deny-list path

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission project-intent-deny-rename-01M68J6A`).
- Address every feedback item before declaring the work complete, and record each with `spec-kitty tasks add-history WP02 --note "..."`.

---

## Objective

WP01 made the project-intent rename carry a deny entry, through one new sanctioned
`DenyListChoice.RENAME` (`#6565`). The contract documents still say four paths may change a deny
list, and the issue's operator ruling was explicitly "document this and follow up". Bring the
normative text in line with the code, and state the new path's **limit**: it moves one entry between
two spellings of the same artifact; it never adds or removes a denial.

Read WP01's diff first (`git log -p --follow -- src/charter/activation/synthesizer/legacy_rename.py`)
and quote the real code, not the plan.

## Files you own

`docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md`,
`docs/api/charter-commands.md`, `docs/changelog/CHANGELOG.md`, `AGENTS.md`. Nothing under `src/` or
`tests/` (WP01 owns those). Do not touch `docs/api/cli-commands.md` (generated).

---

## T007 — ADR `2026-10-19-1`: Decision 4 gains a fifth, narrowing path

In `docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md`, Decision 4:

1. Change "Four paths, and no others, may add to or remove from a `deactivated_<plural>` list" to
   name five paths, and add the row to the table:

   | Path | Effect on the deny-list |
   |---|---|
   | the project-intent rename (`#6443`, `#6565`) | moves an entry from `NNN-mission-type-scope-directive` to `NNN-project-intent-directive` when it runs (`charter synthesize`, `charter resynthesize`, `spec-kitty upgrade`) |

2. Keep the existing paragraph about presets/interview/promotion/seeding intact, and add the
   narrowing sentence: the rename adds and removes **nothing**; it rewrites the id the user's own
   `charter deactivate` recorded, so the same artifact stays excluded. It runs only on the activation
   ledger — a hand-written legacy deny key on `charter.yaml` / `config.yaml` is left where it is.
   It runs only when a legacy stem is present, so a project that never had one performs no deny
   write.
3. Extend the guard paragraph: the choices are now `activate`, `deactivate`,
   `cascade-include-deactivated`, `preset-force` and `rename`; the gate pins each origin exactly, and
   since the rename's allowance would otherwise be vacuous, the gate carries a positive control that
   the rename does carry an entry (and only that entry).
4. Add a dated amendment at the end, in the file's existing style (an `## Amendment 2026-10-31
   (#6565): the rename carries an exclusion` section after the last amendment): the operator ruling
   of 2026-10-21 (document and follow up), why "refuse the rename" was rejected (it would break
   `charter synthesize` and ask the user to clear state they cannot see), the narrow window the bug
   needs (a refused or skipped rename — `#6539` — then a deny, then a retry), and that `#6539` stays
   unfixed because this makes it harmless.

Update the front-matter `updated:` date and the "amended" line in the status block to include
`2026-10-31`.

## T008 — `AGENTS.md` and `docs/api/charter-commands.md`

`AGENTS.md`, "Activation Ledger" bullet "**Only explicit choices change a deny list**": keep the
sentence that presets without `--force`, the interview, promotion, synthesis and migrations never do,
and add the exception in the same bullet — the project-intent rename (`#6443`, `#6565`) rewrites the
legacy stem of the project-intent directive in the deny list too, through `DenyListChoice.RENAME`,
moving the entry and never adding or removing a denial. The same bullet's `DenyListChoice.*` list
gains `rename`.

`docs/api/charter-commands.md`, in "Activation and the activation ledger" (near the
`deactivated_<kind>` note) or immediately after the `charter deactivate` subsection, add a short
paragraph: a deactivation stays with its artifact when the project-intent directive is renamed
(`spec-kitty upgrade`, `charter synthesize`, `charter resynthesize`); the exclusion is moved to the
new stem in the same write as the allow list, so you do not need to deactivate it again. Mention that
an id you spell as a declared id (`DIRECTIVE_003`) is not renamed (only the legacy stem is).

## T009 — Changelog `[Unreleased]` entry and docs freshness

`docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink to it), under `[Unreleased]`,
following the neighbouring entries' shape: a bold impact-first lead with `(#6565)`, then
**Before:** / **After:**, under 1,200 characters for the entry. Content: before — a project whose
denial named the old `mission-type-scope-directive` stem silently lost that deactivation when the
rename ran, and the directive came back into force; after — the rename carries the exclusion to
`project-intent-directive` in the same write, reports it, and leaves every other deny entry alone.

Then verify the docs surface:

```bash
uv run python -m scripts.docs.check_docs_freshness --ci     # expect errors=0
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
```

Do **not** run `scripts.docs.docs_index --write` or any full CLI-reference rebuild: this change adds
no doc page and no ADR, and the global asset cache on this host is shared with other missions.

## Definition of Done

- [ ] Decision 4 names five paths; the fifth is described as narrowing in one sentence a reviewer can
      check against the code.
- [ ] The dated amendment records the ruling, the rejected alternative and the narrow window.
- [ ] `AGENTS.md` and `docs/api/charter-commands.md` agree with Decision 4 word-for-word on the limit.
- [ ] The changelog entry is impact-first, cites `(#6565)`, has before/after, and is under 1,200
      characters.
- [ ] `check_docs_freshness --ci` reports `errors=0`; `test_no_legacy_terminology.py` passes.
- [ ] No `src/` or `tests/` edit, no `docs/api/cli-commands.md` edit.

## Reviewer guidance

Diff the wording against WP01's code: does every claim in the ADR and the docs have a matching
predicate (ledger only, legacy stem only, one write, entry moved not cleared)? Is there any sentence a
reader could take as "synthesis may now clear a denial"? Is the changelog entry user-facing rather
than implementation-facing?
