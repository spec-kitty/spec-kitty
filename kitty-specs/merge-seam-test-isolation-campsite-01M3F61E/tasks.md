# Tasks: Merge-seam placement, test-isolation sweep & model-slot verdict

**Mission**: `merge-seam-test-isolation-campsite-01M3F61E` · **Branch**: `issue-5119-merge-seam-test-isolation` (planning base = merge target) · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Research**: [research.md](research.md)

Issues: #5119 (WP02–WP04), #5118 (WP01, WP06–WP14), #5117 (WP05). #5116 parked (not in scope).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Promote the prototype detector to `tests/architectural/_global_state_scan.py` | WP01 | |
| T002 | Gate `test_no_manual_global_state_mutation.py` (verdicts 1–6, actionable messages) — commit RED with empty allowlist | WP01 | |
| T003 | Detector self-mutation tests (planted + aliased forms, negative controls) | WP01 | [P] |
| T004 | Generate permanent shards `S1..S8.yaml` + `deferred-01M3EW3Z.yaml` — gate GREEN | WP01 | |
| T005 | Vacuity/cost checks (floor, drop-one-row, <10 s) + coexistence with home-pin gates | WP01 | |
| T006 | Full `tests/architectural/` + ruff/mypy | WP01 | |
| T007 | Delete the duplicate blob reader; import the canonical one | WP02 | |
| T008 | Inventory navigation refresh (git_probes docstring fix moves to T018 — WP04 owns `git_probes.py`) | WP02 | [P] |
| T009 | Single-definition guard test + merge suites | WP02 | |
| T010 | Golden case fixtures for all six drivers | WP03 | |
| T011 | Golden capture helper (subprocess, temp HOME, normalized paths) | WP03 | |
| T012 | `test_merge_driver_goldens.py` — subprocess + in-process legs | WP03 | |
| T013 | All-six-resolve replay test | WP03 | [P] |
| T014 | Site-level import collector in `test_layer_rules.py` (relative / submodule / dynamic string) | WP04 | |
| T015 | `TestMergeCliBoundary` + console ledger + self-mutation — commit RED | WP04 | |
| T016 | Create `src/specify_cli/merge/drivers.py` (six bodies, error/outcome types, table) | WP04 | |
| T017 | Thin CLI shell `cli/commands/merge_driver.py` | WP04 | |
| T018 | Resolver in `git_probes.py` → `MERGE_DRIVER_BODIES` | WP04 | |
| T019 | Completeness + focused unit tests for `drivers.py` | WP04 | |
| T020 | Re-point tests/monkeypatch target, re-pin inline-meta gate, docstrings | WP04 | |
| T021 | Goldens unchanged, full `tests/architectural/`, ruff/mypy, import cost | WP04 | |
| T022 | `model` field description in `schema_models.py`; regenerate schema | WP05 | |
| T023 | Disk → repository → `_compute_recommendation` test | WP05 | |
| T024 | Mutation proof + doctrine/schema suites | WP05 | |
| T026–T030 | Sweep shard S1 — charter CLI (54 sites / 7 files) | WP06 | |
| T031–T035 | Sweep shard S2 — widen/decision CLI (64 / 10) | WP07 | |
| T036–T040 | Sweep shard S3 — doctrine/doctor/upgrade CLI (52 / 6) | WP08 | |
| T041–T045 | Sweep shard S4 — misc CLI (48 / 12) | WP09 | |
| T046–T050 | Sweep shard S5 — other `tests/specify_cli` (49 / 20) | WP10 | |
| T051–T055 | Sweep shard S6 — import hygiene: docs/architectural/release/scripts/ci/lint (58 / 46) | WP11 | |
| T056–T060 | Sweep shard S7 — integration + research (51 / 12) | WP12 | |
| T061–T065 | Sweep shard S8 — remaining dirs incl. root `conftest.py` (79 / 37) | WP13 | |
| T066 | Sealed-invariant test (no transitional rows; frozen per-class caps) | WP14 | |
| T067 | Seal self-mutation tests | WP14 | |
| T068 | Final census report + full architectural/fast-tier runs | WP14 | |

(T025 intentionally unused.)

---

## Phase 1 — Foundations (parallel: WP01, WP02, WP03, WP05)

### WP01 — Census gate for manual global-state mutation in tests (#5118)

