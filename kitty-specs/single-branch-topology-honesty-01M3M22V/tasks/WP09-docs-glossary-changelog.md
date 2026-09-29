---
work_package_id: WP09
title: Truthful docs, glossary and changelog
dependencies:
- WP08
requirement_refs:
- FR-023
planning_base_branch: issue-5100-single-branch-topology
merge_target_branch: issue-5100-single-branch-topology
branch_strategy: Planning artifacts for this mission were generated on issue-5100-single-branch-topology. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5100-single-branch-topology unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-single-branch-topology-honesty-01M3M22V
base_commit: b1d397061491858776902e2ea97355cb3d50457d
created_at: '2026-09-29T09:58:07.363509+00:00'
subtasks:
- T039
- T040
- T041
phase: Phase 8 - Docs
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- docs/context/topology.md
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- CLAUDE.md
- docs/architecture/execution-lanes.md
- docs/context/topology.md
- docs/context/orchestration.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – Truthful docs, glossary and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `scribe-sally` (role `implementer`, agent `claude`), then follow the profile's guidance.

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log for `review_ref`. If there is feedback, address every item.

---

## Objectives & Success Criteria

FR-023: docs must mirror shipped behaviour. The charter's rule is that code is the source of truth and a doc/code disagreement is a doc defect.

1. **CLAUDE.md**, "Execution Workspace Strategy (2.x)" section. It currently says flat / `SINGLE_BRANCH` / `LANES` missions all require `lanes.json` and resolve `.worktrees/<feature>-lane-<id>`. Correct it:
   - `single_branch` has a one-lane repo-root manifest.
   - Every WP of a `single_branch` mission runs sequentially in the write checkout, stamped `execution_mode: direct_repo`.
   - A protected target gets a create-time mission branch.
   - `--commit-to-target` opts out.
   - The `lanes` default applies on non-primary branches.
   - Mention the lane work-tip refs (`refs/spec-kitty/lane-tip/*`) and the restore command.
2. **`docs/architecture/execution-lanes.md:39-41`.** It claims SINGLE_BRANCH requires computed lanes. Correct it to the same facts.
3. **Topology glossary entry.** Create `docs/context/topology.md`, or add a `#topology` section to `docs/context/orchestration.md` and link it from there. The entry defines:
   - the four topologies;
   - write checkout;
   - repo-root lane;
   - code lane;
   - protected target;
   - mission branch;
   - lane work tip;
   - absorbed lane;
   - execution-mode stamp versus work-product kind.

   Each term gets a "Do NOT use when" guard, in the style of the existing `primary`/`merge`/`routing` entries.
4. **CHANGELOG.** Add an `[Unreleased]` entry in `docs/changelog/CHANGELOG.md`. Each line leads with a bold, impact-first phrase and the issue number, then states before → after. Cover:
   - #5100: single_branch really has no lanes;
   - #2602 / #4828: the create default is `lanes`, and single_branch-direct is available;
   - #5115: the destroyed-lane guard covers lanes and flat missions, and stranded work is restorable;
   - the migration notes: the re-stamp migration, the recorder hook install, and `SINGLE_BRANCH_CODE_LANES_UNMIGRATED`.

**Done when**:
- `scripts/docs/docs_index.py --write` has been run, if a new page was added.
- `scripts/docs/check_docs_freshness.py --ci` reports errors=0.
- `tests/architectural/test_no_legacy_terminology.py` passes.
- The docs structural and SEO gates pass for the new page.

## Context & Constraints

- **Read first:**
  - `spec.md`, especially the Domain Language table, which is the source for the glossary.
  - `data-model.md` and `contracts/*.md`.
  - The shipped code from WP02–WP08. Read the actual flag names and error codes from the code, not from the plan.
  - The existing glossary style in `docs/context/orchestration.md`.
- **Divio discipline.** A glossary entry is a Reference page. It needs frontmatter (`title`, `description`, `doc_status`, `updated: 2026-09-28`) as other `docs/context/` pages have. Copy the frontmatter keys an existing page uses.
- **Terminology canon.**
  - Say "mission", never "feature".
  - Say "repository root checkout", never "main repository".
  - Name the sense whenever you write "primary", "merge" or "routing".
  - Never use `main` as a generic branch name.
- **CLAUDE.md.** Keep edits to the Execution Workspace Strategy section plus any one-line pointers. Do not restructure the file.

## Branch Strategy

- **Planning base / merge target:** `issue-5100-single-branch-topology`.
- Run `spec-kitty implement WP09 --mission single-branch-topology-honesty-01M3M22V`.

## Subtasks & Detailed Guidance

**Red-first exemption (charter C-011; analysis finding C2).** This WP changes documentation only. Its proof is the docs freshness, SEO and structural gates plus the terminology gate, all run and recorded.


### Subtask T039 – CLAUDE.md and execution-lanes.md

1. Rewrite the affected bullets precisely.
2. Search both files for "SINGLE_BRANCH" and "single_branch" and fix every mention that is now false.
3. Also search `docs/` for "single_branch on a non-primary" and the old default wording, using the leftovers noted by WP06. Fix each hit with a minimal edit. An edit outside the owned files needs a one-line rationale.

### Subtask T040 – Topology glossary entry

1. Write the entry as described above.
2. Add an anchor link from `docs/context/orchestration.md#routing`, or wherever topology is mentioned.
3. Run `scripts/docs/docs_index.py --write` if the page is new.

### Subtask T041 – CHANGELOG and gates

1. Add the entry. Union with existing `[Unreleased]` content; do not reorder other entries.
2. Run the gates:

```bash
.venv/bin/python scripts/docs/docs_index.py --write
.venv/bin/python scripts/docs/check_docs_freshness.py --ci
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
.venv/bin/python -m pytest tests/docs/test_description_length_gate.py tests/docs/test_docs_seo.py tests/docs/test_docs_structural_lint.py -q
```

## Risks & Mitigations

- **Stale claims.** Verify every sentence against the merged code on this branch.
- **Freshness gate.** Set `updated:` on every page you touch.

## Review Guidance

- Each changed sentence matches the code.
- Each glossary term has a "Do NOT use when" guard.
- The CHANGELOG is impact-first and carries the issue numbers.
- All gate commands and counts are recorded.

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
