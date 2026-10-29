---
work_package_id: WP03
title: orchestrator-api reads the C2 host refusal; contract 1.19.0
dependencies:
- WP02
requirement_refs:
- FR-012
- FR-013
- SC-003
planning_base_branch: issue-6354-owned-issue-verdict-cleanup
merge_target_branch: issue-6354-owned-issue-verdict-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-6354-owned-issue-verdict-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6354-owned-issue-verdict-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5
base_commit: 9ecaa2f213671458c7d87e1bf0e4f8dbf64a7925
created_at: '2026-10-27T21:49:21.988639+00:00'
subtasks:
- T013
- T014
- T015
- T016
phase: Phase 3 - Contract consumers
history:
- at: '2026-10-27T19:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/orchestrator_api/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/orchestrator_api/design_phase.py
- src/specify_cli/orchestrator_api/runtime_next.py
- src/specify_cli/orchestrator_api/envelope.py
- docs/api/orchestrator-api.md
- tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py
- tests/specify_cli/orchestrator_api/test_contract_version.py
- tests/specify_cli/orchestrator_api/test_runtime_next.py
- tests/orchestrator_api/test_origin_freshness_envelopes.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – orchestrator-api reads the C2 host refusal; contract 1.19.0

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP03 --note "..."`.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

After WP02 the host commands' owned refusal is C2: `{ok:false, error:{code,message}, ...}`.
Two orchestrator-api verbs embed host output:

- `orchestrator-api check-prerequisites` (`design_phase.py:449-476`,
  `_classify_check_prerequisites_error`) reads `payload.get("error")` as a string message
  and `payload.get("error_code")` as the code. On a C2 host owned refusal it would emit a
  stringified dict as the message and fall back to `CHECK_PREREQUISITES_FAILED`.
- `orchestrator-api next` (`runtime_next.py:62-110`) treats `"error" in payload` as a
  refusal and embeds the raw host payload in `data`. The `error` key is still present, so
  detection still works, but `data`'s content changed.

Done when:
- FR-012: the classifier returns the host code (with the existing
  `MISSION_CONTEXT_UNRESOLVED` → `MISSION_NOT_FOUND` translation, applied to the whole
  payload, nested `error.code` included) and the plain-text `error.message`. The non-owned
  host errors (`{"error": "<text>"}`, still a string) classify exactly as before.
- FR-013: `CONTRACT_VERSION = "1.19.0"`; the version tests are re-pinned; the reference doc
  shows `1.19.0` and a change note.

## Context & Constraints

- Contract: `kitty-specs/owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5/contracts/owned-refusal-envelope.md` (Consumers section).
- `upstream_contract.json` is unaffected: codes do not change.
- No orchestrator module calls the CLI renderer; do not import it here.
- ATDD: T013 red first.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6354-owned-issue-verdict-cleanup`
- **Merge target branch**: `issue-6354-owned-issue-verdict-cleanup`

```bash
spec-kitty agent action implement WP03 --agent claude --mission owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5
```

## Subtasks & Detailed Guidance

### Subtask T013 – Red-first classifier tests

In `tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py` add
pure unit tests on `_classify_check_prerequisites_error` (it is a module-level function;
import it as the existing tests do):

1. `test_classifier_reads_c2_host_owned_refusal`:
   payload `{"ok": False, "error": {"code": "OWNED_CHECKOUT_IS_REPOSITORY_ROOT", "message": "m"}, "spec_kitty_version": "x"}`
   → returns `("OWNED_CHECKOUT_IS_REPOSITORY_ROOT", "m", payload)`.
2. `test_classifier_translates_c2_mission_context_unresolved`:
   `error.code == "MISSION_CONTEXT_UNRESOLVED"` → first element `"MISSION_NOT_FOUND"`,
   message `error.message`, and the returned payload contains no `MISSION_CONTEXT_UNRESOLVED`
   anywhere (nested `error.code` included; `_sanitize_forbidden_error_code` already walks dicts).
3. `test_classifier_keeps_string_error_host_payloads`: the non-owned shape
   `{"error": "boom", "spec_kitty_version": "x"}` → `("CHECK_PREREQUISITES_FAILED", "boom", payload)`;
   `{"error": "boom", "error_code": "X"}` → `("X", "boom", payload)` (positive control:
   the legacy shapes still classify unchanged).
4. Optionally (only if cheap with the existing `_init_repo` helpers): an end-to-end run of
   `orchestrator-api check-prerequisites` where the host adopts an owned checkout refusal.
   If no cheap fixture exists, the unit tests above plus WP04's cross-command test are the pin;
   say so in the history note.

Commit red: `test(orchestrator-api): red classifier for the C2 host owned refusal (#6353)`.

### Subtask T014 – Classifier reads C2

Change `_classify_check_prerequisites_error` (`design_phase.py:449-476`):

```python
error = payload.get("error")
if isinstance(error, Mapping):
    message = str(error.get("message") or "check-prerequisites failed")
    error_code = error.get("code")
else:
    message = str(error or payload.get("message") or "check-prerequisites failed")
    error_code = payload.get("error_code")
```

then keep the existing translation/return logic unchanged. Extend the docstring with one
sentence naming the C2 owned refusal shape (ADR `2026-10-27-2`). Keep complexity <= 15
(extract a `_host_error_code_and_message(payload) -> tuple[object, str]` helper if needed).

### Subtask T015 – Contract version 1.19.0

- `src/specify_cli/orchestrator_api/envelope.py:150`: `CONTRACT_VERSION = "1.19.0"`.
- Re-pin `tests/specify_cli/orchestrator_api/test_contract_version.py:80-86` (rename the
  test to `..._1_19_0`) and `tests/orchestrator_api/test_origin_freshness_envelopes.py:29`.
- `grep -rn '1\.18\.0' src tests docs` and update every pin of the **current** version
  (leave historical change-log lines describing 1.18.0 itself).
- `runtime_next.py`: read `_fail_native_refusal` (~62-79). Detection (`"error" in payload`)
  still works for the C2 shape; `data` embeds the new payload. No code change is expected.
  If `tests/specify_cli/orchestrator_api/test_runtime_next.py` pins an owned refusal's
  embedded keys, re-pin it to C2. Record in the history note whether any change was needed.

### Subtask T016 – Reference doc

`docs/api/orchestrator-api.md`:
- line ~33: `CONTRACT_VERSION`: `1.19.0`; the example envelope (~187) `"contract_version": "1.19.0"`.
- Add a change-log entry above the `1.18.0` one (~163), matching its style:
  "`1.19.0` — host owned-checkout refusals embedded by `check-prerequisites` and `next`
  now use the CLI's C2 error contract (`{ok: false, error: {code, message}}`, ADR
  `2026-10-27-2`); `check-prerequisites` classifies the code and message from `error`.
  Error codes are unchanged."
- Bump the page's `updated:` freshness date if it has one.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/orchestrator_api/ tests/orchestrator_api/ -q
uv run --frozen ruff check src/specify_cli/orchestrator_api/ tests/specify_cli/orchestrator_api/
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy src/specify_cli/orchestrator_api/design_phase.py src/specify_cli/orchestrator_api/envelope.py
```

## Risks & Mitigations

- Missing a `1.18.0` pin turns a test red: grep the whole repo.
- Do not change orchestrator error codes; consumers key on them.

## Review Guidance

- String-error host payloads still classify exactly as before (positive control).
- The forbidden host code never leaks, nested or top-level.
- Version is 1.19.0 everywhere current; the doc change note is present.

## Progress & Status

- `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP03 --to <status>`
- `spec-kitty agent tasks status`
