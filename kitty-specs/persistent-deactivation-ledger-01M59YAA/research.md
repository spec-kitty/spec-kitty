# Research: Persistent deactivation, one activation ledger

Inputs: spec.md (operator rulings), spec-kitty-charter ADR-0013, grounding scouts
(activation store; cascade/required; migrations/corpus; process), live code at
`core-align-3-persistent-deactivation` (= origin/main f1663393). Each decision lists the
alternatives considered.

## D-01 One seam module in `charter.activation`, one kernel floor holding the one resolver

**Decision** (revised, R2): the kernel module `kernel.activation_ledger_store` holds four things:

- the path constant;
- the raw YAML read (ruamel safe loader, after the `kernel.yaml_io` precedent);
- the legacy-scope ContextVar;
- **the only source resolver**, `resolve_activation_source(repo_root, *, legacy_keys)`, returning
  `LEDGER | LEGACY` or raising, with the pointer rule moved from `pack_context.py:306-334`.

The activation seam `charter.activation.activation_ledger` owns vocabulary, typed load, write,
the deny guard and `resolve_deny`. `pack_context` and the offering-side SPDD probe both call the
kernel resolver, and the probe's pointer replica (`spdd_reasons/activation.py:141-147, 171-184`)
is deleted.

**Why**: C-002 forbids `charter.offering` from importing activation, yet the SPDD probe must read
the ledger. Kernel is importable by every layer and already hosts charter knowledge
(`kernel.charter_pack_paths`). One resolver removes the second pointer implementation. The
vocabulary needs `ArtifactKind`, so it stays in activation, and the resolver takes the legacy key
set as a parameter.

**Alternatives**:

- (a) everything in kernel: the vocabulary cannot live there;
- (b) a raw reader in `charter.offering`: a core-owned store inside the package being extracted;
- (c) move the SPDD probe into activation: breaks the pure re-export facade `charter.spdd_reasons`;
- (d) a kernel plugin registry: hidden coupling;
- (e) the draft's `FRESH` enum member, which collapses into `LEDGER` with `exists=False` (R2).

## D-02 Keep the `(path, data, save)` write-target triple

**Decision**: `resolve_activation_write_target` keeps its exported shape and returns the ledger
triple. The ledger save takes a keyword `deny_change`, and `commit_plan` passes
`deny_change=plan.deny_change` (R1). The draft's `authorize_deny_write` binder is dropped.

**Why**: the shipped rc35 migration consumes the triple through `charter.activation.api` (C-001).

**Alternatives**: a new write-target object (breaks the shipped consumer); a second deny-only
writer.

## D-03 Upgrade-only legacy scope: kernel ContextVar, canonical-root aware, wide wrapping

**Decision** (revised, M3/M4): `legacy_activation_scope(repo_root, canonical_root=None)` records
the resolved and the canonical root, and `in_legacy_activation_scope` matches either.

It is entered by:

- `BaseMigration.__init_subclass__`, which wraps every public method a subclass defines in its own
  `cls.__dict__` whose first positional parameter is the project path: `detect`, `can_apply`,
  `apply`, and the rc6 `structural_detect` / `is_first_application` / `reselect_when_recorded`.
  The wrapper uses `functools.wraps` and is re-entrant;
- `MigrationRegistry.get_applicable` (`registry.py:87-130`);
- the runner's selection points (`runner.py:364`, `:573`);
- `spec-kitty migrate ledger` (`migrate_cmd.py:1773`);
- the `spec-kitty upgrade` command body.

`base.py` imports the scope from kernel directly.

**Why**:

- charter cannot import specify_cli;
- selection-time calls such as rc6 `structural_detect` turn exceptions into `True`, so a
  refusal outside the scope would silently re-select;
- readers canonicalise the root (`sync.py:102/:215`, `m_3_2_0rc35_unified_bundle.py:157`), so
  a worktree upgrade must match the canonical root.

**Alternatives**: an explicit parameter (edits shipped migrations); the runner only (misses
selection, direct callers and tests); an environment variable (leaks to subprocesses).

