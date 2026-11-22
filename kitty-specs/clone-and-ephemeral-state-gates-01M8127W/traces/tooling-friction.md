# Tooling friction

Context: this Mission runs on spec-kitty 4.0.0rc9 (installed CLI) in a cloud session. Its target branch is stacked on PR #7804. Entries are appended as they happen.

- 2026-11-22 (specify): the AskUserQuestion batch was lost to a worker restart and re-asked. No tool friction in spec-kitty itself.
- 2026-11-22 (specify): `spec-commit` refuses a directory path and the `decisions/index.json.lock` runtime lock. You have to pass explicit files without the lock. The refusal text was clear.
- 2026-11-22 (tasks): the Mission spec cites the hex-colour bug's own trigger, so the spec avoids writing a literal hash-zero colour (the #7808 gate would fire on this Mission's own artifacts).
- 2026-11-22 (tasks): several natural test homes (`tests/specify_cli/lanes`, `.../review`, `.../tasks`, `tests/integration`) are out-of-matrix (#7801), so new tests were placed in per-PR directories instead.
