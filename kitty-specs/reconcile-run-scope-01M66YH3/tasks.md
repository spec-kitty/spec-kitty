# Tasks: An explicit run scope for legacy-edge reconciliation (#6728)

**Mission**: `reconcile-run-scope-01M66YH3`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Data model**: [data-model.md](./data-model.md) · **Discovery**: [research.md](./research.md)

Two work packages. WP01 carries the whole functional change (red-first tests, the `RunScope`
type, the six call sites) in `src/charter/activation/synthesizer/`. WP02 records the
maintainer-facing note and runs the targeted gate sweep. WP02 depends on WP01; nothing here is
user-facing, so no shipped docs page changes and `contracts/` stays empty (`meta.json`
`"contracts": "none"`).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first test section: `RunScope` import + no-`Ellipsis` signature guard (fails on the pre-fix tree) | WP01 |  |
| T002 | Add the `RunScope` enum with `dead_edge_filter()` next to `SynthesizeMode`, and `__all__` | WP01 |  |
| T003 | Rewire `_is_legacy_applies` + `legacy_applies_edges` to the required keyword-only `run_scope`; drop `EllipsisType` | WP01 |  |
| T004 | Rewire `merge_project_overlay` (one bool→enum conversion) and `_graph_delta` (`RunScope.FULL`) | WP01 |  |
| T005 | `resynthesize_pipeline` names `RunScope.TOPIC_SCOPED`; the seven test call sites name their scope | WP01 |  |
| T006 | Behaviour pins: both scopes on one fixture, `applies` invariance, scope-vs-`merge_project_overlay` equivalence | WP01 |  |
| T007 | Targeted verification: owning suites, ruff, mypy on the touched files | WP01 |  |
| T008 | `[Unreleased]` changelog entry (maintainer-facing; states no product behaviour change) | WP02 |  |
| T009 | Gate sweep: `test_no_dead_symbols`, terminology guard, diff-cover sanity on changed lines | WP02 |  |

---

## WP01 — The RunScope type and its call sites

- **Goal**: the sentinel is gone; `RunScope.FULL` / `RunScope.TOPIC_SCOPED` name the two runs, the enum owns the dead-edge filter, every caller states its scope, and behaviour is unchanged.
- **Priority**: P1 (the issue).
- **Independent test**: `pytest tests/charter/synthesizer/ tests/charter/test_project_registration.py -q` is green before and after, and the new scope tests fail if either scope's dead-edge result is swapped.
- **Prompt**: [tasks/WP01-run-scope-type-and-call-sites.md](./tasks/WP01-run-scope-type-and-call-sites.md)

Included subtasks: T001, T002, T003, T004, T005, T006, T007

---

## WP02 — Maintainer-facing record and gate sweep

- **Goal**: the change is recorded where maintainers look (changelog) and the gates the `__all__`/module edit implicates are green.
- **Priority**: P2 (record and verification; depends on WP01).
- **Independent test**: the changelog entry is in `[Unreleased]`, and `pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_legacy_terminology.py -q` is green.
- **Dependencies**: WP01.
- **Prompt**: [tasks/WP02-changelog-and-gate-sweep.md](./tasks/WP02-changelog-and-gate-sweep.md)

Included subtasks: T008, T009

