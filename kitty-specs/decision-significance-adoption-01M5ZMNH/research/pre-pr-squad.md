# Pre-PR adversarial squad — decision-significance adoption

Point-cut: pre-merge (aggregate diff vs `origin/main` at `edb6ddc99`). Question: does the diff adopt the shared contract correctly and completely, without a behaviour change beyond the operator rulings or a boundary leak?

Cast (procedure `adversarial-squad-deployment`, profile-loaded, read-only): `reviewer-renata` (correctness), `architect-alphonso` (architecture, boundaries, contract alignment). Verdicts: renata DO-NOT-SHIP → SHIP-WITH-FIXES; alphonso SHIP-WITH-FIXES. Both lenses independently found the Java read API coupling.

## Dispositions

| # | Lens | Severity | Finding | Disposition | Evidence |
|---|------|----------|---------|-------------|----------|
| 1 | both | BLOCKER / MAJOR | Lock move left the conformance manifest at 11.0.0 and `PORTED_EVENTS_VERSION` at 11.0.0; 4 conformance tests red | accepted | `42e3b6ea2` (manifest regenerated; constant 11.3.0 with port-review Javadoc). Python conformance 53 passed. Java `ManifestCouplingTest` not runnable here (Maven Central 429); equality verified directly |
| 2 | alphonso | MAJOR | `src/specify_cli/events/decision_log.py` became a direct events importer not covered by the reducer-lock census | accepted | `201abfe0c` (`REDUCER_LOCK_UNOWNED_IMPORTERS` → `execution_context`); census 11 passed |
| 3 | renata | MAJOR | On the real `next` path the inferred fallback recorded sentinels for roles the inputs could resolve (FR-005) | accepted (operator ruling 2026-10-28: resolve per role) | `ce928dabc`; 5 red-first tests; re-review ACCEPT |
| 4 | renata | MINOR | Whitespace-only template `actor_id` now counts as missing | changed: documented as an edge case | `spec.md` Edge Cases (`ce928dabc`) |
| 5 | alphonso | MINOR | Safe-adoption checklist made the Java port review conditional and omitted the two gates | accepted | `e8d5fb187` (`docs/development/reference/events-in-core.md` steps 4, 6) |
| 6 | alphonso | MINOR | `engine.py` hard-coded the `SignificanceEvaluated` event type | accepted | `5cc8067af` (package `SIGNIFICANCE_EVALUATED`) |
| 7 | alphonso | MINOR | Architecture page grounding line still named the 11.0.0 lock | accepted | `e8d5fb187` |
| 8 | alphonso | MINOR (upstream) | Package docstring describes core as a by-shape mirror | deferred_with_rationale: upstream docs, not this repo | spec-kitty-events#146 |
| 9 | both | NIT | Soft-gate sentinel is unreachable in production (validated actor identity) | deferred_with_rationale: the operator ruling on #6445 names the soft-gate path; the branch is defensive and the test comment says so | `tests/next/test_decision_significance_adoption.py` |
| 10 | alphonso | NIT | `RACIRoleSpec` vs `RaciRoleBinding` casing | deferred_with_rationale: kept by design (operator split ruling); cosmetic | — |
| 11 | renata (re-review) | NIT | `inputs if inputs is not None else {}` could be `inputs or {}` | deferred_with_rationale: cosmetic, no behaviour difference | — |
| 12 | renata (re-review) | NIT (pre-existing) | When an explicit template RACI fails R/A resolution the fallback uses the inferred assignment and drops the explicit spec | deferred_with_rationale: pre-existing, outside the ruling; raised to the operator in the PR | PR body |
