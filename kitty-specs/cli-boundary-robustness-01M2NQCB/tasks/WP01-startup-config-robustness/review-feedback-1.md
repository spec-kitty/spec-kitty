**Issue 1 — The `doctor` acceptance assertion does not prove a domain-level result.**

`test_issue_4600_invalid_utf8_config_preserves_cli_repair_entry_points` invokes the real CLI, but for `doctor` it only checks that the output lacks `Traceback`/`UnicodeDecodeError`. The test would pass if `doctor` exited non-zero with an unrelated error or emitted no useful domain output, contrary to T001 and the acceptance matrix. Assert the expected controlled outcome explicitly (at minimum the intended exit code and recognizable doctor/help/domain output), while retaining the forbidden-diagnostic assertion.

**Issue 2 — The healthy-config control does not cover a representative normal command.**

T001/T005 require valid configuration to preserve both `--version` and representative normal-command behavior. `test_valid_config_keeps_cli_version_fast_and_healthy` invokes only `--version` (twice for warm-up/measurement). Add a valid-config normal-command assertion, preferably using the same `doctor` boundary selected for the corrupt-config case, and assert its controlled exit/output behavior. Keep the latency check lightweight and scoped to the intended startup interval.

The production changes otherwise reviewed cleanly: the RED commit fails on the original import-time `UnicodeDecodeError`, HEAD passes the focused and adjacent suites, bootstrap import purity passes, Ruff lint passes, all modified files are WP-owned, and no prohibited `Feature` terminology was introduced.