- **Goal**: A non-vacuous, content-keyed, shrink-only AST census gate over every `*.py` under `tests/`, landed RED first, then GREEN over permanent per-shard allowlists.
- **Priority**: P1 · **Independent test**: `pytest tests/architectural/test_no_manual_global_state_mutation.py` — red with an empty allowlist (471 sites), green with shards; a planted `os.chdir` fails it.
- **Subtasks**:
  T001 Promote the prototype detector to `tests/architectural/_global_state_scan.py` (WP01)
  T002 Gate test with verdicts 1–6 + actionable messages, committed RED with an empty allowlist (WP01)
  T003 Detector self-mutation tests incl. aliased forms and negative controls (WP01)
  T004 Generate permanent shards `S1..S8.yaml` + `deferred-01M3EW3Z.yaml`; gate GREEN (WP01)
  T005 Vacuity/cost checks + coexistence with `_home_pin_scan` seam gates (WP01)
  T006 Full `tests/architectural/` run + ruff/mypy (WP01)
- **Dependencies**: none. **Estimated prompt**: ~450 lines.
- **Risks**: `_home_pin_scan` second-copy / verdict-seam gates (keep allowlist I/O + comparisons in the gate file; no "census"/"baseline" in YAML paths); ratchet-owned registry files are off-limits (C-002/C-007).

### WP02 — Single raw git blob reader in the merge domain (#5119)

- **Goal**: One blob reader (`merge/git_probes.py::_read_git_blob_bytes`); `bookkeeping_projection` reuses it.
- **Priority**: P1 · **Independent test**: single-definition guard + `tests/merge` green; `git_probes.py:236` census pin unchanged.
- **Subtasks**:
  T007 Delete `_git_show_blob_bytes` + unused `subprocess` import; import and use the canonical reader (WP02)
  T008 Refresh `tests/architectural/tool_artifact_enrolment/inventory.md` navigation lines (the git_probes L609 docstring fix is done in WP04/T018 — WP04 owns `git_probes.py`) (WP02)
  T009 Single-definition guard test + merge/architectural blast radius (WP02)
- **Dependencies**: none. **Estimated prompt**: ~220 lines.

### WP03 — Golden characterisation of the six merge drivers (#5119)

- **Goal**: Byte-level goldens for all six registered drivers via subprocess and in-process replay, captured on today's code; all six resolvable in replay.
- **Priority**: P1 · **Independent test**: `pytest tests/merge/test_merge_driver_goldens.py` green on the pre-move code.
- **Subtasks**:
  T010 Golden case fixtures (≥3 cases + 1 path-injection per driver) (WP03)
  T011 Capture helper: subprocess `python -m specify_cli merge-driver-X`, temp HOME, `<TMP>` normalization (WP03)
  T012 `tests/merge/test_merge_driver_goldens.py` — subprocess + in-process legs (WP03)
  T013 All-six-resolve replay test (WP03)
- **Dependencies**: none. **Estimated prompt**: ~350 lines.

### WP05 — `model` slot keep-verdict and end-to-end proof (#5117)

- **Goal**: The `model` slot is documented as consumer-authored in its canonical source and pinned from a profile YAML on disk to the dispatch routing advisory.
- **Priority**: P2 · **Independent test**: new test in `tests/doctrine/test_agent_profile_model_field.py` passes; fails when the alias is removed; `generate_schemas.py --check` clean.
- **Subtasks**:
  T022 Add `description=` to `schema_models.py` `preferred_model` (+ mirror comment in `profile.py`); regenerate `agent-profile.schema.yaml` (WP05)
  T023 Disk → `AgentProfileRepository` → `invocation.executor._compute_recommendation` test (WP05)
  T024 Mutation proof + doctrine/schema suites (WP05)
- **Dependencies**: none. **Estimated prompt**: ~220 lines.

## Phase 2 — Merge seam relocation

### WP04 — Merge → CLI-command-layer rule and driver-body relocation (#5119)

- **Goal**: The merge domain stops importing the CLI command layer; all six driver bodies live in `merge/drivers.py`, shared by the subprocess entrypoint and the in-process replay.
- **Priority**: P1 · **Independent test**: `TestMergeCliBoundary` red before the move (naming `git_probes.py:667`) and green after; goldens byte-identical.
- **Subtasks**:
  T014 Site-level import collector (relative, `from X import sub`, literal-string dynamic imports); existing ledgers unchanged (WP04)
  T015 `TestMergeCliBoundary` + `_MERGE_CLI_CONSOLE_IMPORTERS` ledger + stale guard + self-mutation; commit RED (WP04)
  T016 Create `merge/drivers.py`: `MergeDriverError`, `MergeDriverOutcome`, six bodies, `MERGE_DRIVER_BODIES` (WP04)
  T017 Thin CLI shell (same six function names/signatures) (WP04)
  T018 Resolver → `MERGE_DRIVER_BODIES` via function-local import; stale `typer.Exit` comment + L609 blob-reader docstring fix (WP04)
  T019 Completeness test (table == registry == registrars) + focused unit tests for new branches (WP04)
  T020 Re-point pure-logic imports + the `monkeypatch` target; re-pin `test_inline_meta_read_gate.py` (qualname-existence assert); docstrings (WP04)
  T021 Goldens diff empty; full `tests/architectural/`; ruff/mypy; import-cost check (WP04)
