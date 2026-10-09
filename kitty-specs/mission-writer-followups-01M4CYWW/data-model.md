# Data Model: mission-writer-followups-01M4CYWW

This Mission adds no persisted schema. It adds one key function, two locked helpers, one injected runtime fact and two error codes. Everything it writes is already persisted under an existing shape.

## Mission lock key (D1, amended by A1–A4)

| Input (read from the canonical primary `meta.json`) | Key |
|-------|-----|
| `coordination_branch` recorded, mid8 resolvable by the transaction cascade (`meta.mid8`, then `mission_id[:8]`, then the slug tail) | `coord_mission_dir_name(mission_slug, mid8)` |
| `coordination_branch` recorded, no resolvable mid8 | typed error (no silent fallback, no trailing-dash key) |
| no `coordination_branch` (flat, primary-only) or no `meta.json` | `feature_dir.name` |

- `mission_lock_key(feature_dir) -> str` is git-free. It reads `meta.json` through the read-path resolver's canonical primary copy, never a lane worktree's copy.
- Invariant (A1): for every Mission, `mission_lock_key(primary_dir) == mission_lock_key(coord_dir) == BookkeepingTransaction._mission_specs_dir_name`, and every per-Mission lock caller passes this key.
- Hold stability (A4): while a thread holds a Mission lock, nested entries for the same Mission reuse the held key from a thread-local, so a writer that changes `coordination_branch` or `mid8` inside the hold never takes a second lock.
- The uncontended cost (NFR-003): one lock acquisition and no subprocess once the `git_common_dir` cache is warm.

## Locked helpers (D2)

| Helper | Lock | Read | Write | Returns |
|--------|------|------|-------|---------|
| `mission_metadata.locked_update_meta(feature_dir, mutate, *, repo_root=None, timeout=BOUNDED)` | `mission_write_lock(feature_dir)` | `meta.json` re-read under the lock | atomic write of `mutate(meta)` | the written dict |
| `frontmatter.locked_update_frontmatter(wp_path, mutate, *, feature_dir, repo_root=None)` | `mission_write_lock(feature_dir)` | WP frontmatter + body re-read under the lock | atomic write, body preserved byte-for-byte | the written frontmatter |

`mutate` is a pure function from the read value to the new value. It is only called; it is never stored, returned or assigned (gate Rule 2). It returning the input unchanged means "no write".

**Finalize restore (compare-and-swap).** For each file, finalize records the bytes it wrote. A restore writes the pre-finalize bytes back only while the file's current bytes equal the recorded ones, and reports any other file as `kept (changed by another writer)`.

## Runtime terminal gate (D4)

- The hook is `before_run_completed: Callable[[], None] | None`. It is passed to `commit_advance` (it exists today) and to `next_step` (new).
- If the hook raises anything (`MissionCompletionBlocked(decision: GateDecision)`, the policy error, or a capture failure), nothing is appended to `run.events.jsonl` or `state.json`.
- One bridge-level adapter maps every hook failure, on the legacy and composition paths, to a decision with `kind="blocked"`, a `reason` naming the retrospective gate, and `guard_failures` taken from the gate decision when present. It is caught before the generic engine-error handlers.

## Analysis-currency fact (D7)

- Type: `AnalysisCurrency = Callable[[], AnalysisVerdict]`. It is injected into `DecideNextContext.analysis_currency` by the shared `next_cmd.decide_next` wrapper. On the analyze step and in the finalized-board override, a missing callable fails closed with `ANALYSIS_CURRENCY_UNAVAILABLE`.
- `AnalysisVerdict` has two fields: `status: Literal["current", "missing", "stale"]` and `stale_inputs: tuple[str, ...]`.

| Verdict | Decision on the `analyze` step |
|---------|-------------------------------|
| `current` | advance to `implement` |
| `missing` | re-issue `analyze`, `error_code="ANALYSIS_REPORT_MISSING"` |
| `stale` | re-issue `analyze`, `error_code="ANALYSIS_REPORT_STALE"`, `guard_failures` = one entry per stale input |
| no callable | re-issue `analyze`, `error_code="ANALYSIS_CURRENCY_UNAVAILABLE"` |

The verdict is computed by the bridge into the snapshot's `status_facts`; the cores module stays pure. A prompt-resolution error code takes precedence over these. The finalized-board override applies the same table before it hands out implement.

## Software-dev runtime step order (D7)

`discovery → specify → plan → tasks → analyze → implement → review → accept`

A run frozen before this Mission keeps its recorded order. The analyze step is absent there, and the implement-time `analysis_report_required` refusal is the backstop.
