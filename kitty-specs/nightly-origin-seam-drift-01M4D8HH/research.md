# Research: nightly reds after origin freshness (#5886 #5887 #5888 #5889)

Run 37723696665 (head `4cabb9042c8e`) red; run 37567676962 (`ecc257f40d9b`) green. Range: 199 commits.
Venv synced with `uv sync --frozen --all-extras`; exact node ids run with `-n0`.
Every group reproduced on `4cabb904` and on `main` `add98cdb` (16 failed / 187 passed over the four files).
Classification (CLAUDE.md baseline-red gotcha): none is p0_repro, CI-env, stale-install or stale-venv. All are real reds introduced by the range.
They escaped per-PR CI because the files run only in nightly shards (out-of-matrix shard 3/5, `integration`).

Source: `git bisect run` per group (scripts in the session scratchpad), then a parent-green / commit-red check per culprit. All culprits belong to PR #5845 (#5780).

| Group | Node ids | Culprit | Verdict | Evidence |
|---|---|---|---|---|
| G1 | `tests/specify_cli/doctrine/test_sources.py::TestGitSource` (7) | `dc4524a5` fix(kernel): no_prompt_env keeps the user's ssh transport choice | test | `no_prompt_env` now runs `git config [--global|--system] --get core.sshCommand` via `run_git`. `_GitRunRecorder` patches `git_source.subprocess.run`, which is the global `subprocess.run`, so the reads consume scripted results (`calls[1][-1] == 'core.sshCommand'`). The empty-script fallback returns str stdout to a bytes caller (`'str' object has no attribute 'decode'`). |
| G2a | `test_merge_cli_golden.py::test_help_pins_one_line_help_and_every_visible_flag` | `73682930` fix(consolidate): refuse when origin has status evidence or lanes this clone lacks | test (intended flag) | Unexpected flag `--origin-check`, documented in ADR `2026-10-06-3` and CLAUDE.md. |
| G2b | `test_accept_decomposition.py::TestOwnedEntry::test_stamp_receives_the_cli_edge_fact`, `::TestBridgesToUnconvertedCallees::test_merge_commit_verification_bridge[owned]` | `9ed59d9c` fix(accept): accept and orchestrator-api check origin freshness | test | The harness fakes every collaborator except the new `run_origin_gate`. The owned run passes the `SimpleNamespace` ownership stub into `placement_seam(...).write_target`, which reads `owned.topology` and raises `AttributeError`. The real `OwnedCheckout` has `topology`. |
| G3 | `tests/integration/test_explicit_checkout_commands.py` accept tests (6) | `460ba7c8` fix(landing): a clone whose remote was removed passes the origin check with a warning, not in silence | test | stdout is exactly one JSON payload. The new note goes to stderr (`typer.echo(..., err=True)`) and into `advisories`, as `_check_origin_freshness`'s docstring states. The fixture has `refs/remotes/origin/main` with no remote. `CliRunner.result.output` mixes in stderr, so the tests parsed `Warning: ...\n{...}`. |

Hypothesis check (orchestrator): "origin-freshness work changed git subprocess calls (G1), added a flag (G2), and emits non-JSON output ahead of `accept --json` (G3)". G1 and G2 are confirmed. G3 is confirmed only for the merged CliRunner output: real stdout stays pure JSON, so there is no contract break and no design decision to escalate.

Decision gate: conclusive for all groups. Remediate by re-pinning the test seams; no product change.
