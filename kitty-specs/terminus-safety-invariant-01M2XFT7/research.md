# Research — Terminus-Safety Invariant

Consolidated from the pre-spec research squad (root-cause), the architecture-alignment squad
(consolidation design + boundary hazards), and the post-spec adversarial squad (fakeability + scope).
All claims verified against `main` @ `207bbc1307` (v4.0.0rc4).

## Root-cause decisions

### #4764 — merge warn-mode consolidates+bakes unapproved lanes, no rollback
- **Decision**: add an UNCONDITIONAL merge-ready precondition in `merge/executor.py` `_phase_gates_and_state` (before `_phase_merge_lanes` consolidation), keyed on the terminal-lane invariant, NOT routed through `policy.mode`.
- **Rationale**: `MergeGateConfig.mode="warn"` (`policy/config.py:27`) makes the evidence gate non-blocking (`merge_gates.py:121`/`:53-54`), so `executor.py:380-382` never stops; consolidation (`:443`) + bake (`:506`) happen before the backstop fails (`done_bookkeeping.py:392`→`:497-503`) with no rollback. A precondition stops before any mutation — identical safety to `block` mode for this one invariant, while `warn` still legitimately softens evidence-QUALITY gates.
- **Alternatives considered**: rollback-only (rejected D2 — keeps the fail-open, unreviewed code still consolidates); reuse `is_mission_completed` (rejected D4 — false-blocks normal merges, vacuous on `--resume`).

### #4765 — mission close fabricates completion on an unmerged mission
- **Decision**: fail-closed `is_mission_merged(feature_dir)` guard at the top of `close_cmd`'s non-discard `else` (`mission_type.py:639`, before `_teardown_coordination_worktree` at `:644`); refuse with `Exit(1)` pointing at `--discard`.
- **Rationale**: the non-discard branch has zero preconditions today despite the docstring (`:514`); it commits a `runtime_post_completion` retrospective to the mainline via `coordination/teardown.py` and tears down the coord worktree. Mirrors the existing `reopen_cmd` guard (`:1362`, #1926). `is_mission_merged` (merged_at) — NOT `is_mission_completed` — because an all-terminal-but-unmerged mission must go via `--discard` (D4).

### #4474 — mission_number bake fail-opens on a merge-ready coord mission (distinct from #4764)
- **Decision (D7)**: FR-011 — make the bake write-back topology-aware (reach the primary-tree `meta.json`) OR surface the unbaked field as a queryable event + merge-summary line; never a silent log-only fail-open on a merge-ready mission.
- **Rationale**: `merge/ordering.py:398-414` composes the meta.json path inside the mission-branch tree and `return False` (skip, number lost, `doctor` stuck at `pending`) when it is absent — which on coord topologies it can be. This is the OPPOSITE failure mode from #4764 (which bakes too early → split-brain), so FR-006 does not cover it.

### #2745 — terminus half-termination + completion affordances (direct-on-target)
- **Decision (safety)**: refuse-before-advance guard on the direct-on-target path (`done_marked_before_target=False`, `executor.py:486`; done marked after target advance at `:971-985`); rollback-after-target-advance is the harder tail (D5).
- **Decision (affordances, D6)**: add `merge --skip-lanes`/`--no-lanes` transactional completion path (FR-012); mission-close orphan-branch tolerance + doubled-slug fix + `--json` (FR-013).
- **Facet-2 (accept guidance, FR-014)**: liveness confirmation — the protected-primary hard-reject was already removed (`accept.py:1007`); a red-first probe expected green-on-main.

## Consolidation design (single canonical authority)

- **Per-lane authority already single** — `status_lanes.is_acceptable_ending` (`:82`) + `has_operator_provenance` (`:114`); `status_lanes.TERMINAL_LANES` (`:26`). Keep.
- **Mission-level** — `status/lifecycle.py` `is_mission_merged` (`:294`), `is_mission_completed` (`:320`); facade-exported. Keep.
- **Missing aggregate** — no "is every non-cancelled WP at an acceptable ending?" reader; re-inlined ~9× (`merge_gates.py:166/314`, `done_bookkeeping.py:84`, `acceptance/gates_core.py:87`, `acceptance/summary_core.py:226`, runtime sites). **ADD** `mission_terminal_acceptability(work_packages) -> (ok, missing_wp_ids)` in `status_lanes.py` (pure, provenance-aware); reroute the three `specify_cli` terminus commands onto it; retire `doctor.py:28/:270` duplicate terminal-set. Runtime loops NOT rewired (layer ledger).
- **Coord-transaction rollback** — UNIFY `_capture_pre_target_coord_ref_sha` (`:553`), `_restore_and_guard_coord_coherence` (`:788`), `_revert_coord_done_commit` (`:644`) into one checkpoint primitive with named checkpoints (new pre-mutation + existing pre-done); reset coord ref on post-mutation failure.

## Adversarial evidence dispositions (per contracts/adversarial-evidence-contract.md)

| Finding (source) | Disposition | Where folded |
|------------------|-------------|--------------|
| Reusing `is_mission_completed` for merge false-blocks normal merges + vacuous on `--resume` (paula, alphonso) | **changed** | D4; merge uses merge-ready predicate; US1-3/US1-5 pin it |
| `is_mission_completed` vs `is_mission_merged` for close (paula vs alphonso divergence) | **changed** | D4 — `is_mission_merged` chosen (all-cancelled-unmerged must use `--discard`) |
| #4474 folded in name only; FR-006 doesn't touch the merge-ready fail-open (renata, priti) | **changed** | D7 / FR-011 added |
| #2745 is a 3-facet bundle; affordances unaddressed (renata, priti) | **changed** | operator D6 — FR-012/013/014 added |
| `--resume` vacuous-pass not pinned by a numbered scenario (renata) | **changed** | US1-5 added |
| cancelled-without-provenance negative unpinned (renata) | **changed** | US1-6 added |
| D5 interim refuse-before-advance had no clean scenario (renata) | **changed** | US3 split into rollback arm + refuse-before-advance arm |
| FR-009/US4 over-claimed repo-wide "no inline loops" (priti) | **changed** | scoped to the three `specify_cli` terminus commands |
| tidy-first sequencing hazard (enabler Medium behind High consumers) (priti) | **accepted** | FR-009 marked tidy-first enabler; IC-1 sequenced first in the dep graph |
| direct-on-target rollback-after-target-advance is a distinct hard seam (paula, alphonso) | **deferred_with_rationale** | D5 — own WP; refuse-before-advance interim guard keeps state safe if deferred |
| facade import + exception-type + layer-ledger + arch-battery re-pin hazards (paula, alphonso) | **accepted** | Technical Context constraints; per-WP validation notes |
| accept is genuinely gate-then-mutate (alphonso, priti confirm) | **accepted** | US4/FR-009 rely on accept as the precedent |

No contested finding dropped silently.

## Supply-chain security (DIR-051)

**N/A** — this mission adds/upgrades/removes **no** dependency (internal-module changes only). No registry/freshness/lifecycle-script surface to examine.