- **Dependencies**: WP02, WP03. **Estimated prompt**: ~600 lines.
- **Risks**: `git_probes.py:236` pin (edit only below L236); stderr byte-identity (`str(exc)`; do not broaden catches); diff-cover on ~950 moved lines; C-002 exception scope (only the inline-meta pin).

## Phase 3 — Test-isolation sweep (parallel lanes after WP01)

Every sweep WP follows the same procedure on its fixed file set (`research/sweep_shards.tsv`), using per-site fix classes from `research/global_state_sites_classified.tsv`:

1. Capture junit-xml for the shard's files on the WP base.
2. Convert class A sites (`monkeypatch.*`, autouse fixtures).
3. Convert class B sites (`contextlib.chdir`, `mock.patch.dict`/`patch.object`).
4. Handle class C/D sites (`MonkeyPatch.context()`, redundant import-time `sys.path` inserts, canonical imports); confirm E rows stay justified or convert them.
5. Drain the shard's `transitional-sweep` rows (recorded out-of-map edit of exactly `tests/architectural/global_state_allowlist/S<n>.yaml`), run the gate, compare junit-xml, run under `-n auto --dist loadfile`, ruff format/check.

### WP06 — Sweep S1: charter CLI tests (54 sites / 7 files)
- **Subtasks**: T026 baseline capture · T027 class A · T028 class B · T029 class C/D + E review · T030 drain + verify (WP06)
- **Dependencies**: WP01. **Estimated prompt**: ~300 lines.

### WP07 — Sweep S2: widen/decision CLI tests (64 / 10)
- **Subtasks**: T031 baseline capture · T032 class A · T033 class B · T034 class C/D + E review · T035 drain + verify (WP07)
- **Dependencies**: WP01. **Estimated prompt**: ~300 lines.

### WP08 — Sweep S3: doctrine/doctor/upgrade CLI tests (52 / 6)
- **Subtasks**: T036 baseline capture · T037 class A · T038 class B · T039 class C/D + E review · T040 drain + verify (WP08)
- **Dependencies**: WP01. **Estimated prompt**: ~300 lines.

### WP09 — Sweep S4: misc CLI tests (48 / 12)
- **Subtasks**: T041 baseline capture · T042 class A · T043 class B · T044 class C/D + E review · T045 drain + verify (WP09)
- **Dependencies**: WP01. **Estimated prompt**: ~300 lines.

### WP10 — Sweep S5: other `tests/specify_cli` (49 / 20)
- **Subtasks**: T046 baseline capture · T047 class A · T048 class B · T049 class C/D + E review · T050 drain + verify (WP10)
- **Dependencies**: WP01. **Estimated prompt**: ~320 lines.

### WP11 — Sweep S6: import hygiene in docs/architectural/release/scripts/ci/lint tests (58 / 46)
- **Subtasks**: T051 baseline capture · T052 class A · T053 class B · T054 class C/D (redundant inserts, canonical `scripts.*` imports) + E review · T055 drain + verify (WP11)
- **Dependencies**: WP01. **Estimated prompt**: ~340 lines.

### WP12 — Sweep S7: integration + research tests (51 / 12)
- **Subtasks**: T056 baseline capture · T057 class A · T058 class B · T059 class C/D (22 research `sys.path.insert`) + E review · T060 drain + verify (WP12)
- **Dependencies**: WP01. **Estimated prompt**: ~320 lines.

### WP13 — Sweep S8: remaining dirs incl. root `conftest.py` (79 / 37)
- **Subtasks**: T061 baseline capture · T062 class A · T063 class B · T064 class C (`test_venv` → `MonkeyPatch.context()`) /D + E review · T065 drain + verify incl. full `tests/architectural/` (cross-cutting conftest) (WP13)
- **Dependencies**: WP01. **Estimated prompt**: ~360 lines.

