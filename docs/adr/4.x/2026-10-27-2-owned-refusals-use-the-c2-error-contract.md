---
title: 'ADR: owned-checkout refusals use the C2 error contract'
description: 'Every owned-checkout refusal prints the strict C2 error core in JSON mode, with an optional context object and spec_kitty_version stamp; one shared renderer fixes the shape.'
status: Accepted
date: '2026-10-27'
updated: '2026-10-29'
---

# Owned-checkout refusals use the C2 error contract

**Status:** Accepted (2026-10-27). Operator rulings of 2026-10-27.

**Date:** 2026-10-27

**Deciders:** Stijn Dejongh (operator).

**Technical Story:**
- #6353 (the `agent issue-verdict` owned refusal had no `code` key of its own shape; every owned command printed a different refusal).
- Mission `owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5`; research in `kitty-specs/owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5/research.md` (§1.2-§1.4), contract in its `contracts/owned-refusal-envelope.md`.
- Decision Moments `01M5ZBE3TX7KPA6F9E7HSSHA4B` (one shape: `json_error` C2), `01M5ZBE9FD66H8J4CW72ZQTZEF` (fix every violator), `01M5ZBEFDQXVEF4YGYYBZV322B` (strict C2), `01M5ZBENHR8GGQ23WBMM5VSMAX` (owned refusals outside the renderer move too), `01M5ZBF17G07XDN9VP13PABYX3` (mark-status facts under `context`), `01M5ZBF3XRP75H4818JD3SHF0H` (decision verbs on stdout), `01M5ZBF6YS6ARPVF4NCS5RRE18` (human mode unchanged), `01M5ZBMV9Y11KH4043KYS1KBAK` (`spec_kitty_version` stays top-level) and `01M5ZBTH94211PW53NREWSZ283` (engineering alignment).

## Context and Problem Statement

An owned-checkout refusal is the typed `ActionContextError` a command raises when its `--owned-checkout` claim, or a flagless adoption, is refused, or when an owned run is refused after resolution by the owned checkout's own guards, such as write containment (`OWNED_MISSION_PATH_REFUSED`) or the staged-index check (`OWNED_INDEX_REFUSED`) (`OWNED_*`, `OWNERSHIP_*`, `WORKTREE_INVOCATION_REFUSED`, `WORKTREE_REGISTRY_UNAVAILABLE`, `MISSION_CONTEXT_UNRESOLVED`, `MISSION_CONTEXT_CONFLICT`). All of them render through one function, `emit_owned_refusal` in `src/specify_cli/cli/commands/_owned_checkout.py`. Until now that function took a per-command envelope builder and added a top-level `error_code` when the envelope lacked one.

