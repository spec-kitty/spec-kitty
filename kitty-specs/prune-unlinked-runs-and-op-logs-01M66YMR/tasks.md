# Work Packages: Prune unlinked runs and Op-scoped glossary logs

**Mission**: `prune-unlinked-runs-and-op-logs-01M66YMR` · **Issue**: #6739
**Plan**: [plan.md](./plan.md) · **Spec**: [spec.md](./spec.md)

Three work packages, each owning a disjoint set of files, executed in dependency
order on the mission branch `issue-6739-prune-unlinked-runs-and-op-logs`:

1. **WP01** — the one owner for "is this Op open" (`invocation.writer`), so the
   cleanup engine never grows a second copy of the closure rule.
2. **WP02** — the retention engine: link states, unlinked runs, Op-scoped logs
   (depends on WP01's predicate).
3. **WP03** — the surfaces an operator reads: help text (regenerated reference),
   the how-to page and the changelog (depends on WP02's vocabulary).

## Path Conventions

Repository root: `/home/exedev/work/sk-6739` (the mission branch checkout).
Paths below are repository-root relative.

## Work Package WP01: One owner for "is this Op open" (Priority: P0)

**Goal**: `specify_cli.invocation.writer.open_invocation_ids(repo_root)` returns the
ids of the Ops that are still open, computed from the two durable traces (the
per-record `completed` event and the closure spine), and
`specify_cli.doctor.ops.list_orphan_ops` keeps its exact behaviour by calling it.

**Independent test**: `tests/specify_cli/invocation/test_doctor_ops.py` — the new
direct tests for `open_invocation_ids`, plus the existing `list_orphan_ops` tests,
pass unchanged.

### Included Subtasks

- T001 Red-first: direct tests for `open_invocation_ids` (started-only open; `completed` event closes; spine closure closes; `ops-index.jsonl`, `lifecycle.jsonl`, `propagation-errors.jsonl`, `op-closures.jsonl` are not Ops; missing dir → empty set).
- T002 Implement `open_invocation_ids` in `src/specify_cli/invocation/writer.py`, moving the non-Op filename set next to the Op-record layout.
- T003 Route `doctor/ops.list_orphan_ops` through it, keeping the sorted order and the `Path` return type.
- T004 Verify: the whole `test_doctor_ops.py` file, plus `mypy --strict` and `ruff` on the changed files.

### Implementation Notes

The predicate reads each `kitty-ops/*.jsonl` once and returns a `set[str]`, because
the engine calls it once per scan (NFR-001) and must not probe per id. `list_orphan_ops`
must keep returning the same sorted list of record paths that it returns today.

### Parallel Opportunities

None: this WP is a prerequisite for WP02.

### Dependencies

None.

### Risks & Mitigations

The risk is a behaviour change in `doctor ops` (a different open set). The existing
tests in `tests/specify_cli/invocation/test_doctor_ops.py` pin the behaviour; they
are the regression net and must pass untouched.

---

## Work Package WP02: Linked, unlinked and unknown — the retention engine (Priority: P0) 🎯 MVP

**Goal**: `scan_retention` gives an unlinked item an age-only verdict and an
Op-scoped log an Op-state verdict, while a recorded unknown Mission stays protected.

**Independent test**: the engine test file — an old unindexed run whose snapshot
records `inputs.mission_slug` of a merged Mission is a candidate; an old run that
names nothing is a candidate `past retention; no Mission recorded`; an old log of a
completed Op is a candidate `past retention; Op completed`; an old log of an open Op
is kept `Op is open`; a log with no Op record is a candidate `past retention; no Op
recorded`; an old run with an unknown recorded `mission_id` is still kept.

### Included Subtasks

- T005 Red-first: split `test_run_whose_mission_resolves_nowhere_is_kept` so the recorded-unknown and ambiguous shapes stay pinned and the anonymous/unindexed shapes move to their new expectations.
- T006 Red-first: a run started by the real writer, index entry removed, snapshot names the Mission only through `inputs.mission_slug` → candidate once past both limits (and kept as `Mission is open` when the Mission is open).
- T007 Red-first: the Op-log family — closed, open, and no-record cases; `kind == "op_log"`; `_cli`/`_renderer` still absent; `keep_runs` ranks Op logs among Op logs; apply deletes the completed Op's log through the writers' log lock and leaves the Op record and index untouched.
- T008 Implement the link state in `src/specify_cli/state/retention.py`: a tri-state link on the unit, the snapshot slug fallback applied only to a snapshot that records no identity, the unlinked candidate branch and the new reason constants.
- T009 Implement the Op-log family: `KIND_OP_LOG`, its own collector reading the WP01 predicate once per scan, the existing glossary deleter, and the `Op is open` kept reason.
- T010 Update the `_delete_run` docstring residual (the #6739 leftover is now age-pruned) and the module docstring's verdict summary.
- T012 Red-first: the command renders the new vocabulary — an old open Op's log appears under kept reasons as `Op is open`, an old closed Op's log appears under candidates, and the `--json` payload carries `kind: op_log` with the matching reasons (the command test file belongs to this WP, so the rendering test lands here rather than in WP03).
- T013 Verify including the scale assertion: 1,000 Op records and 1,000 glossary logs, one `scan_retention` under 2 s and a byte-identical tree (NFR-001, SC-005); then the engine tests, the command tests, `mypy --strict` and `ruff` on the changed files.

### Implementation Notes

Verdict order is fixed (data-model.md): keep_runs → age → link state → work over →
lock → candidate. The expense order must stay: the link lookup happens only for items
past both limits. `_assert_deletable` and the registry-driven collector selection are
untouched, so drift detection (`retention_policy_drift`) still governs what is scanned.

### Parallel Opportunities

T005–T007 are one red-first commit per behaviour but can be written together; T008
and T009 must not interleave edits in the same function region.

### Dependencies

WP01 (the open-Op predicate).

### Risks & Mitigations

The identity rule must not widen: `inputs.mission_slug` is read **only** for a
snapshot that records no `mission_id` and no `mission_slug`. An unreadable snapshot
stays `unknown` (kept). Add the same-fixture positive control in every test that
asserts a new candidate, so a no-op change cannot pass.

---

## Work Package WP03: The surfaces an operator reads (Priority: P1)

**Goal**: the command's help text, the generated CLI reference, the how-to page and
the changelog describe the new verdicts, so an operator can predict what the command
will delete.

### Included Subtasks

- T014 Update the `event-logs` docstring in `src/specify_cli/cli/commands/_event_logs_doctor.py` for the new eligibility rules.
- T015 Regenerate `docs/api/cli-commands.md` with `uv run python -m scripts.docs.build_cli_reference --write` and confirm `scripts/docs/check_cli_reference_freshness.py` reports clean (never hand-edit the generated block).
- T016 Update `docs/guides/how-to/monitoring/clean-up-local-event-logs.md`: the reasons table, the "what is never removed" list, the run/Op eligibility prose.
- T017 Add the `[Unreleased]` changelog entry in `docs/changelog/CHANGELOG.md` (bold impact-first lead with `(#6739)`, before/after, under 1,200 characters).
- T018 Verify: docs freshness (`check_docs_freshness --ci`), `tests/architectural/test_no_legacy_terminology.py`, the command tests and the CLI reference test.

### Implementation Notes

The command-rendering test is WP02's T012 (it owns
`tests/cli/commands/test_doctor_event_logs.py`); this WP documents the vocabulary that
test pins.

`docs/api/cli-commands.md` is generated from the live Typer surface; the freshness
gate compares it against the app docstring, so the docstring edit and the
regeneration land in the same commit.

### Parallel Opportunities

T016 and T017 are independent of T014/T015.

### Dependencies

WP02 (the vocabulary it documents).

### Risks & Mitigations

Changelog limits are enforced by a gate (length, bold lead, issue reference). The
how-to is the page #6610 introduced; keep its structure and update the tables in
place rather than rewriting the page.

---

## Dependency & Execution Summary

```
WP01 ──▶ WP02 ──▶ WP03
```

All three merge into `issue-6739-prune-unlinked-runs-and-op-logs`; the operator
merges the PR.

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
| --- | --- |
| FR-001 | WP02 |
| FR-002 | WP02 |
| FR-003 | WP02 |
| FR-004 | WP02 |
| FR-005 | WP02 |
| FR-006 | WP02 |
| FR-007 | WP02 |
| FR-008 | WP02, WP03 |
| FR-009 | WP02 |
| FR-010 | WP02 |
| FR-011 | WP02 |
| FR-012 | WP02 |
| FR-013 | WP01 |
| FR-014 | WP03 |
| NFR-001 | WP01, WP02 |
| NFR-002 | WP02 |
| NFR-003 | WP02 |
| NFR-004 | WP02 |
| C-001 | WP02 |
| C-002 | WP02 |
| C-003 | WP02 |
| C-004 | WP01, WP02 |
| C-005 | WP02, WP03 |
| C-006 | WP02 |
| SC-001 | WP02 |
| SC-002 | WP02 |
| SC-003 | WP02, WP03 |
| SC-004 | WP02 |
| SC-005 | WP02 |

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
| --- | --- | --- | --- | --- |
| T001 | Red-first tests for `open_invocation_ids` | WP01 | P0 | No |
| T002 | Implement `open_invocation_ids` in `invocation/writer.py` | WP01 | P0 | No |
| T003 | Route `list_orphan_ops` through the owner predicate | WP01 | P0 | No |
| T004 | WP01 verification (tests, mypy, ruff) | WP01 | P0 | No |
| T005 | Split the pinned "resolves nowhere" engine test | WP02 | P0 | No |
| T006 | Red-first: unindexed run linked only by its snapshot slug | WP02 | P0 | No |
| T007 | Red-first: Op-log family (closed / open / no record) | WP02 | P0 | No |
| T008 | Implement the link state and unlinked verdict | WP02 | P0 | No |
| T009 | Implement the Op-log family | WP02 | P0 | No |
| T010 | Update engine docstrings and the #6739 residual note | WP02 | P1 | Yes |
| T011 | WP02 verification (engine + CLI tests, mypy, ruff) | WP02 | P0 | No |
| T012 | Red-first: command rendering of the new reasons | WP02 | P0 | No |
| T013 | Scale assertion: 1,000 records under 2 s, tree unchanged | WP02 | P0 | No |
| T014 | Update the `event-logs` docstring | WP03 | P1 | No |
| T015 | Regenerate `docs/api/cli-commands.md` and check freshness | WP03 | P1 | No |
| T016 | Update the how-to page | WP03 | P1 | Yes |
| T017 | Add the `[Unreleased]` changelog entry | WP03 | P1 | Yes |
| T018 | WP03 verification (docs freshness, terminology, CLI tests) | WP03 | P1 | No |