## D-04 Deny guard: a plain `deny_change` keyword, normalised compare (R1, P13)

**Decision**: `prepare_ledger_write(..., deny_change: DenyListChoice | None = None)` raises
`DenyListWriteRefused` when any deny key's **normalised** set (absent == `[]` == `null`) differs
before and after while `deny_change is None`. Legacy saves refuse a non-`None` value. The FR-014
static gate pins every call site passing non-`None`.

**Why**: the gate makes the guard structural. A minted token type with a private sentinel
(draft) adds ceremony without adding protection the gate does not already give. The normalised
compare stops a hand-edited `deactivated_x: []` from tripping non-explicit writers.

**Alternatives**: the draft's `ExplicitDenyChoice`/`_MINT` token (changed, R1); caller-stack
inspection; a second deny file.

## D-05 Effective deny = identity-resolved deny − strict required floor, computed once

**Decision** (revised, R3/R4/R5):

- `D* = resolve_deny(D) − R`, held as a `DenySet` (stems, declared ids, URNs);
- it is computed once in `PackContext.from_config`, only for kinds with a non-empty deny list;
- `R` comes from the one org-pack iterator, which gains provenance and one `extends:` walk.

The read is strict: an unreadable declared pack, a malformed `org-charter.yaml` or a bad
`extends:` chain raises `ActiveCharterConfigError`, after the `require_org_skill_policy_readable`
precedent (`org_pack_discovery.py:248`). It never widens.

**Why**:

- ADR-0013 Decision 2;
- NFR-003;
- the overlay and the exemption must agree;
- a silently empty floor would subtract a required artifact, and a silently skipped pack would
  let a required one be denied.

**Alternatives**: a parallel `_build_pack_set`/`_resolve_chain` provenance path (draft, changed:
two floors); lenient reading (changed); rewriting stale entries (forbidden writer).

## D-06 `PackContext` carries `denied` plus an effective-membership accessor

**Decision** (revised, M2):

- present allow lists are netted in identity space;
- absent lists stay `None`;
- the readers move onto `admits(kind, token)` / `effective_ids(kind, available)`.

Those readers are the resolver, the DRG filter, the compiler, the action governance bundle
(`_catalog_default_or_activated` `:53-91`, `_graph_and_catalog_default_ids` `:94`, `_seed_sets`
`:173`), the service builder, profile resolution, skill preparation, the invocation registry,
empty-charter, workflow executor, finalize bootstrap, tasks status, profiles and preflight.

A new gate (`test_no_raw_activation_membership.py`) forbids raw `activated_<kind> is None`
membership logic outside the seam.

**Why**: the draft's "enumerated absent-key consumers" missed about a dozen of them (M2). An
accessor plus a gate closes the class.

**Alternatives**: materialise "all minus deny" at construction (a catalogue scan); per-kind deny
fields.

## D-07 SPDD offering probe subtracts deny but not the required floor (residual)

**Decision** (unchanged, operator-accepted): the probe reads through the kernel resolver and
applies `allow and not deny`; the directive deny reuses `_is_directive_038` (m3). It applies no
org required floor.

**Why**: the floor lives in activation (C-002). The authority path (the resolver-served
context) applies it, and doctor warns on stale deny entries for required ids.

**Alternatives**: replicate the org scan in the offering (a second replica).

## D-08 Retire `NoActivationRestrictionsError`; one refusal seam for required (and later locked)

**Decision**: delete the class, its message and every catch site; deactivation always records
an exclusion; `check_deactivation_permitted` raises `RequiredArtifactDeactivationError`, a
`DeactivationRefused` subtype a later `locked` check can join.
**Why**: FR-007, C-008, out-of-scope note on ADR-0012.
**Alternatives**: keep the error for "required-only" kinds (skills) — the spec records a deny
entry for a non-required skill instead.

## D-09 Activating a denied id from an absent "all" list does not materialise

