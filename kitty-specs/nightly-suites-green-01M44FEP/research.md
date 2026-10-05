# Research decisions: nightly suites green on main

Evidence for every decision is in [research/code-grounding.md](research/code-grounding.md).
No dependency is added, upgraded or removed, so the supply-chain controls do not apply.

## D1. Track A fix shape

- **Decision**: alias authority plus fold to one directory (operator rulings, 2026-10-05).
- **Rationale**: keeps the composed coordination directory that `5b5699e500` introduced, fixes the three failure layers with one rule, and restores the pre-regression end state of one directory on the target.
- **Alternatives considered**: one directory name keyed on the primary directory (no classifier change, but a read fallback for Missions seeded since 2 October); alias without the fold (leaves a split status log on the target); refusing the bare-slug shape (changes a documented contract).

## D2. Where the alias authority lives

- **Decision**: extend `src/specify_cli/missions/_read_path_resolver.py`; resolve once and pass names to pure classifiers.
- **Rationale**: that module already owns the directory composers and the primary metadata read; resolving in `mission_runtime` would grow an outbound ledger in a gate file this mission may not edit.
- **Alternatives considered**: a new module (a sixth composer); deriving the alias inside `mission_runtime/artifacts.py`.

## D3. Reconciliation exemption

- **Decision**: derive the composed name inside `_is_bookkeeping` from `planning_prefix`; for that name only, exempt coordination record kinds.
- **Amendment (2026-10-05, nested-prefix rule)**: the leg applies only when `planning_prefix` is nested (`<something>/kitty-specs/<alias>`) and `alias` differs from the Mission slug, and it exempts only a root-anchored three-segment path `kitty-specs/<alias>/<file>` of kind `STATUS_STATE`. A bare-slug coordination claim's prefix is always nested (measured: `.worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>`). For a root-form prefix the existing prefix leg already exempts the whole directory; that is pre-existing and unchanged. Second amendment (2026-10-05, after the test-design scrutiny): the leg's only proof is the `--strategy merge` variant of the reproduction; under squash with the fold it is unnecessary, so it is added only if that variant is red without it. The existing prefix leg is dead under coordination topology (its prefix is a worktree path no commit contains); that is a follow-up, not changed here.
- **Rationale**: the function exempts a whole subtree for the primary name; an unrestricted alias would exempt planning artifacts and source under the composed directory. No signature or call-site change keeps the edit clear of the approved-claim bound.
- **Alternatives considered**: threading the alias set through the claim object (edits outside the permitted function).

## D4. Performance measure

- **Decision**: ratio of the command median to a start-up floor median, interleaved in the same run; start-up against a fixed interpreter workload; a git-subprocess count pin as the clock-free signal.
- **Rationale**: in the grounding probe a delta doubled under load while the ratio moved from 1.34 to 1.51, matching six nightly runs; a planted slowdown landed at 1.82 or above. The count pin is exact and can run on pull requests.
- **Alternatives considered**: delta over the floor (still runner-bound); one wider absolute budget (the same test moves 1.7 times between nightlies); count proxies alone (blind to CPU slowdowns).

## D5. Limits are calibrated, not chosen in advance

- **Decision**: the ratio limits are set by the calibration spike in the plan and recorded in the Track B decision record with their headroom.
- **Rationale**: a figure of about 1.7 separates the grounding data but was measured on one machine with a possibly unclean floor command.
- **Alternatives considered**: fixing 1.7 now.

## D6. Recipe gate

- **Decision**: classify by command-line shape; move the gate to `tests/architectural/`.
- **Rationale**: 12 of 14 allowlist entries are log lines, the replay keeps all 11 historical recipes flagged, and the architectural jobs are selected for every `src/specify_cli` change without a registry edit.
- **Alternatives considered**: exempting strings that reach `help=` (a recipe in help text would pass); rewording the help (does not fix the class); promoting the 2,960-test directory to a shard (blocked by the nested-claim rule).

## D7. One-directory mechanism

- **Decision**: fold in the existing bookkeeping commit. After the union into the primary directory, `_phase_commit_and_assert` removes the composed directory's two status files from the target checkout, once every `event_id` in them is proven present in the primary log, and the existing bookkeeping commit carries the deletion.
- **Rationale**: the landed tree is fixed by the mission-branch squash, in a file another mission owns; the bookkeeping commit is the first point after it that this mission may edit, and it already runs through the single commit door and the rollback authority. A probe showed one directory and 8 event lines with the fold, and a failed, rolled-back reconciliation without it. The reproduction is switched to the real bookkeeping door (operator ruling 2026-10-05: replacing a mock of product code with the real path is allowed) and is the proof for the fold; measured there under squash: one directory, 1 `done` event, clean checkout, with no `_is_bookkeeping` change. The `_is_bookkeeping` leg (D3) is needed only under `--strategy merge`, where the per-commit axis flags the seed, fold and `done` status-transition commits.
- **Alternatives considered**: a deletion commit before the squash (removes the coordination home mid-run and re-seeds); seeding only when the coordination branch differs from the mission branch (48 of 50 Missions would have no status home); filtering the squash (only possible in a file another mission owns).

## Open items handed to implementation

- The floor command and throttle method (D5 spike).
- The one-directory mechanism is decided (D7); anything beyond the approved removal of the two status files, or an out-of-list file, is a stop condition.
- Whether `phase_bookkeeping.py:567` needs conversion (only with a red proof).