## Phase 4 — Seal

### WP14 — Seal the census allowlist (#5118)

- **Goal**: Freeze the end state: no `transitional-sweep` rows anywhere, per-class caps frozen at the actual post-sweep counts (never above process-bootstrap 6, subprocess-entry 13, leak-sentinel 2, deferred-01M3EW3Z 16).
- **Subtasks**:
  T066 `tests/architectural/test_global_state_allowlist_sealed.py` (WP14)
  T067 Seal self-mutation tests (planted transitional row / over-cap on a tmp copy) (WP14)
  T068 Final census report (471 → N) in the Activity Log; full `tests/architectural/` + `make test-fast` (WP14)
- **Dependencies**: WP02, WP03, WP04, WP05, WP06, WP07, WP08, WP09, WP10, WP11, WP12, WP13 (WP01 transitively). The lane is cut at the mission base, so T066 first stacks WP01 + WP02..WP13 (cherry-pick in order; files disjoint) and verifies the gate, `test_layer_rules`, the goldens and `test_home_owner_behaviour` before sealing. **Estimated prompt**: ~250 lines.

## Dependency summary

```
WP01 ─┬─> WP06..WP13 ──┐
WP02 ─┐                 │
WP03 ─┴─> WP04 ─────────┼──> WP14 (stacks all lanes, then seals)
WP05 ───────────────────┘
(WP04 T021 also stacks the WP02 + WP03 lanes before verifying — multi-dependency lanes are cut at the mission base.)
```

## Orchestrator notes (before and after implement)

- **Issue matrix**: before the first `implement`, the orchestrator creates issue-matrix rows for #5119, #5118, #5117 (claimed, verdict slot open) and #5116 (parked — `not-applicable` to this mission; blocked on #2633 and ratchet WP11).
- **Tracer files**: every WP appends dated entries to `tracer-*.md` as friction/decisions occur; the orchestrator commits them in the lifecycle trail.
- **No CHANGELOG entry**: the mission is internal (C-001 holds; no user-facing change; no `__init__.py` touched). Reviewers must not reject a WP for a missing CHANGELOG entry.
- **Census-blind lanes**: WP02–WP05 lanes do not contain WP01's gate until consolidation; their prompts require zero manual global-state mutation in new/changed tests, verified with the prototype scanner.
- **Closeout (§5 rebase)**: after rebasing onto `upstream/main`, re-run `tests/architectural/test_no_manual_global_state_mutation.py`. If mission `01M3EW3Z` has landed, its edits may change the deferred files' site counts — **shrink** (never raise) the `deferred-01M3EW3Z.yaml` rows to match, or move rows out if the files are no longer ratchet-owned; keep WP04's `test_inline_meta_read_gate.py` hunk minimal so the rebase over ratchet WP13 is trivial.

## Commit-history plan (§5)

The repo lands commits individually (rebase-merge), so no commit on the final branch may be red. The per-lane RED commits (WP01 commit A; WP04 T015) are folded at branch cleanup into a green-cut snapshot chain (not reordered, cut only at green states; verify the census gate, `test_layer_rules` and the goldens at each cut):

1. WP01 — census gate + detector + shards (RED commit folded in)
2. WP02 — single blob reader
3. WP03 — merge-driver goldens
4. WP04 — merge→CLI rule + driver-body move (RED rule commit folded in; its failing assertion quoted in the commit body)
5. WP05 — `model` slot verdict
6. WP06–WP12 — sweeps S1–S7
7. WP13 — sweep S8 + root `conftest.py` (kept separate for bisect)
8. WP14 — seal
9. Mission bookkeeping (lifecycle trail, tracer files, issue matrix)

Rebuild with `git add -f kitty-specs/<slug>/` where artifacts are gitignored; the rebuilt tree must be byte-identical to a backup of the pre-cleanup head. Red-first evidence lives in each WP's Activity Log and in the PR's "red-first evidence" section.

## Requirement coverage

| WP | Requirements |
|----|--------------|
| WP01 | FR-007, FR-008, FR-009, NFR-004, NFR-005, C-006, C-007 |
| WP02 | FR-001 |
| WP03 | NFR-001 |
| WP04 | FR-002, FR-003, FR-004, FR-005, C-001, C-002, C-008 |
| WP05 | FR-010, FR-011 |
| WP06–WP13 | FR-006, NFR-002, C-005 |
| WP14 | NFR-003, FR-008 |
| all | NFR-006, C-009 |
