# Contracts — move-task-evidence-fixture-repin-01M6EJZB

This is a test-remediation mission (issue #7057). It defines no new contract and
introduces no executable behavior.

The contract surface it touches already exists and is only *cited*, not changed:

- **Owned-file evidence gate** (#6715, `8c5703e48f`): `move-task` refuses a
  review-ward transition whose evidence window
  (`lanes.json` `planning_commit_sha..<lane branch>`) holds no change to the
  work package's authored `owned_files`
  (`src/specify_cli/cli/commands/agent/tasks_move_task.py`,
  `src/specify_cli/consolidation/wp_evidence.py`). The Mission re-pins its test
  fixtures to *satisfy* this contract; the gate itself is untouched.
- **Review independence gate** (#6715): a `done`/`approved` move must name a
  reviewer identity; a placeholder is refused. The done-override node now passes
  one (`--agent reviewer-renata`), so the contract is exercised, not bypassed.
- **No runtime seam changes**: the diff under `src/` is empty (NFR-002/C-002);
  the only code change is one test module plus a per-PR changelog fragment.
