# Contract: CLI Behavior for Handle Resolution

# round-trip: skip: prose behavior contract, not a serialized fixture

Behavioral contracts for the in-scope commands. Message text below is the target
canonical form; `<handle>` is the verbatim user-supplied handle. Exit codes are
non-zero for every error path (never a `typer.BadParameter` / "Invalid value"
usage error for a resolution outcome).

## C1 — Nonexistent handle (all in-scope commands)

**Given** a workspace with ≥1 real mission and a handle `H` matching none of them.

| Command | Before (defect) | After (contract) |
|---------|-----------------|------------------|
| `research --mission H` | scaffolds `kitty-specs/H/`, exits 0 | `Mission not found: H`, non-zero, **no filesystem change** (human-only; no `--json`) |
| `plan --mission H` | `N missions found, pass --mission to disambiguate` | `Mission not found: H`, non-zero (JSON parity) |
| `tasks --mission H` | same disambiguate message | `Mission not found: H`, non-zero (JSON parity) |
| `merge --mission H` (fresh) | `lanes.json is required … run task-finalization` | `Mission not found: H`, non-zero (human; `--json` is dry-run-only) |
| `merge --resume --mission H` | `No interrupted merge to resume` | `Mission not found: H`, non-zero — the unknown-handle refusal pre-empts the no-state message |
| `next --mission H` | already clean not-found | keeps its richer `_emit_mission_not_found_error` envelope (names H) |
| `materialize --mission H` | already clean `Mission not found: H` | unchanged (this is the exemplar) |
| resolver error (accept/review/audit) | `No mission found for handle "H"` + backfill remediation | **unchanged** — keeps FR-005 `backfill-identity` remediation |
| `reconcile --mission H` | `mission dossier not found: H` | **unchanged** — semantically distinct |

- **JSON parity (FR-011, scoped)**: only where a JSON surface exists — `next`,
  the plan/tasks agent commands, materialize — emit a structured error object
  carrying the error kind and the handle. research (no `--json`) and merge
  (dry-run-only `--json`) are out of the parity claim.
- **Snapshot invariant (NFR-001)**: for every row, a byte-for-byte listing of
  `kitty-specs/` is identical before and after (assert via in-process
  `CliRunner`).

## C2 — Path-unsafe handle (unchanged)

**Given** `--mission ../x` (or any unsafe segment): the existing path-safety
refusal fires (`Mission slug is not a single safe path segment` or equivalent).
This is a **distinct** error from C1 and is **not** converted to "mission not
found".

## C3 — Ambiguous handle (unchanged)

**Given** a handle prefix matching >1 mission: the existing structured
ambiguous-selector error (`MISSION_AMBIGUOUS_SELECTOR`) fires — distinct from C1.

## C4 — `merge --abort` tolerance (preserved)

**Given** `merge --abort --mission H` where `H` is unresolvable during a broken
coordination cleanup: abort remains tolerant (non-raising), completing
coordination teardown. The C1 not-found gate applies only to the fresh/resume
entry, never to `--abort`.

## C5 — `next` with a *missing* `--mission`

**Given** `next` invoked with no `--mission`:

| Mission count | Contract |
|---------------|----------|
| exactly 1 | auto-select that mission and proceed as if its handle were passed |
| >1 | print each mission as `mission_slug (mid8) — friendly_name`, ask to re-run with `--mission <handle>`, exit non-zero (non-usage) |
| 0 | print "no missions found" + point to the specify command, exit non-zero |

- **No usage error**: none of these is a `typer.BadParameter` / "Invalid value".
- **JSON parity**: `--json` yields the same outcome; the >1 case includes
  `available_missions: [{mission_slug, mid8, friendly_name}, …]`.
- **Regression**: `next --mission H` with a nonexistent-but-present handle still
  yields C1's clean not-found (the missing-handle change must not regress the
  bad-handle path).

## C6 — Canonical message shape (scoped)

`Mission not found: <handle>` (capital M, matching the `materialize` exemplar) —
one source constant, handle verbatim, adopted by the FIXED commands (plan, tasks,
research, merge fresh/resume) and reused by `next`. **Excluded** (keep richer
envelopes): the identity-aware resolver error (`No mission found for handle
"<h>"` + `spec-kitty migrate backfill-identity` remediation, FR-005),
`reconcile`'s "mission dossier not found", and audit/doctor. NFR-002 measures
that the fixed commands route through the one constant — not byte-identity across
the whole CLI.