The result was six different JSON shapes for one kind of refusal (research §1.3): `{success, error_code, error}`, `{result, phase_complete, error_code, error}`, `{error, error_code}`, `{error, error_code, spec_kitty_version}`, `{ok, error: {code, message}, error_code}` and `{status, code, message, error_code}`. The `agent decision` verbs printed a seventh, `{error, code}`, on **stderr**. A consumer had to know which command it called to find the code. The issue-verdict refusal (#6353) carried the code only through the force-added key. The operator asked for one shape for every command (2026-10-18 triage, 2026-10-27 rulings).

## Decision

1. **The core is C2.** Every owned refusal in JSON mode prints the adopted CLI error contract C2, `{"ok": false, "error": {"code": "<code>", "message": "<text>"}}`, built by `specify_cli.cli.json_contract.json_error`, on **stdout**, and exits 1.
2. **Strict.** There is no top-level `error_code`, `success`, `result`, `status`, `code` or `message`. The redundant `result: "error"` / `success: false` keys are dropped, not moved.
3. **Optional `context`.** Command-specific facts go in one optional top-level `context` object: `agent tasks mark-status` carries its nothing-applied or recovery facts (`state_applied`, `event_ids`, `applied_wps`, `destination_ref`, `status_events_path`, `status_snapshot_path`, `dirty`), `spec-commit` carries `committed: false`, and `agent mission setup-plan` carries `phase_complete: false`. Every other command has none.
4. **`spec_kitty_version` stays top-level** on the commands that stamp every payload with it: `setup-plan`, `finalize-tasks`, `check-prerequisites` and `record-analysis` (and `agent mission create`).
5. **The renderer takes no envelope builder.** `emit_owned_refusal(exc, *, json_output, context=None, stamp_version=False)` and `resolve_owned_or_refuse(..., context=None, stamp_version=False)` fix the shape by construction. The four builders (`success_false_envelope`, `json_error_envelope`, `flat_error_envelope`, `result_error_envelope`) are deleted. The registered-code check still runs first and still fails closed on an unregistered code.
6. **One payload builder.** `owned_refusal_payload(code, message, *, context=None, stamp_version=False)` is the only builder of the shape. It does not validate the code, so the owned paths that do not go through the renderer use it too: the mark-status in-command owned failure (fallback code `MARK_STATUS_FAILED`), the move-task owned catch-all and `agent mission create`'s owned refusal, all converted in the same Mission.
7. **Decision verbs.** On an owned run, the `agent decision` verbs print as C2 on stdout through the renderer: the ownership-resolution refusal (any code the renderer's registry accepts, including `MISSION_CONTEXT_UNRESOLVED`, `MISSION_CONTEXT_CONFLICT` and `WORKTREE_REGISTRY_UNAVAILABLE`), and a registered `OwnedRefusalCode` raised after resolution, such as the decision ledger's write-containment `OWNED_MISSION_PATH_REFUSED` (`decision.py::_handle_action_context_error`, which takes the validated owned fact) and `agent decision repair-runtime-lock`'s lock-path `OWNED_MISSION_PATH_REFUSED` from `owned.files([lock])` (`decision.py::cmd_repair_runtime_lock`). Every other code, and every error on a non-owned run, keeps the `{error, code}` payload on stderr until #4664; `repair-runtime-lock`'s other failures keep its `{status, code, message}` payload on stdout.
8. **Human mode is unchanged:** `Error: [<CODE>] <message>` on stderr, exit 1.
9. **Non-owned errors and success payloads are unchanged.** For example, `agent context resolve` keeps `{success, error_code, error}` for its non-owned errors, and `stale_repository_root_copy` stays additive-only on success payloads.

### Supersedes

This decision supersedes the sentence "`emit_owned_refusal` keeps each command's existing JSON envelope keys. `error_code` is always one of the registered codes." in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/contracts/cli-owned-checkout-surface.md` (line 21, **Refusals**). That Mission file is a historical record and is not edited. The registered-code rule still holds and now applies to `error.code`.

## Consequences

### Positive

- A consumer reads `error.code` and `error.message` from every owned refusal, whatever the command.
- The renderer cannot drift back to per-command shapes: the shape is built in one place.
- The `agent decision` verbs' owned refusal is machine-readable on stdout like every other command's.

### Negative

- **Accepted behaviour change.** A consumer that reads a top-level `error_code` (or `success`, `result`, `status`, `code`) from an owned refusal must move to `error.code`. The orchestrator-api reads the host payload this way for `check-prerequisites`, `plan`, `tasks` and `specify` (`design_phase._host_error_code_and_message`), so their owned `error_code` is kept (`plan` still maps an unregistered code to `PLAN_SETUP_FAILED` with `data.reason`), and `next` embeds the new payload in `data`; its contract moves to `1.19.0` in the same Mission.
- `spec-commit`'s owned-batch refusals (`OWNED_MISSION_PATH_REFUSED`, `OWNED_INDEX_REFUSED`) and `finalize-tasks`' staged-index refusal (`OWNED_INDEX_REFUSED`) now render through the renderer, so their human line moves to the `Error: [<CODE>] <message>` form on stderr like every other owned refusal.
- The `agent decision` verbs' ledger write-containment refusal (`OWNED_MISSION_PATH_REFUSED` on an owned run, for example a symlinked `decisions/index.json`) moves from `{error, code}` on stderr to the C2 owned refusal on stdout, and `repair-runtime-lock`'s lock-path owned refusal moves from `{status, code, message}` with code `RUNTIME_LOCK_REPAIR_FAILED` to the C2 owned refusal with its own code.
- `agent context resolve` still renders `WORK_PACKAGE_UNRESOLVED` through its own non-owned error path (`{success, error_code, error}`), although the code is registered: it is raised after ownership is resolved, not by the ownership check.

### Neutral

- **Residual:** on an owned run, the generic error arm of `agent mission finalize-tasks` (`src/specify_cli/cli/commands/agent/mission_finalize_commit.py::_emit_finalize_error_with_revert_note`) still prints `{stale_repository_root_copy, error, spec_kitty_version}`, not C2, if a commit-time `owned.files` check refuses. It is reachable only through a time-of-check/time-of-use race: a symlink planted mid-run, after the minter's upfront `follow_links` screen of every top-level Mission entry, which already refuses such an escape as C2.
- The `agent decision` verbs' non-owned errors still print JSON on stderr; #4664 tracks that.
- The registered owned refusal codes are unchanged.

## Alternatives Considered

- **Keep each command's own envelope and add `error_code` (the previous rule).** Rejected: it is the six-shape problem this ADR closes.
- **One fixed `{success: false, error_code, error}` shape.** Rejected: it is a second error contract beside C2, which the CLI already adopted.
- **C2 plus an additive top-level `error_code`.** Rejected by the operator (Decision `01M5ZBEFDQXVEF4YGYYBZV322B`): two places for one code invite readers of either, and the duplicate never goes away.

## References

- `src/specify_cli/cli/commands/_owned_checkout.py` (`owned_refusal_payload`, `emit_owned_refusal`, `resolve_owned_or_refuse`)
- `src/specify_cli/cli/json_contract.py` (`json_error`)
- `kitty-specs/owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5/contracts/owned-refusal-envelope.md`
