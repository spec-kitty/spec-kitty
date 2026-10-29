---
affected_files: []
cycle_number: 1
mission_slug: owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5
reproduction_command:
reviewed_at: '2026-10-29T04:58:22Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review feedback (reviewer-renata)

Verdict: changes requested. The classifier change is correct as a pure function, but FR-012 is
not met on the real `orchestrator-api check-prerequisites` path: the C2 host owned refusal never
reaches the classifier.

## Blocking finding

The host renderer prints the owned refusal indented:
`src/specify_cli/cli/commands/_owned_checkout.py:352`, `print(json.dumps(payload, indent=2))`.
That is the path `check-prerequisites` takes through `resolve_owned_or_refuse` (adoption from the cwd
still runs when no `--owned-checkout` is passed) and through `emit_owned_refusal(..., stamp_version=True)`
at `mission_check_prerequisites.py:760`.

`_extract_json_payload` (`src/specify_cli/orchestrator_api/design_phase.py:99-117`) only parses a JSON
object that sits on ONE line. A multi-line document gives `payload is None`, so
`_classify_check_prerequisites_error` takes its `payload is None` branch. The result:

- `error_code` is `CHECK_PREREQUISITES_FAILED`, not the host code.
- The message is the whole stringified JSON document, not `error.message`.
- For `MISSION_CONTEXT_UNRESOLVED`, the forbidden host code LEAKS into the envelope, in both
  `data.raw_output` and `data.message`. The sanitizer is never applied on the `None` branch.

Reproduction against the real renderer (lane-c HEAD):

```python
emit_owned_refusal(ActionContextError("MISSION_CONTEXT_UNRESOLVED", "msg"), json_output=True, stamp_version=True)
# captured stdout -> _extract_json_payload(raw) is None
# -> _classify_check_prerequisites_error(None, raw)[0] == "CHECK_PREREQUISITES_FAILED"
# and "MISSION_CONTEXT_UNRESOLVED" is in the returned data
```

An end-to-end CliRunner run (the `_init_repo` + `_build_mission` + monkeypatched-host pattern of
`test_check_prerequisites_translates_forbidden_code_in_nested_payload_too`, with the host printing the
C2 payload with `indent=2` as the real renderer does) failed for both
`OWNED_CHECKOUT_IS_REPOSITORY_ROOT` and `MISSION_CONTEXT_UNRESOLVED`. Both came back as
`error_code: CHECK_PREREQUISITES_FAILED`.

The history note says the optional T013 e2e test was skipped because "no cheap fixture exists". That
is inaccurate: the same test module already has the cheap fixture. That skipped test is the one that
would have caught this defect.

## Required changes

1. Make the `check-prerequisites` delegate payload extraction parse the host's indented, multi-line
   JSON document. Examples: try `json.loads(raw_output.strip())` first and fall back to the line scan,
   or use a `json.JSONDecoder().raw_decode` scan from each `{`. Keep the existing single-line/noise
   tolerance. If `_extract_json_payload` is shared with plan/tasks/specify, keep their behaviour
   unchanged or pin it. Changing that helper is in WP03's owned file `design_phase.py`.
2. Close the leak on the `payload is None` branch. When the raw output is unparseable, the forbidden
   `MISSION_CONTEXT_UNRESOLVED` must still not cross onto the surface in `data.raw_output` or the
   message. For example, pass the raw output and message through `_sanitize_forbidden_error_code`, or
   equivalent.
3. Add the end-to-end pin (T013 item 4) to
   `tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py`. Drive
   `orchestrator-api check-prerequisites` with the host monkeypatched to emit the refusal through the
   REAL `emit_owned_refusal` (or with `json.dumps(..., indent=2)`, matching it). Parametrize over a
   registered owned code (for example `OWNED_CHECKOUT_IS_REPOSITORY_ROOT`, expecting that code and
   `error.message` as the envelope message) and `MISSION_CONTEXT_UNRESOLVED` (expecting
   `MISSION_NOT_FOUND`, with no forbidden token anywhere in `json.dumps(envelope)`). Commit it red
   first.
4. Update the WP history note so it records the e2e test and drops the "no cheap fixture" rationale.

## Verified and fine (no change needed)

- `_host_error_code_and_message` / `_classify_check_prerequisites_error`: a C2 mapping yields
  `error.code`/`error.message`, string-error payloads classify as before, and the forbidden code is
  sanitized when it is the classified code. A C2 payload with no code falls back to
  `CHECK_PREREQUISITES_FAILED`. Complexity is 2 and 4.
- `runtime_next.py` needs no change. Before WP02, the native owned refusal (`success_false_envelope`)
  also had no `kind: error`, so it already took the generic `"Native next refused the request"` path
  with the payload in `data`. The C2 payload is still detected (`"error" in payload`), and `_decode`
  parses the whole stdout, so indentation is fine there. That is acceptable under FR-012/FR-013.
- Version: `CONTRACT_VERSION = "1.19.0"`, the tests are re-pinned and the docs show 1.19.0. The
  remaining `1.18.0` hits (`envelope.py:142`, `docs/api/orchestrator-api.md:167`,
  `docs/changelog/CHANGELOG.md:156`) are historical lines. The doc change note is accurate.
- Scope: the WP03 commits touch only owned files plus status bookkeeping.
- ruff, ruff format and mypy are clean on the touched files.

## Commands run (reviewer)

- Red-first, in a detached temporary worktree at 1314d20f (removed afterwards):
  `pytest tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py -k classifier`
  gave 3 failed and 1 passed (the string-error control). The red is genuine.
- `uv run --frozen pytest tests/specify_cli/orchestrator_api/ tests/orchestrator_api/ -q -n 4 --dist loadfile`
  gave 269 passed and 1 skipped.
- `ruff check` and `ruff format --check --force-exclude` on the 5 touched py files: clean. `mypy` on
  design_phase.py and envelope.py: no issues.
- The temporary e2e CliRunner test (host prints the C2 payload with indent=2), deleted afterwards:
  2 of 2 failed with `CHECK_PREREQUISITES_FAILED`.
