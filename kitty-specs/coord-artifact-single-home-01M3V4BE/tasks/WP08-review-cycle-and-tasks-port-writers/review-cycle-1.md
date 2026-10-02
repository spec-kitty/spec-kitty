---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-02T02:11:05Z'
reviewer_agent: claude
wp_id: WP08
---

# WP08 review, cycle 1: changes requested

Reviewer: claude (reviewer-renata, opus). Lane-f tip `ff74a9800a`. Diff base `7d473689c7` (the lane-o merge).

The core of the change is sound:

- The `_review_cycle_wp_dir` default flips to REVIEW_CYCLE, and every reader moves with it. Reverting the default turns 4 tests red, including the co-resolution guard and the CLI test that renders fix mode after a rejection.
- Review cycles are now written in place, and `checkout_root` is threaded into `_evidence_ref`. Reverting that threading turns 16 tests red.
- mark-status now writes through `feature_write_dir`. Reverting it turns 1 test red.
- A refused surface hidden behind a top-level `committed` status is now caught. Removing the check turns 1 test red.

Four items block approval.

## Blocking

### B1: new red test, green at base and undisclosed

`tests/agent/test_workflow_review_cycle_pointer.py::test_coord_status_state_split_resolves_feedback_file_contents` fails:

| Checkout | Result |
|---|---|
| base `7d473689c7` | 10/10 pass |
| HEAD | `assert None is not None` ("coord-partition rejection record must resolve to a readable artifact") |

The test writes `review-cycle-1.md` into the PRIMARY Mission dir (the physical home before WP08), appends a `review_ref` event on the coordination log, and calls `workflow_cores.latest_review_feedback_reference(ctx.primary_feature_dir, "WP01")`. Since the default flip, the `review-cycle://` pointer resolves under the coordination dir, where the file does not exist.

This is either a stale fixture or a real backward-compatibility gap, and you have to decide which. Missions that were rejected before WP08 committed their cycle onto the coordination branch through the stage-in-root-then-copy path, so their coordination copy exists. A **local-only** rejection is different: `--no-auto-commit` or `commit_router=None` produces a `local_only` outcome. In that case the old cycle exists only in the PRIMARY root checkout, and `has_prior_rejection` and the fix-mode render now miss it. A missed rejection there is fail-open.

**Required:** pick one, record the decision through tracer-append, and pin it with a test.

- (a) Make reads of a coordination-routed Mission tolerate an old PRIMARY-only cycle: if the coordination copy is missing, look in PRIMARY.
- (b) Re-pin this test, stale → re-pin with a one-line rationale, and record that old PRIMARY-only local cycles are no longer seen, as an accepted residual with an operator ruling.

Either way, the WP08 report must list this file. It is not on the re-pin list.

### B2: `markup=False` prints the markup tags literally

`tasks_map_requirements.py:668` runs `_tasks.console.print(f"[yellow]Warning:[/yellow] {line}", markup=False)`. With `markup=False`, Rich prints the tags as text, so the operator sees `[yellow]Warning:[/yellow] ✗ coordination (...): refused — ...: STATUS_LOCK_HELD`. I confirmed this with a real `rich.Console`.

The test does not catch it because it monkeypatches `console.print` and only checks for a substring.

**Required:**

- Style the prefix without parsing markup in the rendered line. Either use `Text.assemble(("Warning: ", "yellow"), line)`, or print the prefix with markup and the line with `markup=False`.
- Assert on real console output, for example `Console(record=True)` or capsys against the real console, and check that no `[yellow]` survives.

### B3: outcomes are not rendered on every arm (contract rule 5, T046 step 1, your ruling)

**`review/cycle.py::_commit_review_cycle_artifact`** calls `render_commit_outcome` only in the masked-refusal arm.

- The `durable` arm drops `result.surfaces`.
- The non-committed arms (`unchanged`, `no_op_wrong_surface`, `error`, and `commit_failed`) build their message from `result.diagnostic` alone, through `_commit_failure_message`.
- T046 step 1 requires a `COORD_RECORD_IN_ROOT_CHECKOUT` skip on the coordination group to show up in the message. No arm does that today.

**`tasks_map_requirements._mr_render_refused_surfaces`** renders only when `commit_outcome_exit_code != 0`. Contract rule 5 says "`skipped` and `unchanged` exit 0 and are rendered". D8 says a site that discards the result warns whenever a surface is not committed or unchanged, so a `skipped` surface must render too.

