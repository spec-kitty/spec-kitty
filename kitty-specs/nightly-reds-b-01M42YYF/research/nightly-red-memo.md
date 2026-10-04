# Nightly red memo — run 37177460494 (2026-10-04)

Newest nightly at time of writing: https://github.com/spec-kitty/spec-kitty/actions/runs/37177460494 (head `b2c466d7d1`). No newer nightly existed. Branch base: `skupstream/main` = `bc8d53d09` (26 commits after `b2c466d7d1`); every row below reproduces on that base.

Logs for the three jobs were read through the GitHub MCP job-log endpoint (the `gh run view --log` download is refused from the sandbox).

## Bisect

- The previous nightly (run 37094126479, head `a3f76f673`) had the **stress** and **integration + next** suites green. The integration-slice job did not exist yet (added by `8a956af88`).
- All five stress + integration reds pass at `5b5699e50^` and fail at `5b5699e50` ("give coordination artifacts one durable home", the 480-commit squash of the coord single-home mission). Command: worktree at each commit, `PYTHONPATH=<wt>/src pytest -n0 -m "" <ids>`.
- The integration-slice reds pre-date `5b5699e50`: they were never selected by any lane before the slice.

## Table

| Test id | Suite | Classification | Root cause | File to change |
|---|---|---|---|---|
| `tests/stress/test_concurrent_emits.py::test_concurrent_emits_produce_valid_event_log` | stress (#5610) | stale fixture | Fixture wrote no `meta.json`, so the placement seam degrades to PRIMARY and the coordination append is refused; with `meta.json` it also fails because `MID8="01J6STRSS"` is 9 chars, contradicting the single-derived `mid8 == mission_id[:8]` (FR-012, `mission_runtime/context.py`). `5b5699e50` added the same `_write_modern_meta` to the sibling unit tests in `tests/specify_cli/coordination/test_transaction.py` but missed this nightly-only file. | `tests/stress/test_concurrent_emits.py` |
| `tests/integration/test_placement_partition_golden_path.py::test_lifecycle_mutation_bookkeeping_lands_on_correct_surface[MissionTopology.COORD]` | integration (#5611) | stale fixture | Create now seeds and commits `status.events.jsonl` on the coordination branch (CHANGELOG #5440 entry; `core/mission_creation.py` `_commit_coord_create_events`), so the fixture's own `git commit -m "seed empty coord status log"` has nothing to commit. | `tests/integration/test_placement_partition_golden_path.py` |
| `tests/integration/test_coord_read_residuals_proof.py::test_executor_status_feature_dir_stays_coord_aware` | integration (#5611) | stale oracle | The executor's STATUS leg moved from `seam.read_dir(STATUS_STATE)` to `seam.write_dir(STATUS_STATE).path` (`consolidation/executor.py::_resolve_run_status_dir`, "WRITE accessor (ruling Q4, FR-003)"). The spy only watches `read_dir`, so it captures nothing (`None`). A pass-through `write_dir` spy captures exactly `ctx.coord_feature_dir`. | `tests/integration/test_coord_read_residuals_proof.py` |
| `tests/integration/test_owned_lifecycle_acceptance_finalize.py::test_armed_get_main_repo_root_pin_owned_finalize` | integration (#5611) | stale literal | `read_primary_meta`'s raw-miss fallback now routes through the shared `_canonicalize_primary_read_handle` (WP09 review cycle 2, the B1-residual fix), adding one `_compose_primary_feature_dir` read under `mission_has_coordination_branch` per status transaction (two transactions → +2: 16 → 18). Same entry frame, same leaf, a WHERE lookup. | `tests/integration/test_owned_lifecycle_acceptance_finalize.py` |
| `tests/integration/test_merge_lane_planning_data_loss.py::TestRetentionConstraintSurvivesCleanup::test_explicit_delete_override_still_reachable` | integration (#5611) | **product bug — operator decision, left red** | See "Stopped item" below. | — |
| `tests/init/test_init_idempotent.py::test_initialized_clone_vibe_pointer_recovery_and_repeat` | integration-slice (#5612) | product bug | `agent config sync` hits `continue` for an already-installed skill agent (`_skill_agent_already_installed`) before `_register_skill_agent` could rewrite the vibe pointer; introduced by `f4a2e63ed` (stop a normal sync rewriting pinned manifests). The pointer is gitignored and not part of the manifest. | `src/specify_cli/cli/commands/agent/config.py` |
| `tests/upgrade/test_mission_corpus_recovery.py` (9 tests) | integration-slice (#5612) | harness defect | The tests `git archive c0054153…` from the repository's own object store; the `integration-slice` job checks out with the default `fetch-depth: 1`. Every other job that runs this suite already sets `fetch-depth: 0` (`module-tests.yml`, `ci-router.yml`, the nightly architectural job, commit `6ce98087b`). Reproduced from a `git clone --depth 1`. | `.github/workflows/ci-nightly.yml` |
| `tests/characterization/test_trio_json_envelope.py::TestImplementRecoverJson::test_coord_mission_no_crashed_sessions` | integration-slice (#5612) | stale fixture | Since `2fd7eabf0` a coordination read on an unmaterialized coordination worktree fails closed by design. The `coord_repo` fixture never materializes it, while `mission create` does. The sibling accept test on the same fixture was already re-pinned to the refusal. | `tests/characterization/test_trio_json_envelope.py` |
| `tests/test_repo_root_status_guard.py::test_leak_attribution_does_not_straddle_into_the_next_test` | integration-slice (#5612) | harness defect | With `CI` set, pytest appends ` - <message>` to `-rA` summary lines; the nested-pytest parser's regex requires end-of-line after the node id, so the `ERROR` line is never seen (the job log shows `ERROR test_polluter.py::test_a_… - tests._support…RepoRootStatusArtifactLeak: …`). Reproduced locally with `CI=true`. | `tests/test_repo_root_status_guard.py` |

No row carries `@pytest.mark.regression` (checked per test).

## Stopped item (operator decision)

`test_explicit_delete_override_still_reachable` fails with `MERGE_UNSAFE_WORKTREE_DIRTY`: two untracked seed files in the coordination worktree. Chain: the consolidate executor resolves STATUS through `write_dir`, which seeds the composed `<slug>-<mid8>` coordination dir; `coord_seed._commit_seed` commits through `commit_for_mission(..., mission_slug=<bare slug>)`; `partition_for_mission_path` classifies by the `kitty-specs/<segment>` name and does not match `<slug>-<mid8>`, so the files regroup to PRIMARY, which is refused on protected `main`; the seed leaves the files untracked.

- The fixture itself is off-grammar (slug embeds the mid8 mid-string, and its declared `coordination_branch` is `kitty/mission-<slug>` rather than the composed `kitty/mission-<slug>-<mid8>`).
- But a realistic bare-slug shape (primary dir `retention-override`, branch `kitty/mission-retention-override-01KX0000`, the shape `coordination/transaction.py::_canonical_coord_mission_slug` documents as genuine) consolidates at `5b5699e50^` and fails at `bc8d53d09`: a real regression.
- A partition fix (recognise the composed coord dir in `partition_for_mission_path`) moves the failure one seam on: the reconciliation gate's `_is_bookkeeping` is anchored on the same bare segment and rejects `kitty-specs/<slug>-<mid8>/status.*` as un-attributable content, and the Mission would land a second Mission dir on the target.
- Widening a closed-world reconciliation exemption and deciding where a bare-slug Mission's coordination records land is a design decision, not a fold. Left red; the experimental partition patch is described in the hand-off.

## Out of scope (named by the brief)

PR #5617 (shard 3, out-of-matrix, performance e2e), #5614 (owned-checkout perf budget flakes) and #5353 (suite quality) are not touched.
