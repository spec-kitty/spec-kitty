# Pre-compaction commit references

This mission's branch (`issue-5189-per-pr-shard-timings-recapture-friction`, 72+
commits over an older `main`, including two merges of `origin/main`) was never
pushed. Per the charter's readable-PR directive and the operator's username-leak
policy (an absolute `/home/<user>` path was committed in `ba579634e` and redacted
later in `b792f8533`), the branch actually opened as a PR (`issue-5189-pr-compact`)
was built fresh: a new branch cut from the current `origin/main`, carrying this
mission's changes re-applied as a small number of clean, logically-sliced,
Conventional-Commits-conforming commits, with every review-cycle/status-transition/
scaffold commit compressed into the substantive commit it belongs to.

As a result, every SHA the review trail (`reviews/*.yaml`, `tracer-*.md`,
`analysis-report.md`, `status.events.jsonl`, etc.) cites from the old branch now
dangles — it exists only in local history (or on the still-local
`origin/kitty/mission-per-pr-shard-timings-recapture-friction-01M3H7V8-lane-a`
branch) and was never pushed. This file maps each such SHA to what actually
carries that change on the pushed branch.

## How to read the table

- **New commit** — the commit on the pushed branch that carries the same content.
- **"bookkeeping, folded"** — a pipeline status/administrative commit (a
  `status.json` / `status.events.jsonl` transition record, a per-WP review-cycle
  record) with no independent code or doc content; its net effect is captured
  inside the mission-artifact commit named alongside it.
- **"net-zero, folded"** — a commit and its own revert that cancel out; the final
  content is exactly as if neither had happened, and that final content is what
  the named commit carries.

## Commits still valid on `origin/main`

These SHAs were already commits on `origin/main` (this mission's own earlier work,
already-merged prerequisites, or unrelated history) before the rebuild, and are
cited correctly as-is; no mapping needed.