**The masked-refusal message** reaches the operator through `tasks_move_task._output_error`, which prints `f"[red]Error:[/red] {error_message}"` with markup on. Today's rendered lines contain no lowercase `[tag]` tokens, so this is latent rather than live. Your rule still applies: the rendered lines must print with `markup=False`.

**Required:**

- Every arm of `_commit_review_cycle_artifact` carries `render_commit_outcome(result)` lines in `VerdictPersistenceOutcome.message`.
- The map-requirements site renders `skipped` as well as `refused`/`error`.
- Add tests for a `skipped(COORD_RECORD_IN_ROOT_CHECKOUT)` surface and a non-committed arm.

### B4: mutation-surviving gaps and missing tests the binding corrections required

Both of these code changes survive the 11-file WP08 test set:

| Mutant | Change | What it shows |
|---|---|---|
| MU2 | Writer back to the read-mode `_review_cycle_wp_dir` (no `write_dir`) | 145/145 pass. Every fixture is already MATERIALIZED, where `read_dir` and `write_dir` agree, so the single-home write contract (materialize or seed an EMPTY/UNMATERIALIZED surface, no PRIMARY substitution) is unpinned for review cycles. |
| MU7 | `workflow.py::review` back to the `_resolve_workflow_read_dir(WORK_PACKAGE_TASK) / "tasks" / wp_slug` hand-join | 145/145 pass. The binding correction for this routing (numbering restarts at 1, empty PRIMARY dir) has no test. |

**Required tests:**

- A coordination rejection where the coordination surface is UNMATERIALIZED or EMPTY when `move-task --to planned --review-feedback-file` runs. Assert an in-place write on the coordination worktree and an empty root `git status --porcelain -- kitty-specs/<dir>`.
- `agent action review` on a WP that has a prior coordination-surface cycle. Assert that the advertised feedback path is numbered N+1 and that no `tasks/<wp>/` dir is created in the PRIMARY root checkout.
- The binding correction's PUBLISHED case: one reject after consolidation, where REVIEW_CYCLE resolves to the target (D23). There is none.
- A pre-fix forked shape (an untracked, divergent coordination dir with no seed trailer) whose review-cycle write gets `CoordSeedForkRefused`. ff74a9800a moved the durability-matrix cells off that shape, which is fine, but the refusal and how move-task renders it are now pinned nowhere for review-cycle writes.
- T043 step 3, mark-status:
  - Assert that the root log gains nothing.
  - Assert that the new event comes after any carried events. Use `make_prefix_coord_mission(worktree="empty")` as the prompt specifies; the test uses `make_mission`, which is UNMATERIALIZED with no carry.
  - Add a remote-only Mission. It must render the refusal with its hint, not a traceback (T045 edge case).
- Parametrize the coordination scenarios over `coord` and `lanes_with_coord` (T043 step 1).

## Non-blocking

- **New suppressions.** `test_tasks_port_commit_outcome.py` adds two `# type: ignore[arg-type]` with no rationale (NFR-005). Make `_FakeCommitRouter` satisfy `CoordCommitRouter`, or `cast` with a one-line reason.
- **Lock ordering (binding correction: record the finding).** I verified it:
  - The verdict queue is a checkout-wide file lock (`<git-common-dir>/…/review-verdict-save.lock`), not the workspace lock.
  - Order is queue lease ⊃ `write_dir` seed status lock (bounded) ⊃ workspace lock, then the allocation status lock (bounded via `_in_queue_status_lock_timeout`), then the git commit.
  - No caller takes the lease while holding the status lock or the workspace lock. A `FeatureStatusLockTimeoutError` raised by the seed under the queue is translated by the existing `except FeatureStatusLockTimeoutError` arm (`tasks_verdict_persistence.py` ≈L507).
  - I-SEED-2 holds. The finding is not in the tracer; add it.
- **Your question (3) is moot.** `_ms_output` emits `status_events_path` and `status_snapshot_path` only for the owned arm, and WP08 did not change that arm; its value changed in WP07. `test_json_contract_enumeration` passes (126).
- **Coverage gap in the revert coordination arm.** `tasks_verdict_persistence.py:290/292/295` is uncovered in the unit and dir run; only the integration cells reach it. Optionally add a unit test.
- **Stated reason for not reusing `_porcelain_path`:** n/a (that was WP07).

