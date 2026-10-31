# Discovery — activation writes under the charter synthesis lock (#6719)

## Decisions

### D-01 — Take the existing run-wide synthesis lock; do not invent a second one

The lock already exists for exactly this class of write: `charter.activation.synthesizer.synthesis_lock.synthesis_lock()`
(#6453). It is one lock per worktree, re-entrant per thread, dies with its holder, and
`charter synthesize` / `charter resynthesize` hold it from just after the soundness gate to the end of the
command (`synthesize.py:233`, `resynthesize.py:117`). `charter.activation.bundle_restamp.restamp_bundle_hash`
already wraps its manifest read-modify-write in it (`bundle_restamp.py:61`).

Evidence: the module docstring states the intent ("the one lock a writing run holds"), and #6719 was filed as
the residual of that mission after the operator ruled the remaining writers into their own issue rather than
widening #6453. A new "activation lock" would be a second source of truth for mutual exclusion over
`.kittify/charter/activation.yaml` and `synthesis-manifest.yaml`, i.e. exactly the defect #6453 fixed.

### D-02 — The invariant is "the activation config's read-modify-write is one unit", not "the write is atomic"

`prepare_yaml_write` / `apply_yaml_write` already write atomically (temp file + rename), and
`_save_ledger` refuses with `precondition_changed` when the file changed since its own read. Neither is
enough: the *read* that feeds the plan happens earlier (`resolve_activation_write_target`), so a concurrent
synthesis run that lands between that read and the write makes the later writer either lose the race loudly
(`precondition_changed`) or write a stale document. The lock has to span read → plan → write, which is a
window the command owns, not a single function.

### D-03 — Scope: the two writers the issue names, at the seams every caller shares

1. `ActiveCharterManager.activate` / `.deactivate` (`charter/activation/pack_manager.py`) — the single write
   entry point for `charter activate KIND ID`, `charter deactivate KIND ID` and every cascade child.
2. `apply_preset_plan` (`charter/activation/preset_application.py`) for `charter activate --preset`, where the
   plan is computed from a read the write must not outlive (`activate.py::_plan_and_apply_preset`).
3. `charter.activation.activation_engine.promote_activations` — the shared append-only primitive; `reach_only`
   already calls it under the lock from a synthesis run, but the interview/org-required promotion path
   (`org_charter._promote_org_required_to_config`) calls it unlocked.
4. `charter.activation.activation_ledger.apply_ledger_migration` — its manifest stamp
   (`_stamp_manifest`, read-modify-write of the whole `synthesis-manifest.yaml`) is the second writer the issue
   names. The lock spans the whole apply (ledger write → stamp → legacy-key strips) because the stamp's hash
   must describe the document the strips produce.

Not in scope (named in the PR's Deferred section if it remains): the compiled-catalog write
(`compiler.write_compiled_charter` / mission-type provisioning) reached from the post-write `recompile_or_notify`.
It reads the config after the RMW and is re-derived by the next synthesis run, so it is a staleness question for
a separate issue, not a lost-write one.

### D-04 — A held lock is a coded refusal, not a silent skip

`restamp_bundle_hash` degrades to a stderr warning when it cannot get the lock, because it is a post-write
adjustment inside a command that has already done its work. The writers above are the *command*, so they must
refuse: `CHARTER_SYNTHESIS_LOCK_HELD` (bounded 10 s wait, nothing written) and
`CHARTER_SYNTHESIS_LOCK_UNAVAILABLE`, rendered through the existing coded-error seam so `--json` keeps its
envelope. That matches `charter synthesize`, which renders the same codes via its
`KittyInternalConsistencyError` branch.

## Evidence

### E-01 — Reproduction on `main` at `6f73b2a98e`

Two writers on one migrated-shape project (`charter:` pointer, activation ledger seeded with
`activated_directives=[001-architectural-integrity-standard]`, `activated_tactics=[existing-tactic]`):

- writer S: `append_synthesized_activations(repo, {"tactic": ["new-tactic"]})` (what a synthesis run does),
- writer D: `ActiveCharterManager().deactivate(..., "directive", "001-architectural-integrity-standard")`,
  paused at its ledger commit while S completes.

Observed (pre-fix):

```
LEDGER: {'activated_directives': [...], 'activated_tactics': ['existing-tactic', 'new-tactic']}
ERRORS: [ValueError('precondition_changed: .../.kittify/charter/activation.yaml')]
```

The deactivation is not recorded and there is no `deactivated_directives` entry: the operator's deactivation
is lost, which is the issue's "synthesis puts the artifact back". The same window in the other order makes the
synthesis append fail with `precondition_changed` instead, killing a whole run.

### E-02 — Existing test conventions to reuse

- `tests/charter/synthesizer/test_synthesize_activation_append.py::_Handshake` — the deterministic
  two-writer handshake #6453 introduced: pause the first writer at its write, wait until the second is
  *provably* waiting on the lock (`kernel.locks._LockCore.try_lock_once` returns `False`), then continue.
- `tests/charter/synthesizer/test_synthesis_lock.py::hold_from_other_thread` — hold the lock from another
  thread (`synthesis_lock` is re-entrant on one thread, so same-thread holding proves nothing).
- `tests/charter/test_activate_restamps_bundle_hash.py::_project` — the migrated-shape fixture with a real
  synthesis manifest; `tests/_factories/activation_ledger.seed_activation_ledger` seeds activation state the
  way production writes it.
- `synthesis_lock._SYNTHESIS_LOCK_TIMEOUT_S` is read at call time, so a test can monkeypatch it to keep a
  refusal test sub-second.

## Open questions

- OQ-1 — Should the post-write catalog refresh (`recompile_or_notify`) be inside the same window? Decision:
  no in this mission (see D-03); the config RMW is the coherence unit, and a stale compiled catalog is
  re-derived. Recorded as a follow-up candidate rather than silently skipped.
- OQ-2 — Does any activation write path remain that is neither `promote_activations`, the manager, the preset
  applier, nor the migration? To be answered by a grep over `prepare_activation_write` /
  `resolve_activation_write_target` callers in the plan step.
