# Research: Owned-checkout issue-verdict cleanup

Phase 0 grounding for mission `owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5`.
Baseline: `origin/main` at `581b5c46` (2026-10-27). Every file:line below was re-read on
that commit.

## 1. Code grounding

### 1.1 Migration placement (issue 6354)

- `src/specify_cli/tasks/issue_matrix_migration.py:301-383` --
  `migrate_issue_matrix_to_json(feature_dir, *, repo_root, mission_slug, policy, read_dir,
  target_branch, actor)` has no `owned` parameter, and its call to `write_issue_matrix`
  (`:376-383`) passes neither `owned=` nor `matrix_dir=`.
- `src/specify_cli/tasks/issue_matrix.py:404-414` -- `write_issue_matrix` already accepts
  `owned: OwnedCheckout | None` and `matrix_dir`; with both omitted it resolves the write
  location lazily against the repository root checkout.
- `src/specify_cli/cli/commands/agent/issue_verdict.py:178-215` -- `_migrate_if_needed`
  receives `owned` and uses it for the read dir (`_resolve_read_dir(..., owned=owned)`),
  but does not forward it to `migrate_issue_matrix_to_json` (`:208-215`).
- Other callers of `migrate_issue_matrix_to_json`: the bulk `issue-matrix migrate` command
  (`issue_matrix_migration.py:408`, repository-root only, non-owned by design) and unit
  tests in `tests/specify_cli/tasks/test_issue_matrix_structured.py:347-401`.

**Red-first reproduction.** An owned-only `single_branch` Mission (the
`tests/integration/test_explicit_checkout_commands.py::checkouts` fixture) with a
legacy `issue-matrix.md` in the owned checkout. `agent issue-verdict --owned-checkout <P>
--json` then exits 1 with `FileNotFoundError(2, 'No such file or directory')` (the
migration's write resolves against the repository root, where the Mission does not
exist). The issue described it as failing safe rather than writing to the wrong root, and
that is what the reproduction shows.

### 1.2 Owned refusal shape (issue 6353)

- `src/specify_cli/cli/commands/_owned_checkout.py:298-326` -- `emit_owned_refusal` prints
  `envelope(code, message)` and force-adds a top-level `error_code` when missing; human
  mode prints `Error: [<code>] <message>` on stderr; exit 1. Unregistered codes raise
  `UnregisteredOwnedRefusalCode` (`:263-295`).
- Builders `:329-346`: `success_false_envelope`, `json_error_envelope`,
  `flat_error_envelope`, `result_error_envelope`.
- `src/specify_cli/cli/commands/agent/issue_verdict.py:379-387` -- issue-verdict passes
  `success_false_envelope`; its ordinary errors are `{error, code}` (`:519-524`).
- `src/specify_cli/cli/json_contract.py:18-20` -- `json_error(code, message)` returns
  `{"ok": False, "error": {"code", "message"}}`, "the adopted CLI error contract" (C2,
  `kitty-specs/cli-boundary-robustness-01M2NQCB/contracts/json-envelope-contract.md`),
  gated by `tests/architectural/test_json_contract_enumeration.py` (`assert_json_result`,
  `:64-71`).

**Red-first reproduction.** `agent issue-verdict --mission no-such-mission-01ZZZZZZ
--owned-checkout <P> --json` prints `{"success": false, "error_code":
"MISSION_CONTEXT_UNRESOLVED", "error": ...}`; a consumer reading `code` (issue-verdict's
own error key) finds nothing.

### 1.3 Caller inventory (every owned refusal)

The owned-refusal keys in the table are those after the `error_code` force-add.

