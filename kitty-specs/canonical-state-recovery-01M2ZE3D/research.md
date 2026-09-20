# Research — Canonical-State Integrity & Recovery (#4758, #4786)

Phase 0. Two profile-loaded opus grounding lenses reproduced live on HEAD `b17f199576` (repo tree untouched). Full transcripts summarized here; this is the authoritative research the plan builds on.

## Verdicts

- **#4758 — REAL P0, unfixed, distinct** from #4075 (failure-path txn ordering), #2802 (flattened-topology commit dest), #3311 (rerun *rewrites* existing lanes — opposite mode; its guard partly seals #4758's wedge). Reproduced live: `agent tasks finalize-tasks` seeds `genesis→planned` events with **no `lanes.json`**, then `move-task --to doing` succeeds (planned→in_progress) with lanes still absent.
- **#4786 — PARTIAL; P0 "unclearable" framing is stale.** Attribution-drop reproduces (bare rejection → `agent=null` → accept blocks at `summary_core.py:87`), **but is clearable** via `move-task --to <lane> --agent <x>` (±`--force`) — #3029 remedy-1, shipped in `e455ce26c1`. Two of four "broken remedies" already fixed (`--agent` retrofit; `merge --dry-run` OptionInfo crash does not reproduce via CLI, #4723 wrapped it). Scar tissue: same spot patched by #2512/#2960/#4673. Taken as full structural fix **per operator ruling**.

## Seam map (file:line, HEAD b17f199576)

### Canonical runtime state — the object
- `src/specify_cli/status/models.py:535-551` — `WPInnerStateDelta` scalar family: `shell_pid`, `shell_pid_created_at`, `agent`, `assignee`, `role`, `agent_profile`, `agent_profile_version`, `model`, `provider`. Claim **triple** = agent + shell_pid + shell_pid_created_at.
- `models.py:569` `release_runtime_claim: bool` — explicit "clear the claim triple" signal; `:579-588` `_SCALAR_FIELDS` SSOT; `:590-603` guards a bare `agent=""` no-op.
- Reducer folds latest-wins; `release_runtime_claim` clears BEFORE the replace-slot loop, so a concrete value in the same delta overrides the clear.

### #4758 — lanes.json minting split
- `src/specify_cli/cli/commands/agent/tasks_finalize.py:271` — `bootstrap_canonical_state(...)`, **no** `_compute_and_write_lanes` anywhere in the file. Docstring: "this legacy command family."
- `src/specify_cli/cli/commands/agent/mission_finalize.py:2819`→`:2829` — canonical path bootstraps THEN `_compute_and_write_lanes` (both writes co-located = correct).
- `src/specify_cli/lanes/persistence.py:111` `require_lanes_json` — file-existence gate; reached on approval/implement/owned-review (`context/resolver.py:262`, `implement.py:1393`, `workspace/context.py:873`, `tasks_move_task.py:642`) but **NOT** on `move-task --to doing`.
- `src/specify_cli/cli/commands/agent/mission_finalize.py:2039` `_execution_has_begun` (lane-state) + `:2210-2230` refusal (execution begun AND lanes absent → `typer.Exit(1)`). Docstring asserts this "should never reach" — #4758 falsifies it.
- Rollback refusal: `src/specify_cli/cli/commands/agent/tasks_transition_core.py:407-423` `WP_METADATA_UNSUPPORTED_ON_PROTECTED_COORD_BRANCH`.

### #4786 — attribution drop
- `src/specify_cli/acceptance/summary_core.py:86-98` — accept gate. `agent` required on **every** lane (`:87`); `assignee`(`:96`)/`shell_pid`(`:98`) only for active lanes `{doing,in_progress,for_review}` (terminal exempt, #2369). `strict_metadata` toggles; `accept --lenient` downgrades all to advisory.
- `src/specify_cli/cli/commands/agent/tasks_move_task.py:2891` — `release_runtime_claim=True` on any rollback→planned (`_build_claim_review_override`, ~2838-2898).
- `tasks_move_task.py:2970-2978` — same-identity suppression: a same-actor restamp on a PLANNED target is suppressed so the release wins; passing `--agent` on a non-planned transition re-stamps (why the retrofit works).
- `src/specify_cli/status/doctor.py:215-240` — ALREADY DETECTS blanked runtime slots (#2960) but offers **no repair** — detect-without-cure.
- `src/specify_cli/status/wp_metadata.py:437-505` `resolved_agent()` — dispatch-time family resolution.

### Existing recovery surfaces (extend, don't invent)
- `src/specify_cli/cli/commands/agent/mission_repair.py` — cross-partition (coord vs primary) ff-reconciliation only (`_classify_repair_state:69`). Does NOT rebuild lanes.json or repair attribution.
- `doctor coordination --fix` (`_coordination_doctor.py`), `doctor mission-state --fix` → `repair_repo` (`migration/mission_state.py:518`, JSON-shape canonicalization), `lanes/recovery.py` (worktree crash-recovery only). None rebuild lanes-from-log or attribution.

## Triple-authority (the wedge mechanism)
"Has lanes / execution begun" answered by three non-coincident authorities: `require_lanes_json` (file-existence) vs `_execution_has_begun` (lane-state) vs ~20 soft `read_lanes_json→None` sites. Their disagreement mints the unrecoverable state. Top brownfield fold: one "execution-ready" predicate.
