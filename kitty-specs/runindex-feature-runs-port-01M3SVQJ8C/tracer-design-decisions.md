# Tracer — Design Decisions

Mission: **runindex-feature-runs-port** (fixes #5390 P0 + #5389 P1, refs #2624)

Seeded at planning; appended during implement; assessed at close.

## DD-01 — Single locked RunIndex port (both bugs, one seam)
Both defects live in one writer (`get_or_start_run`, `runtime_bridge_io.py`). Per
Stijn's triage we introduce ONE port — the RunIndex — as the sole reader/writer of
`.kittify/runtime/feature-runs.json`, rather than N parallel patches. Consolidate-to-one-seam
(Standing Order #2) + closes both defect classes by construction.

## DD-02 — run_dir persisted as a repo-relative token, never absolute
`run_store` is always `repo_root/.kittify/runtime/runs` (io.py:825), so every run_dir is
inside the invoking repo by construction. The port persists `run_dir` as the token
`Path(run_dir).relative_to(repo_root).as_posix()` (canonically `.kittify/runtime/runs/<run_id>`),
resolved at READ time against the INVOKING repo_root. This mirrors the ADR
`2026-08-16-5` operator-config/env-expand rule ("persisted state stores a token, never a
resolved path") already used by committed provenance (`${SPEC_KITTY_PACKS_ROOT}/…` +
`m_3_2_7_heal_provenance_paths`) and the already-tokenized `WorkspaceContext.worktree_path`
(the good model the audit cited). `${VAR}` tokens are still expanded via
`kernel.env_expand.expand_raw_template` so a future runtime-root knob in `.kitty.env` works.

## DD-03 — Containment: a resolved run_dir outside the invoking repo is refused, never followed
Per epic #2624 containment discipline. On read, the port resolves the token and refuses
(does not follow) any run_dir that escapes `repo_root`. This is what turns the P0 from
"silently mutate the ORIGINAL folder, exit 0" into an explicit, actionable refusal for a
legacy absolute index; a *post-fix* copy/move carries a relative token and simply works.

## DD-04 — Locked read-modify-write (concurrency, #5389)
The port wraps the whole read→merge→write span in `kernel.locks.machine_file_lock`
(blocking, bounded timeout) against a DEDICATED sidecar `feature-runs.json.lock` (never the
payload path — G1). Inside the lock it RE-READS the on-disk index, merges this invocation's
entry against that fresh snapshot, RE-CHECKS the same mission still exists, then atomically
replaces. Distinct-mission concurrent starts can no longer lose each other's registration.

## DD-05 — Heal migration + doctor check for legacy absolute indexes
Modelled 1:1 on `m_3_2_7_heal_provenance_paths` + `doctor provenance`: a
`BaseMigration` that rewrites absolute `run_dir` entries to the canonical relative token,
plus a shared `describe_leaks(project_path)` reused by a self-registering
`doctor run-index` sibling (`cli/commands/_run_index_doctor.py`, auto-discovery seam).

## DD-06 — Empty-allowlist ratchet gates (Stijn 2026-09-30: no shrink-only debt)
Two hard gates, each closing with an EMPTY allowlist:
1. the literal `feature-runs.json` / the index open appears ONLY in the RunIndex port module;
2. the port never persists an absolute `run_dir` (behavioural self-mutation test).

## DD-07 — Mission mechanics: direct-on-branch, not lane worktrees (reasonable default)
The mission names LANES topology, but this is a tightly-scoped 2-issue fix on one seam and
the deliverable must land on the single designated branch
`claude/runindex-feature-runs-port-77d5xu`. Spinning up lane worktrees + a mission branch +
consolidation would fight that constraint for no parallelism benefit. Per the escalation
rule this is not an ADR/scope/irreversible fork, so we pick the reasonable default: honour
the SPIRIT (distinct implement/review roles via subagents, tracer files, adversarial squads,
red-first regression tests, empty-allowlist gates, clean history, non-draft PR) while
implementing directly on the topic branch. Recorded here rather than escalated.

## DD-08 — Sibling absolute-path leaks are AUDIT-ONLY here (Stijn directive)
The audit found in-family siblings — chiefly `state.json`'s absolute `template_path` (drift
detection silently skipped on move, HIGH), the run event-log paths, and `review/lock.py`
`worktree_path`. Per directive these are report-only → ONE follow-up issue, not fixed in this
mission, even though `template_path` shares the very state.json the cursor lives in.

## DD-09 — Audit follow-up filed as #5484
The sibling absolute-path leaks (state.json `template_path` drift-skip [HIGH], run
event-log paths, review-lock `worktree_path`, dormant consolidation `workspace_path`)
are tracked in #5484, not fixed here (operator directive). Fix pattern recorded there:
repo-relative token + heal migration + doctor, mirroring this mission's port.
