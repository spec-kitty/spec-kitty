---
work_package_id: WP01
title: Vendor the pin and repoint the curated DRG edge
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-001
- NFR-003
- C-001
- C-003
- SC-001
- SC-003
planning_base_branch: issue-6693-red-main-refs-to-directive
merge_target_branch: issue-6693-red-main-refs-to-directive
branch_strategy: Planning artifacts for this mission were generated on issue-6693-red-main-refs-to-directive. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6693-red-main-refs-to-directive unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundation
history:
- at: '2026-10-30T17:55:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/drg/migration/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- packs/built-in.source.yaml
- packs/internal.source.yaml
- src/charter/offering/drg/migration/extractor.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Vendor the pin and repoint the curated DRG edge

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission issue-6693-red-main-refs-to-directive-01M66YZX`) and address every item before handing back.

## Objectives & Success Criteria

- Both pin lockfiles name `72cb7dbcba69efa608327be9921d915f435d1565` (the
  `spec-kitty-open-packs` merge commit of PR #74). Spec FR-001, C-003.
- The fetched trees are the source of the doctrine change: after `make sync-packs`,
  `packs/built-in/directives/red-main-release-discipline.directive.yaml` exists and
  `packs/built-in/procedures/red-main-release-discipline.procedure.yaml` does not.
  Spec SC-003, NFR-001.
- The curated `DIRECTIVE_030` edge in `_CURATED_ARTIFACT_EDGES` targets
  `directive:RED_MAIN_RELEASE_DISCIPLINE`, so pure regeneration produces exactly the
  shipped built-in graph (346 → 345 node count is what the *broken* state produced;
  the fixed state must match the shipped inventory again). Spec FR-002, NFR-003.
- **No tracked file under `packs/**` other than the two `*.source.yaml` pins changes.**
  Spec NFR-001, C-001.

## Context

`spec-kitty-open-packs` PR #74 moved two rule-shaped artifacts from `procedures/` to
`directives/`:

- built-in `red-main-release-discipline` procedure → `RED_MAIN_RELEASE_DISCIPLINE` directive
- internal `spec-kitty-red-main-policy` procedure → `SPEC_KITTY_RED_MAIN_POLICY` directive

Core holds no pack content: it holds the pin lockfiles `packs/built-in.source.yaml`
and `packs/internal.source.yaml`, and `make sync-packs` fetches, digest-verifies and
places the trees (see `AGENTS.md`, "Template Source Location" and "Pack Tiers").
So the doctrine half of #6693 is a pin bump, nothing else.

Pin to `72cb7dbc`, **not** to open-packs `main` tip: the tip carries an unrelated
breaking "sanitized-shape" migration, and the diff `af1c370f..72cb7dbc` (built-in) and
`ecda7b00..72cb7dbc` (internal) is exactly the red-main move.

## Subtasks

### T001 — Vendor both pins and sync

Run from the repository root **inside `uv run`** (the globally installed CLI resolves
`packs/<pack>.source.yaml` relative to its own package directory and fails):

```bash
uv run --frozen spec-kitty charter pack vendor --pack built-in --ref 72cb7dbcba69efa608327be9921d915f435d1565
uv run --frozen spec-kitty charter pack vendor --pack internal --ref 72cb7dbcba69efa608327be9921d915f435d1565
make sync-packs
```

Expected vendor output: `Pinned packs/built-in.source.yaml to 72cb7dbc… (tree_digest …)`
and the internal equivalent. Expected sync output:
`built-in: synced 72cb7dbcba69` / `internal: synced 72cb7dbcba69`.

Do **not** hand-edit anything under `packs/built-in/` or `packs/internal/`: those trees
are untracked, digest-verified and regenerated.

### T002 — Record the red evidence before fixing anything

Run the four files named by the issue and record the exact failures in your hand-back
(the PR body's `## Tests run` needs them):

```bash
uv run --frozen pytest -q -p no:randomly \
  tests/charter_offering/drg/test_single_owner_edges.py \
  tests/charter_offering/drg/migration/test_extractor_projection.py \
  tests/charter_offering/test_testing_doctrine_single_owner.py \
  tests/integration/test_org_pack_chain_delivery.py
```

Six tests must fail, and they must fail for the *repointing* reason, not for some
unrelated breakage:

1. `test_single_owner_edges.py::test_test_first_bug_fixing_points_at_its_owners[procedure:red-main-release-discipline-requires]`
2. `test_extractor_projection.py::TestDRGZeroDelta::test_regenerated_graph_matches_baseline_counts` (`assert 346 == 345`)
3. `test_extractor_projection.py::TestDRGZeroDelta::test_shipped_graph_is_fresh_and_byte_identical` (`Extra items in the left set: 'procedure:red-main-release-discipline'`)
4. `test_testing_doctrine_single_owner.py::…::test_references_034_and_red_main`
5. `test_org_pack_chain_delivery.py::test_class_b_internal_pack_delivers_every_declared_kind` (missing `('procedure:landing-contributor-prs', 'procedure:red-main-release-discipline')`)
6. `test_org_pack_chain_delivery.py::test_class_a_second_org_pack_fragment_folds` (`DRGValidationError: Dangling target …`)

If the count or the reasons differ, **stop and report** — do not proceed on a
different red.

### T003 — Repoint the curated edge

In `src/charter/offering/drg/migration/extractor.py`, `_CURATED_ARTIFACT_EDGES`
currently contains:

```python
    (
        "directive:DIRECTIVE_030",
        "procedure:red-main-release-discipline",
        Relation.SUGGESTS,
    ),
```

Change the target to `"directive:RED_MAIN_RELEASE_DISCIPLINE"` and extend the adjacent
comment so the next reader knows why the kind moved (open-packs#74 turned the rule
into a directive; the id is unchanged). Keep the relation `SUGGESTS` — the packs ship
the same relation, so any other relation reintroduces a regeneration delta.

Check whether a nearby comment or docstring names the retired id and update it only
where it describes the live graph (not where it records history).

### T004 — Prove the regeneration delta is zero

```bash
uv run --frozen pytest -q -p no:randomly \
  tests/charter_offering/drg/migration/test_extractor_projection.py::TestDRGZeroDelta
```

Both tests must pass. Confirm the mechanism yourself rather than trusting the green:
`test_shipped_graph_is_fresh_and_byte_identical` compares a fresh extraction against
`packs/built-in/*.graph.yaml`, and `test_regenerated_graph_matches_baseline_counts`
compares node/edge totals. Before T003 the extraction emits one extra node; after it,
it must not.

## Branch Strategy

Planning branch and final merge target: `issue-6693-red-main-refs-to-directive`.
This mission is `single_branch`; the runtime allocates the workspace. **Never** choose
a base branch by hand.

## Test strategy

Only the named files. This repository's doctrine
(`NO_FULL_HEAVY_SUITES_IN_MISSION`) forbids full architectural/e2e/performance or
`make test-full` runs during mission work; CI owns those.

## Definition of Done

- [ ] Both `packs/*.source.yaml` name `72cb7dbcba69efa608327be9921d915f435d1565`.
- [ ] `make sync-packs` reports both packs synced, and the new directive file is present in the fetched built-in tree.
- [ ] `git status --porcelain -- packs` lists only the two `*.source.yaml` files.
- [ ] The curated edge names `directive:RED_MAIN_RELEASE_DISCIPLINE` with a comment explaining the kind move.
- [ ] `TestDRGZeroDelta` is green; the four failing files' remaining failures are documented in your hand-back as WP02's scope.
- [ ] Tracer entry appended via `spec-kitty agent tracer-append` for any friction found.

## Risks & Reviewer Guidance

- **Wrong pin target.** If the pin moved past `72cb7dbc` to open-packs `main`, the diff
  will contain far more than the red-main move. Reject that.
- **Hand-edited pack content.** Any changed tracked file under `packs/built-in/` or
  `packs/internal/` (other than the pins) is a defect: `make sync-packs` overwrites it
  and the digest check fails.
- **Relation drift.** Changing `Relation.SUGGESTS` on the curated edge to `REQUIRES`
  would make the extraction disagree with the shipped graph again.
- Reviewer: verify by re-running `TestDRGZeroDelta`, not by reading the diff alone.
