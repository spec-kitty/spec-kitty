# Discovery findings — #6693 red-main reference repoint

## Decisions

### D1. The upstream change exists; this mission is a pin bump plus core repoints

**Evidence.** `spec-kitty/spec-kitty-open-packs` PR #74 ("Move the rule-shaped
red-main procedures to directives") merged 2026-10-26T20:29:53Z, merge commit
`72cb7dbcba69efa608327be9921d915f435d1565`, and is an ancestor of open-packs
`main`. The issue's premise holds: this is a vendoring mission, not an upstream
authoring mission. Verified with
`git merge-base --is-ancestor 72cb7dbc <open-packs main>` → true.

### D2. Pin to `72cb7dbc`, not to open-packs `main` tip

**Evidence.** open-packs `main` is far ahead (`5df92a5`, "describe the sanitized
procedure fields…") and carries a breaking "sanitized-shape migration". The diff
between the current pins and `72cb7dbc` is exactly the red-main move:

- built-in (6 files): `directive.graph.yaml`, new
  `directives/red-main-release-discipline.directive.yaml`,
  `pack-manifest.yaml`, `procedure.graph.yaml`,
  deleted `procedures/red-main-release-discipline.procedure.yaml`,
  `procedures/test-first-bug-fixing.procedure.yaml`.
- internal (5 files): `README.md`, new
  `directives/spec-kitty-red-main-policy.directive.yaml`,
  `drg/fragment.yaml`, `glossary_packs/spk-internal.glossary-pack.yaml`,
  deleted `procedures/spec-kitty-red-main-policy.procedure.yaml`.

Pinning the merge commit keeps the review surface honest and matches the issue
title ("on the next open-packs pin bump").

### D3. The new directive keeps the procedure's file stem, so config ids are stable

**Evidence.** The directive id is `RED_MAIN_RELEASE_DISCIPLINE` in
`directives/red-main-release-discipline.directive.yaml`; activation keys are
per-kind stems, so `activated_procedures` → `activated_directives` moves the same
stem `red-main-release-discipline` between two namespaces. Running
`spec-kitty charter activate directive RED_MAIN_RELEASE_DISCIPLINE` reported
`Activated: red-main-release-discipline`.

### D4. Red is measurable at the bumped pin, before any fix

**Evidence.** With both pins bumped to `72cb7dbc` and `make sync-packs` run, six
pre-existing tests fail through their normal entry points:

- `tests/charter_offering/drg/test_single_owner_edges.py::test_test_first_bug_fixing_points_at_its_owners[procedure:red-main-release-discipline-requires]`
- `tests/charter_offering/drg/migration/test_extractor_projection.py::TestDRGZeroDelta::test_regenerated_graph_matches_baseline_counts`
  (`346 == 345` nodes: the curated edge mints an extra
  `procedure:red-main-release-discipline` node)
- `tests/charter_offering/drg/migration/test_extractor_projection.py::TestDRGZeroDelta::test_shipped_graph_is_fresh_and_byte_identical`
- `tests/charter_offering/test_testing_doctrine_single_owner.py::TestTestFirstBugFixingTopologyAndRefactor::test_references_034_and_red_main`
- `tests/integration/test_org_pack_chain_delivery.py::test_class_b_internal_pack_delivers_every_declared_kind`
  (missing `('procedure:landing-contributor-prs', 'procedure:red-main-release-discipline')`)
- `tests/integration/test_org_pack_chain_delivery.py::test_class_a_second_org_pack_fragment_folds`
  (`DRGValidationError: Dangling target: … procedure:red-main-release-discipline`)

`tests/charter/test_activation_preserves_effective_4253.py` stays green: it names
the artifact only in #4253 historical prose.

### D5. The bump also dangles this repository's own charter — a live warning, not just a test

**Evidence.** `spec-kitty charter context --action implement` at the bumped pin
reports `Charter catalog miss for procedure:red-main-release-discipline;
cause=missing_artifact`, and `spec-kitty doctor charter-packs` reports
`DENY_UNKNOWN_ID: deactivated_procedures … lists red-main-release-discipline,
which no layer provides. Remove the stale entry by hand.` The issue does not list
this surface, but it is the user-visible half of the same defect: Standing Order
#9's doctrine pointer stops resolving. In scope (proportional: 1 procedure
deactivation + 1 directive activation + 1 stale deny line).

### D6. Reorder: deactivate first, then activate

**Evidence.** Activating the directive while the retired procedure was still
activated produced `Catalog not recompiled: No procedure artifact with config ID
'red-main-release-discipline' found …`. The deactivate-then-activate order
recompiles cleanly and touches 4 files with a 13-line diff.

## Evidence

- Issue: spec-kitty/spec-kitty#6693 (open, unassigned, no labels at read time).
- Upstream: spec-kitty/spec-kitty-open-packs#74, merged `72cb7dbc`.
- Current pins before this mission: built-in `af1c370f`, internal `ecda7b00` —
  both ancestors of `main`, so the bump is a forward move.
- `requires_core: '>=4.0.0rc7,<5'` on the new built-in pin; the CLI in this
  checkout is `4.0.0rc8`, so the constraint is satisfied.
- No open or merged PR in spec-kitty/spec-kitty mentions #6693 (checked with
  `gh pr list --state all --search 6693`), and `git log -S
  RED_MAIN_RELEASE_DISCIPLINE origin/main` is empty: the work is not done and not
  superseded.
- Historical citations to be preserved (C-002): `docs/changelog/CHANGELOG.md`,
  `docs/plans/engineering-notes/doctrine-drg-missing-links-analysis.md`,
  `kitty-specs/**`, `.kittify/evidence/**`.

## Open questions (left for specify/plan)

- Should the repository's own activation move from procedure to directive in this
  PR, or in a separate "dogfood the new pin" change? — Resolved in D5: same PR,
  because the warning is introduced *by* this bump.
- Does a consumer-side note belong in the changelog? — Yes: a consumer who
  activated the procedure by name must repoint their own ledger; core cannot
  rewrite it.
- Is the `graph.yaml` label refresh (`Project Intent Directive` → `Mission Type
  Scope Directive`) and the `generated_at` stamp legitimate regeneration output?
  — Yes; they are emitted by the ledger compile seam and hand-editing them back
  would create drift.