**Decision**: deny-only plan; the allow list stays absent (US1.4). For a "required" kind
(skill) the in-force set is materialised first, otherwise the id would not become effective.
**Why**: keeps new built-ins arriving (ADR-0013 "absent means all stays").
**Alternatives**: always materialise (#4253 path) — freezes the list for an id that only needed
its exclusion cleared.

## D-10 Cascade: keep the relation, flag `requires`, stop at denied nodes

**Decision** (operator ruling `cascade_walk_through_denied`, 2026-10-19): the adjacency keeps
`Relation`. `via_requires` is true when the source or a reached node has a `REQUIRES` edge to
the node. A denied node is skipped and reported, and **the walk stops there**. A node is still
reached when another path to it avoids every denied node. `--include-deactivated` restores the
full walk.
**Why**: nothing that is reachable only through an excluded artifact is reinstated behind the
user's back. The closure is the reachability set of the graph with the denied nodes removed,
which is still deterministic.
**Alternatives**: walking through a denied node (its children cascade silently); "all-REQUIRES
path" semantics (harder to explain).

## D-11 Cascade deactivation records only the named id

**Decision**: children removed with it lose only their present allow-list entry
(`record_exclusion=False`); required children are skipped naming the pack; C-005 shared-reference
skip unchanged; the cascade now runs even when the named id was implicit ("absent = all").
**Why**: FR-012, ADR-0013 Decision 3.

## D-12 Ledger migration: thin shell, re-runnable after a crash (P9)

**Decision**:

- **Identity**: `4.0.0rc8_activation_ledger`, `target_version = "4.0.0rc8"`, tracked partition,
  appended after `4.0.0rc7_track_charter_pack_yaml`. The logic is in
  `activation_ledger.plan_ledger_migration` / `apply_ledger_migration`, exported on the API by
  the migration WP.
- **Comparison**: order-insensitive, keeping all three states.
- **Refusal**: any two differing values refuse, including a stray `config.yaml` copy of a key
  the authority lacks (operator ruling `stray_config_copy`).
- **Apply order**: ledger write → strip `charter.yaml` → strip `config.yaml` → restamp. A re-run
  with a ledger present strips legacy keys **equal** to the ledger, so a crash at any point is
  recovered by re-running. Crash-injection tests sit between every write.

**Why**: the migration needs the vocabulary and both legacy readers. NFR-001 holds per refusal,
and partial progress is safe.

**Alternatives**: a hand copy of the key list (drift); a single atomic multi-file write (not
available across files); stripping first (loses data on a crash).

**Amendment (analyze pass 4, H1; operator ruling `dogfood_migration_path`)**: a narrow command,
`spec-kitty migrate activation-ledger`, exposes the same planner and apply functions without the
rest of the upgrade (FR-021). It records the migration as applied **only when a migration ledger
already exists** (binding: WP08 T051.2; with none, creating the file would drop `metadata.yaml`'s
history, so it records nothing and a later upgrade re-skips rc8 harmlessly). Why: this repository, like any project without a populated
migration ledger, would run its entire manifest under `spec-kitty upgrade`, so the dogfood and
any re-move after an older CLI wrote legacy keys again need a scoped path.

**Alternatives**: running the full upgrade here (rejected: 125/125 pending); calling the seam
from a throwaway script (rejected: not canonical, leaves no ledger record).

## D-13 Bundle: optional tracked member and optional hash member (M5, P14)

**Decision**:

- `CharterBundleManifest` gains `optional_tracked_files`;
- `tracked_files` is unchanged, because `charter bundle validate` (`charter_bundle.py:323-400`,
  `require_tracked=True`), `generate.py:645-655` and the shipped `m_3_2_0rc35_unified_bundle.py`
  treat it as "must be present";
- the ledger digest joins `compute_bundle_content_hash` only when the file exists, so an
  out-of-band edit is detected;
- writers keep restamping after a successful write;
- `test_bundle_file_lists_stay_in_sync` pins the freshness computer's copy.

FR-018's "a deny change marks the bundle stale" is dropped: a seam write restamps, so it never
reads as stale. The guarantee is detection of out-of-band edits. The P7 references filter keeps
a skipped recompile from leaking a denied artifact.

**Alternatives**: adding the ledger to `tracked_files` (draft, changed: breaks validate for every
ledger-less project and changes the shipped migration's output); a required hash member (stales
fresh projects).

## D-14 FR-014 gate: static classifier plus dynamic runs

**Decision** (revised, R12):

- a migration counts as **activation-touching** when it imports from `charter.activation` or names
  a ledger or activation key or path. Today that is 10 modules plus
  `_charter_pack_cutover_snapshots.py` (m4) plus the new one;
- each gets a fixture on which `detect()` is true, run with deny entries present and a byte check
  on disk;
- all other migrations are not applicable **by derivation** from the classifier, with no hand
  table;
- registry count == manifest count;
- every built-in preset is applied without `--force`;
- self-mutation tests prove non-vacuity.

**Why**: a reviewed hand table drifts; the classifier is the same predicate the gate enforces.

**Amendment (analyze pass 2, F8/H2/H3)**: deny entries exist only in a ledger. A pre-ledger-shaped migration is proven safe by ordering (it runs before `4.0.0rc8_activation_ledger`); every migration ordered after rc8 must be inapplicable or deny-preserving on a post-ledger fixture. **Revised in analyze pass 3 (M3)**: ledger-diff selection can re-select `skipped`/`failed` records and `reselect_when_recorded` migrations, so every activation-touching migration (including `m_3_2_x_normalize_activation_absence`) runs on a post-ledger fixture where it applies and must preserve the deny bytes; the ordering exemption is allowed only for a migration whose `detect()` is proven False on the post-ledger fixture. The withdrawn `MIGRATION_MOVE` choice is not introduced: the rc8 migration moves allow keys only and refuses a legacy `deactivated_*` key.

**Alternatives**: a detect-true fixture for all 125 migrations; static scan only; a `MIGRATION_MOVE` deny choice for the rc8 migration (withdrawn: it contradicts the `deny_writers` ruling).

## D-15 Fixture re-seeding with a red signal (R9; superseded by D0, post-tasks squad 2026-10-19)

**Decision** (revised, D0; **superseded at the flip by D-24**, `mission_pivot_option_b`): **in-Mission only**, the resolver has a tolerant mode (today's storage behaviour, the
default) and a strict test mode (never shipped), chosen by `kernel.activation_ledger_store.activation_strict()`,
which reads `SPEC_KITTY_ACTIVATION_STRICT` during the transition (`1` = strict, `test` = strict
plus a raise on stray legacy keys beside a ledger). One autouse fixture in `tests/conftest.py`
sets `test` for an explicit swept-prefix list; each of the three sweep WPs appends its trees in
the same commit as its re-seeding. The flip WP (D-24) does **not** make strict unconditional: it deletes the
variable, the hooks and the list, and ships the one-mode resolver (unmigrated reads stay legacy). No opt-out flag; class-A tests enter `legacy_activation_scope`.

**Amendment (analyze pass 2, H1/A2)**: every code WP lists each new test file by exact path in `SWEPT_PREFIXES` in the same commit; no test file references the variable except the kernel resolver test (rewritten by the flip WP); no WP adds a tolerant-mode-only test. This makes the flip's "no reference left in `src/` or `tests/`" check attainable.

**Amendment (analyze pass 3, M1/H2/H1)**: the mode is set by a `pytest_runtest_setup` hookimpl (`tryfirst=True`) and restored by `pytest_runtest_teardown`, so module- and session-scoped fixtures see the same mode as the test body. The first sweep WP's step 0 re-seeds every shared cross-tree activation helper so that it follows the mode (production provisioner or a mode-following factory helper); later sweeps never edit helpers. The two repository-reading tests move to the migration WP's dogfood commit.

**Why**: the earlier ContextVar override did not reach subprocess CLI tests or threads (F4),
ignored stray keys beside a ledger (F5), covered only 16 trees (F6), and the legacy save
refusing deny keys broke legacy-shaped fixtures from the deactivate WP on (F1). Tolerant mode keeps every WP
green; new behaviour is tested strict, on ledger fixtures.

**Alternatives**: the R9 constant + ContextVar override (replaced); per-tree conftest switches
(replaced by one swept list); an opt-out module flag (forbidden).

## D-16 No `schema_version`; unknown deny keys tolerated (P15)

**Decision**:

- no `schema_version` key;
- an unknown **non-deny** key refuses;
- an unknown `deactivated_<x>` key (from a later CLI with a new kind) is preserved verbatim,
  ignored by readers and reported as a doctor warning.

**Why**: an older CLI must not brick a project, or lose a newer exclusion, just because a kind
was added.

**Alternatives**: refuse all unknown keys (draft, changed); a version marker.

## D-17 Conformance table format

**Decision**: one YAML table (`activation-ledger-conformance/1`) with sections `effective_set`,
`identity`, `readers`, `cascade`, `deactivation` and `ledger_migration`, plus a Python runner.
There is no export script (operator ruling).

**Precedent**: Mission Status conformance (`tests/contract/_mission_status_conformance.py`). This
table is hand-authored because the answers are specified, not observed.

## D-18 Selection overlay gains `extends:`-inherited requirements (consequence of R3)

**Decision**: `_read_org_required_selections` reads the same `extends:`-walking iterator as the
floor.

**Why**: the floor subtracted from deny and the floor unioned into `selected_*` must be the same
set. This is a behaviour alignment and is recorded in the ADR and the changelog.

## D-19 `spec-kitty init` writes the ledger (B1)

**Decision**: `provision_default_mission_type_activations` (`default_charter.py:47-89`,
`init.py:1456`) goes through `compiler.provision_mission_type_activations` (existing baseline
row). `rendering_inputs` (`command_renderer.py:517-542`) lists the ledger as the provisioning
authority, which `validate_mission_provisioning` (`:545`), `assessment.py:127` and
`command_installer.py:887-895` compare against. The finalizer re-prepares provisioning after
migrations (m6). The `mission_creation_scaffold.py:147` message names the ledger.

**Why**: the init seed records every migration as applied, including rc8. A fresh project that
wrote `config.yaml` would therefore be "unmigrated" forever after the flip.

## D-20 Fail-open callers become fail-closed (P2)

**Decision**: `gate_bindings.py:238-251`, `mission_step_contracts/executor.py:593-608` and
`preflight/runner.py:221-224` let `ActiveCharterConfigError` propagate, as they already do for
`OrgPackEnvVarUnsetError`.

**Why**: swallowing the error means an unfiltered graph, which serves denied artifacts.

## D-21 Mission-step contracts, include selectors, references (P6, P7)

**Decision**:

- `drg_activation._node_is_activated` checks the per-id deny before the mission-type early return
  (`:419-425`);
- the executor's `get_by_action` pick (`executor.py:184`) is gated through `admits`;
- `build_charter_context_include` (`context.py:374-490`) gates every kind and renders a
  "deactivated" note for a denied selector;
- `reference_pointers` (`_load_references` `:247`, selection `:94-245`) drops denied targets.

**Why**: these were ungated paths that would serve a denied artifact. FR-016's reader list must
name them (spec wording).

## D-22 Late legacy writes after the ledger exists (P10)

**Decision**: when the resolver returns `LEDGER` and legacy activation keys sit beside it,
ordinary commands print one stderr warning per process naming the keys ("ignored; the ledger
wins"), and doctor reports `LEGACY_KEYS_PRESENT` as an error. A reconcile command is deferred,
and the PR body announces the cutover for open branches.

**Why**: an older CLI or a pre-cutover branch merge can write `charter.yaml` keys after rc8
settled. A silent ignore would surprise the user.

## D-23 Cascade deactivation under an absent allow list (P11)

**Decision**: children are rendered "still active (no allow-list; only <P> excluded)", with a
conformance row.

**Why**: FR-012 records no deny entry for children, so with "absent = all" nothing about them
changes, and the output must say so.

## Squad findings

Post-plan squad, 2026-10-19: architect-alphonso, researcher-robbie (code truth), randy-reducer
(simplification), paula-patterns (failure modes). The dispositions are the orchestrator's
binding ruling.

| ID | Finding | Disposition | Where folded |
|---|---|---|---|
| R1 | Token/sentinel deny guard is ceremony; use a plain `deny_change` keyword, gate-pinned; normalised compare | accepted (changed design) | D-04, IC-02, data-model §6 |
| R2 | One source resolver in kernel; SPDD pointer replica deleted; enum LEDGER/LEGACY | accepted (changed design) | D-01, IC-01, data-model §5 |
| R3 | One required-floor reader with provenance and one `extends:` walk; strict read | accepted (changed design) | D-05, D-18, IC-04, data-model §4 |
| R4/R5 | One identity-space deny subtraction (`resolve_deny`), computed once in `PackContext`; `deactivated_urns` derived; conformance rows for stem vs declared id | accepted | D-05, D-06, IC-05, data-model §2.1, §8 |
| R6–R8 | Re-slice: lean WP02; helpers/exports with their consumers; FR-018 out of WP02; split migration/doctor/gate; docs last; ~11–12 WPs | accepted | plan WP table (12 WPs) |
| R9 | Red signal during the sweep: refuse constant from WP02, per-tree strict conftest, flip deletes overrides | accepted | D-15, IC-01, IC-12, IC-13 |
| R10 | Reuse `ReferencedArtifact` for skipped entries | accepted | IC-07, data-model §7 |
| R11 | Compute reporting deltas from before/after deny lists | accepted | IC-04, data-model §3 |
| R12 | Doctor: one store-error code + LEGACY_KEYS_PRESENT + three warnings; drop `list_deactivated`; FR-014 non-applicability by static classifier | accepted | D-14, IC-09, IC-10, data-model §9 |
| B1 | `init` provisioning writes `config.yaml` while the init seed marks rc8 applied → new projects stuck after the flip | accepted (blocker) | D-19, IC-03, WP02, WP11 acceptance |
| M1 | Provisioning target must equal `rendering_inputs()[-1]`; include the ledger | accepted | D-19, IC-03 |
| M2 | Missed None-as-all readers; add a membership accessor and a gate | accepted | D-06, IC-05, IC-06 |
| M3 | Scope must match the canonical root (worktrees) | accepted | D-03, IC-01, IC-08 |
| M4 | Wrap all subclass public methods and the selection entry points; base.py imports kernel | accepted | D-03, IC-08 |
| M5 | `tracked_files` means "must be present"; use an optional-tracked field; pin the freshness list test | accepted | D-13, IC-09 |
| m1 | Keep `ACTIVATION_YAML_KEYS` order byte-identical; tuple pin | accepted | IC-02 |
| m2 | More `NoActivationRestrictionsError` sites (`pack_manager.py:50/78/859/887`) | accepted | IC-04 |
| m3 | SPDD directive deny reuses `_is_directive_038`; keep the early `False` (`:128-138`) | accepted | D-07, IC-02, IC-06 |
| m4 | `_charter_pack_cutover_snapshots.py` names activation keys: in the classifier | accepted | D-14, IC-10 |
| m5 | `DenyListChoice`/`RequiringPack` reach specify_cli via the API or `pack_manager.__all__` | accepted | IC-02, IC-04, data-model §4/§6 |
| m6 | `prepare_upgrade_repairs` prepares a legacy CAS write before migrations | accepted | D-19, IC-03 |
| m7 | Kernel follows the `yaml_io` precedent | accepted | IC-01 |
| anchors | compiler `:923`, `_load_governance_charter_config` `:291`, `_run_retired_governance_key_check` `:1101` (and others re-verified) | accepted | plan IC map |
| P1 | = B1 | accepted | — |
| P2 | Three fail-open `PackContext` callers | accepted | D-20, IC-06 |
| P3/P4 | = M2 (`_seed_sets` widening) | accepted | IC-05 |
| P5 | = R4 | accepted | — |
| P6 | Mission-step contracts bypass the per-id gate; executor picks ungated | accepted (gate both) | D-21, IC-05, IC-06 |
| P7 | Include selectors and unfiltered references rendering | accepted | D-21, IC-05 |
| P8 | = R3 strict read | accepted | — |
| P9 | Migration atomicity: ledger first, re-run strips equal keys, crash tests | accepted | D-12, IC-08 |
| P10 | Late legacy writes: warn once per command, doctor error; reconcile command | accepted; reconcile command **deferred_with_rationale** (no user demand yet; doctor plus the warning make the state visible; tracked for a follow-up issue) | D-22, IC-01 |
| P11 | Cascade-deactivation rendering under an absent allow list | accepted | D-23, IC-04 |
| P12 | Stop-at-denied needs an "unreached" bucket; total-partition invariant | accepted | D-10, IC-07, data-model §7 |
| P13 | = R1 normalised compare | accepted | — |
| P14 | FR-018: keep restamp; the ledger in the hash detects out-of-band edits; drop "marks stale" | accepted (spec wording) | D-13, IC-09 |
| P15 | Dogfood at the end of the migration WP; unknown deny keys tolerated | accepted | D-16, IC-08, plan resolved points 7 and 9 |
| operator | `cascade_walk_through_denied` → stop | accepted (ruling) | D-10 |
| operator | `stray_config_copy` → refuse | accepted (ruling) | D-12 |

## Supply chain (DIRECTIVE_051)

No dependency is added, upgraded or removed; no control applies.

## D-24 Mission pivot: the reduced flip (operator ruling `mission_pivot_option_b`, 2026-10-20)

**Decision**: Option B of the charter-contract impact plan
(`docs/architecture/activation-ledger-and-charter-contract.md`).
- **Kept**: WP07, WP08 (migration, `migrate activation-ledger`, dogfood), WP09 (bundle, doctor, plus FR-023), WP10 (gate, corpus, plus the FR-024 divergence register and both spellings), WP15 docs.
- **Canceled**: WP11–WP13.
- **Reduced flip, WP14**:
  - deletes the transition machinery;
  - legacy saves never carry deny keys;
  - fresh projects and `init` get the ledger;
  - deny writes on an unmigrated project refuse;
  - unmigrated reads stay on the legacy allow keys, the same answer as `main`, because no deny can exist there.
- **Moved to the epic** on milestone #11 (epic child #6535: retire the legacy activation reader): the strict fail-closed read and the full fixture sweep.

**Why**: the charter contract does not care where core stores state (`contract_document_scope`),
but C-003, the downgrade ruling and #66 still require deny keys never to land off the ledger. The
reduced flip gives that without the ~230-file sweep. The legacy reader is retired anyway when the
ACL lands.

**Holes closed in the reduced semantics** (WP14):
1. A `deny_change` with no deny delta must not refuse, or plain activate, `--force` and `--include-deactivated` would break on unmigrated projects.
2. Cascade deactivation refuses before any write (all-or-nothing).
3. No implicit ledger on an unmigrated project, which would strand legacy keys and widen.
4. The charter.yaml bootstrap allow-key copy stays.
5. The `CharterYaml` activation fields stay.
6. Legacy deny keys are never applied and are reported.

**Alternatives**: A (full flip with the sweep; costly, and drifts on a long-lived branch); C/C′
(ship tolerant mode; breaches C-003 and ships a hidden mode).

## D-25 Contract rulings carried by this Mission (2026-10-20)

**Decision**: `contract_rulings_r2_r12`, `required_always_active_divergence` and
`contract_epic_ga_milestone` are recorded. This Mission implements:
- R3 (#6423 in WP07);
- R6 (NFR-003 = no regression; #6506 tracks the budget);
- R12 (FR-023);
- the divergence register (FR-024).

R2's amendment and the reply to charter ADR-0020's "Requests to core" land in WP15's ADR
amendment. R4, R5 export, R9, R10 and R11 export are epic work.

**Amendment (2026-10-20, charter #125 answer to request 4)**: activate and deactivate are **aligned
with the contract**, not divergent. The contract's `select` clears the named id's own exclusion,
and `deactivate` records the exclusion and unselects, exactly as core's `charter activate` /
`charter deactivate` do. R8 stands, because the CLI verbs are kept, but it is now a pure 1:1
mapping and the adapter composes nothing. Both entries are removed from the divergence register
(FR-024, WP10, WP15, data-model §8).