| SHA | Subject |
|---|---|
| `4a036b905` | docs(friction): record per-PR shard-timings recapture friction |
| `5469c4d77` | ci(tests): make shard-timings count drift non-blocking per PR (#5189) |
| `b17a81506` | Refresh stale pinning-rule inventory and declare ci-stale-running-sweep.yml (red main) (#4667) |
| `cc788d50e` | docs(landing): record the gate deletion as an ADR amendment and cite #3285 |
| `e2dcf69c8` | test(ci): recapture charter shard timings against current main |

## Commits from the old local mission branch (now dangling)

| Old SHA | One-line subject | Maps to |
|---|---|---|
| `9fb510b5f` | feat(...): squash merge of mission (WP01/WP02/WP03 lane squash-merges) | Split across `e6b9c0f78` `chore(tests): fix mypy no-any-return in _resolve_test_dirs (WP01 T007)`, `a439f4ed2` `test(architectural): red-first tests for the #5240 shard-timings drift demotion (WP01)`, `5bc6623e1` `feat(ci): recapture charter shard timings script and coverage (WP02)`, `227ff46ab` `ci(shard-timings): schedule the charter recapture workflow (WP03)`, `05ba48e7a` `test(architectural): register the charter recapture workflow in the CI gates` |
| `17493143c` | feat(ci): add charter shard-timings recapture decision script (WP02) | `5bc6623e1` `feat(ci): recapture charter shard timings script and coverage (WP02)` |
| `0e8e7ad9a` | test(architectural): isolate warning-emission tests from strict shard-timings env | `a439f4ed2` `test(architectural): red-first tests for the #5240 shard-timings drift demotion (WP01)` (isolation fix folded in) |
| `186143daf` | test(ci): cover a subprocess failure at every push/open step | `4615ee291` `fix(ci): fail loudly on malformed gh CLI output and subprocess failures` |
| `d6a225c69` | test(architectural): register ci-charter-shard-recapture.yml in the workflow registries | `05ba48e7a` `test(architectural): register the charter recapture workflow in the CI gates` |
| `054b6434d` | docs(friction): note per-pr shard-timings friction superseded by #5189 | `227ff46ab` `ci(shard-timings): schedule the charter recapture workflow (WP03)` |
| `4a0e0cde1` | spec: per-PR charter shard-timings recapture friction (#5189) | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` |
| `7fafd7e35` | fix(spec): round 2 — final allowlist-count sweep, marker consistency, secret-check timing | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` |
| `cfb79841e` | fix(spec): round 2 — final allowlist-count sweep, marker consistency, secret-check timing | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` |
| `b0dda19ea` | fix(spec): round 3 — resolve FR-007/FR-010 marker-identity tension | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` |
| `c00c97591` | test(review): commit round-3 fresh-sweep + verify trail (HALT — SPEC-FRESH3-001 sev4 survives) | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` |
| `a117695b5` | docs(plan): author per-pr-shard-timings-recapture-friction plan; close out ruling-2 re-entry (PASSED) | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` |
| `b893ce5c7` | Add tasks for feature per-pr-shard-timings-recapture-friction-01M3H7V8 | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` |
| `ac925fffc` | fix(tasks): engage subtask-ceiling guideline for WP01, fix T011 gh pr list json fields, recount WP02 line total | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` |
| `9efd2ec77` | fix(tasks): supersede plan.md's stale gh pr list sample, add WP01 prompt-file line count | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` |
| `4983c561d` | fix(tasks): run WP03 recapture job in the synced uv environment (AMENDMENT-FRESH-001) | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` |
| `423463a10` | docs(record-analysis): record analysis report for mission per-pr-shard-timings-recapture-friction-01M3H7V8 | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` |
| `f8dcce82a` | docs(record-analysis): record analysis report for mission per-pr-shard-timings-recapture-friction-01M3H7V8 | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` |
| `14a7ef69c` | docs(tracer): record WP01's global_assets race (ledger SK-243) | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` |
| `7cc42e945` | docs(tracer): record WP02 tooling friction | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` (net-zero, folded — see below) |
| `472616135` | Revert "docs(tracer): record WP02 tooling friction" | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` (net-zero, folded — see below) |
| `90f6c2645` | chore: remove planning artifacts from lane branch | `148d5d22a` `spec(5189): mission design — spec, plan, tasks, analysis and review trail` (bookkeeping, folded) |
| `353c6742b` | chore: merge origin/main into issue-5189 branch before pre-merge review | compacted out — superseded by rebasing the new branch directly onto the current `origin/main` |
| `d3169133b` | test(review): record pre-merge squad trail (R1-R3, 5 confirmed findings) | `3edf9cf79` `test(review): implementation review trail and mission bookkeeping` |
| `0026722d9` | chore(review): persist WP03 approval review-cycle record and status | `3edf9cf79` `test(review): implementation review trail and mission bookkeeping` (bookkeeping, folded) |
| `9d83c7ed1` | chore(spec-kitty): status transition WP03 | `3edf9cf79` `test(review): implementation review trail and mission bookkeeping` (bookkeeping, folded) |

Every `chore(spec-kitty): status transition WP0*` / `chore(review): persist WP0*
approval review-cycle record` commit on the old branch not individually listed
above is the same kind of bookkeeping, folded the same way into
`3edf9cf79` `test(review): implementation review trail and mission bookkeeping`.

## Net-zero pair: `7cc42e945` / `472616135`

`reviews/wp-WP02.yaml` itself records (line 20-21) that "the tracer commit
`7cc42e945` and its revert `472616135` net to zero on `kitty-specs/` ... producing
the exact inverse patch." The rebuilt branch's design commit carries the final,
correct tracer content (the WP01 `global_assets` race entry recorded properly on
the planning branch via `14a7ef69c`), which is the state both commits were
converging on.

## Non-commit hex/numeric strings in the review trail

`grep -rhoE '\b[0-9a-f]{7,40}\b'` over the mission directory also matches strings
that look like SHAs but are not commit ids in this repository. Listed for
completeness; no mapping needed.

| Value | What it actually is |
|---|---|
| `1790559121`, `1790559123`, `1790577358` | Unix epoch `shell_pid_created_at` timestamps in `status.json` / `status.events.jsonl` |
| `2603568`, `2603799` | Recorded `shell_pid` values in `status.json` / `status.events.jsonl` |
| `34285209` | The `MOES-Media` GitHub numeric user id (part of the `actor` email in `status.events.jsonl`'s `MissionCreated` event) |
| `8a4a7da6`, `b31664abfee4` | Fragments of `project_uuid` (`8a4a7da6-a97c-4bb4-893a-b31664abfee4`) recorded in `status.events.jsonl`, not a commit |
| `08c6903cd8c0fde910a37f88322edcfb5dd907a8` | `actions/checkout@v5.0.0`'s pinned SHA (an upstream `actions/checkout` commit, not one in this repository) cited in `plan.md` / `analysis-report.md` |
| `20cfd1bf945f4377ade1205e4dbc17946fc9a30d` | `astral-sh/setup-uv@v10.0.1`'s pinned SHA (an upstream `astral-sh/setup-uv` commit, not one in this repository) cited in `analysis-report.md` |
