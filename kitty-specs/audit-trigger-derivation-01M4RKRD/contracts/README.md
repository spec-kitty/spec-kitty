# Contracts — audit-trigger-derivation-01M4RKRD

This mission ships no new API/wire contract. Its executable contract is a test:

- `tests/ci/test_mission_state_audit_routing.py::test_every_executed_audit_module_matches_the_group`

The contract it enforces: **every `src/` module the `mission-state` audit executes
at runtime (derived from an in-process `doctor mission-state --audit` run over a small
git fixture) must be matched by a `mission_state` router group glob in
`.github/workflows/ci-router.yml`.** It is non-vacuous (same-fixture positive control)
and self-mutation-proven (RED when a covering glob is dropped or when the audit executes
an out-of-glob module). The complementary non-derivable trigger inputs (dependency
manifests, the router workflow, the report renderer, the typer command shell, a
module-level-only constant source) are pinned by
`test_non_derivable_trigger_inputs_match_the_group`.

No runtime/product or CI-workflow behaviour changes; `ci-router.yml` is unmodified
(the grounding corpus scan showed all executed modules already covered).
