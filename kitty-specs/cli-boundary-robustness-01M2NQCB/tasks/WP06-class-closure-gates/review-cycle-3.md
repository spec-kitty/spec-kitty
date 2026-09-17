---
affected_files: []
cycle_number: 3
mission_slug: cli-boundary-robustness-01M2NQCB
reproduction_command:
reviewed_at: '2026-09-16T23:18:21Z'
reviewer_agent: user
wp_id: WP06
---

## Review verdict: rejected

The explicit 171-path classification and 69 parse-only drivers correct the prior
vacuous allow-list. The architectural file is the only implementation file in
commit `ff8372984`, and its 85 tests pass. Two contract gaps remain.

### 1. The parse-only drivers do not consistently exercise an error arm

`test_verified_parseable_error_arms_remain_json` invokes every leaf Click
command with only `--json`. Several such calls are successful normal outputs,
not the outside-project or equivalent generic **error** input required by
G1/T027. In a temporary isolated filesystem, direct checks give:

- `doctor bytecode --json`: exit 0, normal payload with `root` and `findings`.
- `doctor channel --json`: exit 0, normal payload with `channel`.
- `tracker providers --json`: exit 0, normal payload with `local` and `saas`.
- `zeitgeist operability drill-timeout --json`: exit 0, normal outcome payload.

These passing cases cannot detect a regression where the success JSON remains
parseable but the command's error output becomes prose. Provide a deterministic
error condition for each `already-parseable` record, or classify a path as
deferred if no bounded error condition can be verified. Assert the driver
actually reaches the intended error condition as well as parsing raw stdout.
Keep the nine adopted paired-exit/shape drivers unchanged.

### 2. Some deferred evidence inaccurately claims stderr output

The per-path record for `agent tasks status` says “empty stdout; error or usage
output on stderr”; an isolated leaf invocation of `status --json` instead
exits 1 with **both streams empty**. `agent profile list` has the same mismatch.
Correct these records to the behavior actually observed, and audit the shared
wording on other deferred rows. The explicit path/callback identity and #4664
follow-up are good; this is about evidence accuracy.

### Verification

- `PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_cli_boundary_contract_enumeration.py -q`: 85 passed in 47.31s.
- Focused isolated Click probes above reproduced the successful parse-only
  paths and empty-stream deferred paths.

### WP anti-pattern checklist

1. Dead code: PASS.
2. Synthetic-fixture test: PASS (production command objects are invoked).
3. Silent empty return: FAIL for the deferred evidence on the two named paths.
4. FR coverage: FAIL for G1/T027's error-arm requirement.
5. Frozen surface: PASS (only the owned architectural test changed).
6. Locked decision: FAIL (parse-only allow-list is not fully error-driven).
7. Shared-file ownership: PASS.
8. Production fragility: N/A (no production code changed).
