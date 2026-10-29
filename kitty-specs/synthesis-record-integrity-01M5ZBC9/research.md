# Phase 0 Grounding — Synthesis record integrity

Base: `origin/main` @ `581b5c46` (2026-10-27).

## 1. Code grounding (cited lines re-verified)

The brief's line numbers predate #6442 (record generalized from tactics to every reach-only kind) and #6454 (fail closed on an unreadable manifest). Current locations:

| Issue | Brief cite | Current location | Notes |
|-------|-----------|------------------|-------|
| #6453 | `reach_only.py` record read-merge-write | `src/charter/activation/synthesizer/reach_only.py:264-289` (`append_synthesized_activations`: `_read_record` → merge → `_write_record`) | Record is now `.kittify/charter/synthesized-artifacts.yaml` (`:49`); legacy `synthesized-tactics.yaml` still read (`:50`). Only `atomic_write` protects the bytes. Callers: `src/specify_cli/cli/commands/charter/synthesize.py:546-548`, `resynthesize.py:209-211`. |
| #6453 | "existing charter/synthesis lock" | none exists | Confirmed by triage and by grep: no lock in `src/charter/`. Canonical primitive `kernel.locks.machine_file_lock`; placement precedent `kernel.event_log_append.event_log_lock_path` (`<git-common-dir>/spec-kitty-locks/<subdir>/<digest>.lock`, non-git sibling fallback, `*_LOCK_TIMEOUT` error with a code). |
| #6455 | warning `~48-50`, emitted `~134-135` | `reach_only.py:56-58` (`_UNREADABLE_RECORD_WARNING`), emitted `:266-267` | Names the file and suggests per-artifact activation; no repair step, no deletion caution. A missing file reads as empty (`_load_record_file`, `:86-87`). Test: `tests/charter/synthesizer/test_synthesize_activation_append.py:174-183`. |
| #6456 | `reconcile.py:~310`, reason `~224` | `reconcile.py:310-331` (`_is_legacy_applies`), `:393` (strip in `merge_project_overlay`, `topic_scoped` only), `:610`/`:620` (`_graph_level_refs` reports every synthesized source, no regenerated filter), reason `:224` | Since #6442 the same strip hits synthesized styleguides. Pinned by `tests/charter/synthesizer/test_synthesize_reconcile.py:899-931` and `test_styleguide_reach_only.py:471-488`. |

### Red-first reproductions (live, `.venv/bin/python`, script in session scratchpad)

- **#6453** — two threads call `append_synthesized_activations` with a barrier after `_read_record`; record starts `{t1}`, runs add `t2` and `t3`. Result: `['t1', 't3']` — `t2` lost. **RED confirmed.**
- **#6456** — `merge_project_overlay` full run, `tactic:untargeted` has a legacy `applies` edge, only `tactic:regen` regenerated. Result: no edge touching `tactic:untargeted` survives. **RED confirmed.**
- **#6455** — static: the warning text lacks repair and deletion guidance (`reach_only.py:56-58`). Red test lands with WP02.

## 2. Architectural alignment

- **ADR 2026-10-22-1** (Java write service is the canonical event writer): governs event-log rows (`status.events.jsonl` and similar). The created-artifacts record, the overlay and the manifest are charter YAML, not event logs. No overlap.
- **ADR 2026-10-16-1** (+ Amendment 2026-10-19): `charter.activation` stays in core until its post-GA rework; Python fixes there are in direction. The offering is replaced in place behind `charter.offering.api`; synthesis is under `charter.activation.synthesizer`, not the offering read seam.
- **ADR 2026-10-19-1** (activation ledger): synthesis appends to `activated_<kind>s` through `promote_activations` → the ledger; this mission keeps that path unchanged and only serializes it.
- **Epic #6518** (activation contract): maps activation state onto `ActivationConfig`. The created-artifacts record is "not an activation surface" (`reach_only.py:19-20`), so this work is not redone by that direction.
- **Epics #6117 / #6608, spec-kitty-events #92**: event writer / event contract work; no charter synthesis surface.

Verdict: nothing in scope is redone by the declared direction.

## 3. Related issues and in-flight work

- Open PRs touching synthesizer/synthesize/resynthesize: **none** (search 2026-10-27).
- #6454 merged (`a4474d16`, `73be5503`): this mission keeps its fail-closed fallback.
- Adjacent, out of scope: #6631 (commit reminder omits `synthesized-artifacts.yaml`, `synthesize.py`), #6510, #5452, #4226 (synthesize refusals), #6685 (interview fills absent activation key).
- Sibling sessions to avoid: #6715, #6675, #6193/PR #6716, events #92, M1 (`context_contract.py`/doctor), M3 (`pack_manager.py`/`resolver.py`), M4 (`decisions/`), M5 (status lanes), M6 (`issue_verdict`). This mission does not edit any of those files (`pack_manager.resolve_activation_write_target` is only called).

## 4. Tidy-first

- `merge_project_overlay` / `_graph_level_refs` use two different strip predicates (`topic_scoped`-gated vs. unconditional). A behaviour-preserving step threads `regenerated_urns` through `_graph_level_refs` before the behaviour change, so the fix is one predicate change.
- `reach_only.append_synthesized_activations` sits near the complexity ceiling; the lock is taken in a thin wrapper so the merge body stays unchanged.
