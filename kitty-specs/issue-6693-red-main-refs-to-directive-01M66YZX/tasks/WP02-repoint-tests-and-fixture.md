---
work_package_id: WP02
title: Repoint the five tests and the org-pack fixture
dependencies:
- WP01
requirement_refs:
- FR-003
- NFR-002
- C-002
- SC-001
- SC-004
planning_base_branch: issue-6693-red-main-refs-to-directive
merge_target_branch: issue-6693-red-main-refs-to-directive
branch_strategy: Planning artifacts for this mission were generated on issue-6693-red-main-refs-to-directive. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6693-red-main-refs-to-directive unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T009
phase: Phase 1 - Foundation
history:
- at: '2026-10-30T17:55:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/charter_offering/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/charter_offering/drg/test_single_owner_edges.py
- tests/charter_offering/drg/migration/test_extractor_projection.py
- tests/charter_offering/test_testing_doctrine_single_owner.py
- tests/charter_offering/fixtures/minimal_org_pack_2/drg/fragment.yaml
- tests/integration/test_org_pack_chain_delivery.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Repoint the five tests and the org-pack fixture

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission issue-6693-red-main-refs-to-directive-01M66YZX`) and address every item before handing back.

## Objectives & Success Criteria

- The five assertion sites named by issue #6693 name the artifact the packs now ship
  (`directive:RED_MAIN_RELEASE_DISCIPLINE` / id `RED_MAIN_RELEASE_DISCIPLINE`), with the
  same checks they made before. Spec FR-003.
- The `minimal_org_pack_2` fixture's `refines` edge resolves against the built-in layer,
  so its merge validates. Spec FR-003.
- No assertion is weakened, no expected value is loosened, and no node/edge count is
  changed unless the shipped graph genuinely changed. Spec NFR-002, C-002.
- Every historical mention still reads as it was written. Spec C-002.

## Context

WP01 pinned both packs to open-packs `72cb7dbc`, which turned the built-in
`red-main-release-discipline` procedure into the `RED_MAIN_RELEASE_DISCIPLINE`
directive and removed the procedure from the tree. The tests below read the *fetched*
tree (or a fixture that models it), so they now assert against something that no
longer exists.

Three of these sites are not simple string swaps — the URN **kind** prefix changes too
(`procedure:` → `directive:`), and two of them are keyed by an artifact id rather than a
URN.

## Subtasks

### T005 — `tests/charter_offering/drg/test_single_owner_edges.py`

`test_test_first_bug_fixing_points_at_its_owners` is parametrized with
`("procedure:red-main-release-discipline", Relation.REQUIRES)`. The shipped
`procedure.graph.yaml` now carries
`procedure:test-first-bug-fixing --requires--> directive:RED_MAIN_RELEASE_DISCIPLINE`
(the relation is still `requires`; only the kind and id moved). Update the
parametrization entry, keeping it in the same list and position with its comment.

### T006 — `tests/charter_offering/drg/migration/test_extractor_projection.py`

Two ledger comments (around the residual-orphan and orphan-wiring sections) describe
`procedure:red-main-release-discipline` as the artifact behind charter Standing Order
#9. Repoint them to the directive. Also inspect the pinned inventories the file asserts:
if any test pins a node/edge count or an orphan set that the red-main move changes,
update the *number only after* re-deriving it from the shipped graph, and say in the
commit message which number changed and why. Do not adjust a count to make a test pass.

### T007 — `tests/charter_offering/test_testing_doctrine_single_owner.py`

`test_references_034_and_red_main` asserts
`expected = {"DIRECTIVE_034", "red-main-release-discipline"}` against
`test-first-bug-fixing.procedure.yaml`'s `references[].id`. The pack now lists
`{"type: directive, id: RED_MAIN_RELEASE_DISCIPLINE}`, so the expected set becomes
`{"DIRECTIVE_034", "RED_MAIN_RELEASE_DISCIPLINE"}`.

Also review the sibling test `test_states_commit_topology_carve_out`, which currently
accepts `"red-main-release-discipline" in content or "already landed" in content`. The
fetched procedure now says `under RED_MAIN_RELEASE_DISCIPLINE`, so the first disjunct
never matches. Keep the assertion honest: either widen it to the directive id or drop
the dead disjunct — but do not leave a clause that can never be true. State which you
chose and why in the commit message.

### T008 — `tests/integration/test_org_pack_chain_delivery.py`

Two sites:

- the module-level constant list of declared edges
  (`("procedure:landing-contributor-prs", "procedure:red-main-release-discipline")`),
- the `marker_edges` assertion that the internal pack's `refines` edge reached the
  consumer.

Both become `directive:RED_MAIN_RELEASE_DISCIPLINE`, matching the internal pack's
`drg/fragment.yaml`.

### T009 — `tests/charter_offering/fixtures/minimal_org_pack_2/drg/fragment.yaml`

The fixture declares `target: "procedure:red-main-release-discipline"`. Repoint it to
`"directive:RED_MAIN_RELEASE_DISCIPLINE"`. This fixture is core-owned test data (not
fetched pack content), so editing it is correct — the fixture models an org pack that
refines the built-in rule.

## Do not touch

- `tests/charter/test_activation_preserves_effective_4253.py` — its three mentions are
  #4253 historical narrative and the file stays green.
- `tests/charter_offering/fixtures/content-manifest.json` — a relocation-guard manifest
  of *pre-relocation* `src/charter/offering/**` paths, asserted absent; rewriting it
  would fabricate a path that never existed.
- `docs/changelog/CHANGELOG.md` history, `docs/adr/**`, `kitty-specs/**` of other
  missions, `.kittify/evidence/**`.

## Branch Strategy

Planning branch and final merge target: `issue-6693-red-main-refs-to-directive`.
`single_branch` mission; the runtime allocates the workspace, so never pick a base by
hand. Your dependency WP01 must be `done`/`approved` before you are claimed.

## Test strategy

```bash
uv run --frozen pytest -q -p no:randomly \
  tests/charter_offering/drg/test_single_owner_edges.py \
  tests/charter_offering/drg/migration/test_extractor_projection.py \
  tests/charter_offering/test_testing_doctrine_single_owner.py \
  tests/integration/test_org_pack_chain_delivery.py \
  tests/charter/test_activation_preserves_effective_4253.py
```

All five must be green, and the last one must be green **without being edited**. No full
heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION).

## Definition of Done

- [ ] The five files above are green at the bumped pin.
- [ ] `git diff` touches only the five owned files plus whatever WP01 owns.
- [ ] Every historical record still reads as written (`git grep -n 'red-main-release-discipline'` returns hits only in the preserved-history paths).
- [ ] No assertion was loosened; any count change is justified in the commit message by a re-derivation from the shipped graph.
- [ ] Tracer entry appended for any friction found.

## Risks & Reviewer Guidance

- **Loosening to green.** The fastest wrong fix is `assert x in content or True`-style
  edits or dropping the assertion. Reviewer: compare each changed assertion with its
  previous check and confirm the same property is still checked.
- **Fixture vs fetched tree.** `minimal_org_pack_2` is core test data (edit it); anything
  under `packs/**` is fetched (never edit it).
- **Kind vs id.** Two sites are keyed by id only (`test-first-bug-fixing`'s reference
  list, the activation ledger in WP03). Changing them to the `directive:`-prefixed URN
  is wrong there — check the shape each site expects.
