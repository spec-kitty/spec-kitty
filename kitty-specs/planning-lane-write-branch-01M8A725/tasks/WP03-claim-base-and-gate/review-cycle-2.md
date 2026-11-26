---
affected_files: []
cycle_number: 2
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-26T03:40:59Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP03
---

# WP03 review cycle 2 feedback (reviewer: claude::reviewer-renata)

Reviewed fold commit 60aeb939 on lane-c (diff against e94a5626). All eight cycle-1 findings are folded or recorded:

- The HIGH finding is fixed. I re-ran my cycle-1 reproduction: `agent action implement WP02` now records `refs/spec-kitty/wp-base/<slug>/WP02`.
- The single_branch waiver probe now gives `DEFERRED None`.
- The contract bump to 1.31.0 follows the 1.30.0 precedent: envelope history, the API doc, a changelog fragment and the test_contract_version pin.
- lane-c and lane-d merge cleanly (`git merge-tree`).

Three small items remain. Fold each one, or answer it explicitly.

## 1. LOW: the fallback envelope's `data.error_code` still carries the unregistered code and disagrees with the envelope `error_code`

- Location: `src/specify_cli/orchestrator_api/wp_lifecycle.py`, `_fail_workspace_resolution`, fallback branch. It spreads `exc.to_dict()` into `data`, and `StructuredError.to_dict()` (`core/errors.py:35`) includes `error_code`.
- Probe (`start-implementation`, `PlanningCheckoutMissing` monkeypatched, scratchpad `wp03-review2-probe/test_data_probe.py`):
  - `error_code` is `LANE_ALLOCATION_FAILED`;
  - `data.error_code` is `PLANNING_CHECKOUT_MISSING`;
  - `data.workspace_error_code` is `PLANNING_CHECKOUT_MISSING`;
  - `data.message` and `data.reason` hold the same text.
- Why it matters:
  - The documented refinement key is `data.workspace_error_code`. `data.error_code` is undocumented and contradicts the top-level code.
  - A consumer that reads `data.error_code` still receives the unregistered code, which is the leak this fold set out to close (PR-CONTRACT-002).
  - The #5642 precedent (`_fail_from_bookkeeping_error`) puts only the refinement key in `data`.
- Fix:
  - Drop `error_code` from the spread in the fallback branch, for example `{k: v for k, v in exc.to_dict().items() if k != "error_code"}`. Optionally drop the duplicate `reason` too.
  - Assert `"error_code" not in envelope["data"]` (or that it equals the envelope code) in `test_a_mission_branch_no_checkout_holds_reports_planning_checkout_missing_in_data`.

## 2. LOW: the changed public `error_code` for `WRITE_CHECKOUT_*` on `start-implementation` (single_branch callers) has no pinning test

- The changelog fragment and the API doc say a `WRITE_CHECKOUT_*` refusal on `start-implementation` is now `LANE_ALLOCATION_FAILED` with `data.workspace_error_code`. This is a public behavior change for existing single_branch callers.
- The only tests of that path (`tests/specify_cli/orchestrator_api/test_single_branch_repo_root_workspace.py::test_occupied_...` / `test_wrong_branch_...`) assert just a substring of stdout. They pass whether the code sits in `error_code` or in `data`.
- Fix: in one of them (or a new test), parse the envelope and assert `error_code == "LANE_ALLOCATION_FAILED"` and `data["workspace_error_code"] == "WRITE_CHECKOUT_OCCUPIED"` (or `_WRONG_BRANCH`).

## 3. LOW (nit, fold or record): the orchestrator start path lets a `record_claim_base` failure escape as a traceback

- Location: `wp_lifecycle.py`, `_ensure_repo_root_checkout_or_fail`. It calls `record_claim_base(...)` outside any guarded block. `record_claim_base` raises `RuntimeError` when `HEAD` does not resolve or when `git update-ref` fails.
- This behavior is pre-existing for the repository root checkout. It now also covers the Mission-branch checkout.
- Two inconsistencies follow:
  - The agent path (`workflow_executor._record_shared_checkout_claim_base`) catches the same error and warns.
  - NFR-002 asks for one JSON envelope per call, never a traceback.
- Fix: envelope that `RuntimeError` through `_fail_workspace_resolution` (`data.error_type == "RuntimeError"`), or record the residual with add-history.

## Judgments on items 3 and 7 (no change asked beyond the above)

- Item 3: the 1.31.0 minor bump is consistent with precedent: 1.30.0 (#7829) touched the same five kinds of file, and 1.24.0 / 1.27.0 were additive minor bumps. `upstream_contract.json` carries no contract version (only `_schema_version` 3.0.0), and neither `docs/api/cli-commands.md` nor the operator skill reference pins a version, so the version is consistent everywhere it appears. The registered-code check (`is_allowed_error_code`, fail-closed) is the right seam.
- Item 7: fail-open to `"worktree"` on an unreadable `lanes.json` is acceptable. The status-event `execution_mode` is metadata: the only readers are validation (`status/validate.py`, `migration/mission_state.py`) and the stamp itself, and nothing branches on its value to gate. The `execution_mode` comparisons elsewhere read the WP-kind field (`code_change` / `planning_artifact`), a different field.

## Tests run (reviewer)

- Blast (`-n 4 --dist loadfile`): the WP03 test files, `tests/lanes`, `tests/orchestrator_api`, `tests/specify_cli/orchestrator_api`, `tests/contract`, `tests/coordination`, `tests/specify_cli/workspace`, `tests/specify_cli/cli/commands/agent`, `tests/agent/test_orchestrator_commands_integration.py`, `test_implement_claim_concurrency.py`, `tests/integration/test_7860_planning_evidence_window.py`, `tests/docs/test_orchestrator_api_verb_doc_presence.py`.
  - Result: 8337 passed, 12 skipped, 3 xfailed, 2 failed.
  - Both failures are the expected non-WP03 reds:
    - `..._on_the_topic_branch_...` fails with `IMPLEMENTATION_MISSING` over `<base>..main` (WP04's evidence axis);
    - `..._where_implement_puts_it_...` now refuses with a recorded claim base in the Mission-branch checkout (it commits on the repository root checkout; WP05 re-pins it).
- Cycle-1 claim reproduction: claim base recorded. Single_branch waiver probe: `code_lanes_deferred_to is None`.
- ruff check, ruff C901, `ruff format --check --force-exclude` (changed files) and mypy (6 source files): clean.
- `python -m scripts.docs.check_spelling --pass all`: 0 findings.
- Changelog fragment names follow `docs/changelog/unreleased/README.md`.
