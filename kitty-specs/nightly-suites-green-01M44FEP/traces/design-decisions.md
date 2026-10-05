# Design decisions: nightly-suites-green-01M44FEP

Running log of design choices and their rationale. Append dated entries of one to three sentences. Evidence is in `research/code-grounding.md`; the decisions are summarised in `research.md`.

## Decisions made before implementation (2026-10-05)

- **D1, Track A fix shape**: alias authority plus fold to one directory (operator rulings). It keeps the composed coordination directory introduced by `5b5699e500`, fixes the three failure layers with one rule and restores one directory on the target. Rejected: one directory name keyed on the primary directory; alias without the fold; refusing the bare-slug shape.
- **D2, where the alias authority lives**: `src/specify_cli/missions/_read_path_resolver.py`, resolved once and passed to pure classifiers. That module already owns the directory composers and the primary metadata read; resolving in `mission_runtime` would grow an outbound ledger in a gate file this mission may not edit. Rejected: a new module; deriving the alias inside `mission_runtime/artifacts.py`.
- **D3, reconciliation exemption**: derive the composed name inside `_is_bookkeeping` from `planning_prefix`; for that name only, exempt coordination record kinds. The function exempts a whole subtree for the primary name, so an unrestricted alias would exempt planning artifacts and source under the composed directory. No signature or call-site change. Rejected: threading the alias set through the claim object.
- **D4, performance measure**: ratio of the command median to a start-up floor median, interleaved in the same run; start-up against a fixed interpreter workload; a git-subprocess count pin as the clock-free signal. Rejected: delta over the floor; one wider absolute budget; count proxies alone.
- **D5, limits are calibrated**: the ratio limits are set by the calibration spike and recorded in the Track B decision record with their headroom. Rejected: fixing 1.7 in advance.
- **D6, recipe gate**: classify by command-line shape and move the gate to `tests/architectural/`. Rejected: exempting strings that reach `help=`; rewording the help text; promoting the 2,960-test directory to a shard.

## Operator rulings (2026-10-05)

1. Alias authority (decision `DM-01M44FNPQWA759DSQPAJRNTSGM`).
2. Move the recipe gate (decision `DM-01M44FNVCK8K5V0B60MVQTBS22`).
3. Alias plus fold to one directory (decision `DM-01M456JJB072M7V36XMYZXZSKX`).

## Entries

- 2026-10-05 (tasks): The refused-seed backstop's CLI-level test uses a Mission whose primary directory carries the composed name and a commit hook that rejects only the seed commit, so its result does not depend on the bare-slug misroute that WP02 removes.
- 2026-10-05 (tasks): The Track B decision record is written by WP05 (it holds the measured figures) but registered in the ADR index and page inventory by WP08, so the contended index files have one owner.
- 2026-10-05 (tasks): The resolver unit tests go in a new file `tests/specify_cli/missions/test_mission_dir_aliases.py`; the consolidation alias-consumer tests in a new file `tests/consolidation/test_bare_slug_alias_consumers.py`; the backstop tests in `tests/consolidation/test_refused_seed_commit_backstop.py`.
- 2026-10-05 (post-tasks design): D7, the one-directory mechanism, is a fold in the existing bookkeeping commit: the composed directory's two status files are removed after an event-preservation assert, with no new git argv and no run-state field. D3 is narrowed to a nested-prefix leg that exempts only the root-anchored status pair; it stays because the reproduction mocks the bookkeeping commit and `--strategy merge` checks each commit.
- 2026-10-05 (test-design scrutiny): The reproduction switches from `_real_merge_external_mocks` to the real-door helper and asserts the end state, by operator ruling that replacing a mock of product code is not test tampering; it becomes the proof for the partition fix, the teardown fix and the fold. The `_is_bookkeeping` leg moves after the fold and is added only if a `--strategy merge` variant is red without it; the separate sibling test is dropped.
- 2026-10-05 (implement, WP02): the directory alias equals what the seed's composer writes, gated only on one safe path segment. A canonical-shape check on the recorded mid8 was tried and removed: no writer normalises case or shape, so the check made the alias miss directories the seed really writes.
- 2026-10-05 (implement, WP03): the reconciliation leg exempts only the status pair directly under the composed name and is needed for `--strategy merge` only; with the leg in place the gate no longer backstops a skipped fold under squash, so the reproduction's one-directory assertion carries that.
- 2026-10-05 (implement, WP07): a printed recovery command must be proven in the failure context before it ships. A `spec-kitty safe-commit` recipe was refused on a protected target; both converted warnings now print the idempotent `mission close` re-run, and a Mission with no recorded identity is told to backfill first.
- 2026-10-05 (implement, WP06): the git-subprocess counts are pinned for the default drain posture (7 / 14 / 7). The forced-on posture of the test harness added four calls behind a wall-clock deadline.
- 2026-10-05 (implement, WP05): the owned-checkout limit (1.78) sits 8 percent above the largest clean local ratio and 4 percent below the smallest planted one; it is provisional until nightly runs on the branch report the ratios on the CI runner.
- 2026-10-05 (closeout): a stale fixture (`test_malformed_retention_value_is_treated_as_retaining`) was re-pinned to the composed coordination branch: 0 of 50 real coordination Missions declare an uncomposed branch, and the old shape was only green behind mocks.
- 2026-10-05 (closeout): the fold and the gate leg cover every coordination kind the seed carries (one shared predicate, `coordination/coherence.py::is_coordination_kind_file`). A file is removed from the target only when byte-identical to the primary directory's copy now or as the run found it; otherwise `ALIAS_FILE_NOT_PRESERVED`, nothing deleted, rollback.
- 2026-10-05 (closeout): one declared-mid8 core now serves `resolve_declared_mid8` and `mission_dir_aliases`; `mission_metadata.recorded_mid8` serves `mission close` and the retrospective warning.
- 2026-10-05 (closeout): the shared fixture constant `COORD_BRANCH` was re-pinned to the composed name on measured evidence: on the mainline an ordinary coordination write for the uncomposed shape already raises the branch mismatch, and no mint or migration path produces it.
