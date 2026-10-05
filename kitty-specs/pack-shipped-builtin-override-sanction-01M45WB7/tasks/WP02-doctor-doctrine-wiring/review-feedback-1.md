# WP02 review feedback (cycle 1) — reviewer-renata

Overall the WP is close: collector wiring, JSON contract, parity gate, red-first evidence, FR-012
byte identity (verified against mission base ca59bbea, not just the WP01 tip), legacy hint and
escaping are all correct, and a real-CLI smoke (directive:MINUTES_STAND_ALONE) gives RC=1 / legacy
hint / RC=0 as specified. One required fix blocks approval.

## Issue 1 (REQUIRED): the human policy-error block is untested

`src/specify_cli/cli/commands/doctor.py:1213-1227` `_render_override_policy_errors` is the ONLY
human-surface channel for FR-006 / FR-007 errors (`org_drg.errors` is not rendered anywhere else in
human mode, so without it a malformed pack/consumer file or an unknown revocation target would be a
silent RC=1). The deviation itself is therefore justified and should stay; T009 also explicitly
requires "Render `pack_sanction_errors` in the same red block style".

But no test drives it: `grep -rn "Override sanction file error" tests/` is empty, and every
`_run_doctrine_human` test in `test_doctor_override_diagnostics.py` uses a well-formed policy. The
consumer-prefix filter (`str(m).startswith(str(POLICY_RELPATH))`) and the escape of error messages
(NFR-005) are likewise unasserted. Charter/Sonar rule: every new branch/helper needs a test in the
same PR (diff-cover >= 90%).

Fix: add 1-2 human-surface tests in `test_doctor_override_diagnostics.py`, e.g.
- malformed pack file + consumer `revoked_pack_sanctions: [{pack: Nope}]` -> RC=1, output contains
  `Override sanction file error(s) — 2`, the pack name, and `revoked_pack_sanctions names pack 'Nope'`;
- assert an unrelated `org_drg.errors` entry (e.g. the `unsanctioned built-in override:` error) is NOT
  duplicated into this block (pins the prefix filter);
- optionally a pack dir containing `[bold]` in a malformed-pack case to pin escaping of the block.

## Non-blocking observations (fix only if cheap)

- `doctor.py:1253` derives the pack root with `path.removesuffix(LEGACY_TEMPLATE_RELPATH)` where the
  suffix is a POSIX string; on Windows `str(path)` uses backslashes, so the hint would read
  "move X to X/replaceable-builtins.yaml". Carrying the pack root (or using `Path(path).parents[2]`)
  avoids string surgery.
- `make test-fast` was not re-run by the reviewer (targeted suite was); please record it in the notes.