| # | Command | Call site | Owned refusal keys today | Extras to keep (operator ruling) |
|---|---|---|---|---|
| 1 | `agent issue-verdict` | agent/issue_verdict.py:379 | success, error_code, error | -- |
| 2 | `agent [mission] acceptance-verdict` | agent/acceptance_verdict.py:593 | success, error_code, error | -- |
| 3 | `agent context resolve` | agent/context.py:259-268 | success, error_code, error | -- (non-owned `_emit_context_error` :208-229 keeps its shape) |
| 4 | `next` | next_cmd.py:238-252 | success, error_code, error | -- |
| 5 | `agent mission setup-plan` | agent/mission_setup_plan.py:1246-1249 | result, phase_complete, error_code, error | context.phase_complete=false; spec_kitty_version |
| 6 | `agent mission finalize-tasks` | agent/mission_finalize.py:660, :794 | error, error_code, spec_kitty_version | spec_kitty_version |
| 7 | `agent [mission] check-prerequisites` | agent/mission_check_prerequisites.py:678-686, :768 | error, error_code, spec_kitty_version | spec_kitty_version |
| 8 | `agent mission record-analysis` | agent/mission_record_analysis.py:372, :419 | success, error_code, error | spec_kitty_version (its other payloads carry it) |
| 9 | `agent tasks status` | agent/tasks_status_cmd.py:200-209 | ok, error{code,message}, error_code | -- |
| 10 | `agent tasks move-task` | agent/tasks.py:891 | error, error_code | -- |
| 11 | `agent tasks mark-status` | agent/tasks.py:1020 (`_ms_failure_payload`) | result, error_code, error, state_applied, event_ids, applied_wps, destination_ref, status_events_path, status_snapshot_path, dirty | context.{state_applied, event_ids, applied_wps, destination_ref, status_events_path, status_snapshot_path, dirty} |
| 12 | `agent tasks map-requirements` | agent/tasks.py:1354 | error, error_code | -- |
| 13 | `spec-commit` | spec_commit_cmd.py:519-527 | result, success, committed, error, error_code | context.committed=false |
| 14 | `accept`, `agent mission accept` | accept.py:983 | error_code, error | -- |
| 15 | `charter generate` | charter/generate.py:461-469 | success, error_code, error | -- |
| 16 | `agent decision repair-runtime-lock` | decision.py:1099-1107 | status, code, message, error_code | -- |
| 17 | `agent action implement/review` | agent/workflow.py:1109-1119 | human only (no `--json`) | -- |
| 18 | `research` | research.py:216-224 | human only (no `--json`) | -- |
| 19 | `dispatch` | dispatch.py:409 | error, error_code | -- |
| 20 | `invocations list` | invocations_cmd.py:382 | error, error_code | -- |
| 21 | `profile-invocation complete` | profile_invocation.py:172 | error, error_code | -- |

Owned refusals that bypass the shared renderer (all in scope by operator ruling):

