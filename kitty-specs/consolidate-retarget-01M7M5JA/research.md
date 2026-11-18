# Research: Consolidate retarget adopts the override target

Discovery notes (pre-spec): `research/discovery-tracked-issues.md`, `research/discovery-similar-surfaces.md`.

## Decisions

| Decision | Choice | Rationale | Alternatives considered |
|---|---|---|---|
| Opt-in | `--retarget` requires `--target` | Operator ruling Q1; keeps #7688 for a plain override | Implicit adoption on `--target` (weakens #7688) |
| Record timing | First mutation inside the rollback door; effective target in memory before the snapshot | Operator ruling Q2; the snapshot keys on the effective target | Rewrite inside the landing (bookkeeping would resolve the old target until then) |
| Record placement | The Mission branch copy (when present) AND the primary tree on `<b>` | The meta merge driver's two-way landing takes `target_branch` from the Mission side (spike + squad A1) | Change the driver to make `target_branch` target-authoritative (a C-002 semantics change, needs ADR); write `<b>` only (reverted by the landing) |
| lanes.json | Not rewritten | Read once and reseeded in memory; no reader after the landing; no merge driver | Rewrite with CAS (extra undo path and squash surface, no reader) |
| #5385 on a retarget | Probe re-pointed at `<b>` | Keeps the workflow mutation policy's own verdict (C-001) | Skip it and rely on #6464 (only `is_protected`, not the whole policy) |
| orchestrator-api | Refuses a retarget (no flag); text-only remedy update | Operator ruling Q5; no rollback door | Add `--retarget` without rollback |
| Default-topology Missions | IN scope (operator ruling 2026-11-17, "no follow-up"): the record is written on the topic (Mission) branch and carried by the landing | The landing reads the record from the Mission side | A follow-up issue (rejected by the operator) |

## Spike (2026-11-17, discarded)

On the #5783 lanes fixture, `develop` was cut from `main`, and `meta.json` (with `lanes.json`) was rewritten by hand to name `develop` and committed on `develop`. A plain `consolidate` then landed on `develop` and refused the `done` write with `STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH ... write branch 'main'`, then rolled back. The coord fixture landed with exit 0, because the coord Mission branch carries no `meta.json`. This confirms squad finding A1: the record has to be on the Mission branch as well.

## Post-plan squad (adversarial-squad-deployment, 2026-11-17)

The lenses were architect-alphonso (SOUND-WITH-CHANGES), reviewer-renata (ADEQUATE-WITH-CHANGES) and randy-reducer (TRIM). They converged on two findings: A1 was also witnessed by the spike, and R6 matches A6.

