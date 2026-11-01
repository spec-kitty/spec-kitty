# WP07 review cycle 1: changes requested

Reviewer: claude:opus:reviewer-renata:reviewer. Implementer of record: claude:opus:python-pedro.

## What holds

- **`release.yml` steps.**
  - The fetch step and the `--check` step sit directly after the packs `--check` step and before `python -m build`.
  - Neither has `if:` or `continue-on-error`, and the job has none either.
  - A digest mismatch exits 1 there, before anything is built. The fetch step itself also verifies digests, so a mismatch fails even before `--check` runs.
- **The wheel-content Python, checked by hand.**
  - I extracted it from the step's heredoc and ran it, in a temp directory, on a wheel I built locally (`uv build --wheel`):
    - Result: 2149 members. `specify_cli/_pins/README.md` and `read-service.source.yaml` are present; there is no `services/` or `contracts/` member and no binary.
    - The check exits 0 on that wheel.
  - With a planted `specify_cli/_bin/mission-status-api-0.1.0-linux-x64` member it exits 1 with `::error::the wheel ships service binaries: [...]`.
  - The heredoc terminator lands at column 0 once YAML strips the indentation, and the step runs under `bash -e`.
- **`RELEASE_CHECKLIST.md`.**
  - The wording is accurate. `spec-kitty service vendor --service read-service --check` verifies the lockfile online; its default service is write-service, so naming read-service matters.
  - `make sync-services` fetches and verifies; `ARGS=--check` verifies the cache only.
  - The hunk is minimal, one bullet.
- **Tests and lint.** The tests listed below pass, and ruff is clean.

## 1. MEDIUM (blocks under the WP checklist item 2, synthetic fixture): the wheel rule is re-implemented in the test, not run

`tests/ci/test_release_service_pins.py:70-84` (`test_the_wheel_rule_the_step_states`) re-states the rule in the test body and checks it against planted member lists. It never executes the step's own Python.

The other two tests only look for substrings (`PIN_MEMBER`, the four patterns, `zipfile`, `dist/*.whl`) in the `run:` text. So an edit that breaks the step's logic would still pass every test. Examples: inverting `if binaries:`, matching against the full member path instead of the basename, or checking a different pin member while still mentioning the right one in a message.

This is core-authored code, so running it in a test is safe and cheap.

Ask: replace the re-implemented rule with a test that does the following.
- Extract the Python between `python - <<'PY'` and `PY` from the "Verify wheel contents" step.
- Write minimal wheels into `tmp_path / "dist"`: one with the pin member only, one without the pin, and one per binary pattern (`specify_cli/_bin/mission-status-api-…`, `…/command-cli-…`, `….jar`, `….exe`).
- Run the snippet with `cwd=tmp_path` (subprocess `sys.executable -I`, or `exec` with `chdir`).
- Assert exit 0 only for the clean wheel, and that the message names the offending member otherwise.
- Keep a control that the extraction found the snippet, so the test cannot pass on an empty string.

## Low / informational

- The check step names only `--service all`. Once a `write-service` pin is added it is covered automatically. The checklist names only read-service for the online `vendor --check`, which is correct today; consider "one line per pinned service" wording when a second pin lands.