| # | Path | Site | Keys today |
|---|---|---|---|
| 22 | `agent mission create` | agent/mission_create.py:509-530 | success, error_code, error (+ spec_kitty_version via `_emit_json`) |
| 23 | move-task owned catch-all | agent/tasks_move_task.py:1726-1740 | error_code, error (any ActionContextError code) |
| 24 | mark-status in-command owned failure (see #3865) | agent/tasks_mark_status.py:653-690 | as row 11 |
| 25 | `agent decision open/resolve/defer/cancel/verify/list` | decision.py:231 (`resolve_owned_or_adopt`) caught by `_handle_action_context_error` :238-253 | `{error, code}` on **stderr** |

### 1.4 Contracts and consumers that pin the shapes

- `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/contracts/cli-owned-checkout-surface.md:21`:
  "`emit_owned_refusal` keeps each command's existing JSON envelope keys. `error_code` is
  always one of the registered codes." This mission supersedes that line (ADR, FR-014).
- `_owned_checkout.py:25-32` module docstring: added keys are additive only.
- orchestrator-api (`CONTRACT_VERSION = "1.18.0"`, `src/specify_cli/orchestrator_api/envelope.py:150`;
  documented in `docs/api/orchestrator-api.md:33`). No orchestrator module calls the
  renderer, but two verbs embed host output:
  - `orchestrator_api/design_phase.py:449-476` `_classify_check_prerequisites_error` reads
    top-level `error`/`message` (as a string) and `error_code`. Under C2 it must read
    `error.code` / `error.message`.
  - `orchestrator_api/runtime_next.py:62-110` treats `"error" in payload` as a refusal and
    embeds the raw payload in `data`; the `error` key stays present, but `data` changes.
- Tests that pin the old owned shapes (to be re-pinned, not deleted):
  `tests/specify_cli/cli/commands/test_owned_checkout_helper.py` (:187, :516, :531-541,
  :597-615), `test_next_owned_fact.py:198`, `test_accept_decomposition.py:269-270, :713`,
  `agent/test_task_command_owned_conversion.py` (:114, :132, :342, :443-459),
  `agent/test_mission_finalize_phases.py:1516`, `agent/test_mission_setup_plan_phases.py:1200-1202`,
  `tests/integration/test_owned_lifecycle_acceptance_next.py:193`,
  `tests/agent/test_agent_feature.py:725-727`. Shape-agnostic tests that read
  `["error_code"]` move to `["error"]["code"]` (list in the plan's IC-02/IC-03).

## 2. Architectural alignment

- **ADR 2026-10-22-1** (the Java write service is the canonical event writer) concerns
  status event writes. It does not mention the issue matrix, owned refusals or CLI JSON
  envelopes, so nothing here would be redone by that direction.
- **ADR 2026-10-26-1** (done judges every issue-matrix row; see #6653, merged) reads the issue
  matrix at the terminality gate. This mission changes only where an owned legacy
  migration writes, not what a row contains. C-003 keeps its tests green.
- **Owned-checkout model** (CLAUDE.md "Execution Workspace Strategy";
  `_owned_checkout.py` G2 single-authority gate). Validation stays in the one shared
  surface; only rendering changes. `test_owned_checkout_single_authority.py` must stay
  green.
- **C2 contract** (`json_contract.json_error`) is the single adopted CLI error contract;
  reusing it for the core removes four competing builders. This applies the "single
  canonical authority" principle.

## 3. Related issues and in-flight work

- See #6715 (accept/consolidate claimed-but-empty, P0). It adds accept refusals that are
  not owned refusals. Accept's owned refusal (row 14) adopts C2 here; nothing else in
  accept changes, so envelope shapes stay compatible.
- See #6675, PR #6716 (see #6193 lock-interop spike), PR #6705 (see #6651 move-task
  stdout note), PR #6717 (see #6706): no overlap with the files above except PR #6705,
  which touches move-task's dirty-files note, not its owned refusal.
- Sibling missions M1-M5 work on other surfaces; no file overlap was found in this
  inventory.
- See #4664: the decision verbs' stderr JSON (DEFERRED in the C2 gate) remains; only
  their owned refusal moves to stdout C2.

## 4. Decisions (operator rulings, recorded as Decision Moments)

| Decision | Choice | Rationale | Alternatives considered |
|---|---|---|---|
| Shared owned refusal shape | C2 `{ok:false, error:{code,message}}` | One adopted CLI error contract, already gated | Command-faithful + `error_code` (the earlier contract line); fixed `success_false` |
| Top-level `error_code` | dropped (strict C2) | One place to read the code | Keep it additively |
| Scope | every owned refusal, incl. the four off-renderer paths | No odd one out | Helper callers only |
| Command-specific facts | one optional top-level `context` object | Strict core, facts preserved | Drop them |
| `spec_kitty_version` | stays top-level where the command stamps payloads | It is a payload stamp, not refusal context | Under `context` |
| Decision verbs' owned refusal | stdout | Same stream as every other owned refusal | stderr |
| Human mode | unchanged | Only the JSON contract was in question | -- |
| Redundant keys (`result:"error"`, `success:false`) | dropped; replaced by `ok:false` | `ok:false` carries the same fact | Move under `context` |
| move-task catch-all codes | accepts any ActionContextError code (unchanged) | It never validated; tightening it is out of scope | Validate |

## 5. Tidy-first

- `_owned_checkout.py` keeps its validation untouched; the renderer change is the
  behaviour change itself, so no separate preparatory refactor is needed there.
- `issue_matrix_migration.py`: adding a keyword-only `owned=None` parameter is additive
  and behaviour-preserving for every existing caller; it lands in the same WP as its test.
- No god-surface is touched beyond one call site each; the Sonar/complexity check is done
  per touched function in review (NFR-003).

## 6. Adversarial squad (pre-spec point-cut)

Ran as a single independent inventory pass (Explore agent, no edits), reading the code
rather than my hypothesis. Findings folded in: (a) the existing contract line already
states the "command-faithful" rule, so the C2 ruling needs an ADR to supersede it
(FR-014); (b) orchestrator-api depends on the host keys indirectly (FR-012/FR-013);
(c) `resolve_mission_handle` emits `success_false` for non-owned handle errors. That is
out of scope: it is not an owned refusal, and FR-011 leaves non-owned errors unchanged.
No contested finding was dropped.
