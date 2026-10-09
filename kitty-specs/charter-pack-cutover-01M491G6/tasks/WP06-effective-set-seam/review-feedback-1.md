# WP06 review feedback, round 1 (reviewer-renata)

Verdict: **changes requested**. The seam, the engine's fail-closed promotion and
the four promotion callers are correct and well tested. One blocker remains in
`ActiveCharterManager.activate()`: it is a regression against the WP base and
belongs to the #4400 failure class.

Base used for the before/after probes: `a8b52d7a` (parent of the red commit
`7f27fa7d`). Head: `bb985e3c`.

## 1. BLOCKER: the `activate()` fallback narrows what was effective in a multi-org-pack chain

`_preservation_set` (`src/charter/activation/pack_manager.py`, about lines 423-457)
falls back to `available` when the seam returns `resolved=False`. `available` is
`self.list_available(ctx, kind, layer_roots=layer_roots)`, and the CLI's
`layer_roots["org"]` holds only org pack #1. Org packs 2 and later that are
declared and readable are left out of the list it writes. Those packs are still
effective at runtime, so the first `charter activate <kind> <id>` deactivates
them. That is the #4253/#4400 failure.

The base helper `_chain_complete_available` scanned every declared org root it
could read (`is_dir()` filter), so it preserved them. The WP prompt (T-step 4)
says to "fall back to `available` exactly as today". The behaviour before WP06
was the union over the whole chain, not the truncated map.

Reproduction: three declared org packs `a`, `b`, `c`. `b`'s directory is
missing, so the seam is unresolved ("declared org pack root … is not a
directory"). `a` and `c` each ship one tactic. The key `activated_tactics` is
absent. Run `ActiveCharterManager().activate(ctx, "tactic", "org-a-tactic",
layer_roots=resolve_layer_roots(root))`:

| | base a8b52d7a | head bb985e3c |
|---|---|---|
| `org-c-tactic` effective before (activation-aware service) | yes | yes |
| `org-c-tactic` in the written `activated_tactics` | **yes** (123 ids) | **no** (122 ids) |
| `org-c-tactic` effective after | yes | **no** |

Head also emits two warnings that contradict each other: "The effective tactic
set could not be resolved …; initialized from the 122 available artifact(s)
instead." and then the engine's "Initialized from the 122 artifact(s) already
effective, so nothing in force was deactivated." The second one is false here.

The same narrowing happens whenever the seam is unresolved for another reason,
such as a service build failure or a scan error, while a readable org pack 2+
exists. The resynthesis preflight already fails closed in this case, but plain
`charter activate` (no `--resynthesize`) writes the narrowed list.

Required fix. Pick one and record the choice in the Activity Log:

- (a) **Fail closed in `activate()`.** When the set for an absent key is
  unresolved, raise a structured error before any write. The CLI exits 1 with
  the reason and says that nothing was written, which matches the resynthesis
  preflight's choice. This is the option most consistent with FR-015 / #4400.
  It overrides the WP prompt's "tolerant" wording, so say so in the log.
- (b) **Keep the tolerance, but make the fallback no narrower than the base.**
  Use the union of `list_available` over the built-in layer, the project layer
  and **every readable declared org root**. That is the old chain-complete
  scan, implemented once, for example as a seam-internal "best effort" mode
  rather than a second copy in `pack_manager`. Add the service keys when the
  service can be built. Do not emit the engine's "nothing in force was
  deactivated" warning when the fallback was used.

Add a regression test that pins this case: a three-pack chain with the middle
root missing, then `activate` on an absent key. Assert either that the pack-3
artifact is still effective after activation (b) or that the activation is
refused with config bytes unchanged (a). Also cover the service-build-failure
fallback, for example by monkeypatching `build_activation_aware_doctrine_service`
to raise while two readable org packs exist.

## 2. Non-blocking (fix while you are here): mission-type seeding now covers org pack #1 only

Commit `0b413398` makes `activate("mission-type", X)` on an absent
`mission_type_activations` key seed `sorted(available)`, where `available` comes
from the truncated `layer_roots`. With two org packs (mission types `mt-one` in
pack 1 and `mt-two` in pack 2) and the key absent:

- base writes `[documentation, mt-one, mt-two, plan, research, software-dev]`;
- head writes `[documentation, mt-one, plan, research, software-dev]`.

**This is not the #4400 class and not a blocker.** An absent
`mission_type_activations` key means **nothing** is in force
(`PackContext._read_activated_mission_types` returns `frozenset()`; it is
deliberately not "all", #2657/FR-008). No mission type that was effective
before is lost; pack 2's types were inactive both before and after. Even so,
the change has two defects:

- It makes the seeding asymmetric: org pack 1's mission types get activated as
  a side effect and pack 2's do not.
- The engine warning "Initialized from the 5 artifact(s) already effective, so
  nothing in force was deactivated" is factually wrong for this ledger. None of
  them were effective.

Choose one: seed from the whole chain (the same helper as option 1(b) restores
base parity), or seed only the requested id plus whatever is already in force.
Either way, suppress or reword the "already effective" warning for
`mission-type`. WP09 owns default-preset provisioning of
`mission_type_activations`, not single activation, so this stays with WP06. If
you decide to leave it, add a line to the Activity Log that says why.

## 3. Minor

- `m_unify_charter_activation` `dry_run` reports the promotions it would make
  but cannot report the keys that would be left absent, because it never
  resolves the seam. Consider resolving the seam in dry-run too, so the preview
  matches what a real run does. Optional.

## Verified as correct (no action)

- **The seam** (`charter.activation.effective_set.resolve_effective_sets`):
  - It unions the built-in layer, every declared org root and the project layer.
  - Directives stay in stem spelling.
  - An artifact whose id differs from its stem appears in id spelling. My probe
    with two org packs and the procedure `b-stem` / `b-declared-id` shows both
    spellings, and only the id spelling is what the filter needs.
  - The set is unresolved, with a reason, for a malformed registry, a missing
    org root, a build failure, or an empty set while built-ins ship.
  - `skill` is always unresolved, and `mission_type_activations` raises
    `ValueError`. Confirmed by tests and by my own probe.
- **`promote_activations` / `_plan_promotion`**: never writes an absent key
  whose set is unresolved, and reports it in `left_absent`. All four callers
  (interview, org-charter union, `m_unify_charter_activation`, resynthesis
  preflight) report left-absent keys or refuse. No other caller writes
  activation keys from `default.yaml`. `default.yaml` is now read only for
  `mission_type_activations` (provisioning).
- **Deleted symbols**: `merge_defaults`, `MergeResult`, `_load_default_pack`,
  `_chain_complete_available` and `_effective_ids_for_kind` have no aliases.
  The dead-symbol and dead-module gates are green. Interview imports
  `resolve_selected_id_to_stem` from `kind_vocabulary`. `m_unify_charter_activation`
  is `@MigrationRegistry.register`ed, so listing it as discovery-only
  (category 1) is legitimate.
- **Tests and checks**:
  - Acceptance suite: 107 passed, 1 skipped, 246 xfailed, 0 failed, 0 xpassed.
  - Targeted charter, CLI and upgrade tests: 1159 passed, 4 skipped.
  - `ruff check .` and `ruff format --check .` are clean.
  - mypy on the touched files: 4 errors, all pre-existing lines outside WP06 code.
- **Architectural gates**: all green except
  `test_remediation_effectiveness.py::test_case_table_matches_ast_derived_states`.
  That gate is also red on base `a8b52d7a`, and WP06 does not touch
  `computer.py`. It is not attributed to WP06.
