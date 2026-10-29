# Research: local event-log retention (#5212 → #6610)

Grounded on `origin/main` @ `f90c9f2a` (2026-10-27). Read-only pass, before any spec.

## 1. Code grounding (file:line re-verified on origin/main)

| Claim in the issues | Current location | Status |
|---|---|---|
| `StateSurface` has no cleanup field | `src/specify_cli/state/contract.py:87-127` (issue cited `78-106`) | Holds. Fields: name, path_pattern, root, format, authority, git_class, owner_module, creation_trigger, deprecated, atomic_write, notes, target_owned, ignored_via_agent_block. `to_dict()` (`:112-127`) emits no policy. |
| Registry `STATE_SURFACES` | `contract.py:134` onward, 62 entries | Holds. |
| No `keep_runs` / `max_age_days` in `src/` | `grep -rn` over `src/` | Holds (gap G-9, `docs/architecture/event-ledger-writers-and-readers.md:225`). |

### Surfaces the cleanup touches (all `git_class=IGNORED`)

| Surface | Path | Facts |
|---|---|---|
| `runtime_run_snapshot` / `runtime_run_event_log` / `runtime_frozen_template` | `.kittify/runtime/runs/<run_id>/` | Created by `runtime/next/_internal_runtime/engine.py:203 start_mission_run`; run id `uuid4().hex`. Dir also holds `state.json.lock` (run-cursor lock, `runtime/next/run_lock.py`). Snapshot has no timestamp field (`schema.py:501-519`); `run.events.jsonl` rows carry `timestamp`. Snapshot carries optional `mission_id` / `mission_slug`. Terminal is computed, not stored; only marker is a `MissionRunCompleted` row (`engine.py:540-544`). |
| `runtime_feature_index` | `.kittify/runtime/feature-runs.json` | `runtime/next/run_index.py`: `index_lock` (`:129`, blocking, 10 s), `read_index_file`, `save_index` (`:216`), `resolve_run_dir`. One entry per mission key, reused across states. An index entry whose `state.json` is gone raises `RunStateMissing` (`runtime_bridge_io.py:345-362`) — so a deleted run dir MUST drop its index entry (ADR D-3). |
| `glossary_fallback_events` | `.kittify/events/glossary/<mission_id>.events.jsonl` | `glossary/events.py:67-86`. Non-Mission siblings `_cli.events.jsonl` (`cli/commands/glossary.py:85`), `_renderer.events.jsonl` (`template/renderer.py:222`). Sidecars `<log>.lock`, `<log>.torn`. |
| `derived_mission_views` | `.kittify/derived/<mission_slug>/` | Rebuilt on read: `status/views.py:256-316 materialize_if_stale`. |
| `op_invocation_index` | `kitty-ops/ops-index.jsonl` | Writer `invocation/writer.py:203-230`; reader `cli/commands/invocations_cmd.py:345-351` falls back to a directory scan when absent (no rebuild function). Appended under the event-log lock. |

### Locks
- `kernel/locks.py` guarantee G3 (`:38`, `:388-407`): release truncates, **never unlinks**; unlinking would let a later acquirer create a new inode and break mutual exclusion. **Decision: no lock file is cleanup-eligible** — neither `<git-common-dir>/spec-kitty-locks/event-logs/*.lock` (`kernel/event_log_append.py:153 event_log_lock_path`), nor `<log>.lock`, nor `state.json.lock` / `feature-runs.json.lock` as standalone items. A run dir is deleted whole (its `state.json.lock` goes with it) only after a non-blocking acquire of its run-cursor lock succeeds and while held.
- "Holds a lock" is detected authoritatively by a non-blocking `machine_file_lock(path, blocking=False)` (`LockNotAcquired`, `locks.py:147`), not by file presence.
- `event_log_lock` / `append_event_log_lines` are frozen doors (`tests/architectural/test_event_log_writes_gate.py:161 EXPECTED_DOOR_CALLERS`). The cleanup must not call them; it probes `event_log_lock_path(anchor)` with `machine_file_lock` instead (not a door). The gate scans writes only; `unlink`/`rmtree` are not counted.

### Mission openness
- `status/lifecycle.py:321 is_mission_completed(feature_dir)`: `merged_at` set, or derived state `recently_completed`/`archived`. "Open" = not completed. No `is_mission_open` exists.
- Mission lookup: by `mission_slug` (`kitty-specs/<slug>/`) or by scanning `kitty-specs/*/meta.json` for `mission_id`.

### Unfinished glossary step
- `glossary/checkpoint.py:137-201 load_checkpoint` reads `StepCheckpointed` rows across every log; no closing event exists, so "unfinished step" is not definable from the log alone. A completed Mission has no step to resume; the protection reduces to "Mission is open" (ADR D-3 bullet 4 is subsumed by bullet 2). Non-Mission logs (`_cli`, `_renderer`) are never eligible (they name no Mission).

### Doctor family
- `cli/commands/doctor.py` is a closed orchestration shim (header `:1-14`). New subcommands self-register via `cli/commands/_*_doctor.py` + `register(app)` (`_auto_discover_doctor_siblings`, `:226-243`). Template: `_run_index_doctor.py`.
- Conventions: `--json`, shared `console`, `resolve_project_root_or_exit`, exit 0 clean / 1 findings / 2 usage-or-internal.
- `docs/api/cli-commands.md` must list every non-hidden command path (`tests/architectural/test_docs_cli_reference_parity.py`).

