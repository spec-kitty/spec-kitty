---
work_package_id: WP04
title: Record the justified budget and tell users what improved
dependencies:
- WP02
requirement_refs:
- FR-006
- SC-005
planning_base_branch: issue-6506-charter-write-roundtrip-latency
merge_target_branch: issue-6506-charter-write-roundtrip-latency
branch_strategy: Planning artifacts for this mission were generated on issue-6506-charter-write-roundtrip-latency. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6506-charter-write-roundtrip-latency unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
phase: Phase 4 - Documentation
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/adr/4.x/
create_intent:
- docs/adr/4.x/2026-10-31-1-charter-write-budget-for-repository-scale-projects.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/adr/4.x/**
- docs/adr/index.md
- docs/development/page-inventory.yaml
- docs/changelog/CHANGELOG.md
role: architect
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Record the justified budget and the user-facing change

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `architect-alphonso`
- **Role**: `architect`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this
work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log
  (`spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP04 --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

Issue #6506 asks for one of two things: bring `charter activate`/`deactivate` under the charter's
2 s CLI budget, **or record a justified budget for repositories of this size**. This mission does
the second, because at this repository's scale a *pure read* already costs more than 2 s. This
work package makes that record durable and tells users what improved.

Done means:

- an ADR states the measured read floor, the post-fix write cost, the ratio between them, the
  measurement method, and what would have to change to reach 2 s;
- a `[Unreleased]` changelog entry leads with the user-visible impact and cites `(#6506)`;
- `scripts.docs.check_docs_freshness --ci` reports `errors=0`.

## Context & Constraints

Read first:

- `kitty-specs/charter-write-roundtrip-latency-01M68ZVK/research.md` — Decision 5 states why 2 s is
  unreachable here, Decision 6 records the two prior decisions this one is consistent with.
- `docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md` — the sibling decision about
  how repository-scale performance is measured. Your ADR must be consistent with it, and should
  cite it rather than restate it.
- `.kittify/charter/charter.md`, section "Performance and Scale" — the `< 2 seconds` line, and the
  "for typical projects" wording that scopes it.

Hard constraints:

- **C-004**: do not change the charter's stated budget. That is an operator decision; this
  mission records a budget for a *different* repository size band, it does not renegotiate the
  existing one.
- Keep the changelog entry under 1,200 characters, bold impact-first lead, cite `(#6506)`, with
  before/after.
- Regenerate **only** the docs surfaces this ADR touches (see the shared-machine warning below).

## Branch Strategy

- **Strategy**: single-lane mission on the mission branch.
- **Planning base branch**: `main`
- **Merge target branch**: `main`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change manually.

## Subtasks & Detailed Guidance

### Subtask T010 – The ADR

- **Purpose**: Give the next engineer the numbers instead of a shrug, and record the two
  alternatives that were considered and rejected so they are not re-litigated.
- **Steps**:
  1. Create `docs/adr/4.x/2026-10-31-1-charter-write-budget-for-repository-scale-projects.md`
     (confirm the number is still free at implementation time; if taken, take the next free `-N`
     for that date and update `create_intent` accordingly).
  2. Frontmatter matching the sibling ADRs: `title`, `description`, `status: Accepted`, `date`,
     `updated`.
  3. Body sections, in the shape the other 4.x ADRs use: **Status**, **Date**, **Deciders**,
     **Technical Story** (link #6506 and the mission), **Context and Problem Statement**,
     **Decision**, **Considered Options**, **Consequences**, and a short **Calibration** section.
  4. Content the ADR must carry:
     - the command medians measured before the fix and after, on a project seeded from this
       repository's own `.kittify/`, with the fixture's shape stated (165 KB / 1,937-line
       `charter.yaml`, 264 catalog references);
     - the **read floor** (`charter list`) measured in the same run, and the observation that the
       floor alone exceeds 2 s at this scale;
     - the resulting budget statement: what a command that recompiles and rewrites the compiled
       charter is allowed to cost, expressed as a ratio over the read floor (this is what the
       committed test asserts) plus the absolute figure observed for context;
     - the measured whole-document round trips per refresh, before (10) and after (2), and that
       this is the structural property the other committed test pins;
     - **what would have to change to reach 2 s**: an incremental catalog update instead of a full
       recompile (cite the changelog note under `#4785` that already accepts a ~2.4-2.5 s
       recompile cost as the price of single-authority compilation), and note that this is
       explicitly out of scope here.
  5. **Considered Options** must record at least: (a) delete the two whole-document equality
     checks — rejected, they are the no-op-bytes guarantee and the alias guard; (b) raise the
     charter's 2 s budget — rejected, it is an operator-owned governance statement and it is
     correct for typical projects; (c) assert an absolute seconds budget in the test — rejected by
     `2026-10-05-2`; (d) incremental catalog update — rejected as out of scope, filed separately if
     the operator wants it.
  6. Every number must be re-derivable from the committed tests' reported values (WP03's ratio
     test reports the floor median, the command median and the ratio). If a number can only come
     from a throwaway profile, say where it came from and that it is a one-off measurement.
- **Files**: the new ADR file.
- **Notes**: Write for someone who asks "why is this 9 s and not 2 s?" — answer that question
  directly in the Decision section, first.

### Subtask T011 – Changelog and generated docs surfaces

- **Purpose**: Users must learn what improved, and the docs index must stay fresh.
- **Steps**:
  1. Add one `[Unreleased]` entry to `docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a
     symlink to it — do not create a second file). Shape: a **bold impact-first lead** ending in
     `(#6506)`, then **Before:** / **After:**, under 1,200 characters. Cover that
     `charter activate`/`deactivate` did far less redundant document work, that the output is
     byte-identical, and that `charter generate`, skill rendering and skill installation share the
     cheaper document comparison. Do not claim a specific millisecond figure as a promise; quote
     the measured before/after honestly and attribute it to repository scale.
  2. Regenerate only what the new ADR needs:
     ```bash
     uv run python -m scripts.docs.freshen_adr_inventory
     uv run python -m scripts.docs.docs_index --write
     ```
     Then verify — do not trust the rebuild:
     ```bash
     uv run python -m scripts.docs.check_docs_freshness --ci   # expect errors=0
     ```
  3. Run `uv run pytest tests/architectural/test_no_legacy_terminology.py -q` and the docs tests
     that guard the changelog shape, if any exist (`rg -l 'changelog' tests/architectural/`).
- **Files**: `docs/changelog/CHANGELOG.md`, `docs/development/page-inventory.yaml`,
  `docs/adr/index.md`, `docs/adr/4.x/index.md` (whichever the generators actually change).
- **Notes**: **Shared machine warning.** Twenty other agents are working in their own clones on
  this host, and the docs-surface regenerators read the *installed* CLI's global asset cache. If a
  regenerated file changes in ways that have nothing to do with your ADR, do **not** commit that
  churn: revert the unrelated hunks, say so in your WP history note, and mention it in the PR's
  `## Deferred`. A partial, verifiable regeneration beats a churny full one. If you need an
  isolated cache, set `XDG_CACHE_HOME="$PWD/.cache-agent"` for your own commands.

## Test Strategy

```bash
uv run python -m scripts.docs.check_docs_freshness --ci     # expect errors=0
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
uv run pytest tests/docs/ -q
```

## Risks & Mitigations

- **A budget nobody can re-measure.** Every figure must point at the committed test that re-derives
  it, or be labelled a one-off measurement with its method.
- **Changelog over the length limit** or missing the `(#6506)` reference — the docs gates check
  this.
- **Generated-surface churn** from the shared machine — see the warning above.

## Review Guidance

- Does the ADR answer "why 9 s and not 2 s?" without hedging, and without implying the 2 s budget is
  wrong?
- Is every figure traceable to a committed test or an explicitly labelled one-off measurement?
- Are the rejected options stated with their real reasons (not strawmen)?
- Changelog: impact-first, under 1,200 characters, cites #6506, has before/after.
- No unrelated generated-doc churn in the diff.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP04 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP04 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
