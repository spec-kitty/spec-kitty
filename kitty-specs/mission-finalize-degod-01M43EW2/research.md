# Research: Decompose mission_finalize god-module

## R-1 Module boundaries

- **Decision**: seven phase modules cut at the existing phase seams. The file was already organised in phase order: branch contract (L559–914), validation (L915–1561), bootstrap/ownership/local events (L1562–2358), planning pin (L2359–3568), lanes (L3569–3831), commit pipeline and rollback guards (L3832–4836). Constants and the `mission`-routed seams (L128–262) go into a shared `seams` module.
- **Rationale**: the boundaries match the phase helpers `finalize_tasks` already calls in sequence, and the extracted pieces are the units #5343 will turn into plan/apply steps.
- **Alternatives considered**: a `_finalize/` sub-package was rejected because it diverges from the sibling `mission_*.py` / `tasks_*.py` decomposition convention. A finer split (separate refresh and preserve modules) was rejected because they share the `PlanningCommitResolution` value and its report.

## R-2 Keeping test patches intercepting

- **Decision**: re-export every moved name from `mission_finalize`. Inside phase modules, call (a) every name a test patches on `mission_finalize` and (b) every function owned by another finalize module through a lazy in-function `from specify_cli.cli.commands.agent import mission_finalize as _mf`.
- **Rationale**: a test that patches `mission_finalize.X` only intercepts callers that look `X` up in `mission_finalize`'s namespace. This is the established seam-bridge idiom (`tasks_shared.py`, research D1 of mission `tasks-py-degod-wave2`). The lazy import is cycle-safe.
- **Alternatives considered**: (1) re-pointing every patch to the owning module. Rejected: there are about 60 patch sites, some patch a name used by both the command and a phase module, and it widens the diff without behavioural value. (2) Keeping the full pre-split import surface in `mission_finalize`. Rejected as clutter. Only names that tests reference are kept, found by an AST scan of `tests/` and `src/`.
- **Evidence**: an AST scan of every test that references the `mission_finalize` module found three non-defined names (`PinClass`, `classify_recorded_pin`, `detect_post_integration_acceptance`). They are re-exported, and `classify_recorded_pin` is routed.

## R-3 Logger identity

- **Decision**: `seams` defines `logger = logging.getLogger("specify_cli.cli.commands.agent.mission_finalize")` and every module imports it.
- **Rationale**: caplog filters and log routing key on the historical logger name.

## R-4 Source-reading pins

- **Decision**: add `tests/_support/finalize_source.py`, which concatenates the family's source and strips the `_mf.` qualifier, so whole-flow pins (`test_finalize_refresh_pin_authority`) read the family. Per-function pins are re-pointed at the owning module. The guard-capability scan gains the two moved `_bootstrap_canonical_state_via_mission` call-site modules, without which it would silently cover one of three.
- **Rationale**: a pin must keep watching the code it guards (spec FR-005, SC-003).

## R-5 Baseline reds

- `tests/integration/test_merge_lane_planning_data_loss.py::test_bare_slug_coord_mission_consolidates_onto_a_protected_target` fails on base `7c2dbd4e`. Unrelated.
- `tests/next/test_next_command_integration.py::TestNextCommandImplementState` (2 tests) fail only when co-scheduled under `-n 8` with the finalize corpus, and pass in isolation on both base and branch. They are classified during WP01 verification.
