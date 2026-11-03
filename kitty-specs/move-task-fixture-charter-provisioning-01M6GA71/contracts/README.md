# Contracts

This mission changes no interface, no production surface and no data shape: it provisions a test
fixture's charter so the mission-type resolver it exercises succeeds. The only contract it affects is
the fixture's own shape, pinned by `TestFixtureCharterProvisioning` in
`tests/tasks/test_move_task_git_validation_unit.py`:

- `resolve_mission_type_context(repo_root, mission_type="software-dev")` returns a bundle whose
  `mission_type` is `software-dev` and whose `action_sequence` is the curated sequence.
- `charter.activation.api.code_producing_for(repo_root, "software-dev")` resolves without emitting a
  `charter.activation.mission_type_profiles` WARNING record (no built-in-default fallback).

No API, CLI flag, schema or file-format contract in `src/` moves.