### Config
- `ledger.projection` reader: `core/ledger_posture.py` (`_read_repo_ledger_key :104-140`, fails open with a warning). No typed `ledger.retention` loader exists. For a destructive command, invalid retention values fail closed (`consolidation/config.py:39-90` style `ConfigError`), defaults when absent.

## 2. Architectural alignment
- ADR 2026-10-13-2 D-3 (`:127-160`) is the governing rule set; its Confirmation (`:195`) is the acceptance test shape.
- ADR 2026-10-22-1 says nothing about deletion; it keeps D-3 unchanged (`:27`). Retention is reader/doctor-side, adds **no Python writer** and no new door caller — nothing to redo when logs hand over to the Java service. Deletion still respects the event-log lock the service will share (`flock`, D-4 `:125`).
- Epics #6608 / #6117, events #92 (CloudEvents envelope, PR events#142): file-level retention is independent of the row envelope. No conflict.
- ADR 2026-10-13-2 Amendment 2026-10-18: uncommitted Op records are in neither tier — never pruned.

## 3. Related issues / sibling runs (tracked-issues squad)
| Item | Disposition |
|---|---|
| #5212 | Closes (policy field). |
| #6610 | Closes (cleanup command). |
| #3895 epic | Refs (bullet 1 done). |
| #5213 authority classes | Refs — sibling, not folded; the policy is orthogonal to `AuthorityClass`. |
| #3970 cleanup postcondition report | Refs — the policy field is the per-surface input its report reads; not folded. |
| #6185 item 4 | Refs (split out as #6610). |
| PR #6716 (#6193 lock spike) | No file overlap (Java spike tests + docs). Our lock rule (never unlink, probe non-blocking) matches its subject. |
| #6715, #6675 | No overlap (consolidation / write-service protocol). |
| M12 (`events tail`, G-10) | No overlap: we don't touch `cli/commands/events.py`. |
| Stale docstring `doctor.py:828` (`.kittify/events/profile-invocation-lifecycle.jsonl`; real path `kitty-ops/lifecycle.jsonl`) | Campsite fix only if the file is touched; otherwise file-and-link. |

## 4. Similar-surfaces squad
- Other unbounded local logs: `.kittify/logs/` (`runtime_agent_logs`, external orchestrator), `encoding_provenance_global_log`. Not in ADR D-3's local tier; policy = `manual`, no cleanup this run.
- `review/prompt_metadata.py:186-222` already prunes review prompts to newest N — a per-surface owner lifecycle; policy = `owner_lifecycle` naming that path.

## 5. Operator decisions (2026-10-27, this session)
- Command: `spec-kitty doctor event-logs`, dry run by default, `--apply` deletes.
- Scope includes the rebuildable caches (`.kittify/derived/`, `kitty-ops/ops-index.jsonl`).
- A Mission not found in this checkout: protect and report ("kept: Mission not found").
- #5212 shape: `CleanupPolicy(retention: RetentionRule, cleanup_command: str | None)` on every surface; rules `never`, `ledger_retention`, `rebuildable`, `owner_lifecycle`, `manual`, `retired`.
- Earlier ruling (2026-10-23, #6610): `keep_runs=20`, `max_age_days=30`, delete only when both are exceeded; committed ledgers never pruned.

## 6. Test seams and churn
- Contract tests: `tests/specify_cli/test_state_contract.py` (635 lines), `test_state_doctor.py:133`, `test_gitignore_contract.py`.
- 90-day churn: `contract.py` 1 commit, `run_index.py` 1 commit. Low.
- Gates implicated: `test_event_log_writes_gate.py`, `test_docs_cli_reference_parity.py`, `test_mutation_ownership_routing.py` (doctor siblings outside its module set).

## 7. Plan-phase decisions

- **Decision: age = newest file modification time.** Rationale: one `stat` per file keeps a 1,000-run preview well under 2 s (NFR-001) without parsing journals; a project copy resets mtimes forward, which only delays deletion (safe direction). Alternative considered: the last `timestamp` row of `run.events.jsonl` — rejected as extra parsing and absent for glossary logs and caches.
- **Decision: lock order run → index for a run deletion.** Rationale: the run-index entry must disappear in the same critical section as the directory (ADR D-3), and no path holds the index lock while waiting on a run lock (`run_lock.py` C-002), so one-way nesting cannot deadlock. Alternative considered: delete the directory, release, then take the index lock — rejected because `next` would hit `RunStateMissing` in the window.
- **Decision: probe locks with the kernel primitive, not the event-log door.** Rationale: `event_log_lock` / `append_event_log_lines` callers are frozen in `EXPECTED_DOOR_CALLERS` and the cleanup is not a writer (ADR 2026-10-22-1). `machine_file_lock(event_log_lock_path(anchor), blocking=False)` takes the same OS lock. Alternative considered: adding a door caller — rejected (grows a frozen debt ledger).
- **Decision: completion check is lazy and memoized.** Only items already outside both limits pay for `is_mission_completed`, once per Mission.
- **Decision: `.torn` and `<log>.lock` sidecars stay.** The lock never goes (G3); the torn-tail sidecar has no registry surface and is out of the confirmed scope (FR-011 lists only what is never deleted; nothing widens the set).