## Verified (your questions)

1. **Unowned re-pin of `test_verdict_dir_co_resolution.py`: accepted.** Only the final literal changed, and the co-resolution assertion and the AST guard are untouched. It is still a working guard: reverting the reader default (MU1) turns `test_multi_consumer_co_resolution_under_coord_topology` red. The operator's flip decision makes the old PRIMARY literal necessarily stale. Record it as a deviation in the WP08 report, which you have done.
2. **Durability-matrix fixture: realistic.** A committed coordination surface that carries a seed trailer is the steady state a post-fix Mission reaches. The PRIMARY decoy is kept for the read-path cells. The pre-fix forked refusal is not covered for review-cycle writes; see B4.
3. Moot (above).
4. **Confirmed.** The WP08 prompt's binding corrections say "Drop the dead `tasks_mark_status.py:279` (`_ms_commit`) shim from scope (operator decision)", and T046 step 2 is struck through.
5. **Verified** (above).
6. **Fails.** See B2 and B3.
7. **Diff coverage is 95%, not 100%.** I measured against `7d473689c7` over 64 source lines with 3 missing (`tasks_verdict_persistence.py` 290, 292, 295). It passes the ≥90% gate.

## Red-first

I ran the final WP08 tests against base source:

- 3 failed: the in-place/no-residue test, the mark-status materialization test, and the reject-then-fix-mode test.
- 1 collection error: the outcome tests, because the helper does not exist at base.
- 2 passed as expected controls: second-cycle numbering and single_branch.

## Mutation evidence (11 files, 145 tests)

| Mutant | Result |
|---|---|
| MU1: reader default back to WORK_PACKAGE_TASK | 4 killed |
| MU2: writer read mode | **survives** |
| MU4: no masked-refusal check | 1 killed |
| MU5: no map-requirements render | 1 killed |
| MU6: mark-status non-owned back to `resolve_status_surface` | 1 killed |
| MU7: `workflow.review` PRIMARY join | **survives** |
| MU8: `_evidence_ref` against the repo root | 16 killed |

## Tests run (`-n 3 --dist loadfile`, tip `ff74a9800a`)

| Suite | Result |
|---|---|
| `tests/review/`, `tests/coordination/`, `tests/specify_cli/cli/commands/agent/`, plus 24 files elsewhere matching `review_cycle\|mark_status\|map_requirements\|has_prior_rejection\|…` (with `--cov`) | **1 failed (B1)**, 4245 passed, 21 skipped, 2 xfailed |
| `tests/integration/review/`, 16 integration files matching the grep, `test_rejection_cycle`, `test_review_durability_matrix`, `test_two_partition_preview`, plus 3 B1 guards | 189 passed |

Named gates, each run on its own:

| Gate | Result |
|---|---|
| layer_rules | 74 passed |
| no_write_side_rederivation | 27 passed |
| write_surface_placement_guard | 17 passed |
| merge_reconciliation_class_guard | 8 passed |
| status_events_writes_gate | 25 passed |
| ruff_format_exclude_ratchet | 6 passed |
| mission_resolver_walker_gate | 4 passed |
| destructive_op_routing | 37 passed |
| no_legacy_terminology | 96 passed |
| no_read_side_bypass | 38 passed |
| status_state_read_dir_single_authority | 13 passed |
| untrusted_path_containment | 12 passed |
| lifted_root_meta_fail_closed_census | 12 passed |
| exemption_registry_ratchet | 11 passed |
| json_contract_enumeration | 126 passed |
| no_worktree_name_guess | 17 passed |
| 2093_authority_invariant | 9 passed |
| single_mission_surface_resolver | 8 passed |
| no_dead_modules | 3 passed |
| wp_integrity_partition_call_shape | 5 passed |
| no_dead_symbols | 1 failed / 35 passed |
| dead_symbol_allowlist_contract | 1 failed / 3 passed |

Both dead-symbol reds are `COORD_SEED_TRAILER` only, which is allowed.

Static checks: ruff, `ruff format --check --force-exclude` and C901 are clean. `mypy --strict` reports no issues on the 6 changed source files, at both base and HEAD.