| # | Lens | Finding | Disposition | Evidence |
|---|---|---|---|---|
| A1 | architect | The two-way meta driver reverts a `<b>`-only retarget at the landing | accepted | plan D4 |
| A2 | architect | The claim's status surface resolves the old target on `lanes` | accepted | plan D3 |
| A3 | architect | `note_advance_intent` is infeasible; a kill between commit and persist is caught as `UNEXPLAINED_BRANCH_MOVE` | accepted (decorator; residual documented) | plan D4, D6; ADR amendment |
| A4 | architect | A full-restore re-baseline that drops the retarget strands a bare `--resume` | changed (keep it with `committed=False`) | plan D7 |
| A5 | architect | #6464 is not the same verdict as #5385 | accepted (re-point the probe) | plan D2 |
| A6 / R6 | architect, reducer | `lanes.json` rewrite unnecessary and risky | accepted (dropped) | plan D4 |
| R1 | reducer | Reuse `_primary_checkout_refusal` | accepted | plan D1 |
| R2 | reducer | Share the meta write and undo mechanics with the bake | accepted (mechanics only; the bake stays fail-open, the retarget fail-closed) | plan D4 |
| R3 | reducer | One bounded-history helper | accepted | plan D5 |
| R4 | reducer | One verdict for all three sites; keep each site's rendering | accepted | plan D1 |
| R5 | reducer | No new module; add the phase to `_SPAN_PHASES` | accepted | plan D7, Charter Check |
| T1 | renata | "Every S4 write" is partly vacuous on these fixtures (no gate matrix, no tombstones) | changed (SC-001 reworded to the observed rows; seam-level tests for the rest) | spec SC-001, plan IC-04 |
| T2 | renata | The retrospective is fail-open and outside the door, so exit 0 alone does not prove it | accepted (assert the file and its commit on `develop`) | test list below |
| T3 | renata | The retrospective already goes to the effective target (#7201), so it is a weak red witness | accepted (red witnesses are `done`, the flatten, and `meta.json` naming `develop`) | test list |
| T4 | renata | D2 is untested; the #5385 clause cannot be told apart from #6464 | accepted (protected-`main` retarget arm; unit test of the re-pointed probe) | test list |
| T5 | renata | Stale-record hazard after a full restore | accepted (fail → re-run arm) | test list |
| T6/T7 | renata | The injected-failure and kill seams are unnamed | accepted (the `_phase_merge_lanes` raise wrapper; kill at the persist seam) | plan IC-04 |
| T8 | renata | Fixture hides `<b>` ahead of `main` | accepted (divergent-`<b>` arm) | test list |
| T9 | renata | The FR-010 text and `CONTRACT_VERSION` are not asserted | accepted | plan D9 |
| T10 | renata | SC-004 leaves out the new codes | accepted | spec SC-004 |
| T11 | renata | NFR-003 budget is at risk (about 8 s per end-to-end run) | accepted (parametrise only where the topology matters) | test list |
| T12 | renata | `--push` / origin freshness not reachable in these fixtures | deferred_with_rationale: the fixtures have no origin; `--push` happens after the door and is unaffected by the record | — |

## Planned acceptance tests (end-to-end, `tests/terminus/test_consolidate_retarget.py`)

**Red-first witnesses on lanes and coord.** `--target develop --retarget` exits 0, and on `develop`:
- `meta.json` has `target_branch == develop`, one `retarget_history` entry, and `mission_number` set;
- on coord, the flatten has run (`flattened` / no `coordination_branch`);
- every WP is `done` on the status surface;
- `retrospective.yaml` is present;
- the commit subjects for done, retrospective and flatten are on `develop` and absent from `main`;
- the retarget commit is the first commit after the pre-run tip;
- `kitty-specs/` is clean;
- `main`'s tip and reflog are unchanged.

**Further arms:**
- Exactly one `retarget main -> develop` commit after the fresh run, after a fail → re-run, and after a resume.
- **Failure arm:** `_phase_merge_lanes` raises → `develop` is back at its pre-run tip, its `meta.json` names `main`, and the record keeps the retarget with `committed=False`. A re-run then exits 0.
- **Abort arm:** after the failure, `--abort` gives a full restore. A plain re-run without `--retarget` is then refused with the #7688 code.
- **Protection arms:**
  - a protected `develop` → `PROTECTED_BRANCH_REFUSED`, nothing moves;
  - a protected `main`, retarget to an unprotected `develop` → admitted.
- **FR-011 arms:** `develop` cut before the Mission existed, a dirty `meta.json`, and an untracked `meta.json` → `RETARGET_RECORD_UNWRITABLE`, nothing moves, with dry-run parity.
- **Divergent `<b>`:** `develop` carries its own commit and the run lands. The `_lanes` arm is enough here.
- **CLI validation:** `--retarget` alone exits 2; `--retarget-reason` alone exits 2; `--target main --retarget` makes no retarget commit.
- **Dry-run:** shows a `retarget` object, and gives the same code as the real run for each refusal arm.
- **Resume mismatch:** `RETARGET_RESUME_MISMATCH`, through a persisted record built with the state API.

## Operator ruling 2026-11-17 (relayed by the core triager) on the plan flags

- Flag 2 (default-topology Missions): **fold in, no follow-up.** Handled by the holder rule (plan D4/D10) and WP06.
- Flag 1 (a retarget away from a protected recorded target is admitted) and Flag 3 (the kill-window residual): no objection. Both are documented in the PR.

## Post-tasks squad (2026-11-17): planner-priti (READY-WITH-CHANGES), implementer-ivan (REALISTIC-WITH-CHANGES)

| # | Finding | Disposition | Evidence |
|---|---|---|---|
| P1 | Frontmatter dependencies empty | changed: finalize-tasks derived them from tasks.md (WP02←WP03←WP01, WP04/WP06←WP02, WP05←WP03) | finalize commit |
| P2 / I1 | The status-surface read lives in `run_state._capture_coord_checkpoint`, not in WP03's files | accepted | WP03 owned_files, T014 |
| P3 / I2 | Attestations write to the old target before the door on coordination-less Missions | changed: refuse `RETARGET_WITH_ATTESTATION_UNSUPPORTED` up front (reported to the operator) | WP03 T008.6, WP02 T009.6, contract |
| P4 | Contradictory owner for raising codes and call sites | accepted | WP01 T002/T003 |
| P5 | T008 persisted-record source ambiguous | accepted (loaded inside `_retarget_mode`) | WP03 T008.1 |
| P6 | The kill-arm patch point was only a suggestion | accepted (MUST be module-level) | WP03 T013.6 |
| P7 | Wrong path and helper names | accepted | WP02 T007, WP03 T012, WP04 T019 |
| P8 | C-006 single_branch arm missing | accepted | WP03 T017.2b, WP06 T026 |
| P9 | Parallelism lost | deferred_with_rationale: serial order kept; the executor keyword contract is simpler to keep honest in sequence | tasks.md |
| P10 | Census gate not named | accepted | WP01 T006.4 |
| I3 | The `committed` early return is unsafe after a partial rollback | accepted (idempotent mutate + history dedupe) | WP03 T013.2 |
| I4 | The retarget dict must reach `_locked` | accepted | WP03 T012.3 |
| I5 | More tests pin phase lists | accepted (`test_executor_rollback_wiring.py` owned by WP03) | WP03 T017.4 |
| I6 | The forecast's claim uses the old status surface | accepted | WP02 T009.5 (+ `claim_inputs.py` owned) |
| I7 | Simpler #5385 re-point keyword | accepted | WP01 T004 |
| I8 | Lane staleness when a lane touched `meta.json` | accepted as a risk with a pinning test | WP03 Risks |

## Operator ruling on P3 (attestations under a retarget), and the post-merge review folds

- **P3, superseded: option A.** The operator ruled that `--attest-*` flags follow the retarget instead of being refused. `RETARGET_WITH_ATTESTATION_UNSUPPORTED` was never defined; the plan (D10), the WP prompts and the analysis report that name it describe the rejected disposition. On a Mission without a coordination branch the attestation status events land on `<b>` (`contracts/cli-retarget.md`, Attestations).
- **Mission review RISK-2 (folded).** Those attestations are undone with the run: the one rollback authority restores `<b>` below them (`rollback.OwnMove.undo`, the snapshot `seed`).
- **Mission review RISK-1 (folded).** A persisted retarget binds every later run: any other target refuses `RETARGET_RESUME_MISMATCH`, with or without `--retarget`, and `orchestrator-api consolidate-mission` refuses every persisted retarget with the same code.
