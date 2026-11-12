---
work_package_id: "WP06"
title: "Documentation close-out: changelog fragment and CLAUDE.md"
dependencies: ["WP05"]
requirement_refs: ["C-003", "NFR-006"]
subtasks: ["T029", "T030", "T031"]
owned_files: ["docs/changelog/unreleased/7578.*.md", "CLAUDE.md"]
authoritative_surface: "docs/changelog/unreleased/"
execution_mode: "code_change"
agent_profile: "scribe-sally"
role: "documentarian"
agent: "claude"
model: ""
---

# WP06: Documentation close-out: changelog fragment and CLAUDE.md

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `documentarian`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Record the shipped behaviour of Mission `review-context-wp-diff-01M774QF` (#7578) for users and
maintainers: one changelog fragment set under `docs/changelog/unreleased/7578.*.md` and a short
extension of the CLAUDE.md "Work-package windows (#7403)" paragraph. Then run the final quality
sweep over the whole Mission diff (NFR-006) and draft, without filing, the
`spec-kitty-open-packs` follow-up for the stale review-template wording (C-003).

Implementation command:

```bash
spec-kitty agent action implement WP06 --agent claude --mission review-context-wp-diff-01M774QF
```

## Context

- **Why this WP exists.** Plan concern IC-07 ("Documentation and close-out") requires a changelog
  fragment, one CLAUDE.md sentence-level update on commit-to-target stamping and on the review
  range, and an `spec-kitty-open-packs` follow-up for template wording that this Mission makes
  stale. The ADR `2026-11-08-2` amendment (C-008) ships with IC-02 in an earlier WP; this WP does
  not edit the ADR.
- **What it depends on.** WP05 (the shared renderer and the retirement of the old pathspec
  builders). Every behaviour this WP describes must already be on the Mission branch. Before you
  write a sentence, confirm the module and behaviour it names exist in the tree:
  - `src/specify_cli/status/wp_window_selector.py` (the moved FR-021 window-opener rule, IC-01);
  - `src/specify_cli/review/wp_range.py` (`resolve_wp_review_range` -> `WpReviewRange`, IC-03),
    whose `owned_pathspecs` is the one owner of the review pathspecs;
  - `src/specify_cli/review/context_block.py` (`render_review_context`, IC-05), called by
    `src/runtime/next/prompt_builder.py` and by `workflow_executor.py` (both review entry points);
  - `src/specify_cli/requirement_mapping/text.py` (`resolve_requirement_texts`, IC-04);
  - `src/specify_cli/status/lane_head.py` (commit-to-target `single_branch` reading, IC-02).
  If any of these is missing or named differently, describe what actually shipped and report the
  drift to the orchestrator. Docs mirror shipped behaviour only.
- **Key design decisions (plan.md, research.md).**
  - The review range runs from the window open (the same FR-021 window-opener rule consolidation
    uses) to the newest `for_review` `lane_head` stamp (R1, rulings Q2/Q3). It is bounded above.
  - The prompt shows provenance, implementation commits, a per-file change summary scoped to the
    work package's owned files with an out-of-map warning line, and the exact `git log` /
    `git diff` commands. It never inlines patch text and writes no diff file (C-001, ruling Q1).
  - When the range cannot be determined, the prompt prints an `unavailable` notice naming why and
    the review still proceeds (FR-013, NFR-004).
  - Cited requirement text comes from the canonical declaration parser (R6).
  - Commit-to-target `single_branch` Missions now record the window-open and submission points
    (the write checkout's target head); such Missions stay out of the approval-stamp and
    write-branch bounds (R3, C-008). Planning lanes still record no window (C-009).
  - No new gate, refusal code or exit code (C-002).
- **Constraints that bind this WP.**
  - C-003: no edit under `packs/built-in/`. Stale template wording is filed upstream in
    `spec-kitty-open-packs`, and in this WP only drafted.
  - No edit of `docs/changelog/CHANGELOG.md`; fragments only.
  - Terminology canon: "Mission", "work package"; never "feature". Never bare "routing",
    "primary", "merge" or "residue"; never "sync" for this behaviour.
  - Owned files are exactly `docs/changelog/unreleased/7578.*.md` and `CLAUDE.md`. Anything T031
    finds outside them is reported, not fixed.

### Subtask T029: Changelog fragment(s)

**Purpose**: give users a plain-language, user-facing entry for #7578 that the release assembles
into `## [Unreleased]`.

**Steps**:

1. Read `docs/changelog/unreleased/README.md` again for the name grammar `<id>.<section>.md` and
   the allowed sections (`breaking`, `upgrade-notes`, `added`, `changed`, `fixed`, `internal`).
   Look at one existing fragment (e.g. `7159-implement-claim-profile.fixed.md`) for style: a single
   bullet, bold lead, issue number in parentheses, optional **Before:** / **After:**.
2. Pick the section(s). Recommended split, one file per section:
   - `docs/changelog/unreleased/7578.added.md`: the review prompt now carries the work package's
     own review range and the text of cited requirements.
   - `docs/changelog/unreleased/7578.changed.md`: commit-to-target `single_branch` Missions now
     record window points.
   A single `7578.added.md` holding both bullets is not allowed if one of them is a change; keep
   one section per file. If you judge both are best under one section, use one file.
3. Write the review-prompt entry. It must cover, in plain language:
   - both entry points (`spec-kitty agent action review` and the `spec-kitty next` review step)
     show the same review-context block;
   - the block states the work package's own review range and where each end came from
     (provenance), lists the implementation commits, gives a per-file change summary scoped to the
     work package's owned files, warns about changed paths outside the ownership map, and prints
     the exact `git log` / `git diff` commands for that range;
   - the diff itself is not inlined and no diff file is written; the reviewer runs the commands;
   - when the range cannot be determined, the prompt says so and why, and review proceeds;
   - the declared text of every requirement the work package cites is shown, so the reviewer
     does not re-read `spec.md` to find it.
   A **Before:** / **After:** form fits well: before, the reviewer reconstructed the range by hand
   (an empty `<base>..HEAD` on `single_branch`, or an unbounded one on lanes).
4. Write the window-recording entry: commit-to-target `single_branch` Missions now record the
   window-open and submission points on status events, so the review range is recorded on every
   topology; name ADR `2026-11-08-2` (amendment). State the consolidation effect only as the ADR
   amendment records it (read the amendment; do not invent verdict changes). Planning-lane work
   packages still record no window.
5. Name `#7578` in each bullet. Use "Mission" and "work package"; never "feature".
6. Run the style and spelling checks:
   ```bash
   uv run --frozen python -m scripts.docs.check_changelog_style
   uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
   uv run --frozen python -m scripts.release.changelog_fragments assemble   # preview only, no --write
   ```

**Files**: `docs/changelog/unreleased/7578.added.md` (~1 bullet, 3-6 lines),
`docs/changelog/unreleased/7578.changed.md` (~1 bullet, 2-4 lines).

**Validation**:
- Both checkers pass with no finding at the fragment lines.
- `assemble` (without `--write`) shows the bullets under the right `###` headings.
- `git diff --stat` shows no change to `docs/changelog/CHANGELOG.md`.
- Every claim in the bullets is traceable to code that exists on the branch.

### Subtask T030: Extend the CLAUDE.md "Work-package windows (#7403)" paragraph

**Purpose**: keep the maintainer-facing CLAUDE.md accurate about where the window is recorded and
who reads it.

**Steps**:

1. Locate the paragraph that starts `**Work-package windows (#7403).**` in `CLAUDE.md` (in the
   "Consolidation & Preflight Patterns" section). Do not move, split or reformat it.
2. Append 2-3 sentences, before the closing `ADR docs/adr/4.x/2026-11-08-2-...` reference (so the
   ADR citation stays last), in the paragraph's existing style (dense, backticked module paths,
   issue numbers in parentheses). Content:
   - commit-to-target `single_branch` Missions are now stamped too (the write checkout's target
     head, `status/lane_head.py`), and stay out of the approval-stamp and write-branch bounds
     (ADR `2026-11-08-2` amendment, #7578);
   - the review range (`specify_cli/review/wp_range.py`) reuses the same window rule
     (`status/wp_window_selector.py`; `consolidation/wp_attribution.py` re-exports it), runs to
     the newest `for_review` `lane_head`, and is the single owner of the review pathspecs;
   - both review entry points (`agent action review` and the `next` review step) render through
     `review/context_block.py`; the prompt prints commands, never patch text.
   Example shape (adapt to what shipped):
   > Since #7578 a commit-to-target `single_branch` Mission is stamped as well (the write
   > checkout's target head, `status/lane_head.py`) and still stays out of the approval-stamp and
   > write-branch bounds. The review range (`specify_cli/review/wp_range.py`) reuses the same
   > window rule (`status/wp_window_selector.py`, re-exported by `consolidation/wp_attribution.py`),
   > runs to the newest `for_review` `lane_head` and is the single owner of the review pathspecs;
   > both review entry points render it through `review/context_block.py`, with commands and no
   > patch text.
3. No other CLAUDE.md edit: no new section, no other paragraph touched, no wording cleanup
   elsewhere (even if you see drift; report it instead).
4. Run the terminology guard: `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`.

**Files**: `CLAUDE.md` (+2-3 sentences in one paragraph).

**Validation**:
- `git diff CLAUDE.md` touches exactly one line (the paragraph is a single line).
- Every module path named exists: `ls src/specify_cli/review/wp_range.py src/specify_cli/review/context_block.py src/specify_cli/status/wp_window_selector.py`.
- No "feature", bare "routing" or "sync" introduced.

### Subtask T031: Final quality sweep and upstream follow-up draft

**Purpose**: prove NFR-006 holds across the whole Mission diff, and hand the orchestrator the
`spec-kitty-open-packs` issue text (C-003).

**Steps**:

1. Compute the Mission diff file list against the landing base (the branch this Mission lands on,
   `feat/7578-review-context`, or its merge-base with the Mission branch):
   ```bash
   BASE=$(git merge-base HEAD feat/7578-review-context)
   git diff --name-only "$BASE"..HEAD > /tmp/wp06-changed.txt   # or your scratchpad
   ```
2. Lint and format (formatter needs `--force-exclude` for per-file invocation):
   ```bash
   uv run --frozen ruff check $(grep '\.py$' /tmp/wp06-changed.txt)
   uv run --frozen ruff format --check --force-exclude $(grep '\.py$' /tmp/wp06-changed.txt)
   ```
3. Type check the changed source modules (strict per NFR-006):
   ```bash
   uv run --frozen mypy --strict $(grep '^src/.*\.py$' /tmp/wp06-changed.txt)
   ```
   Also confirm no new `# noqa` / `# type: ignore` was added:
   `git diff "$BASE"..HEAD -- src | grep -E '^\+.*(# noqa|# type: ignore)'` (expect nothing, or only
   individually justified ones with an inline rationale).
4. Complexity: `uv run --frozen ruff check --select C901 $(grep '^src/.*\.py$' /tmp/wp06-changed.txt)`
   must report nothing (ceiling 15).
5. Terminology: `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`.
6. Confirm C-003: `git diff --name-only "$BASE"..HEAD -- packs/` is empty, and
   `git diff --name-only "$BASE"..HEAD -- docs/changelog/CHANGELOG.md` is empty.
7. Report every finding to the orchestrator with file, line and owning WP. Do **not** edit any
   file outside `owned_files`.
8. Draft (do not file) the `spec-kitty-open-packs` follow-up. The stale wording is in
   `packs/built-in/missions/mission-steps/software-dev/review/prompt.md` around lines 222-232
   (the review checklist):
   - item 5 ("Frozen surface") gives the recipe `git log --oneline <base>..HEAD -- <frozen-file>`;
     `<base>..HEAD` is empty on `single_branch` and unbounded above on lanes, which is the failure
     #7578 fixed in core;
   - item 6 ("Locked decision") and item 4 ("FR coverage") lead the reviewer to re-read
     `spec.md` / `plan.md` for requirement and constraint text that the review-context block now
     carries.
   Suggested issue text (refine against the shipped block format in
   `kitty-specs/review-context-wp-diff-01M774QF/contracts/review-context-block.md`):
   > **Title:** software-dev review prompt: use the review-context block's range and requirement text
   >
   > Core #7578 (spec-kitty) adds a review-context block to both review entry points: the work
   > package's own review range (window open to newest `for_review` lane head), its implementation
   > commits, a per-file summary scoped to owned files with an out-of-map warning, the exact
   > `git log` / `git diff` commands, and the declared text of every cited requirement.
   > `missions/mission-steps/software-dev/review/prompt.md` (checklist items 4-6, ~lines 222-232)
   > still tells the reviewer to run `git log --oneline <base>..HEAD -- <frozen-file>` and to
   > re-read `spec.md` / `plan.md`. `<base>..HEAD` is empty on `single_branch` and unbounded on
   > lane topologies. Proposed change: point those items at the range and commands printed in the
   > review-context block (append `-- <frozen-file>` to the printed `git log`), and at the cited
   > requirement text it carries; keep `spec.md` / `plan.md` reads for clauses the work package
   > does not cite. After release, bump the core pin with `spec-kitty charter pack vendor`.
   Put this text in the WP completion note (the `for_review` move reason or the review handoff),
   for the orchestrator to file.

**Files**: none (sweep and draft only).

**Validation**: every command above was run; results (pass or findings) and the draft issue text
are in the completion note.

## Definition of Done

- T029: `docs/changelog/unreleased/7578.<section>.md` file(s) exist, user-facing, plain language,
  name #7578, use "Mission", pass `check_changelog_style` and `check_spelling --pass unreleased`;
  `CHANGELOG.md` unchanged. Recorded with
  `spec-kitty agent tasks mark-status T029 --status done`.
- T030: the CLAUDE.md "Work-package windows (#7403)" paragraph carries 2-3 new sentences naming
  commit-to-target stamping, `review/wp_range.py`, `status/wp_window_selector.py` and
  `review/context_block.py`; no other CLAUDE.md change; terminology guard green. Recorded with
  `spec-kitty agent tasks mark-status T030 --status done`.
- T031: ruff check, ruff format (`--force-exclude`), `mypy --strict`, C901 and the terminology
  guard run over the Mission diff, with results and any findings reported; no `packs/` change;
  the `spec-kitty-open-packs` draft is in the completion note. Recorded with
  `spec-kitty agent tasks mark-status T031 --status done`.
- Only `owned_files` are modified by this WP's commits.

## Risks

- **Docs describe planned rather than shipped behaviour.** Mitigation: verify each named module
  and behaviour on the branch before writing; prefer the code and ADR amendment over plan prose.
- **Overstating the consolidation effect of commit-to-target stamping.** Mitigation: copy the
  verdict statement from the ADR `2026-11-08-2` amendment only.
- **Fragment name collision or wrong section.** Mitigation: the README grammar; `assemble` preview.
- **Sweep findings in other WPs' files tempt a fix.** Mitigation: report only; the owning WP fixes.
- **CLAUDE.md paragraph churn.** The paragraph is one long line; an editor reflow would rewrite it.
  Mitigation: append in place and check `git diff CLAUDE.md` is a one-line change.

## Reviewer Guidance

- Docs mirror shipped behaviour only: spot-check each claim in the fragment and the CLAUDE.md
  sentences against the code on the branch.
- No edit under `packs/built-in/` (C-003); no edit of `docs/changelog/CHANGELOG.md`.
- CLAUDE.md diff is confined to the "Work-package windows (#7403)" paragraph, keeps its style and
  keeps the ADR citation last.
- Terminology canon: "Mission", "work package"; no "feature", bare "routing" or "sync".
- The completion note carries the T031 command results and the drafted `spec-kitty-open-packs`
  issue text; nothing was filed by this WP.
