# Data Model: CI Terminal-Cancel Verdict

No persistent storage. In-process values of two pure functions.

## 4a — `classify(runs, labels) -> str` (edit)

**Inputs:** `runs: dict[str, dict|None]` (required-gate name → GitHub run object or None if absent); `labels: set[str]` (PR labels).
**Output:** one of `"red" | "running" | "green" | "infra-error"` (`infra-error` is NEW).

### Precedence (each returns immediately)
| # | Rule | Result |
|---|------|--------|
| 1 | any present run `status=="completed"` and `conclusion ∈ {failure,timed_out,startup_failure,action_required}` | `red` |
| 2 | `labels ∩ {pr:deferred, pr:skip-ci}` | `running` |
| 3 | `not runs` or `len(present) != len(runs)` (a required run absent) | `running` |
| 4 (NEW) | `all(r.status=="completed" for r in present)` **AND** `any(r.conclusion=="cancelled" for r in present)` | `infra-error` |
| 5 | all present `completed`/`success` → `green`; else `running` | `green`/`running` |

### Invariants (testable)
- **INV-1 never-green:** `infra-error ⇒ ∃ run.conclusion=="cancelled"`; an all-`success` set has none ⇒ `green`, never `infra-error`. (green path unchanged)
- **INV-2 never-premature:** `{cancelled, in_progress}` → `running` AND `{cancelled, absent}` → `running` (rule 3 / the all-completed conjunct).
- **INV-3 red dominates:** `{failure, cancelled}` → `red` (rule 1 before rule 4).
- **INV-4 deferred respected:** `{cancelled}` + `pr:skip-ci` → `running` (rule 2 before rule 4).
- **INV-5 skipped≠cancelled:** `{skipped, success}` → `running` (rule 4 needs `cancelled`, not "not-green").
- **Main coherence:** `infra-error` at `fleet_main.report` ⇒ NO `issues` mutation (P0 gate keys on `"red"`).

## 4b — `find_stale_running(...) -> list[StaleHead]` (new)

**Inputs (injected):** per candidate head — `head_sha`, `latest_verdict` (the `[ci] <state> @<sha>` state or None), `required_runs: list[run]`, and any existing `[ci-sweep]` marker/fingerprint.
**StaleHead:** `{subject (pr#|"main"), head_sha, reason}`.

### Detection rule
A head is **stale-running** iff: `latest_verdict == "running"` for `head_sha` AND `required_runs` non-empty AND `all(r.status=="completed" for r in required_runs)` (every required run terminal, incl. `cancelled`).
- NOT stale if latest verdict is terminal (green/red/infra-error) — the reporter already released.
- NOT stale if any required run is non-terminal (evidence still pending).

### Invariants
- **SW-1 (backstop only):** the surface is a `[ci-sweep]`-namespaced watch comment/annotation, NEVER a `[ci] <state> @head` verdict; never edits reporter comments; never re-triggers CI.
- **SW-2 idempotent:** a re-run against an already-flagged stale head produces no duplicate surface (fingerprint dedup).
- **SW-3 fail-closed:** ambiguous/partial evidence → not flagged (no false watch item).
